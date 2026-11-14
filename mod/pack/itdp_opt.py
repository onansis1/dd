#!/usr/bin/env python
"""itd_options_toggle.py - COPY-ONLY tool: adds ONE boolean setting (default OFF) to the game's options (data_user_settings bundle).
  python -I -X utf8 itd_options_toggle.py plan  --src <data_user_settings copy> [--key drs.accessibility.quiet_footsteps] [--name-key LABEL_VITALS] [--desc-key LABEL_DEMO_TITLE]
  python -I -X utf8 itd_options_toggle.py build --src <data_user_settings copy> --out <dir> [...] [--position end|<index>] [--no-keygroup]
What it does (3 objects of the serialized file; the UnityFS container is read/written by ufs2.py, blocks-info-at-end layout supported):
  1. NEW object: a byte-level clone of the provider ContentControlAllowSuicideSettingOptionsProvider (AdjustableBoolSettingOptionsProvider) with new m_Name / m_settingKey / m_nameKey / m_descriptionKey,
     new rids for its two SettingValueOption<bool> managed references (LABEL_OFF = 0, LABEL_ON = 1) and m_defaultSetting = the OFF option;
  2. GeneralAccessibilitySettingsOptionsCollection.SettingProviders += new provider (at the end or at --position);
  3. AccessibilitySettingKeyGroup.m_settingIDs += <key suffix> (the group lists the ids of its collection; skip with --no-keygroup).
No scene object is created: the options screen builds every row from the provider list with the same prefab as the other rows. Never writes into the game folder (refused)."""
import sys, os, json, struct, hashlib, argparse
HERE = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import itdp_ufs2 as ufs2, itdp_ser as S, itdp_tt as tt, itdp_edit as ser_edit
GAME_MARK = os.path.normcase(r'steamapps\common\into the dead our darkest days')
TEMPLATE = dict(pid=1160308168920237736, name='ContentControlAllowSuicideSettingOptionsProvider', key='drs.accessibility.allow_suicide', off_rid=8415198295467753715, on_rid=8415198295467753716)
COLLECTION = dict(pid=2621438742948663674, name='GeneralAccessibilitySettingsOptionsCollection'); KEYGROUP = dict(pid=4223283978059422009, name='AccessibilitySettingKeyGroup', prefix='drs.accessibility')
NEW_OFF, NEW_ON = 8415198295467760001, 8415198295467760002

def _s(x): b = x.encode('utf8'); return struct.pack('<i', len(b)) + b + b'\0' * ((-len(b)) % 4)
class Ctx:
    def __init__(self, path):
        self.b = ufs2.Bundle2(path); self.node = self.b.nodes[0][3]; self.orig = self.b.node_data(self.node); self.s = S.Ser(self.orig); self.trees = [tt.build_tree(t) for t in self.s.types]; self.P = self.s.by_pid()
    def raw(self, pid): return bytes(self.s.object_bytes(self.P[pid]))
    def tid(self, pid): return self.s.objects[self.P[pid]][3]
    def prefix(self, pid, stop='references'):
        ob = self.raw(pid); root = self.trees[self.tid(pid)]; w = tt.Walker(ob, 0, len(ob))
        for c in root.children:
            if c.name == stop: break
            w.read(c, c.name)
        return ob, w
    def name(self, pid):
        ob = self.raw(pid); root = self.trees[self.tid(pid)]; w = tt.Walker(ob, 0, len(ob))
        for c in root.children[:4]: w.read(c, c.name)
        return dict((p, v) for p, o, t, v in w.leaves).get('m_Name')
    def full(self, pid):
        i = self.P[pid]; lv = tt.parse_object(self.s, i, self.trees); return {p: (o, t, v) for p, o, t, v in lv}

