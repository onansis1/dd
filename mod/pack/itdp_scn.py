#!/usr/bin/env python
"""itd_scenario_btn.py - COPY-ONLY tool: add the "martial artist start" button to BuildPlayer-ScenarioSettings inside a ui_screens bundle copy.
  python -I -X utf8 itd_scenario_btn.py plan  --src <ui_screens copy> [--key LABEL_STATE_AND_TYPE] [--x -375] [--y 160]
  python -I -X utf8 itd_scenario_btn.py build --src <ui_screens copy> --out <dir> [...]
What it does (all inside the scene file, generalising the MapScreen tree builder's primitives: Obj, call_bytes, make_go, ser_edit.rebuild, ufs.write_bundle):
  1. clones the whole subtree of ConfirmButton (GO 132, 59 objects) with EVERY PPtr that points into the subtree re-targeted to the clone (generic leaf scan of the type trees);
  2. puts the clone root as the last child of Panels (same parent as ConfirmButton), anchored position (x, y) (default -375, 160 = left of the original);
  3. new SelectableActionButton.m_OnClick = [GameObject.SetActive(marker, true) (Mode 6), UserInterfaceAudio.PlayClickSound (clone's own), ScenarioSettingsScreen.StartGameWithParameters (id 670, unchanged)];
  4. marker = new GameObject "MartialMarker" (inactive, RectTransform only) = LAST child of ScenarioMenuParent (child count 5 -> 6, marker index 5);
  5. StartingParameters FlowStateActiveToggle.m_onShow += GameObject.SetActive(marker, false);
  6. label: clone's LocaliseSmartText.m_key = --key, SmartText.m_text = fallback text.
Never writes into the game folder (refused); the source is only read."""
import sys, os, json, struct, hashlib, argparse
HERE = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import itdp_ufs as ufs, itdp_ser as S, itdp_tt as tt, itdp_edit as ser_edit
from itdp_build import Obj, call_bytes, make_go, in_game_folder

SCENE = 'BuildPlayer-ScenarioSettings'
G = dict(confirm=132, menu_parent=2, panels=1, starting=75, screen_mb=670, button_mb=1091, toggle_mb=834)
NAMES = {132: 'ConfirmButton', 2: 'ScenarioMenuParent', 1: 'Panels', 75: 'StartingParameters', 139: 'Handle'}
CLS = {'GO': 1, 'T': 4, 'RT': 224}
NEW_NAME = 'MartialStartButton'; MARKER_NAME = 'MartialMarker'; MARKER_CHILDREN = 6

def class_of(sr, pid): return sr.types[sr.objects[sr.by_pid()[pid]][3]].class_id
def rt_of_go(sr, trees, go_pid):
    g = Obj(sr, trees, go_pid); n = g.val['m_Component.Array.size']
    for i in range(n):
        p = g.val['m_Component.Array[%d].component.m_PathID' % i]
        if class_of(sr, p) in (CLS['T'], CLS['RT']): return p
    raise KeyError(go_pid)
def subtree(sr, trees, go_pid):
    """all object pids of a GameObject subtree: GO, its components, children (via RectTransform m_Children)"""
    acc = []; g = Obj(sr, trees, go_pid); acc.append(go_pid)
    for i in range(g.val['m_Component.Array.size']): acc.append(g.val['m_Component.Array[%d].component.m_PathID' % i])
    rt = Obj(sr, trees, rt_of_go(sr, trees, go_pid))
    for i in range(rt.val['m_Children.Array.size']):
        ch = Obj(sr, trees, rt.val['m_Children.Array[%d].m_PathID' % i]); acc += subtree(sr, trees, ch.val['m_GameObject.m_PathID'])
    return acc
def pptr_leaves(o):
    """[(path_of_m_PathID, offset, value, fileid)] for every PPtr of the object"""
    out = []
    for p, (off, t) in o.off.items():
        if p.endswith('.m_PathID') and t == 'SInt64':
            fp = p[:-len('m_PathID')] + 'm_FileID'
            if fp in o.val: out.append((p, off, o.val[p], o.val[fp]))
    return out
def calls_range(o, field):
    """(array size offset, end offset) of <field>.m_PersistentCalls.m_Calls (end = offset of the next leaf after the array = start of the next field / object end)"""
    key = field + '.m_PersistentCalls.m_Calls.Array.size'; a0 = o.off[key][0]; pre = field + '.m_PersistentCalls.m_Calls.Array'
    offs = sorted(set(oo for p, (oo, t) in o.off.items() if oo > a0 and not p.startswith(pre)))
    return a0, (offs[0] if offs else len(o.b))
def children_append(o, pid_new):
    n = o.val['m_Children.Array.size']; a0 = o.off['m_Children.Array.size'][0]; ins = a0 + 4 + 12 * n
    assert ins == o.off['m_Father.m_FileID'][0], 'unexpected RectTransform layout'
    o.b[ins:ins] = struct.pack('<iq', 0, pid_new); struct.pack_into('<i', o.b, a0, n + 1)

