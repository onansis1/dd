"""Into the Dead: Our Darkest Days - 지도 랜덤 배치 + 탐색 반경 x1.5 (공유용 간편 실행기).
메뉴에서 번호만 고르면 됩니다. 게임 폴더는 자동으로 찾고, 못 찾으면 직접 붙여넣게 합니다.
"""
import json, os, re, subprocess, sys

FROZEN = getattr(sys, "frozen", False)
HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
GAME = "Into the Dead Our Darkest Days"

def _opts_path():
    root = os.path.dirname(sys.executable) if FROZEN else HERE
    return os.path.join(root, "launcher_options.json")

def load_opts():
    try:
        with open(_opts_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_opts(o):
    try:
        with open(_opts_path(), "w", encoding="utf-8") as f:
            json.dump(o, f, ensure_ascii=False, indent=1)
    except OSError:
        pass

def yn(q, default):
    s = input("%s [%s]: " % (q, "Y/n" if default else "y/N")).strip().lower()
    return default if not s else s in ("y", "yes", "ㅇ")

def pause():
    try: input("\n엔터를 누르면 닫힙니다...")
    except EOFError: pass

def steam_libraries():
    libs = []
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    for v in ("SteamPath", "InstallPath"):
                        try: libs.append(winreg.QueryValueEx(k, v)[0])
                        except OSError: pass
            except OSError: pass
    except ImportError:
        pass
    for p in (r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"):
        libs.append(p)
    extra = []
    for l in libs:
        vdf = os.path.join(l, "steamapps", "libraryfolders.vdf")
        try:
            txt = open(vdf, encoding="utf-8", errors="ignore").read()
            extra += [m.replace("\\\\", "\\") for m in re.findall(r'"path"\s+"([^"]+)"', txt)]
        except OSError: pass
    out, seen = [], set()
    for l in libs + extra:
        n = os.path.normpath(l)
        if n.lower() not in seen: seen.add(n.lower()); out.append(n)
    return out

def find_ab():
    for lib in steam_libraries():
        root = os.path.join(lib, "steamapps", "common", GAME)
        if not os.path.isdir(root): continue
        for dp, dn, fn in os.walk(root):
            if os.path.basename(dp) == "AssetBundles" and "data_levels" in fn:
                return dp
            if dp.count(os.sep) - root.count(os.sep) > 4: dn[:] = []
    return None

def ask_ab():
    print("게임 폴더를 자동으로 찾지 못했습니다.")
    print(r"스팀 > 게임 우클릭 > 관리 > 로컬 파일 탐색 으로 연 뒤, ...\StreamingAssets\AssetBundles 폴더 경로를 붙여넣으세요.")
    while True:
        p = input("AssetBundles 경로 (취소: 엔터): ").strip().strip('"')
        if not p: return None
        if os.path.isfile(os.path.join(p, "data_levels")): return p
        print("그 폴더에 data_levels 파일이 없습니다. 다시 입력하세요.")

def game_running():
    try:
        out = subprocess.run(["tasklist"], capture_output=True, text=True, errors="ignore").stdout
        return "intothedead" in out.lower()
    except Exception:
        return False

def ensure_unitypy():
    if FROZEN: return True
    try:
        import UnityPy  # noqa
        return True
    except Exception:
        pass
    print("필요한 구성요소(UnityPy)를 설치합니다. 인터넷이 필요하고 1분 정도 걸립니다...")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "UnityPy==1.25.3"])
    if r.returncode != 0:
        print("설치에 실패했습니다. 인터넷 연결을 확인하거나 명령 프롬프트에서  pip install UnityPy==1.25.3  를 직접 실행해 보세요.")
        return False
    return True

