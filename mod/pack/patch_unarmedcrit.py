"""data_balancing: 맨손 무기 2종(무술가 SurvivorUnarmedMartialArts, 레슬링/브루탈 SurvivorUnarmedBrutal)의 크리티컬(치명 처형) 확률을 올린다.
사용: python patch_unarmedcrit.py <data_balancing 파일> <출력 파일> [확률 0~1, 기본 0.10]
 - 두 무기 정의의 CriticalExecuteChanceDamageAttribute.m_criticalChance 를 원래 값(0.02)에서 지정한 값으로 바꾼다 (float 4바이트 두 곳, 크기 불변).
 - 무기 정의 단위라 그 무기를 쓰는 모든 생존자에게 적용된다 (특성 섞기를 켜면 하오/이사야가 아니라 무술가/프로레슬러 특성을 새로 받은 생존자의 맨손 무기에 해당).
 - 그 밖의 치명 확률 요소(대상 종류별 보정, 체력 곡선, 특성의 +20% 등)는 그대로다.
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
CHANCE = float(sys.argv[3]) if len(sys.argv) > 3 else 0.10
if not 0.0 <= CHANCE <= 1.0:
    sys.exit("확률은 0~1 사이여야 합니다.")
WEAPONS = ("SurvivorUnarmedMartialArts_WeaponDefinition", "SurvivorUnarmedBrutal_WeaponDefinition")
env = UnityPy.load(SRC)
bundle = env.file
sfs = {n: f for n, f in bundle.files.items() if hasattr(f, "types")}
assert len(sfs) == 1, list(bundle.files)
name, sf = next(iter(sfs.items()))
raw = bytearray(sf.reader.bytes)
flags = sf.flags
found = {}
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        tt = o.read_typetree()
    except Exception:
        continue
    if tt.get("m_Name") in WEAPONS:
        found[tt["m_Name"]] = (o, tt)
if len(found) != len(WEAPONS):
    sys.exit("맨손 무기 정의를 %d개만 찾았습니다 (예상 %d개). 게임 업데이트로 구조가 바뀌었을 수 있습니다." % (len(found), len(WEAPONS)))
total = 0
done = []
for wn in WEAPONS:
    o, tt = found[wn]
    hits = [r for r in tt["references"]["RefIds"] if r["type"]["class"] == "CriticalExecuteChanceDamageAttribute"]
    if len(hits) != 1:
        sys.exit("%s 에서 CriticalExecuteChanceDamageAttribute 를 %d개 찾았습니다 (예상 1개). 아무것도 바꾸지 않았습니다." % (wn, len(hits)))
    d0 = hits[0]["data"]
    old = d0["m_criticalChance"]
    if abs(old - 0.02) > 1e-6 and abs(old - CHANCE) > 1e-6:
        sys.exit("%s 의 크리티컬 확률이 예상(0.02)과 다릅니다(%r). 이미 바뀌었거나 게임 업데이트로 값이 달라졌습니다. 아무것도 바꾸지 않았습니다." % (wn, old))
    d0["m_criticalChance"] = CHANCE
    st = o.byte_start
    seg = bytes(raw[st:st + o.byte_size])
    new = o.save_typetree(tt)
    assert len(new) == len(seg), "크기가 달라짐"
    dd = [i for i in range(len(seg)) if seg[i] != new[i]]
    assert len(dd) <= 4, "예상과 다른 변경 범위: %d" % len(dd)
    raw[st:st + len(seg)] = new
    total += len(dd)
    done.append((wn.replace("_WeaponDefinition", ""), old))
r = EndianBinaryReader(bytes(raw))
r.flags = flags
bundle.files[name] = r
open(OUT, "wb").write(bundle.save(packer="lz4"))
print("맨손 무기 크리티컬 확률: " + ", ".join("%s %.0f%% -> %.0f%%" % (n, o_ * 100, CHANCE * 100) for n, o_ in done) + " (바뀐 바이트 %d)" % total)
