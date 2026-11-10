"""data_balancing: 무기 작업대(WeaponsBench)에서 모든 총알 종류(권총/리볼버/샷건/소총/돌격소총, 각 일반/탄약 전문가 판)를 1레벨부터 만들 수 있게 한다.
사용: python patch_ammolevel.py <data_balancing 파일> <출력 파일>
 - 무기 작업대 정의(WorkstationDefinition 'WeaponsBench')는 레벨(1~3)마다 '만들 수 있는 레시피 목록'(m_recipeDefinitionIds)을 따로 가진다.
   기본: 1레벨=권총 총알, 2레벨=+리볼버/샷건, 3레벨=+소총/돌격소총. 3레벨 목록에 있는 총알 레시피(탄약 전문가 판 포함)가 1,2레벨 목록에도 모두 들어가게 빠진 것을 목록 끝에 덧붙인다.
 - 목록 길이가 바뀌므로 그 오브젝트의 크기가 늘어난다. 이 오브젝트 뒤의 모든 오브젝트의 위치를 같은 만큼 옮기고, 오브젝트 표와 파일 크기를 고친다. 고친 뒤 다시 읽어서 (1) 바뀐 오브젝트가 의도한 대로인지 (2) 다른 오브젝트의 내용이 한 바이트도 달라지지 않았는지 확인하고, 아니면 아무것도 쓰지 않고 중단한다.
 - 재료/제작 시간/특성 조건은 그대로다. 작업대 레벨 올리기 자체는 그대로 필요하지만 총알은 1레벨부터 만들 수 있다.
"""
import copy, re, struct, sys
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
AMMO_RE = re.compile(r"^[A-Za-z0-9]+Ammo(_MunitionsExpert)?_Recipe$")

def align8(n):
    return (n + 7) // 8 * 8

def guid_of(x):
    g = x.get("m_guid")
    return bytes(g["bytes[%d]" % i] for i in range(16)) if isinstance(g, dict) and "bytes[0]" in g else None

env = UnityPy.load(SRC)
bundle = env.file
sfs = {n: f for n, f in bundle.files.items() if hasattr(f, "types")}
assert len(sfs) == 1, list(bundle.files)
name, sf = next(iter(sfs.items()))
raw = bytes(sf.reader.bytes)
scripts = {o.path_id: o.read().m_ClassName for o in env.objects if o.type.name == "MonoScript"}
objs = list(env.objects)
recipe_name = {}
wb = None
for o in objs:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        t = o.read_typetree()
    except Exception:
        continue
    c = scripts.get(t["m_Script"]["m_PathID"])
    if c == "QueuedRecipeDefinition":
        g = guid_of(t.get("m_guid") or {})
        if g is not None:
            recipe_name[g] = t.get("m_Name", "")
    elif c == "WorkstationDefinition" and t.get("m_Name") == "WeaponsBench":
        wb = (o, t)
if wb is None:
    sys.exit("무기 작업대(WeaponsBench) 정의를 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음)")
o, t = wb
levels = t["m_levelDefinitions"]
if len(levels) < 2:
    sys.exit("무기 작업대의 레벨 구조가 예상과 다릅니다")
top = levels[-1]["m_definition"]["m_recipeDefinitionIds"]
ammo = [x for x in top if AMMO_RE.match(recipe_name.get(guid_of(x), ""))]
if not ammo:
    sys.exit("무기 작업대에서 총알 레시피를 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음)")
added = 0
per_level = []
for lv in levels:
    lst = lv["m_definition"]["m_recipeDefinitionIds"]
    have = {guid_of(x) for x in lst}
    n = 0
    for a in ammo:
        if guid_of(a) not in have:
            lst.append(copy.deepcopy(a))
            n += 1
    per_level.append(n)
    added += n
if added == 0:
    print("무기 작업대: 모든 레벨에 이미 모든 총알 레시피가 있습니다 (바꿀 것이 없음).")
    open(OUT, "wb").write(open(SRC, "rb").read())
    sys.exit(0)

