"""data_config: 공용구역에서 '로맨스 아이템'을 쓸 수 있는 인원 조건을 '정확히 2명' -> '2명 이상' 으로 바꾼다.
사용: python patch_romance.py <data_config 파일> <출력 파일>
 - RomanceCommunalAreaItemComponent.m_communalUseConditions 에서 ExactlyTwoSlotsOccupied(정확히 2칸 차 있음)를
   InteractableHasTwoSlotsOccupied(2칸 이상 차 있음)로 바꾼다. (포인터 하나만 바뀌므로 오브젝트 크기는 변하지 않는다.)
 - 가족 관계 쌍 없음 / 모든 쌍의 나이대 일치 / 이미 연애 중인 사람 없음 조건은 그대로다 (인원이 늘면 쌍이 늘어 더 까다로워진다).
 - 로비 일지(RobbieJournal) 아이템은 건드리지 않는다.
"""
import sys
import UnityPy.helpers.TypeTreeNode as T
_orig = T.TypeTreeNode.parse_blob.__func__
def _pb(cls, reader, version):
    reader.Position = reader.Position + 28
    return _orig(cls, reader, version)
T.TypeTreeNode.parse_blob = classmethod(_pb)
# Windows + Python 3.14 에서 UnityPy 의 C 가속 모듈이 접근 위반으로 죽는 문제 대응 (다른 스크립트와 동일)
try:
    import UnityPy.helpers.TypeTreeHelper as _TTH
    _TTH.read_typetree_boost = None
except Exception:
    pass
import UnityPy
from UnityPy.streams import EndianBinaryReader

SRC, OUT = sys.argv[1], sys.argv[2]
env = UnityPy.load(SRC)
bundle = env.file
sfs = {n: f for n, f in bundle.files.items() if hasattr(f, "types")}
assert len(sfs) == 1, list(bundle.files)
name, sf = next(iter(sfs.items()))
raw = bytearray(sf.reader.bytes)
flags = sf.flags
ids, target = {}, None
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        tt = o.read_typetree()
    except Exception:
        continue
    ids[tt.get("m_Name")] = o.path_id
    if tt.get("m_Name") == "RomanceCommunalAreaItemComponent":
        target = (o, tt)
for need in ("ExactlyTwoSlotsOccupied", "InteractableHasTwoSlotsOccupied"):
    if need not in ids:
        sys.exit("필요한 데이터를 찾지 못했습니다: %s (게임 업데이트로 구조가 바뀌었을 수 있음)" % need)
if target is None:
    sys.exit("RomanceCommunalAreaItemComponent 를 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음)")
o, tt = target
old, new_id = ids["ExactlyTwoSlotsOccupied"], ids["InteractableHasTwoSlotsOccupied"]
hits = [c for c in tt["m_communalUseConditions"] if c["m_PathID"] == old]
if len(hits) != 1:
    sys.exit("바꿀 조건을 찾지 못했습니다 (이미 바뀌었거나 구조가 달라졌습니다)")
hits[0]["m_PathID"] = new_id
st = o.byte_start
seg = bytes(raw[st:st + o.byte_size])
new = o.save_typetree(tt)
assert len(new) == len(seg), "크기가 달라짐"
d = [i for i in range(len(seg)) if seg[i] != new[i]]
assert d and len(d) <= 8, "예상과 다른 변경 범위"
raw[st:st + len(seg)] = new
r = EndianBinaryReader(bytes(raw))
r.flags = flags
bundle.files[name] = r
open(OUT, "wb").write(bundle.save(packer="lz4"))
print("로맨스 아이템 사용 조건: 정확히 2명 -> 2명 이상 (공용구역)")
