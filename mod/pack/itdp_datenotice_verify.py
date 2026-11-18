#!/usr/bin/env python
"""itdp_datenotice_verify.py - 날짜 안내 문구 패치(ui_screens + data_config)의 결과 번들 검증기. 하나라도 FAIL 이면 종료 코드 1.
  python itdp_datenotice_verify.py --orig-ui <원본 ui_screens> --new-ui <새 ui_screens> --ui-info <build.json> --orig-cfg <원본 data_config> --new-cfg <새 data_config> --cfg-info <build.json> [--full]
검사 (구조 검사는 모두 저수준 파서, 마지막에 UnityPy 로 독립 재파싱):
 번들: 노드 목록 동일, 목표 노드만 다름(나머지 노드는 압축 해제 바이트까지 동일), 전체 크기/블록 정합.
 장면: 객체 수/타입/스크립트/외부 파일 증가량, 기존 객체 중 바뀐 것은 Panel RectTransform 뿐, 새 객체 전부 타입 트리로 정확히 파싱, PPtr 유효성(로컬/외부/클래스), 계층(부모-자식/GameObject-컴포넌트 쌍방 참조),
       새 타입 항목 = 지도 화면의 같은 타입 항목(script_index 만 다름), 조건 PPtr 이 가리키는 data_config 객체의 클래스.
 data_config: 객체 +1, 바뀐 기존 객체는 등록부 뿐, 새 객체 파싱, 등록부 끝 항목 = (0, 새 pid), 이름 중복 없음.
 UnityPy: 두 번들 전체 로드 + 객체 열거, 장면/데이터 객체 타입트리 읽기."""
import sys, os, json, struct, argparse, hashlib, collections
HERE = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
_D = os.path.join(HERE, '..', 'deps')                         # 패키지 레이아웃(tools/ 옆의 deps/)이면 앱 itdp_* 스냅샷을 쓴다. 앱 폴더에 넣어 쓸 때는 필요 없음
if os.path.isdir(_D) and _D not in sys.path:
    sys.path.insert(0, _D)

import itdp_ufs as ufs, itdp_ser as S, itdp_tt as tt
from itdp_build import Obj
from itdp_scn import pptr_leaves, class_of, CLS

SCENE = 'BuildPlayer-NewCycleCard'; MAP_SCENE = 'BuildPlayer-MapScreen'


def _patch_unitypy():
    """UnityPy 가 이 게임 번들(타입 트리 28바이트 확장)을 읽도록 parse_blob 을 한 번만 감싼다 (두 번 감싸면 읽기가 깨진다)"""
    from UnityPy.helpers.TypeTreeNode import TypeTreeNode
    if getattr(TypeTreeNode, '_itd_patched', False): return
    o_ = TypeTreeNode.parse_blob.__func__
    def pb(cls, reader, version): reader.read(28); return o_(cls, reader, version)
    TypeTreeNode.parse_blob = classmethod(pb); TypeTreeNode._itd_patched = True


class Rep:
    def __init__(self): self.rows = []
    def add(self, name, ok, note=''): self.rows.append((name, bool(ok), note))
    def fails(self): return [r for r in self.rows if not r[1]]
    def dump(self):
        for n, ok, note in self.rows: print(('OK   ' if ok else 'FAIL ') + n + (('  -> ' + str(note)) if note else ''))
        print('%d checks, %d FAIL' % (len(self.rows), len(self.fails())))


def _nodes_equal(o, n, target, R, label):
    R.add('%s: 노드 목록(이름/순서)이 같다' % label, [x[3] for x in o.nodes] == [x[3] for x in n.nodes])
    diff = []; od = o.decompress(); nd = n.decompress()
    for (oo, os_, of, on), (no, ns, nf, nn) in zip(o.nodes, n.nodes):
        if on == nn and (od[oo:oo + os_] != nd[no:no + ns]): diff.append(on)
    R.add('%s: 바뀐 노드는 %s 하나뿐' % (label, target), diff == [target], diff)
    R.add('%s: 번들 크기 필드 = 실제 파일 크기, 블록 합 = 압축 해제 크기' % label, n.size == len(n.raw) and sum(b[0] for b in n.blocks) == sum(x[1] for x in n.nodes))


