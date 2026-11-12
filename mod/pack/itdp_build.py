#!/usr/bin/env python
"""itd_mapscreen_addimg.py - COPY-ONLY tool: add fixed Image slots to BuildPlayer-MapScreen inside a ui_screens bundle copy.

  python -I -X utf8 itd_mapscreen_addimg.py plan  --src <ui_screens copy> --spec spec.json
  python -I -X utf8 itd_mapscreen_addimg.py build --src <ui_screens copy> --spec spec.json --out <dir> [--mode rebuild|append]

Never writes into the game folder (refused). The source file is only read. Requires: python 3.10+, lz4, UnityPy (common-string table only).
"""
import sys, os, json, struct, hashlib, argparse
HERE = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import itdp_ufs as ufs, itdp_ser as S, itdp_tt as tt, itdp_edit as ser_edit

SCENE = 'BuildPlayer-MapScreen'
GAME_MARK = os.path.normcase(r'steamapps\common\into the dead our darkest days')
PARENT_GO_NAME = 'MapHud'; PARENT_RT = 1174; PARENT_GO = 4
CLONE = {'go': 17, 'rt': 1185, 'cr': 675, 'mb': 1693}      # VignetteImage (child of MapHud: RectTransform+CanvasRenderer+Image, no SoftMaskable)
CLONE_GO_NAME = 'VignetteImage'

def in_game_folder(p): return GAME_MARK in os.path.normcase(os.path.abspath(p))

PRIMFMT = {'float': 'f', 'bool': '?', 'UInt8': 'B', 'int': 'i', 'SInt64': 'q', 'unsigned int': 'I', 'UInt16': 'H'}

class Obj:
    """raw object bytes + leaf offsets from the type tree"""
    def __init__(self, sr, trees, pid):
        P = sr.by_pid(); self.i = P[pid]; self.pid = pid; self.tid = sr.objects[self.i][3]
        self.root = trees[self.tid]; self.b = bytearray(sr.object_bytes(self.i)); lv = tt.parse_object(sr, self.i, trees)
        self.off = {p: (o, t) for p, o, t, v in lv}; self.val = {p: v for p, o, t, v in lv}
    def set(self, path, v):
        o, t = self.off[path]; struct.pack_into('<' + PRIMFMT[t], self.b, o, v)
    def set_str(self, path, s):
        o, t = self.off[path]; assert t == 'string', (path, t)
        ln, = struct.unpack_from('<i', self.b, o); old = 4 + ln + ((-ln) % 4)
        nb = s.encode('utf8'); new = struct.pack('<i', len(nb)) + nb + b'\0' * ((-len(nb)) % 4)
        self.b[o:o + old] = new
        lv = tt.parse_bytes(self.root, bytes(self.b)); self.off = {p: (oo, tt_) for p, oo, tt_, v in lv}; self.val = {p: v for p, oo, tt_, v in lv}

def make_go(comp_pids, layer, name, active):
    b = struct.pack('<i', len(comp_pids))
    for p in comp_pids: b += struct.pack('<iq', 0, p)
    nb = name.encode()
    b += struct.pack('<I', layer) + struct.pack('<i', len(nb)) + nb + b'\0' * ((-len(nb)) % 4)
    b += struct.pack('<HB', 0, 1 if active else 0)
    return b

def resolve_sprite(spec, table, ext_paths):
    """-> (kind, bundle, pid) ; kind face/trait"""
    if isinstance(spec, str):
        k, n = spec.split(':', 1)
        if k == 'face': return 'character_icons', table['faces'][n]['pid'], table['meta']['character_icons_cab']
        if k == 'trait':
            key = n if n in table['traits'] else 'Trait+' + n
            return 'data_visual', table['traits'][key]['pid'], table['meta']['data_visual_cab']
        raise ValueError(spec)
    return spec['bundle'], spec['pid'], table['meta'][spec['bundle'] + '_cab']

