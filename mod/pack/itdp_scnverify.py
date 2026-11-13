#!/usr/bin/env python
"""verify_scenario_btn.py - independent verifier of a built ui_screens (martial-artist button). Reads only.
  python -I -X utf8 verify_scenario_btn.py --orig <source ui_screens> --new <built ui_screens> --info <built>.build.json [--unitypy]
Checks (every one must pass, exit code 0): bundle (other nodes byte-identical), scene object table (+61, only 3 replaced), every PPtr valid, clone independence (no clone->original, no original->clone except the expected parent
lists/call targets), clone == original subtree byte-for-byte after pid mapping except the 5 intended objects, the 3 onClick calls, marker (inactive, last child index 5 of 6), toggle reset call, label, Panels child list."""
import sys, os, struct, json, argparse
HERE = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import itdp_ufs as ufs, itdp_ser as S, itdp_tt as tt
SCENE = 'BuildPlayer-ScenarioSettings'
class Scene:
    def __init__(self, data):
        self.d = data; self.s = S.Ser(data); self.trees = [tt.build_tree(t) for t in self.s.types]; self.P = self.s.by_pid(); self._c = {}
    def b(self, pid): return self.s.object_bytes(self.P[pid])
    def leaves(self, pid):
        if pid not in self._c: self._c[pid] = tt.parse_object(self.s, self.P[pid], self.trees)
        return self._c[pid]
    def val(self, pid): return {p: v for p, o, t, v in self.leaves(pid)}
    def off(self, pid): return {p: (o, t) for p, o, t, v in self.leaves(pid)}
    def cls(self, pid): return self.s.types[self.s.objects[self.P[pid]][3]].class_id if pid in self.P else -1
    def pptrs(self, pid):
        v = self.val(pid); o = self.off(pid); out = []
        for p, (off, t) in o.items():
            if p.endswith('.m_PathID') and t == 'SInt64':
                fp = p[:-8] + 'm_FileID'
                if fp in v: out.append((p, off, v[p], v[fp]))
        return out
    def calls(self, pid, field):
        v = self.val(pid); n = v[field + '.m_PersistentCalls.m_Calls.Array.size']; r = []
        for i in range(n):
            k = '%s.m_PersistentCalls.m_Calls.Array[%d].' % (field, i)
            r.append(dict(target=v[k + 'm_Target.m_PathID'], tfile=v[k + 'm_Target.m_FileID'], type=v[k + 'm_TargetAssemblyTypeName'], method=v[k + 'm_MethodName'], mode=v[k + 'm_Mode'], i=v[k + 'm_Arguments.m_IntArgument'], s=v[k + 'm_Arguments.m_StringArgument'], b=v[k + 'm_Arguments.m_BoolArgument'], state=v[k + 'm_CallState']))
        return r
def children(sc, rt): v = sc.val(rt); return [v['m_Children.Array[%d].m_PathID' % i] for i in range(v['m_Children.Array.size'])]
def rt_of(sc, go):
    v = sc.val(go)
    for i in range(v['m_Component.Array.size']):
        p = v['m_Component.Array[%d].component.m_PathID' % i]
        if sc.cls(p) in (4, 224): return p
def subtree(sc, go):
    v = sc.val(go); acc = [go] + [v['m_Component.Array[%d].component.m_PathID' % i] for i in range(v['m_Component.Array.size'])]
    for ch in children(sc, rt_of(sc, go)): acc += subtree(sc, sc.val(ch)['m_GameObject.m_PathID'])
    return acc
