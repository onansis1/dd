"""data_balancing: 스필존 관제실의 오토(Otto) 영입 때 방호복을 건네는 조건/소모를 '락픽 1개'로 바꾼다.
사용: python patch_otto.py <data_balancing 파일> <data_config 파일> <출력 파일>
 - 관제실 대화(Spillzone_16_ControlRoom_01_NPCI_01)에서 오토가 방호복을 요구하면, 배낭에 방호복(초록/오렌지/흰색/노랑/노라 5종 중 하나, 장착 중이 아닌 것)이 있을 때만
   '건네기' 선택지가 열리고, 고른 색의 방호복 1개가 소모된다. 이 흐름을 락픽으로 바꾼다:
   (1) 건네기 선택지를 여는 조건 두 곳(재방문 노드 Step_00B, 선택 노드 Step_12)의 조건: '방호복 있음' -> data_config 의 HasInBackpack_Lockpick (배낭에 락픽 1개 이상)
   (2) 색별 분기(Op_01_Step_00): 초록 분기만 락픽 조건으로 열고, 나머지 4색 분기는 data_config 의 ReturnFalseCondition (항상 거짓)으로 닫는다
   (3) 초록 분기의 소모 동작(AlterSurvivorInventory_Green)이 빼는 아이템을 방호복(초록)에서 락픽 1개로 바꾼다
   모두 같은 크기의 참조/GUID 교체라 오브젝트 크기는 변하지 않는다. 이 대화 노드들은 이 장면에서만 쓰이는 것들이며, 방호복 조건 객체 자체(여러 곳에서 공유)는 건드리지 않는다.
 - 대화 문구(번역 텍스트)는 코드/번역 파일 쪽이라 바꾸지 않았다: 대사에는 여전히 방호복이라고 나올 수 있다.
"""
import copy, sys
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

BAL, CFG, OUT = sys.argv[1:4]
P = "Spillzone_16_ControlRoom_01_NPCI_01_Step_11_Op_02_Step_02_Op_03_Step_12"
N_REVISIT = "Spillzone_16_ControlRoom_01_NPCI_01_Step_00B"
N_CHOICE = P
N_COLORS = P + "_Op_01_Step_00"
N_GREEN = P + "_Op_01_Step_01_Green"
OTHERS = {c: P + "_Op_01_Step_01_" + c for c in ("Orange", "White", "Yellow", "Nora")}
ALT_GREEN = "Spillzone_16_ControlRoom_01_NPCI_01_AlterSurvivorInventory_Green"
HAZ_ANY = "HasInBackpack_NotEquipped_HazmatSuit"
HAZ_COLOR = {"Green": "HasInBackpack_NotEquipped_HazmatSuit_Green", "Orange": "HasInBackpack_NotEquipped_HazmatSuit_Orange",
             "White": "HasInBackpack_NotEquipped_HazmatSuit_White", "Yellow": "HasInBackpack_NotEquipped_HazmatSuit_Yellow",
             "Nora": "HasInBackpack_NotEquipped_HazmatSuit_Nora"}

def guid_bytes(g):
    x = g.get("m_guid") if isinstance(g, dict) else None
    return bytes(x["bytes[%d]" % i] for i in range(16)) if isinstance(x, dict) and "bytes[0]" in x else None

def scripts_of(env):
    return {o.path_id: o.read().m_ClassName for o in env.objects if o.type.name == "MonoScript"}

# ---- data_config: 락픽 아이템 / 락픽 조건 / 항상 거짓 조건 ----
cenv = UnityPy.load(CFG)
csc = scripts_of(cenv)
lock_item = lock_cond = false_cond = None
for o in cenv.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        t = o.read_typetree()
    except Exception:
        continue
    c = csc.get(t["m_Script"]["m_PathID"])
    n = t.get("m_Name")
    if c == "InventoryItemDefinition" and n == "Lockpick":
        lock_item = t["m_guid"]
    elif c == "HasItemInInventory" and n == "HasInBackpack_Lockpick":
        lock_cond = (o.path_id, t)
    elif c == "AlwaysTrueCondition" and n == "ReturnFalseCondition":
        false_cond = (o.path_id, t)
if lock_item is None or lock_cond is None or false_cond is None:
    sys.exit("락픽 아이템/조건 또는 항상 거짓 조건을 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음)")
if guid_bytes(lock_cond[1]["m_itemDefinitionId"]) != guid_bytes(lock_item) or lock_cond[1]["m_numItemsRequired"] != 1 or lock_cond[1]["m_invert"] != 0:
    sys.exit("HasInBackpack_Lockpick 의 내용이 예상과 다릅니다")
if false_cond[1]["m_invert"] != 1:
    sys.exit("ReturnFalseCondition 이 항상 거짓이 아닙니다")
LOCK_PTR = {"m_FileID": 1, "m_PathID": lock_cond[0]}
FALSE_PTR = {"m_FileID": 1, "m_PathID": false_cond[0]}

