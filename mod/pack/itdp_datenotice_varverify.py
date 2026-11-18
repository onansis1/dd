#!/usr/bin/env python
"""itdp_datenotice_varverify.py - 시험 변형(itdp_datenotice_var) 결과 번들 검증기. 하나라도 FAIL 이면 종료 코드 1.
  python itdp_datenotice_varverify.py --orig-ui <원본 ui_screens> --new-ui <변형 ui_screens> --info <ui_screens.build.json>
검사: 번들(노드 목록 동일, 바뀐 노드 = 변형이 바꾼 노드뿐, 나머지는 압축 해제 바이트까지 동일) / 장면(객체/타입/스크립트/외부 표의 정확한 증감, 기존 객체는 의미 단위로 동일(외부 번호 이동 반영, Panel 은 자식 2개만 증가),
새 객체 전부 타입 트리 파싱, PPtr 유효성, 스크립트 참조 = 타입의 script_index 가 가리키는 스크립트 표 항목, 계층 쌍방 참조) / 스크립트 소스(외부 MonoScript 가 실제로 있고 클래스 이름이 맞는지; c2 는 로컬 복제본) /
PreloadData(e, e_day) / UnityPy 독립 재파싱."""
import sys, os, json, struct, hashlib, argparse
HERE = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
_D = os.path.join(HERE, '..', 'deps')
if os.path.isdir(_D) and _D not in sys.path:
    sys.path.insert(0, _D)
import itdp_ufs as ufs, itdp_ser as S, itdp_tt as tt
from itdp_build import Obj
from itdp_scn import pptr_leaves
import itdp_datenotice as N, itdp_datenotice_var as V
from itdp_datenotice_verify import Rep, _patch_unitypy


def _name(raw):
    n = struct.unpack_from('<i', raw, 0)[0]; return raw[4:4 + n].decode('utf8', 'replace')