def plan_build(src_bundle_path, spec):
    if 'root' in spec or 'roots' in spec: return plan_build_tree(src_bundle_path, spec)
    return plan_build_slots(src_bundle_path, spec)

def plan_build_slots(src_bundle_path, spec):
    sb = ufs.Bundle(src_bundle_path)
    orig = sb.node_data(SCENE)
    sr = S.Ser(orig); trees = [tt.build_tree(t) for t in sr.types]
    P = sr.by_pid()
    # --- sanity: the objects we depend on are what we think they are
    def name_of(go): return Obj(sr, trees, go).val['m_Name']
    assert name_of(PARENT_GO) == PARENT_GO_NAME, 'MapHud GO changed'
    assert name_of(CLONE['go']) == CLONE_GO_NAME, 'clone source changed'
    rt_par = Obj(sr, trees, PARENT_RT); assert rt_par.val['m_GameObject.m_PathID'] == PARENT_GO
    table = json.load(open(os.path.join(HERE, 'panel_sprites.json'), encoding='utf8'))
    ext_paths = [e['path'] for e in sr.externals]
    new_ext = []
    def fid_for(cab):
        path = 'archive:/%s/%s' % (cab, cab)
        if path in ext_paths: return ext_paths.index(path) + 1
        if path not in new_ext: new_ext.append(path)
        return len(ext_paths) + new_ext.index(path) + 1
    next_pid = max(o[0] for o in sr.objects) + 1
    append = []; slots_out = []; child_pids = []
    for k, sl in enumerate(spec['slots']):
        gpid, rpid, cpid, mpid = [next_pid + 4 * k + j for j in range(4)]
        bundle, spid, cab = resolve_sprite(sl['sprite'], table, ext_paths)
        fid = fid_for(cab)
        rt = Obj(sr, trees, CLONE['rt']); cr = Obj(sr, trees, CLONE['cr']); mb = Obj(sr, trees, CLONE['mb'])
        amin = sl.get('anchor_min', sl.get('anchor', [0, 0])); amax = sl.get('anchor_max', sl.get('anchor', [0, 0]))
        rt.set('m_GameObject.m_PathID', gpid); rt.set('m_Father.m_PathID', PARENT_RT); rt.set('m_Father.m_FileID', 0)
        for pth, v in (('m_AnchorMin.x', amin[0]), ('m_AnchorMin.y', amin[1]), ('m_AnchorMax.x', amax[0]), ('m_AnchorMax.y', amax[1]),
                       ('m_AnchoredPosition.x', sl['pos'][0]), ('m_AnchoredPosition.y', sl['pos'][1]),
                       ('m_SizeDelta.x', sl['size'][0]), ('m_SizeDelta.y', sl['size'][1]),
                       ('m_Pivot.x', sl.get('pivot', [0.5, 0.5])[0]), ('m_Pivot.y', sl.get('pivot', [0.5, 0.5])[1])):
            rt.set(pth, float(v))
        cr.set('m_GameObject.m_PathID', gpid)
        mb.set('m_GameObject.m_PathID', gpid)
        for c, v in zip('rgba', sl.get('color', [1, 1, 1, 1])): mb.set('m_Color.' + c, float(v))
        mb.set('m_RaycastTarget', 0)
        mb.set('m_Sprite.m_FileID', fid); mb.set('m_Sprite.m_PathID', spid)
        mb.set('m_PreserveAspect', 1 if sl.get('preserve_aspect', True) else 0)
        go = make_go([rpid, cpid, mpid], 0, sl['name'], sl.get('active', True))
        types = {n: sr.objects[P[CLONE[n]]][2:] for n in CLONE}
        append += [(gpid, sr.objects[P[CLONE['go']]][3], go), (rpid, rt.tid, bytes(rt.b)), (cpid, cr.tid, bytes(cr.b)), (mpid, mb.tid, bytes(mb.b))]
        child_pids.append(rpid)
        slots_out.append({'name': sl['name'], 'go': gpid, 'rect': rpid, 'canvasRenderer': cpid, 'image': mpid, 'sprite': sl['sprite'],
                          'spriteFileID': fid, 'spritePathID': spid, 'bundle': bundle, 'active': bool(sl.get('active', True))})
    # --- parent: append children to m_Children (array grows by 12 bytes per child), inserted before m_Father
    n_old = rt_par.val['m_Children.Array.size']; ins = rt_par.off['m_Father.m_FileID'][0]
    assert ins == rt_par.off['m_Children.Array.size'][0] + 4 + 12 * n_old
    pb = bytearray(rt_par.b)
    struct.pack_into('<i', pb, rt_par.off['m_Children.Array.size'][0], n_old + len(child_pids))
    pb[ins:ins] = b''.join(struct.pack('<iq', 0, c) for c in child_pids)
    new_ser = ser_edit.rebuild(orig, replace={PARENT_RT: bytes(pb)}, append=append, new_externals=new_ext)
    return sb, orig, new_ser, {'slots': slots_out, 'new_externals': new_ext, 'parent_rect': PARENT_RT, 'parent_children_before': n_old,
                               'objects_before': len(sr.objects), 'objects_after': len(sr.objects) + len(append)}

