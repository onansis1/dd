#!/usr/bin/env python
"""itdp_datenotice_cfg.py - 복사본 전용 도구: data_config 번들에 새 조건 오브젝트 IsCycleWithinRange(min=20, max=21)를 추가하고,
게임이 시작할 때 조건을 초기화하는 등록부(InitialisableScriptableObjectsConfig.m_initialisableConditions)에 그 PPtr 을 덧붙인다.

 - 새 오브젝트 = 기존 'IsCycleWitinRange_6-15'(68바이트)를 바이트 복제 -> 이름/ m_min / m_max 만 바꿈 (m_invert 0).
   IsCycleWithinRange.EvaluateInternal(0xCA1700) 은 min <= cyclesPassed <= max (양 끝 포함)이고, 초기화되지 않은(m_gameCycleModel 없음) 조건은 오류 로그 후 거짓을 돌려준다 (크래시 없음).
 - 등록부 갱신이 필요한 이유: 게임의 모든 사이클 조건(IsCycle 44 / IsCycleWithinRange 17 / IsCycleId 5, 전부 등록됨)은 이 목록에 들어 있어야 시작 때 GameCycleModel 이 주입된다. 목록에 없으면 항상 거짓.
 - 바뀌는 기존 객체는 등록부 하나뿐(배열 끝에 12바이트). 나머지 객체는 바이트 그대로.
Never writes into the game folder (refused)."""
import sys, os, json, struct, hashlib, argparse
HERE = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
_D = os.path.join(HERE, '..', 'deps')                         # 패키지 레이아웃(tools/ 옆의 deps/)이면 앱 itdp_* 스냅샷을 쓴다. 앱 폴더에 넣어 쓸 때는 필요 없음
if os.path.isdir(_D) and _D not in sys.path:
    sys.path.insert(0, _D)

import itdp_ufs as ufs, itdp_ser as S, itdp_tt as tt, itdp_edit2 as ed2
from itdp_build import Obj, in_game_folder


def open_bundle(path):
    """data_config 는 두 가지 UnityFS 배치가 있다: 원본(블록 정보가 헤더 뒤, itdp_ufs) / 앱이 다시 쓴 파일(블록 정보가 파일 끝, 플래그 0x80, itdp_ufs2). 둘 다 읽는다."""
    try:
        return ufs.Bundle(path)
    except AssertionError:
        import itdp_ufs2 as u2
        return u2.Bundle2(path)


def write_node(sb, node, new_bytes):
    if isinstance(sb, ufs.Bundle):
        return ufs.write_bundle(sb, node, new_bytes, 'rebuild')
    return sb.build(node, new_bytes, level=6)           # blocks-info-at-end 배치: 같은 배치로 다시 씀 (전체 재압축)


TEMPLATE_PID = 4719989157237761955         # IsCycleWitinRange_6-15 (m_invert 0, 6..15)
TEMPLATE_NAME = 'IsCycleWitinRange_6-15'
REGISTRY_PID = 7934266414914667133         # InitialisableScriptableObjectsConfig
REGISTRY_NAME = 'InitialisableScriptableObjectsConfig'
NOTNIGHT_PID = 1361094819312709118; NOTNIGHT_NAME = 'IsCycleId_NotNight'
CFG_CAB = 'CAB-e04823e81dec6fc2099bf567eba2f429'
NEW_NAME = 'DateNotice_Aug30_IsCycleWithinRange_20_21'
MIN_OBJECTS = 16000; MIN_REGISTRY_COND = 3000     # 앱의 다른 항목(상인 등)이 객체를 더하거나 등록부를 키웠을 수 있어 정확한 개수 대신 하한만 본다
INT64_MAX = 2 ** 63 - 1


