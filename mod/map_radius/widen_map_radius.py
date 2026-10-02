"""Into the Dead: Our Darkest Days - 은신처 탐색 반경(지도의 원) 넓히기.
사용: python widen_map_radius.py <AssetBundles 폴더 경로> [배수=1.5]
data_levels 의 각 은신처(MapShelterLocationData)의 m_scavengeRadius 를 배수만큼 키우고,
m_reachableLocations(갈 수 있는 장소 목록)를 새 반경 안의 모든 장소로 다시 만든다.
처음 실행할 때 data_levels.bak 으로 백업한다. 게임을 끈 상태에서 실행할 것.
이미 넓혀진 파일에 다시 실행해도 원본 반경(987.5) 기준으로 계산하므로 배수가 누적되지 않는다.
"""
import math, os, shutil, struct, sys
import UnityPy.helpers.TypeTreeNode as T

# 빌드 6000.5.x 번들의 타입트리 헤더 추가 28바이트를 건너뛰는 패치 (저장은 원본 바이트를 직접 수정하므로 안전)
_orig = T.TypeTreeNode.parse_blob.__func__
def _pb(cls, reader, version):
    reader.Position = reader.Position + 28
    return _orig(cls, reader, version)
T.TypeTreeNode.parse_blob = classmethod(_pb)

import UnityPy
from UnityPy.files import ObjectReader as _ORcls
from UnityPy.streams import EndianBinaryReader

BASE_RADIUS = 987.5      # 게임 기본 반경 (배수 누적 방지용 기준)
ENTRY = {}               # path_id -> 오브젝트 표 항목의 파일 내 오프셋

_orig_from_reader = _ORcls.from_reader.__func__
def _fr(cls, assets_file, reader):
    before = reader.Position
    obj = _orig_from_reader(cls, assets_file, reader)
    ENTRY[obj.path_id] = (before + 3) // 4 * 4
    return obj
_ORcls.from_reader = classmethod(_fr)

def gid(g):
    return bytes(g["m_guid"]["bytes[%d]" % i] for i in range(16))

def mkguid(b):
    return {"m_guid": {"bytes[%d]" % i: b[i] for i in range(16)}}

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = os.path.join(sys.argv[1], "data_levels")
    factor = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
    if not os.path.isfile(path):
        sys.exit("data_levels 를 찾을 수 없습니다: " + path)
    with open(path, "rb") as fh:
        data = fh.read()
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
    refs = tt["references"]["RefIds"]

    pos = {}
    for r in refs:
        d = r["data"]
        if "m_locationReference" in d and "m_position" in d:
            pos[gid(d["m_locationReference"])] = (d["m_position"]["x"], d["m_position"]["y"])

    newR = round(BASE_RADIUS * factor, 1)
    report = []
    for r in refs:
        if r["type"]["class"] != "MapShelterLocationData":
            continue
        d = r["data"]
        me = gid(d["m_locationReference"])
        px, py = pos[me]
        old_list = [gid(x) for x in d["m_reachableLocations"]]
        have = set(old_list)
        # 새 반경 안의 장소 (자기 자신 포함) - 기존 순서는 유지하고 새로 들어오는 곳만 거리순으로 뒤에 추가
        within = [k for k in pos if math.hypot(pos[k][0] - px, pos[k][1] - py) <= newR]
        # 기본 반경 기준 목록은 항상 유지 (반경을 줄이는 경우 방지)
        keep = [k for k in old_list if k in pos]
        add = sorted((k for k in within if k not in have), key=lambda k: math.hypot(pos[k][0] - px, pos[k][1] - py))
        d["m_scavengeRadius"] = newR
        d["m_reachableLocations"] = [mkguid(k) for k in keep + add]
        report.append((len(old_list), len(keep) + len(add)))

    new = bytes(o.save_typetree(tt))
    old_start = o.byte_start - hdr.data_offset          # 데이터 영역 기준
    old_size = o.byte_size
    A = 16
    up = lambda n: (n + A - 1) // A * A
    # 대상 오브젝트 뒤에 오는 모든 오브젝트의 시작 위치를 같은 만큼 이동
    objs = sorted(env.objects, key=lambda x: x.byte_start)
    idx = [x.path_id for x in objs].index(o.path_id)
    abs_start = o.byte_start
    old_span = (objs[idx + 1].byte_start - abs_start) if idx + 1 < len(objs) else (len(raw) - abs_start)
    if old_span != up(old_size):
        sys.exit("예상과 다른 오브젝트 배치입니다.")
    new_span = up(len(new))
    delta = new_span - old_span
    out = bytearray(raw[:abs_start]) + new + b"\x00" * (new_span - len(new)) + raw[abs_start + old_span:]

    # 오브젝트 표 갱신 (path_id 8 / byte_start 8 / byte_size 4)
    for x in objs:
        e = ENTRY[x.path_id]
        pid, bs, sz = struct.unpack_from("<qqI", raw, e)
        if pid != x.path_id or bs != x.byte_start - hdr.data_offset or sz != x.byte_size:
            sys.exit("오브젝트 표 해석이 예상과 다릅니다. 중단합니다.")
        if x.byte_start > abs_start:
            struct.pack_into("<q", out, e + 8, bs + delta)
        elif x.path_id == o.path_id:
            struct.pack_into("<I", out, e + 16, len(new))
    struct.pack_into(">q", out, 24, len(out))              # 헤더(빅엔디안)의 file_size

    bak = path + ".bak"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        print("백업 생성:", bak)
    r_ = EndianBinaryReader(bytes(out))
    r_.flags = sf.flags
    bundle.files[name] = r_
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(bundle.save(packer="lz4"))
    try:
        os.replace(tmp, path)
    except PermissionError:
        sys.exit("파일을 교체하지 못했습니다. 게임/스팀이 실행 중이면 끄고 다시 시도하세요. 새 파일은 " + tmp + " 에 있습니다.")
    print("탐색 반경: %.1f -> %.1f (x%.2f)" % (BASE_RADIUS, newR, factor))
    print("은신처 %d곳, 갈 수 있는 장소 수(평균): %.1f -> %.1f" % (
        len(report), sum(a for a, _ in report) / len(report), sum(b for _, b in report) / len(report)))

if __name__ == "__main__":
    main()
