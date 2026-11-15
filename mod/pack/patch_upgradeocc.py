"""data_balancing: 스테이션 업그레이드 레시피(작업대에서 만드는 *EquipmentL*_Recipe 와 *_Recipe_Engineer)의 필요 작업량 m_queueOccupancy 를 3 에서 2 로 낮춘다.
사용: python patch_upgradeocc.py <data_balancing 파일> <출력 파일> [새 값, 기본 2]
 - 이 52개 레시피만 바꾼다 (같은 값 3 을 가진 총기 수리/투척물/의약품 레시피 12개는 건드리지 않는다). 정수 4바이트씩이라 번들 크기는 그대로다.
 - 작업자 1명이 한 번 작업 틱마다 처리하는 양은 작업대 정의의 m_occupancyCapacity(5)이고, 이 값은 레시피 하나를 끝내는 데 필요한 총량이다.
   업그레이드를 대기열에 여러 개 넣었을 때 한 틱에 끝나는 개수가 늘어난다 (1개만 넣으면 3이든 2든 한 틱에 끝난다).
 - 새로 대기열에 넣는 항목에만 적용된다 (이미 대기열에 든 항목의 남은 작업량은 세이브에 저장돼 있다).
"""
import re, sys
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
NEW = int(sys.argv[3]) if len(sys.argv) > 3 else 2
OLD, EXPECT = 3, 52
NAME = re.compile(r"^[A-Za-z]+EquipmentL[123]_Recipe(_Engineer)?$")
if not 1 <= NEW <= 3:
    sys.exit("새 값은 1~3 사이여야 합니다.")
env = UnityPy.load(SRC)
bundle = env.file
sfs = {n: f for n, f in bundle.files.items() if hasattr(f, "types")}
assert len(sfs) == 1, list(bundle.files)
name, sf = next(iter(sfs.items()))
raw = bytearray(sf.reader.bytes)
flags = sf.flags
found = []
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        tt = o.read_typetree()
    except Exception:
        continue
    if NAME.match(tt.get("m_Name", "")) and "m_queueOccupancy" in tt:
        found.append((o, tt))
if len(found) != EXPECT:
    sys.exit("업그레이드 레시피를 %d개 찾았습니다 (예상 %d개). 게임 업데이트로 구조가 바뀌었을 수 있습니다. 아무것도 바꾸지 않았습니다." % (len(found), EXPECT))
vals = {tt["m_queueOccupancy"] for _o, tt in found}
if vals == {NEW}:
    print("스테이션 업그레이드 작업량: 이미 %d 입니다 (레시피 %d개)." % (NEW, EXPECT))
    open(OUT, "wb").write(open(SRC, "rb").read())
    sys.exit(0)
if vals != {OLD}:
    sys.exit("업그레이드 레시피의 작업량이 예상(%d)과 다릅니다(%s). 게임 업데이트로 값이 달라졌을 수 있습니다. 아무것도 바꾸지 않았습니다." % (OLD, sorted(vals)))
total = 0
for o, tt in found:
    tt["m_queueOccupancy"] = NEW
    st = o.byte_start
    seg = bytes(raw[st:st + o.byte_size])
    new = o.save_typetree(tt)
    assert len(new) == len(seg), "크기가 달라짐"
    dd = [i for i in range(len(seg)) if seg[i] != new[i]]
    assert len(dd) <= 4, "예상과 다른 변경 범위: %d (%s)" % (len(dd), tt["m_Name"])
    raw[st:st + len(seg)] = new
    total += len(dd)
r = EndianBinaryReader(bytes(raw))
r.flags = flags
bundle.files[name] = r
open(OUT, "wb").write(bundle.save(packer="lz4"))
print("스테이션 업그레이드 작업량: %d -> %d (레시피 %d개, 바뀐 바이트 %d)" % (OLD, NEW, EXPECT, total))
