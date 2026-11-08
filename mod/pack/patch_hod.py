"""data_balancing: 어둠의 심연(Heart of Darkness) 단서를 게임 시작부터 얻은 상태로 만든다 (시도).
사용: python patch_hod.py <data_balancing 파일> <data_config 파일> <출력 파일> [hod] [spillzone]   (기본 hod)
 - 어둠의 심연의 기존 '지식 얻기' 동작 3개(HoD_Leads_Unlock_Attempt_01/02, HoD_Leads_Unlocked)가 가리키는 지식을
   HoD_Lead_01, 02, 03 (단서 3개)으로 바꾼다. (같은 크기 포인터 교체)
 - 은신처 이벤트 두 개(Opening_Hellhole_ShelterEventData, Onboarding_01_Phases_ShelterEventData; 둘 다 매 사이클 앞부분에 조건이 약하고
   동작이 비어 있는 이벤트)의 동작 목록에 위 3개를 넣는다. (오브젝트 크기가 늘어나므로 오브젝트 표를 갱신한다)
 - 탈출 단서 수 옵션(--leads)과 같이 쓰면 이미 3개 이상 얻은 상태가 되어 해금 조건을 만족한다.
 - 게임이 이 이벤트들을 실제로 그 시점에 실행하는지, 동작이 정상 처리되는지는 확인하지 못했다.
"""
import sys, struct
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
from UnityPy.files import ObjectReader as _ORcls
from UnityPy.streams import EndianBinaryReader

ENTRY = {}
_orig_from_reader = _ORcls.from_reader.__func__
def _fr(cls, assets_file, reader):
    before = reader.Position
    obj = _orig_from_reader(cls, assets_file, reader)
    ENTRY[obj.path_id] = (before + 3) // 4 * 4
    return obj
_ORcls.from_reader = classmethod(_fr)

SRC, CFG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
PLANS = sys.argv[4:] or ["hod"]
PLAN_DEF = {
    "hod": (["HoD_Lead_01", "HoD_Lead_02", "HoD_Lead_03"],
            ["HoD_Leads_Unlock_Attempt_01_AcquireSharedKnowledgeAction", "HoD_Leads_Unlock_Attempt_02_AcquireSharedKnowledgeAction", "HoD_Leads_Unlocked_AcquireSharedKnowledgeAction"]),
    # 유출구역: 해금 시도 4~6 단계의 '지식 얻기' 동작 세 개를 단서 01~03 지급용으로 재지정 (해금 시도 장치는 단서를 직접 주므로 필요 없어짐)
    "spillzone": (["Spillzone_Lead_01", "Spillzone_Lead_02", "Spillzone_Lead_03"],
                  ["Spillzone_Leads_Unlock_Attempt_04_AcquireSharedKnowledgeAction", "Spillzone_Leads_Unlock_Attempt_05_AcquireSharedKnowledgeAction", "Spillzone_Leads_Unlock_Attempt_06_AcquireSharedKnowledgeAction"]),
}
for p_ in PLANS:
    if p_ not in PLAN_DEF:
        sys.exit("알 수 없는 계획: %s" % p_)
LEADS = [x for p_ in PLANS for x in PLAN_DEF[p_][0]]
ACTIONS = [x for p_ in PLANS for x in PLAN_DEF[p_][1]]
EVENTS = ["Opening_Hellhole_ShelterEventData", "Onboarding_01_Phases_ShelterEventData"]

cfg_ids = {}
for o_ in UnityPy.load(CFG).objects:
    if o_.type.name != "MonoBehaviour":
        continue
    try:
        cfg_ids[o_.read_typetree().get("m_Name")] = o_.path_id
    except Exception:
        pass
for n in LEADS:
    if n not in cfg_ids:
        sys.exit("필요한 데이터를 찾지 못했습니다: %s" % n)

ENTRY.clear()
env = UnityPy.load(SRC)
bundle = env.file
name, sf = [(n, f) for n, f in bundle.files.items() if hasattr(f, "types")][0]
raw = bytearray(sf.reader.bytes)
hdr = sf.header
A = 16
up = lambda n: (n + A - 1) // A * A

by = {}
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        tt = o.read_typetree()
    except Exception:
        continue
    by[tt.get("m_Name")] = (o, tt)
for n in ACTIONS + EVENTS:
    if n not in by:
        sys.exit("필요한 데이터를 찾지 못했습니다: %s (게임 업데이트로 구조가 바뀌었을 수 있음)" % n)

new_bytes = {}     # path_id -> 새 바이트
# 1) 지식 얻기 동작 3개의 대상 지식 교체 (같은 크기)
for an, ln in zip(ACTIONS, LEADS):
    o, tt = by[an]
    kid = tt["m_knowledgeId"]
    if kid["m_FileID"] != 1:
        sys.exit("%s: 예상과 다른 참조 형식" % an)
    kid["m_PathID"] = cfg_ids[ln]
    nb = bytes(o.save_typetree(tt))
    assert len(nb) == o.byte_size, "크기가 달라짐: " + an
    new_bytes[o.path_id] = nb
# 2) 이벤트 두 개의 동작 목록에 3개 추가 (크기 증가)
ptrs = [{"m_FileID": 0, "m_PathID": by[an][0].path_id} for an in ACTIONS]
for en in EVENTS:
    o, tt = by[en]
    if tt["m_actions"] != []:
        sys.exit("%s: 동작 목록이 비어 있지 않습니다 (이미 바뀌었거나 구조가 달라졌습니다)" % en)
    tt["m_actions"] = [dict(p) for p in ptrs]
    new_bytes[o.path_id] = bytes(o.save_typetree(tt))

# 오브젝트 전체를 순서대로 다시 배치
objs = sorted(env.objects, key=lambda x: x.byte_start)
base = hdr.data_offset
if objs[0].byte_start != base:
    sys.exit("예상과 다른 오브젝트 배치입니다 (시작)")
for i, x in enumerate(objs):
    end = objs[i + 1].byte_start if i + 1 < len(objs) else len(raw)
    if end - x.byte_start != (up(x.byte_size) if i + 1 < len(objs) else x.byte_size):
        sys.exit("예상과 다른 오브젝트 배치입니다.")
out = bytearray(raw[:base])
pos = 0
newpos = {}
for i, x in enumerate(objs):
    data = new_bytes.get(x.path_id)
    if data is None:
        data = bytes(raw[x.byte_start:x.byte_start + x.byte_size])
    newpos[x.path_id] = (pos, len(data))
    pad = (up(len(data)) - len(data)) if i + 1 < len(objs) else 0
    out += data + b"\x00" * pad
    pos += len(data) + pad
for x in objs:
    e = ENTRY[x.path_id]
    pid, bs, sz = struct.unpack_from("<qqI", raw, e)
    if pid != x.path_id or bs != x.byte_start - base or sz != x.byte_size:
        sys.exit("오브젝트 표 해석이 예상과 다릅니다. 중단합니다.")
    struct.pack_into("<q", out, e + 8, newpos[x.path_id][0])
    struct.pack_into("<I", out, e + 16, newpos[x.path_id][1])
struct.pack_into(">q", out, 24, len(out))
r_ = EndianBinaryReader(bytes(out))
r_.flags = sf.flags
bundle.files[name] = r_
open(OUT, "wb").write(bundle.save(packer="lz4"))
print("%s 단서 3개씩을 시작부터 지급 (시도, 게임 내 동작 미확인): 이벤트 %d개 크기 증가" % ("/".join({"hod": "어둠의 심연", "spillzone": "유출구역"}[p_] for p_ in PLANS), len(EVENTS)))
