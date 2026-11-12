"""Into the Dead: Our Darkest Days - 지도 화면 '탐색 생존자 패널'을 켜고 끄는 코드 (GameAssembly.dll 패치, 이 게임 빌드 전용).
사용: python patch_panelcode.py <check|apply|revert|status> <GameAssembly.dll 경로>
 - 지도 화면(MapHud.OnPush)이 열릴 때 한 번, 내 은신처 생존자와 그들의 특성을 읽어 패널(ui_screens 번들에 patch_panelbundle.py 가 만든 줄/칸)의 해당하는 줄과 칸만 켜고 나머지는 끈다.
   코드는 GameObject.SetActive 등 게임의 Unity 호출만 쓰고, 패널의 구조가 예상과 다르면(번들이 적용되지 않았거나 다른 버전) 아무것도 하지 않는다.
 - 구현: 스테이션 휠/문 엿보기 등 다른 패치가 쓰는 '.itdx' 구역(없으면 만든다) 뒤에 새 실행 구역 '.itd2'(0xA00바이트)를 추가하고(구역 헤더 40바이트 + NumberOfSections + SizeOfImage + 파일 끝에 0xA00바이트),
   그 구역에 코드와 표를 한 덩어리로 쓰고, MapHud.OnPush 안의 8바이트(RVA 0xDE5DF3)를 그 코드로 점프하게 바꾼다.
 - 개발 중 도구(itd_panel_code_patch.py)로 적용한 '이전 버전' 코드(.itdx 안 5조각 + 후크)도 알아보고, 새 코드로 교체한다(후크 -> 조각 순서로 먼저 되돌림).
 - 적용 순서: (필요하면 .itdx) -> .itd2 구역 -> 코드 -> 후크(마지막). 되돌리기는 반대. 쓴 뒤 읽어서 확인한다.
 - 이 게임 빌드(SHA-256 3F45B1F9...)에서만 적용한다. GameAssembly.dll.bak 이 원본인지 확인하고(없으면 파일이 원본일 때만 만든다), 후크 앞뒤 20바이트가 예상과 같은지 확인한다. 게임이 실행 중이면 중단한다.
"""
import hashlib, json, os, shutil, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "_MEIPASS", None):
    HERE = sys._MEIPASS
ORIGINAL_SHA256 = "3F45B1F9FA8B5F28AD4A0ECAAA87DB1A1D711BC559DBB1A3672855D82F9061C8"
ORIGINAL_SIZE = 103912960
PAGE = 4096
PAGE2 = 0xA00
GAME_EXE = "IntoTheDeadOurDarkestDays.exe"
HDR_ALT = {368: "00705e06", 294: "0900"}
HEADER = [   # .itdx 구역 (다른 패치와 같은 값)
    ("구역 헤더 .itdx", 832, "00" * 40, "2e697464780000000010000000505e060010000000963106000000000000000000000000200000" "60"),
    ("SizeOfImage 0x65E5000 -> 0x65E6000", 368, "00505e06", "00605e06"),
    ("NumberOfSections 7 -> 8", 294, "0700", "0800"),
]
D = json.load(open(os.path.join(HERE, "panel_code.json"), encoding="utf-8"))
SECTION = bytes.fromhex(D["section_hex"])
ITD2_HDR_OFF = D["itd2_header_off"]                       # 872
ITD2_HDR = D["itd2_header_hex"]
HOOK_OFF, HOOK_ORIG, HOOK_NEW = D["hook_off"], D["hook_orig"], D["hook_new"]
HOOK_BEFORE, HOOK_AFTER = D["hook_before"], D["hook_after"]
V1_PIECES = [(p["name"], p["page_off"], p["hex"]) for p in D["v1_pieces"]]    # 개발 도구가 .itdx 안에 쓴 이전 버전 조각
V1_HOOK = D["v1_hook_new"]
assert len(SECTION) == PAGE2 and len(ITD2_HDR) == 80


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def read_at(path, off, n):
    with open(path, "rb") as f:
        f.seek(off)
        return f.read(n)


def game_running():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + GAME_EXE], capture_output=True, text=True).stdout
        return GAME_EXE.lower() in out.lower()
    except Exception:
        return False


def need_dll(dll):
    if not os.path.isfile(dll):
        sys.exit("GameAssembly.dll 을 찾을 수 없습니다: " + dll)