# ----------------------------------------------------------------------------------------------------------------------
# Tree spec (version 2): panel root -> rows -> cells, built from clones of existing MapScreen objects
#   image : VignetteImage (GO 17): RectTransform 1185, CanvasRenderer 675, Image MB 1693
#   text  : StreetText (GO 16): CanvasRenderer 674, SmartText MB 1691, LocaliseSmartText MB 1692, + child 'inlineImages'
#           (GO 15: plain Transform 555 + CanvasRenderer 673, as every SmartText in the scene has)
#   layout: VerticalLayoutGroup MB 2381 (from ScavengeGroup GO 243), HorizontalLayoutGroup MB 1825 (from HoriGroup GO 487)
#   fitter: ContentSizeFitter MB 2559 (from ResourceText GO 80)
#   button: Button MB 2561 (from CTAMoveShelterButton GO 515): the 308-byte fixed part is cloned (ColorTint instead of Animation, no Animator), the UnityEvent call list is re-serialised
TREE_SRC = {'rt': 1185, 'cr': 675, 'image': 1693, 'smarttext': 1691, 'localise': 1692, 'vlg': 2381, 'hlg': 1825, 'csf': 2559,
            'inl_go': 15, 'inl_tr': 555, 'inl_cr': 673, 'button': 2561}
TREE_SRC_NAMES = {17: 'VignetteImage', 16: 'StreetText', 243: 'ScavengeGroup', 487: 'HoriGroup', 80: 'ResourceText', 15: 'inlineImages', 515: 'CTAMoveShelterButton'}
BTN_COLORS = {'normal': [1, 1, 1, 1], 'highlighted': [1.8, 1.8, 1.8, 1], 'pressed': [0.6, 0.6, 0.6, 1], 'selected': [1, 1, 1, 1], 'disabled': [0.5, 0.5, 0.5, 0.5], 'multiplier': 1.0, 'fade': 0.1}
BTN_COLOR_FIELDS = (('normal', 'm_NormalColor'), ('highlighted', 'm_HighlightedColor'), ('pressed', 'm_PressedColor'), ('selected', 'm_SelectedColor'), ('disabled', 'm_DisabledColor'))
BTN_FIXED = 308                      # bytes before m_OnClick.m_PersistentCalls.m_Calls.Array.size in the Button object
CALL_METHODS = {'SetActive': ('UnityEngine.GameObject, UnityEngine', 6)}     # method -> (target type name, PersistentListenerMode: 6 = Bool)

def _s(x):
    b = x.encode('utf8'); return struct.pack('<i', len(b)) + b + b'\0' * ((-len(b)) % 4)

