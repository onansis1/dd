#!/usr/bin/env python
"""itdp_datenotice.py - 복사본 전용 도구: ui_screens 번들의 BuildPlayer-NewCycleCard 장면(날짜 안내 화면, NewCycleScreen)에 '발걸음 소리를 켜세요' 글자 오브젝트를 추가한다.
(게임 폴더에는 쓰지 않는다. 원본은 읽기만 한다. 앱의 itdp_ufs / itdp_ser / itdp_tt / itdp_build / itdp_scn 과 같은 방식)

장면 안에서 하는 일 (모두 BuildPlayer-NewCycleCard 한 파일 안, 다른 노드는 바이트 그대로):
  1. Panel 아래 'Date'(GO 7: RectTransform + CanvasRenderer + SmartText, 자식 inlineImages) 부분 트리를 복제 -> 'DateNotice'
     - 복제본 안쪽을 가리키는 PPtr 은 모두 복제본으로 돌리고(일반 잎 스캔), 글자 = 고정 한국어 문구, 위치 = 날짜 아래, 처음엔 꺼짐(m_IsActive=0).
  2. 새 GameObject 'DateNoticeCondition' = RectTransform + ConditionalActiveGameObjects(DRS.Utils; 지도 화면/은신처 HUD 가 이미 쓰는 컴포넌트, OnEnable 에서 조건을 평가해 대상을 켜고 끈다)
     - m_conditions = [IsCycleId_NotNight(data_config 기존), 새 IsCycleWithinRange(20~21)(data_config 에 추가한 오브젝트)]   (mode prod)
     - m_targets    = [DateNotice]
  3. 이 장면 파일에 없던 컴포넌트 타입이라, 타입 표에 항목 1개(지도 화면 장면의 같은 타입 항목을 그대로 복사, script_index 만 새 번호), 스크립트 표에 (외부 파일 번호, 146) 1개,
     외부 파일 표에 BuildPlayer-MapScreen.sharedAssets 1개를 추가한다 (은신처 HUD 장면이 이미 같은 방식으로 이 MonoScript 를 가리킨다).
  4. Panel RectTransform 의 자식 목록에 새 RectTransform 2개를 덧붙인다 (기존 객체 중 바뀌는 것은 이것 하나뿐).
mode:  prod        = [NotNight, 새 범위 조건]            -> 8월 30일 낮에만 보임
       test_day    = [NotNight]                          -> 모든 낮에 보임 (조건 평가/초기화 시험)
       test_always = []                                  -> 항상 보임 (컴포넌트 동작/글꼴/위치 시험)
       test_range  = [새 범위 조건]  (cfg 에서 만든 범위를 --min/--max 로 바꿔 시험)
"""
import sys, os, json, struct, hashlib, argparse
HERE = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
_D = os.path.join(HERE, '..', 'deps')                         # 패키지 레이아웃(tools/ 옆의 deps/)이면 앱 itdp_* 스냅샷을 쓴다. 앱 폴더에 넣어 쓸 때는 필요 없음
if os.path.isdir(_D) and _D not in sys.path:
    sys.path.insert(0, _D)

import itdp_ufs as ufs, itdp_ser as S, itdp_tt as tt, itdp_edit2 as ed2
from itdp_build import Obj, make_go, in_game_folder
from itdp_scn import subtree, rt_of_go, pptr_leaves, children_append, class_of, CLS

SCENE = 'BuildPlayer-NewCycleCard'
MAP_SCENE = 'BuildPlayer-MapScreen'
NAMES = {12: 'Canvas', 11: 'Panel', 7: 'Date', 6: 'Date', 2: 'CycleName', 8: 'UnityEventStopSirenAudio', 5: 'inlineImages'}
PANEL_GO, PANEL_RT, DATE_GO, STOP_GO = 11, 37, 7, 8
OBJECTS_BEFORE = 58
PANEL_CHILDREN_BEFORE = 5
MAP_COND_MB = 2338                         # BuildPlayer-MapScreen: ConditionalActiveGameObjects (type/template source)
MAP_SCRIPT_LOCAL_ID = 146                  # MonoScript ConditionalActiveGameObjects in BuildPlayer-MapScreen.sharedAssets
CFG_CAB = 'CAB-e04823e81dec6fc2099bf567eba2f429'   # data_config 의 CAB 이름 (이 장면의 외부 9번)
NOTNIGHT_PID = 1361094819312709118         # data_config: IsCycleId_NotNight (기존, 초기화 목록 등록됨)
NEW_NAME = 'DateNotice'; COND_NAME = 'DateNoticeCondition'
TEXT = '발걸음 소리를 켜세요'
DEFAULT_POS = (0.0, -250.0); DEFAULT_SIZE_Y = -980.0   # Date: pos y -124 / size y -868 (높이 212). 새 글자: 높이 100, 날짜 아래
FONT_SIZE = 34
COLOR = (0.9294117689132690, 0.9215686321258545, 0.8549019694328308, 1.0)   # Date 뒷글자와 같은 색


