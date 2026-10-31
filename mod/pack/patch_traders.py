"""data_balancing: 상인(마와 파 / 미스터 베일 / 리키)이 처음 나올 수 있는 시점을 게임 시작부터로 앞당긴다.
사용: python patch_traders.py <data_balancing 파일> <data_config 파일> <출력 파일>  (조건 객체의 이름을 data_config 에서 찾는다)
 - PassiveShelterEvents_MedPriority 선택기의 상인 항목(빈도 기본/빠름/느림 3개)에서 'IsCycleGreaterOrEqual10'(사이클 10 이상) 조건을 뺀다.
   (같은 목록의 다른 조건을 가리키게 바꾸는 방식이라 오브젝트 크기는 변하지 않는다.)
 - 그 밖의 조건(90% 확률, 쓸 수 있는 교역소가 있어야 함, 튜토리얼 아님, 상인별 '최근 N사이클 이내에 나왔으면 안 됨')은 그대로다.
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

SRC, CFG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
# 조건 객체(IsCycleGreaterOrEqual10 등)는 data_config 에 있고, data_balancing 의 선택기는 그것을 외부 참조(m_FileID != 0)로 가리킨다.
cfg_ids = {}
for o_ in UnityPy.load(CFG).objects:
    if o_.type.name != "MonoBehaviour":
        continue
    try:
        cfg_ids[o_.read_typetree().get("m_Name")] = o_.path_id
    except Exception:
        pass
for need in ("IsCycleGreaterOrEqual10", "Trader_FeatureFlagDefinedCondition", "AvailableTradingPostExists"):
    if need not in cfg_ids:
        sys.exit("필요한 데이터를 찾지 못했습니다: %s (게임 업데이트로 구조가 바뀌었을 수 있음)" % need)
cyc10, keep, post = cfg_ids["IsCycleGreaterOrEqual10"], cfg_ids["Trader_FeatureFlagDefinedCondition"], cfg_ids["AvailableTradingPostExists"]
env = UnityPy.load(SRC)
bundle = env.file
sfs = {n: f for n, f in bundle.files.items() if hasattr(f, "types")}
assert len(sfs) == 1, list(bundle.files)
name, sf = next(iter(sfs.items()))
raw = bytearray(sf.reader.bytes)
flags = sf.flags
target = None
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        tt = o.read_typetree()
    except Exception:
        continue
    if tt.get("m_Name") == "PassiveShelterEvents_MedPriority_ConditionallyWeightedPassiveEventTriggerPicker":
        target = (o, tt)
        break
if target is None:
    sys.exit("PassiveShelterEvents_MedPriority 선택기를 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음)")
o, tt = target
n = 0
for w in tt["m_weightedOptions"]:
    cs = [c["m_PathID"] for c in w["m_conditions"]]
    if post in cs and cyc10 in cs and keep in cs:
        # 같은 목록에 이미 있는 '상인 기능 켜짐' 조건(항상 참)을 한 번 더 가리키게 해서 사이클 조건을 없앤다
        w["m_conditions"][cs.index(cyc10)] = dict(w["m_conditions"][cs.index(keep)])
        n += 1
if n != 3:
    sys.exit("상인 항목 %d개만 찾았습니다 (예상 3개). 이미 바뀌었거나 구조가 달라졌습니다." % n)
st = o.byte_start
seg = bytes(raw[st:st + o.byte_size])
new = o.save_typetree(tt)
assert len(new) == len(seg), "크기가 달라짐"
d = [i for i in range(len(seg)) if seg[i] != new[i]]
assert d and len(d) <= 3 * 8, "예상과 다른 변경 범위"
raw[st:st + len(seg)] = new
r = EndianBinaryReader(bytes(raw))
r.flags = flags
bundle.files[name] = r
open(OUT, "wb").write(bundle.save(packer="lz4"))
print("상인 첫 등장 조건: 사이클 10 이상 -> 제한 없음 (게임 시작부터) / 상인 항목 %d개" % n)