def main():
    print("=== Into the Dead: Our Darkest Days 간편 도구 (지도 랜덤 배치 + 반경 x1.5 / 시나리오 프리셋) ===\n")
    if not os.path.exists(os.path.join(HERE, "apply_all.py")):
        print("apply_all.py 가 같은 폴더에 있어야 합니다. 압축을 완전히 푼 뒤 실행하세요 (exe 는 이 문제가 없습니다)."); return
    ab = find_ab()
    if ab: print("게임 폴더를 찾았습니다:\n  " + ab + "\n")
    else:
        ab = ask_ab()
        if not ab: print("취소했습니다."); return
    print("1) 적용 (항목을 골라서)   * 새 게임 시작 전에만!   - 탐색 반경 x1.5 는 항상 포함")
    print("2) 적용 - 시드 지정 (같은 숫자면 같은 지도, 친구와 같은 지도로 하고 싶을 때)")
    print("3) 원래대로 되돌리기")
    print("4) 사용자 지정 시나리오 프리셋 (내 설정 저장 / 게임의 프리셋 칸에 넣기)")
    print("0) 종료")
    c = input("\n번호: ").strip()
    if c == "4":
        if not ensure_unitypy(): return
        import preset_tool
        preset_tool.menu(ab, game_running)
        return
    if c not in ("1", "2", "3"): return
    if game_running():
        print("\n게임이 실행 중입니다. 게임과 스팀을 완전히 끄고 다시 실행하세요."); return
    args = []
    if c == "3":
        args = ["--restore"]
    else:
        if c == "2":
            s = input("시드 숫자 (예: 12345): ").strip()
            if not s.isdigit(): print("숫자만 입력하세요."); return
            args += ["--seed", s]
        print("\n주의: 새 게임을 시작하기 전에만 사용하세요. 진행 중인 세이브에는 쓰지 마세요 (지도가 바뀝니다).")
        print("\n적용할 항목을 고르세요. (엔터 = [ ] 안의 기본값, 기본값은 지난번에 고른 것)")
        print("!! 이 도구는 항상 원본에서 다시 계산합니다. 이번에 'n' 으로 둔 항목은, 전에 적용했더라도 원래대로 돌아갑니다.")
        o = load_opts()
        o["map"] = yn("지도 건물 위치 랜덤 섞기", o.get("map", True))
        o["bal"] = yn("총알 산출량 x5 / 생존자 가방 24칸 / 지도 스테이션 2칸 / 시체 회수 24칸 / 미스터 베일 신규 품목 순서", o.get("bal", False))
        if o["bal"]:
            s = input("미스터 베일의 첫 석궁/샷건이 열리는 시점 - 0=게임 시작부터, 10, 20=원래 [%s]: " % o.get("vale_start", 20)).strip()
            o["vale_start"] = int(s) if s in ("0", "10", "20") else o.get("vale_start", 20)
        o["leads"] = yn("탈출 퀘스트를 열기 위한 조사 장소(단서) 3곳 -> 1곳", o.get("leads", False))
        o["traders"] = yn("상인(마와 파/베일/리키)이 처음 나오는 시점을 사이클 10 -> 게임 시작부터로 앞당기기", o.get("traders", False))
        save_opts(o)
        if not o["bal"]: args += ["--only-map"]
        if not o["map"]: args += ["--no-shuffle"]
        if o["leads"]: args += ["--leads", "1"]
        if o["traders"]: args += ["--trader-start", "0"]
        if o["bal"] and o.get("vale_start", 20) != 20: args += ["--vale-start", str(o["vale_start"])]
        print("\n이번에 적용: 탐색 반경 x1.5" + (" / 지도 섞기" if o["map"] else "") + (" / 총알·가방·스테이션·시체·베일" if o["bal"] else "") + (" / 탈출 단서 1곳" if o["leads"] else "") + (" / 상인 조기 등장" if o["traders"] else ""))
    if input("진행할까요? (y/n): ").strip().lower() != "y": print("취소했습니다. 아무것도 바꾸지 않았습니다."); return
    if c != "3" and not ensure_unitypy(): return
    print()
    if FROZEN: cmd = [sys.executable, "--run-script", os.path.join(HERE, "apply_all.py"), ab] + args
    else: cmd = [sys.executable, "-X", "utf8", "-u", os.path.join(HERE, "apply_all.py"), ab] + args
    r = subprocess.run(cmd, env=dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8"))
    if r.returncode != 0:
        print("\n문제가 생겼습니다. 위 메시지를 캡처해서 알려주세요. (exe 와 같은 폴더의 apply_all.log 도 같이)")
    else:
        print("\n끝! 스팀에서 게임을 켜고 '새 게임'을 시작하세요." if c != "3" else "\n원래대로 되돌렸습니다.")

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\n중단했습니다.")
    except Exception as e: print("\n예상치 못한 오류: %r" % (e,))
    pause()
