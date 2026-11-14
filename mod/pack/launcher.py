"""Into the Dead: Our Darkest Days - 지도 랜덤 배치 + 탐색 반경 x1.5 (공유용 간편 실행기).
메뉴에서 번호만 고르면 됩니다. 게임 폴더는 자동으로 찾고, 못 찾으면 직접 붙여넣게 합니다.
"""
import json, os, re, subprocess, sys

FROZEN = getattr(sys, "frozen", False)
HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
GAME = "Into the Dead Our Darkest Days"
MAPONLY = os.path.exists(os.path.join(HERE, "edition_map.txt"))   # 지도 전용 배포판 표시 파일 (있으면 지도 관련 항목만 보여줌)

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
        out = subprocess.run(["tasklist"], capture_output=True, text=True, errors="ignore", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
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
    print("=== Into the Dead: Our Darkest Days 지도 도구 (지도 랜덤 배치 + 반경 x1.5) ===\n" if MAPONLY else "=== Into the Dead: Our Darkest Days 간편 도구 (지도 랜덤 배치 + 반경 x1.5 / 시나리오 프리셋) ===\n")
    if not os.path.exists(os.path.join(HERE, "apply_all.py")):
        print("apply_all.py 가 같은 폴더에 있어야 합니다. 압축을 완전히 푼 뒤 실행하세요 (exe 는 이 문제가 없습니다)."); return
    ab = find_ab()
    if ab: print("게임 폴더를 찾았습니다:\n  " + ab + "\n")
    else:
        ab = ask_ab()
        if not ab: print("취소했습니다."); return
    print("1) 적용   * 새 게임 시작 전에만!" if MAPONLY else "1) 적용 (항목을 골라서)   * 새 게임 시작 전에만!   - 탐색 반경 x1.5 는 항상 포함")
    print("2) 적용 - 시드 지정 (같은 숫자면 같은 지도, 친구와 같은 지도로 하고 싶을 때)")
    print("3) 원래대로 되돌리기")
    if not MAPONLY: print("4) 사용자 지정 시나리오 프리셋 (내 설정 저장 / 게임의 프리셋 칸에 넣기)")
    print("0) 종료")
    c = input("\n번호: ").strip()
    if c == "4" and not MAPONLY:
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
        if MAPONLY: print("\n적용 내용(고정): 지도 건물 위치 랜덤 섞기 + 교역소 중앙부 이동 + 거점 위치 섞기 + 유출구역 세트 이동 + 탐색 반경 x1.5")
        else:
            print("\n적용할 항목을 고르세요. (엔터 = [ ] 안의 기본값, 기본값은 지난번에 고른 것)")
            print("!! 이 도구는 항상 원본에서 다시 계산합니다. 이번에 'n' 으로 둔 항목은, 전에 적용했더라도 원래대로 돌아갑니다.")
        o = load_opts()
        if MAPONLY:
            # 지도 전용 배포판: 선택 없이 고정 (지도 섞기 + 교역소 중앙 이동 + 거점 섞기 + 반경 x1.5)
            o["map"] = True; o["move_posts"] = True; o["shuffle_shelters"] = True; o["move_spillzone"] = True
            o["bal"] = o["leads"] = o["romance_all"] = o["zombie"] = False
            o["trader_start"] = 10
            o["wheel_gold"] = True; o["panel"] = True; o["quiet_toggle"] = False
        else:
            o["map"] = yn("지도 건물 위치 랜덤 섞기", o.get("map", True))
        if not MAPONLY:
            o["bal"] = yn("총알 산출량 x5 / 생존자 가방 24칸 / 지도 스테이션 2칸 / 시체 회수 24칸 / 미스터 베일 신규 품목 순서", o.get("bal", False))
            if o["bal"]:
                s = input("미스터 베일의 첫 석궁/샷건이 열리는 시점 - 0=게임 시작부터, 10, 20=원래 [%s]: " % o.get("vale_start", 20)).strip()
                o["vale_start"] = int(s) if s in ("0", "10", "20") else o.get("vale_start", 20)
                o["vale_s12only"] = yn("미스터 베일이 샷건(S12 라이엇)만 계속 판매 (석궁과 석궁 볼트는 판매하지 않음)", o.get("vale_s12only", False))
            o["leads"] = yn("탈출 퀘스트를 열기 위한 조사 장소(단서) 3곳 -> 1곳", o.get("leads", False))
            s = input("상인(마와 파/베일/리키)이 처음 나오는 사이클 - 0=게임 시작부터, 1~9, 10=원래 [%s]: " % o.get("trader_start", 10)).strip()
            o["trader_start"] = int(s) if s.isdigit() and 0 <= int(s) <= 10 else o.get("trader_start", 10)
            o["unarmed_crit"] = yn("맨손 무기 2종(무술가/레슬링)의 크리티컬 확률 2% -> 10%", o.get("unarmed_crit", False))
            o["trader_sure"] = yn("상인 방문 확률 제한 해제: 쿨다운(자주 3일/기본 6일/드물게 10일)마다 확정으로 방문 (원래는 쿨다운이 지나도 사이클마다 약 10%만 통과하는 것으로 보임)", o.get("trader_sure", False))
            o["move_posts"] = yn("교역소 5곳을 지도 중앙부로 옮겨 모든 거점의 원 안에 교역소가 1곳 이상 있게 하기 (지도 섞기를 켠 경우에만. 모든 거점의 원 크기는 그대로 같음)", o.get("move_posts", False))
            o["shuffle_shelters"] = yn("메사냉방/치프웨이즈를 뺀 거점 16곳끼리 위치를 서로 바꾸기 (지도 섞기를 켠 경우에만. 스토리와 충돌할 위험은 게임에서 직접 확인하지 못함)", o.get("shuffle_shelters", False))
            o["move_spillzone"] = yn("유출구역 세트(치프웨이즈 계열 5곳)를 배치 그대로 통째로 다른 곳으로 옮기기 (지도 섞기를 켠 경우에만)", o.get("move_spillzone", False))
            o["romance_all"] = yn("연애의 모든 제한 풀기 (공용구역 2명 사용 기준: 가족/나이대/연애 중/호환성/관계 단계/연애 대상 여부 + 성공 확률 최대)", o.get("romance_all", False))
            o["zombie"] = yn("탐험 중 죽은 생존자가 좀비가 될 확률 50% -> 100% + 예외(첫 이탈자/좀비 아닌 것에게 죽음) 전부 해제 + 강제 좀비화 (깊은 상처 감염 좀비화는 별개라 그대로)", o.get("zombie", False))
        if not MAPONLY:
            o["hod_start"] = yn("어둠의 심연 단서 3개를 게임 시작부터 얻은 상태로 시작", o.get("hod_start", False))
            o["repair"] = yn("정비 작업대 레벨 때문에 못 하던 무기 수리를 레벨 제한 없이 가능하게 하기 (수리공/건스미스 특성과 재료는 그대로 필요)", o.get("repair", False))
            o["dismantle"] = yn("정비 작업대 레벨 때문에 못 하던 무기 분해를 레벨 제한 없이 가능하게 하기", o.get("dismantle", False))
            o["random_traits"] = yn("모든 생존자의 시작 특성(양성 1 + 음성 1)을 섞어서 다시 나누기 (쿠퍼의 파일럿처럼 스토리와 얽힌 특성 12칸은 고정. 새 게임/새로 영입하는 생존자에게 적용, 진행 중인 세이브는 그대로)", o.get("random_traits", False))
            o["random_skills"] = yn("모든 생존자의 스킬 트리를 티어(1~4)별로 섞어서 다시 나누기 (스토리와 얽힌 티어는 고정, 같은 티어끼리만 섞음. 새 게임/새로 영입하는 생존자에게 적용, 진행 중인 세이브는 그대로)", o.get("random_skills", False))
            o["martial_h2h"] = yn("무술가/프로레슬러 특성(하오/이사야의 원래 특성)을 가진 생존자는 스킬 트리 4티어에 맨손격투 전문가(맨손 스텔스 처형)가 반드시 오게 하기 (스킬 트리 섞기와 같이 쓰면 섞은 뒤에 맞춤)", o.get("martial_h2h", False))
            o["ammo_levels"] = yn("무기 작업대에서 모든 총알 종류(권총/리볼버/샷건/소총/돌격소총)를 1레벨부터 만들 수 있게 하기 (재료와 작업 시간은 그대로)", o.get("ammo_levels", False))
            o["otto"] = yn("스필존 관제실의 오토(Otto) 영입 때 건네는 방호복을 락픽 1개로 바꾸기 (대사 문구는 그대로 방호복이라고 나올 수 있음)", o.get("otto", False))
            o["unarmed_sound"] = yn("[효과음 번들 수정] 맨손 스텔스 처형(기본 맨손/무술/브루탈)의 효과음이 허드슨/하오/이사야뿐 아니라 모든 생존자에게 나게 하기 (효과음 번들 data_visual 약 530MB를 다시 써서 백업/적용에 시간이 걸림. 목소리는 처형하는 생존자 자신의 것으로 나는 것으로 보이지만 게임에서 확인하지 못함. 이 게임 빌드 전용)", o.get("unarmed_sound", False))
            o["wheel_gold"] = yn("[게임 실행 파일 수정] 스테이션 휠(F 길게)에서 지금 조작 중인 생존자의 특기와 맞는 작업 칸을 금색으로 강조 (나쁜 특성은 제외, 자리가 꽉 찬 칸은 회색 그대로. GameAssembly.dll 에 새 실행 구역(4KB)을 추가하는 큰 변경이라 이 게임 빌드 전용이고 게임 업데이트/스팀 파일 검사 후에는 다시 적용해야 함. GameAssembly.dll.bak 백업을 만듦)", o.get("wheel_gold", False))
            o["shelter_move"] = yn("[게임 실행 파일 수정, 게임에서 동작 미확인] 한 번이라도 살았던 거점은 '수색해서 소탕'하지 않아도 바로 은신처로 이동 (한 번도 안 살아 본 거점은 그대로. GameAssembly.dll 에 새 실행 구역을 쓰며 이 게임 빌드 전용이고 게임 업데이트/스팀 무결성 검사 때 되돌아갈 수 있음. 원래대로 되돌릴 수 있음)", False)
            o["random_start"] = yn("[게임 실행 파일 수정] 사용자 지정 시나리오에서 생존자를 아무도 안 고르고 시작하면 후보 18명(Bowman 제외) 중 랜덤 3명 + 랜덤 거점으로 시작 (GameAssembly.dll 에 새 실행 구역을 쓰며 이 게임 빌드 전용이고 게임 업데이트/스팀 무결성 검사 때 되돌아갈 수 있음. 원래대로 되돌릴 수 있음)", False)
            o["quiet_toggle"] = yn("[게임 파일 수정, 게임에서 동작 미확인] 게임 옵션(접근성 맨 끝)에 '발걸음 소리 무음' 켜기/끄기 줄 추가 (기본 끔. 켜면 생존자 발소리만 사라짐)", o.get("quiet_toggle", False))
            o["panel"] = yn("[게임 파일 수정] 지도 화면에 '탐색 생존자 패널' 표시: 지금 내 은신처 생존자 중 탐색/근접/사격/정신 특성이 유리한 사람의 사진과 특성을 탭으로 보여 줌 (ui_screens 번들 + GameAssembly.dll 을 고치며 이 게임 빌드 전용이고 게임 업데이트/스팀 무결성 검사 때 되돌아갈 수 있음. 원래대로 되돌릴 수 있음)", False)
            o["peek"] = yn("[게임 실행 파일 수정] 서 있는 상태에서도 문 엿보기 (이 게임 빌드 전용. 게임 업데이트 후엔 다시 안 맞을 수 있고, 스팀 파일 검사로 원복됨. GameAssembly.dll 백업을 만듦)", o.get("peek", False))
            o["lock_notes"] = yn("맵 정보의 장소 설명 끝에 락픽/볼트 절단기 필요 개수 적기 (방문 전 장소도 표시. 서랍/로커 + 열쇠가 필요한 문 기준, 지식으로 여는 문 제외. 장소 이름 글자 파일 loc.* 수정, 백업 생성)", o.get("lock_notes", False))
            o["june"] = yn("스필존 스킵의 스쿱 준에게 방호복 받기: 칠리 콘 카르네 4개 -> 락픽 1개 (대사 문구는 그대로일 수 있음)", o.get("june", False))
            o["spillzone_start"] = yn("유출구역(스필존) 단서 3개를 게임 시작부터 얻은 상태로 시작", o.get("spillzone_start", False))
            o["quiet"] = yn("생존자가 걷거나 달려도 발소리(소음)가 나지 않게 하기 (웅크릴 때와 같음. 문/루팅/전투 소음은 그대로)", o.get("quiet", False))
        else:
            o["quiet"] = False; o["hod_start"] = False; o["june"] = False; o["repair"] = False; o["dismantle"] = False; o["ammo_levels"] = False; o["random_traits"] = False; o["random_skills"] = False; o["martial_h2h"] = False; o["peek"] = False; o["shelter_move"] = False; o["random_start"] = False; o["unarmed_sound"] = False; o["otto"] = False; o["lock_notes"] = False; o["spillzone_start"] = False
        save_opts(o)
        if not o["bal"]: args += ["--only-map"]
        if not o["map"]: args += ["--no-shuffle"]
        if o["leads"]: args += ["--leads", "1"]
        if o.get("trader_start", 10) != 10: args += ["--trader-start", str(o["trader_start"])]
        if o.get("trader_sure"): args += ["--trader-sure"]
        if o.get("unarmed_crit"): args += ["--unarmed-crit"]
        if o["move_posts"]: args += ["--move-posts"]
        if o["shuffle_shelters"]: args += ["--shuffle-shelters"]
        if o.get("move_spillzone"): args += ["--move-spillzone"]
        if o["romance_all"]: args += ["--romance-all"]
        if o["zombie"]: args += ["--zombie"]
        if o["quiet"]: args += ["--quiet-steps"]
        if o["hod_start"]: args += ["--hod-start"]
        if o["spillzone_start"]: args += ["--spillzone-start"]
        if o["june"]: args += ["--june-lockpick"]
        if o.get("repair"): args += ["--repair-any-level"]
        if o.get("dismantle"): args += ["--dismantle-any-level"]
        if o.get("ammo_levels"): args += ["--ammo-all-levels"]
        if o.get("random_traits"): args += ["--random-traits"]
        if o.get("random_skills"): args += ["--random-skills"]
        if o.get("martial_h2h"): args += ["--martial-h2h"]
        if o.get("unarmed_sound"): args += ["--unarmed-sound"]
        if o.get("otto"): args += ["--otto-lockpick"]
        if o.get("peek"): args += ["--peek-standing"]
        if o.get("wheel_gold"): args += ["--wheel-gold"]
        if o.get("shelter_move"): args += ["--shelter-move"]
        if o.get("random_start"): args += ["--random-start"]
        if o.get("panel"): args += ["--panel"]
        if o.get("quiet_toggle"): args += ["--quiet-toggle"]
        if o.get("lock_notes"): args += ["--lock-notes"]
        if o["bal"] and o.get("vale_start", 20) != 20: args += ["--vale-start", str(o["vale_start"])]
        if o["bal"] and o.get("vale_s12only"): args += ["--vale", "s12only"]
        print("\n이번에 적용: 탐색 반경 x1.5" + (" / 지도 섞기" if o["map"] else "") + (" / 총알·가방·스테이션·시체·베일" if o["bal"] else "") + (" / 탈출 단서 1곳" if o["leads"] else "") + (" / 상인 %d사이클부터" % o["trader_start"] if o.get("trader_start", 10) != 10 else "") + (" / 교역소 중앙부로 이동" if o["move_posts"] else "") + (" / 거점 섞기" if o["shuffle_shelters"] else "") + (" / 연애 제한 해제" if o["romance_all"] else "") + (" / 좀비화 100%" if o["zombie"] else "") + (" / 발소리 없음" if o["quiet"] else "") + (" / 어둠의 심연 시작부터(시도)" if o["hod_start"] else "") + (" / 유출구역 시작부터(시도)" if o["spillzone_start"] else "") + (" / 준 방호복 락픽 1개" if o["june"] else ""))
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
