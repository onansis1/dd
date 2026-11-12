"""Into the Dead: Our Darkest Days - 지도 화면에 '탐색 생존자 패널'(UI)을 추가한다 (ui_screens 번들의 BuildPlayer-MapScreen 장면 수정, 이 게임 빌드 전용).
사용: python patch_panelbundle.py <작업 폴더>   (작업 폴더 안의 ui_screens 를 제자리에서 고친다. 원본은 호출하는 쪽이 백업해 둔다)
 - 지도 화면(MapHud) 아래에 패널 UI 오브젝트(열기/닫기 버튼, 탭 5개, 탭별 패널의 생존자 줄(얼굴 + 이름 + 특성 칸))를 새로 만든다. 줄/칸은 처음에 전부 꺼져 있고,
   지도를 열 때 patch_panelcode.py 가 넣은 코드가 지금 내 은신처 생존자와 그들의 특성에 맞는 줄/칸만 켠다. 버튼과 탭은 번들 안의 'GameObject.SetActive' 호출만 쓴다(코드 없음).
 - 기존 장면 오브젝트 중 바뀌는 것은 MapHud 의 RectTransform(자식 목록) 하나뿐이다. 번들의 나머지 노드는 바이트 그대로다.
 - 쓴 뒤 검증기(itdp_verify)로 번들 구조/참조/계층/버튼 호출을 전부 확인하고, 하나라도 실패하면 아무것도 바꾸지 않는다.
 - 이 게임 빌드의 ui_screens 에서만 동작한다 (구조가 다르면 아무것도 바꾸지 않고 중단한다).
"""
import hashlib, io, json, os, sys, tempfile, contextlib

HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import itdp_build as B
import itdp_ufs as ufs
import itdp_verify as V


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    stage = sys.argv[1]
    src = os.path.join(stage, "ui_screens")
    if not os.path.isfile(src):
        sys.exit("ui_screens 를 찾을 수 없습니다: %s" % src)
    spec = json.load(open(os.path.join(HERE, "panel_spec.json"), encoding="utf-8"))
    try:
        sb, orig, new_ser, info = B.plan_build(src, spec)
    except Exception as e:
        sys.exit("중단: 지도 패널을 만들 수 없습니다 (게임 업데이트로 ui_screens 구조가 달라졌을 수 있습니다): %r. 아무것도 바꾸지 않았습니다." % (e,))
    out = ufs.write_bundle(sb, B.SCENE, new_ser, "rebuild")
    tmp = tempfile.mkdtemp(prefix="itd_panel_")
    try:
        outp = os.path.join(tmp, "ui_screens.new")
        open(outp, "wb").write(out)
        info.update({"out": outp, "mode": "rebuild", "sha256": hashlib.sha256(out).hexdigest(), "src_sha256": hashlib.sha256(sb.raw).hexdigest(), "size": len(out)})
        infop = os.path.join(tmp, "build.json")
        json.dump(info, open(infop, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        specp = os.path.join(tmp, "spec.json")
        json.dump(spec, open(specp, "w", encoding="utf-8"))
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = V.main(["--orig", src, "--new", outp, "--info", infop, "--spec", specp])
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
        text = buf.getvalue()
        fails = [l for l in text.splitlines() if l.startswith("FAIL")]
        if fails or (rc not in (0, None)):
            sys.exit("중단: 지도 패널 번들 검증에 실패했습니다. 아무것도 바꾸지 않았습니다.\n" + "\n".join(fails[:8]))
        os.replace(outp, src + ".out")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    os.replace(src + ".out", src)
    print("지도 탐색 생존자 패널(UI) 추가: 새 오브젝트 %d개 (장면 %d -> %d개), 번들 검증 완료." % (len(info["new_pids"]), info["objects_before"], info["objects_after"]))


if __name__ == "__main__":
    main()