def children_append_many(o, pids):
    """RectTransform.m_Children 끝에 여러 개를 한 번에 덧붙인다 (itdp_scn.children_append 는 한 개씩이고 갱신된 개수를 다시 읽지 않는다)"""
    n = o.val['m_Children.Array.size']; a0 = o.off['m_Children.Array.size'][0]; ins = a0 + 4 + 12 * n
    assert ins == o.off['m_Father.m_FileID'][0], 'unexpected RectTransform layout'
    o.b[ins:ins] = b''.join(struct.pack('<iq', 0, p) for p in pids); struct.pack_into('<i', o.b, a0, n + len(pids))


def _ext_index(externals, suffix):
    for i, e in enumerate(externals):
        if e['path'].endswith(suffix):
            return i + 1
    return None


EXIT_MB = 54; EXIT_DELAY_ORIG = 2.0           # WindowTransitionFadeExit (m_delay 2.0 s, m_duration 0.25 s): 카드가 닫히기 시작하기까지의 대기. 바꾸면 모든 날짜 카드에 적용된다 (선택 사항)


def plan_build(src_path, cond_pid, mode='prod', text=TEXT, pos=DEFAULT_POS, size_y=DEFAULT_SIZE_Y, font_size=FONT_SIZE, color=COLOR, exit_delay=None):
    """src_path: ui_screens 복사본. cond_pid: data_config 에 추가한 새 IsCycleWithinRange 의 path id (mode 에 따라 쓰지 않으면 None 가능).
    returns (bundle, orig_scene_bytes, new_scene_bytes, info)"""
    assert mode in ('prod', 'test_day', 'test_always', 'test_range'), mode
    sb = ufs.Bundle(src_path); orig = sb.node_data(SCENE); sr = S.Ser(orig); trees = [tt.build_tree(t) for t in sr.types]; P = sr.by_pid()
    # ---- 가드: 이 게임 빌드의 원본 장면인가
    assert len(sr.objects) == OBJECTS_BEFORE, 'NewCycleCard 객체 수 %d (원본 %d 아님: 이미 편집되었거나 게임이 업데이트됨)' % (len(sr.objects), OBJECTS_BEFORE)
    for pid, nm in NAMES.items():
        assert Obj(sr, trees, pid).val['m_Name'] == nm, 'scene differs: GO %d is not %s' % (pid, nm)
    assert not any(class_of(sr, p) == CLS['GO'] and Obj(sr, trees, p).val['m_Name'] in (NEW_NAME, COND_NAME) for p in P), '이미 날짜 안내 문구가 들어 있습니다 (두 번 만들지 않음)'
    panel_rt = Obj(sr, trees, PANEL_RT)
    assert panel_rt.val['m_GameObject.m_PathID'] == PANEL_GO
    assert panel_rt.val['m_Children.Array.size'] == PANEL_CHILDREN_BEFORE, 'Panel 자식 %d개 (원본 %d)' % (panel_rt.val['m_Children.Array.size'], PANEL_CHILDREN_BEFORE)
    assert rt_of_go(sr, trees, DATE_GO) == 34 and rt_of_go(sr, trees, STOP_GO) == 35
    sub = subtree(sr, trees, DATE_GO); assert sorted(sub) == [5, 7, 15, 24, 26, 34, 48], sorted(sub)   # GO7, RT34, CR26, SmartText48 + 자식 inlineImages(GO5, T15, CR24)
    # ---- 외부 파일 / 스크립트 / 타입 (지도 화면 장면의 ConditionalActiveGameObjects 에서 가져온다)
    msb = sb; map_orig = msb.node_data(MAP_SCENE); msr = S.Ser(map_orig); mtrees = [tt.build_tree(t) for t in msr.types]; MP = msr.by_pid()
    mcond = Obj(msr, mtrees, MAP_COND_MB); mtype = msr.types[mcond.tid]
    assert mtype.class_id == 114 and mcond.val['m_Script.m_PathID'] == MAP_SCRIPT_LOCAL_ID, 'MapScreen 의 ConditionalActiveGameObjects 템플릿이 달라졌습니다'
    assert set(k.split('.')[0].split('[')[0] for k in mcond.val) >= {'m_conditions', 'm_targets'}
    map_fi = mcond.val['m_Script.m_FileID']; map_ext_path = msr.externals[map_fi - 1]['path']
    assert map_ext_path.endswith('BuildPlayer-MapScreen.sharedAssets'), map_ext_path
    new_ext = []
    fid_map = _ext_index(sr.externals, 'BuildPlayer-MapScreen.sharedAssets')
    if fid_map is None:
        new_ext.append(map_ext_path); fid_map = len(sr.externals) + 1
    fid_cfg = _ext_index(sr.externals, CFG_CAB)
    assert fid_cfg is not None, 'data_config CAB 외부 항목이 없습니다'
    new_type_id = len(sr.types); new_script_index = len(sr.scripts)
    tb = bytearray(map_orig[mtype.start:mtype.end]); struct.pack_into('<h', tb, 5, new_script_index)     # class_id(4) + stripped(1) + script_index(2)
    new_types = [bytes(tb)]; new_scripts = [(fid_map, MAP_SCRIPT_LOCAL_ID)]
    # ---- 1. 'Date' 부분 트리 복제
    sub = subtree(sr, trees, DATE_GO)
    nxt = max(P) + 1; newp = {}
    for p in sub:
        newp[p] = nxt; nxt += 1
    cond_go, cond_rt, cond_mb = nxt, nxt + 1, nxt + 2
    objs = {}; outward = set(); append = []
    for p in sub:
        o = Obj(sr, trees, p)
        for path, off, val, fid in pptr_leaves(o):
            if fid == 0 and val in newp:
                struct.pack_into('<q', o.b, off, newp[val])
            elif fid == 0 and val != 0 and val not in newp:
                outward.add((p, path, val))
        objs[p] = o
    go_root = objs[DATE_GO]; go_root.set_str('m_Name', NEW_NAME); go_root.set('m_IsActive', 0)
    rt_root = objs[34]
    rt_root.set('m_AnchoredPosition.x', float(pos[0])); rt_root.set('m_AnchoredPosition.y', float(pos[1])); rt_root.set('m_SizeDelta.y', float(size_y))
    st = objs[48]; st.set_str('m_text', text)
    st.set('m_fontData.m_fontSize', int(font_size)); st.set('m_fontData.m_minSize', 10); st.set('m_fontData.m_maxSize', int(font_size))
    for c, v in zip('rgba', color):
        st.set('m_Color.' + c, float(v))
    st.set('m_RaycastTarget', 0)
    for p in sub:
        append.append((newp[p], objs[p].tid, bytes(objs[p].b)))
    # ---- 2. 조건 컴포넌트 GameObject
    sib = Obj(sr, trees, 35)                                       # UnityEventStopSirenAudio 의 RectTransform (자식 없음) = 조건 GO 의 RectTransform 원본
    assert sib.val['m_Children.Array.size'] == 0
    struct.pack_into('<q', sib.b, sib.off['m_GameObject.m_PathID'][0], cond_go)
    struct.pack_into('<q', sib.b, sib.off['m_Father.m_PathID'][0], PANEL_RT); struct.pack_into('<i', sib.b, sib.off['m_Father.m_FileID'][0], 0)
    layer = Obj(sr, trees, PANEL_GO).val['m_Layer']
    gtid = sr.objects[P[DATE_GO]][3]
    mgo = make_go([cond_rt, cond_mb], layer, COND_NAME, True); tt.parse_bytes(trees[gtid], mgo)
    conds = {'prod': [(fid_cfg, NOTNIGHT_PID), (fid_cfg, cond_pid)], 'test_day': [(fid_cfg, NOTNIGHT_PID)], 'test_always': [], 'test_range': [(fid_cfg, cond_pid)]}[mode]
    if mode in ('prod', 'test_range'):
        assert cond_pid, 'cond_pid 필요'
    # ConditionalActiveGameObjects 바이트: 지도 화면의 템플릿 객체 앞부분(헤더+이름) + 새 배열 2개
    tb_ = bytearray(mcond.b); a0 = mcond.off['m_conditions.Array.size'][0]
    head = bytearray(tb_[:a0])
    struct.pack_into('<q', head, mcond.off['m_GameObject.m_PathID'][0], cond_go); struct.pack_into('<i', head, mcond.off['m_GameObject.m_FileID'][0], 0)
    struct.pack_into('<i', head, mcond.off['m_Script.m_FileID'][0], fid_map); struct.pack_into('<q', head, mcond.off['m_Script.m_PathID'][0], MAP_SCRIPT_LOCAL_ID)
    mb = bytes(head) + struct.pack('<i', len(conds)) + b''.join(struct.pack('<iq', f, p) for f, p in conds) + struct.pack('<i', 1) + struct.pack('<iq', 0, newp[DATE_GO])
    tt.parse_bytes(mtrees[mcond.tid], mb)                          # 새 타입(지도 화면의 같은 타입 트리)으로 레이아웃 검사
    # ---- 3. Panel 자식 목록
    panel = Obj(sr, trees, PANEL_RT); children_append_many(panel, [newp[34], cond_rt])
    append += [(cond_go, gtid, mgo), (cond_rt, sib.tid, bytes(sib.b)), (cond_mb, new_type_id, mb)]
    replace = {PANEL_RT: bytes(panel.b)}
    if exit_delay is not None:
        ex = Obj(sr, trees, EXIT_MB); assert ex.val['m_delay'] == EXIT_DELAY_ORIG and ex.val['m_duration'] == 0.25, 'WindowTransitionFadeExit 값이 원본과 다릅니다'
        ex.set('m_delay', float(exit_delay)); replace[EXIT_MB] = bytes(ex.b)
    new_ser = ed2.rebuild_ext(orig, replace=replace, append=append, new_externals=new_ext, new_types=new_types, new_scripts=new_scripts)
    info = {'scene': SCENE, 'mode': mode, 'text': text, 'objects_before': len(sr.objects), 'objects_after': len(sr.objects) + len(append), 'new_pids': [a[0] for a in append],
            'clone_map': {str(k): v for k, v in newp.items()}, 'notice_go': newp[DATE_GO], 'notice_rt': newp[34], 'notice_text_mb': newp[48], 'cond_go': cond_go, 'cond_rt': cond_rt, 'cond_mb': cond_mb,
            'panel_rt': PANEL_RT, 'panel_children_before': PANEL_CHILDREN_BEFORE, 'replaced': sorted(replace), 'exit_delay': exit_delay, 'types_before': len(sr.types), 'new_type_id': new_type_id, 'new_script_index': new_script_index,
            'new_scripts': [list(x) for x in new_scripts], 'externals_before': len(sr.externals), 'new_externals': new_ext, 'map_sharedassets_fid': fid_map, 'cfg_fid': fid_cfg,
            'conditions': [[f, p] for f, p in conds], 'cond_pid_new': cond_pid, 'notnight_pid': NOTNIGHT_PID, 'outward_references': sorted([list(map(str, t)) for t in outward]),
            'rect': {'pos': list(pos), 'size_y': size_y, 'font_size': font_size, 'color': list(color)}, 'type_entry_source': {'scene': MAP_SCENE, 'mb': MAP_COND_MB, 'type_id': mcond.tid},
            'src_scene_sha256': hashlib.sha256(orig).hexdigest(), 'new_scene_sha256': hashlib.sha256(new_ser).hexdigest()}
    return sb, orig, new_ser, info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['plan', 'build']); ap.add_argument('--src', required=True); ap.add_argument('--out'); ap.add_argument('--cond-pid', type=int, default=None)
    ap.add_argument('--mode', default='prod', choices=['prod', 'test_day', 'test_always', 'test_range']); ap.add_argument('--text', default=TEXT)
    ap.add_argument('--y', type=float, default=DEFAULT_POS[1]); ap.add_argument('--size', type=int, default=FONT_SIZE); ap.add_argument('--exit-delay', type=float, default=None)
    a = ap.parse_args(argv)
    sb, orig, new_ser, info = plan_build(a.src, a.cond_pid, a.mode, a.text, (0.0, a.y), DEFAULT_SIZE_Y, a.size, exit_delay=a.exit_delay)
    print('source %s (%d bytes, sha256 %s)' % (a.src, len(sb.raw), hashlib.sha256(sb.raw).hexdigest()[:16]))
    print('scene %s: %d -> %d bytes; objects %d -> %d (+%d); types +1 (id %d), scripts +1, externals +%d; notice GO %d, cond GO %d' % (SCENE, len(orig), len(new_ser), info['objects_before'], info['objects_after'], info['objects_after'] - info['objects_before'], info['new_type_id'], len(info['new_externals']), info['notice_go'], info['cond_go']))
    if a.cmd == 'plan':
        print('(plan only, nothing written)'); return 0
    if not a.out:
        ap.error('--out required')
    if in_game_folder(a.out):
        print('REFUSED: --out is inside the game folder'); return 2
    os.makedirs(a.out, exist_ok=True); out = ufs.write_bundle(sb, SCENE, new_ser, 'rebuild'); op = os.path.join(a.out, 'ui_screens')
    if os.path.abspath(op) == os.path.abspath(a.src):
        print('REFUSED: output would overwrite the source'); return 2
    open(op, 'wb').write(out); info.update({'out': op, 'sha256': hashlib.sha256(out).hexdigest(), 'src_sha256': hashlib.sha256(sb.raw).hexdigest(), 'size': len(out)})
    json.dump(info, open(op + '.build.json', 'w', encoding='utf8'), indent=1, ensure_ascii=False); print('wrote %s (%d bytes) sha256 %s' % (op, len(out), info['sha256'])); return 0


if __name__ == '__main__':
    sys.exit(main())
