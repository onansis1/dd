"""data_config: 탐험(외출) 중 죽은 생존자가 좀비가 될 확률을 50% -> 100% 로 만든다.
사용: python patch_zombie.py <data_config 파일> <출력 파일>
 - DrsConfigsData.m_zombificationConfigs.m_defaultZombificationConditions 의 '50PercentChance'(공용 오브젝트) 를
   가리키던 연결을 '항상 참' 조건(Trader_FeatureFlagDefinedCondition, 같은 목록에서 쓰이는 기능 켜짐 조건)으로 바꾼다.
   공용 50PercentChance 오브젝트 자체는 건드리지 않는다 (다른 곳에서도 쓰임). 오브젝트 크기 불변.
 - 예외 조건(좀비 진영에게 죽은 경우 / 처음 떠난 생존자)은 그대로 둔다 -> 그 경우엔 여전히 좀비가 되지 않는다.
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
ids, target = {}, None
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        tt = o.read_typetree()
    except Exception:
        continue
    ids[tt.get("m_Name")] = o.path_id
    if "m_zombificationConfigs" in tt:
        target = (o, tt)
if target is None:
    sys.exit("m_zombificationConfigs 를 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음)")
for need in ("50PercentChance", "Trader_FeatureFlagDefinedCondition"):
    if need not in ids:
        sys.exit("필요한 데이터를 찾지 못했습니다: %s" % need)
o, tt = target
lst = tt["m_zombificationConfigs"]["m_defaultZombificationConditions"]
if len(lst) != 1 or lst[0]["m_PathID"] != ids["50PercentChance"] or lst[0]["m_FileID"] != 0:
    sys.exit("좀비화 기본 조건이 예상(50PercentChance 하나)과 다릅니다. 이미 바뀌었거나 구조가 달라졌습니다.")
lst[0] = {"m_FileID": 0, "m_PathID": ids["Trader_FeatureFlagDefinedCondition"]}
st = o.byte_start
seg = bytes(raw[st:st + o.byte_size])
new = o.save_typetree(tt)
assert len(new) == len(seg), "크기가 달라짐"
d = [i for i in range(len(seg)) if seg[i] != new[i]]
assert d and len(d) <= 8, "예상과 다른 변경 범위: %d" % len(d)
raw[st:st + len(seg)] = new
r = EndianBinaryReader(bytes(raw))
r.flags = flags
bundle.files[name] = r
open(OUT, "wb").write(bundle.save(packer="lz4"))
print("좀비화 확률: 50%% -> 100%% (바뀐 바이트 %d)" % len(d))
