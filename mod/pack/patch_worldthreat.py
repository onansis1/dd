"""data_config: 세계 난이도(날짜/스토리 진행 단계) 때문에 '지금 사는 거점'의 최대 위협이 오르지 않게 한다.
사용: python patch_worldthreat.py <data_config 파일> <출력 파일>
 - 거점의 최대 위협 = ShelterThreatCategory 4개(난이도 설정, 생존자 수, 거점 체류 시간, 세계 난이도)의 합이다.
   그중 ShelterThreatCategory_WorldDifficulty 는 세계 난이도 단계(사이클 20/40/60 + 스토리 진행 조건, 80)에 따라 0,1,2,3,4 를 더한다.
   이 목록의 값 5개를 모두 첫 항목(단계 0)의 값으로 맞춘다. 조건은 그대로라 어느 단계든 같은 값이 나온다.
 - 이 위협은 지금 사는 거점에만 적용된다(다른 거점의 위협은 비어 있는 동안 오르지 않고, 이사하면 새 거점은 0에서 다시 계산).
   즉 '내가 털어서 쓰는 거점'만 대상이고, 지도의 장소(아직 안 털린 곳)의 난이도(WorldDifficultyData)는 건드리지 않는다.
 - 난이도 설정/생존자 수/체류 시간 항목과 이벤트가 직접 바꾸는 위협은 그대로다. 값만 바뀌므로 오브젝트 크기는 변하지 않는다.
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

SRC, OUT = sys.argv[1], sys.argv[2]
env = UnityPy.load(SRC)
bundle = env.file
sfs = {n: f for n, f in bundle.files.items() if hasattr(f, "types")}
assert len(sfs) == 1, list(bundle.files)
name, sf = next(iter(sfs.items()))
raw = bytearray(sf.reader.bytes)
target = None
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        tt = o.read_typetree()
    except Exception:
        continue
    if tt.get("m_Name") == "ShelterThreatCategory_WorldDifficulty" and "m_threatContributions" in tt:
        target = (o, tt)
if target is None:
    sys.exit("ShelterThreatCategory_WorldDifficulty 를 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음)")
o, tt = target
lst = tt["m_threatContributions"]
vals = [c["m_value"] for c in lst]
if len(lst) != 5 or vals != [0, 1, 2, 3, 4]:
    sys.exit("세계 난이도 위협 항목이 예상([0,1,2,3,4])과 다릅니다: %s (이미 바뀌었거나 구조가 달라졌습니다)" % vals)
for c in lst:
    c["m_value"] = vals[0]
st = o.byte_start
seg = bytes(raw[st:st + o.byte_size])
new = o.save_typetree(tt)
assert len(new) == len(seg), "크기가 달라짐"
d = [i for i in range(len(seg)) if seg[i] != new[i]]
assert d and len(d) <= 16, "예상과 다른 변경 범위"
raw[st:st + len(seg)] = new
r = EndianBinaryReader(bytes(raw))
r.flags = sf.flags
bundle.files[name] = r
open(OUT, "wb").write(bundle.save(packer="lz4"))
print("거점 위협: 세계 난이도 단계로 오르던 값 [0,1,2,3,4] -> [0,0,0,0,0] (사는 거점 한정, 바뀐 바이트 %d)" % len(d))