def new_provider_bytes(c, key, name_key, desc_key, mname):
    ob, w = c.prefix(TEMPLATE['pid']); lv = {p: (o, t, v) for p, o, t, v in w.leaves}
    assert lv['m_Name'][2] == TEMPLATE['name'] and lv['m_settingKey'][2] == TEMPLATE['key'], 'template provider differs from the expected one'
    assert lv['m_settingOptions.Array.size'][2] == 2 and lv['m_settingOptions.Array[0].rid'][2] == TEMPLATE['off_rid'] and lv['m_settingOptions.Array[1].rid'][2] == TEMPLATE['on_rid']
    head = ob[:28]; tail = bytearray(ob[lv['m_usageConditions.Array.size'][0]:])
    assert tail.count(struct.pack('<q', TEMPLATE['off_rid'])) == 2 and tail.count(struct.pack('<q', TEMPLATE['on_rid'])) == 3, (tail.count(struct.pack('<q', TEMPLATE['off_rid'])), tail.count(struct.pack('<q', TEMPLATE['on_rid'])))
    tail = bytes(tail).replace(struct.pack('<q', TEMPLATE['off_rid']), struct.pack('<q', NEW_OFF)).replace(struct.pack('<q', TEMPLATE['on_rid']), struct.pack('<q', NEW_ON))
    tail = bytearray(tail); struct.pack_into('<q', tail, 196 - 180, NEW_OFF)          # m_defaultSetting = the OFF option (value 0)
    return head + _s(mname) + _s(key) + _s(name_key) + _s(desc_key) + _s('accessibility') + bytes(tail)