def _py_scripts(env):
    scr = {}
    for ob in env.objects:
        if ob.type.name == 'MonoScript':
            t = ob.read_typetree(); scr[(ob.assets_file.name, ob.path_id)] = t['m_ClassName']
    return scr


def verify_ui(orig_ui, new_ui, info, orig_cfg=None, new_cfg=None, full=True, R=None):
    R = R or Rep()
    ob = ufs.Bundle(orig_ui); nb = ufs.Bundle(new_ui)
    _nodes_equal(ob, nb, SCENE, R, 'ui_screens')
    o = ob.node_data(SCENE); n = nb.node_data(SCENE)
    R.add('ui_screens: 원본 장면 SHA-256 이 빌드 기록과 같다', hashlib.sha256(o).hexdigest() == info['src_scene_sha256'])
    R.add('ui_screens: 새 장면 SHA-256 이 빌드 기록과 같다', hashlib.sha256(n).hexdigest() == info['new_scene_sha256'])
    so = S.Ser(o); sn = S.Ser(n)
    to = [tt.build_tree(t) for t in so.types]; tn = [tt.build_tree(t) for t in sn.types]
    R.add('장면: 객체 수 %d -> %d (+%d)' % (len(so.objects), len(sn.objects), len(info['new_pids'])), len(sn.objects) == len(so.objects) + len(info['new_pids']) == info['objects_after'])
    R.add('장면: 타입 +1, 스크립트 +1, 외부 파일 +%d' % len(info['new_externals']), len(sn.types) == len(so.types) + 1 and len(sn.scripts) == len(so.scripts) + 1 and len(sn.externals) == len(so.externals) + len(info['new_externals']))
    R.add('장면: 기존 타입 항목은 바이트 그대로', all(o[a.start:a.end] == n[b.start:b.end] for a, b in zip(so.types, sn.types)))
    R.add('장면: 기존 스크립트 표/외부 표 항목 그대로', sn.scripts[:len(so.scripts)] == so.scripts and [e['path'] for e in sn.externals[:len(so.externals)]] == [e['path'] for e in so.externals])
    # ---- 객체 비교
    Po = so.by_pid(); Pn = sn.by_pid(); changed = []; typechg = []
    for pid, i in Po.items():
        if pid not in Pn: changed.append(('missing', pid)); continue
        if so.object_bytes(i) != sn.object_bytes(Pn[pid]): changed.append(pid)
        if so.objects[i][3] != sn.objects[Pn[pid]][3]: typechg.append(pid)
    R.add('장면: 기존 객체 중 바뀐 것 = %s 뿐 (타입 번호 변경 없음)' % info['replaced'], sorted(changed) == sorted(info['replaced']) and not typechg, changed)
    R.add('장면: 새 객체 pid = 계획과 같고 중복 없음', sorted(set(Pn) - set(Po)) == sorted(info['new_pids']))
    # ---- 새 타입 항목
    mb = ob.node_data(MAP_SCENE); sm = S.Ser(mb)
    mt = sm.types[info['type_entry_source']['type_id']]; nt = sn.types[-1]
    mbytes = bytearray(mb[mt.start:mt.end]); struct.pack_into('<h', mbytes, 5, info['new_script_index'])
    R.add('타입: 새 타입 항목 = 지도 화면의 ConditionalActiveGameObjects 항목(script_index 만 %d)' % info['new_script_index'], bytes(mbytes) == n[nt.start:nt.end] and nt.class_id == 114 and nt.script_index == info['new_script_index'])
    R.add('스크립트 표: 마지막 = %s' % info['new_scripts'], [list(x) for x in sn.scripts[-1:]] == info['new_scripts'])
    ext_ok = (not info['new_externals']) or sn.externals[-1]['path'] == info['new_externals'][-1]
    R.add('외부 표: 새 항목 = BuildPlayer-MapScreen.sharedAssets', ext_ok and sn.externals[info['map_sharedassets_fid'] - 1]['path'].endswith('BuildPlayer-MapScreen.sharedAssets'), sn.externals[info['map_sharedassets_fid'] - 1]['path'])
    R.add('외부 표: %d번 = data_config CAB' % info['cfg_fid'], sn.externals[info['cfg_fid'] - 1]['path'].endswith('CAB-e04823e81dec6fc2099bf567eba2f429'))
    # ---- 새 객체 파싱 + PPtr 유효성
    objs = {p: Obj(sn, tn, p) for p in info['new_pids'] + info['replaced']}
    pars_ok = True
    for p in list(objs):
        try: tt.parse_object(sn, Pn[p], tn)
        except Exception as e: pars_ok = False; R.add('파싱 pid %d' % p, False, repr(e))
    R.add('새/교체 객체 %d개 전부 타입 트리로 정확히 파싱 (길이 일치)' % len(objs), pars_ok)
    bad = []
    for p, ob_ in objs.items():
        for path, off, val, fid in pptr_leaves(ob_):
            if val == 0 and fid == 0: continue
            if fid == 0:
                if val not in Pn: bad.append((p, path, val))
            elif fid > len(sn.externals): bad.append((p, path, 'fid', fid))
    R.add('PPtr: 로컬 PPtr 은 모두 장면에 존재, 외부 번호는 외부 표 범위 안', not bad, bad[:5])
    ng = Obj(sn, tn, info['notice_go']); cg = Obj(sn, tn, info['cond_go']); nrt = Obj(sn, tn, info['notice_rt']); crt = Obj(sn, tn, info['cond_rt']); cmb = Obj(sn, tn, info['cond_mb']); prt = Obj(sn, tn, info['panel_rt'])
    R.add('GameObject DateNotice: 이름/비활성(m_IsActive=0)', ng.val['m_Name'] == 'DateNotice' and ng.val['m_IsActive'] == 0, (ng.val['m_Name'], ng.val['m_IsActive']))
    R.add('GameObject DateNoticeCondition: 활성(켜짐)', cg.val['m_Name'] == 'DateNoticeCondition' and cg.val['m_IsActive'] == 1)
    comps = lambda g: [g.val['m_Component.Array[%d].component.m_PathID' % i] for i in range(g.val['m_Component.Array.size'])]
    R.add('조건 GO 컴포넌트 = [RectTransform, ConditionalActiveGameObjects]', comps(cg) == [info['cond_rt'], info['cond_mb']] and class_of(sn, info['cond_rt']) == 224 and class_of(sn, info['cond_mb']) == 114)
    R.add('컴포넌트 -> GameObject 되돌림 참조 (조건 RT/MB, 새 RT)', crt.val['m_GameObject.m_PathID'] == info['cond_go'] and cmb.val['m_GameObject.m_PathID'] == info['cond_go'] and nrt.val['m_GameObject.m_PathID'] == info['notice_go'])
    back = all(Obj(sn, tn, c).val['m_GameObject.m_PathID'] == info['notice_go'] for c in comps(ng))
    R.add('DateNotice GO 의 컴포넌트 %s 가 모두 이 GO 를 가리킨다' % comps(ng), back)
    kids = [prt.val['m_Children.Array[%d].m_PathID' % i] for i in range(prt.val['m_Children.Array.size'])]
    R.add('Panel RT 자식: 기존 %d개 순서 유지 + 새 RT 2개 덧붙임' % info['panel_children_before'], prt.val['m_Children.Array.size'] == info['panel_children_before'] + 2 and kids[-2:] == [info['notice_rt'], info['cond_rt']] and kids[:5] == [31, 36, 33, 34, 35], kids)
    R.add('새 RT 의 부모 = Panel RT', nrt.val['m_Father.m_PathID'] == info['panel_rt'] and crt.val['m_Father.m_PathID'] == info['panel_rt'])
    inl = [p for p in info['new_pids'] if class_of(sn, p) == 4]
    R.add('복제본 inlineImages Transform 의 부모 = 새 RT, 새 RT 의 자식 = 그 Transform', len(inl) == 1 and Obj(sn, tn, inl[0]).val['m_Father.m_PathID'] == info['notice_rt'] and nrt.val['m_Children.Array[0].m_PathID'] == inl[0])
    # 복제본이 원본(Date)과 안 섞였는지: 원본 Date 트리 객체는 변하지 않음 (changed 검사) + 복제본 바깥 참조
    R.add('복제 안쪽 PPtr 은 모두 복제본으로 돌려졌다 (바깥 참조는 Panel 부모 하나뿐)', [x[2] for x in info['outward_references']] == ['37'] or info['outward_references'] == [], info['outward_references'])
    # 텍스트 MB
    tx = Obj(sn, tn, info['notice_text_mb']); R.add('글자: m_text = %r, 폰트 Heading-Black 그대로' % info['text'], tx.val['m_text'] == info['text'] and tx.val['m_fontData.m_globalFont'] == 'Heading-Black')
    # 조건 MB
    conds = [(cmb.val['m_conditions.Array[%d].m_FileID' % i], cmb.val['m_conditions.Array[%d].m_PathID' % i]) for i in range(cmb.val['m_conditions.Array.size'])]
    tg = [(cmb.val['m_targets.Array[%d].m_FileID' % i], cmb.val['m_targets.Array[%d].m_PathID' % i]) for i in range(cmb.val['m_targets.Array.size'])]
    R.add('ConditionalActiveGameObjects: m_conditions = %s, m_targets = [(0, %d)]' % (info['conditions'], info['notice_go']), [list(c) for c in conds] == info['conditions'] and tg == [(0, info['notice_go'])])
    R.add('ConditionalActiveGameObjects: m_Script = (%d, 146)' % info['map_sharedassets_fid'], (cmb.val['m_Script.m_FileID'], cmb.val['m_Script.m_PathID']) == (info['map_sharedassets_fid'], 146) and cmb.val['m_Enabled'] == 1)
    if info.get('exit_delay') is not None:
        ex = Obj(sn, tn, 54); R.add('WindowTransitionFadeExit(54): m_delay 2.0 -> %s (m_duration 0.25 그대로), 나머지 필드 그대로' % info['exit_delay'], abs(ex.val['m_delay'] - info['exit_delay']) < 1e-6 and ex.val['m_duration'] == 0.25 and ex.val['m_easingMode'] == 2)
    # ---- UnityPy 독립 재파싱
    try:
        import UnityPy
        _patch_unitypy()
        env = UnityPy.load(new_ui)
        cnt = collections.Counter(); scene_ok = 0; scr = {}; scene_objs = {}
        for ob_ in env.objects:
            cnt[ob_.assets_file.name] += 1
            if ob_.type.name == 'MonoScript': scr[(ob_.assets_file.name, ob_.path_id)] = ob_.read_typetree()['m_ClassName']
            if ob_.assets_file.name == SCENE: scene_objs[ob_.path_id] = ob_
        ref = UnityPy.load(orig_ui); cnt0 = collections.Counter(ob_.assets_file.name for ob_ in ref.objects)
        R.add('UnityPy: ui_screens 전체 로드, 파일별 객체 수 = 원본 (목표 장면만 +%d)' % len(info['new_pids']), all(cnt[k] == cnt0[k] + (len(info['new_pids']) if k == SCENE else 0) for k in cnt0) and set(cnt) == set(cnt0), (cnt[SCENE], cnt0[SCENE]))
        errs = []
        for pid, ob_ in scene_objs.items():
            try: ob_.read_typetree()
            except Exception as e: errs.append((pid, repr(e)))
        R.add('UnityPy: 목표 장면 객체 %d개 전부 타입트리 읽기 성공' % len(scene_objs), not errs, errs[:3])
        mbo = scene_objs[info['cond_mb']]; t = mbo.read_typetree()
        sc = scr.get(('BuildPlayer-MapScreen.sharedAssets', t['m_Script']['m_PathID'])) if t['m_Script']['m_FileID'] == info['map_sharedassets_fid'] else None
        R.add('UnityPy: 새 MB 의 m_Script 가 가리키는 MonoScript = ConditionalActiveGameObjects (DRS.Utils)', sc == 'ConditionalActiveGameObjects', sc)
        ngo = scene_objs[info['notice_go']].read_typetree(); R.add('UnityPy: DateNotice GO 읽기 (이름/비활성)', ngo['m_Name'] == 'DateNotice' and not ngo['m_IsActive'])
        # 조건이 가리키는 data_config 객체
        if new_cfg:
            cenv = UnityPy.load(new_cfg); cmap = {ob_.path_id: ob_ for ob_ in cenv.objects}
            cscr = {ob_.path_id: ob_.read_typetree()['m_ClassName'] for ob_ in cenv.objects if ob_.type.name == 'MonoScript'}
            got = []
            for f, p in info['conditions']:
                tt_ = cmap[p].read_typetree(); got.append((tt_['m_Name'], cscr.get(tt_['m_Script']['m_PathID'])))
            R.add('UnityPy: 조건 PPtr 이 가리키는 data_config 객체 = %s' % got, [g[1] for g in got] == (['IsCycleId', 'IsCycleWithinRange'] if info['mode'] == 'prod' else {'test_day': ['IsCycleId'], 'test_always': [], 'test_range': ['IsCycleWithinRange']}[info['mode']]), got)
    except Exception as e:
        R.add('UnityPy 재파싱', False, repr(e))
    return R


