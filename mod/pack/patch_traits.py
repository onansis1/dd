"""data_balancing: 모든 생존자(이름 있는 38명)의 시작 특성(양성 1개 + 음성 1개)을 섞어서 다시 나눠준다. 스토리와 얽힌 특성은 그대로 둔다.
사용: python patch_traits.py <data_balancing 파일> <data_config 파일> <출력 파일> [시드]
 - 각 생존자 정의(SurvivorData)의 m_startingTraits 에는 'Trait+...'(양성)과 'Trait-...'(음성)이 하나씩 있다. 고정되지 않은 칸의 양성끼리, 음성끼리 모아서 시드로 섞은 뒤 다시 나눠준다(특성 종류와 개수는 그대로라 한 특성이 여러 명에게 겹치지 않는다).
 - 다음 칸은 고정한다 (스토리/조건에 쓰이는 특성):
     (1) 그 생존자를 지정해서 그 특성을 치료/부여/검사하는 스토리 액션·조건이 있는 칸 (치료 이벤트 'Treat_...', 'Give_...', 'SpecifiedShelterCharacterHasTrait' 등)
     (2) 그 생존자의 영입 데이터(RecruitmentData)가 직접 가리키는 특성
     (3) 파일럿(쿠퍼의 능력), 체프웨이즈 직원, '시나리오 모드' 전용 특성 같은 스토리 특성
   MI_/State_ 로 시작하는 것(개 애호가, 시작 경험치 등)은 건드리지 않는다.
 - 맨손 격투 능력은 특성이 아니라 생존자에게 지정된 맨손 무기(m_innateEquipment)가 만든다: Hao 는 SurvivorUnarmedMartialArts_WeaponDefinition, Isaiah 는 SurvivorUnarmedBrutal_WeaponDefinition, 나머지는 SurvivorUnarmed_WeaponDefinition. 그래서 'Trait+MartialArtist'를 받은 생존자에게는 MartialArts 무기를, 'Trait+ProfessionalWrestler'를 받은 생존자에게는 Brutal 무기를, 둘 다 없으면 기본 맨손 무기를 같이 준다(특성과 능력이 함께 움직임).
 - 영입 데이터나 시작 생존자 쌍에 한 번도 나오지 않는 생존자(게임에서 얻을 수 없는 사람, 예: Jett/Julie/Norman)는 섞기에서 뺀다(그들에게 특성이 가서 낭비되지 않게).
 - 참조(PathID 8바이트)만 바뀌므로 오브젝트 크기는 변하지 않는다. 이미 진행 중인 세이브의 생존자 특성은 세이브에 저장돼 있어서 바뀌지 않는다(새 게임/새로 영입하는 생존자에게 적용).
"""
import sys, random
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
SEED = int(sys.argv[4]) if len(sys.argv) > 4 else None
STORY_NAME_PARTS = ("Pilot", "Chiefways", "ScenarioMode")


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
trait_by_guid = {}
trait_name_by_id = {}
for o, t, c in cfg_objs:
    if c == "CharacterTraitDefinition":
        g = guid_of(t.get("m_guid") or {})
        if g:
            trait_by_guid[g] = t["m_Name"]
        trait_name_by_id[o.path_id] = t["m_Name"]
bal_name_by_id = {o.path_id: t.get("m_Name") for o, t, c in bal_objs}


def trait_name(p):
    return (trait_name_by_id if p["m_FileID"] else bal_name_by_id).get(p["m_PathID"], "?")


surv = {}                       # 생존자 guid -> (object, typetree)
for o, t, c in bal_objs:
    if c == "SurvivorData":
        g = guid_of(t.get("m_guid") or {})
        if g:
            surv[g] = (o, t)
if len(surv) < 30:
    sys.exit("생존자 정의를 충분히 찾지 못했습니다 (%d명). 게임 업데이트로 구조가 바뀌었을 수 있습니다." % len(surv))

