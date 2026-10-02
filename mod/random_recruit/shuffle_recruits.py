"""Into the Dead: Our Darkest Days - 영입 생존자 무작위 섞기.
사용: python shuffle_recruits.py <AssetBundles 폴더 경로> [시드]
data_balancing 의 일반 영입 15곳(Bowman 제외)에 나올 생존자를 한 바퀴짜리 단일 순환으로 무작위로 섞고, 추천 영입 순서를 출력한다.
게임이 '영입한 생존자의 원래 장소 NPC'를 지우므로, 단일 순환 + 추천 순서를 따르면 15곳 중 14곳을 영입할 수 있다. 여러 번 실행해도 안전(매번 새로 섞음).
처음 실행할 때 data_balancing.bak 으로 백업한다. 게임을 끈 상태에서 실행할 것.
"""
import os, random, shutil, sys
import UnityPy.helpers.TypeTreeNode as T

# 빌드 6000.5.x 번들의 타입트리 헤더에 들어간 추가 28바이트를 건너뛰는 패치
_orig = T.TypeTreeNode.parse_blob.__func__
def _pb(cls, reader, version):
    reader.Position = reader.Position + 28
    return _orig(cls, reader, version)
T.TypeTreeNode.parse_blob = classmethod(_pb)

import UnityPy
from UnityPy.streams import EndianBinaryReader

# 섞는 대상 (일반 영입 장소). 인질/스토리 전용은 제외.
# 제외(키 캐릭터): Bowman. 이미 섞인 상태여도 원래 생존자로 되돌린다.
KEEP = ["Bowman"]
SLOTS = ["Aubrey", "Barb", "Candy", "Christine", "Frank", "Hudson", "Isabel",
         "Joe", "Kirk", "Lester", "Michelle", "Miguel", "Rahul", "Robbie", "Vince"]

def gid(g):
    return bytes(g["m_guid"]["bytes[%d]" % i] for i in range(16))

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    folder = sys.argv[1]
    path = os.path.join(folder, "data_balancing")
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else random.SystemRandom().randrange(1 << 30)
    if not os.path.isfile(path):
        sys.exit("data_balancing 을 찾을 수 없습니다: " + path)
    bak = path + ".bak"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        print("백업 생성:", bak)

    with open(path, "rb") as fh:   # Windows는 열린 파일을 덮어쓸 수 없으므로 메모리로 읽고 바로 닫는다
        data = fh.read()
    env = UnityPy.load(data)
    bundle = env.file
    name, sf = [(n, f) for n, f in bundle.files.items() if hasattr(f, "types")][0]
    raw = bytearray(sf.reader.bytes)
    flags = sf.flags

    surv, rows = {}, []
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            tt = o.read_typetree()
        except Exception:
            continue
        n = tt["m_Name"]
        if n.startswith("Survivor_") and "m_inventorySize" in tt:
            surv[n[9:]] = gid(tt["m_guid"])
        elif "m_recruitmentId" in tt and "m_survivorGuid" in tt:
            rows.append((o, n, gid(tt["m_survivorGuid"])))
    for s in SLOTS + KEEP:
        if s not in surv:
            sys.exit("생존자 데이터를 찾지 못했습니다: " + s)

    # 게임은 '영입된 생존자'의 원래 장소 NPC를 지운다. 장소 X를 쓰면 생존자 newof[X]를 영입하고 newof[X] 장소가 사라진다.
    # 모든 장소를 한 바퀴짜리 단일 순환으로 잇고, 추천 순서대로 영입하면 15곳 중 14곳을 영입할 수 있다(손실 1).
    rnd = random.Random(seed)
    cyc = SLOTS[:]
    rnd.shuffle(cyc)
    L = len(cyc)
    newof = {cyc[i]: cyc[(i + 1) % L] for i in range(L)}
    order = [cyc[L - 1 - j] for j in range(L - 1)]   # 마지막 cyc[0] 장소는 영입 불가

    patched = 0
    restored = 0
    for o, n, g in rows:
        slot = n.split("_")[0]
        if n.startswith("Hostage_"):
            continue
        if slot in KEEP:
            if g != surv[slot]:
                st = o.byte_start
                seg = bytes(raw[st:st + o.byte_size])
                if seg.count(g) != 1:
                    sys.exit("예상과 다른 데이터 구조: " + n)
                p = st + seg.find(g)
                raw[p:p + 16] = surv[slot]
                restored += 1
            continue
        if slot not in newof:
            continue
        st = o.byte_start
        seg = bytes(raw[st:st + o.byte_size])
        if seg.count(g) != 1:
            sys.exit("예상과 다른 데이터 구조: " + n)
        p = st + seg.find(g)
        raw[p:p + 16] = surv[newof[slot]]
        patched += 1

    r = EndianBinaryReader(bytes(raw))
    r.flags = flags
    bundle.files[name] = r
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(bundle.save(packer="lz4"))
    try:
        os.replace(tmp, path)
    except PermissionError:
        sys.exit("파일을 교체하지 못했습니다. 게임/스팀이 실행 중이면 끄고 다시 시도하세요. 새 파일은 "
                 + tmp + " 에 저장돼 있습니다.")
    print("시드:", seed, "/ 수정한 영입 데이터:", patched, "/ 되돌린 데이터:", restored)
    lines = []
    lines.append("== 장소별 등장 생존자 ==")
    for s_ in SLOTS:
        lines.append("  %s 장소 -> %s 등장" % (s_, newof[s_]))
    lines.append("")
    lines.append("== 추천 영입 순서 (이 순서대로 하면 15곳 중 14곳 영입 가능) ==")
    lines.append("게임이 '영입한 생존자의 원래 장소 NPC'를 지우기 때문에, 순서를 어기면 영입 가능한 수가 줄어듭니다.")
    for i, s_ in enumerate(order, 1):
        lines.append("  %2d. %s 장소 -> %s 영입" % (i, s_, newof[s_]))
    lines.append("  영입 불가: %s 장소 (%s 생존자는 장소에서 영입할 수 없음)" % (cyc[0], newof[cyc[0]]))
    text = "\n".join(lines)
    print(text)
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "recruit_order.txt"), "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print("\n(위 내용은 recruit_order.txt 에도 저장됨)")
    except OSError:
        pass

if __name__ == "__main__":
    main()
