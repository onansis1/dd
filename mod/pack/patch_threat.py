"""data_balancing: 시간이 지나면서 지도 장소의 위협(해골 표시)이 오르는 것을 멈춘다.
사용: python patch_threat.py <data_balancing 파일> <출력 파일>
 - WorldDifficultyData 의 난이도 단계(사이클 20/40/60/80 에서 시작)마다 있는 m_spawnDifficultyIncrease(+1)를 모두 0 으로 바꾼다.
   게임 시작 단계(사이클 0)는 원래 0 이다. 정수 값만 바뀌어 크기는 그대로다.
 - 난이도 '단계' 번호(IsWorldDifficultyTier 조건, 이벤트/위협 계산에 쓰임)와 단계가 열리는 시점은 그대로다. 언데드 출현 난이도 증가분만 없앤다.
 - 장소마다 '한 번 턴 거점인지' 구분하는 값은 데이터에 없어서, 모든 장소에 똑같이 적용된다. 장소 자체의 기본 위협은 그대로다.
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

SRC, OUT = sys.argv[1:3]
env = UnityPy.load(SRC)
bundle = env.file
name, sf = [(n, f) for n, f in bundle.files.items() if hasattr(f, "types")][0]
raw = bytearray(sf.reader.bytes)
done = 0
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        t = o.read_typetree()
    except Exception:
        continue
    if "m_difficultyTiers" not in t:
        continue
    tiers = t["m_difficultyTiers"]
    if [x["m_startDay"] for x in tiers] != [0, 20, 40, 60, 80] or [x["m_spawnDifficultyIncrease"] for x in tiers] != [0, 1, 1, 1, 1]:
        sys.exit("난이도 단계가 예상과 다릅니다 (이미 바뀌었거나 게임 업데이트로 구조가 바뀌었을 수 있음)")
    for x in tiers:
        x["m_spawnDifficultyIncrease"] = 0
    st = o.byte_start
    seg = bytes(raw[st:st + o.byte_size])
    nb = o.save_typetree(t)
    assert len(nb) == len(seg), "크기가 달라짐"
    d = [i for i in range(len(seg)) if seg[i] != nb[i]]
    assert d and len(d) <= 16, "예상과 다른 변경 범위"
    raw[st:st + len(seg)] = nb
    done += 1
if done != 1:
    sys.exit("WorldDifficultyData 를 %d개 찾았습니다 (예상 1개)" % done)
r = EndianBinaryReader(bytes(raw))
r.flags = sf.flags
bundle.files[name] = r
open(OUT, "wb").write(bundle.save(packer="lz4"))
print("지도 장소 위협: 사이클 20/40/60/80 의 출현 난이도 증가(+1씩)를 제거 (시간이 지나도 위협이 오르지 않음)")
