#!/usr/bin/env python
"""itdp_datenotice_var.py - 복사본 전용 시험 변형 빌더: 날짜 안내 문구의 조건 컴포넌트가 게임에서 "referenced script ... is missing" 으로 만들어지지 않는 원인을 한 번의 실행으로 가르기 위한 변형들.
모든 변형은 '원본 ui_screens' 에서 따로 만든다 (한 번에 하나만 적용). 게임 폴더에는 쓰지 않는다.

 변형(variant)          장면(BuildPlayer-NewCycleCard)에서 달라지는 점                                                    판정 (Player.log 의 "missing" 줄 + 화면)
 probe_a  : DateNotice 는 처음부터 켜짐. 빈 GameObject(DateNoticeProbe)에 MapScreen.sharedAssets 의 다른 스크립트(WindowTransitionScaleExit, (외부,151))를 붙임.
                         "missing"(DateNoticeProbe) 이 뜨면 → 외부 파일(MapScreen.sharedAssets) 연결/미리 읽기 문제.  안 뜨면 → ConditionalActiveGameObjects 타입 항목 문제.
 b        : 조건 없음 CAGO(켜져야 함). 타입 항목/MB 틀을 은신처 HUD(ShelterHud) 것으로 복사 + 타입 항목을 표 끝이 아니라 중간(MB 타입 구간 한가운데)에 삽입.
 c1       : 조건 없음 CAGO. 새 외부 항목(MapScreen.sharedAssets)을 목록 끝이 아니라 6번(unity default resources 앞, 원본 파일들의 관례적 위치)에 삽입 (이후 외부 번호 전부 +1 로 정리).
 c2       : 조건 없음 CAGO. MapScreen.sharedAssets 를 가리키지 않고 NewCycleCard.sharedAssets(이미 외부 4번)에 ConditionalActiveGameObjects 의 MonoScript 복제본을 넣어 그것을 가리킴.
 d        : 조건 없음 CAGO. MB 틀 = 은신처 HUD 의 MB(1216), 위치는 표 끝 (b 에서 '타입 위치' 만 뺀 것). GameObject/MB 헤더가 다른 MB 와 같음을 확인하는 용도.
 e        : 조건 없음 CAGO. NewCycleCard.sharedAssets 의 PreloadData(장면이 쓰는 외부 객체 미리 읽기 목록, class 150)에 MapScreen.sharedAssets 의 MonoScript 146 을 추가 (+ 그 파일을 외부 항목으로 추가).
 e_day    : e + 조건 [IsCycleId_NotNight] 이고 PreloadData 에 NotNight 도 추가 (낮마다 보임; 조건 평가까지 시험).
조건 없음 CAGO 는 OnEnable 에서 All([])=참 이라 DateNotice 를 켠다 → 컴포넌트가 정상 생성되면 문구가 보인다."""
import sys, os, json, struct, hashlib, bisect, argparse, tempfile
HERE = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
_D = os.path.join(HERE, '..', 'deps')
if os.path.isdir(_D) and _D not in sys.path:
    sys.path.insert(0, _D)

import itdp_ufs as ufs, itdp_ser as S, itdp_tt as tt, itdp_edit2 as ed2, itdp_edit3 as ed3
from itdp_build import Obj, make_go, in_game_folder
from itdp_scn import subtree, rt_of_go, pptr_leaves, class_of, CLS
import itdp_datenotice as N

VARIANTS = ('probe_a', 'b', 'c1', 'c2', 'd', 'e', 'e_day', 'prod')
PRELOAD_VARIANTS = ('e', 'e_day', 'prod')      # 'prod' = 실제 8월 30일 낮 모드 (조건 [NotNight, 새 IsCycleWithinRange] + 미리읽기 항목 3개)
SA = 'BuildPlayer-NewCycleCard.sharedAssets'; MSA = 'BuildPlayer-MapScreen.sharedAssets'; SHUD = 'BuildPlayer-ShelterHud'
SHUD_MB = 1216; PROBE_SCRIPT = 151; PROBE_NAME = 'DateNoticeProbe'
PRELOAD_CLASS = 150


# ---------- PreloadData (class 150) : m_Name(string) / m_Assets(PPtr[]) / m_Dependencies(string[]) / m_ExplicitDataLayout(bool)
def preload_parse(raw):
    n0 = struct.unpack_from('<i', raw, 0)[0]; pos = (4 + n0 + 3) // 4 * 4
    n = struct.unpack_from('<i', raw, pos)[0]; start = pos + 4
    ent = [struct.unpack_from('<iq', raw, start + 12 * k) for k in range(n)]
    return pos, start, n, ent, raw[start + 12 * n:]


