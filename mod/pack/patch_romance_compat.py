"""data_balancing: 연애가 맺어질 확률에 반영되는 '호환성 속성' 4개(나이대 / 성적 지향 / 실연 상태 / 입냄새)를 푼다.
사용: python patch_romance_compat.py <data_balancing 파일> <data_config 파일> <출력 파일>
 - RomanceCompatibilityAttribute 의 m_compatibilityCondition 을 '항상 참'인 조건(Relationships_FeatureFlagDefinedCondition)으로 바꾼다.
   이 조건은 문맥(생존자/쌍)과 상관없이 기능 플래그만 보므로 어느 문맥에서 평가돼도 안전하다. 포인터만 바뀌어 오브젝트 크기는 같다.
 - 'IsDateable'(연애 대상이 될 수 있는 캐릭터인가)과 'RelationshipPairTier'(관계 단계)는 건드리지 않는다.
   (개 같은 부양 대상이나 서로 모르는 사이가 연애 대상이 되는 것을 막는 장치이기 때문)
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
WANT = ["AgeMatch_RomanceCompatibilityAttribute", "SexualPreferenceMatch_RomanceCompatibilityAttribute",
        "BrokenHeart_RomanceCompatibilityAttribute", "BadBreath_RomanceCompatibilityAttribute"]
TRUE_COND = "Relationships_FeatureFlagDefinedCondition"
true_pid = None
for o_ in UnityPy.load(CFG).objects:
    if o_.type.name != "MonoBehaviour":
        continue
    try:
        if o_.read_typetree().get("m_Name") == TRUE_COND:
            true_pid = o_.path_id
            break
    except Exception:
        pass
if true_pid is None:
    sys.exit("data_config 에서 %s 를 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음)" % TRUE_COND)
env = UnityPy.load(SRC)
bundle = env.file
sfs = {n: f for n, f in bundle.files.items() if hasattr(f, "types")}
assert len(sfs) == 1, list(bundle.files)
name, sf = next(iter(sfs.items()))
raw = bytearray(sf.reader.bytes)
flags = sf.flags
done = []
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        tt = o.read_typetree()
    except Exception:
        continue
    if tt.get("m_Name") not in WANT:
        continue
    st = o.byte_start
    seg = bytes(raw[st:st + o.byte_size])
    tt["m_compatibilityCondition"] = {"m_FileID": 1, "m_PathID": true_pid}   # FileID 1 = data_config (다른 bal 오브젝트도 같은 방식으로 참조)
    new = o.save_typetree(tt)
    assert len(new) == len(seg), tt["m_Name"] + ": 크기가 달라짐"
    d = [i for i in range(len(seg)) if seg[i] != new[i]]
    assert d and max(d) - min(d) < 16, tt["m_Name"] + ": 예상과 다른 변경 범위"
    raw[st:st + len(seg)] = new
    done.append(tt["m_Name"].replace("_RomanceCompatibilityAttribute", ""))
if len(done) != len(WANT):
    sys.exit("호환성 속성 %d개만 찾았습니다 (예상 %d개)" % (len(done), len(WANT)))
r = EndianBinaryReader(bytes(raw))
r.flags = flags
bundle.files[name] = r
open(OUT, "wb").write(bundle.save(packer="lz4"))
print("연애 호환성 속성 해제: " + ", ".join(sorted(done)))