# 맨손 무기 PPtr 모으기 (생존자 정의의 m_innateEquipment 안에 있는 것을 그대로 복사해서 쓴다)
UNARMED = {"base": "SurvivorUnarmed_WeaponDefinition", "martial": "SurvivorUnarmedMartialArts_WeaponDefinition", "brutal": "SurvivorUnarmedBrutal_WeaponDefinition"}
unarmed_ptr = {}
unarmed_names = set(UNARMED.values())
for g, (o, t) in surv.items():
    for p in t.get("m_innateEquipment", []):
        n = bal_name_by_id.get(p["m_PathID"]) if not p["m_FileID"] else None
        for k, v in UNARMED.items():
            if n == v and k not in unarmed_ptr:
                unarmed_ptr[k] = dict(p)
WEAPONS_OK = len(unarmed_ptr) == 3
if not WEAPONS_OK:
    print("주의: 맨손 무기 정의 3종을 모두 찾지 못해 무기는 옮기지 않고 특성만 섞습니다 (%s)" % sorted(unarmed_ptr))

# (1) 스토리 액션/조건: (생존자 guid, 특성 guid) 쌍
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
# 게임에서 실제로 얻을 수 있는 생존자: 영입 데이터(RecruitmentData)나 시작 생존자 쌍(StartingSurvivorsData)에 나오는 사람만
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
skipped = sorted(t["m_Name"].replace("Survivor_", "") for g, (o, t) in surv.items() if g not in obtainable)
if len(skipped) > 8:
    sys.exit("얻을 수 있는 생존자를 제대로 찾지 못했습니다 (제외 %d명). 게임 업데이트로 구조가 바뀌었을 수 있습니다." % len(skipped))
# (2) 영입 데이터가 가리키는 특성 (PPtr)
recruit_refs = set()
for o, t, c in bal_objs:
    if c == "RecruitmentData":
        sg = guid_of(t.get("m_survivorGuid") or {})
        for p in t.get("m_additionalTraits", []):
            if sg and p["m_PathID"]:
                recruit_refs.add((sg, trait_name(p)))

fixed = []                       # (survivor, trait name, 이유)
pools = {"+": [], "-": []}       # 섞을 PPtr 모음
slots = {"+": [], "-": []}       # (생존자 이름, 리스트 위치)
plan = {}
for g, (o, t) in surv.items():
    lst = t["m_startingTraits"]
    plan[t["m_Name"]] = (o, t)
    if g not in obtainable:
        continue          # 얻을 수 없는 생존자는 건드리지 않는다 (특성이 낭비되지 않게 풀에서 뺌)
    for i, p in enumerate(lst):
        n = trait_name(p)
        if not n.startswith(("Trait+", "Trait-")):
            continue
        sign = "+" if n.startswith("Trait+") else "-"
        tg = next((k for k, v in trait_by_guid.items() if v == n), None)
        why = None
        if tg is not None and (g, tg) in story_pairs:
            why = "스토리 액션/조건"
        elif (g, n) in recruit_refs:
            why = "영입 데이터"
        elif any(s in n for s in STORY_NAME_PARTS):
            why = "스토리 특성"
        if why:
            fixed.append((t["m_Name"], n, why))
            continue
        slots[sign].append((t["m_Name"], i))
        pools[sign].append(dict(p))

rng = random.Random(SEED)
changes = {}
for sign in ("+", "-"):
    pool = list(pools[sign])
    rng.shuffle(pool)
    # 아무도 그대로 남지 않게 시도 (가능한 범위에서)
    for _ in range(50):
        if all(pool[k]["m_PathID"] != pools[sign][k]["m_PathID"] for k in range(len(pool))):
            break
        rng.shuffle(pool)
    for (name, idx), newp in zip(slots[sign], pool):
        changes.setdefault(name, {})[idx] = newp

print("특성 섞기: 생존자 %d명 중 %d칸을 다시 나눔 (고정 %d칸)" % (len(surv), sum(len(v) for v in changes.values()), len(fixed)))
if skipped:
    print("섞기에서 뺀 생존자(영입/시작 데이터가 없어 게임에서 얻을 수 없음): " + ", ".join(skipped))
print("고정된 칸: " + ", ".join("%s(%s)" % (n.replace("Survivor_", ""), tn.replace("Trait", "")) for n, tn, _w in sorted(fixed)))

