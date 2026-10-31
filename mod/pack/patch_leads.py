"""data_balancing: 탈출 퀘스트(탈출 계획)를 해금하는 데 필요한 '단서(조사 장소)' 수를 바꾼다.
사용: python patch_leads.py <data_balancing 파일> <필요 단서 수> <출력 파일>
 - 모든 탈출 계획(EscapePlanDefinition)의 m_numberOfLeadsRequiredToUnlock 중 3 인 것을 지정한 수로 바꾼다. (튜토리얼 0, 스팀 데모 전용 4 는 그대로)
 - 같은 크기의 정수 하나만 바뀌므로 오브젝트 크기/배치는 변하지 않는다.
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

SRC, NEW, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3]
if NEW < 1:
    sys.exit("필요 단서 수는 1 이상이어야 합니다")
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
    if tt.get("m_numberOfLeadsRequiredToUnlock") != 3:
        continue
    st = o.byte_start
    seg = bytes(raw[st:st + o.byte_size])
    tt["m_numberOfLeadsRequiredToUnlock"] = NEW
    new = o.save_typetree(tt)
    assert len(new) == len(seg), tt["m_Name"] + ": 크기가 달라짐"
    d = [i for i in range(len(seg)) if seg[i] != new[i]]
    assert d and max(d) < d[0] + 4, tt["m_Name"] + ": 예상과 다른 변경 범위"
    raw[st + d[0]:st + d[0] + 4] = bytes(new[d[0]:d[0] + 4])
    done.append(tt["m_Name"])
if not done:
    sys.exit("바꿀 탈출 계획을 찾지 못했습니다 (이미 바뀌었거나 게임 업데이트로 구조가 바뀌었을 수 있음)")
r = EndianBinaryReader(bytes(raw))
r.flags = flags
bundle.files[name] = r
open(OUT, "wb").write(bundle.save(packer="lz4"))
print("탈출 퀘스트 필요 단서 수 3 -> %d : %s" % (NEW, ", ".join(done)))
