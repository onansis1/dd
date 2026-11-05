"""data_balancing: 어둠의 심연(HeartOfDarkness_PlanDefinition)을 해금하는 데 필요한 단서 수를 0 으로 바꾼다 (게임 시작부터 열리게 하려는 시도).
사용: python patch_hod.py <data_balancing 파일> <출력 파일>
 - 튜토리얼 탈출 계획은 필요 단서 수가 0 이다. 같은 값(0)을 어둠의 심연에도 넣는다. 정수 하나만 바뀌어 크기는 그대로다.
 - 게임 코드가 이 값을 0 일 때 '바로 열림'으로 처리하는지는 확인하지 못했다 (단서 획득 이벤트가 있을 때만 비교하면 효과가 없을 수 있다).
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
done = False
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        tt = o.read_typetree()
    except Exception:
        continue
    if tt.get("m_Name") != "HeartOfDarkness_PlanDefinition":
        continue
    if tt.get("m_numberOfLeadsRequiredToUnlock") not in (1, 3):
        sys.exit("어둠의 심연 필요 단서 수가 예상(1 또는 3)과 다릅니다: %r" % tt.get("m_numberOfLeadsRequiredToUnlock"))
    st = o.byte_start
    seg = bytes(raw[st:st + o.byte_size])
    tt["m_numberOfLeadsRequiredToUnlock"] = 0
    new = o.save_typetree(tt)
    assert len(new) == len(seg), "크기가 달라짐"
    d = [i for i in range(len(seg)) if seg[i] != new[i]]
    assert d and max(d) < d[0] + 4, "예상과 다른 변경 범위"
    raw[st + d[0]:st + d[0] + 4] = bytes(new[d[0]:d[0] + 4])
    done = True
if not done:
    sys.exit("HeartOfDarkness_PlanDefinition 을 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음)")
r = EndianBinaryReader(bytes(raw))
r.flags = flags
bundle.files[name] = r
open(OUT, "wb").write(bundle.save(packer="lz4"))
print("어둠의 심연 필요 단서 수 -> 0 (시작부터 열리게 하는 시도, 게임 내 동작 미확인)")
