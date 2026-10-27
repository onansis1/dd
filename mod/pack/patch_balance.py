"""Into the Dead: Our Darkest Days - data_balancing 수정을 한 번에 적용한다.
사용: python patch_balance.py <AssetBundles 폴더 경로> [총알배수=5] [가방칸수=24] [지도스테이션 시작 슬롯=2]
 - 총알 레시피(권총/리볼버/소총/산탄총/돌격소총, 제작 전문가 버전 포함) 산출량을 배수만큼 올린다 (재료는 그대로)
 - 모든 생존자(Survivor_*)의 가방 칸 수(m_inventorySize)를 지정값으로
 - 지도 스테이션 레벨 1 슬롯(MapStationDefinition)을 지정값으로
항상 처음 백업(data_balancing.origbak)에서 시작해 다시 계산하므로 여러 번 실행해도 배수가 누적되지 않는다.
게임 업데이트로 파일이 바뀌면(백업과 맞지 않으면) 경고를 내고 현재 파일을 새 기준으로 삼는다. 게임을 끈 상태에서 실행할 것.
"""
import os, re, shutil, sys
import UnityPy.helpers.TypeTreeNode as T

_orig = T.TypeTreeNode.parse_blob.__func__
def _pb(cls, reader, version):
    reader.Position = reader.Position + 28
    return _orig(cls, reader, version)
T.TypeTreeNode.parse_blob = classmethod(_pb)

# Windows + Python 3.14 에서 UnityPy 의 C 가속 모듈(UnityPyBoost)이 접근 위반(access violation)으로 죽는 문제 대응:
# 가속 모듈을 끄고 순수 파이썬 읽기 경로를 쓴다 (느리지만 결과는 같다).
try:
    import UnityPy.helpers.TypeTreeHelper as _TTH
    _TTH.read_typetree_boost = None
except Exception:
    pass
import UnityPy
from UnityPy.streams import EndianBinaryReader