def plan_build(src_path, cmin=20, cmax=21, name=NEW_NAME):
    assert 0 <= cmin <= cmax < 1 << 15, (cmin, cmax)
    sb = open_bundle(src_path); node = sb.nodes[0][3]; assert len(sb.nodes) == 1 and node == CFG_CAB, 'data_config 번들이 아닙니다: %r' % [n[3] for n in sb.nodes]
    orig = sb.node_data(node); sr = S.Ser(orig); trees = [tt.build_tree(t) for t in sr.types]; P = sr.by_pid()
    assert len(sr.objects) >= MIN_OBJECTS, 'data_config 객체 수 %d (게임이 업데이트되었거나 data_config 가 아닙니다)' % len(sr.objects)
    tmpl = Obj(sr, trees, TEMPLATE_PID); assert tmpl.val['m_Name'] == TEMPLATE_NAME and tmpl.val['m_min'] == 6 and tmpl.val['m_max'] == 15 and tmpl.val['m_invert'] == 0, 'IsCycleWithinRange 템플릿이 달라졌습니다'
    assert sr.types[tmpl.tid].class_id == 114
    nn = Obj(sr, trees, NOTNIGHT_PID); assert nn.val['m_Name'] == NOTNIGHT_NAME and nn.val['m_invert'] == 1, 'IsCycleId_NotNight 가 달라졌습니다'
    reg = Obj(sr, trees, REGISTRY_PID); assert reg.val['m_Name'] == REGISTRY_NAME
    n = reg.val['m_initialisableConditions.Array.size']; assert n >= MIN_REGISTRY_COND, n
    # 새 pid: 최대 pid + 1 (int64 범위 확인, 중복 없음)
    new_pid = max(o[0] for o in sr.objects) + 1
    assert new_pid <= INT64_MAX and new_pid not in P, new_pid
    # 이미 같은 이름의 오브젝트가 있으면 중복 생성 금지
    for o in sr.objects:
        if o[3] == tmpl.tid:
            assert Obj(sr, trees, o[0]).val['m_Name'] != name, '이미 같은 이름의 조건이 있습니다 (두 번 만들지 않음)'
    # 새 오브젝트
    obj = Obj(sr, trees, TEMPLATE_PID); obj.set_str('m_Name', name); obj.set('m_min', int(cmin)); obj.set('m_max', int(cmax))
    lv = tt.parse_bytes(obj.root, bytes(obj.b)); vals = {p: v for p, o, t, v in lv}
    assert vals['m_Name'] == name and vals['m_min'] == cmin and vals['m_max'] == cmax and vals['m_invert'] == 0
    # 등록부: 조건 배열 끝에 (0, new_pid) 덧붙임 (다음 잎 = m_initialisableActions.Array.size 바로 앞)
    a0 = reg.off['m_initialisableConditions.Array.size'][0]; ins = a0 + 4 + 12 * n
    assert ins == reg.off['m_initialisableActions.Array.size'][0], '등록부 배열 레이아웃이 예상과 다릅니다'
    rb = bytearray(reg.b); struct.pack_into('<i', rb, a0, n + 1); rb[ins:ins] = struct.pack('<iq', 0, new_pid)
    tt.parse_bytes(reg.root, bytes(rb))
    new_ser = ed2.rebuild_ext(orig, replace={REGISTRY_PID: bytes(rb)}, append=[(new_pid, tmpl.tid, bytes(obj.b))])
    info = {'bundle': 'data_config', 'node': node, 'objects_before': len(sr.objects), 'objects_after': len(sr.objects) + 1, 'new_pid': new_pid, 'new_name': name, 'min': cmin, 'max': cmax, 'type_id': tmpl.tid,
            'template_pid': TEMPLATE_PID, 'registry_pid': REGISTRY_PID, 'registry_cond_before': n, 'registry_cond_after': n + 1, 'replaced': [REGISTRY_PID], 'notnight_pid': NOTNIGHT_PID,
            'src_node_sha256': hashlib.sha256(orig).hexdigest(), 'new_node_sha256': hashlib.sha256(new_ser).hexdigest()}
    return sb, orig, new_ser, info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['plan', 'build']); ap.add_argument('--src', required=True); ap.add_argument('--out'); ap.add_argument('--min', type=int, default=20); ap.add_argument('--max', type=int, default=21)
    a = ap.parse_args(argv)
    sb, orig, new_ser, info = plan_build(a.src, a.min, a.max)
    print('source %s (%d bytes, sha256 %s)' % (a.src, len(sb.raw), hashlib.sha256(sb.raw).hexdigest()[:16]))
    print('data_config node: %d -> %d bytes; objects %d -> %d; new pid %d; registry conditions %d -> %d' % (len(orig), len(new_ser), info['objects_before'], info['objects_after'], info['new_pid'], info['registry_cond_before'], info['registry_cond_after']))
    if a.cmd == 'plan':
        print('(plan only, nothing written)'); return 0
    if not a.out:
        ap.error('--out required')
    if in_game_folder(a.out):
        print('REFUSED: --out is inside the game folder'); return 2
    os.makedirs(a.out, exist_ok=True); out = write_node(sb, info['node'], new_ser); op = os.path.join(a.out, 'data_config')
    if os.path.abspath(op) == os.path.abspath(a.src):
        print('REFUSED: output would overwrite the source'); return 2
    open(op, 'wb').write(out); info.update({'out': op, 'sha256': hashlib.sha256(out).hexdigest(), 'src_sha256': hashlib.sha256(sb.raw).hexdigest(), 'size': len(out)})
    json.dump(info, open(op + '.build.json', 'w', encoding='utf8'), indent=1, ensure_ascii=False); print('wrote %s (%d bytes) sha256 %s' % (op, len(out), info['sha256'])); return 0


if __name__ == '__main__':
    sys.exit(main())
