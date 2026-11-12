#!/usr/bin/env python
"""verify_addimg.py - read-only verification of a bundle built by itd_mapscreen_addimg.py (work on copies only).
  python -I -X utf8 verify_addimg.py --orig <orig ui_screens copy> --new <new ui_screens> --info <new>.build.json [--game-bundles <AssetBundles dir>]
exit code 0 = all checks passed."""
import sys, os, json, struct, hashlib, argparse
HERE = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import itdp_ufs as ufs, itdp_ser as S, itdp_tt as tt
import itdp_build as T

class V:
    def __init__(s): s.fail = 0; s.n = 0
    def check(s, ok, msg):
        s.n += 1; print(('PASS  ' if ok else 'FAIL  ') + msg)
        if not ok: s.fail += 1

def ptrs(sr, trees, skip=()):
    """yield (object index, pid, path_prefix, fileID, pathID) for every PPtr (leaf pair)"""
    for i, (pid, bs, bsz, tid) in enumerate(sr.objects):
        if pid in skip: continue
        lv = tt.parse_object(sr, i, trees); m = {}
        for p, o, t, v in lv:
            if p.endswith('.m_FileID'): m[p[:-9]] = v
        for p, o, t, v in lv:
            if p.endswith('.m_PathID') and p[:-9] in m: yield i, pid, p[:-9], m[p[:-9]], v

F32 = lambda x: struct.unpack('<f', struct.pack('<f', float(x)))[0]

