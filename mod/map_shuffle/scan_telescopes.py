"""Into the Dead: Our Darkest Days - 어느 장소에 '진짜 망원경'이 있는지 장면 번들에서 확인한다 (읽기 전용, 한 번만 실행).
사용: python scan_telescopes.py <AssetBundles 폴더 경로>
각 장소의 장면 번들(multi_scene.*)을 열어 'VantagePoint' 상호작용 오브젝트가 실제로 있는지 검사하고, 결과를 telescopes.json 으로 저장한다.
shuffle_map.py 는 이 파일이 있으면 진짜 망원경이 있는 장소만 발견 연쇄에 사용한다 (지도 데이터에는 있다고 적혀 있지만 실제론 없는 장소 대응).
번들이 크기 때문에 몇 분 걸릴 수 있다. 이미 검사한 번들은 건너뛴다(캐시).
"""
import json, os, sys
import UnityPy.helpers.TypeTreeNode as T

_orig = T.TypeTreeNode.parse_blob.__func__
def _pb(cls, reader, version):
    reader.Position = reader.Position + 28
    return _orig(cls, reader, version)
T.TypeTreeNode.parse_blob = classmethod(_pb)

import UnityPy

def gid(g):
    return bytes(g["m_guid"]["bytes[%d]" % i] for i in range(16)).hex()

def active_in_hierarchy(go):
    """게임오브젝트 자신과 모든 부모가 활성인지"""
    seen = 0
    while go is not None and seen < 64:
        if not go.m_IsActive:
            return False
        tr = None
        for c in go.m_Components:
            try:
                ob = c.deref()
                if ob.type.name in ("Transform", "RectTransform"):
                    tr = ob.read()
                    break
            except Exception:
                pass
        if tr is None or not tr.m_Father.path_id:
            return True
        try:
            go = tr.m_Father.deref().read().m_GameObject.deref().read()
        except Exception:
            return True
        seen += 1
    return True

def has_telescope(bundle_path):
    """번들 안에 'VantagePoint' 게임오브젝트가 InteractableObject 를 갖고, 계층 전체가 활성이면 True.
    (Essentials 프리팹에는 모든 장소에 비활성 VantagePoint 가 기본으로 들어 있어 이름만으로는 알 수 없다)"""
    with open(bundle_path, "rb") as fh:
        env = UnityPy.load(fh.read())
    for o in env.objects:
        if o.type.name != "GameObject":
            continue
        try:
            go = o.read()
        except Exception:
            continue
        if "vantagepoint" not in (go.m_Name or "").lower():
            continue
        has_inter = False
        for c in go.m_Components:
            try:
                ob = c.deref()
                if ob.type.name == "MonoBehaviour" and ob.read().m_Script.deref().read().m_ClassName == "InteractableObject":
                    has_inter = True
                    break
            except Exception:
                pass
        if has_inter and active_in_hierarchy(go):
            return True
    return False

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    folder = sys.argv[1]
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telescopes.json")
    lv_path = os.path.join(folder, "data_levels.shufflebak")
    if not os.path.exists(lv_path):
        lv_path = os.path.join(folder, "data_levels")
    with open(lv_path, "rb") as fh:
        env = UnityPy.load(fh.read())
    scr = {o.path_id: o.read().m_ClassName for o in env.objects if o.type.name == "MonoScript"}
    objs = {}
    deps = {}
    locdata = {}
    mdata = None
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            tt = o.read_typetree()
        except Exception:
            continue
        c = scr.get(tt["m_Script"]["m_PathID"])
        if c == "MultiScene":
            objs[o.path_id] = tt["m_bundleName"]
            deps[o.path_id] = [d["m_PathID"] for d in tt.get("m_dependencies", [])]
        elif c in ("LocationData", "ShelterLocationData"):
            locdata[gid(tt["m_guid"])] = tt
        elif c == "MapData":
            mdata = tt
    if mdata is None:
        sys.exit("MapData 를 찾지 못했습니다.")
    hosts = []
    for r in mdata["references"]["RefIds"]:
        d = r["data"]
        if r["type"]["class"] == "MapLocationData" and d["m_vantagePointObservableLocations"]:
            hosts.append(gid(d["m_locationReference"]))
    cache = {}
    if os.path.exists(out_path):
        try:
            cache = json.load(open(out_path, encoding="utf-8")).get("bundles", {})
        except Exception:
            cache = {}
    result, missing = {}, []
    for i, g in enumerate(hosts, 1):
        tt = locdata.get(g)
        if tt is None:
            continue
        name = tt["m_Name"]
        scenes = []
        roots = []
        ms = tt.get("m_multiScene")
        if ms and ms["m_PathID"] in objs:
            roots.append(ms["m_PathID"])
        for v in tt.get("m_cycleOverrideMultiScene", {}).get("m_values", []):
            if v["m_PathID"] in objs:
                roots.append(v["m_PathID"])
        seen_ms, stack = set(), list(roots)
        while stack:                       # day/night 장면과 그 의존성(common 등)을 모두 따라간다
            p = stack.pop()
            if p in seen_ms or p not in objs:
                continue
            seen_ms.add(p)
            scenes.append(objs[p])
            stack.extend(deps.get(p, []))
        found, checked = False, 0
        for b in dict.fromkeys(scenes):
            p = os.path.join(folder, b)
            if not os.path.exists(p):
                missing.append(b)
                continue
            if b not in cache:
                print("[%d/%d] 검사 중: %s" % (i, len(hosts), b[:70]))
                cache[b] = has_telescope(p)
            checked += 1
            found = found or cache[b]
        result[name] = {"telescope": bool(found), "checked_bundles": checked}
    json.dump({"locations": result, "bundles": cache}, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    yes = [n for n, v in result.items() if v["telescope"]]
    no = [n for n, v in result.items() if not v["telescope"]]
    print("\n진짜 망원경이 있는 장소 %d곳 / 지도 데이터엔 있지만 장면에 없는 장소 %d곳" % (len(yes), len(no)))
    for n in no:
        print("  망원경 없음:", n, "" if result[n]["checked_bundles"] else "(검사한 번들 없음 - 번들 파일 부재)")
    if missing:
        print("\n찾지 못한 번들 %d개 (파일 이름이 다르거나 없음)" % len(set(missing)))
    print("\n저장:", out_path)

if __name__ == "__main__":
    main()