def verify_cfg(orig_cfg, new_cfg, info, R=None):
    R = R or Rep()
    from itdp_datenotice_cfg import open_bundle
    ob = open_bundle(orig_cfg); nb = open_bundle(new_cfg); node = info['node']
    _nodes_equal(ob, nb, node, R, 'data_config')
    o = ob.node_data(node); n = nb.node_data(node)
    R.add('data_config: 원본 노드 SHA-256 이 빌드 기록과 같다', hashlib.sha256(o).hexdigest() == info['src_node_sha256'])
    so = S.Ser(o); sn = S.Ser(n); tn = [tt.build_tree(t) for t in sn.types]
    R.add('data_config: 객체 수 +1, 타입/스크립트/외부 파일 수 그대로', len(sn.objects) == len(so.objects) + 1 and len(sn.types) == len(so.types) and len(sn.externals) == len(so.externals) and len(sn.scripts) == len(so.scripts))
    R.add('data_config: 타입 항목 바이트 그대로', all(o[a.start:a.end] == n[b.start:b.end] for a, b in zip(so.types, sn.types)))
    Po = so.by_pid(); Pn = sn.by_pid(); changed = [p for p, i in Po.items() if p in Pn and so.object_bytes(i) != sn.object_bytes(Pn[p])]
    R.add('data_config: 기존 객체 중 바뀐 것 = 등록부 하나뿐', changed == [info['registry_pid']] and all(p in Pn for p in Po), changed)
    R.add('data_config: 기존 객체 타입 번호 그대로', all(so.objects[i][3] == sn.objects[Pn[p]][3] for p, i in Po.items()))
    R.add('data_config: 새 pid 는 하나뿐이고 계획과 같다', sorted(set(Pn) - set(Po)) == [info['new_pid']])
    reg = Obj(sn, tn, info['registry_pid']); newo = Obj(sn, tn, info['new_pid'])
    tt.parse_object(sn, Pn[info['registry_pid']], tn); tt.parse_object(sn, Pn[info['new_pid']], tn)
    n_ = reg.val['m_initialisableConditions.Array.size']
    R.add('등록부: 조건 %d -> %d, 마지막 항목 = (0, %d), 앞의 %d개 항목은 그대로' % (info['registry_cond_before'], n_, info['new_pid'], info['registry_cond_before']), n_ == info['registry_cond_after'] and (reg.val['m_initialisableConditions.Array[%d].m_FileID' % (n_ - 1)], reg.val['m_initialisableConditions.Array[%d].m_PathID' % (n_ - 1)]) == (0, info['new_pid']))
    ro = Obj(so, [tt.build_tree(t) for t in so.types], info['registry_pid'])
    same = all(ro.val['m_initialisableConditions.Array[%d].m_PathID' % i] == reg.val['m_initialisableConditions.Array[%d].m_PathID' % i] and ro.val['m_initialisableConditions.Array[%d].m_FileID' % i] == reg.val['m_initialisableConditions.Array[%d].m_FileID' % i] for i in range(n_ - 1))
    R.add('등록부: 기존 조건/액션/컨텍스트 항목 값 변화 없음', same and ro.val['m_initialisableActions.Array.size'] == reg.val['m_initialisableActions.Array.size'] and ro.val['m_initialisableContextProviders.Array.size'] == reg.val['m_initialisableContextProviders.Array.size'])
    R.add('새 조건: 이름/ m_min / m_max / m_invert = %s / %d / %d / 0' % (info['new_name'], info['min'], info['max']), (newo.val['m_Name'], newo.val['m_min'], newo.val['m_max'], newo.val['m_invert']) == (info['new_name'], info['min'], info['max'], 0))
    tmpl = Obj(so, [tt.build_tree(t) for t in so.types], info['template_pid'])
    R.add('새 조건: 템플릿과 타입/스크립트 PPtr 동일, m_Enabled=1', sn.objects[Pn[info['new_pid']]][3] == so.objects[Po[info['template_pid']]][3] and newo.val['m_Script.m_PathID'] == tmpl.val['m_Script.m_PathID'] and newo.val['m_Enabled'] == 1)
    names = [Obj(sn, tn, o_[0]).val['m_Name'] for o_ in sn.objects if o_[3] == newo.tid]
    n_old = sum(1 for o_ in so.objects if o_[3] == so.objects[Po[info['template_pid']]][3])
    R.add('새 조건 이름 중복 없음 (이 번들의 IsCycleWithinRange %d개 -> %d개)' % (n_old, len(names)), names.count(info['new_name']) == 1 and len(names) == n_old + 1, len(names))
    try:
        import UnityPy
        _patch_unitypy()
        env = UnityPy.load(new_cfg); errs = []; k = 0; found = None
        for ob_ in env.objects:
            k += 1
            try: t = ob_.read_typetree()
            except Exception as e: errs.append((ob_.path_id, repr(e)))
            else:
                if ob_.path_id == info['new_pid']: found = t
        R.add('UnityPy: data_config 전체 %d개 객체 타입트리 읽기 성공' % k, not errs and k == info['objects_after'], errs[:3])
        R.add('UnityPy: 새 조건 = IsCycleWithinRange 20..21', found is not None and found['m_min'] == info['min'] and found['m_max'] == info['max'] and found['m_Name'] == info['new_name'], found and (found['m_Name'], found['m_min'], found['m_max']))
    except Exception as e:
        R.add('UnityPy 재파싱', False, repr(e))
    return R


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--orig-ui'); ap.add_argument('--new-ui'); ap.add_argument('--ui-info'); ap.add_argument('--orig-cfg'); ap.add_argument('--new-cfg'); ap.add_argument('--cfg-info'); ap.add_argument('--report')
    a = ap.parse_args(argv); R = Rep()
    if a.orig_cfg and a.new_cfg and a.cfg_info:
        verify_cfg(a.orig_cfg, a.new_cfg, json.load(open(a.cfg_info, encoding='utf8')), R)
    if a.orig_ui and a.new_ui and a.ui_info:
        verify_ui(a.orig_ui, a.new_ui, json.load(open(a.ui_info, encoding='utf8')), a.orig_cfg, a.new_cfg, True, R)
    R.dump()
    if a.report: json.dump([{'check': n, 'ok': ok, 'note': str(note)} for n, ok, note in R.rows], open(a.report, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    return 1 if R.fails() else 0


if __name__ == '__main__':
    sys.exit(main())

