"""data_levels: 모든 거점(은신처)의 '갈 수 있는 장소'(m_reachableLocations)에 교역소 5곳을 추가한다.
사용: python add_trading_posts.py <작업 폴더(data_levels, data_config 가 들어 있는 곳)>
 - 상인이 나오려면 AvailableTradingPostExists 조건(= 교역소 5곳 중 현재 거점에서 도달 가능한 곳이 있을 것)이 맞아야 한다.
   교역소 목록은 data_config 의 AvailableTradingPostExists.m_locationFilter 에서 읽는다.
 - 이미 들어 있는 교역소는 그대로 두고, 빠진 것만 목록 끝에 추가한다. 다른 목록/좌표는 건드리지 않는다.
 - 지도 섞기(shuffle_map.py)가 이 목록을 다시 계산하므로 반드시 섞기/반경 단계 '뒤'에 실행해야 한다.
 - 목록이 길어져 MapData 오브젝트 크기가 바뀌므로, 오브젝트 표/파일 크기를 함께 고친다 (shuffle_map.py 와 같은 방식).
"""
import os, struct, sys
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
    nsh, nadd, before_full, after_full = 0, 0, 0, 0
    for r in tt["references"]["RefIds"]:
        dd = r["data"]
        if "m_reachableLocations" not in dd or not dd["m_reachableLocations"]:
            continue   # 거점(은신처)만 갈 수 있는 장소 목록을 가진다
        nsh += 1
        have = {gid(g) for g in dd["m_reachableLocations"]}
        missing = [p for p in posts if p not in have]
        before_full += not missing
        for p in missing:
            dd["m_reachableLocations"].append(mkguid(p))
        nadd += len(missing)
        after_full += 1
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
    print("교역소 %d곳을 거점 %d곳의 '갈 수 있는 장소'에 추가: 추가한 항목 %d개 (원래 5곳 모두 포함이던 거점 %d곳)" % (len(posts), nsh, nadd, before_full))

if __name__ == "__main__":
    main()
