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
    need = ["apply_all.py", "launcher.py", "patch_balance.py", "patch_config.py", "widen_map_radius.py", "shuffle_map.py", "scan_telescopes.py", "preset_tool.py", "patch_leads.py", "patch_traders.py", "telescopes.json"]
    miss = [n for n in need if not os.path.exists(os.path.join(base, n))]
    print("UnityPy", getattr(UnityPy, "__version__", "?"), "| 누락 파일:", miss or "없음")
    sys.exit(1 if miss else 0)
elif len(sys.argv) > 2 and sys.argv[1] == "--run-script":
    script = sys.argv[2]
    sys.argv = [script] + sys.argv[3:]
    runpy.run_path(script, run_name="__main__")
else:
    import multiprocessing
    multiprocessing.freeze_support()
    import launcher, preset_tool  # noqa
    try:
        launcher.main()
    except KeyboardInterrupt:
        print("\n중단했습니다.")
    except Exception as e:
        print("\n예상치 못한 오류: %r" % (e,))
    launcher.pause()
