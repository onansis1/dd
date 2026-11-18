"""Into the Dead: Our Darkest Days - 날짜 안내 화면(NewCycleScreen)에 '발걸음 소리를 켜세요' 문구를 추가한다 (일반판 전용, 이 게임 빌드 전용; 코드(GameAssembly.dll) 무변경).
사용: python patch_datenotice.py <작업 폴더> [mode] [min max [exit_delay]]   (exit_delay: 선택. 카드가 닫히기 시작하기까지의 대기(원본 2.0초)를 바꾼다 -> 모든 날짜 카드에 적용되므로 기본은 바꾸지 않음)
   작업 폴더 안의 ui_screens, data_config 를 제자리에서 고친다 (원본은 호출하는 쪽이 백업해 둔다. 앱은 항상 원본 백업에서 다시 계산한다).
 mode  prod (기본) : 게임 속 8월 30일 낮(경과 일 수 10, cyclesPassed 20~21 중 낮)에만 보인다.
       test_day    : 모든 낮에 보인다 (조건 평가/초기화 시험, data_config 는 건드리지 않음)
       test_always : 항상 보인다 (컴포넌트/글꼴/위치 시험, data_config 는 건드리지 않음)
       test_range  : [min, max] 사이클에서 보인다 (예: 2 3 = 둘째 날 낮, 새 조건과 등록부 시험)
       test_probe_a / test_b / test_c1 / test_c2 / test_d / test_e / test_e_day : "referenced script ... is missing" 원인 가르기용 시험 변형 (ui_screens 만; 설명은 itdp_datenotice_var.py 맨 위와 README_variants.md). 한 번에 하나만 적용.
 - data_config: 새 조건 IsCycleWithinRange(min=20, max=21) 1개 추가 + 초기화 등록부(InitialisableScriptableObjectsConfig)에 1항목 (기존 객체 중 바뀌는 것은 등록부 하나뿐).
 - ui_screens : BuildPlayer-NewCycleCard 장면에 글자 오브젝트(복제) + 조건 컴포넌트 오브젝트 추가 (기존 객체 중 바뀌는 것은 Panel RectTransform 하나뿐). 다른 노드(지도 패널, 시나리오 버튼 포함)는 바이트 그대로.
 - 쓰기 전에 두 번들 검증(구조/참조/계층/UnityPy 재파싱)을 통과해야 한다. 하나라도 실패하면 아무것도 바꾸지 않는다.
 - 지도 패널(patch_panelbundle)/시나리오 버튼(patch_scnbtn) 적용 전/후 어느 순서로 해도 된다 (서로 다른 장면 노드를 고친다)."""
import hashlib, json, os, shutil, sys, tempfile

HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
_D = os.path.join(HERE, '..', 'deps')                         # 패키지 레이아웃(tools/ 옆의 deps/)이면 앱 itdp_* 스냅샷을 쓴다. 앱 폴더에 넣어 쓸 때는 필요 없음
if os.path.isdir(_D) and _D not in sys.path:
    sys.path.insert(0, _D)



def is_applied(ui_path):
    import itdp_ufs as ufs, itdp_ser as S, itdp_tt as tt
    from itdp_build import Obj
    import itdp_datenotice as N
    sb = ufs.Bundle(ui_path); sr = S.Ser(sb.node_data(N.SCENE)); trees = [tt.build_tree(t) for t in sr.types]
    from itdp_scn import class_of, CLS
    return any(class_of(sr, p) == CLS['GO'] and Obj(sr, trees, p).val['m_Name'] in (N.NEW_NAME, N.COND_NAME) for p in sr.by_pid())


VARIANT_MODES = {"test_probe_a": "probe_a", "test_b": "b", "test_c1": "c1", "test_c2": "c2", "test_d": "d", "test_e": "e", "test_e_day": "e_day"}


