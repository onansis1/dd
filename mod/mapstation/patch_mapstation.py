"""Into the Dead: Our Darkest Days - 지도 스테이션 시작 슬롯 늘리기.
사용: python patch_mapstation.py <AssetBundles 폴더 경로> [슬롯수=2]
MapStationDefinition 의 레벨 1(시작 상태) m_numSlots 를 올린다. 이미 적용돼 있으면 아무것도 안 한다.
처음 실행할 때 data_balancing.mapbak 으로 백업한다. 게임을 끈 상태에서 실행할 것.
"""
import os, shutil, sys
import UnityPy.helpers.TypeTreeNode as T

_orig = T.TypeTreeNode.parse_blob.__func__
def _pb(cls, reader, version):
    reader.Position = reader.Position + 28
    return _orig(cls, reader, version)
T.TypeTreeNode.parse_blob = classmethod(_pb)

import UnityPy
from UnityPy.streams import EndianBinaryReader

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = os.path.join(sys.argv[1], "data_balancing")
    slots = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    if not os.path.isfile(path):
        sys.exit("data_balancing 을 찾을 수 없습니다: " + path)
    with open(path, "rb") as fh:
        data = fh.read()
    env = UnityPy.load(data)
    bundle = env.file
    name, sf = [(n, f) for n, f in bundle.files.items() if hasattr(f, "types")][0]
    raw = bytearray(sf.reader.bytes)
    flags = sf.flags

    target = None
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            tt = o.read_typetree()
        except Exception:
            continue
        if tt.get("m_Name") == "MapStationDefinition":
            target = (o, tt)
            break
    if target is None:
        sys.exit("MapStationDefinition 을 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있습니다).")
    o, tt = target
    d = tt["m_levelDefinitions"][0]["m_definition"]
    old = d["m_numSlots"]
    if old == slots:
        print("이미 적용돼 있습니다 (레벨 1 슬롯 = %d). 변경 없음." % old)
        return
    d["m_numSlots"] = slots
    new = o.save_typetree(tt)
    st = o.byte_start
    seg = bytes(raw[st:st + o.byte_size])
    if len(new) != len(seg):
        sys.exit("예상과 다른 데이터 구조입니다.")
    diff = [i for i in range(len(seg)) if seg[i] != new[i]]
    if not diff or max(diff) >= diff[0] + 4:
        sys.exit("예상과 다른 데이터 구조입니다.")
    bak = path + ".mapbak"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        print("백업 생성:", bak)
    raw[st + diff[0]:st + diff[0] + 4] = new[diff[0]:diff[0] + 4]

    r = EndianBinaryReader(bytes(raw))
    r.flags = flags
    bundle.files[name] = r
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(bundle.save(packer="lz4"))
    try:
        os.replace(tmp, path)
    except PermissionError:
        sys.exit("파일을 교체하지 못했습니다. 게임/스팀이 실행 중이면 끄고 다시 시도하세요. 새 파일은 " + tmp + " 에 있습니다.")
    print("지도 스테이션 레벨 1 슬롯: %d -> %d" % (old, slots))

if __name__ == "__main__":
    main()
