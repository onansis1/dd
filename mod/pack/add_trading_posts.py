"""data_levels: 모든 거점(은신처)의 탐색 반경(지도의 원) 안에 교역소가 최소 N곳(기본 1) 들어가게 한다.
사용: python add_trading_posts.py <작업 폴더(data_levels, data_config 가 들어 있는 곳)> [최소 교역소 수=1]
 - 상인이 나오려면 AvailableTradingPostExists 조건(= 교역소 5곳 중 현재 거점에서 도달 가능한 곳이 있을 것)이 맞아야 한다.
   교역소 목록은 data_config 의 AvailableTradingPostExists.m_locationFilter 에서 읽는다.
 - 원 안에 교역소가 N곳 미만인 거점만, 그 거점의 반경(m_scavengeRadius)을 N번째로 가까운 교역소에 닿을 만큼(+3%) 늘리고,
   새 반경 안의 장소를 '갈 수 있는 장소' 목록에 추가한다. 원 밖의 먼 교역소는 목록에 넣지 않는다 (게임이 원 밖 교역소를 뽑는 것을 막기 위해).
 - 스토리 전용으로 숨긴 장소(이름에 chiefways 포함)는 새로 목록에 넣지 않는다.
 - 지도 섞기(shuffle_map.py)가 목록을 다시 계산하므로 반드시 섞기/반경 단계 '뒤'에 실행해야 한다.
 - 목록이 길어져 MapData 오브젝트 크기가 바뀌므로, 오브젝트 표/파일 크기를 함께 고친다 (shuffle_map.py 와 같은 방식).
"""
import math, os, struct, sys
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
from UnityPy.files import ObjectReader as _ORcls
from UnityPy.streams import EndianBinaryReader

ENTRY = {}
_orig_from_reader = _ORcls.from_reader.__func__
def _fr(cls, assets_file, reader):
    before = reader.Position
    obj = _orig_from_reader(cls, assets_file, reader)
    ENTRY[obj.path_id] = (before + 3) // 4 * 4
    return obj
_ORcls.from_reader = classmethod(_fr)

