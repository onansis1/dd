"""사용자 지정 시나리오 화면에 새 버튼 '무술가 포함 뽑기'를 추가한다 (ui_screens 번들의 BuildPlayer-ScenarioSettings 장면 + loc 번들의 라벨 한 키).
사용: python patch_scnbtn.py <작업 폴더>   (작업 폴더 안의 ui_screens, loc.korean, loc.english 를 제자리에서 고친다. 원본은 호출하는 쪽이 백업해 둔다)
 - [시작] 버튼(ConfirmButton) 서브트리를 복제해 왼쪽에 새 버튼을 둔다. 새 버튼의 클릭 = 표식 오브젝트 켜기 -> 클릭음 -> 기존 StartGameWithParameters.
   표식은 patch_randstart.py 의 동굴이 읽는다(읽은 즉시 끔). 화면이 열릴 때마다 표식은 꺼진다.
 - 라벨은 게임에서 쓰이지 않는 번역 키 LABEL_STATE_AND_TYPE 의 값을 바꿔 쓴다 (한국어 '무술가 포함 뽑기', 영어 'Start with Martial Artist').
 - 쓰기 전에 번들 검증(23개 항목)을 통과해야 한다. 실패하면 아무것도 바꾸지 않는다.
"""
import contextlib, hashlib, io, json, os, shutil, sys, tempfile
HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

KEY = "LABEL_STATE_AND_TYPE"
LABELS = {"loc.korean": ("[KOR] State - {0}", "무술가 포함 뽑기"), "loc.english": ("State - {0}", "Start with Martial Artist")}


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    stage = sys.argv[1]
    import itdp_scn as B, itdp_scnverify as V, itdp_ufs as ufs
    import patch_lootnote as L
    src = os.path.join(stage, "ui_screens")
    if not os.path.isfile(src):
        sys.exit("ui_screens 를 찾을 수 없습니다: %s" % src)
    # 1) 라벨 값 (먼저 읽어서 예상과 다르면 아무것도 바꾸지 않는다)
    locs = {}
    for fn, (old, new) in LABELS.items():
        p = os.path.join(stage, fn)
        if not os.path.isfile(p):
            sys.exit("%s 를 찾을 수 없습니다: %s" % (fn, p))
        data = open(p, "rb").read()
        _, strs = L.unityfs_objects(data)
        if not strs or KEY not in strs:
            sys.exit("중단: %s 에서 번역 키 %s 를 찾지 못했습니다 (게임 버전이 달라졌을 수 있습니다). 아무것도 바꾸지 않았습니다." % (fn, KEY))
        if strs[KEY] not in (old, new):
            sys.exit("중단: %s 의 %s 값이 예상('%s')과 다릅니다(%r). 아무것도 바꾸지 않았습니다." % (fn, KEY, old, strs[KEY]))
        locs[fn] = (data, strs)
    # 2) 번들: 장면에 버튼 추가
    try:
        sb, orig, new_ser, info = B.plan_build(src, KEY, "Start with Martial Artist")
    except Exception as e:
        sys.exit("중단: 무술가 포함 뽑기 버튼을 만들 수 없습니다 (게임 업데이트로 ui_screens 구조가 달라졌거나 이미 추가된 파일일 수 있습니다): %r. 아무것도 바꾸지 않았습니다." % (e,))
    out = ufs.write_bundle(sb, B.SCENE, new_ser, "rebuild")
    tmp = tempfile.mkdtemp(prefix="itd_scn_")
    try:
        outp = os.path.join(tmp, "ui_screens.new")
        open(outp, "wb").write(out)
        info.update({"out": outp, "mode": "rebuild", "sha256": hashlib.sha256(out).hexdigest(), "src_sha256": hashlib.sha256(sb.raw).hexdigest(), "size": len(out)})
        R = V.verify_bundles(src, outp, info, False)
        fails = [n + (("  -> " + note) if note else "") for n, ok, note in R if not ok]
        if fails:
            sys.exit("중단: 무술가 포함 뽑기 버튼 번들 검증에 실패했습니다. 아무것도 바꾸지 않았습니다.\n" + "\n".join(fails[:8]))
        # 3) 라벨 편집
        newloc = {}
        for fn, (old, new) in LABELS.items():
            data, strs = locs[fn]
            if strs[KEY] == new:
                continue
            nb, changed = L.edit_bundle(data, {KEY: new})
            assert changed == 1, changed
            _, back = L.unityfs_objects(nb)
            want = dict(strs); want[KEY] = new
            if back != want:
                sys.exit("중단: %s 편집 결과 검증에 실패했습니다. 아무것도 바꾸지 않았습니다." % fn)
            newloc[fn] = nb
        os.replace(outp, src + ".out")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    os.replace(src + ".out", src)
    for fn, nb in newloc.items():
        open(os.path.join(stage, fn + ".new"), "wb").write(nb)
        os.replace(os.path.join(stage, fn + ".new"), os.path.join(stage, fn))
    print("사용자 지정 시나리오 화면에 '무술가 포함 뽑기' 버튼 추가: 새 오브젝트 %d개, 라벨 '무술가 포함 뽑기' (번들 검증 완료)." % (info["objects_after"] - info["objects_before"]))


if __name__ == "__main__":
    main()
