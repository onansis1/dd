"""Into the Dead: Our Darkest Days - 영입 생존자 무작위 섞기.
사용: python shuffle_recruits.py <AssetBundles 폴더 경로> [시드]
data_balancing 의 일반 영입 16곳에 나올 생존자를 매번 무작위로 섞는다. 여러 번 실행해도 안전(매번 새로 섞음).
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
SLOTS = ["Aubrey", "Barb", "Bowman", "Candy", "Christine", "Frank", "Hudson", "Isabel",
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
    for s in SLOTS:
        if s not in surv:
            sys.exit("생존자 데이터를 찾지 못했습니다: " + s)

    rnd = random.Random(seed)
    while True:
        perm = SLOTS[:]
        rnd.shuffle(perm)
        if all(a != b for a, b in zip(SLOTS, perm)):
            break
    newof = dict(zip(SLOTS, perm))

    patched = 0
    for o, n, g in rows:
        slot = n.split("_")[0]
        if slot not in newof or n.startswith("Hostage_"):
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
    print("시드:", seed, "/ 수정한 영입 데이터:", patched)
    for s in SLOTS:
        print("  %s 장소 -> %s 등장" % (s, newof[s]))

if __name__ == "__main__":
    main()
