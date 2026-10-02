"""Into the Dead: Our Darkest Days - 지도에서 장소(건물)가 놓이는 위치를 무작위로 섞기 (실험적).
사용: python shuffle_map.py <AssetBundles 폴더 경로> [시드 | keep]
  keep : 위치는 섞지 않고, 현재 좌표 기준으로 목록 재계산만 한다 (이미 섞은 파일에 적용 가능)
data_levels 의 MapData 에서 장소들의 좌표(m_position)를 서로 바꾼다. 건물 이름/장면/NPC 는 그대로 함께 움직인다.
- 상인, HOD 전용 장소, 은신처는 제자리에 둔다. (시작 지역 고정은 풀었음: 시작 은신처 주변 장소도 섞인다)
- 위치가 바뀌므로 각 은신처의 '갈 수 있는 장소' 목록을 새 좌표/반경 기준으로 다시 만든다.
- 망원경 목록(m_vantagePointObservableLocations)을 새 좌표 기준 '가까운 장소'로 다시 만든다 (개수 유지, 은신처가 대상에 들어가는 구조 유지,
  원래 보이던 장소가 어디에서도 안 보이게 되면 가장 가까운 망원경 장소에 추가). 은신처의 시작 해금은 원본처럼 그 은신처 망원경 목록과 같게 둔다.
처음 실행할 때 data_levels.shufflebak 으로 백업한다. 게임을 끈 상태에서 실행할 것.
복원: data_levels.shufflebak 을 data_levels 로 덮어쓰면 된다.
"""
import math, os, random, shutil, struct, sys
import UnityPy.helpers.TypeTreeNode as T

_orig = T.TypeTreeNode.parse_blob.__func__
def _pb(cls, reader, version):
    reader.Position = reader.Position + 28
    return _orig(cls, reader, version)
T.TypeTreeNode.parse_blob = classmethod(_pb)

import UnityPy
from UnityPy.files import ObjectReader as _ORcls
from UnityPy.streams import EndianBinaryReader