def apply_variant(stage, variant, write=True):
    """원인 가르기용 시험 변형 (itdp_datenotice_var). ui_screens 만 고친다 (c2/e 는 같은 번들 안의 NewCycleCard.sharedAssets 도). 검증 실패 시 아무것도 바꾸지 않는다."""
    import itdp_datenotice_var as VAR, itdp_datenotice_varverify as VV
    ui = os.path.join(stage, "ui_screens")
    tmp = tempfile.mkdtemp(prefix="itd_datenotice_var_")
    try:
        try:
            sb, nodes, info = VAR.plan_variant(ui, variant)
        except Exception as e:
            sys.exit("중단: 시험 변형 %s 을 만들 수 없습니다 (게임 업데이트로 구조가 달라졌거나 이미 편집된 파일일 수 있습니다): %r. 아무것도 바꾸지 않았습니다." % (variant, e))
        out = VAR.write_variant(sb, nodes); ui_new = os.path.join(tmp, "ui_screens.new"); open(ui_new, "wb").write(out)
        info.update({"out": ui_new, "sha256": hashlib.sha256(out).hexdigest(), "src_sha256": hashlib.sha256(sb.raw).hexdigest(), "size": len(out)})
        R = VV.verify_variant(ui, ui_new, info)
        if R.fails():
            sys.exit("중단: 변형 %s 검증에 실패했습니다. 아무것도 바꾸지 않았습니다.\n" % variant + "\n".join("%s -> %s" % (n, note) for n, ok, note in R.fails()[:8]))
        if write:
            import gc; gc.collect()
            shutil.copyfile(ui_new, ui + ".out"); os.replace(ui + ".out", ui)
        return {"ui": info, "cfg": None, "variant": variant}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def apply(stage, mode="prod", cmin=20, cmax=21, write=True, exit_delay=None):
    """returns dict(info...). 실패하면 SystemExit(메시지) — 파일은 바뀌지 않는다."""
    import itdp_ufs as ufs, itdp_datenotice as N, itdp_datenotice_cfg as C, itdp_datenotice_verify as V
    ui = os.path.join(stage, "ui_screens"); cfgp = os.path.join(stage, "data_config")
    if not os.path.isfile(ui):
        sys.exit("ui_screens 를 찾을 수 없습니다: %s" % ui)
    need_cfg = mode in ("prod", "test_range")
    if need_cfg and not os.path.isfile(cfgp):
        sys.exit("data_config 를 찾을 수 없습니다: %s" % cfgp)
    if is_applied(ui):
        print("날짜 안내 문구: 이미 적용되어 있습니다."); return {"already": True}
    if mode in VARIANT_MODES:
        return apply_variant(stage, VARIANT_MODES[mode], write)
    tmp = tempfile.mkdtemp(prefix="itd_datenotice_")
    try:
        cfg_info = None; cfg_new = None
        if need_cfg:
            try:
                sbc, origc, new_ser_c, cfg_info = C.plan_build(cfgp, cmin, cmax)
            except Exception as e:
                sys.exit("중단: data_config 에 날짜 조건을 만들 수 없습니다 (게임 업데이트로 구조가 달라졌거나 이미 추가된 파일일 수 있습니다): %r. 아무것도 바꾸지 않았습니다." % (e,))
            outc = C.write_node(sbc, cfg_info["node"], new_ser_c); cfg_new = os.path.join(tmp, "data_config.new"); open(cfg_new, "wb").write(outc)
            cfg_info.update({"out": cfg_new, "sha256": hashlib.sha256(outc).hexdigest(), "src_sha256": hashlib.sha256(sbc.raw).hexdigest(), "size": len(outc)})
            R = V.verify_cfg(cfgp, cfg_new, cfg_info)
            if R.fails():
                sys.exit("중단: data_config 검증에 실패했습니다. 아무것도 바꾸지 않았습니다.\n" + "\n".join("%s -> %s" % (n, note) for n, ok, note in R.fails()[:8]))
        cond_pid = cfg_info["new_pid"] if cfg_info else None
        try:
            sb, orig, new_ser, info = N.plan_build(ui, cond_pid, mode, exit_delay=exit_delay)
        except Exception as e:
            sys.exit("중단: 날짜 안내 문구를 만들 수 없습니다 (게임 업데이트로 ui_screens 구조가 달라졌을 수 있습니다): %r. 아무것도 바꾸지 않았습니다." % (e,))
        out = ufs.write_bundle(sb, N.SCENE, new_ser, "rebuild"); ui_new = os.path.join(tmp, "ui_screens.new"); open(ui_new, "wb").write(out)
        info.update({"out": ui_new, "sha256": hashlib.sha256(out).hexdigest(), "src_sha256": hashlib.sha256(sb.raw).hexdigest(), "size": len(out)})
        R = V.verify_ui(ui, ui_new, info, cfgp if cfg_new else None, cfg_new, True)
        if R.fails():
            sys.exit("중단: ui_screens 검증에 실패했습니다. 아무것도 바꾸지 않았습니다.\n" + "\n".join("%s -> %s" % (n, note) for n, ok, note in R.fails()[:8]))
        if write:
            # 검증에서 UnityPy 가 임시 파일을 붙잡고 있을 수 있어(Windows) 이동 대신 복사한 뒤, 두 파일을 모두 준비해 놓고 한꺼번에 교체한다
            import gc; gc.collect()
            pairs = [(ui_new, ui)] + ([(cfg_new, cfgp)] if cfg_new else [])
            for src, dst in pairs:
                shutil.copyfile(src, dst + ".out")
            for src, dst in pairs:
                os.replace(dst + ".out", dst)
        return {"ui": info, "cfg": cfg_info}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    mode = sys.argv[2] if len(sys.argv) > 2 else "prod"
    if mode not in ("prod", "test_day", "test_always", "test_range", "test_static") + tuple(VARIANT_MODES):
        sys.exit("mode 는 prod / test_day / test_always / test_range / %s 중 하나: %r" % (" / ".join(VARIANT_MODES), mode))
    cmin, cmax = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (20, 21)
    exit_delay = float(sys.argv[5]) if len(sys.argv) > 5 else None
    r = apply(sys.argv[1], mode, cmin, cmax, exit_delay=exit_delay)
    if r.get("already"):
        return
    u = r["ui"]
    print("날짜 안내 문구 추가 (%s): ui_screens 새 오브젝트 %d개 (장면 %d -> %d개) + data_config %s, 번들 검증 완료." % (
        mode, len(u["new_pids"]), u["objects_before"], u["objects_after"],
        ("조건 1개(min=%d, max=%d) + 등록부 1항목" % (r["cfg"]["min"], r["cfg"]["max"])) if r["cfg"] else "변경 없음"))


if __name__ == "__main__":
    main()
