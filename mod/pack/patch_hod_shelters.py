"""data_balancing: 어둠의 심연 '사우스버러로 이동' 목표(AtShelter_RecordStore_OR_Electronics)가 요구하는 거점을
거점 섞기 후 그 자리(사우스버러)에 온 두 거점으로 바꾼다.
사용: python patch_hod_shelters.py <data_balancing> <data_config> <거점1 guid hex> <거점2 guid hex> <출력>
 - OrCondition 의 조건 포인터 두 개를 해당 거점의 'AtShelter_*' 조건(data_config 안)으로 바꾼다. 같은 크기.
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

SRC, CFG, G1, G2, OUT = sys.argv[1:6]
def gb(d):
    try:
        return bytes(d["bytes[%d]" % i] for i in range(16)).hex()
    except Exception:
        return None
cfg = UnityPy.load(CFG)
scr = {o.path_id: o.read().m_ClassName for o in cfg.objects if o.type.name == "MonoScript"}
at = {}
for o in cfg.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        t = o.read_typetree()
    except Exception:
        continue
    if scr.get(t["m_Script"]["m_PathID"]) == "AtShelter" and not t.get("m_invert"):
        h = gb(t["m_shelter"]["m_guid"]) if "m_shelter" in t else None
        if h and (h not in at or t["m_Name"].startswith("AtShelter_")):
            at[h] = o.path_id
for g in (G1, G2):
    if g not in at:
        sys.exit("그 거점의 AtShelter 조건을 찾지 못했습니다: %s" % g)
env = UnityPy.load(SRC)
bundle = env.file
name, sf = [(n, f) for n, f in bundle.files.items() if hasattr(f, "types")][0]
raw = bytearray(sf.reader.bytes)
tgt = None
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        t = o.read_typetree()
    except Exception:
        continue
    if t.get("m_Name") == "AtShelter_RecordStore_OR_Electronics":
        tgt = (o, t)
if tgt is None:
    sys.exit("AtShelter_RecordStore_OR_Electronics 를 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음)")
o, t = tgt
if len(t["m_conditions"]) != 2 or any(c["m_FileID"] != 1 for c in t["m_conditions"]):
    sys.exit("조건 목록이 예상과 다릅니다")
new_ids = [at[G1], at[G2]]
if [c["m_PathID"] for c in t["m_conditions"]] == new_ids or [c["m_PathID"] for c in t["m_conditions"]] == new_ids[::-1]:
    open(OUT, "wb").write(open(SRC, "rb").read())
    print("어둠의 심연 사우스버러 조건: 변경 없음 (밸류 레코드/베스트 일렉트로닉스 그대로)")
    sys.exit(0)
t["m_conditions"] = [{"m_FileID": 1, "m_PathID": new_ids[0]}, {"m_FileID": 1, "m_PathID": new_ids[1]}]
st = o.byte_start
seg = bytes(raw[st:st + o.byte_size])
nb = o.save_typetree(t)
assert len(nb) == len(seg), "크기가 달라짐"
d = [i for i in range(len(seg)) if seg[i] != nb[i]]
assert d and len(d) <= 16, "예상과 다른 변경 범위"
raw[st:st + len(seg)] = nb
r = EndianBinaryReader(bytes(raw))
r.flags = sf.flags
bundle.files[name] = r
open(OUT, "wb").write(bundle.save(packer="lz4"))
print("어둠의 심연 사우스버러 조건: 이 자리에 온 거점 두 곳으로 변경 (바뀐 바이트 %d)" % len(d))
