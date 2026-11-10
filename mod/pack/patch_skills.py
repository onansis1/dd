"""data_balancing: 생존자 스킬 트리를 티어(레벨)별로 섞어서 다시 나눠준다. 스토리와 얽힌 티어는 그대로 둔다.
사용: python patch_skills.py <data_balancing 파일> <data_config 파일> <출력 파일> [시드] [h2h] [noshuffle]
   h2h = 무술가(Trait+MartialArtist)/프로레슬러(Trait+ProfessionalWrestler) 특성을 가진 생존자의 4티어에 맨손격투 전문가(Trait+HandToHandExpert)가 오도록 맞춘다 (4티어 항목을 서로 맞바꿈)
   noshuffle = 섞지 않고(원래 스킬 트리 그대로) h2h 보정만 한다
 - 생존자마다 스킬 트리(SkillTreeData)는 4개 티어이고, 티어마다 선택지가 1~2개(m_firstChoice, m_secondChoice) 있다.
   각 티어끼리 모아서(1티어는 1티어끼리, 2티어는 2티어끼리 ...) 시드로 섞어 다시 나눠준다. 선택지가 1개인 티어는 그 구조(선택지 1개)가 그대로 따라간다.
 - 섞을 때, 그 생존자가 이미 가진 시작 특성(Trait+/Trait-)이나 같은 트리의 다른 티어와 겹치는 선택지가 가능한 한 적게 가도록 여러 번 시도해서 가장 좋은 것을 고른다.
 - 건드리지 않는 것: 파일럿용 임시 트리(TEMP_SkillTreeData), 비어 있는 트리, 영입/시작 데이터가 없어 얻을 수 없는 생존자(Jett/Julie/Norman)의 트리, 그리고 그 생존자를 지정해서 그 특성을 치료/부여/검사하는 스토리 액션·조건이 있는 티어.
 - 선택지는 16바이트 GUID 값을 그대로 옮기는 것이라 오브젝트 크기는 변하지 않는다. 진행 중인 세이브의 이미 고른 스킬은 세이브에 저장돼 있어 바뀌지 않는다(새 게임/새로 영입하는 생존자에게 적용).
"""
import sys, random, copy
import UnityPy.helpers.TypeTreeNode as T
_orig = T.TypeTreeNode.parse_blob.__func__
def _pb(cls, reader, version):
    reader.Position = reader.Position + 28
    return _orig(cls, reader, version)
T.TypeTreeNode.parse_blob = classmethod(_pb)
try:
    import UnityPy.helpers.TypeTreeHelper as _TTH
    _TTH.read_typetree_boost = None
except Exception:
    pass
import UnityPy
from UnityPy.streams import EndianBinaryReader

SRC, CFG, OUT = sys.argv[1:4]
SEED = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4].lstrip('-').isdigit() else None
FLAGS = set(a for a in sys.argv[4:] if a in ('h2h', 'noshuffle'))
FORCE_H2H = 'h2h' in FLAGS
NOSHUFFLE = 'noshuffle' in FLAGS
ZERO = b"\0" * 16


def guid_of(x):
    g = x.get("m_guid") if isinstance(x, dict) else None
    return bytes(g["bytes[%d]" % i] for i in range(16)) if isinstance(g, dict) and "bytes[0]" in g else None


def load(fn):
    env = UnityPy.load(fn)
    sc = {o.path_id: o.read().m_ClassName for o in env.objects if o.type.name == "MonoScript"}
    objs = []
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            t = o.read_typetree()
        except Exception:
            continue
        objs.append((o, t, sc.get(t["m_Script"]["m_PathID"])))
    return env, objs


cfg_env, cfg_objs = load(CFG)
bal_env, bal_objs = load(SRC)
trait_by_guid, trait_name_by_id = {}, {}
for o, t, c in cfg_objs:
    if c == "CharacterTraitDefinition":
        g = guid_of(t.get("m_guid") or {})
        if g:
            trait_by_guid[g] = t["m_Name"]
        trait_name_by_id[o.path_id] = t["m_Name"]
bal_name_by_id = {o.path_id: t.get("m_Name") for o, t, c in bal_objs}


def tname(g):
    return trait_by_guid.get(g, "?") if g and g != ZERO else None


surv = {}
for o, t, c in bal_objs:
    if c == "SurvivorData":
        g = guid_of(t.get("m_guid") or {})
        if g:
            surv[g] = t
trees = {}
for o, t, c in bal_objs:
    if c == "SkillTreeData":
        trees[o.path_id] = (o, t)
if len(surv) < 30 or len(trees) < 30:
    sys.exit("생존자/스킬 트리 정의를 충분히 찾지 못했습니다 (생존자 %d, 트리 %d). 게임 업데이트로 구조가 바뀌었을 수 있습니다." % (len(surv), len(trees)))