old_start, old_size = o.byte_start, o.byte_size
old_seg = raw[old_start:old_start + old_size]
new_seg = o.save_typetree(t)
delta_obj = len(new_seg) - old_size
assert delta_obj == 16 * added, (delta_obj, added)
# 오브젝트 표(직렬화 파일 머리 부분의 메타데이터): 오브젝트마다 (path_id int64, byte_start int64, byte_size uint32, type_id) 가 이어진다
ver, = struct.unpack(">I", raw[8:12]); assert ver >= 22, ver
meta_size, file_size, data_off = struct.unpack(">IqQ", raw[20:40])
assert file_size == len(raw), (file_size, len(raw))
first = objs[0]
pat = struct.pack("<qqI", first.path_id, first.byte_start - data_off, first.byte_size)
base = raw.find(pat, 0, data_off)
assert base >= 0 and raw.find(pat, base + 1, data_off) < 0, "오브젝트 표 위치를 찾지 못했습니다"
# 표의 항목 간격(오브젝트마다 같은 크기)을 두 번째 항목으로 알아낸다
second = objs[1]
pat2 = struct.pack("<qqI", second.path_id, second.byte_start - data_off, second.byte_size)
stride = raw.find(pat2, base + 1, data_off) - base
assert 20 <= stride <= 32, stride
ents = {}
for k, ob in enumerate(objs):
    off = base + stride * k
    p, bs, sz = struct.unpack("<qqI", raw[off:off + 20])
    assert (p, bs, sz) == (ob.path_id, ob.byte_start - data_off, ob.byte_size), ("오브젝트 표가 예상과 다릅니다", k)
    ents[ob.path_id] = off
old_end = align8(old_start + old_size - data_off) + data_off          # 이 오브젝트 다음 오브젝트가 시작하는 위치(8바이트 정렬)
new_end = align8(old_start + len(new_seg) - data_off) + data_off
shift = new_end - old_end
assert shift == delta_obj and shift % 8 == 0, (shift, delta_obj)
new_raw = bytearray(raw[:old_start]) + new_seg + b"\0" * (new_end - (old_start + len(new_seg))) + raw[old_end:]
struct.pack_into("<qqI", new_raw, ents[o.path_id], o.path_id, old_start - data_off, len(new_seg))
for ob in objs:
    if ob.path_id != o.path_id and ob.byte_start >= old_end:
        struct.pack_into("<qqI", new_raw, ents[ob.path_id], ob.path_id, ob.byte_start - data_off + shift, ob.byte_size)
struct.pack_into(">q", new_raw, 24, len(new_raw))

# 쓰기 전 검증 1: 직렬화 파일을 다시 읽어 오브젝트 수/내용 비교
r = EndianBinaryReader(bytes(new_raw))
r.flags = sf.flags
bundle.files[name] = r
data = bundle.save(packer="lz4")
env2 = UnityPy.load(data)
objs2 = list(env2.objects)
assert len(objs2) == len(objs), "오브젝트 수가 달라졌습니다"
changed = 0
for a, b in zip(objs, objs2):
    assert a.path_id == b.path_id and a.type.name == b.type.name
    ra = raw[a.byte_start:a.byte_start + a.byte_size]
    rb = bytes(new_raw[b.byte_start:b.byte_start + b.byte_size])
    if a.path_id == o.path_id:
        assert rb == new_seg
        continue
    if ra != rb:
        changed += 1
assert changed == 0, "다른 오브젝트 %d개의 내용이 달라졌습니다" % changed
t2 = [x for x in objs2 if x.path_id == o.path_id][0].read_typetree()
for lv in t2["m_levelDefinitions"]:
    have = {guid_of(x) for x in lv["m_definition"]["m_recipeDefinitionIds"]}
    assert all(guid_of(a) in have for a in ammo), "총알 레시피가 빠졌습니다"
open(OUT, "wb").write(data)
print("무기 작업대 총알 레시피 %d종을 모든 레벨(1~%d)에서 사용 가능하게: 레벨별 추가 %s개 (오브젝트 %d바이트 증가, 이후 오브젝트 %d개 이동)" % (len(ammo), len(levels), "/".join(map(str, per_level)), delta_obj, sum(1 for ob in objs if ob.byte_start >= old_end)))