def call_bytes(target_pid, method, flag):
    """one UnityEngine.Events.PersistentCall: GameObject.SetActive(<fixed bool>), CallState RuntimeOnly (the same bytes as ShelterTab/ScavengeTab in this scene)"""
    tname, mode = CALL_METHODS[method]
    return (struct.pack('<iq', 0, target_pid) + _s(tname) + _s(method) + struct.pack('<i', mode) + struct.pack('<iq', 0, 0) + _s('UnityEngine.Object, UnityEngine')
            + struct.pack('<i', 0) + struct.pack('<f', 0.0) + _s('') + struct.pack('<B', 1 if flag else 0) + b'\0\0\0' + struct.pack('<i', 2))

def spec_roots(spec): return [spec['root']] if 'root' in spec else spec['roots']

def place_children(orig_children, new_rects, inserts):
    """children list of the parent after inserting the new roots one by one: 'back' (default) | 'front' | integer index"""
    lst = list(orig_children)
    for r, ins in zip(new_rects, inserts):
        idx = len(lst) if ins in (None, 'back') else 0 if ins == 'front' else max(0, min(int(ins), len(lst)))
        lst.insert(idx, r)
    return lst
ALIGN = {'UpperLeft': 0, 'UpperCenter': 1, 'UpperRight': 2, 'MiddleLeft': 3, 'MiddleCenter': 4, 'MiddleRight': 5, 'LowerLeft': 6, 'LowerCenter': 7, 'LowerRight': 8}
FIT = {'unconstrained': 0, 'min': 1, 'preferred': 2}

def _align(v): return ALIGN[v] if isinstance(v, str) else int(v)

def norm_rect(r):
    r = r or {}
    amin = r.get('anchor_min', r.get('anchor', [0, 1])); amax = r.get('anchor_max', r.get('anchor', [0, 1]))
    return {'anchor_min': list(amin), 'anchor_max': list(amax), 'pivot': list(r.get('pivot', [0, 1])), 'pos': list(r.get('pos', [0, 0])), 'size': list(r.get('size', [0, 0]))}

def validate_tree(node, path='root'):
    if 'name' not in node: raise ValueError(path + ': name missing')
    if 'image' in node and 'text' in node: raise ValueError(path + ': a node cannot have both image and text (one Graphic per GameObject)')
    if 'layout' in node and node['layout'].get('type') not in ('horizontal', 'vertical'): raise ValueError(path + ': layout.type must be horizontal|vertical')
    if 'button' in node:
        if 'image' not in node: raise ValueError(path + ': a button needs an image on the same node (its target graphic)')
        for c in node['button'].get('calls', []):
            if c.get('method') not in CALL_METHODS: raise ValueError(path + ': unsupported call method %r (only %s)' % (c.get('method'), ', '.join(CALL_METHODS)))
            if not isinstance(c.get('bool'), bool) or not c.get('target'): raise ValueError(path + ': a call needs target (node name) and bool (fixed argument)')
    for k, c in enumerate(node.get('children', [])): validate_tree(c, path + '/' + c.get('name', str(k)))
    if node.get('children') and 'text' in node: raise ValueError(path + ': text nodes cannot have children')

def validate_spec(spec):
    if ('root' in spec) == ('roots' in spec): raise ValueError('spec needs exactly one of root / roots')
    names = {}
    def walk(nd):
        names.setdefault(nd['name'], 0); names[nd['name']] += 1
        for c in nd.get('children', []): walk(c)
    for r in spec_roots(spec):
        validate_tree(r)
        if r.get('insert', 'back') not in ('back', 'front') and not isinstance(r.get('insert'), int): raise ValueError('root %s: insert must be back|front|<int>' % r['name'])
        walk(r)
    def calls(nd):
        for c in nd.get('button', {}).get('calls', []):
            if names.get(c['target'], 0) != 1: raise ValueError('button %s: call target %r matches %d nodes (must be exactly 1)' % (nd['name'], c['target'], names.get(c['target'], 0)))
        for c in nd.get('children', []): calls(c)
    for r in spec_roots(spec): calls(r)

