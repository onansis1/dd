"""data_balancing: 생존자(플레이어)가 서 있을 때/달릴 때의 발소리를 없앤다 (웅크릴 때처럼 소음 없음).
사용: python patch_noise.py <data_balancing 파일> <출력 파일>
 - NoiseData_Survivor 의 상태별 소음 표에서 '서 있음(걷기)'과 '달리기' 상태의 발소리(Footstep_Survivor_Standing / _Speeding)를
   '없음'으로, 발소리 빈도를 0 으로 바꾼다. 웅크리기 상태가 원래 쓰는 값(발소리 없음, 빈도 0)과 같게 만든 것이다. 크기 불변.
 - 문 열기/루팅/전투/난간 오르기 같은 다른 소음은 그대로이고, 좀비/NPC 의 발소리(NoiseData_Zombie, NoiseData_HumanNPC)도 그대로다.
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
flags = sf.flags
names, target = {}, None
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        tt = o.read_typetree()
    except Exception:
        continue
    names[o.path_id] = tt.get("m_Name")
    if tt.get("m_Name") == "NoiseData_Survivor":
        target = (o, tt)
if target is None:
    sys.exit("NoiseData_Survivor 를 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음)")
o, tt = target
n = 0
for v in tt["m_characterStateNoises"]["m_values"]:
    fp = v["m_footstep"]
    nm = names.get(fp["m_PathID"]) if fp["m_FileID"] == 0 else None
    if nm in ("Footstep_Survivor_Standing", "Footstep_Survivor_Speeding"):
        v["m_footstep"] = {"m_FileID": 0, "m_PathID": 0}
        v["m_footstepFrequency"] = 0.0
        n += 1
if n != 2:
    sys.exit("발소리 항목을 %d개만 찾았습니다 (예상 2개). 이미 바뀌었거나 구조가 달라졌습니다." % n)
st = o.byte_start
seg = bytes(raw[st:st + o.byte_size])
new = o.save_typetree(tt)
assert len(new) == len(seg), "크기가 달라짐"
d = [i for i in range(len(seg)) if seg[i] != new[i]]
assert d and len(d) <= 40, "예상과 다른 변경 범위: %d" % len(d)
raw[st:st + len(seg)] = new
r = EndianBinaryReader(bytes(raw))
r.flags = flags
bundle.files[name] = r
open(OUT, "wb").write(bundle.save(packer="lz4"))
print("생존자 발소리: 서 있을 때/달릴 때 소음 제거 (바뀐 바이트 %d)" % len(d))
