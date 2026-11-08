"""data_balancing: 은신처로 언데드 '웨이브'(위협)가 새로 몰려오는 것을 막는다.
사용: python patch_waves.py <data_balancing 파일> <data_config 파일> <출력 파일>
 - ShelterAttackData.m_waveTriggerConditions 는 '모두 참일 때' 새 웨이브가 몰려오는 조건 목록이다.
   그 첫 번째 조건(WaveTrigger_ThreatBelowMaxThreat) 자리를 '항상 거짓' 조건(Trader_FeatureFlagDefinedCondition_Inverted, 기존 객체)으로 바꿔
   새 웨이브가 영영 시작되지 않게 한다. 크기 불변 (포인터 하나).
 - 거점에 처음 들어갔을 때 장면에 이미 있는 언데드를 처치하는 것(털기)은 그대로다. 이벤트가 직접 위협 수준을 올리는 경우는 그대로 남는다.
 - '한 번 턴 거점만' 구분하는 조건은 데이터에 없어서, 모든 은신처에 똑같이 적용된다.
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
cfg_ids = {}
for o_ in UnityPy.load(CFG).objects:
    if o_.type.name != "MonoBehaviour":
        continue
    try:
        cfg_ids[o_.read_typetree().get("m_Name")] = o_.path_id
    except Exception:
        pass
for need in ("Trader_FeatureFlagDefinedCondition_Inverted", "WaveTrigger_ThreatBelowMaxThreat"):
    if need not in cfg_ids:
        sys.exit("필요한 데이터를 찾지 못했습니다: %s" % need)
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
    if "m_waveTriggerConditions" not in t:
        continue
    wc = t["m_waveTriggerConditions"]
    if not wc or wc[0]["m_PathID"] != cfg_ids["WaveTrigger_ThreatBelowMaxThreat"] or wc[0]["m_FileID"] != 1:
        sys.exit("웨이브 조건 목록이 예상과 다릅니다 (이미 바뀌었거나 구조가 달라졌습니다)")
    wc[0] = {"m_FileID": 1, "m_PathID": cfg_ids["Trader_FeatureFlagDefinedCondition_Inverted"]}
    st = o.byte_start
    seg = bytes(raw[st:st + o.byte_size])
    nb = o.save_typetree(t)
    assert len(nb) == len(seg), "크기가 달라짐"
    d = [i for i in range(len(seg)) if seg[i] != nb[i]]
    assert d and len(d) <= 8, "예상과 다른 변경 범위"
    raw[st:st + len(seg)] = nb
    done += 1
if done != 1:
    sys.exit("ShelterAttackData 를 %d개 찾았습니다 (예상 1개)" % done)
r = EndianBinaryReader(bytes(raw))
r.flags = sf.flags
bundle.files[name] = r
open(OUT, "wb").write(bundle.save(packer="lz4"))
print("은신처 새 웨이브 조건: 항상 거짓으로 변경 (언데드 웨이브가 더 몰려오지 않음)")
