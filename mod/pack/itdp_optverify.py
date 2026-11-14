#!/usr/bin/env python
"""verify_options_toggle.py - independent verifier of a built data_user_settings. Reads only.
  python -I -X utf8 verify_options_toggle.py --orig <source> --new <built> --info <built>.build.json
Checks: container (blocks-info at the end, same header fields, valid blocks), serialized file (object table, byte-identical objects except the 2 replaced), UnityPy re-read of EVERY object (type trees incl. managed references)
and comparison with the source objects, the new provider field by field against its template, the registry (rids unique, default = LABEL_OFF/value 0), the collection list, the key group."""
import sys, os, json, struct, argparse
HERE = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import itdp_ufs2 as ufs2, itdp_ser as S, itdp_tt as tt
import UnityPy
from UnityPy.helpers.TypeTreeNode import TypeTreeNode
if not getattr(TypeTreeNode, '_itd_patched', False):
    _o = TypeTreeNode.parse_blob.__func__
    def _pb(cls, reader, version): reader.read(28); return _o(cls, reader, version)
    TypeTreeNode.parse_blob = classmethod(_pb); TypeTreeNode._itd_patched = True
def unity_objs(path):
    env = UnityPy.load(path); out = {}
    for o in env.objects:
        try: out[o.path_id] = o.read_typetree()
        except Exception as e: out[o.path_id] = ('ERR', str(e)[:60])
    return out
