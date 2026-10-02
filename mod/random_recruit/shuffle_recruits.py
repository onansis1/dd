"""Into the Dead: Our Darkest Days - 영입 생존자 무작위 섞기.
사용: python shuffle_recruits.py <AssetBundles 폴더 경로> [시드]
data_balancing 의 영입 장소 11곳에 나올 생존자를 무작위로 섞는다 (여러 번 실행해도 안전, 매번 새로 섞음).
- 영입 결과(RecruitmentData)와, 장소 NPC를 켜고 끄는 조건(X_SurvivorExistence_NeitherList)을 함께 바꾼다.
  그래서 어떤 생존자를 영입하면 '그 생존자가 서 있는 장소'의 NPC가 사라진다 (원래 장소가 아니라).
- 장소 조건이 확인되지 않은 Candy/Christine/Frank/Vince 와 키 캐릭터 Bowman 은 섞지 않고, 이미 섞인 상태면 원래대로 복원한다.
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

# 섞는 대상: 장소 NPC 조건(X_SurvivorExistence_NeitherList)이 확인된 일반 영입 장소
SLOTS = ["Aubrey", "Barb", "Hudson", "Isabel", "Joe", "Kirk", "Lester", "Michelle", "Miguel", "Rahul", "Robbie"]
# 섞지 않음(키 캐릭터 / 장소 조건 미확인). 이미 섞인 상태여도 원래 생존자로 되돌린다.
KEEP = ["Bowman", "Candy", "Christine", "Frank", "Vince"]

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

    surv, rows, conds = {}, [], {}
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
        elif n.endswith("_SurvivorExistence_NeitherList") and "m_characterGuid" in tt:
            conds[n.split("_")[0]] = (o, gid(tt["m_characterGuid"]))
    for s in SLOTS + KEEP:
        if s not in surv:
            sys.exit("생존자 데이터를 찾지 못했습니다: " + s)
    for s in SLOTS:
        if s not in conds:
            sys.exit("장소 조건을 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있습니다): " + s)

    # 모든 장소가 원래와 다른 생존자가 되는 무작위 순열 (derangement)
    rnd = random.Random(seed)
    while True:
        perm = SLOTS[:]
        rnd.shuffle(perm)
        if all(a_ != b_ for a_, b_ in zip(SLOTS, perm)):
            break
    newof = dict(zip(SLOTS, perm))

    def set_guid(o, old, new, label):
        st = o.byte_start
        seg = bytes(raw[st:st + o.byte_size])
        if seg.count(old) != 1:
            sys.exit("예상과 다른 데이터 구조: " + label)
        p = st + seg.find(old)
        raw[p:p + 16] = new

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

    cond_n = 0
    for slot, (o, g) in conds.items():
        if slot in newof:
            want = surv[newof[slot]]
        elif slot in KEEP:
            want = surv[slot]
        else:
            continue
        if g != want:
            set_guid(o, g, want, slot + " 조건")
            cond_n += 1

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
    print("시드:", seed, "/ 수정한 영입 데이터:", patched, "/ 되돌린 데이터:", restored, "/ 장소 조건 수정:", cond_n)
    print("== 장소별 등장 생존자 ==")
    for s_ in SLOTS:
        print("  %s 장소 -> %s 등장" % (s_, newof[s_]))
    print("  (섞지 않음: %s)" % ", ".join(KEEP))

if __name__ == "__main__":
    main()
