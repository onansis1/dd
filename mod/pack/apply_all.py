"""Into the Dead: Our Darkest Days - 모든 수정을 한 번에 적용한다 (게임 업데이트 후에도 같은 명령으로 다시 적용 가능).
사용: python apply_all.py <AssetBundles 폴더 경로> [옵션]
  --seed N        지도 섞기 시드 (생략하면 무작위)
  --leads 1       탈출 퀘스트를 열기 위해 조사해야 하는 단서(장소) 수 (기본 3 = 원래대로)
  --trader-start N  상인(마와 파/베일/리키)이 처음 나올 수 있는 시점 (0=게임 시작부터, 1~9, 10=원래)
  --posts         모든 거점의 탐색 반경 안에 교역소가 최소 2곳 들어가게 한다 (모자란 거점만 반경을 늘림. --posts-min N 으로 최소 곳수 변경)
  --zombie        탐험 중 죽은 생존자가 좀비가 될 확률 50% -> 100% + 예외(첫 이탈자/좀비 아닌 것에게 죽음) 전부 해제 + 강제 좀비화 (깊은 상처 감염 좀비화는 별개라 그대로)
  --quiet-steps   생존자가 걷거나 달려도 발소리(소음)가 나지 않게 한다 (웅크릴 때와 같게). 문/루팅/전투 소음은 그대로
  --hod-start     어둠의 심연 단서 3개를 게임 시작부터 얻은 상태로 (시도. 게임 내 동작 미확인)
  --romance       공용구역에 3명 이상 있어도 로맨스 아이템을 쓸 수 있게 한다 (주의: 연애 시도는 게임 코드가 2명만 처리해, 아이템만 소모될 수 있음)
  --romance-all   연애의 모든 제한을 푼다 (정확히 2명일 때. --romance 와 같이 쓰면 2명 이상) (가족/나이대/연애 중/호환성 6종/관계 단계 + 성공 확률 구성 값 최대)
  --move-posts    교역소 5곳을 지도 중앙부로 옮겨 모든 거점의 원 안에 교역소가 1곳 이상 들어가게 한다 (지도 섞기를 켠 경우에만, 반경은 모두 동일)
  --shuffle-shelters  메사냉방/치프웨이즈를 뺀 나머지 거점끼리 위치를 서로 바꾼다 (실험적, 지도 섞기를 켠 경우에만)
  --only-map      지도 섞기 + 탐색 반경만 적용 (총알/가방/슬롯/시체/미스터 베일은 건드리지 않음)
  --no-shuffle    지도 위치는 섞지 않고 탐색 반경만 넓힌다
  --restore       모든 수정을 되돌린다 (백업으로 복원)
  --vale-start 0  미스터 베일의 첫 신규 품목(석궁/샷건)이 열리는 시점 (0=게임 시작부터, 10, 20=원래)
  --vale random   미스터 베일 신규 판매 품목 순서 (random=첫 품목 석궁/샷건 50:50 후 번갈아, crossbow / s12riot=첫 품목 지정, none=건드리지 않음). R77 권총은 안 나옴
  --ammo 5 --inv 24 --corpse 24 --radius 1.5 --slots 2   수치 바꾸기
적용 내용: 총알 산출량 x배수, 생존자 가방 칸 수, 지도 스테이션 시작 슬롯, 시체 회수 칸 수, 탐색 반경, 미스터 베일 신규 판매 품목 순서(석궁/샷건 번갈아), (선택) 지도 위치 섞기.
백업은 <AssetBundles>/_mods_backup 에 한 번만 만들고, 항상 거기서 다시 계산하므로 여러 번 실행해도 배수가 쌓이지 않는다.
파일이 백업/이전 결과와 다르면(= 게임 업데이트) 현재 파일을 새 원본으로 인식하고 백업을 갱신한다. 게임을 끈 상태에서 실행할 것.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile

FROZEN = getattr(sys, "frozen", False)   # PyInstaller exe
HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))   # 스크립트/데이터가 있는 곳
OUTDIR = os.path.dirname(sys.executable) if FROZEN else HERE                          # 로그를 남길 곳
FILES = ["data_balancing", "data_config", "data_levels"]

def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

LOG = os.path.join(OUTDIR, "apply_all.log")
KEEP_STAGE = []

def log(text):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError:
        pass

def run(script, *args):
    """하위 단계를 실행한다. 출력은 버퍼 없이(UTF-8) 받고, 실패하면 종료 코드와 모든 출력을 보여주고 로그에 남긴다."""
    if FROZEN:
        cmd = [sys.executable, "--run-script", os.path.join(HERE, script)] + [str(a) for a in args]
    else:
        cmd = [sys.executable, "-X", "utf8", "-X", "faulthandler", "-u", os.path.join(HERE, script)] + [str(a) for a in args]
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    r = subprocess.run(cmd, capture_output=True, env=env)
    out = (r.stdout or b"").decode("utf-8", errors="replace")
    err = (r.stderr or b"").decode("utf-8", errors="replace")
    log("$ " + " ".join(cmd) + "\n[returncode %s]\n%s\n%s" % (r.returncode, out, err))
    if r.returncode != 0:
        print("\n===== 단계 실패: %s (종료 코드 %s) =====" % (script, r.returncode))
        print(out.strip() or "(표준 출력 없음)")
        print(err.strip() or "(오류 출력 없음 - 프로그램이 오류 문구 없이 갑자기 종료된 것입니다)")
        print("=====")
        print("전체 기록: " + LOG)
        if KEEP_STAGE:
            print("작업 폴더(지우지 않음): " + KEEP_STAGE[0])
            print("이 단계만 직접 실행해 보려면 명령 프롬프트에서:  " + " ".join('"%s"' % c if " " in c else c for c in [sys.executable, os.path.join(HERE, script)] + [str(a) for a in args]))
        sys.exit("단계 실패: %s (설치된 게임 파일은 바뀌지 않았습니다)" % script)
    return out

def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("folder", nargs="?")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--no-shuffle", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--ammo", type=int, default=5)
    ap.add_argument("--inv", type=int, default=24)
    ap.add_argument("--corpse", type=int, default=24)
    ap.add_argument("--radius", type=float, default=1.5)
    ap.add_argument("--slots", type=int, default=2)
    ap.add_argument("--only-map", action="store_true")
    ap.add_argument("--leads", type=int, default=3)
    ap.add_argument("--posts", action="store_true")
    ap.add_argument("--move-posts", action="store_true")
    ap.add_argument("--shuffle-shelters", action="store_true")
    ap.add_argument("--posts-min", type=int, default=2)
    ap.add_argument("--zombie", action="store_true")
    ap.add_argument("--hod-start", action="store_true")
    ap.add_argument("--quiet-steps", action="store_true")
    ap.add_argument("--romance", action="store_true")
    ap.add_argument("--romance-all", action="store_true")
    ap.add_argument("--trader-start", type=int, default=10, choices=list(range(0, 11)))
    ap.add_argument("--vale-start", type=int, default=20, choices=[0, 10, 20])
    ap.add_argument("--vale", default="random", choices=["random", "crossbow", "s12riot", "none"])
    a = ap.parse_args()
    if not a.folder:
        sys.exit(__doc__)
    ab = a.folder
    try:
        open(LOG, "w", encoding="utf-8").close()
    except OSError:
        pass
    try:
        import UnityPy
        uv = getattr(UnityPy, "__version__", "?")
    except Exception as e:
        uv = "import 실패: %r" % (e,)
    log("python %s | UnityPy %s | 폴더 %s" % (sys.version.split()[0], uv, ab))
    for f in FILES:
        if not os.path.isfile(os.path.join(ab, f)):
            sys.exit("%s 를 찾을 수 없습니다: %s" % (f, os.path.join(ab, f)))
    bdir = os.path.join(ab, "_mods_backup")
    mpath = os.path.join(bdir, "manifest.json")
    os.makedirs(bdir, exist_ok=True)
    man = json.load(open(mpath, encoding="utf-8")) if os.path.exists(mpath) else {}

    # 1) 각 파일이 '원본 / 지난번 우리 결과 / 업데이트된 새 파일' 중 무엇인지 판정하고 백업을 맞춘다
    for f in FILES:
        cur_p, bak_p = os.path.join(ab, f), os.path.join(bdir, f)
        cur = sha(cur_p)
        rec = man.get(f, {})
        has_bak = os.path.exists(bak_p)
        if has_bak and rec.get("out") == cur:
            state = "이전 결과 (백업 기준으로 다시 계산)"
        elif has_bak and sha(bak_p) == cur:
            state = "원본 (수정 없음)"
        elif has_bak:
            print("안내: %s 이(가) 백업/이전 결과와 다릅니다. 게임 업데이트로 보고 현재 파일을 새 원본으로 삼습니다." % f)
            shutil.copy2(bak_p, bak_p + ".prev")
            shutil.copy2(cur_p, bak_p)
            state = "새 원본(업데이트)"
        else:
            shutil.copy2(cur_p, bak_p)
            state = "새 원본 (백업 생성)"
        man[f] = {"orig": sha(bak_p), "out": rec.get("out") if state.startswith("이전") or state.startswith("원본") else None}
        print("  %-15s %s" % (f, state))

    if a.restore:
        for f in FILES:
            tmp = os.path.join(ab, f + ".tmp")
            shutil.copy2(os.path.join(bdir, f), tmp)
            os.replace(tmp, os.path.join(ab, f))
            man[f]["out"] = None
        json.dump(man, open(mpath, "w", encoding="utf-8"), indent=1)
        print("모든 수정을 되돌렸습니다 (원본 백업으로 복원).")
        return

    # 2) 임시 작업 폴더에 원본을 복사해서 각 도구를 돌린다 (낡은 백업이 섞일 일이 없다)
    stage = tempfile.mkdtemp(prefix="itd_mods_")
    KEEP_STAGE.append(stage)
    ok_done = False
    try:
        for f in FILES:
            shutil.copy2(os.path.join(bdir, f), os.path.join(stage, f))
        # 망원경 검사 결과가 현재 장면 번들과 맞는지 (장면 번들 이름이 바뀌었으면 다시 검사)
        tj = os.path.join(HERE, "telescopes.json")
        need_scan = not os.path.exists(tj)
        if not need_scan:
            try:
                scanned = set(json.load(open(tj, encoding="utf-8")).get("bundles", {}))
                present = {n for n in os.listdir(ab) if n.startswith("multi_scene.")}
                if scanned and present and not scanned <= present:
                    print("안내: telescopes.json 이 현재 장면 번들과 맞지 않습니다 (장면 업데이트). 다시 검사합니다.")
                    need_scan = True
            except Exception:
                need_scan = True
        if need_scan:
            print("장면에 진짜 망원경이 있는 장소를 검사합니다 (몇 분 걸릴 수 있음)...")
            keep = None
            if os.path.exists(tj):
                keep = open(tj, "rb").read()
            run("scan_telescopes.py", ab)
            ok = False
            try:
                loc = json.load(open(tj, encoding="utf-8")).get("locations", {})
                ok = any(v.get("checked_bundles") for v in loc.values())
            except Exception:
                ok = False
            if ok:
                print("검사 완료")
            else:
                if keep is not None:
                    open(tj, "wb").write(keep)
                print("경고: 장면 번들을 검사하지 못했습니다. 기존 telescopes.json 을 그대로 사용합니다 (없으면 가짜 망원경 제외 없이 진행).")
        if not a.only_map:
            print(run("patch_balance.py", stage, a.ammo, a.inv, a.slots).strip())
        if not a.only_map:
            out_cfg = os.path.join(stage, "data_config.out")
            vale = []
            if a.vale != "none":
                import random
                first = a.vale if a.vale != "random" else random.Random(a.seed if a.seed is not None else None).choice(["crossbow", "s12riot"])
                vale = [first, str(a.vale_start)]
            print(run("patch_config.py", os.path.join(stage, "data_config"), a.corpse, out_cfg, *vale).strip())
            os.replace(out_cfg, os.path.join(stage, "data_config"))
        if a.leads != 3:
            out_bal = os.path.join(stage, "data_balancing.out")
            print(run("patch_leads.py", os.path.join(stage, "data_balancing"), a.leads, out_bal).strip())
            os.replace(out_bal, os.path.join(stage, "data_balancing"))
        if a.hod_start:
            out_bal5 = os.path.join(stage, "data_balancing.out")
            print(run("patch_hod.py", os.path.join(stage, "data_balancing"), os.path.join(stage, "data_config"), out_bal5).strip())
            os.replace(out_bal5, os.path.join(stage, "data_balancing"))
        if a.romance_all:
            out_bal2 = os.path.join(stage, "data_balancing.out")
            print(run("patch_romance_compat.py", os.path.join(stage, "data_balancing"), os.path.join(stage, "data_config"), out_bal2).strip())
            os.replace(out_bal2, os.path.join(stage, "data_balancing"))
        if a.romance or a.romance_all:
            out_cfg2 = os.path.join(stage, "data_config.out")
            print(run("patch_romance.py", os.path.join(stage, "data_config"), out_cfg2, *((["all"] if a.romance else ["keep2"]) if a.romance_all else [])).strip())
            os.replace(out_cfg2, os.path.join(stage, "data_config"))
        if a.quiet_steps:
            out_bal4 = os.path.join(stage, "data_balancing.out")
            print(run("patch_noise.py", os.path.join(stage, "data_balancing"), out_bal4).strip())
            os.replace(out_bal4, os.path.join(stage, "data_balancing"))
        if a.zombie:
            out_cfg3 = os.path.join(stage, "data_config.out")
            print(run("patch_zombie.py", os.path.join(stage, "data_config"), out_cfg3).strip())
            os.replace(out_cfg3, os.path.join(stage, "data_config"))
        if a.trader_start < 10:
            out_bal = os.path.join(stage, "data_balancing.out")
            print(run("patch_traders.py", os.path.join(stage, "data_balancing"), os.path.join(stage, "data_config"), out_bal, a.trader_start).strip())
            os.replace(out_bal, os.path.join(stage, "data_balancing"))
        print(run("widen_map_radius.py", stage, a.radius).strip().splitlines()[-2])
        if not a.no_shuffle:
            args = [stage] + ([a.seed] if a.seed is not None else [])
            if a.move_posts:
                os.environ["ITD_MOVE_POSTS"] = "1"
            if a.shuffle_shelters:
                os.environ["ITD_SHUFFLE_SHELTERS"] = "1"
            lines = run("shuffle_map.py", *args).strip().splitlines()
            print("\n".join(l for l in lines if l.startswith(("시드", "스토리", "telescopes", "교역소", "거점"))))
        if a.move_posts and a.no_shuffle:
            print("안내: 교역소 이동은 지도 섞기를 켠 경우에만 동작합니다 (이번에는 건너뜀).")
        if a.posts:
            print(run("add_trading_posts.py", stage, a.posts_min).strip())
        # 3) 결과를 설치 폴더에 반영
        for f in FILES:
            tmp = os.path.join(ab, f + ".tmp")
            shutil.copy2(os.path.join(stage, f), tmp)
            try:
                os.replace(tmp, os.path.join(ab, f))
            except PermissionError:
                sys.exit("%s 를 교체하지 못했습니다. 게임/스팀이 실행 중이면 끄고 다시 시도하세요." % f)
            man[f]["out"] = sha(os.path.join(ab, f))
        json.dump(man, open(mpath, "w", encoding="utf-8"), indent=1)
        print("\n완료. 이제 스팀에서 게임을 켜고 새 게임을 시작하세요.")
        ok_done = True
    finally:
        if ok_done:
            shutil.rmtree(stage, ignore_errors=True)

if __name__ == "__main__":
    main()