def preload_insert(raw, adds):
    """adds: [(index, (fileid, pid))] 삽입 위치(기존 항목 기준 index 앞)와 항목 -> 새 바이트"""
    pos, start, n, ent, tail = preload_parse(raw)
    new = list(ent)
    for idx, e in sorted(adds, key=lambda a: -a[0]):
        new.insert(idx, e)
    out = bytearray(raw[:pos]) + struct.pack('<i', len(new)) + b''.join(struct.pack('<iq', f, p) for f, p in new) + tail
    return bytes(out), new


def _ext_index(externals, suffix):
    for i, e in enumerate(externals):
        if e['path'].endswith(suffix):
            return i + 1
    return None


def plan_variant(src_path, variant, text=N.TEXT, cond_pid=None):
    assert variant in VARIANTS, variant
    assert variant != 'prod' or cond_pid, 'prod 에는 data_config 에 추가한 새 조건의 path id(cond_pid)가 필요합니다'
    sb = ufs.Bundle(src_path); orig = sb.node_data(N.SCENE); sr = S.Ser(orig); trees = [tt.build_tree(t) for t in sr.types]; P = sr.by_pid()
    # ---- 가드 (itdp_datenotice.plan_build 와 같음)
    assert len(sr.objects) == N.OBJECTS_BEFORE, 'NewCycleCard 객체 수 %d (원본 %d 아님)' % (len(sr.objects), N.OBJECTS_BEFORE)
    for pid, nm in N.NAMES.items():
        assert Obj(sr, trees, pid).val['m_Name'] == nm, 'scene differs: GO %d is not %s' % (pid, nm)
    assert not any(class_of(sr, p) == CLS['GO'] and Obj(sr, trees, p).val['m_Name'] in (N.NEW_NAME, N.COND_NAME, PROBE_NAME) for p in P), '이미 날짜 안내 문구가 들어 있습니다'
    panel_rt = Obj(sr, trees, N.PANEL_RT)
    assert panel_rt.val['m_GameObject.m_PathID'] == N.PANEL_GO and panel_rt.val['m_Children.Array.size'] == N.PANEL_CHILDREN_BEFORE
    assert rt_of_go(sr, trees, N.DATE_GO) == 34 and rt_of_go(sr, trees, N.STOP_GO) == 35
    assert sorted(subtree(sr, trees, N.DATE_GO)) == [5, 7, 15, 24, 26, 34, 48]
    assert sr.reftypes_count == 0
    # ---- 틀 장면
    map_orig = sb.node_data(N.MAP_SCENE); msr = S.Ser(map_orig); mtrees = [tt.build_tree(t) for t in msr.types]
    if variant in ('b', 'd'):
        t_orig = sb.node_data(SHUD); tsr = S.Ser(t_orig); ttrees = [tt.build_tree(t) for t in tsr.types]; tpid = SHUD_MB; t_scene = SHUD
    else:
        tsr, ttrees, tpid, t_scene = msr, mtrees, N.MAP_COND_MB, N.MAP_SCENE
    probe = variant == 'probe_a'
    if probe:
        cand = [o[0] for o in msr.objects if msr.types[o[3]].class_id == 114 and msr.types[o[3]].script_index >= 0 and tuple(msr.scripts[msr.types[o[3]].script_index]) == (2, PROBE_SCRIPT)]
        assert len(cand) == 1, cand
        tsr, ttrees, tpid, t_scene = msr, mtrees, cand[0], N.MAP_SCENE
    tmb = Obj(tsr, ttrees, tpid); ttype = tsr.types[tmb.tid]; assert ttype.class_id == 114
    t_script = tuple(tsr.scripts[ttype.script_index]); t_fid, t_lid = t_script
    t_ext_path = tsr.externals[t_fid - 1]['path']; assert t_ext_path.endswith(MSA), t_ext_path
    assert tmb.val['m_Script.m_PathID'] == t_lid and t_lid == (PROBE_SCRIPT if probe else 146)
    if not probe:
        assert set(k.split('.')[0].split('[')[0] for k in tmb.val) >= {'m_conditions', 'm_targets'}
    # ---- 외부 파일
    ext_paths = [e['path'] for e in sr.externals]; assert _ext_index(sr.externals, MSA) is None
    use_local = variant == 'c2'
    ext_pos = None
    if not use_local:
        ext_pos = 6 if variant == 'c1' else len(ext_paths) + 1
        if variant == 'c1':
            assert ext_paths[5].endswith('unity default resources'), ext_paths[5]
    final_ext_paths = ext_paths if use_local else ext_paths[:ext_pos - 1] + [t_ext_path] + ext_paths[ext_pos - 1:]
    mid_insert = ext_pos is not None and ext_pos <= len(ext_paths)
    shift = (lambda f: f + 1 if (mid_insert and f >= ext_pos) else f)
    sa_orig = sb.node_data(SA); sas = S.Ser(sa_orig); sa_nodes = {}
    sa_info = {}
    if use_local:
        fid_script = _ext_index(sr.externals, SA); assert fid_script == 4
        msa = S.Ser(sb.node_data(MSA)); ms_bytes = msa.object_bytes(msa.by_pid()[146]); assert b'ConditionalActiveGameObjects' in ms_bytes and msa.types[msa.objects[msa.by_pid()[146]][3]].class_id == 115
        tid115 = [i for i, t in enumerate(sas.types) if t.class_id == 115]; assert len(tid115) == 1
        local_pid = max(o[0] for o in sas.objects) + 1
        script_lid = local_pid
        sa_nodes[SA] = ed2.rebuild_ext(sa_orig, append=[(local_pid, tid115[0], ms_bytes)])
        sa_info = {'local_monoscript_pid': local_pid, 'local_monoscript_source': [MSA, 146]}
    else:
        fid_script = ext_pos; script_lid = t_lid
    fid_cfg_final = _ext_index([{'path': p} for p in final_ext_paths], N.CFG_CAB); assert fid_cfg_final
    # ---- e / e_day : sharedAssets PreloadData
    if variant in PRELOAD_VARIANTS:
        pidx = [i for i, o in enumerate(sas.objects) if sas.types[o[3]].class_id == PRELOAD_CLASS]; assert len(pidx) == 1
        raw = sas.object_bytes(pidx[0]); pre_pid = sas.objects[pidx[0]][0]
        fid_sa_map = len(sas.externals) + 1; fid_sa_cfg = _ext_index(sas.externals, N.CFG_CAB); assert fid_sa_cfg
        _, _, n, ent, _t = preload_parse(raw)
        adds = [(n, (fid_sa_map, 146))]
        if variant in ('e_day', 'prod'):
            last = max(i for i, e in enumerate(ent) if e[0] == fid_sa_cfg); adds.append((last + 1, (fid_sa_cfg, N.NOTNIGHT_PID)))
        if variant == 'prod':
            adds.append((last + 1, (fid_sa_cfg, cond_pid)))
        nb, newent = preload_insert(raw, adds)
        sa_nodes[SA] = ed2.rebuild_ext(sa_orig, replace={pre_pid: nb}, new_externals=[t_ext_path])
        sa_info = {'preload_pid': pre_pid, 'preload_before': n, 'preload_after': len(newent), 'preload_added': [list(a[1]) for a in adds], 'sa_new_external_fid': fid_sa_map, 'sa_cfg_fid': fid_sa_cfg}
    # ---- 스크립트 표 / 타입 표
    new_script = (fid_script, script_lid)
    scripts_shifted = [(shift(f), l) for f, l in sr.scripts]; assert scripts_shifted == sorted(scripts_shifted)
    j = bisect.bisect_left(scripts_shifted, new_script); scripts_final = scripts_shifted[:j] + [new_script] + scripts_shifted[j:]
    types_raw = ed3.types_raw(sr)
    for i, t in enumerate(sr.types):
        if t.class_id == 114 and t.script_index >= j:
            struct.pack_into('<h', types_raw[i], 5, t.script_index + 1)
    first_mb = min(i for i, t in enumerate(sr.types) if t.class_id == 114)
    type_pos = (first_mb + len(sr.types)) // 2 if variant == 'b' else len(sr.types)
    tb = bytearray(tsr.data[ttype.start:ttype.end]); struct.pack_into('<h', tb, 5, j)
    types_final = [bytes(x) for x in types_raw[:type_pos]] + [bytes(tb)] + [bytes(x) for x in types_raw[type_pos:]]
    tmap = lambda t: t + 1 if t >= type_pos else t
    ext_raw = ed3.externals_raw(sr)
    ext_final = ext_raw if use_local else ext_raw[:ext_pos - 1] + [ed3.external_entry(t_ext_path)] + ext_raw[ext_pos - 1:]

    def shift_obj(o):
        if mid_insert:
            for path, off, val, fid in pptr_leaves(o):
                if fid >= ext_pos:
                    struct.pack_into('<i', o.b, off - 4, fid + 1)
        return o

    origobj = {pid: shift_obj(Obj(sr, trees, pid)) for pid in P}
    # ---- 'Date' 부분 트리 복제
    sub = subtree(sr, trees, N.DATE_GO); nxt = max(P) + 1; newp = {}
    for p in sub:
        newp[p] = nxt; nxt += 1
    cond_go, cond_rt, cond_mb = nxt, nxt + 1, nxt + 2
    objs = {}
    for p in sub:
        o = shift_obj(Obj(sr, trees, p))
        for path, off, val, fid in pptr_leaves(Obj(sr, trees, p)):
            if fid == 0 and val in newp:
                struct.pack_into('<q', o.b, off, newp[val])
        objs[p] = o
    go_root = objs[N.DATE_GO]; go_root.set_str('m_Name', N.NEW_NAME); go_root.set('m_IsActive', 1 if probe else 0)
    rt_root = objs[34]
    rt_root.set('m_AnchoredPosition.x', float(N.DEFAULT_POS[0])); rt_root.set('m_AnchoredPosition.y', float(N.DEFAULT_POS[1])); rt_root.set('m_SizeDelta.y', float(N.DEFAULT_SIZE_Y))
    st = objs[48]; st.set_str('m_text', text)
    st.set('m_fontData.m_fontSize', N.FONT_SIZE); st.set('m_fontData.m_minSize', 10); st.set('m_fontData.m_maxSize', N.FONT_SIZE)
    for c, v in zip('rgba', N.COLOR):
        st.set('m_Color.' + c, float(v))
    st.set('m_RaycastTarget', 0)
    append = [(newp[p], tmap(objs[p].tid), bytes(objs[p].b)) for p in sub]
    # ---- 조건 GameObject
    sib = origobj[35]; assert sib.val['m_Children.Array.size'] == 0
    sib = shift_obj(Obj(sr, trees, 35))
    struct.pack_into('<q', sib.b, sib.off['m_GameObject.m_PathID'][0], cond_go)
    struct.pack_into('<q', sib.b, sib.off['m_Father.m_PathID'][0], N.PANEL_RT); struct.pack_into('<i', sib.b, sib.off['m_Father.m_FileID'][0], 0)
    layer = Obj(sr, trees, N.PANEL_GO).val['m_Layer']; gtid = sr.objects[P[N.DATE_GO]][3]
    go_name = PROBE_NAME if probe else N.COND_NAME
    mgo = make_go([cond_rt, cond_mb], layer, go_name, True); tt.parse_bytes(trees[gtid], mgo)
    conds = [(fid_cfg_final, N.NOTNIGHT_PID)] if variant == 'e_day' else [(fid_cfg_final, N.NOTNIGHT_PID), (fid_cfg_final, cond_pid)] if variant == 'prod' else []
    if probe:
        mb = bytearray(tmb.b)
        struct.pack_into('<q', mb, tmb.off['m_GameObject.m_PathID'][0], cond_go); struct.pack_into('<i', mb, tmb.off['m_GameObject.m_FileID'][0], 0)
        struct.pack_into('<i', mb, tmb.off['m_Script.m_FileID'][0], fid_script); struct.pack_into('<q', mb, tmb.off['m_Script.m_PathID'][0], script_lid)
        mb = bytes(mb)
        for k in tmb.val:                                           # 틀 MB 의 다른 PPtr 은 없어야 한다 (장면 밖을 가리키면 안 됨)
            if k.endswith('m_PathID') and not k.startswith(('m_GameObject', 'm_Script')):
                assert tmb.val[k] == 0, k
    else:
        a0 = tmb.off['m_conditions.Array.size'][0]; head = bytearray(tmb.b[:a0])
        struct.pack_into('<q', head, tmb.off['m_GameObject.m_PathID'][0], cond_go); struct.pack_into('<i', head, tmb.off['m_GameObject.m_FileID'][0], 0)
        struct.pack_into('<i', head, tmb.off['m_Script.m_FileID'][0], fid_script); struct.pack_into('<q', head, tmb.off['m_Script.m_PathID'][0], script_lid)
        mb = bytes(head) + struct.pack('<i', len(conds)) + b''.join(struct.pack('<iq', f, p) for f, p in conds) + struct.pack('<i', 1) + struct.pack('<iq', 0, newp[N.DATE_GO])
    tt.parse_bytes(ttrees[tmb.tid], mb)
    panel = shift_obj(Obj(sr, trees, N.PANEL_RT)); N.children_append_many(panel, [newp[34], cond_rt])
    append += [(cond_go, tmap(gtid), mgo), (cond_rt, tmap(sib.tid), bytes(sib.b)), (cond_mb, type_pos, mb)]
    final_objs = []
    for pid, bs, bsz, tid in sr.objects:
        b = bytes(panel.b) if pid == N.PANEL_RT else bytes(origobj[pid].b)
        final_objs.append((pid, tmap(tid), b))
    final_objs += append
    new_scene = ed3.assemble(orig, final_objs, types_final, scripts_final, ext_final)
    nodes = {N.SCENE: new_scene}; nodes.update(sa_nodes)
    info = {'variant': variant, 'scene': N.SCENE, 'text': text, 'objects_before': len(sr.objects), 'objects_after': len(final_objs), 'new_pids': [a[0] for a in append],
            'notice_go': newp[N.DATE_GO], 'notice_rt': newp[34], 'notice_text_mb': newp[48], 'cond_go': cond_go, 'cond_rt': cond_rt, 'cond_mb': cond_mb, 'cond_go_name': go_name,
            'panel_rt': N.PANEL_RT, 'type_pos': type_pos, 'types_before': len(sr.types), 'script_entry': list(new_script), 'script_pos': j, 'scripts_before': len(sr.scripts),
            'externals_before': len(ext_paths), 'ext_pos': ext_pos, 'ext_mid_insert': mid_insert, 'use_local_monoscript': use_local, 'conditions': [list(c) for c in conds],
            'template': {'scene': t_scene, 'mb': tpid, 'script': list(t_script), 'type_class': ttype.class_id}, 'sa': sa_info, 'nodes_changed': sorted(nodes), 'notice_active': 1 if probe else 0,
            'src_scene_sha256': hashlib.sha256(orig).hexdigest(), 'new_scene_sha256': hashlib.sha256(new_scene).hexdigest(), 'map_ext_path': t_ext_path}
    return sb, nodes, info