def verify(src, new, info, ub_src=None, ub_new=None):
    R = []; ck = lambda n, ok, note='': R.append((n, bool(ok), note))
    a = ufs2.Bundle2(src); b = ufs2.Bundle2(new)
    ck('B1 container: blocks-info at the END like the source, same flags/version/engine, 1 node with the same name', b.at_end == a.at_end == True and b.flags == a.flags and b.version == a.version and b.engine == a.engine and [n[3] for n in a.nodes] == [n[3] for n in b.nodes])
    ck('B2 every block decompresses to its declared size, stream = node', all(len(b.dec_block(i)) == b.blocks[i][0] for i in range(len(b.blocks))) and len(b.decompress()) == b.nodes[0][1] and b.size == len(b.raw))
    sa = S.Ser(a.node_data(a.nodes[0][3])); sb = S.Ser(b.node_data(b.nodes[0][3])); Pa, Pb = sa.by_pid(), sb.by_pid(); newp = info['new_pid']; repl = set(info['replaced'])
    ck('S1 object count +1, all source pids present, the new pid is new', len(sb.objects) == len(sa.objects) + 1 and all(p in Pb for p in Pa) and newp in Pb and newp not in Pa)
    chg = {p for p in Pa if sa.object_bytes(Pa[p]) != sb.object_bytes(Pb[p])}
    ck('S1b only the replaced objects differ from the source (changed: %s)' % sorted(chg), chg == repl)
    ck('S1c types/externals/reference types tables identical', [t.nodes_raw for t in sa.types] == [t.nodes_raw for t in sb.types] and [e['path'] for e in sa.externals] == [e['path'] for e in sb.externals] and [t.nodes_raw for t in sa.reftypes] == [t.nodes_raw for t in sb.reftypes])
    ua = ub_src or unity_objs(src); ub = ub_new or unity_objs(new)
    ck('U1 UnityPy re-reads ALL %d objects of the new bundle (managed references included)' % len(ub), len(ub) == len(ua) + 1 and not [p for p, v in ub.items() if isinstance(v, tuple)] and not [p for p, v in ua.items() if isinstance(v, tuple)])
    same = [p for p in ua if p not in repl and ua[p] == ub.get(p)]
    ck('U2 UnityPy type trees of all %d untouched objects equal the source' % (len(ua) - len(repl)), len(same) == len(ua) - len(repl))
    t = ua[info['template_pid']]; n = ub[newp]; fld = {k for k in t if t[k] != n.get(k)}
    ck('U3 new provider differs from its template only in %s' % sorted(fld), fld <= {'m_Name', 'm_settingKey', 'm_nameKey', 'm_descriptionKey', 'm_defaultSetting', 'm_settingOptions', 'references'} and set(t) == set(n))
    ck('U3b names/keys: m_Name=%s, key=%s, nameKey=%s, descKey=%s, category=accessibility' % (info['m_name'], info['key'], info['name_key'], info['desc_key']), n['m_Name'] == info['m_name'] and n['m_settingKey'] == info['key'] and n['m_nameKey'] == info['name_key'] and n['m_descriptionKey'] == info['desc_key'] and n['m_category'] == 'accessibility')
    refs = {r['rid']: r for r in n['references']['RefIds']}; opts = [x['rid'] for x in n['m_settingOptions']]; dflt = n['m_defaultSetting']['rid']
    ok = len(refs) == 2 and set(opts) == set(refs) and dflt in refs and len(opts) == 2
    if ok:
        off = [r for r in refs.values() if r['data']['m_localisedKey'] == 'LABEL_OFF'][0]; on = [r for r in refs.values() if r['data']['m_localisedKey'] == 'LABEL_ON'][0]
        ok = off['data']['m_value']['m_value'] == 0 and on['data']['m_value']['m_value'] == 1 and dflt == off['rid'] and all(r['type']['class'].startswith('SettingValueOption`1[[System.Boolean') for r in refs.values())
    ck('U4 registry: 2 unique rids = the 2 options (LABEL_OFF value 0, LABEL_ON value 1, bool type), m_defaultSetting = the OFF option', ok)
    ck('U4b the template provider (AllowSuicide) is untouched, rids differ from the new ones', ub[info['template_pid']] == ua[info['template_pid']] and not ({info['new_off_rid'], info['new_on_rid']} & {r['rid'] for r in ua[info['template_pid']]['references']['RefIds']}))
    co, cn = ua[info['collection_pid']], ub[info['collection_pid']]; pa = co['m_platformOptionCollectionGroups'][0]['SettingProviders']; pn = cn['m_platformOptionCollectionGroups'][0]['SettingProviders']
    ck('C1 collection SettingProviders = source list with the new provider inserted at index %d; every entry points at an existing object; nothing else changed' % info['position'], pn == pa[:info['position']] + [{'m_FileID': 0, 'm_PathID': newp}] + pa[info['position']:] and all(x['m_FileID'] == 0 and x['m_PathID'] in ub for x in pn)
       and {k: v for k, v in cn.items() if k != 'm_platformOptionCollectionGroups'} == {k: v for k, v in co.items() if k != 'm_platformOptionCollectionGroups'} and {k: v for k, v in cn['m_platformOptionCollectionGroups'][0].items() if k != 'SettingProviders'} == {k: v for k, v in co['m_platformOptionCollectionGroups'][0].items() if k != 'SettingProviders'})
    if info['keygroup']:
        ko, kn = ua[info['keygroup_pid']], ub[info['keygroup_pid']]; suffix = info['key'][len(ko['m_prefix']) + 1:]
        ck('K1 key group m_settingIDs = source + [%s] (prefix %s), nothing else changed' % (suffix, ko['m_prefix']), kn['m_settingIDs'] == ko['m_settingIDs'] + [suffix] and {k: v for k, v in kn.items() if k != 'm_settingIDs'} == {k: v for k, v in ko.items() if k != 'm_settingIDs'})
    else: ck('K1 key group untouched (--no-keygroup)', info['keygroup_pid'] is None and info['keygroup_pid'] not in repl)
    keys = [v['m_settingKey'] for v in ub.values() if isinstance(v, dict) and 'm_settingKey' in v]
    ck('X1 the new setting key is unique among all %d settings' % len(keys), keys.count(info['key']) == 1)
    return R
def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('--orig', required=True); ap.add_argument('--new', required=True); ap.add_argument('--info', required=True); a = ap.parse_args(argv)
    R = verify(a.orig, a.new, json.load(open(a.info)))
    for n, ok, note in R: print(('PASS ' if ok else 'FAIL ') + n + ('' if ok or not note else '  -> ' + note))
    nf = sum(1 for r in R if not r[1]); print('%d checks, %d failed' % (len(R), nf)); return 1 if nf else 0
if __name__ == '__main__': sys.exit(main())