def verify_scene(o, n, info):
    """o, n: Scene objects (source / built). returns [(name, ok, note)]"""
    R = []; ck = lambda name, ok, note='': R.append((name, bool(ok), note))
    newp = info['new_pids']; cm = {int(k): v for k, v in info['clone_map'].items()}; mgo, mrt = info['marker_go'], info['marker_rt']; menu, panels = info['menu_parent_rt'], info['panels_rt']; tog = info['toggle_mb']
    replaced = set(info['replaced'])
    ck('S1 object count +%d, source pids all still present' % len(newp), len(n.s.objects) == len(o.s.objects) + len(newp) and all(p in n.P for p in o.P) and set(newp) == set(n.P) - set(o.P))
    changed = {p for p in o.P if o.b(p) != n.b(p)}
    ck('S1b only the 3 replaced objects differ from the source scene (changed: %s)' % sorted(changed), changed == replaced)
    # PPtr validity
    bad = []
    for p in list(newp) + sorted(replaced):
        for path, off, val, fid in n.pptrs(p):
            if fid == 0 and val != 0 and val not in n.P: bad.append((p, path, val))
    ck('S2 every PPtr (FileID 0) of the new/replaced objects points at an existing object', not bad, str(bad[:3]))
    clsbad = []
    for p in newp:
        v = n.val(p)
        if 'm_GameObject.m_PathID' in v and v['m_GameObject.m_PathID'] and n.cls(v['m_GameObject.m_PathID']) != 1: clsbad.append((p, 'm_GameObject'))
        if 'm_Father.m_PathID' in v and v['m_Father.m_PathID'] and n.cls(v['m_Father.m_PathID']) not in (4, 224): clsbad.append((p, 'm_Father'))
    ck('S2b m_GameObject points at a GameObject, m_Father at a transform', not clsbad, str(clsbad[:3]))
    # independence
    orig_sub = set(subtree(o, 132)); allowed_out = {670, info['panels_rt']}
    c2o = [(p, path, val) for p in newp for path, off, val, fid in n.pptrs(p) if fid == 0 and val in orig_sub]
    ck('S3 no clone object references the original ConfirmButton subtree', not c2o, str(c2o[:3]))
    out = {(p, val) for p in newp for path, off, val, fid in n.pptrs(p) if fid == 0 and val != 0 and val not in set(newp)}
    ck('S3b the only references from clones to the original scene are the screen (670), the clone parent (Panels RT) and the marker parent (ScenarioMenuParent RT)', {v for _, v in out} <= allowed_out | {info['menu_parent_rt']} and {v for _, v in out} >= {670}, str(sorted(out)))
    ck('S3c every untouched original object is byte-identical to the source (S1b), so none can reference a clone/marker object (their pids did not exist)', changed == replaced)
    exp_refs = {(panels, info['clone_root_rt']), (menu, mrt), (tog, mgo)}
    got = {(p, val) for p in replaced for path, off, val, fid in n.pptrs(p) if fid == 0 and val in set(newp)}
    ck('S3e replaced objects point at new objects exactly: %s' % sorted(exp_refs), got == exp_refs, str(sorted(got)))
    # byte-for-byte clone check
    allowed_diff = {132: 'name', 648: 'pos', 1091: 'calls', 3: 'warning-hidden'}
    txt_go = [p for p in subtree(o, 132) if o.cls(p) == 1 and o.val(p)['m_Name'] == 'Text'][0]; tv = o.val(txt_go); comps = [tv['m_Component.Array[%d].component.m_PathID' % i] for i in range(tv['m_Component.Array.size'])]
    loc = [c for c in comps if 'm_key' in o.val(c)][0]; stx = [c for c in comps if 'm_text' in o.val(c) and 'm_fontData.m_fontSize' in o.val(c)][0]; allowed_diff[loc] = 'key'; allowed_diff[stx] = 'text'
    diffs = []
    for p in subtree(o, 132):
        b = bytearray(o.b(p))
        for path, off, val, fid in o.pptrs(p):
            if fid == 0 and val in cm: struct.pack_into('<q', b, off, cm[val])
        nb = n.b(cm[p])
        if bytes(b) != nb: diffs.append(p)
    ck('S4 clone == original subtree byte for byte (after pid mapping) except exactly the intended objects %s' % sorted(allowed_diff), set(diffs) == set(allowed_diff), 'differs: %s' % sorted(diffs))
    # field-level for the intended ones
    nv = {p: n.val(cm[p]) for p in allowed_diff}; ov = {p: o.val(p) for p in allowed_diff}
    ck('S4b clone root GO renamed MartialStartButton (original keeps ConfirmButton)', nv[132]['m_Name'] == 'MartialStartButton' and o.val(132)['m_Name'] == 'ConfirmButton' and n.val(132)['m_Name'] == 'ConfirmButton')
    ck('S4c clone root RectTransform at (%s, %s), original unchanged' % (info['pos'][0], info['pos'][1]), abs(nv[648]['m_AnchoredPosition.x'] - info['pos'][0]) < 1e-6 and abs(nv[648]['m_AnchoredPosition.y'] - info['pos'][1]) < 1e-6 and n.b(648) == o.b(648) and nv[648]['m_Father.m_PathID'] == panels)
    ck('S4d clone Warning GO is inactive (hidden, so it cannot overlap the original warning); the original Warning GO is untouched', nv[3]['m_IsActive'] == 0 and n.b(3) == o.b(3), 'clone %s orig_changed %s' % (nv[3].get('m_IsActive'), n.b(3) != o.b(3)))
    # calls
    cc = n.calls(cm[1091], 'm_OnClick'); audio = [p for p in subtree(o, 132) if o.cls(p) == 114 and any(k.startswith('m_clickFmodEvent') for k in o.val(p))][0]
    ok = len(cc) == 3
    if ok:
        a, b_, c = cc
        ok = (a['target'] == mgo and a['tfile'] == 0 and a['type'] == 'UnityEngine.GameObject, UnityEngine' and a['method'] == 'SetActive' and a['mode'] == 6 and a['b'] == 1 and a['state'] == 2 and
              b_['target'] == cm[audio] and b_['method'] == 'PlayClickSound' and b_['mode'] == 1 and b_['state'] == 2 and b_['type'].endswith('UserInterfaceAudio, DRS.Presentation') and
              c['target'] == 670 and c['tfile'] == 0 and c['method'] == 'StartGameWithParameters' and c['mode'] == 1 and c['state'] == 2 and c['type'] == 'DRS.Presentation.UI.Screens.Difficulty.ScenarioMode.ScenarioSettingsScreen, DRS.Presentation')
    ck('S5 clone onClick = [SetActive(marker, true) Mode 6][PlayClickSound(clone audio) Mode 1][StartGameWithParameters(screen 670) Mode 1], CallState 2', ok, str(cc))
    oc = o.calls(1091, 'm_OnClick'); nc = n.calls(1091, 'm_OnClick')
    ck('S5b original ConfirmButton onClick untouched (2 calls: original audio, screen)', oc == nc and len(oc) == 2 and n.b(1091) == o.b(1091))
    sel = n.calls(cm[1091], 'm_onSelect'); ck('S5c clone m_onSelect hover sound targets the clone audio', len(sel) == 1 and sel[0]['target'] == cm[audio] and sel[0]['method'] == 'PlayHoverSound')
    # marker
    mg = n.val(mgo); mr = n.val(mrt); mv = n.val(n.s.objects[n.P[menu]][0]) if False else n.val(menu); ov_menu = children(o, menu); nk = children(n, menu)
    ck('S6 marker GO "MartialMarker" inactive, one component (its RectTransform), same layer as ScenarioMenuParent', mg['m_Name'] == 'MartialMarker' and mg['m_IsActive'] == 0 and mg['m_Component.Array.size'] == 1 and mg['m_Component.Array[0].component.m_PathID'] == mrt and mg['m_Layer'] == o.val(2)['m_Layer'])
    ck('S6b marker RectTransform: father = ScenarioMenuParent RT, no children, GameObject = marker', mr['m_Father.m_PathID'] == menu and mr['m_Children.Array.size'] == 0 and mr['m_GameObject.m_PathID'] == mgo and n.cls(mrt) == 224)
    ck('S6c ScenarioMenuParent children = old 5 + marker as LAST (index 5 of 6)', nk == ov_menu + [mrt] and len(nk) == 6 and nk[5] == mrt)
    ck('S6d Panels children = old + clone root RT at the end; ConfirmButton still in place', children(n, panels) == children(o, panels) + [info['clone_root_rt']] and 648 in children(n, panels))
    tc = n.calls(tog, 'm_onShow'); oc2 = o.calls(tog, 'm_onShow')
    ck('S7 StartingParameters toggle m_onShow = [SelectFirstSurvivor (unchanged)] + [SetActive(marker, false) Mode 6]', len(tc) == 2 and tc[0] == oc2[0] and tc[1]['target'] == mgo and tc[1]['method'] == 'SetActive' and tc[1]['mode'] == 6 and tc[1]['b'] == 0 and tc[1]['state'] == 2 and tc[1]['type'] == 'UnityEngine.GameObject, UnityEngine')
    ck('S8 label: clone LocaliseSmartText.m_key = %s, original key unchanged' % info['label_key'], nv[loc]['m_key'] == info['label_key'] and o.val(loc)['m_key'] == 'LABEL_SCENARIO_MODE_START_SCENARIO' and n.val(loc)['m_key'] == 'LABEL_SCENARIO_MODE_START_SCENARIO')
    return R
