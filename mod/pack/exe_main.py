"""PyInstaller 진입점. exe 하나로 메뉴(launcher)와 하위 스크립트 실행(--run-script)을 모두 처리한다."""
import argparse, hashlib, json, math, os, random, re, runpy, shutil, struct, subprocess, sys, tempfile  # 하위 스크립트가 쓰는 표준 모듈을 번들에 포함
import lz4.block  # noqa  (preset_tool 이 세이브 압축을 풀 때 사용)
import UnityPy, UnityPy.helpers.TypeTreeHelper, UnityPy.helpers.TypeTreeNode, UnityPy.streams, UnityPy.files  # noqa
for _st in (sys.stdout, sys.stderr, sys.stdin):   # 파이프/리다이렉트일 때 cp1252 등으로 한글이 깨지거나 죽는 것 방지
    try:
        if _st is not None and (_st.encoding or "").lower().replace("-", "") != "utf8":
            _st.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
try:
    import winreg  # noqa
except ImportError:
    pass

if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    need = ["apply_all.py", "launcher.py", "patch_balance.py", "patch_config.py", "widen_map_radius.py", "shuffle_map.py", "scan_telescopes.py", "preset_tool.py", "patch_leads.py", "patch_traders.py", "add_trading_posts.py", "patch_romance.py", "patch_romance_compat.py", "patch_zombie.py", "patch_noise.py", "patch_hod.py", "patch_june.py", "patch_hod_shelters.py", "patch_repair.py", "patch_peek.py", "patch_traits.py", "patch_skills.py", "patch_cleared.py", "patch_wheelgold.py", "patch_shelter.py", "patch_randstart.py", "patch_panelbundle.py", "patch_loclabel.py", "patch_scnbtn.py", "itd_fastload.py", "patch_rsmask.py", "itdp_scn.py", "itdp_scnverify.py", "patch_panelcode.py", "itdp_build.py", "itdp_ufs.py", "itdp_ser.py", "itdp_tt.py", "itdp_edit.py", "itdp_verify.py", "panel_code.json", "panel_spec.json", "panel_sprites.json", "patch_otto.py", "patch_unarmedsound.py", "patch_ammolevel.py", "patch_lootnote.py", "lootnotes.json", "telescopes.json", "gui_app.py", "assets/bg_map.png", "assets/bg_full.png", "assets/BusanDandiGothicM.ttf"]
    try:
        import tkinter, gui_app  # noqa
    except Exception as e:
        print("GUI 모듈 오류:", repr(e)); sys.exit(1)
    miss = [n for n in need if not os.path.exists(os.path.join(base, n))]
    print("UnityPy", getattr(UnityPy, "__version__", "?"), "| 누락 파일:", miss or "없음")
    sys.exit(1 if miss else 0)
elif len(sys.argv) > 2 and sys.argv[1] == "--run-script":
    script = sys.argv[2]
    sys.argv = [script] + sys.argv[3:]
    try:
        import itd_fastload
        itd_fastload.apply()          # UnityPy 가 번들을 열 때마다 AssetBundle 경로 목록을 통째로 파싱하는 시간(단계당 약 10초)을 건너뜀
    except Exception:
        pass
    runpy.run_path(script, run_name="__main__")
elif len(sys.argv) > 2 and sys.argv[1] == "--preset-menu":
    import launcher, preset_tool  # noqa
    try:
        preset_tool.menu(sys.argv[2], launcher.game_running)
    except KeyboardInterrupt:
        pass
    launcher.pause()
else:
    import multiprocessing
    multiprocessing.freeze_support()
    import launcher, preset_tool  # noqa
    if True:   # 창 + 버튼 (지도 전용판은 고정 적용, 일반판은 항목 선택)
        if not launcher.MAPONLY and os.name == "nt":   # 일반판은 콘솔 exe 라서 검은 창을 숨김 (프리셋 도구는 새 콘솔로 띄움)
            try:
                import ctypes
                _h = ctypes.windll.kernel32.GetConsoleWindow()
                if _h:
                    ctypes.windll.user32.ShowWindow(_h, 0)
            except Exception:
                pass
        import gui_app
        try:
            gui_app.main()
        except Exception as e:
            try:
                import tkinter.messagebox as mb
                mb.showerror("오류", "예상치 못한 오류: %r" % (e,))
            except Exception:
                pass
        sys.exit(0)
    try:
        launcher.main()
    except KeyboardInterrupt:
        print("\n중단했습니다.")
    except Exception as e:
        print("\n예상치 못한 오류: %r" % (e,))
    launcher.pause()