def same_build(a_bytes, b_bytes):
    """두 데이터 번들이 같은 게임 빌드의 것인지(오브젝트 집합이 같고 크기가 같은 오브젝트는 내용도 같아야 한다)"""
    ea, eb = UnityPy.load(a_bytes), UnityPy.load(b_bytes)
    sa = [f for f in ea.file.files.values() if hasattr(f, "types")][0]
    sb = [f for f in eb.file.files.values() if hasattr(f, "types")][0]
    ra, rb = bytes(sa.reader.bytes), bytes(sb.reader.bytes)
    oa = {o.path_id: o for o in ea.objects}
    ob = {o.path_id: o for o in eb.objects}
    if set(oa) != set(ob):
        return False
    diff = 0
    for pid, x in oa.items():
        y = ob[pid]
        if x.byte_size != y.byte_size or ra[x.byte_start:x.byte_start + x.byte_size] != rb[y.byte_start:y.byte_start + y.byte_size]:
            diff += 1
    # 수정 대상(총알 레시피 10개 + 생존자 + 지도 스테이션)은 값만 다르고 크기는 같다. 바뀐 오브젝트가 많으면 다른 빌드로 본다.
    return diff <= 80

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    folder = sys.argv[1]
    ammo = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    inv = int(sys.argv[3]) if len(sys.argv) > 3 else 24
    slots = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    path = os.path.join(folder, "data_balancing")
    if not os.path.isfile(path):
        sys.exit("data_balancing 을 찾을 수 없습니다: " + path)
    cur = open(path, "rb").read()
    bak = path + ".origbak"
    data = cur
    if os.path.exists(bak):
        bd = open(bak, "rb").read()
        if bd != cur and same_build(bd, cur):
            data = bd
            print("원본 백업(data_balancing.origbak)을 기준으로 다시 계산합니다.")
        elif bd != cur:
            print("경고: data_balancing.origbak 이 현재 파일과 맞지 않습니다 (게임 업데이트?). 현재 파일을 새 기준으로 삼습니다.")
            shutil.copy2(bak, bak + ".old")
            shutil.copy2(path, bak)
    else:
        shutil.copy2(path, bak)
        print("백업 생성:", bak)

    env = UnityPy.load(data)
    bundle = env.file
    name, sf = [(n, f) for n, f in bundle.files.items() if hasattr(f, "types")][0]
    raw = bytearray(sf.reader.bytes)
    flags = sf.flags
    log = {"ammo": [], "inv": 0, "slot": None}
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            t = o.read()
            n = t.m_Name
        except Exception:
            continue
        st = o.byte_start
        seg = bytes(raw[st:st + o.byte_size])
        if re.fullmatch(r"\w*Ammo(_\w+)?_Recipe", n) and "Dismantle" not in n and ammo != 1:
            tt = o.read_typetree()
            if "m_exchangeData" not in tt:
                continue
            outs = [r for r in tt["references"]["RefIds"] if r["rid"] == tt["m_exchangeData"]["m_outputs"][0]["rid"]][0]["data"]["m_items"]
            g = outs[0]["m_itemDefinitionGuid"]["m_guid"]
            gb = bytes(g["bytes[%d]" % i] for i in range(16))
            cnt = outs[0]["m_count"]
            pat = gb + cnt.to_bytes(4, "little")
            if seg.count(pat) != 1:
                sys.exit("예상과 다른 데이터 구조: " + n)
            p = st + seg.find(pat) + 16
            raw[p:p + 4] = (cnt * ammo).to_bytes(4, "little")
            log["ammo"].append((n, cnt, cnt * ammo))
        elif re.fullmatch(r"Survivor_\w+", n):
            tt = o.read_typetree()
            if "m_inventorySize" not in tt:
                continue
            tt["m_inventorySize"] = inv
            new = o.save_typetree(tt)
            if len(new) != len(seg):
                sys.exit("예상과 다른 데이터 구조: " + n)
            d = [i for i in range(len(seg)) if seg[i] != new[i]]
            if d:
                if max(d) >= d[0] + 4:
                    sys.exit("예상과 다른 데이터 구조: " + n)
                raw[st + d[0]:st + d[0] + 4] = new[d[0]:d[0] + 4]
            log["inv"] += 1
        elif n == "MapStationDefinition":
            tt = o.read_typetree()
            old = tt["m_levelDefinitions"][0]["m_definition"]["m_numSlots"]
            tt["m_levelDefinitions"][0]["m_definition"]["m_numSlots"] = slots
            new = o.save_typetree(tt)
            if len(new) != len(seg):
                sys.exit("예상과 다른 데이터 구조: MapStationDefinition")
            d = [i for i in range(len(seg)) if seg[i] != new[i]]
            if d:
                if max(d) >= d[0] + 4:
                    sys.exit("예상과 다른 데이터 구조: MapStationDefinition")
                raw[st + d[0]:st + d[0] + 4] = new[d[0]:d[0] + 4]
            log["slot"] = (old, slots)

    r = EndianBinaryReader(bytes(raw))
    r.flags = flags
    bundle.files[name] = r
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(bundle.save(packer="lz4"))
    try:
        os.replace(tmp, path)
    except PermissionError:
        sys.exit("파일을 교체하지 못했습니다. 게임/스팀이 실행 중이면 끄고 다시 시도하세요. 새 파일은 " + tmp + " 에 저장돼 있습니다.")
    print("총알 레시피 %d개: x%d" % (len(log["ammo"]), ammo))
    for n, a, b in sorted(log["ammo"]):
        print("  %s %d -> %d" % (n, a, b))
    print("생존자 가방: %d명 -> %d칸" % (log["inv"], inv))
    print("지도 스테이션 레벨 1 슬롯: %s" % (("%d -> %d" % log["slot"]) if log["slot"] else "대상 없음"))

if __name__ == "__main__":
    main()