# 같은 크기로 적용
env = bal_env
bundle = env.file
sfs = {n: f for n, f in bundle.files.items() if hasattr(f, "types")}
assert len(sfs) == 1, list(bundle.files)
name, sf = next(iter(sfs.items()))
raw = bytearray(sf.reader.bytes)
nch = 0
summary = []
weapon_moves = []
obt_names = {t["m_Name"] for g, (o, t) in surv.items() if g in obtainable}
for sname in sorted(plan):
    o, t = plan[sname]
    edits = changes.get(sname, {})
    before = [trait_name(p) for p in t["m_startingTraits"]]
    for idx, newp in edits.items():
        t["m_startingTraits"][idx] = newp
    after = [trait_name(p) for p in t["m_startingTraits"]]
    wedits = 0
    if WEAPONS_OK and sname in obt_names:
        pos = next((n for n in after if n.startswith("Trait+")), None)
        want = "martial" if pos == "Trait+MartialArtist" else ("brutal" if pos == "Trait+ProfessionalWrestler" else "base")
        for wi, p in enumerate(t["m_innateEquipment"]):
            n = bal_name_by_id.get(p["m_PathID"]) if not p["m_FileID"] else None
            if n in unarmed_names and n != UNARMED[want]:
                t["m_innateEquipment"][wi] = dict(unarmed_ptr[want])
                wedits += 1
                weapon_moves.append((sname.replace("Survivor_", ""), n.replace("SurvivorUnarmed", "").replace("_WeaponDefinition", "") or "기본", UNARMED[want].replace("SurvivorUnarmed", "").replace("_WeaponDefinition", "") or "기본"))
    if not edits and not wedits:
        continue
    st = o.byte_start
    seg = bytes(raw[st:st + o.byte_size])
    nb = o.save_typetree(t)
    assert len(nb) == len(seg), "크기가 달라짐"
    d = [i for i in range(len(seg)) if seg[i] != nb[i]]
    assert d and len(d) <= 8 * (len(edits) + wedits), "예상과 다른 변경 범위"
    raw[st:st + len(seg)] = nb
    nch += len(edits)
    summary.append((sname.replace("Survivor_", ""), [b for b in before if b.startswith("Trait")], [a for a in after if a.startswith("Trait")]))
r = EndianBinaryReader(bytes(raw))
r.flags = sf.flags
bundle.files[name] = r
data = bundle.save(packer="lz4")
# 검증: 다시 읽어서 각 생존자의 특성 구성이 의도와 같은지, 특성 종류별 개수가 같은지
env2 = UnityPy.load(data)
sc2 = {o.path_id: o.read().m_ClassName for o in env2.objects if o.type.name == "MonoScript"}
from collections import Counter
cnt_before, cnt_after = Counter(), Counter()
for o, t, c in bal_objs:
    if c == "SurvivorData":
        for p in t["m_startingTraits"]:
            pass
for o in env2.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        t2 = o.read_typetree()
    except Exception:
        continue
    if sc2.get(t2["m_Script"]["m_PathID"]) == "SurvivorData" and t2.get("m_Name") in plan:
        want = plan[t2["m_Name"]][1]["m_startingTraits"]
        got = t2["m_startingTraits"]
        assert [(p["m_FileID"], p["m_PathID"]) for p in got] == [(p["m_FileID"], p["m_PathID"]) for p in want], "검증 실패: " + t2["m_Name"]
        wi_want = plan[t2["m_Name"]][1]["m_innateEquipment"]
        wi_got = t2["m_innateEquipment"]
        assert [(p["m_FileID"], p["m_PathID"]) for p in wi_got] == [(p["m_FileID"], p["m_PathID"]) for p in wi_want], "검증 실패(무기): " + t2["m_Name"]
open(OUT, "wb").write(data)
if weapon_moves:
    print("맨손 무기 이동: " + ", ".join("%s(%s->%s)" % w for w in weapon_moves))
for n, b, a in sorted(summary):
    print("  %-10s %s -> %s" % (n, "/".join(x.replace("Trait", "") for x in b), "/".join(x.replace("Trait", "") for x in a)))