gid = lambda g: bytes(g["m_guid"]["bytes[%d]" % i] for i in range(16))
mkguid = lambda b: {"m_guid": {"bytes[%d]" % i: b[i] for i in range(16)}}

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    d = sys.argv[1]
    lv_p, cfg_p = os.path.join(d, "data_levels"), os.path.join(d, "data_config")
    posts = None
    for o in UnityPy.load(cfg_p).objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            tt = o.read_typetree()
        except Exception:
            continue
        if tt.get("m_Name") == "AvailableTradingPostExists":
            posts = [gid(g) for g in tt["m_locationFilter"]]
            break
    if not posts:
        sys.exit("data_config 에서 교역소 목록(AvailableTradingPostExists)을 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음)")
    data = open(lv_p, "rb").read()
    ENTRY.clear()
    env = UnityPy.load(data)
    bundle = env.file
    name, sf = [(n, f) for n, f in bundle.files.items() if hasattr(f, "types")][0]
    raw = bytearray(sf.reader.bytes)
    hdr = sf.header
    if hdr.version < 22:
        sys.exit("지원하지 않는 번들 버전입니다: %d" % hdr.version)
    scr = {o.path_id: o.read().m_ClassName for o in env.objects if o.type.name == "MonoScript"}
    target = None
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            tt = o.read_typetree()
        except Exception:
            continue
        if scr.get(tt["m_Script"]["m_PathID"]) == "MapData":
            target = (o, tt)
            break
    if target is None:
        sys.exit("MapData 를 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있습니다).")
    o, tt = target
    min_posts = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    names = {}
    for x in env.objects:
        if x.type.name != "MonoBehaviour":
            continue
        try:
            t2 = x.read_typetree()
        except Exception:
            continue
        if isinstance(t2.get("m_guid"), dict) and "m_guid" in t2["m_guid"]:
            names[gid(t2["m_guid"])] = t2.get("m_Name", "")
    hidden = lambda k: "chiefways" in names.get(k, "").lower()
    refs = tt["references"]["RefIds"]
    pos = {}
    for r in refs:
        dd = r["data"]
        if "m_locationReference" in dd and "m_position" in dd:
            pos[gid(dd["m_locationReference"])] = (dd["m_position"]["x"], dd["m_position"]["y"])
    posts = [p for p in posts if p in pos]
    nsh, widened, added = 0, [], 0
    for r in refs:
        if r["type"]["class"] != "MapShelterLocationData":
            continue
        dd = r["data"]
        nsh += 1
        me = gid(dd["m_locationReference"])
        px, py = pos[me]
        dist = lambda k: math.hypot(pos[k][0] - px, pos[k][1] - py)
        R = dd["m_scavengeRadius"]
        ordered = sorted(posts, key=dist)
        need = min(min_posts, len(ordered))
        newR = R
        if need and dist(ordered[need - 1]) > R:
            newR = math.ceil(dist(ordered[need - 1]) * 1.03 * 10) / 10
        have = {gid(x) for x in dd["m_reachableLocations"]}
        if newR > R:
            dd["m_scavengeRadius"] = newR
            widened.append((names.get(me, "?")[:40], R, newR))
        # 반경 안에 있는 교역소/장소가 목록에 빠져 있으면 채운다 (숨김 장소는 제외)
        within = [k for k in pos if dist(k) <= dd["m_scavengeRadius"] and k not in have and not hidden(k)]
        for k in sorted(within, key=dist):
            dd["m_reachableLocations"].append(mkguid(k))
            added += 1
    if not widened and not added:
        print("모든 거점의 탐색 반경 안에 교역소가 이미 %d곳 이상 있습니다. 바꿀 것이 없습니다." % min_posts)
        return
    new = bytes(o.save_typetree(tt))
    A = 16
    up = lambda n: (n + A - 1) // A * A
    objs = sorted(env.objects, key=lambda x: x.byte_start)
    idx = [x.path_id for x in objs].index(o.path_id)
    abs_start = o.byte_start
    old_span = (objs[idx + 1].byte_start - abs_start) if idx + 1 < len(objs) else (len(raw) - abs_start)
    if old_span != up(o.byte_size):
        sys.exit("예상과 다른 오브젝트 배치입니다.")
    new_span = up(len(new))
    delta = new_span - old_span
    out = bytearray(raw[:abs_start]) + new + b"\x00" * (new_span - len(new)) + raw[abs_start + old_span:]
    for x in objs:
        e = ENTRY[x.path_id]
        pid, bs, sz = struct.unpack_from("<qqI", raw, e)
        if pid != x.path_id or bs != x.byte_start - hdr.data_offset or sz != x.byte_size:
            sys.exit("오브젝트 표 해석이 예상과 다릅니다. 중단합니다.")
        if x.byte_start > abs_start:
            struct.pack_into("<q", out, e + 8, bs + delta)
        elif x.path_id == o.path_id:
            struct.pack_into("<I", out, e + 16, len(new))
    struct.pack_into(">q", out, 24, len(out))
    r_ = EndianBinaryReader(bytes(out))
    r_.flags = sf.flags
    bundle.files[name] = r_
    tmp = lv_p + ".tmp"
    with open(tmp, "wb") as f:
        f.write(bundle.save(packer="lz4"))
    os.replace(tmp, lv_p)
    print("교역소 포함: 거점 %d곳 중 반경을 늘린 곳 %d곳, 목록에 추가한 장소 %d개 (원 안에 교역소 최소 %d곳)" % (nsh, len(widened), added, min_posts))
    for n_, r0, r1 in widened:
        print("  %s : 반경 %.0f -> %.0f" % (n_, r0, r1))

if __name__ == "__main__":
    main()