def verify_layout(dll):
    with open(dll, "rb") as f:
        hdr = f.read(0x1000)
    pe = struct.unpack_from("<I", hdr, 0x3C)[0]
    if hdr[pe:pe + 4] != b"PE\0\0":
        sys.exit("PE 파일이 아닙니다: " + dll)
    fh = pe + 4
    nsec = struct.unpack_from("<H", hdr, fh + 2)[0]
    optsz = struct.unpack_from("<H", hdr, fh + 16)[0]
    opt = fh + 20
    soi_off, tab = opt + 56, opt + optsz
    sa, fa, checksum = struct.unpack_from("<I", hdr, opt + 32)[0], struct.unpack_from("<I", hdr, opt + 36)[0], struct.unpack_from("<I", hdr, opt + 64)[0]
    if (fh + 2, soi_off, tab + 40 * 7) != (294, 368, 832):
        sys.exit("중단: PE 헤더의 모양이 이 패치와 다릅니다 (다른 빌드이거나 파일이 다릅니다).")
    if checksum != 0 or (sa, fa) != (0x1000, 0x200) or nsec not in (7, 8, 9):
        sys.exit("중단: PE 정렬/체크섬/구역 수가 이 패치와 다릅니다.")
    return nsec


def hdrstate(dll):
    out = []
    for _n, off, orig, new in HEADER:
        cur = read_at(dll, off, len(orig) // 2).hex()
        out.append("orig" if cur == orig else "new" if cur in (new, HDR_ALT.get(off)) else "other")
    return out


def hookbytes(dll):
    cur = read_at(dll, HOOK_OFF, 8).hex()
    return "orig" if cur == HOOK_ORIG else "v3" if cur == HOOK_NEW else "v1" if cur == V1_HOOK else "other"


def check_hook_context(dll):
    if read_at(dll, HOOK_OFF - 20, 20).hex() != HOOK_BEFORE or read_at(dll, HOOK_OFF + 8, 20).hex() != HOOK_AFTER:
        sys.exit("중단: 후크 주변의 코드가 예상과 다릅니다 (게임이 업데이트되었거나 다른 빌드입니다).")


def v1_state(dll):
    """개발 도구가 .itdx 안에 쓴 이전 버전 조각: 'none' | 'v1' (전부) | 'partial' | 'other'"""
    if os.path.getsize(dll) < ORIGINAL_SIZE + PAGE:
        return "none"
    st = []
    for _n, po, hx in V1_PIECES:
        b = bytes.fromhex(hx)
        cur = read_at(dll, ORIGINAL_SIZE + po, len(b))
        st.append("blank" if all(c in (0x00, 0xCC) for c in cur) else "v1" if cur == b else "other")
    if all(x == "blank" for x in st):
        return "none"
    if "other" in st:
        return "other"
    return "v1" if all(x == "v1" for x in st) else "partial"


def state(dll):
    """(상태, 설명): 상태 'none' | 'v1' | 'ready'(구역+코드, 후크 없음) | 'final' | 'partial'(알려진 중간) ; 알 수 없으면 (None, 이유)"""
    nsec = verify_layout(dll)
    size = os.path.getsize(dll)
    hk = hookbytes(dll)
    if hk == "other":
        return None, "후크 자리가 원래도 우리 값도 아닙니다"
    hs = hdrstate(dll)
    if "other" in hs:
        return None, "구역 헤더 값이 알려진 상태가 아닙니다: %s" % hs
    has_itd2 = size == ORIGINAL_SIZE + PAGE + PAGE2
    if size not in (ORIGINAL_SIZE, ORIGINAL_SIZE + PAGE, ORIGINAL_SIZE + PAGE + PAGE2):
        return None, "파일 크기 %d 가 알려진 크기가 아닙니다" % size
    v1 = v1_state(dll)
    if v1 == "other":
        return None, ".itdx 안의 코드 자리가 0xCC/00 도 이전 버전 코드도 아닙니다"
    if has_itd2:
        h872 = read_at(dll, ITD2_HDR_OFF, 40).hex()
        if h872 != ITD2_HDR or nsec != 9 or read_at(dll, 368, 4).hex() != HDR_ALT[368]:
            return None, ".itd2 구역 헤더/구역 수/SizeOfImage 가 알려진 상태가 아닙니다"
        sec = read_at(dll, ORIGINAL_SIZE + PAGE, PAGE2)
        scs = "final" if sec == SECTION else "blank" if all(c in (0x00, 0xCC) for c in sec) else "other"
        if scs == "other":
            return None, ".itd2 구역의 내용이 우리 코드도 빈 구역도 아닙니다"
    else:
        if nsec == 9 or read_at(dll, ITD2_HDR_OFF, 40).hex() != "00" * 40 or read_at(dll, 368, 4).hex() == HDR_ALT[368]:
            return None, ".itd2 흔적이 있는데 파일 크기가 맞지 않습니다"
        scs = "none"
    if hk == "v3" and not (has_itd2 and scs == "final"):
        return None, "후크는 연결돼 있는데 새 구역에 코드가 없습니다 (그대로 두면 게임이 멈춥니다)"
    if hk == "v1" and v1 != "v1":
        return None, "이전 버전 후크는 연결돼 있는데 이전 버전 코드가 없습니다 (그대로 두면 게임이 멈춥니다)"
    if hk == "v1":
        return "v1", "이전 버전(개발 도구) 코드"
    if v1 in ("v1", "partial"):
        return "v1", "이전 버전 코드 조각이 남아 있음"
    if hk == "v3":
        return "final", ""
    if has_itd2 and scs == "final":
        return "ready", ""
    if has_itd2:
        return "partial", ".itd2 구역만 있음"
    return "none", ""


def need_bak(dll, st, create=True):
    bak = dll + ".bak"
    if os.path.exists(bak):
        if os.path.getsize(bak) != ORIGINAL_SIZE or sha256(bak) != ORIGINAL_SHA256:
            sys.exit("중단: %s 가 원본이 아닙니다 (크기/해시 불일치). 이 파일을 확인하거나 이름을 바꿔 두고 다시 시도하세요." % bak)
        return
    if os.path.getsize(dll) != ORIGINAL_SIZE or st != "none":
        print("안내: %s 가 없습니다. 이미 다른 패치가 적용된 상태라 백업은 만들지 않습니다 (되돌릴 때는 단계 표로 원상 복구)." % os.path.basename(bak))
        return
    if not create:
        return
    if sha256(dll) != ORIGINAL_SHA256:
        sys.exit("중단: GameAssembly.dll.bak(원본 백업)이 없고, 지금 파일도 수정되지 않은 원본이 아니라서 백업을 만들 수 없습니다.\n"
                 "스팀 '게임 파일 무결성 검사'로 원본을 되돌린 뒤 다시 시도하세요.")
    shutil.copy2(dll, bak)
    print("백업 생성:", bak)


def _write(dll, off, expect, new):
    with open(dll, "r+b") as f:
        f.seek(off)
        if f.read(len(expect)) != expect:
            sys.exit("중단: 쓰는 도중 원래 바이트가 달라졌습니다.")
        f.seek(off)
        f.write(new)
        f.flush()
        os.fsync(f.fileno())


def cmd_status(dll):
    need_dll(dll)
    k = state(dll)
    print("파일:", dll)
    print("크기:", os.path.getsize(dll), "(원본 %d)" % ORIGINAL_SIZE)
    print("SHA-256:", sha256(dll))
    print("상태:", ("알 수 없음 - " + k[1]) if k[0] is None else "%s %s" % (k[0], k[1]))


def cmd_check(dll):
    need_dll(dll)
    k = state(dll)
    if k[0] is None:
        sys.exit("지도 패널 코드: GameAssembly.dll 의 패치 위치가 알려진 어떤 상태와도 맞지 않습니다. 건드리지 않았습니다.\n(%s)\n"
                 "(원본으로 되돌리려면 GameAssembly.dll.bak 을 GameAssembly.dll 로 덮어쓰거나 스팀에서 '게임 파일 무결성 검사'를 하세요.)" % k[1])
    check_hook_context(dll)
    need_bak(dll, k[0], create=False)
    if game_running():
        sys.exit("게임이 실행 중입니다. 게임을 완전히 끄고 다시 시도하세요.")
    print("지도 패널 코드: 적용 가능 (현재 %s)" % k[0])


def _remove_v1(dll):
    if hookbytes(dll) == "v1":
        _write(dll, HOOK_OFF, bytes.fromhex(V1_HOOK), bytes.fromhex(HOOK_ORIG))
    for _n, po, hx in V1_PIECES:
        b = bytes.fromhex(hx)
        if read_at(dll, ORIGINAL_SIZE + po, len(b)) == b:
            _write(dll, ORIGINAL_SIZE + po, b, b"\xcc" * len(b))


def cmd_apply(dll):
    need_dll(dll)
    k = state(dll)
    if k[0] is None:
        sys.exit("지도 패널 코드: 알 수 없는 상태입니다 (%s). 건드리지 않았습니다." % k[1])
    if k[0] == "final":
        print("지도 패널 코드: 이미 적용되어 있습니다.")
        return
    check_hook_context(dll)
    if game_running():
        sys.exit("게임이 실행 중입니다. 게임을 완전히 끄고 다시 시도하세요.")
    need_bak(dll, k[0])
    if k[0] == "v1":
        _remove_v1(dll)                                                 # 이전 버전(개발 도구) 코드: 후크 -> 조각 순서로 먼저 되돌림
        print("이전 버전 지도 패널 코드(개발 도구)를 새 버전으로 교체합니다.")
    if os.path.getsize(dll) == ORIGINAL_SIZE:                           # .itdx 페이지(다른 패치와 공유)가 없으면 만든다
        with open(dll, "ab") as f:
            f.write(b"\xcc" * PAGE)
            f.flush()
            os.fsync(f.fileno())
    for _n, off, orig, new in HEADER:
        if read_at(dll, off, len(orig) // 2).hex() not in (new, HDR_ALT.get(off)):
            _write(dll, off, bytes.fromhex(orig), bytes.fromhex(new))
    if os.path.getsize(dll) == ORIGINAL_SIZE + PAGE:                    # .itd2 구역: 파일 끝에 붙이고 -> 헤더 -> 구역 수 -> SizeOfImage
        with open(dll, "ab") as f:
            f.write(b"\xcc" * PAGE2)
            f.flush()
            os.fsync(f.fileno())
        _write(dll, ITD2_HDR_OFF, b"\x00" * 40, bytes.fromhex(ITD2_HDR))
        _write(dll, 294, bytes.fromhex("0800"), bytes.fromhex("0900"))
        _write(dll, 368, bytes.fromhex("00605e06"), bytes.fromhex("00705e06"))
    cur = read_at(dll, ORIGINAL_SIZE + PAGE, PAGE2)
    if cur != SECTION:
        _write(dll, ORIGINAL_SIZE + PAGE, cur, SECTION)                 # 코드 (아직 아무도 점프하지 않음)
    if hookbytes(dll) == "orig":
        _write(dll, HOOK_OFF, bytes.fromhex(HOOK_ORIG), bytes.fromhex(HOOK_NEW))   # 후크 (마지막)
    k2 = state(dll)
    if k2[0] != "final":
        sys.exit("중단: 쓴 뒤 검증에 실패했습니다 (%s). 'revert' 로 되돌리거나 GameAssembly.dll.bak 으로 복원하세요." % (k2,))
    print("지도 패널 코드 적용 (검증 완료)")


def cmd_revert(dll):
    if not os.path.isfile(dll):
        return
    try:
        k = state(dll)
    except SystemExit:
        return          # 이 패치가 만들어진 게임 빌드가 아니면 건드리지 않고 조용히 끝낸다
    if k[0] is None or k[0] == "none":
        return
    if game_running():
        sys.exit("게임이 실행 중입니다. 게임을 완전히 끄고 다시 시도하세요 (지도 패널 코드를 되돌리지 못했습니다).")
    if hookbytes(dll) == "v3":                                          # 후크 먼저
        _write(dll, HOOK_OFF, bytes.fromhex(HOOK_NEW), bytes.fromhex(HOOK_ORIG))
    _remove_v1(dll)
    if os.path.getsize(dll) == ORIGINAL_SIZE + PAGE + PAGE2:            # .itd2: SizeOfImage -> 구역 수 -> 헤더 -> 파일 끝
        _write(dll, 368, bytes.fromhex("00705e06"), bytes.fromhex("00605e06"))
        _write(dll, 294, bytes.fromhex("0900"), bytes.fromhex("0800"))
        _write(dll, ITD2_HDR_OFF, bytes.fromhex(ITD2_HDR), b"\x00" * 40)
        with open(dll, "r+b") as f:
            f.truncate(ORIGINAL_SIZE + PAGE)
            f.flush()
            os.fsync(f.fileno())
    if os.path.getsize(dll) == ORIGINAL_SIZE + PAGE and read_at(dll, ORIGINAL_SIZE, PAGE) == b"\xcc" * PAGE:   # 다른 패치가 .itdx 를 안 쓰면 그것도 정리
        for _n, off, orig, new in reversed(HEADER):
            if read_at(dll, off, len(orig) // 2).hex() == new:
                _write(dll, off, bytes.fromhex(new), bytes.fromhex(orig))
        with open(dll, "r+b") as f:
            f.truncate(ORIGINAL_SIZE)
            f.flush()
            os.fsync(f.fileno())
    k2 = state(dll)
    if k2[0] != "none":
        sys.exit("중단: 되돌린 뒤 검증에 실패했습니다 (%s). GameAssembly.dll.bak 으로 복원하세요." % (k2,))
    print("지도 패널 코드를 되돌렸습니다.")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("check", "apply", "revert", "status"):
        sys.exit(__doc__)
    {"check": cmd_check, "apply": cmd_apply, "revert": cmd_revert, "status": cmd_status}[sys.argv[1]](sys.argv[2])
