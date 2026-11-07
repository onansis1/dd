"""data_balancing: 스필존 '스킵의 스쿱' 아이스크림 가게의 준(June)에게 방호복을 받는 조건을
'칠리 콘 카르네 4개'에서 '락픽 1개'로 바꾼다.
사용: python patch_june.py <data_balancing 파일> <data_config 파일> <출력 파일>
 - 조건 Spillzone_05_June_01_HasItemOptionalInInventory_4_ChiliConCarne (대화 선택지 두 곳이 사용)과
   소모 동작 Spillzone_05_June_01_RemoveOptionalSurvivorInventory_RemoveChiliConCarne 의 아이템 목록(칠리 콘 카르네 / 오래된 칠리)을
   락픽으로, 개수 4 를 1 로 바꾼다. 목록 길이는 그대로(락픽 두 칸)라 오브젝트 크기는 변하지 않는다.
 - 대화 문구(번역 텍스트)는 코드/번역 파일 쪽이라 바꾸지 않았다: 대사에는 여전히 칠리라고 나올 수 있다.
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

SRC, CFG, OUT = sys.argv[1:4]
lock = None
for o_ in UnityPy.load(CFG).objects:
    if o_.type.name != "MonoBehaviour":
        continue
    try:
        t_ = o_.read_typetree()
    except Exception:
        continue
    if t_.get("m_Name") == "Lockpick" and "m_maxStack" in t_:
        lock = t_["m_guid"]
if lock is None:
    sys.exit("Lockpick 아이템을 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음)")
env = UnityPy.load(SRC)
bundle = env.file
name, sf = [(n, f) for n, f in bundle.files.items() if hasattr(f, "types")][0]
raw = bytearray(sf.reader.bytes)
COND = "Spillzone_05_June_01_HasItemOptionalInInventory_4_ChiliConCarne"
ACT = "Spillzone_05_June_01_RemoveOptionalSurvivorInventory_RemoveChiliConCarne"
found = {}
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        t = o.read_typetree()
    except Exception:
        continue
    if t.get("m_Name") in (COND, ACT):
        found[t["m_Name"]] = (o, t)
if len(found) != 2:
    sys.exit("준의 대화 조건/동작을 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음)")
def edit(o, t, data):
    if len(data["m_itemDefinitionGuids"]) != 2 or data["m_count"] != 4:
        sys.exit("%s: 예상과 다른 구조/개수 (이미 바뀌었거나 구조가 달라졌습니다)" % t["m_Name"])
    data["m_itemDefinitionGuids"] = [{"m_guid": dict(lock["m_guid"])}, {"m_guid": dict(lock["m_guid"])}]
    data["m_count"] = 1
    st = o.byte_start
    seg = bytes(raw[st:st + o.byte_size])
    nb = o.save_typetree(t)
    assert len(nb) == len(seg), "크기가 달라짐"
    d = [i for i in range(len(seg)) if seg[i] != nb[i]]
    assert d and len(d) <= 40, "예상과 다른 변경 범위"
    raw[st:st + len(seg)] = nb
o, t = found[COND]
edit(o, t, t["m_optionItemAmountData"])
o, t = found[ACT]
if len(t["m_items"]) != 1:
    sys.exit("소모 동작 구조가 예상과 다릅니다")
edit(o, t, t["m_items"][0])
r = EndianBinaryReader(bytes(raw))
r.flags = sf.flags
bundle.files[name] = r
open(OUT, "wb").write(bundle.save(packer="lz4"))
print("준(스킵의 스쿱) 방호복 교환: 칠리 콘 카르네 4개 -> 락픽 1개")