def write_variant(sb, nodes):
    """장면 노드(필요하면 sharedAssets 노드도)를 순서대로 교체한 번들 바이트를 돌려준다"""
    names = [N.SCENE] + [k for k in nodes if k != N.SCENE]
    data = ufs.write_bundle(sb, names[0], nodes[names[0]], 'rebuild')
    for nm in names[1:]:
        fd, tmp = tempfile.mkstemp(prefix='itd_var_'); os.close(fd)
        try:
            open(tmp, 'wb').write(data); sb2 = ufs.Bundle(tmp); data = ufs.write_bundle(sb2, nm, nodes[nm], 'rebuild'); del sb2
        finally:
            try: os.remove(tmp)
            except OSError: pass
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['plan', 'build']); ap.add_argument('--src', required=True); ap.add_argument('--out'); ap.add_argument('--variant', required=True, choices=VARIANTS)
    a = ap.parse_args(argv)
    sb, nodes, info = plan_variant(a.src, a.variant)
    print('variant %s: scene %d bytes, objects %d -> %d, type_pos %d, script %s at %d, ext_pos %s, nodes %s' % (a.variant, len(nodes[N.SCENE]), info['objects_before'], info['objects_after'], info['type_pos'], info['script_entry'], info['script_pos'], info['ext_pos'], info['nodes_changed']))
    if a.cmd == 'plan':
        print('(plan only, nothing written)'); return 0
    if not a.out:
        ap.error('--out required')
    if in_game_folder(a.out):
        print('REFUSED: --out is inside the game folder'); return 2
    os.makedirs(a.out, exist_ok=True); op = os.path.join(a.out, 'ui_screens')
    if os.path.abspath(op) == os.path.abspath(a.src):
        print('REFUSED: output would overwrite the source'); return 2
    out = write_variant(sb, nodes); open(op, 'wb').write(out)
    info.update({'out': op, 'sha256': hashlib.sha256(out).hexdigest(), 'src_sha256': hashlib.sha256(sb.raw).hexdigest(), 'size': len(out)})
    json.dump(info, open(op + '.build.json', 'w', encoding='utf8'), indent=1, ensure_ascii=False); print('wrote %s (%d bytes) sha256 %s' % (op, len(out), info['sha256'])); return 0


if __name__ == '__main__':
    sys.exit(main())