def verify_bundles(src_path, new_path, info, unitypy=False):
    R = []; ck = lambda name, ok, note='': R.append((name, bool(ok), note))
    sb = ufs.Bundle(src_path); nb = ufs.Bundle(new_path)
    same = all(sb.node_data(nm) == nb.node_data(nm) for _, _, _, nm in sb.nodes if nm != SCENE); ck('B1 every node except %s is byte-identical to the source bundle (%d nodes)' % (SCENE, len(sb.nodes) - 1), same and [x[3] for x in sb.nodes] == [x[3] for x in nb.nodes])
    ck('B2 the scene node differs', sb.node_data(SCENE) != nb.node_data(SCENE))
    R += verify_scene(Scene(sb.node_data(SCENE)), Scene(nb.node_data(SCENE)), info)
    if unitypy:
        import UnityPy
        from UnityPy.helpers.TypeTreeNode import TypeTreeNode
        if not getattr(TypeTreeNode, '_itd_patched', False):
            _o = TypeTreeNode.parse_blob.__func__
            def _pb(cls, reader, version): reader.read(28); return _o(cls, reader, version)
            TypeTreeNode.parse_blob = classmethod(_pb); TypeTreeNode._itd_patched = True
        env = UnityPy.load(new_path); objs = {x.path_id: x for x in env.objects if x.assets_file.name == SCENE}; err = []
        for p in info['new_pids'] + info['replaced']:
            try: t = objs[p].read_typetree()
            except Exception as e: err.append((p, str(e)[:50]))
        go = objs[info['marker_go']].read_typetree(); cr = objs[info['clone_root_go']].read_typetree()
        ck('B3 UnityPy loads the new scene and reads the type tree of all %d new/replaced objects; marker GO %r, clone root %r' % (len(info['new_pids']) + 3, go['m_Name'], cr['m_Name']), not err and go['m_Name'] == 'MartialMarker' and cr['m_Name'] == 'MartialStartButton', str(err[:2]))
    return R
def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('--orig', required=True); ap.add_argument('--new', required=True); ap.add_argument('--info', required=True); ap.add_argument('--unitypy', action='store_true')
    a = ap.parse_args(argv); info = json.load(open(a.info)); R = verify_bundles(a.orig, a.new, info, a.unitypy)
    for name, ok, note in R: print(('PASS ' if ok else 'FAIL ') + name + ('' if ok or not note else '  -> ' + note))
    nf = sum(1 for r in R if not r[1]); print('%d checks, %d failed' % (len(R), nf)); return 1 if nf else 0
if __name__ == '__main__': sys.exit(main())