def plan_build(src_path, key='LABEL_STATE_AND_TYPE', fallback_text='Start with Martial Artist', x=-375.0, y=160.0):
    sb = ufs.Bundle(src_path); orig = sb.node_data(SCENE); sr = S.Ser(orig); trees = [tt.build_tree(t) for t in sr.types]; P = sr.by_pid()
    for pid, nm in NAMES.items(): assert Obj(sr, trees, pid).val['m_Name'] == nm, 'scene differs: GO %d is not %s' % (pid, nm)
    assert not any(class_of(sr, p) == CLS['GO'] and Obj(sr, trees, p).val['m_Name'] in (NEW_NAME, MARKER_NAME) for p in P), 'scene already contains the martial button (refusing to build twice)'
    sub = subtree(sr, trees, G['confirm']); assert len(sub) == 59 and len(set(sub)) == 59, len(sub)
    nxt = max(P) + 1; newp = {}
    for p in sub: newp[p] = nxt; nxt += 1
    marker_go, marker_rt = nxt, nxt + 1
    menu_rt = rt_of_go(sr, trees, G['menu_parent']); panels_rt = rt_of_go(sr, trees, G['panels']); conf_rt = rt_of_go(sr, trees, G['confirm'])
    assert Obj(sr, trees, panels_rt).val['m_Children.Array.size'] > 0 and Obj(sr, trees, conf_rt).val['m_Father.m_PathID'] == panels_rt, 'ConfirmButton is not a child of Panels'
    mcount = Obj(sr, trees, menu_rt).val['m_Children.Array.size']; assert mcount == MARKER_CHILDREN - 1, 'ScenarioMenuParent has %d children (expected 5)' % mcount
    # ---- 1. clone with PPtr retargeting
    append = []; outward = set()
    for p in sub:
        o = Obj(sr, trees, p)
        for path, off, val, fid in pptr_leaves(o):
            if fid == 0 and val in newp: struct.pack_into('<q', o.b, off, newp[val])
            elif fid == 0 and val != 0 and val not in newp: outward.add((p, path, val))
        append.append((newp[p], o.tid, o))
    # ---- 2. edits of the clone
    objs = {newp[p]: o for p, _, o in [(p_, 0, a[2]) for p_, a in zip(sub, append)]}
    def clone_of(orig_pid): return objs[newp[orig_pid]]
    go_root = clone_of(G['confirm']); go_root.set_str('m_Name', NEW_NAME); go_root.val['m_Name'] = NEW_NAME
    rt_root = clone_of(conf_rt); rt_root.set('m_AnchoredPosition.x', float(x)); rt_root.set('m_AnchoredPosition.y', float(y))
    assert Obj(sr, trees, 3).val['m_Name'] == 'Warning' and 3 in sub, 'GO 3 is not the Warning child of ConfirmButton'
    clone_of(3).set('m_IsActive', 0)      # 복제본의 경고 문구('계속하려면 생존자를 1명 이상 선택해야 합니다')가 원본 경고와 겹쳐 보이므로 복제본 쪽은 숨긴다
    btn = clone_of(G['button_mb']); a0, end = calls_range(btn, 'm_OnClick'); assert btn.val['m_OnClick.m_PersistentCalls.m_Calls.Array.size'] == 2
    assert btn.val['m_OnClick.m_PersistentCalls.m_Calls.Array[0].m_MethodName'] == 'PlayClickSound' and btn.val['m_OnClick.m_PersistentCalls.m_Calls.Array[1].m_MethodName'] == 'StartGameWithParameters'
    assert btn.val['m_OnClick.m_PersistentCalls.m_Calls.Array[1].m_Target.m_PathID'] == G['screen_mb'], 'StartGame target must stay the screen'
    existing = bytes(btn.b[a0 + 4:end]); btn.b[a0:end] = struct.pack('<i', 3) + call_bytes(marker_go, 'SetActive', True) + existing
    # text label: the clone of Text (SmartText + LocaliseSmartText)
    txt_go = None
    for p in sub:
        o = Obj(sr, trees, p)
        if class_of(sr, p) == CLS['GO'] and o.val['m_Name'] == 'Text': txt_go = p
    assert txt_go is not None
    tg = Obj(sr, trees, txt_go); loc_c = st_c = None
    for i in range(tg.val['m_Component.Array.size']):
        cp = tg.val['m_Component.Array[%d].component.m_PathID' % i]; co = Obj(sr, trees, cp)
        if 'm_key' in co.off: loc_c = cp
        if 'm_text' in co.off and 'm_fontData.m_fontSize' in co.off: st_c = cp
    assert loc_c and st_c; clone_of(loc_c).set_str('m_key', key); clone_of(st_c).set_str('m_text', fallback_text)
    # ---- 3. marker
    layer = Obj(sr, trees, G['menu_parent']).val['m_Layer']
    tmpl = Obj(sr, trees, rt_of_go(sr, trees, 139)); assert tmpl.val['m_Children.Array.size'] == 0 and tmpl.tid == Obj(sr, trees, menu_rt).tid
    mrt = Obj(sr, trees, rt_of_go(sr, trees, 139)); mrt.pid = marker_rt
    mrt.set('m_GameObject.m_PathID', marker_go) if False else None
    struct.pack_into('<q', mrt.b, mrt.off['m_GameObject.m_PathID'][0], marker_go); struct.pack_into('<q', mrt.b, mrt.off['m_Father.m_PathID'][0], menu_rt); struct.pack_into('<i', mrt.b, mrt.off['m_Father.m_FileID'][0], 0)
    gtid = sr.objects[P[G['menu_parent']]][3]
    mgo = make_go([marker_rt], layer, MARKER_NAME, False); tt.parse_bytes(trees[gtid], mgo)   # layout check against the real type tree
    # ---- 4. parents / toggle
    menu = Obj(sr, trees, menu_rt); children_append(menu, marker_rt)
    panels = Obj(sr, trees, panels_rt); children_append(panels, newp[conf_rt])
    tog = Obj(sr, trees, G['toggle_mb']); assert tog.val['m_onShow.m_PersistentCalls.m_Calls.Array.size'] == 1 and tog.val['m_onShow.m_PersistentCalls.m_Calls.Array[0].m_MethodName'] == 'SelectFirstSurvivor'
    a0, end = calls_range(tog, 'm_onShow'); tog.b[a0:end] = struct.pack('<i', 2) + bytes(tog.b[a0 + 4:end]) + call_bytes(marker_go, 'SetActive', False)
    # ---- 5. rebuild
    app = [(newp[p], a[1], bytes(a[2].b)) for p, a in zip(sub, append)] + [(marker_go, gtid, mgo), (marker_rt, mrt.tid, bytes(mrt.b))]
    new_ser = ser_edit.rebuild(orig, replace={menu_rt: bytes(menu.b), panels_rt: bytes(panels.b), G['toggle_mb']: bytes(tog.b)}, append=app)
    info = {'scene': SCENE, 'objects_before': len(sr.objects), 'objects_after': len(sr.objects) + len(app), 'new_pids': [a[0] for a in app], 'clone_map': {str(k): v for k, v in newp.items()},
            'clone_root_go': newp[G['confirm']], 'clone_root_rt': newp[conf_rt], 'clone_button_mb': newp[G['button_mb']], 'marker_go': marker_go, 'marker_rt': marker_rt, 'menu_parent_rt': menu_rt, 'panels_rt': panels_rt,
            'toggle_mb': G['toggle_mb'], 'screen_mb': G['screen_mb'], 'label_key': key, 'pos': [x, y], 'outward_references': sorted([list(map(str, t)) for t in outward]),
            'replaced': [menu_rt, panels_rt, G['toggle_mb']]}
    return sb, orig, new_ser, info

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['plan', 'build']); ap.add_argument('--src', required=True); ap.add_argument('--out'); ap.add_argument('--key', default='LABEL_STATE_AND_TYPE'); ap.add_argument('--text', default='Start with Martial Artist')
    ap.add_argument('--x', type=float, default=-375.0); ap.add_argument('--y', type=float, default=160.0); ap.add_argument('--mode', default='rebuild', choices=['rebuild', 'append'])
    a = ap.parse_args(argv)
    sb, orig, new_ser, info = plan_build(a.src, a.key, a.text, a.x, a.y)
    print('source bundle: %s (%d bytes, sha256 %s)' % (a.src, len(sb.raw), hashlib.sha256(sb.raw).hexdigest()[:16]))
    print('scene %s: %d -> %d bytes; objects %d -> %d (+%d); marker GO %d / RT %d (last child of ScenarioMenuParent RT %d); clone root GO %d RT %d button %d' % (SCENE, len(orig), len(new_ser), info['objects_before'], info['objects_after'], info['objects_after'] - info['objects_before'], info['marker_go'], info['marker_rt'], info['menu_parent_rt'], info['clone_root_go'], info['clone_root_rt'], info['clone_button_mb']))
    print('outward references of the clone (kept pointing at the original scene): %s' % info['outward_references'])
    if a.cmd == 'plan': print('(plan only, nothing written)'); return 0
    if not a.out: ap.error('--out required')
    if in_game_folder(a.out): print('REFUSED: --out is inside the game folder'); return 2
    os.makedirs(a.out, exist_ok=True); out = ufs.write_bundle(sb, SCENE, new_ser, a.mode); op = os.path.join(a.out, 'ui_screens')
    if os.path.abspath(op) == os.path.abspath(a.src): print('REFUSED: output would overwrite the source'); return 2
    open(op, 'wb').write(out); info.update({'out': op, 'mode': a.mode, 'sha256': hashlib.sha256(out).hexdigest(), 'src_sha256': hashlib.sha256(sb.raw).hexdigest(), 'size': len(out)})
    json.dump(info, open(op + '.build.json', 'w', encoding='utf8'), indent=1); print('wrote %s (%d bytes) sha256 %s' % (op, len(out), info['sha256'])); return 0
if __name__ == '__main__': sys.exit(main())