def alloc_tree(node, next_pid, out):
    """pre-order id allocation: returns (record, next_pid)"""
    rec = {'node': node, 'ids': {}}
    def take(k): nonlocal next_pid; rec['ids'][k] = next_pid; next_pid += 1
    take('go'); take('rt')
    graphic = 'image' in node or 'text' in node
    if graphic: take('cr')
    if 'image' in node: take('image')
    if 'button' in node: take('button')
    if 'text' in node: take('smarttext'); take('localise')
    if 'layout' in node: take('layout')
    if 'fitter' in node: take('fitter')
    if 'text' in node: take('inl_go'); take('inl_tr'); take('inl_cr')
    rec['children'] = []
    for c in node.get('children', []):
        r, next_pid = alloc_tree(c, next_pid, out); rec['children'].append(r)
    out.append(rec)
    return rec, next_pid

def build_tree_objects(sr, trees, spec, table, fid_for):
    """returns (append_list [(pid, tid, bytes)], tree_info, root_rt_pid)"""
    P = sr.by_pid(); next_pid = max(o[0] for o in sr.objects) + 1
    flat = []; roots = []
    for rn in spec_roots(spec):
        rec, next_pid = alloc_tree(rn, next_pid, flat); roots.append(rec)
    name2go = {}
    for rec in flat: name2go.setdefault(rec['node']['name'], []).append(rec['ids']['go'])
    append = {}
    tid_of = lambda pid: sr.objects[P[pid]][3]
    def mk(kind): return Obj(sr, trees, TREE_SRC[kind])
    def build(rec, father_rt):
        n = rec['node']; ids = rec['ids']
        comps = [ids['rt']] + ([ids['cr']] if 'cr' in ids else [])
        # children RTs (own children + the text's inlineImages transform)
        kid_rts = [c['ids']['rt'] for c in rec['children']] + ([ids['inl_tr']] if 'inl_tr' in ids else [])
        rt = mk('rt'); r = norm_rect(n.get('rect'))
        rt.set('m_GameObject.m_PathID', ids['go']); rt.set('m_Father.m_FileID', 0); rt.set('m_Father.m_PathID', father_rt)
        for pth, v in (('m_AnchorMin.x', r['anchor_min'][0]), ('m_AnchorMin.y', r['anchor_min'][1]), ('m_AnchorMax.x', r['anchor_max'][0]), ('m_AnchorMax.y', r['anchor_max'][1]),
                       ('m_AnchoredPosition.x', r['pos'][0]), ('m_AnchoredPosition.y', r['pos'][1]), ('m_SizeDelta.x', r['size'][0]), ('m_SizeDelta.y', r['size'][1]),
                       ('m_Pivot.x', r['pivot'][0]), ('m_Pivot.y', r['pivot'][1])): rt.set(pth, float(v))
        rb = bytearray(rt.b); ins = rt.off['m_Father.m_FileID'][0]
        struct.pack_into('<i', rb, rt.off['m_Children.Array.size'][0], len(kid_rts))
        rb[ins:ins] = b''.join(struct.pack('<iq', 0, k) for k in kid_rts)
        append[ids['rt']] = (tid_of(TREE_SRC['rt']), bytes(rb))
        if 'cr' in ids:
            cr = mk('cr'); cr.set('m_GameObject.m_PathID', ids['go']); append[ids['cr']] = (cr.tid, bytes(cr.b))
        if 'image' in n:
            im = n['image']; mb = mk('image'); mb.set('m_GameObject.m_PathID', ids['go'])
            for c, v in zip('rgba', im.get('color', [1, 1, 1, 1])): mb.set('m_Color.' + c, float(v))
            mb.set('m_RaycastTarget', 1 if im.get('raycast', False) else 0)
            if im.get('sprite'):
                bundle, spid, cab = resolve_sprite(im['sprite'], table, None); mb.set('m_Sprite.m_FileID', fid_for(cab)); mb.set('m_Sprite.m_PathID', spid)
            else: mb.set('m_Sprite.m_FileID', 0); mb.set('m_Sprite.m_PathID', 0)
            mb.set('m_PreserveAspect', 1 if im.get('preserve_aspect', True) else 0)
            comps.append(ids['image']); append[ids['image']] = (mb.tid, bytes(mb.b))
        if 'button' in n:
            B = n['button']; bt = mk('button'); bt.set('m_GameObject.m_PathID', ids['go']); bt.set('m_Enabled', 1)
            assert bt.off['m_OnClick.m_PersistentCalls.m_Calls.Array.size'][0] == BTN_FIXED
            bt.set('m_Transition', 1); bt.set('m_Navigation.m_Mode', 0); bt.set('m_Interactable', 1 if B.get('interactable', True) else 0)
            bt.set('m_TargetGraphic.m_FileID', 0); bt.set('m_TargetGraphic.m_PathID', ids['image'])
            cols = dict(BTN_COLORS); cols.update(B.get('colors', {}))
            for k_, f_ in BTN_COLOR_FIELDS:
                for c, v in zip('rgba', cols[k_]): bt.set('m_Colors.%s.%s' % (f_, c), float(v))
            bt.set('m_Colors.m_ColorMultiplier', float(cols['multiplier'])); bt.set('m_Colors.m_FadeDuration', float(cols['fade']))
            calls = B.get('calls', [])
            body = b''.join(call_bytes(name2go[c['target']][0], c['method'], c['bool']) for c in calls)
            comps.append(ids['button']); append[ids['button']] = (bt.tid, bytes(bt.b[:BTN_FIXED]) + struct.pack('<i', len(calls)) + body)
        if 'text' in n:
            tx = n['text']; st = mk('smarttext'); st.set('m_GameObject.m_PathID', ids['go'])
            for c, v in zip('rgba', tx.get('color', [0.929411768913269, 0.9215686321258545, 0.8549019694328308, 1.0])): st.set('m_Color.' + c, float(v))
            st.set('m_RaycastTarget', 0)
            st.set('m_fontData.m_fontSize', int(tx.get('size', 20))); st.set('m_fontData.m_alignment', _align(tx.get('align', 'MiddleLeft')))
            st.set('m_fontData.m_bestFit', 0)
            ov = tx.get('overflow', [0, 0]); st.set('m_fontData.m_horizontalOverflow', int(ov[0])); st.set('m_fontData.m_verticalOverflow', int(ov[1]))
            st.set_str('m_text', tx.get('placeholder', '')); st.set_str('m_fontData.m_globalFont', tx.get('font', 'Body-Bold'))
            lo = mk('localise'); lo.set('m_GameObject.m_PathID', ids['go']); lo.set_str('m_key', tx.get('key', '')); lo.set('m_capitalise', 0)
            comps += [ids['smarttext'], ids['localise']]
            append[ids['smarttext']] = (st.tid, bytes(st.b)); append[ids['localise']] = (lo.tid, bytes(lo.b))
        if 'layout' in n:
            L = n['layout']; kind = 'vlg' if L['type'] == 'vertical' else 'hlg'; mb = mk(kind); mb.set('m_GameObject.m_PathID', ids['go'])
            pad = L.get('padding', [0, 0, 0, 0])
            for k_, v in zip(('m_Left', 'm_Right', 'm_Top', 'm_Bottom'), pad): mb.set('m_Padding.' + k_, int(v))
            mb.set('m_ChildAlignment', _align(L.get('align', 'UpperLeft'))); mb.set('m_Spacing', float(L.get('spacing', 0)))
            fe = L.get('force_expand', [False, False]); ct = L.get('control', [False, False])
            mb.set('m_ChildForceExpandWidth', 1 if fe[0] else 0); mb.set('m_ChildForceExpandHeight', 1 if fe[1] else 0)
            mb.set('m_ChildControlWidth', 1 if ct[0] else 0); mb.set('m_ChildControlHeight', 1 if ct[1] else 0)
            mb.set('m_ChildScaleWidth', 0); mb.set('m_ChildScaleHeight', 0); mb.set('m_ReverseArrangement', 1 if L.get('reverse', False) else 0)
            comps.append(ids['layout']); append[ids['layout']] = (mb.tid, bytes(mb.b))
        if 'fitter' in n:
            F = n['fitter']; mb = mk('csf'); mb.set('m_GameObject.m_PathID', ids['go'])
            mb.set('m_HorizontalFit', FIT[F.get('h', 'unconstrained')]); mb.set('m_VerticalFit', FIT[F.get('v', 'unconstrained')])
            comps.append(ids['fitter']); append[ids['fitter']] = (mb.tid, bytes(mb.b))
        append[ids['go']] = (tid_of(TREE_SRC['inl_go']) if False else sr.objects[P[17]][3], make_go(comps, 0, n['name'], n.get('active', True)))
        if 'inl_go' in ids:
            tr = mk('inl_tr'); tr.set('m_GameObject.m_PathID', ids['inl_go']); tr.set('m_Father.m_PathID', ids['rt']); tr.set('m_Father.m_FileID', 0)
            cr = mk('inl_cr'); cr.set('m_GameObject.m_PathID', ids['inl_go'])
            append[ids['inl_tr']] = (tr.tid, bytes(tr.b)); append[ids['inl_cr']] = (cr.tid, bytes(cr.b))
            append[ids['inl_go']] = (sr.objects[P[17]][3], make_go([ids['inl_tr'], ids['inl_cr']], 0, 'inlineImages', True))
        for c in rec['children']: build(c, ids['rt'])
    for root in roots: build(root, PARENT_RT)
    app = [(pid, append[pid][0], append[pid][1]) for pid in sorted(append)]
    def info_of(rec):
        n = rec['node']
        return {'name': n['name'], 'ids': rec['ids'], 'children': [info_of(c) for c in rec['children']]}
    return app, [info_of(r) for r in roots], [r['ids']['rt'] for r in roots]