def plan_build(src, key='drs.accessibility.quiet_footsteps', name_key='LABEL_VITALS', desc_key='LABEL_DEMO_TITLE', position='end', keygroup=True, mname=None):
    c = Ctx(src); mname = mname or 'QuietFootstepsSettingOptionsProvider'
    assert c.name(COLLECTION['pid']) == COLLECTION['name'] and c.name(KEYGROUP['pid']) == KEYGROUP['name']
    assert key.startswith(KEYGROUP['prefix'] + '.'), 'key must start with %s.' % KEYGROUP['prefix']
    for p in c.P:
        if c.tid(p) == c.tid(TEMPLATE['pid']):
            ob, w = c.prefix(p); d = dict((q, v) for q, o, t, v in w.leaves)
            assert d.get('m_settingKey') != key and d.get('m_Name') != mname, 'the setting already exists (refusing to add it twice)'
    newpid = max(c.P) + 1; nb = new_provider_bytes(c, key, name_key, desc_key, mname); tt.parse_bytes(c.trees[c.tid(TEMPLATE['pid'])], nb) if False else None
    # ---- collection: SettingProviders += new
    cf = c.full(COLLECTION['pid']); ob = bytearray(c.raw(COLLECTION['pid']))
    sk = 'm_platformOptionCollectionGroups.Array[0].SettingProviders.Array.size'; a0 = cf[sk][0]; n = cf[sk][2]; assert cf['m_platformOptionCollectionGroups.Array.size'][2] == 1 and n == 2
    idx = n if position == 'end' else int(position); assert 0 <= idx <= n
    ob[a0 + 4 + 12 * idx:a0 + 4 + 12 * idx] = struct.pack('<iq', 0, newpid); struct.pack_into('<i', ob, a0, n + 1)
    # ---- key group: m_settingIDs += suffix
    kf = c.full(KEYGROUP['pid']); kb = bytearray(c.raw(KEYGROUP['pid'])); replace = {COLLECTION['pid']: bytes(ob)}
    if keygroup:
        ka = kf['m_settingIDs.Array.size'][0]; kn = kf['m_settingIDs.Array.size'][2]; end = kf['m_categories.Array.size'][0]
        suffix = key[len(KEYGROUP['prefix']) + 1:]; kb[end:end] = _s(suffix); struct.pack_into('<i', kb, ka, kn + 1); replace[KEYGROUP['pid']] = bytes(kb)
    # ---- AssetBundle 객체: 새 제공자를 '미리 불러오기 목록'에 넣는다 (목록에 없으면 게임이 이 PPtr 을 null 로 읽어 옵션 초기화에서 NullReferenceException 이 난다)
    abp = next(p for p in c.P if any(ch.name == 'm_PreloadTable' for ch in c.trees[c.tid(p)].children)); af = c.full(abp); ab = bytearray(c.raw(abp))
    so = af['m_PreloadTable.Array.size'][0]; npre = af['m_PreloadTable.Array.size'][2]; ncon = af['m_Container.Array.size'][2]
    def _ent(i): return bytes(ab[so + 4 + 12 * i: so + 16 + 12 * i])
    def _con(pid):
        r = [i for i in range(ncon) if af['m_Container.Array[%d].second.asset.m_PathID' % i][2] == pid]; assert len(r) == 1, 'container entry of %d not unique' % pid; return r[0]
    ci = _con(COLLECTION['pid']); ti = _con(TEMPLATE['pid'])
    cidx, csz = af['m_Container.Array[%d].second.preloadIndex' % ci][2], af['m_Container.Array[%d].second.preloadSize' % ci][2]
    tidx, tsz = af['m_Container.Array[%d].second.preloadIndex' % ti][2], af['m_Container.Array[%d].second.preloadSize' % ti][2]
    tmpl_ent = struct.pack('<iq', 0, TEMPLATE['pid']); script_ents = [_ent(j) for j in range(tidx, tidx + tsz) if _ent(j) != tmpl_ent]
    assert cidx + csz <= npre and tidx + tsz <= npre and len(script_ents) == 1 and tmpl_ent in [_ent(j) for j in range(tidx, tidx + tsz)], 'preload slices differ from the expected layout'
    add = b''.join(_ent(j) for j in range(cidx, cidx + csz)) + struct.pack('<iq', 0, newpid) + script_ents[0]; nadd = csz + 2
    struct.pack_into('<i', ab, af['m_Container.Array[%d].second.preloadIndex' % ci][0], npre); struct.pack_into('<i', ab, af['m_Container.Array[%d].second.preloadSize' % ci][0], nadd)
    struct.pack_into('<i', ab, so, npre + nadd); ab[so + 4 + 12 * npre: so + 4 + 12 * npre] = add; replace[abp] = bytes(ab)
    new_ser = ser_edit.rebuild(c.orig, replace=replace, append=[(newpid, c.tid(TEMPLATE['pid']), nb)])
    info = dict(src_objects=len(c.s.objects), new_objects=len(c.s.objects) + 1, new_pid=newpid, template_pid=TEMPLATE['pid'], collection_pid=COLLECTION['pid'], keygroup_pid=KEYGROUP['pid'] if keygroup else None, key=key, name_key=name_key, desc_key=desc_key,
                m_name=mname, position=idx, new_off_rid=NEW_OFF, assetbundle_pid=abp, preload_old=npre, preload_slice=[npre, nadd], collection_old_slice=[cidx, csz], new_on_rid=NEW_ON, replaced=sorted(replace), keygroup=keygroup, scene_bytes=len(c.orig), new_scene_bytes=len(new_ser))
    return c, new_ser, info

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); ap.add_argument('cmd', choices=['plan', 'build']); ap.add_argument('--src', required=True); ap.add_argument('--out')
    ap.add_argument('--key', default='drs.accessibility.quiet_footsteps'); ap.add_argument('--name-key', default='LABEL_VITALS'); ap.add_argument('--desc-key', default='LABEL_DEMO_TITLE'); ap.add_argument('--position', default='end'); ap.add_argument('--no-keygroup', action='store_true')
    a = ap.parse_args(argv); c, new_ser, info = plan_build(a.src, a.key, a.name_key, a.desc_key, a.position, not a.no_keygroup)
    print('source %s (%d bytes, sha256 %s) layout: blocks-info %s, flags 0x%x' % (a.src, len(c.b.raw), hashlib.sha256(c.b.raw).hexdigest()[:16], 'at the END' if c.b.at_end else 'after the header', c.b.flags))
    print('serialized file %d -> %d bytes; objects %d -> %d; new provider pid %d key %s (name key %s, description key %s); collection index %d; key group updated: %s' % (info['scene_bytes'], info['new_scene_bytes'], info['src_objects'], info['new_objects'], info['new_pid'], info['key'], info['name_key'], info['desc_key'], info['position'], info['keygroup']))
    if a.cmd == 'plan': print('(plan only, nothing written)'); return 0
    if not a.out: ap.error('--out required')
    if GAME_MARK in os.path.normcase(os.path.abspath(a.out)): print('REFUSED: --out is inside the game folder'); return 2
    os.makedirs(a.out, exist_ok=True); op = os.path.join(a.out, 'data_user_settings')
    if os.path.abspath(op) == os.path.abspath(a.src): print('REFUSED: output would overwrite the source'); return 2
    out = c.b.build(c.node, new_ser); open(op, 'wb').write(out); info.update(out=op, sha256=hashlib.sha256(out).hexdigest(), src_sha256=hashlib.sha256(c.b.raw).hexdigest(), size=len(out))
    json.dump(info, open(op + '.build.json', 'w'), indent=1); print('wrote %s (%d bytes) sha256 %s' % (op, len(out), info['sha256'])); return 0
if __name__ == '__main__': sys.exit(main())