def verify_variant(orig_ui, new_ui, info, R=None, full=True):
    R = R or Rep(); variant = info['variant']
    b0 = ufs.Bundle(orig_ui); b1 = ufs.Bundle(new_ui)
    R.add('노드 목록 동일 (%d개)' % len(b0.nodes), [n[3] for n in b0.nodes] == [n[3] for n in b1.nodes])
    changed = []
    d0 = b0.decompress(); d1 = b1.decompress()
    for n0, n1 in zip(b0.nodes, b1.nodes):
        if hashlib.sha256(d0[n0[0]:n0[0] + n0[1]]).digest() != hashlib.sha256(d1[n1[0]:n1[0] + n1[1]]).digest():
            changed.append(n0[3])
    R.add('바뀐 노드 = %s' % info['nodes_changed'], sorted(changed) == sorted(info['nodes_changed']), changed)
    orig = b0.node_data(N.SCENE); new = b1.node_data(N.SCENE)
    R.add('새 장면 SHA-256 = 빌드 기록', hashlib.sha256(new).hexdigest() == info['new_scene_sha256'])
    so = S.Ser(orig); sn = S.Ser(new); to = [tt.build_tree(t) for t in so.types]; tn = [tt.build_tree(t) for t in sn.types]
    Po = so.by_pid(); Pn = sn.by_pid()
    newp = info['new_pids']
    R.add('객체 수 %d -> %d' % (len(so.objects), len(sn.objects)), len(sn.objects) == len(so.objects) + len(newp) == info['objects_after'])
    R.add('새 pid 는 기존과 겹치지 않고 모두 존재', all(p not in Po and p in Pn for p in newp))
    # ---- 외부 / 스크립트 / 타입 표
    ext_pos = info['ext_pos']; mid = info['ext_mid_insert']; shift = (lambda f: f + 1 if (mid and f >= ext_pos) else f)
    pa = [e['path'] for e in so.externals]; pn = [e['path'] for e in sn.externals]
    if info['use_local_monoscript']:
        R.add('외부 표 변화 없음 (c2)', pa == pn)
    else:
        exp = pa[:ext_pos - 1] + [info['map_ext_path']] + pa[ext_pos - 1:]
        R.add('외부 표 = 원본 + MapScreen.sharedAssets 가 %d번에 삽입' % ext_pos, pn == exp, pn[-2:])
        e = sn.externals[ext_pos - 1]; R.add('새 외부 항목 guid=0, type=0', e['guid'] == b'\0' * 16 and e['type'] == 0)
    ns = tuple(info['script_entry']); j = info['script_pos']
    exp_sc = [(shift(f), l) for f, l in so.scripts]; exp_sc = exp_sc[:j] + [ns] + exp_sc[j:]
    R.add('스크립트 표 = 원본(외부 번호 이동 반영) + %s 가 %d번에 삽입, 정렬 유지' % (list(ns), j), [tuple(x) for x in sn.scripts] == exp_sc and exp_sc == sorted(exp_sc))
    tp = info['type_pos']
    R.add('타입 수 +1, 새 타입 위치 %d' % tp, len(sn.types) == len(so.types) + 1)
    ok = True; bad = []
    for i, t in enumerate(so.types):
        k = i + 1 if i >= tp else i; u = sn.types[k]
        raw_o = bytearray(so.data[t.start:t.end]); raw_n = bytearray(sn.data[u.start:u.end])
        if t.class_id == 114 and t.script_index >= j:
            struct.pack_into('<h', raw_o, 5, t.script_index + 1)
        if raw_o != raw_n:
            ok = False; bad.append(i)
    R.add('기존 타입 항목 = 원본 (스크립트 번호 밀림만 반영)', ok, bad)
    # 새 타입 항목 = 틀 장면의 같은 타입 항목 (script_index 만 다름)
    tmpl = info['template']; tb = ufs.Bundle(orig_ui).node_data(tmpl['scene']); ts = S.Ser(tb)
    tobj = ts.objects[ts.by_pid()[tmpl['mb']]]; tt_ = ts.types[tobj[3]]
    ref = bytearray(ts.data[tt_.start:tt_.end]); struct.pack_into('<h', ref, 5, j); u = sn.types[tp]
    R.add('새 타입 항목 = %s 장면의 MB %d 의 타입 항목 (script_index %d 만 다름)' % (tmpl['scene'].replace('BuildPlayer-', ''), tmpl['mb'], j), bytearray(sn.data[u.start:u.end]) == ref and u.class_id == 114 and u.script_index == j)
    R.add('다른 장면 틀의 스크립트 표 항목 = (%s, %d) 이고 그 외부 파일 = MapScreen.sharedAssets' % ('.', tmpl['script'][1]), ts.externals[tmpl['script'][0] - 1]['path'] == info['map_ext_path'])
    # ---- 기존 객체: 의미 단위 동일
    amap = lambda tid: tid + 1 if tid >= tp else tid
    diffs = []
    for i, (pid, bs, bsz, tid) in enumerate(so.objects):
        o0 = Obj(so, to, pid); o1 = Obj(sn, tn, pid)
        if amap(tid) != sn.objects[Pn[pid]][3]: diffs.append((pid, 'tid')); continue
        v0 = o0.val; v1 = o1.val
        keys0 = [k for k in v0 if not (pid == info['panel_rt'] and k.startswith('m_Children'))]
        for k in keys0:
            e0 = v0[k]
            if k.endswith('m_FileID'): e0 = shift(e0)
            if v1.get(k) != e0: diffs.append((pid, k)); break
    R.add('기존 객체 %d개 의미 동일 (외부 번호 이동 반영, Panel 은 자식 목록만 다름)' % len(so.objects), not diffs, diffs[:5])
    pr0 = Obj(so, to, info['panel_rt']); pr1 = Obj(sn, tn, info['panel_rt'])
    ch0 = [pr0.val['m_Children.Array[%d].m_PathID' % i] for i in range(pr0.val['m_Children.Array.size'])]
    ch1 = [pr1.val['m_Children.Array[%d].m_PathID' % i] for i in range(pr1.val['m_Children.Array.size'])]
    R.add('Panel 자식 = 원본 5개 + [DateNotice RT, 조건 RT]', ch1 == ch0 + [info['notice_rt'], info['cond_rt']])
    # ---- 새 객체 전부 파싱 + PPtr 유효성
    bad = []
    for p in newp:
        try:
            o = Obj(sn, tn, p)
            for path, off, val, fid in pptr_leaves(o):
                if fid == 0 and val != 0 and val not in Pn: bad.append((p, path, 'local missing %d' % val))
                if fid < 0 or fid > len(sn.externals): bad.append((p, path, 'fid %d' % fid))
        except Exception as ex:
            bad.append((p, 'parse', repr(ex)[:60]))
    R.add('새 객체 %d개 전부 타입 트리로 파싱 + PPtr 유효 (로컬 존재, 외부 번호 범위)' % len(newp), not bad, bad[:5])
    # ---- 조건 GO / MB
    cg = Obj(sn, tn, info['cond_go']); cmb = Obj(sn, tn, info['cond_mb']); crt = Obj(sn, tn, info['cond_rt'])
    R.add('조건 GO 이름 %s, 켜짐, 컴포넌트 = [RT, MB]' % info['cond_go_name'], cg.val['m_Name'] == info['cond_go_name'] and cg.val['m_IsActive'] == 1 and [cg.val['m_Component.Array[%d].component.m_PathID' % i] for i in range(2)] == [info['cond_rt'], info['cond_mb']] and cg.val['m_Component.Array.size'] == 2)
    R.add('MB/RT 의 m_GameObject = 조건 GO, RT 부모 = Panel RT', cmb.val['m_GameObject.m_PathID'] == info['cond_go'] and crt.val['m_GameObject.m_PathID'] == info['cond_go'] and crt.val['m_Father.m_PathID'] == info['panel_rt'])
    mbt = sn.types[sn.objects[Pn[info['cond_mb']]][3]]
    sc_pg = (cmb.val['m_Script.m_FileID'], cmb.val['m_Script.m_PathID'])
    R.add('MB 의 타입 = 새 타입(위치 %d), 타입 script_index → 스크립트 표 = MB 의 m_Script = %s' % (tp, list(ns)), sn.objects[Pn[info['cond_mb']]][3] == tp and tuple(sn.scripts[mbt.script_index]) == sc_pg == ns, (sc_pg, tuple(sn.scripts[mbt.script_index])))
    nt = Obj(sn, tn, info['notice_go'])
    R.add('DateNotice GO 이름/활성: m_IsActive=%d' % info['notice_active'], nt.val['m_Name'] == N.NEW_NAME and nt.val['m_IsActive'] == info['notice_active'])
    if variant == 'probe_a':
        R.add('probe: MB 에 조건/대상 필드 없음 (WindowTransitionScaleExit)', 'm_conditions.Array.size' not in cmb.val and 'm_duration' in cmb.val)
    else:
        nconds = cmb.val['m_conditions.Array.size']
        conds = [(cmb.val['m_conditions.Array[%d].m_FileID' % i], cmb.val['m_conditions.Array[%d].m_PathID' % i]) for i in range(nconds)]
        R.add('CAGO 조건 = %s' % info['conditions'], [list(c) for c in conds] == info['conditions'])
        R.add('CAGO 대상 = [DateNotice GO]', cmb.val['m_targets.Array.size'] == 1 and cmb.val['m_targets.Array[0].m_PathID'] == info['notice_go'] and cmb.val['m_targets.Array[0].m_FileID'] == 0)
        for f, p in conds:
            R.add('조건 PPtr 외부 %d = data_config CAB' % f, sn.externals[f - 1]['path'].endswith(N.CFG_CAB))
    # ---- 스크립트 소스
    fid, lid = ns
    if info['use_local_monoscript']:
        sa1 = S.Ser(b1.node_data(V.SA)); sa0 = S.Ser(b0.node_data(V.SA)); lp = info['sa']['local_monoscript_pid']
        R.add('c2: NewCycleCard.sharedAssets 에 MonoScript 복제본 %d 있음 (기존 객체 2개 + 1)' % lp, len(sa1.objects) == len(sa0.objects) + 1 and lp in sa1.by_pid() and sa1.types[sa1.objects[sa1.by_pid()[lp]][3]].class_id == 115)
        raw = sa1.object_bytes(sa1.by_pid()[lp]); R.add('c2: 복제본 클래스 = ConditionalActiveGameObjects / DRS.Utils', _name(raw) == 'ConditionalActiveGameObjects' and b'DRS.Utils' in raw)
        R.add('c2: 스크립트 외부 번호 %d = NewCycleCard.sharedAssets' % fid, sn.externals[fid - 1]['path'].endswith(V.SA))
        keep = [o for o in sa0.objects]
        R.add('c2: sharedAssets 기존 객체 내용 동일', all(sa0.object_bytes(i) == sa1.object_bytes(sa1.by_pid()[o[0]]) for i, o in enumerate(sa0.objects)))
    else:
        msa = S.Ser(b1.node_data(V.MSA)); mp = msa.by_pid()
        want = b'WindowTransitionScaleExit' if variant == 'probe_a' else b'ConditionalActiveGameObjects'
        R.add('스크립트 소스: MapScreen.sharedAssets 의 MonoScript %d 존재, 클래스 이름 맞음' % lid, lid in mp and msa.types[msa.objects[mp[lid]][3]].class_id == 115 and want in msa.object_bytes(mp[lid]), want)
        R.add('스크립트 외부 번호 %d = MapScreen.sharedAssets' % fid, sn.externals[fid - 1]['path'].endswith(V.MSA))
    # ---- PreloadData
    if variant in V.PRELOAD_VARIANTS:
        sa0 = S.Ser(b0.node_data(V.SA)); sa1 = S.Ser(b1.node_data(V.SA)); pp = info['sa']['preload_pid']
        e0 = V.preload_parse(sa0.object_bytes(sa0.by_pid()[pp])); e1 = V.preload_parse(sa1.object_bytes(sa1.by_pid()[pp]))
        added = [tuple(x) for x in info['sa']['preload_added']]
        R.add('PreloadData: 항목 %d -> %d, 기존 항목 순서 유지 + 추가 %s' % (e0[2], e1[2], added), e1[2] == e0[2] + len(added) and [x for x in e1[3] if x not in added] == e0[3] and all(a in e1[3] for a in added))
        R.add('PreloadData: 의존 번들 이름 목록(tail) 그대로', e0[4] == e1[4])
        nf = info['sa']['sa_new_external_fid']
        R.add('sharedAssets 외부 +1 (MapScreen.sharedAssets = %d번)' % nf, len(sa1.externals) == len(sa0.externals) + 1 and sa1.externals[nf - 1]['path'].endswith(V.MSA) and [x['path'] for x in sa1.externals[:-1]] == [x['path'] for x in sa0.externals])
        R.add('sharedAssets 나머지 객체 내용 동일', all(sa0.object_bytes(i) == sa1.object_bytes(sa1.by_pid()[o[0]]) for i, o in enumerate(sa0.objects) if o[0] != pp))
        for f, p in added:
            R.add('PreloadData 추가 항목 (%d,%d) → %s' % (f, p, sa1.externals[f - 1]['path'].split('/')[-1]), 1 <= f <= len(sa1.externals))
    # ---- UnityPy 독립 재파싱
    if full:
        import UnityPy
        _patch_unitypy()
        env = UnityPy.load(new_ui); cnt = 0; found = None; pre_ok = None
        for o in env.objects:
            cnt += 1
            if o.assets_file.name == N.SCENE and o.path_id == info['cond_mb']:
                t = o.read_typetree(); found = t
            if variant in V.PRELOAD_VARIANTS and o.assets_file.name == V.SA and o.path_id == info['sa']['preload_pid']:
                t = o.read_typetree(); pre_ok = len(t['m_Assets'])
        R.add('UnityPy: 번들 전체 로드 + 객체 %d개 열거' % cnt, cnt > 70000)
        R.add('UnityPy: 조건 MB(%d) 타입 트리 읽힘, m_Script = %s' % (info['cond_mb'], list(ns)), found is not None and (found['m_Script']['m_FileID'], found['m_Script']['m_PathID']) == ns, found and found['m_Script'])
        if variant in V.PRELOAD_VARIANTS:
            R.add('UnityPy: PreloadData m_Assets %d개 읽힘' % info['sa']['preload_after'], pre_ok == info['sa']['preload_after'])
    return R


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--orig-ui', required=True); ap.add_argument('--new-ui', required=True); ap.add_argument('--info', required=True); ap.add_argument('--quick', action='store_true')
    a = ap.parse_args(); info = json.load(open(a.info, encoding='utf8'))
    R = verify_variant(a.orig_ui, a.new_ui, info, full=not a.quick); R.dump(); sys.exit(1 if R.fails() else 0)


if __name__ == '__main__':
    main()