def plan_build_tree(src_bundle_path, spec):
    validate_spec(spec)
    sb = ufs.Bundle(src_bundle_path); orig = sb.node_data(SCENE)
    sr = S.Ser(orig); trees = [tt.build_tree(t) for t in sr.types]; P = sr.by_pid()
    for go, nm in TREE_SRC_NAMES.items(): assert Obj(sr, trees, go).val['m_Name'] == nm, 'clone source %d is not %s' % (go, nm)
    assert Obj(sr, trees, PARENT_GO).val['m_Name'] == PARENT_GO_NAME
    rt_par = Obj(sr, trees, PARENT_RT); assert rt_par.val['m_GameObject.m_PathID'] == PARENT_GO
    table = json.load(open(os.path.join(HERE, 'panel_sprites.json'), encoding='utf8'))
    ext_paths = [e['path'] for e in sr.externals]; new_ext = []
    def fid_for(cab):
        path = 'archive:/%s/%s' % (cab, cab)
        if path in ext_paths: return ext_paths.index(path) + 1
        if path not in new_ext: new_ext.append(path)
        return len(ext_paths) + new_ext.index(path) + 1
    append, tinfos, root_rts = build_tree_objects(sr, trees, spec, table, fid_for)
    n_old = rt_par.val['m_Children.Array.size']; ins = rt_par.off['m_Father.m_FileID'][0]; a0 = rt_par.off['m_Children.Array.size'][0]
    assert ins == a0 + 4 + 12 * n_old
    old_kids = [rt_par.val['m_Children.Array[%d].m_PathID' % j] for j in range(n_old)]
    inserts = [r.get('insert', 'back') for r in spec_roots(spec)]
    new_kids = place_children(old_kids, root_rts, inserts)
    pb = bytearray(rt_par.b); pb[a0:ins] = struct.pack('<i', len(new_kids)) + b''.join(struct.pack('<iq', 0, k) for k in new_kids)
    new_ser = ser_edit.rebuild(orig, replace={PARENT_RT: bytes(pb)}, append=append, new_externals=new_ext)
    info = {'format': 'tree', 'tree': tinfos[-1], 'trees': tinfos, 'new_externals': new_ext, 'parent_rect': PARENT_RT, 'parent_children_before': n_old,
            'objects_before': len(sr.objects), 'objects_after': len(sr.objects) + len(append), 'new_pids': [a[0] for a in append], 'root_rect': root_rts[-1], 'root_rects': root_rts,
            'root_inserts': inserts, 'parent_children_after': new_kids, 'slots': []}
    return sb, orig, new_ser, info