# 얻을 수 있는 생존자
obtainable = set()
for o, t, c in bal_objs:
    if c == "RecruitmentData":
        sg = guid_of(t.get("m_survivorGuid") or {})
        if sg:
            obtainable.add(sg)
    elif c == "StartingSurvivorsData":
        for x in t.get("m_startingSurvivors", []) or []:
            sg = guid_of(x)
            if sg:
                obtainable.add(sg)

# 스토리 쌍 (생존자 guid, 특성 guid)
story_pairs = set()
FIELDS = {
    "SpecifiedShelterCharacterHasTrait": ("m_specifiedCharacter", "m_trait"),
    "AddNewTraitToSpecifiedShelterCharacterAction": ("m_characterGuid", "m_traitGuid"),
    "TreatStateForShelterCharacterAction": ("m_characterGuid", "m_traitDefinition"),
}
for objs in (bal_objs, cfg_objs):
    for o, t, c in objs:
        if c in FIELDS:
            cf, tf = FIELDS[c]
            cg, tg = guid_of(t.get(cf) or {}), guid_of(t.get(tf) or {})
            if cg and tg:
                story_pairs.add((cg, tg))


def start_traits(t):
    names = set()
    for p in t["m_startingTraits"]:
        n = (trait_name_by_id if p["m_FileID"] else bal_name_by_id).get(p["m_PathID"], "?")
        if n.startswith("Trait"):
            names.add(n)
    return names


# 섞을 수 있는 (생존자, 트리) 와 티어별 고정 여부
people = []          # (생존자 이름, 트리 path_id, 시작 특성 이름 집합, 고정 티어 집합)
skipped = []
for g, t in surv.items():
    pid = t["m_skillTreeData"]["m_PathID"] if t.get("m_skillTreeData") and not t["m_skillTreeData"]["m_FileID"] else 0
    name = t["m_Name"].replace("Survivor_", "")
    if pid not in trees:
        skipped.append(name)
        continue
    to, tt = trees[pid]
    lv = tt["m_skillTreeLevels"]
    if g not in obtainable or "TEMP" in tt["m_Name"] or not any(guid_of(l["m_firstChoice"]) not in (None, ZERO) for l in lv):
        skipped.append(name)
        continue
    fixed = set()
    for i, l in enumerate(lv):
        for k in ("m_firstChoice", "m_secondChoice"):
            tg = guid_of(l[k])
            if tg and tg != ZERO and (g, tg) in story_pairs:
                fixed.add(i)
    people.append((name, pid, start_traits(t), fixed))
if len(people) < 25:
    sys.exit("섞을 스킬 트리가 너무 적습니다 (%d명). 게임 업데이트로 구조가 바뀌었을 수 있습니다." % len(people))

NT = 4
slots = {i: [] for i in range(NT)}          # 티어별로 섞을 (사람 번호)
entries = {i: [] for i in range(NT)}        # 티어별 원래 항목
for pi, (name, pid, st, fixed) in enumerate(people):
    lv = trees[pid][1]["m_skillTreeLevels"]
    for i in range(min(NT, len(lv))):
        if i in fixed:
            continue
        slots[i].append(pi)
        entries[i].append(copy.deepcopy(lv[i]))


def names_of(e):
    return [n for n in (tname(guid_of(e["m_firstChoice"])), tname(guid_of(e["m_secondChoice"]))) if n]


rng = random.Random(SEED)


def assignment():
    a = {}
    for i in range(NT):
        perm = list(range(len(slots[i])))
        rng.shuffle(perm)
        a[i] = perm
    return a


def cost(a):
    # 사람별로 최종 티어 구성을 만들어 겹침을 센다
    total = 0
    final = {}
    for pi, (name, pid, st, fixed) in enumerate(people):
        lv = trees[pid][1]["m_skillTreeLevels"]
        per_tier = []
        for i in range(min(NT, len(lv))):
            if i in slots and pi in slots[i]:
                e = entries[i][a[i][slots[i].index(pi)]]
            else:
                e = lv[i]
            per_tier.append(names_of(e))
        seen = set(st)
        for ns in per_tier:
            for n in ns:
                if n in seen:
                    total += 1
                seen.add(n)
        # 같은 사람 안에서 같은 선택지가 두 번 나오는 경우는 위에서 센다
    return total


best, best_c = None, None
if NOSHUFFLE:
    best = {i: list(range(len(slots[i]))) for i in range(NT)}
    best_c = 0
else:
    for _ in range(400):
        a = assignment()
        c = cost(a)
        if best is None or c < best_c:
            best, best_c = a, c
            if c == 0:
                break
base_c = cost({i: list(range(len(slots[i]))) for i in range(NT)})
if NOSHUFFLE:
    print("스킬 트리는 섞지 않음 (맨손격투 전문가 보정만, 생존자 %d명 대상)" % len(people))
else:
    print("스킬 트리 섞기: 생존자 %d명의 4개 티어를 티어끼리 섞음 (겹침: 원래 %d -> 섞은 뒤 %d)" % (len(people), base_c, best_c))