def verify_tree(v, n, trees, spec, info, orig_ser, new_ids):
    """independent check of the new subtree against the spec, walking the REAL new scene from the MapHud RectTransform"""
    Pn = n.by_pid(); Po = orig_ser.by_pid(); otrees = [tt.build_tree(t) for t in orig_ser.types]
    def orig_L(pid): return {p: val for p, off, t, val in tt.parse_object(orig_ser, Po[pid], otrees)}
    _lc = {}
    def L(pid):
        if pid not in _lc: _lc[pid] = {p: val for p, off, t, val in tt.parse_object(n, Pn[pid], trees)}
        return _lc[pid]
    # script pointer -> kind, taken from the ORIGINAL clone-source components
    kind_by_script = {}
    for kind in ('image', 'smarttext', 'localise', 'vlg', 'hlg', 'csf', 'button'):
        lv = {p: val for p, off, t, val in tt.parse_object(orig_ser, Po[T.TREE_SRC[kind]], otrees)}
        kind_by_script[(lv['m_Script.m_FileID'], lv['m_Script.m_PathID'])] = kind
    def kind_of(pid):
        c = n.types[n.objects[Pn[pid]][3]].class_id
        if c == 224: return 'rt'
        if c == 222: return 'cr'
        if c == 4: return 'transform'
        if c == 1: return 'go'
        if c == 114:
            lv = L(pid); return kind_by_script.get((lv['m_Script.m_FileID'], lv['m_Script.m_PathID']), 'unknown-mb')
        return 'class%d' % c
    table = json.load(open(os.path.join(HERE, 'panel_sprites.json'), encoding='utf8'))
    ext_paths = [e['path'] for e in n.externals]
    errs = []; reached = set(); name2go = {}; btns = []
    def err(path, msg): errs.append('%s: %s' % (path, msg))
    def expect_sprite(sp):
        if sp is None: return (0, 0)
        bundle, pid, cab = T.resolve_sprite(sp, table, None); path = 'archive:/%s/%s' % (cab, cab)
        return (ext_paths.index(path) + 1 if path in ext_paths else -1, pid)
    def check(node, rt_pid, father, path):
        if rt_pid not in Pn: err(path, 'RectTransform %d does not exist' % rt_pid); return
        reached.add(rt_pid); rt = L(rt_pid)
        if kind_of(rt_pid) != 'rt': err(path, 'object %d is not a RectTransform' % rt_pid); return
        go = rt['m_GameObject.m_PathID']
        if go not in Pn: err(path, 'GameObject %d missing' % go); return
        reached.add(go); g = L(go); name2go.setdefault(g['m_Name'], []).append(go)
        if rt['m_Father.m_PathID'] != father or rt['m_Father.m_FileID'] != 0: err(path, 'father is %d, expected %d' % (rt['m_Father.m_PathID'], father))
        if g['m_Name'] != node['name']: err(path, 'name %r != %r' % (g['m_Name'], node['name']))
        if bool(g['m_IsActive']) != bool(node.get('active', True)): err(path, 'active flag %s != spec %s' % (g['m_IsActive'], node.get('active', True)))
        if g['m_Layer'] != 0 or g['m_Tag'] != 0: err(path, 'layer/tag not 0')
        comps = [g['m_Component.Array[%d].component.m_PathID' % j] for j in range(g['m_Component.Array.size'])]
        if any(c not in Pn for c in comps): err(path, 'component pid missing'); return
        reached.update(comps)
        kinds = [kind_of(c) for c in comps]
        exp = ['rt'] + (['cr'] if ('image' in node or 'text' in node) else []) + (['image'] if 'image' in node else []) + (['button'] if 'button' in node else []) + (['smarttext', 'localise'] if 'text' in node else []) \
              + ([{'vertical': 'vlg', 'horizontal': 'hlg'}[node['layout']['type']]] if 'layout' in node else []) + (['csf'] if 'fitter' in node else [])
        if kinds != exp: err(path, 'component kinds/order %s != expected %s' % (kinds, exp)); return
        if comps[0] != rt_pid: err(path, 'first component is not the RectTransform')
        for c in comps:
            lv = L(c)
            if lv.get('m_GameObject.m_PathID') != go or lv.get('m_GameObject.m_FileID') != 0: err(path, 'component %d does not point back to GameObject %d' % (c, go))
        r = T.norm_rect(node.get('rect'))
        got = [rt['m_AnchorMin.x'], rt['m_AnchorMin.y'], rt['m_AnchorMax.x'], rt['m_AnchorMax.y'], rt['m_AnchoredPosition.x'], rt['m_AnchoredPosition.y'], rt['m_SizeDelta.x'], rt['m_SizeDelta.y'], rt['m_Pivot.x'], rt['m_Pivot.y']]
        want = [r['anchor_min'][0], r['anchor_min'][1], r['anchor_max'][0], r['anchor_max'][1], r['pos'][0], r['pos'][1], r['size'][0], r['size'][1], r['pivot'][0], r['pivot'][1]]
        if [F32(x) for x in want] != got: err(path, 'rect values %s != spec %s' % (got, want))
        ci = {k: c for c, k in zip(comps, kinds)}
        if 'image' in node:
            im = L(ci['image']); sp = expect_sprite(node['image'].get('sprite'))
            if (im['m_Sprite.m_FileID'], im['m_Sprite.m_PathID']) != sp: err(path, 'sprite PPtr %s != %s' % ((im['m_Sprite.m_FileID'], im['m_Sprite.m_PathID']), sp))
            if im['m_RaycastTarget'] != (1 if node['image'].get('raycast', False) else 0): err(path, 'raycast flag')
            col = node['image'].get('color', [1, 1, 1, 1])
            if [F32(x) for x in col] != [im['m_Color.' + c] for c in 'rgba']: err(path, 'image color')
            if im['m_PreserveAspect'] != (1 if node['image'].get('preserve_aspect', True) else 0): err(path, 'preserve aspect')
        if 'button' in node:
            bt = L(ci['button']); B = node['button']; cols = dict(T.BTN_COLORS); cols.update(B.get('colors', {}))
            if bt['m_Transition'] != 1: err(path, 'button transition %s != 1 (ColorTint)' % bt['m_Transition'])
            if bt['m_Navigation.m_Mode'] != 0: err(path, 'button navigation mode must be None')
            if bt['m_Interactable'] != (1 if B.get('interactable', True) else 0) or bt['m_Enabled'] != 1: err(path, 'button interactable/enabled')
            if (bt['m_TargetGraphic.m_FileID'], bt['m_TargetGraphic.m_PathID']) != (0, ci['image']): err(path, 'button target graphic is not its own image')
            for k_, f_ in T.BTN_COLOR_FIELDS:
                if [F32(x) for x in cols[k_]] != [bt['m_Colors.%s.%s' % (f_, c)] for c in 'rgba']: err(path, 'button color %s' % k_)
            if (bt['m_Colors.m_ColorMultiplier'], bt['m_Colors.m_FadeDuration']) != (F32(cols['multiplier']), F32(cols['fade'])): err(path, 'button color multiplier/fade')
            btns.append((path, node, bt))
        if 'text' in node:
            tx = node['text']; st = L(ci['smarttext']); lo = L(ci['localise'])
            if lo['m_key'] != tx.get('key', ''): err(path, 'text key %r != %r' % (lo['m_key'], tx.get('key', '')))
            if st['m_fontData.m_fontSize'] != int(tx.get('size', 20)): err(path, 'font size')
            if st['m_fontData.m_alignment'] != T._align(tx.get('align', 'MiddleLeft')): err(path, 'alignment')
            if st['m_fontData.m_globalFont'] != tx.get('font', 'Body-Bold'): err(path, 'font name')
            if st['m_RaycastTarget'] != 0: err(path, 'text raycast must be off')
            col = tx.get('color', [0.929411768913269, 0.9215686321258545, 0.8549019694328308, 1.0])
            if [F32(x) for x in col] != [st['m_Color.' + c] for c in 'rgba']: err(path, 'text color')
            if st['m_fontData.m_bestFit'] != 0 or lo['m_capitalise'] != 0: err(path, 'bestFit/capitalise')
        if 'layout' in node:
            lg = L(ci['vlg'] if node['layout']['type'] == 'vertical' else ci['hlg']); Ls = node['layout']
            pad = Ls.get('padding', [0, 0, 0, 0]); fe = Ls.get('force_expand', [False, False]); ct = Ls.get('control', [False, False])
            ok = [lg['m_Padding.m_Left'], lg['m_Padding.m_Right'], lg['m_Padding.m_Top'], lg['m_Padding.m_Bottom']] == [int(x) for x in pad] and lg['m_ChildAlignment'] == T._align(Ls.get('align', 'UpperLeft')) \
                 and lg['m_Spacing'] == F32(Ls.get('spacing', 0)) and (lg['m_ChildForceExpandWidth'], lg['m_ChildForceExpandHeight']) == (int(bool(fe[0])), int(bool(fe[1]))) \
                 and (lg['m_ChildControlWidth'], lg['m_ChildControlHeight']) == (int(bool(ct[0])), int(bool(ct[1]))) and (lg['m_ChildScaleWidth'], lg['m_ChildScaleHeight'], lg['m_ReverseArrangement']) == (0, 0, int(bool(Ls.get('reverse', False))))
            if not ok: err(path, 'layout group fields differ from spec')
        if 'fitter' in node:
            cf = L(ci['csf']); F = node['fitter']
            if (cf['m_HorizontalFit'], cf['m_VerticalFit']) != (T.FIT[F.get('h', 'unconstrained')], T.FIT[F.get('v', 'unconstrained')]): err(path, 'content size fitter modes')
        kids = [rt['m_Children.Array[%d].m_PathID' % j] for j in range(rt['m_Children.Array.size'])]
        spec_kids = node.get('children', [])
        want_kids = len(spec_kids) + (1 if 'text' in node else 0)
        if len(kids) != want_kids: err(path, 'has %d children, spec says %d%s' % (len(kids), want_kids, ' (+inlineImages)' if 'text' in node else '')); return
        for j, c in enumerate(spec_kids): check(c, kids[j], rt_pid, path + '/' + c['name'])
        if 'text' in node:
            irt = kids[-1]
            if irt not in Pn: err(path, 'inlineImages transform missing'); return
            reached.add(irt); tr = L(irt); igo = tr['m_GameObject.m_PathID']
            if kind_of(irt) != 'transform' or tr['m_Father.m_PathID'] != rt_pid: err(path, 'inlineImages transform/father wrong'); return
            reached.add(igo); ig = L(igo); ic = [ig['m_Component.Array[%d].component.m_PathID' % j] for j in range(ig['m_Component.Array.size'])]
            reached.update(ic)
            if ig['m_Name'] != 'inlineImages' or [kind_of(c) for c in ic] != ['transform', 'cr'] or ic[0] != irt or not ig['m_IsActive']: err(path, 'inlineImages GameObject/components wrong')
            for c in ic:
                if L(c)['m_GameObject.m_PathID'] != igo: err(path, 'inlineImages component back-reference wrong')
    par = L(info['parent_rect']); kids = [par['m_Children.Array[%d].m_PathID' % j] for j in range(par['m_Children.Array.size'])]
    roots = T.spec_roots(spec)
    if len(kids) != info['parent_children_before'] + len(roots): err('MapHud', 'children count %d != original+%d' % (len(kids), len(roots))); return errs
    orig_kids = [orig_L(info['parent_rect'])['m_Children.Array[%d].m_PathID' % j] for j in range(info['parent_children_before'])]
    new_kids = sorted(k for k in kids if k not in set(orig_kids))                     # allocation order == spec root order
    if [k for k in kids if k in set(orig_kids)] != orig_kids: err('MapHud', 'the original children changed order or were removed'); return errs
    want = list(orig_kids)
    for rt_, r_ in zip(new_kids, roots):                                                # independent re-implementation of the insertion rule
        ins = r_.get('insert', 'back'); idx = len(want) if ins == 'back' else 0 if ins == 'front' else max(0, min(int(ins), len(want))); want.insert(idx, rt_)
    if kids != want: err('MapHud', 'child order %s != expected %s' % (kids[-6:], want[-6:])); return errs
    for rt_, r_ in zip(new_kids, roots): check(r_, rt_, info['parent_rect'], r_['name'])
    # button calls (second pass: every target must be a GameObject of the walked tree, named as in the spec, exactly one)
    for path, node, bt in btns:
        calls = node['button'].get('calls', [])
        if bt['m_OnClick.m_PersistentCalls.m_Calls.Array.size'] != len(calls): err(path, 'button has %d calls, spec %d' % (bt['m_OnClick.m_PersistentCalls.m_Calls.Array.size'], len(calls))); continue
        for j, c in enumerate(calls):
            q = 'm_OnClick.m_PersistentCalls.m_Calls.Array[%d].' % j
            tg = name2go.get(c['target'], [])
            if len(tg) != 1: err(path, 'call %d: target %r matches %d GameObjects' % (j, c['target'], len(tg))); continue
            if (bt[q + 'm_Target.m_FileID'], bt[q + 'm_Target.m_PathID']) != (0, tg[0]): err(path, 'call %d: target PPtr %s != GameObject %d of %r' % (j, bt[q + 'm_Target.m_PathID'], tg[0], c['target']))
            tname, mode = T.CALL_METHODS[c['method']]
            if (bt[q + 'm_TargetAssemblyTypeName'], bt[q + 'm_MethodName'], bt[q + 'm_Mode']) != (tname, c['method'], mode): err(path, 'call %d: type/method/mode' % j)
            if bt[q + 'm_Arguments.m_BoolArgument'] != (1 if c['bool'] else 0) or bt[q + 'm_CallState'] != 2: err(path, 'call %d: bool argument / call state' % j)
            if (bt[q + 'm_Arguments.m_ObjectArgument.m_PathID'], bt[q + 'm_Arguments.m_IntArgument'], bt[q + 'm_Arguments.m_FloatArgument'], bt[q + 'm_Arguments.m_StringArgument'],
                    bt[q + 'm_Arguments.m_ObjectArgumentAssemblyTypeName']) != (0, 0, 0.0, '', 'UnityEngine.Object, UnityEngine'): err(path, 'call %d: unused arguments not default' % j)
    stray = sorted(set(new_ids) - reached)
    if stray: err('tree', 'new objects not reachable from the spec tree: %s' % stray[:8])
    extra = sorted(reached - set(new_ids))
    if extra: err('tree', 'tree reaches objects that are not new: %s' % extra[:8])
    return errs

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('--orig', required=True); ap.add_argument('--new', required=True)
    ap.add_argument('--info', required=True); ap.add_argument('--game-bundles'); ap.add_argument('--no-unitypy', action='store_true'); ap.add_argument('--spec')
    a = ap.parse_args(argv); v = V(); SCENE = 'BuildPlayer-MapScreen'
    info = json.load(open(a.info, encoding='utf8'))
    ob = ufs.Bundle(a.orig); nb = ufs.Bundle(a.new)
    # ---------------- bundle level
    v.check(nb.size == len(nb.raw), 'B1 header size field == file length (%d)' % len(nb.raw))
    v.check([n[3] for n in nb.nodes] == [n[3] for n in ob.nodes], 'B2 same 140 directory nodes, same order, same names')
    v.check(all(n[2] == o[2] for n, o in zip(nb.nodes, ob.nodes)), 'B3 node flags unchanged')
    dec = nb.decompress(); end = max(n[0] + n[1] for n in nb.nodes)
    v.check(len(dec) == sum(b[0] for b in nb.blocks) and end <= len(dec), 'B4 every directory node lies inside the decompressed stream')
    spans = sorted((n[0], n[0] + n[1]) for n in nb.nodes)
    v.check(all(spans[i][1] <= spans[i + 1][0] for i in range(len(spans) - 1)), 'B5 directory nodes do not overlap')
    same = [n[3] for n in ob.nodes if n[3] != SCENE and nb.node_data(n[3]) == ob.node_data(n[3])]
    v.check(len(same) == len(ob.nodes) - 1, 'B6 all other %d nodes byte-identical to the original (%d)' % (len(ob.nodes) - 1, len(same)))
    kept = sum(1 for i in range(min(len(ob.blocks), len(nb.blocks))) if ob.comp_block(i) == nb.comp_block(i) and ob.blocks[i] == nb.blocks[i])
    print('INFO  compressed blocks reused verbatim: %d of %d (orig %d)' % (kept, len(nb.blocks), len(ob.blocks)))
    v.check(nb.version == ob.version and nb.engine == ob.engine and nb.flags == ob.flags and nb.player == ob.player, 'B7 bundle header fields (version/engine/flags) unchanged')
    # ---------------- serialized file level
    oraw = ob.node_data(SCENE); nraw = nb.node_data(SCENE)
    o = S.Ser(oraw); n = S.Ser(nraw)
    v.check(n.file_size == len(nraw), 'S1 header file_size == scene node length (%d)' % len(nraw))
    v.check(n.metadata_size == n.meta_end - 48 and n.meta_end == 48 + n.metadata_size, 'S2 header metadata_size == parsed metadata length (%d)' % n.metadata_size)
    v.check(n.data_offset == (48 + n.metadata_size + 15) // 16 * 16 and nraw[48 + n.metadata_size:n.data_offset] == b'\0' * (n.data_offset - 48 - n.metadata_size), 'S3 data_offset is 16-aligned after metadata, zero padded (%d)' % n.data_offset)
    v.check(oraw[48:o.objects_count_pos] == nraw[48:n.objects_count_pos], 'S4 type table (86 types incl. v23 28-byte records, ref types) byte-identical')
    v.check(oraw[o.objects_end:o.externals_count_pos] == nraw[n.objects_end:n.externals_count_pos], 'S5 script-type table byte-identical')
    v.check(oraw[o.externals_end:o.meta_end] == nraw[n.externals_end:n.meta_end], 'S6 ref-types + user-info tail byte-identical')
    exp_ext = [e['path'] for e in o.externals] + info['new_externals']
    v.check([e['path'] for e in n.externals] == exp_ext and all(e['guid'] == b'\0' * 16 and e['type'] == 0 and e['empty'] == '' for e in n.externals[len(o.externals):]), 'S7 externals = original %d + new %d (new entries: guid 0, type 0, like the other CAB entries)' % (len(o.externals), len(info['new_externals'])))
    v.check(oraw[o.externals_start:o.externals_end] == nraw[n.externals_start:n.externals_start + (o.externals_end - o.externals_start)], 'S8 original externals byte-identical (FileIDs 1..%d unchanged)' % len(o.externals))
    pos = 0; ok = True
    for pid, bs, bsz, tid in n.objects:
        if bs != pos: ok = False
        pos = (bs + bsz + 15) // 16 * 16
    v.check(ok and pos == len(nraw) - n.data_offset, 'S9 object data contiguous, 16-aligned, ends at file end')
    opids = [x[0] for x in o.objects]; npids = [x[0] for x in n.objects]
    is_tree = info.get('format') == 'tree'
    root_rects = info.get('root_rects') or ([info['root_rect']] if is_tree else [])       # builds made by the older tool version carry only root_rect
    spec_roots_s = T.spec_roots(json.load(open(a.spec, encoding='utf8'))) if (is_tree and a.spec) else []
    new_ids = info['new_pids'] if is_tree else [p for s_ in info['slots'] for p in (s_['go'], s_['rect'], s_['canvasRenderer'], s_['image'])]
    v.check(npids == opids + new_ids and len(set(npids)) == len(npids), 'S10 object table = original order + new ids (unique): %s' % new_ids)
    v.check(all(x[3] == y[3] for x, y in zip(o.objects, n.objects)), 'S11 original objects keep their type ids')
    # object bytes
    PR = info['parent_rect']; po = o.by_pid(); pn = n.by_pid()
    diff = [p for p in opids if o.object_bytes(po[p]) != n.object_bytes(pn[p])]
    v.check(diff == [PR], 'S12 exactly one original object changed: %s (expected [%d])' % (diff, PR))
    ob_, nb_ = o.object_bytes(po[PR]), n.object_bytes(pn[PR])
    trees = [tt.build_tree(t) for t in o.types]
    lo = {p: (off, val) for p, off, t, val in tt.parse_object(o, po[PR], trees)}
    k = len(root_rects) if is_tree else len(info['slots']); ins = lo['m_Father.m_FileID'][0]
    if is_tree:
        a0 = lo['m_Children.Array.size'][0]; n_old = lo['m_Children.Array.size'][1]
        old_kids = [struct.unpack_from('<q', ob_, a0 + 4 + 12 * j + 4)[0] for j in range(n_old)]
        new_in = sorted(struct.unpack_from('<q', nb_, a0 + 4 + 12 * j + 4)[0] for j in range(n_old + k) if struct.unpack_from('<q', nb_, a0 + 4 + 12 * j + 4)[0] not in old_kids)
        wk = list(old_kids)
        for rt_, r_ in zip(new_in, spec_roots_s):
            ins_ = r_.get('insert', 'back'); idx = len(wk) if ins_ == 'back' else 0 if ins_ == 'front' else max(0, min(int(ins_), len(wk))); wk.insert(idx, rt_)
        exp = bytearray(ob_); exp[a0:ins] = struct.pack('<i', len(wk)) + b''.join(struct.pack('<iq', 0, c) for c in wk)
    else:
        child_rects = [s_['rect'] for s_ in info['slots']]
        exp = bytearray(ob_); struct.pack_into('<i', exp, lo['m_Children.Array.size'][0], lo['m_Children.Array.size'][1] + k)
        exp[ins:ins] = b''.join(struct.pack('<iq', 0, c) for c in child_rects)
    v.check(bytes(exp) == nb_, 'S13 parent RectTransform == original + %d children appended (only size field + inserted PPtrs differ)' % k)
    # parse everything
    SKIP = {1706, 2180}
    bad = []
    for i in range(len(n.objects)):
        if n.objects[i][0] in SKIP: continue
        try: tt.parse_object(n, i, trees)
        except Exception as e: bad.append((n.objects[i][0], str(e)[:60]))
    v.check(not bad, 'S14 every object (except the 2 SerializeReference ones, unchanged) parses with its type tree and consumes exactly its bytes %s' % bad[:3])
    # PPtr integrity
    ids = set(npids); nex = len(n.externals); dangling = []; badfid = []; ext_targets = {}
    for i, pid, pre, fid, tp in ptrs(n, trees, SKIP):
        if fid == 0:
            if tp != 0 and tp not in ids: dangling.append((pid, pre, tp))
        elif fid < 0 or fid > nex: badfid.append((pid, pre, fid))
        elif pid in new_ids: ext_targets[(pid, pre)] = (fid, tp)
    v.check(not dangling, 'P1 every internal PPtr (fileID 0) points to an existing object %s' % dangling[:3])
    v.check(not badfid, 'P2 every external PPtr fileID is within 1..%d %s' % (nex, badfid[:3]))
    # new objects structure
    Pn = n.by_pid(); good = True
    def L(pid): return {p: val for p, off, t, val in tt.parse_object(n, Pn[pid], trees)}
    for s_ in info['slots']:
        if not all(q in Pn for q in (s_['go'], s_['rect'], s_['canvasRenderer'], s_['image'])):
            v.check(False, 'N1 slot %s: new objects missing from the object table' % s_['name']); continue
        go, rt, cr, im = L(s_['go']), L(s_['rect']), L(s_['canvasRenderer']), L(s_['image'])
        comps = [go['m_Component.Array[%d].component.m_PathID' % j] for j in range(go['m_Component.Array.size'])]
        c1 = comps == [s_['rect'], s_['canvasRenderer'], s_['image']]
        c2 = all(x['m_GameObject.m_PathID'] == s_['go'] and x['m_GameObject.m_FileID'] == 0 for x in (rt, cr, im))
        pl = L(PR); kids = [pl['m_Children.Array[%d].m_PathID' % j] for j in range(pl['m_Children.Array.size'])]
        c3 = rt['m_Father.m_PathID'] == PR and rt['m_Father.m_FileID'] == 0 and kids.count(s_['rect']) == 1 and kids[-1 - (k - 1 - info['slots'].index(s_))] == s_['rect']
        c4 = go['m_Name'] == s_['name'] and bool(go['m_IsActive']) == s_.get('active', True)
        c5 = im['m_Sprite.m_FileID'] == s_['spriteFileID'] and im['m_Sprite.m_PathID'] == s_['spritePathID'] and im['m_RaycastTarget'] == 0
        types_ok = [n.types[n.objects[Pn[p]][3]].class_id for p in (s_['go'], s_['rect'], s_['canvasRenderer'], s_['image'])] == [1, 224, 222, 114]
        v.check(c1 and c2 and c3 and c4 and c5 and types_ok, 'N1 slot %s: GO->[RT,CR,Image], back-references, parent link, name/active, sprite PPtr (%d,%d), raycast off, classes [1,224,222,114]' % (s_['name'], s_['spriteFileID'], s_['spritePathID']))
        ph = n.externals[s_['spriteFileID'] - 1]['path']
        v.check(ph.endswith('/' + os.path.basename(ph)) and s_['bundle'] != '' and (s_['spriteFileID'] <= len(o.externals) or ph in info['new_externals']), 'N2 slot %s: sprite external #%d = %s' % (s_['name'], s_['spriteFileID'], ph[-52:]))
    if is_tree:
        if not a.spec: v.check(False, 'T0 tree build needs --spec for the structure check')
        else:
            spec = json.load(open(a.spec, encoding='utf8'))
            errs = verify_tree(v, n, trees, spec, info, o, new_ids)
            v.check(not errs, 'T1 new subtree == spec (names, active flags, hierarchy/child order, parents, GameObject<->components, script kinds, rects, sprites, text keys, layout/fitter fields, inlineImages, no stray objects) %s' % errs[:4])
    # external sprite existence in the real bundles (read-only)
    if a.game_bundles and not a.no_unitypy:
        import UnityPy
        from UnityPy.helpers.TypeTreeNode import TypeTreeNode
        if not getattr(TypeTreeNode, '_itd_v23_patch', False):   # skip the v23 28-byte record exactly once (read-only helper for UnityPy)
            orig_pb = TypeTreeNode.parse_blob.__func__
            def pb(cls, reader, version):
                reader.read(28); return orig_pb(cls, reader, version)
            TypeTreeNode.parse_blob = classmethod(pb); TypeTreeNode._itd_v23_patch = True
        cache = {}
        if is_tree and a.spec:
            sprites = {}
            def collect(nd):
                sp = nd.get('image', {}).get('sprite')
                if sp:
                    bundle, pid, cab = T.resolve_sprite(sp, json.load(open(os.path.join(HERE, 'panel_sprites.json'), encoding='utf8')), None); sprites[(bundle, pid)] = sp
                for c in nd.get('children', []): collect(c)
            for r_ in T.spec_roots(json.load(open(a.spec, encoding='utf8'))): collect(r_)
            for (bn, pid), sp in sorted(sprites.items(), key=lambda x: str(x)):
                if bn not in cache: cache[bn] = {x.path_id: x.type.name for x in UnityPy.load(os.path.join(a.game_bundles, bn)).objects}
                v.check(cache[bn].get(pid) == 'Sprite', 'P3 sprite %s: pathID %d exists in bundle %s and is a Sprite' % (sp, pid, bn))
        for s_ in info['slots']:
            bn = s_['bundle']
            if bn not in cache: cache[bn] = {x.path_id: x.type.name for x in UnityPy.load(os.path.join(a.game_bundles, bn)).objects}
            v.check(cache[bn].get(s_['spritePathID']) == 'Sprite', 'P3 slot %s: pathID %d exists in bundle %s and is a Sprite' % (s_['name'], s_['spritePathID'], bn))
        # UnityPy independent read of the new scene objects
        import UnityPy as U
        env = U.load(a.new); objs = {x.path_id: x for x in env.objects if x.assets_file.name == SCENE}
        ok = True
        for s_ in info['slots']:
            t = objs[s_['image']].read_typetree(); g = objs[s_['go']].read_typetree()
            ok &= (t['m_Sprite']['m_FileID'] == s_['spriteFileID'] and t['m_Sprite']['m_PathID'] == s_['spritePathID'] and g['m_Name'] == s_['name'])
        if is_tree:
            for rr, r_ in zip(root_rects, T.spec_roots(json.load(open(a.spec, encoding='utf8')))):
                rg = objs[rr].read_typetree(); gg = objs[rg['m_GameObject']['m_PathID']].read_typetree(); ok &= (gg['m_Name'] == r_['name'])
            ok &= all(pid in objs for pid in info['new_pids'])
        pt = objs[PR].read_typetree(); ok &= ([c['m_PathID'] for c in pt['m_Children']] == info['parent_children_after'] if (is_tree and 'parent_children_after' in info) else pt['m_Children'][-1]['m_PathID'] == root_rects[-1] if is_tree else pt['m_Children'][-1]['m_PathID'] == info['slots'][-1]['rect'])
        v.check(ok and len(objs) == len(n.objects), 'U1 UnityPy (independent reader) loads the new bundle: %d scene objects, new GO/Image/children read back correctly' % len(objs))
    print('\n%d checks, %d failed' % (v.n, v.fail)); return 1 if v.fail else 0

if __name__ == '__main__': sys.exit(main())