def print_tree(t, depth=0):
    print('  ' * (depth + 1) + '%-20s GO %d RT %d  %s' % (t['name'], t['ids']['go'], t['ids']['rt'], ' '.join('%s=%d' % (k, v) for k, v in t['ids'].items() if k not in ('go', 'rt'))))
    for c in t['children']: print_tree(c, depth + 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['plan', 'build']); ap.add_argument('--src', required=True); ap.add_argument('--spec', required=True)
    ap.add_argument('--out'); ap.add_argument('--mode', default='rebuild', choices=['rebuild', 'append'])
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding='utf8'))
    sb, orig, new_ser, info = plan_build(a.src, spec)
    print('source bundle  :', a.src, '(%d bytes, sha256 %s)' % (len(sb.raw), hashlib.sha256(sb.raw).hexdigest()[:16]))
    print('scene file     : %s  %d -> %d bytes' % (SCENE, len(orig), len(new_ser)))
    print('objects        : %d -> %d ; MapHud children %d -> %d' % (info['objects_before'], info['objects_after'], info['parent_children_before'], info['parent_children_before'] + (len(info['root_rects']) if info.get('format') == 'tree' else len(info['slots']))))
    print('new externals  :', info['new_externals'] or '(none)')
    if info.get('format') == 'tree':
        print('tree (new objects %d, %d root(s) placed in MapHud at %s):' % (len(info['new_pids']), len(info['root_rects']), info['root_inserts']))
        for t_ in info['trees']: print_tree(t_)
    for s_ in info['slots']: print('  slot %-16s GO %d RT %d CR %d IMG %d  sprite %s -> fileID %d pathID %d (%s)' % (s_['name'], s_['go'], s_['rect'], s_['canvasRenderer'], s_['image'], s_['sprite'], s_['spriteFileID'], s_['spritePathID'], s_['bundle']))
    if a.cmd == 'plan': print('(plan only, nothing written)'); return 0
    if not a.out: ap.error('--out required for build')
    if in_game_folder(a.out): print('REFUSED: --out is inside the game folder'); return 2
    os.makedirs(a.out, exist_ok=True)
    out = ufs.write_bundle(sb, SCENE, new_ser, a.mode)
    op = os.path.join(a.out, os.path.basename(a.src) if not a.src.endswith('.orig') else 'ui_screens')
    if os.path.abspath(op) == os.path.abspath(a.src): print('REFUSED: output would overwrite the source'); return 2
    open(op, 'wb').write(out)
    info.update({'out': op, 'mode': a.mode, 'sha256': hashlib.sha256(out).hexdigest(), 'src_sha256': hashlib.sha256(sb.raw).hexdigest(), 'size': len(out)})
    json.dump(info, open(op + '.build.json', 'w', encoding='utf8'), indent=1, ensure_ascii=False)
    print('wrote %s (%d bytes) sha256 %s' % (op, len(out), info['sha256']))
    return 0

if __name__ == '__main__': sys.exit(main())
