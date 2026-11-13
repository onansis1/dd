"""data_balancing: 상인(마와 파 / 미스터 베일 / 리키)이 처음 나올 수 있는 시점을 앞당긴다 (원래 사이클 10).
사용: python patch_traders.py <data_balancing 파일> <data_config 파일> <출력 파일> [시작 사이클 0~10] [nochance]  (기본 0)
 - 10: 사이클 조건은 그대로 두고(nochance 와 같이 쓸 때), nochance: 상인 항목 3개에서 '90PercentChance'(RandomChanceCondition, 반전, 확률 0.9) 조건을 뺀다.
   이 조건은 반전돼 있어서 상인 이벤트가 쿨다운을 지난 뒤에도 사이클마다 약 10%만 통과하는 것으로 보인다(실제 플레이에서 25일째 처음 온 사례). 빼면 쿨다운(빠름 3사이클, 기본 6, 느림 10)마다 확정으로 온다.
 - 1~9: 해당 사이클 부터 (N). 아래 방식에서 값을 N-1 로 바꾼다.
 - (7 의 경우) '7 이상' 조건 객체가 없어서, 관계 일상 이벤트 하나만 쓰는 'RelationshipDaylog_Random_IsCycleGreaterThan7'
   (사이클 7 초과)의 값을 6 으로 바꿔 '6 초과 = 7 이상' 으로 만들고 상인 항목이 그것을 보게 한다. (그 관계 이벤트는 1사이클 일찍 시작함)
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
START = int(sys.argv[4]) if len(sys.argv) > 4 else 0
NOCHANCE = "nochance" in sys.argv[5:]
if not 0 <= START <= 10 or (START == 10 and not NOCHANCE):
    sys.exit("시작 사이클은 0~9 이어야 합니다 (10 은 원래대로라 nochance 와 같이 쓸 때만 허용)")
# 조건 객체(IsCycleGreaterOrEqual10 등)는 data_config 에 있고, data_balancing 의 선택기는 그것을 외부 참조(m_FileID != 0)로 가리킨다.
cfg_ids = {}
for o_ in UnityPy.load(CFG).objects:
    if o_.type.name != "MonoBehaviour":
        continue
    try:
        cfg_ids[o_.read_typetree().get("m_Name")] = o_.path_id
    except Exception:
        pass
for need in ("IsCycleGreaterOrEqual10", "Trader_FeatureFlagDefinedCondition", "AvailableTradingPostExists", "90PercentChance"):
    if need not in cfg_ids:
        sys.exit("필요한 데이터를 찾지 못했습니다: %s (게임 업데이트로 구조가 바뀌었을 수 있음)" % need)
cyc10, keep, post = cfg_ids["IsCycleGreaterOrEqual10"], cfg_ids["Trader_FeatureFlagDefinedCondition"], cfg_ids["AvailableTradingPostExists"]
chance = cfg_ids["90PercentChance"]
env = UnityPy.load(SRC)
bundle = env.file
sfs = {n: f for n, f in bundle.files.items() if hasattr(f, "types")}
assert len(sfs) == 1, list(bundle.files)
name, sf = next(iter(sfs.items()))
raw = bytearray(sf.reader.bytes)
flags = sf.flags
target = None
gt7 = None
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        tt = o.read_typetree()
    except Exception:
        continue
    if tt.get("m_Name") == "PassiveShelterEvents_MedPriority_ConditionallyWeightedPassiveEventTriggerPicker":
        target = (o, tt)
    elif tt.get("m_Name") == "RelationshipDaylog_Random_IsCycleGreaterThan7":
        gt7 = (o, tt)
if target is None:
    sys.exit("PassiveShelterEvents_MedPriority 선택기를 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음)")
o, tt = target
if 1 <= START <= 9:
    if gt7 is None or gt7[1].get("m_value") != 7 or gt7[1].get("m_compareLogic") != 2:
        sys.exit("RelationshipDaylog_Random_IsCycleGreaterThan7 를 찾지 못했거나 예상과 다릅니다 (이미 바뀌었거나 게임 업데이트로 구조가 바뀌었을 수 있음)")
    # 이 조건 객체를 쓰는 곳은 관계 일상 이벤트 하나(+초기화 등록)뿐이다. 7 초과 -> 6 초과(= 7 이상) 로 바꿔 상인 항목이 쓰게 한다.
    og, tg = gt7
    tg["m_value"] = START - 1
    stg = og.byte_start
    segg = bytes(raw[stg:stg + og.byte_size])
    newg = og.save_typetree(tg)
    assert len(newg) == len(segg), "크기가 달라짐"
    dg = [i for i in range(len(segg)) if segg[i] != newg[i]]
    assert dg and len(dg) <= 4, "예상과 다른 변경 범위"
    raw[stg:stg + len(segg)] = newg
n = 0
for w in tt["m_weightedOptions"]:
    cs = [c["m_PathID"] for c in w["m_conditions"]]
    if post in cs and keep in cs and (cyc10 in cs or (START == 10 and chance in cs)):
        if START == 10:
            pass                                  # 사이클 조건은 그대로
        elif START >= 1:
            # 사이클 10 조건 자리에 '사이클 N 이상' 조건(같은 번들 안의 객체, FileID 0)을 연결한다
            w["m_conditions"][cs.index(cyc10)] = {"m_FileID": 0, "m_PathID": gt7[0].path_id}
        else:
            # 같은 목록에 이미 있는 '상인 기능 켜짐' 조건(항상 참)을 한 번 더 가리키게 해서 사이클 조건을 없앤다
            w["m_conditions"][cs.index(cyc10)] = dict(w["m_conditions"][cs.index(keep)])
        if NOCHANCE:                              # 90PercentChance 자리를 '상인 기능 켜짐'(항상 참)으로 바꿔 확률 판정을 없앤다 (크기 불변)
            cs2 = [c["m_PathID"] for c in w["m_conditions"]]
            if chance in cs2:
                w["m_conditions"][cs2.index(chance)] = dict(w["m_conditions"][cs2.index(keep)])
        n += 1
if n != 3:
    sys.exit("상인 항목 %d개만 찾았습니다 (예상 3개). 이미 바뀌었거나 구조가 달라졌습니다." % n)
st = o.byte_start
seg = bytes(raw[st:st + o.byte_size])
new = o.save_typetree(tt)
assert len(new) == len(seg), "크기가 달라짐"
d = [i for i in range(len(seg)) if seg[i] != new[i]]
assert d and len(d) <= 3 * 12 * (2 if NOCHANCE else 1), "예상과 다른 변경 범위"
raw[st:st + len(seg)] = new
r = EndianBinaryReader(bytes(raw))
r.flags = flags
bundle.files[name] = r
open(OUT, "wb").write(bundle.save(packer="lz4"))
print("상인 첫 등장 조건: 사이클 10 이상 -> %s / 상인 항목 %d개" % ((("사이클 %d 이상" % START) if START >= 1 else "제한 없음 (게임 시작부터)") if START < 10 else "그대로", n) + (" / 방문 확률 판정 제거(쿨다운마다 확정)" if NOCHANCE else ""))