# ---- data_balancing ----
env = UnityPy.load(BAL)
bundle = env.file
name, sf = [(n, f) for n, f in bundle.files.items() if hasattr(f, "types")][0]
raw = bytearray(sf.reader.bytes)
orig_raw = bytes(raw)
objs1 = list(env.objects)
bsc = scripts_of(env)
want = {N_REVISIT, N_CHOICE, N_COLORS, N_GREEN, ALT_GREEN, HAZ_ANY, *OTHERS.values(), *HAZ_COLOR.values()}
found = {}
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        t = o.read_typetree()
    except Exception:
        continue
    n = t.get("m_Name")
    if n in want:
        if n in found:
            sys.exit("%s 가 둘 이상 있습니다 (구조가 달라졌습니다)" % n)
        found[n] = (o, t)
missing = sorted(want - set(found))
if missing:
    sys.exit("오토 영입 대화 구조를 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음): %s" % ", ".join(missing))
pid_name = {found[n][0].path_id: n for n in found}
def is_ptr(p, name_):
    return p.get("m_FileID") == 0 and pid_name.get(p.get("m_PathID")) == name_

def links_of(t):
    out = []
    for r in t["references"]["RefIds"]:
        out += r["data"].get("m_links", [])
    return out

changes = []        # (오브젝트, 새 typetree dict, 설명)
touched = {}
def mark(n):
    touched[n] = found[n]

# (1) 건네기 선택지를 여는 조건 두 곳
for n in (N_REVISIT, N_CHOICE):
    o, t = found[n]
    hit = 0
    for lk in links_of(t):
        cs = lk["m_conditions"]
        if len(cs) == 1 and is_ptr(cs[0], HAZ_ANY):
            cs[0] = dict(LOCK_PTR)
            hit += 1
    if hit != 1:
        sys.exit("%s 의 방호복 조건 연결이 예상과 다릅니다 (%d개)" % (n, hit))
    mark(n)
# (2) 색별 분기
o, t = found[N_COLORS]
tgt_pid = {found[N_GREEN][0].path_id: "Green", **{found[v][0].path_id: k for k, v in OTHERS.items()}}
seen = set()
for lk in links_of(t):
    col = tgt_pid.get(lk["m_nextNode"]["m_PathID"]) if lk["m_nextNode"].get("m_FileID") == 0 else None
    cs = lk["m_conditions"]
    if col is None or len(cs) != 1 or not is_ptr(cs[0], HAZ_COLOR[col]):
        sys.exit("색별 분기 연결이 예상과 다릅니다")
    cs[0] = dict(LOCK_PTR) if col == "Green" else dict(FALSE_PTR)
    seen.add(col)
if seen != set(HAZ_COLOR):
    sys.exit("색별 분기 5개를 모두 찾지 못했습니다: %s" % sorted(seen))
mark(N_COLORS)
# (3) 초록 분기의 소모 동작
o, t = found[ALT_GREEN]
if len(t["m_items"]) != 1 or t["m_items"][0]["m_count"] != 1 or t["m_option"] != 1:
    sys.exit("소모 동작(AlterSurvivorInventory_Green)의 구조가 예상과 다릅니다")
t["m_items"][0]["m_itemGuid"] = copy.deepcopy(lock_item)
mark(ALT_GREEN)

for n, (o, t) in touched.items():
    st = o.byte_start
    seg = bytes(raw[st:st + o.byte_size])
    nb = o.save_typetree(t)
    assert len(nb) == len(seg), "%s: 크기가 달라짐" % n
    d = [i for i in range(len(seg)) if seg[i] != nb[i]]
    assert d and len(d) <= 80, "%s: 예상과 다른 변경 범위 %d" % (n, len(d))
    raw[st:st + len(seg)] = nb

r = EndianBinaryReader(bytes(raw))
r.flags = sf.flags
bundle.files[name] = r
data = bundle.save(packer="lz4")
# 쓴 뒤 검증: 다시 읽어 의도한 값인지, 다른 오브젝트는 그대로인지
env2 = UnityPy.load(data)
objs2 = {o.path_id: o for o in env2.objects}
assert len(objs2) == len(objs1), "오브젝트 수가 달라졌습니다"
tp = {x[0].path_id for x in touched.values()}
for o in objs1:
    if o.path_id in tp:
        assert o.path_id in objs2
        continue
    assert orig_raw[o.byte_start:o.byte_start + o.byte_size] == bytes(objs2[o.path_id].get_raw_data()), "다른 오브젝트가 바뀜: %d" % o.path_id
t2 = objs2[found[ALT_GREEN][0].path_id].read_typetree()
assert guid_bytes(t2["m_items"][0]["m_itemGuid"]) == guid_bytes(lock_item)
t2 = objs2[found[N_COLORS][0].path_id].read_typetree()
conds = [lk["m_conditions"][0] for lk in links_of(t2)]
assert conds.count(LOCK_PTR) == 1 and sum(1 for c in conds if c == FALSE_PTR) == 4, "색별 분기 조건"
for n in (N_REVISIT, N_CHOICE):
    t2 = objs2[found[n][0].path_id].read_typetree()
    assert any(lk["m_conditions"] == [LOCK_PTR] for lk in links_of(t2)), n
open(OUT, "wb").write(data)
print("오토 영입(스필존 관제실): 방호복 1개 -> 락픽 1개 (건네기 선택지 조건 2곳 + 색별 분기 5개 + 소모 동작 1개, 오브젝트 %d개 수정)" % len(touched))