if skipped:
    print("섞기에서 뺀 트리: " + ", ".join(sorted(skipped)))
fx = [(n, sorted(i + 1 for i in f)) for n, _pid, _st, f in people if f]
if fx:
    print("스토리 때문에 고정한 티어: " + ", ".join("%s(%s티어)" % (n, "/".join(map(str, t))) for n, t in fx))

# 무술가/프로레슬러 특성을 가진 생존자의 4티어에 맨손격투 전문가가 오도록 맞춤 (4티어 항목을 서로 맞바꿈)
h2h_note = ""
if FORCE_H2H:
    H2H = next((g for g, n in trait_by_guid.items() if n == "Trait+HandToHandExpert"), None)
    if H2H is None:
        print("주의: Trait+HandToHandExpert 를 찾지 못해 맨손격투 전문가 보정을 건너뜁니다.")
    else:
        T4 = 3
        targets = [pi for pi, (name, pid, st, fixed) in enumerate(people) if ("Trait+MartialArtist" in st or "Trait+ProfessionalWrestler" in st)]
        def has_h2h(e):
            return H2H in (guid_of(e["m_firstChoice"]), guid_of(e["m_secondChoice"]))
        done, skipped_t = [], []
        for pi in targets:
            if pi not in slots[T4]:
                skipped_t.append(people[pi][0])        # 4티어가 스토리로 고정이거나 없음
                continue
            kt = slots[T4].index(pi)
            if has_h2h(entries[T4][best[T4][kt]]):
                done.append(people[pi][0] + "(이미 있음)")
                continue
            # 맨손격투 전문가가 있는 4티어 항목을 가진, 대상이 아닌 사람을 찾아 맞바꿈
            src = None
            for ks, pj in enumerate(slots[T4]):
                if pj != pi and pj not in targets and has_h2h(entries[T4][best[T4][ks]]):
                    src = ks
                    break
            if src is None:
                skipped_t.append(people[pi][0])
                continue
            best[T4][kt], best[T4][src] = best[T4][src], best[T4][kt]
            done.append(people[pi][0])
        h2h_note = "맨손격투 전문가 4티어 보장: " + (", ".join(done) if done else "해당 없음") + (" / 못 맞춘 사람: " + ", ".join(skipped_t) if skipped_t else "")
        print(h2h_note)

# 적용
changed = {}                    # path_id -> {tier: entry}
for i in range(NT):
    for k, pi in enumerate(slots[i]):
        e = entries[i][best[i][k]]
        pid = people[pi][1]
        orig = trees[pid][1]["m_skillTreeLevels"][i]
        if guid_of(e["m_firstChoice"]) != guid_of(orig["m_firstChoice"]) or guid_of(e["m_secondChoice"]) != guid_of(orig["m_secondChoice"]):
            changed.setdefault(pid, {})[i] = e

bundle = bal_env.file
sfs = {n: f for n, f in bundle.files.items() if hasattr(f, "types")}
assert len(sfs) == 1, list(bundle.files)
name, sf = next(iter(sfs.items()))
raw = bytearray(sf.reader.bytes)
want_all = {}
for pid, edits in changed.items():
    o, t = trees[pid]
    for i, e in edits.items():
        t["m_skillTreeLevels"][i] = e
    st = o.byte_start
    seg = bytes(raw[st:st + o.byte_size])
    nb = o.save_typetree(t)
    assert len(nb) == len(seg), "크기가 달라짐"
    d = [x for x in range(len(seg)) if seg[x] != nb[x]]
    assert d and len(d) <= 32 * len(edits), "예상과 다른 변경 범위"
    raw[st:st + len(seg)] = nb
    want_all[pid] = [(guid_of(l["m_firstChoice"]), guid_of(l["m_secondChoice"])) for l in t["m_skillTreeLevels"]]
r = EndianBinaryReader(bytes(raw))
r.flags = sf.flags
bundle.files[name] = r
data = bundle.save(packer="lz4")
env2 = UnityPy.load(data)
sc2 = {o.path_id: o.read().m_ClassName for o in env2.objects if o.type.name == "MonoScript"}
seen = 0
for o in env2.objects:
    if o.type.name == "MonoBehaviour" and o.path_id in want_all:
        t2 = o.read_typetree()
        got = [(guid_of(l["m_firstChoice"]), guid_of(l["m_secondChoice"])) for l in t2["m_skillTreeLevels"]]
        assert got == want_all[o.path_id], "검증 실패: " + t2["m_Name"]
        seen += 1
assert seen == len(want_all), "검증 실패: 일부 트리를 다시 읽지 못함"
open(OUT, "wb").write(data)
for pid in sorted(changed, key=lambda p: trees[p][1]["m_Name"]):
    o, t = trees[pid]
    print("  %-10s %s" % (t["m_Name"].replace("_SkillTreeData", ""), " | ".join("/".join(x.replace("Trait+", "+") for x in names_of(l)) for l in t["m_skillTreeLevels"])))
