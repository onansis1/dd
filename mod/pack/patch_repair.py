"""data_balancing: 정비 작업대 레벨 때문에 수리할 수 없던 무기를 레벨 제한 없이 수리할 수 있게 한다.
사용: python patch_repair.py <data_balancing 파일> <data_config 파일> <출력 파일> [Repair|Dismantle]   (기본 Repair = 수리, Dismantle = 분해)
 - 수리 레시피(Repair*_Recipe)와 분해 레시피(Dismantle*_Recipe)마다 '사용 가능 조건'(m_availabilityConditions)에 정비 작업대 장비 조건이 걸려 있다:
     HasDismantlingStationEquipmentL2orL3 = 정비 작업대 레벨 2 이상, HasDismantlingStationEquipmentL3 = 레벨 3
   이 조건 참조를 '항상 참'인 기존 조건(Trader_FeatureFlagDefinedCondition, data_config)으로 바꿔 제한을 없앤다.
 - 참조의 PathID 8바이트만 바뀌므로 오브젝트 크기는 변하지 않는다. 특성(수리공/건스미스)·내구도 조건은 그대로다.
 - 수리 재료(아이템 소모)는 그대로다. 스필존 콘솔 수리(Repair_Spillzone_Console_Damaged_Recipe)는 스토리 조건이라 건드리지 않는다.
"""
import sys
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
PREFIX = sys.argv[4] if len(sys.argv) > 4 else "Repair"
if PREFIX not in ("Repair", "Dismantle"):
    sys.exit("4번째 인자는 Repair 또는 Dismantle 이어야 합니다")
KO = "수리" if PREFIX == "Repair" else "분해"
cfg_env = UnityPy.load(CFG)
cfg_ids = {}
for o_ in cfg_env.objects:
    if o_.type.name != "MonoBehaviour":
        continue
    try:
        cfg_ids[o_.read_typetree().get("m_Name")] = o_.path_id
    except Exception:
        pass
for need in ("Trader_FeatureFlagDefinedCondition", "HasDismantlingStationEquipmentL2orL3", "HasDismantlingStationEquipmentL3"):
    if need not in cfg_ids:
        sys.exit("필요한 데이터를 찾지 못했습니다: %s (게임 업데이트로 구조가 바뀌었을 수 있음)" % need)
TRUE = cfg_ids["Trader_FeatureFlagDefinedCondition"]
LEVEL = {cfg_ids["HasDismantlingStationEquipmentL2orL3"], cfg_ids["HasDismantlingStationEquipmentL3"]}
env = UnityPy.load(SRC)
bundle = env.file
sfs = {n: f for n, f in bundle.files.items() if hasattr(f, "types")}
assert len(sfs) == 1, list(bundle.files)
name, sf = next(iter(sfs.items()))
raw = bytearray(sf.reader.bytes)
scripts = {o.path_id: o.read().m_ClassName for o in env.objects if o.type.name == "MonoScript"}
nrec = nref = 0
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        t = o.read_typetree()
    except Exception:
        continue
    if scripts.get(t["m_Script"]["m_PathID"]) != "QueuedRecipeDefinition" or not t.get("m_Name", "").startswith(PREFIX):
        continue
    ch = 0
    for c in t["m_availabilityConditions"]:
        if c["m_FileID"] != 0 and c["m_PathID"] in LEVEL:
            c["m_PathID"] = TRUE
            ch += 1
    if not ch:
        continue
    st = o.byte_start
    seg = bytes(raw[st:st + o.byte_size])
    nb = o.save_typetree(t)
    assert len(nb) == len(seg), "크기가 달라짐"
    d = [i for i in range(len(seg)) if seg[i] != nb[i]]
    assert d and len(d) <= 8 * ch, "예상과 다른 변경 범위"
    raw[st:st + len(seg)] = nb
    nrec += 1
    nref += ch
if nrec == 0:
    sys.exit(KO + " 레시피의 정비 작업대 조건을 찾지 못했습니다 (이미 바뀌었거나 게임 업데이트로 구조가 달라졌습니다)")
r = EndianBinaryReader(bytes(raw))
r.flags = sf.flags
bundle.files[name] = r
open(OUT, "wb").write(bundle.save(packer="lz4"))
print("%s 제한 해제: 정비 작업대 레벨 조건이 걸린 %s 레시피 %d개 (조건 %d개)" % (KO, KO, nrec, nref))