BASE_RADIUS = 987.5
MIN_REACH = 8
ENTRY = {}
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
    keep_mode = len(sys.argv) > 2 and sys.argv[2].lower() == "keep"
    seed = 0 if keep_mode else (int(sys.argv[2]) if len(sys.argv) > 2 else random.SystemRandom().randrange(1 << 30))
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
    names = {}
    target = None
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            tt = o.read_typetree()
        except Exception:
            continue
        c = scr.get(tt["m_Script"]["m_PathID"])
        if c in ("LocationData", "ShelterLocationData"):
            names[gid(tt["m_guid"])] = tt["m_Name"]
        elif c == "MapData" and target is None:
            target = (o, tt)
    if target is None:
        sys.exit("MapData 를 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있습니다).")
    o, tt = target
    refs = tt["references"]["RefIds"]
    refd = {r["rid"]: r for r in refs}

    def cond_names(d):
        out = []
        for c in d["m_unavailabilityConditions"]:
            out.append(refd[c["rid"]]["data"]["m_conditionObject"]["m_PathID"])
        return out

    locs, shelters = {}, {}
    for r in refs:
        d = r["data"]
        if "m_locationReference" not in d or "m_position" not in d:
            continue
        g = gid(d["m_locationReference"])
        (shelters if r["type"]["class"] == "MapShelterLocationData" else locs)[g] = r
    allpos = {g: (r["data"]["m_position"]["x"], r["data"]["m_position"]["y"]) for g, r in {**locs, **shelters}.items()}

    # 장소 이름으로 상인/HOD/스토리 전용 판별 (조건 에셋 이름은 데이터 번들 소속이라 장소 이름과 조건 개수로 판단)
    def special(g):
        n = names.get(g, "")
        return ("Trader" in n) or n.startswith("Midtown_FieldHospital_01") or n.startswith("Midtown_Stadium_01") or n.startswith("Midtown_Airfield") 
    fixed = set(g for g in locs if special(g))
    movable = [g for g in locs if g not in fixed]
    if len(movable) < 6:
        sys.exit("옮길 수 있는 장소가 너무 적습니다.")

    # 무작위 순열 (모든 장소가 다른 자리로 가는 derangement) + 은신처별 최소 접근 가능 수 검사
    rnd = random.Random(seed)
    slots = [allpos[g] for g in movable]
    if keep_mode:
        movable = []
        newpos = dict(allpos)
    else:
        for attempt in range(500):
            perm = slots[:]
            rnd.shuffle(perm)
            if any(a == b for a, b in zip(slots, perm)):
                continue
            newpos = dict(allpos)
            for g, p in zip(movable, perm):
                newpos[g] = p
            ok = True
            for sg, r in shelters.items():
                R = r["data"]["m_scavengeRadius"]
                px, py = newpos[sg]
                n = sum(1 for k in newpos if math.hypot(newpos[k][0] - px, newpos[k][1] - py) <= R)
                if n < MIN_REACH:
                    ok = False
                    break
            if ok:
                break
        else:
            sys.exit("조건을 만족하는 배치를 찾지 못했습니다. 다른 시드로 다시 시도하세요.")

    for g in movable:
        locs[g]["data"]["m_position"]["x"], locs[g]["data"]["m_position"]["y"] = newpos[g]
    # 망원경 목록 재구성: 각 망원경 장소가 보여주는 개수는 유지하고 새 좌표 기준 가까운 장소로 채운다.
    # 원래 어딘가에서 보이던 장소가 어떤 목록에도 없게 되면 가장 가까운 망원경 장소에 추가해 발견 가능성을 유지한다.
    vps = {g: r["data"]["m_vantagePointObservableLocations"] for g, r in {**locs, **shelters}.items()}
    old_lists = {g: [gid(x) for x in v] for g, v in vps.items() if v}
    covered_before = {k for v in old_lists.values() for k in v}
    dpos = lambda a, b: math.hypot(newpos[a][0] - newpos[b][0], newpos[a][1] - newpos[b][1])
    new_lists = {}
    for g, v in old_lists.items():
        cand = sorted((k for k in newpos if k != g), key=lambda k: dpos(g, k))
        new_lists[g] = cand[:len(v)]
    covered_after = {k for v in new_lists.values() for k in v}
    for k in sorted(covered_before - covered_after):
        pts = sorted((g for g in new_lists if g != k), key=lambda g: dpos(g, k))
        new_lists[pts[0]].append(k)
    for g, v in new_lists.items():
        vps[g][:] = [mkguid(k) for k in v]
    vp_new = new_lists
    # 은신처별 갈 수 있는 장소/시작 해금 목록 재계산
    cnts = []
    unl = []
    for sg, r in shelters.items():
        d = r["data"]
        R = d["m_scavengeRadius"]
        px, py = newpos[sg]
        dist = lambda k: math.hypot(newpos[k][0] - px, newpos[k][1] - py)
        old = [gid(x) for x in d["m_reachableLocations"]]
        within = [k for k in newpos if dist(k) <= R]
        keep = [k for k in old if k in set(within)]
        add = sorted((k for k in within if k not in set(keep)), key=dist)
        d["m_reachableLocations"] = [mkguid(k) for k in keep + add]
        # 원본은 모든 은신처에서 '시작 해금 = 그 은신처의 망원경 목록'이다. 같은 관계를 유지한다.
        ini_new = vp_new.get(sg, [])
        d["m_initialUnlockedLocations"] = [mkguid(k) for k in ini_new] if ini_new else d["m_initialUnlockedLocations"]
        unl.append(len(d["m_initialUnlockedLocations"]))
        cnts.append(len(keep) + len(add))

    new = bytes(o.save_typetree(tt))
    old_size = o.byte_size
    A = 16
    up = lambda n: (n + A - 1) // A * A
    objs = sorted(env.objects, key=lambda x: x.byte_start)
    idx = [x.path_id for x in objs].index(o.path_id)
    abs_start = o.byte_start
    old_span = (objs[idx + 1].byte_start - abs_start) if idx + 1 < len(objs) else (len(raw) - abs_start)
    if old_span != up(old_size):
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

    bak = path + ".shufflebak"
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
    print("시드: %s / 위치를 섞은 장소: %d곳 / 고정: %d곳 / 은신처 %d곳의 갈 수 있는 장소 수: 최소 %d, 평균 %.1f / 시작 해금(=은신처 망원경 목록) 평균 %.1f곳" % (
        "keep(섞지 않음)" if keep_mode else seed, len(movable), len(fixed), len(shelters), min(cnts), sum(cnts) / len(cnts), sum(unl) / len(unl)))
    moved = [g for g in movable if allpos[g] != newpos[g]]
    for g in moved[:8]:
        print("  %s : (%.0f, %.0f) -> (%.0f, %.0f)" % (names.get(g, "?")[:44], *allpos[g], *newpos[g]))
    if len(moved) > 8:
        print("  ... 외 %d곳" % (len(moved) - 8))

if __name__ == "__main__":
    main()
