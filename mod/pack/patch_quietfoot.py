"""Into the Dead: Our Darkest Days - 게임 옵션(접근성)의 '발걸음 소리 무음' 토글이 실제로 발소리를 끄게 하는 코드 (GameAssembly.dll 패치, 이 게임 빌드 전용).
사용: python patch_quietfoot.py <check|apply|revert|status> <GameAssembly.dll 경로>
 - ACharacterNoise.PostSimulate(RVA 0xA64B5D)의 '발소리를 만들 시점'에서, 이 객체가 생존자(SurvivorNoise)일 때만 PlayerPrefs 값 drs.accessibility.quiet_footsteps 를 읽어
   1 이면 발소리 생성만 건너뛴다(주기는 유지). 값이 없거나(기본 0) 읽기에 실패하면 원래 소음 그대로이고, 좀비/NPC 는 영향 없음. 문/루팅/전투 소음은 이 지점을 지나지 않아 그대로다.
 - 옵션 항목 자체(게임 옵션 화면의 한 줄)는 data_user_settings 번들(patch_quietopt.py)이 추가한다. 이 패치는 값을 읽어 반영하는 코드만 담당한다.
 - 구현: 스테이션 휠/랜덤 시작과 같은 새 실행 구역 '.itdx'(없으면 만든다) 페이지 꼬리 RVA 0x65E5E80(파일 0x631A480)에 130바이트(코드 81 + 키 문자열 34)를 쓰고 후크 1개를 연결한다.
   적용 순서: 코드 -> 후크, 되돌리기는 반대(후크 먼저).
 - 이 게임 빌드(SHA-256 3F45B1F9...)에서만 적용한다. 쓰기 전에 GameAssembly.dll.bak 이 원본인지 확인하고(없으면 파일이 원본일 때만 만든다), 후크 앞뒤 20바이트가 예상과 같은지 확인하고, 쓴 뒤 읽어서 확인한다.
 - 게임이 실행 중이면 중단한다. check 는 아무것도 쓰지 않고 적용 가능한지만 본다.
"""
import hashlib, os, shutil, struct, subprocess, sys

ORIGINAL_SHA256 = "3F45B1F9FA8B5F28AD4A0ECAAA87DB1A1D711BC559DBB1A3672855D82F9061C8"
ORIGINAL_SIZE = 103912960
PAGE = 4096
HDR_ALT = {368: "00705e06", 294: "0900"}                              # 지도 패널 코드(.itd2 구역)가 더해졌을 때 SizeOfImage / 구역 수
PAGE2 = 0xA00                                                        # .itd2 구역 크기 (patch_panelcode.py)
GAME_EXE = "IntoTheDeadOurDarkestDays.exe"
CAVE_OFF = 0xE80                      # 새 구역 안의 위치 (파일: ORIGINAL_SIZE + 0xE80 = 0x631A480)
CAVE = "488b5818488b07488b0d52cd46ff4885c974344839c8752f4883ec40488d0d3d000000e828f510fa4885c074164889c1e86ba7bcfd4883c44083f8017509e9e6ec47fa4883c440488d4c2450e995ec47facccccccccccccccccccccccccccccc6472732e6163636573736962696c6974792e71756965745f666f6f74737465707300"
CAVE_LEN = len(CAVE) // 2

# --- PE 헤더 3곳 (구역 .itdx 추가; 스테이션 휠 패치와 같은 값)
HEADER = [
    ("구역 헤더 .itdx", 832, "00" * 40, "2e697464780000000010000000505e060010000000963106000000000000000000000000200000" "60"),
    ("SizeOfImage 0x65E5000 -> 0x65E6000", 368, "00505e06", "00605e06"),
    ("NumberOfSections 7 -> 8", 294, "0700", "0800"),
]
# --- 후크: (이름, 파일 위치, 원래 바이트, 바꿀 바이트, 앞 20바이트, 뒤 20바이트)
HOOKS = [
    ('2-hook-PostSimulate', 10894685, '488b5818488d4c2450', 'e91e13b80590909090',
     '84a2000000f30f104820f30f584f540f2fc17258', '4533c0488bd7e81f0e000048897424304c8d4424'),
]
FULL = 1 + len(HOOKS)


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
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + GAME_EXE], capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return GAME_EXE.lower() in out.lower()
    except Exception:
        return False


def need_dll(dll):
    if not os.path.isfile(dll):
        sys.exit("GameAssembly.dll 을 찾을 수 없습니다: " + dll)


def verify_layout(dll):
    """PE 헤더/구역 표가 이 패치가 만들어진 빌드와 같은 모양인지 본다. 다르면 중단."""
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
    prev_end = 0
    for i in range(nsec):
        e = tab + 40 * i
        vs, va, rs, rp = struct.unpack_from("<IIII", hdr, e + 8)
        if va < prev_end or va % sa or rp % fa or rs % fa:
            sys.exit("중단: 구역 %d 의 순서/정렬이 예상과 다릅니다." % i)
        prev_end = va + ((max(vs, 1) + sa - 1) // sa) * sa
    return nsec


def hdrstate(dll):
    out = []
    for _n, off, orig, new in HEADER:
        cur = read_at(dll, off, len(orig) // 2).hex()
        out.append("orig" if cur == orig else "new" if cur in (new, HDR_ALT.get(off)) else "other")
    return out


def hookstate(dll, h):
    _n, off, orig, final, _b, _a = h
    cur = read_at(dll, off, len(orig) // 2).hex()
    return "orig" if cur == orig else "final" if cur == final else "other"


def check_hook_context(dll):
    for _n, off, orig, _f, before, after in HOOKS:
        if read_at(dll, off - 20, 20).hex() != before or read_at(dll, off + len(orig) // 2, 20).hex() != after:
            sys.exit("중단: %s 주변의 코드가 예상과 다릅니다 (게임이 업데이트되었거나 다른 빌드입니다)." % _n)


def page_rest_clean(dll):
    """새 구역에서 우리 코드 자리를 뺀 나머지가 전부 0xCC 인지 (다른 패치(스테이션 휠)가 이 구역을 쓰고 있지 않은지)"""
    data = read_at(dll, ORIGINAL_SIZE, PAGE)
    rest = data[:CAVE_OFF] + data[CAVE_OFF + CAVE_LEN:]
    return rest == b"\xcc" * len(rest)


def cave_kind(dll):
    """새 구역의 우리 코드 자리: 'cc'(비어 있음) | 'final' | 'other'"""
    cur = read_at(dll, ORIGINAL_SIZE + CAVE_OFF, CAVE_LEN)
    if cur == b"\xcc" * CAVE_LEN:
        return "cc"
    return "final" if cur == bytes.fromhex(CAVE) else "other"


def state(dll):
    """('ok', k) k = 0(수정 없음) / 1(코드만) / 2(코드+후크); 알 수 없으면 (None, 이유)"""
    nsec = verify_layout(dll)
    size = os.path.getsize(dll)
    hs = [hookstate(dll, h) for h in HOOKS]
    if "other" in hs:
        return None, "후크 자리가 원래도 패치된 값도 아닙니다: %s" % hs
    if size == ORIGINAL_SIZE:
        if nsec != 7 or any(x != "orig" for x in hdrstate(dll)) or any(x != "orig" for x in hs):
            return None, "새 구역이 없는데 헤더/후크가 바뀌어 있습니다"
        return "ok", 0
    if size not in (ORIGINAL_SIZE + PAGE, ORIGINAL_SIZE + PAGE + PAGE2):
        return None, "파일 크기 %d 가 원본(%d)도 원본+%d 도 아닙니다" % (size, ORIGINAL_SIZE, PAGE)
    h3 = hdrstate(dll)
    if h3 == ["new"] * 3 and nsec in (8, 9):
        sec = "new"
    elif h3 == ["orig"] * 3 and nsec == 7:
        sec = "none"
    else:
        return None, "구역 헤더 상태가 알려진 어떤 단계와도 맞지 않습니다: %s" % h3
    cave = cave_kind(dll)
    if cave == "other":
        return None, "새 구역의 우리 코드 자리가 0xCC 도, 우리 코드도 아닙니다"
    if any(x == "final" for x in hs) and (cave != "final" or sec != "new"):
        return None, "후크는 연결돼 있는데 새 구역에 우리 코드가 없습니다 (그대로 두면 게임이 멈춥니다)"
    if cave == "cc":
        return "ok", 0
    nfin = hs.count("final")
    return "ok", 1 + nfin



def need_bak(dll, k, create=True):
    bak = dll + ".bak"
    if os.path.exists(bak):
        if os.path.getsize(bak) != ORIGINAL_SIZE or sha256(bak) != ORIGINAL_SHA256:
            sys.exit("중단: %s 가 원본이 아닙니다 (크기/해시 불일치). 이 파일을 확인하거나 이름을 바꿔 두고 다시 시도하세요." % bak)
        return
    if size_other_patched(dll, k):
        print("안내: %s 가 없습니다. 이미 다른 패치가 적용된 상태라 백업은 만들지 않습니다 (되돌릴 때는 단계 표로 원상 복구)." % os.path.basename(bak))
        return
    if not create:
        return
    if os.path.getsize(dll) != ORIGINAL_SIZE or sha256(dll) != ORIGINAL_SHA256:
        sys.exit("중단: GameAssembly.dll.bak(원본 백업)이 없고, 지금 파일도 수정되지 않은 원본이 아니라서 백업을 만들 수 없습니다.\n"
                 "스팀 '게임 파일 무결성 검사'로 원본을 되돌린 뒤 다시 시도하세요.")
    shutil.copy2(dll, bak)
    print("백업 생성:", bak)


def size_other_patched(dll, k):
    return os.path.getsize(dll) != ORIGINAL_SIZE or k != 0


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
    print("상태:", ("알 수 없음 - " + k[1]) if k[0] is None else "%d/%d 단계" % (k[1], FULL))


def cmd_check(dll):
    need_dll(dll)
    k = state(dll)
    if k[0] is None:
        sys.exit("발걸음 소리 토글(코드): GameAssembly.dll 의 패치 위치가 알려진 어떤 상태와도 맞지 않습니다. 건드리지 않았습니다.\n(%s)\n"
                 "(원본으로 되돌리려면 GameAssembly.dll.bak 을 GameAssembly.dll 로 덮어쓰거나 스팀에서 '게임 파일 무결성 검사'를 하세요.)" % k[1])
    check_hook_context(dll)
    need_bak(dll, k[1], create=False)
    if game_running():
        sys.exit("게임이 실행 중입니다. 게임을 완전히 끄고 다시 시도하세요.")
    print("발걸음 소리 토글(코드): 적용 가능 (현재 %d/%d 단계)" % (k[1], FULL))


def cmd_apply(dll):
    need_dll(dll)
    k = state(dll)
    if k[0] is None:
        sys.exit("발걸음 소리 토글(코드): 알 수 없는 상태입니다 (%s). 건드리지 않았습니다." % k[1])
    if k[1] == FULL:
        print("발걸음 소리 토글(코드): 이미 적용되어 있습니다.")
        return
    check_hook_context(dll)
    if game_running():
        sys.exit("게임이 실행 중입니다. 게임을 완전히 끄고 다시 시도하세요.")
    need_bak(dll, k[1])
    if os.path.getsize(dll) == ORIGINAL_SIZE:                           # 1) 새 페이지(0xCC) 붙이기 (다른 패치가 이미 만들었으면 건너뜀)
        with open(dll, "ab") as f:
            f.write(b"\xcc" * PAGE)
            f.flush()
            os.fsync(f.fileno())
    for _n, off, orig, new in HEADER:                                   # 2~4) 구역 헤더, SizeOfImage, 구역 수 (순서대로)
        if read_at(dll, off, len(orig) // 2).hex() not in (new, HDR_ALT.get(off)):
            _write(dll, off, bytes.fromhex(orig), bytes.fromhex(new))
    cb = bytes.fromhex(CAVE)                                            # 5) 코드 (점프는 아직 없음)
    if read_at(dll, ORIGINAL_SIZE + CAVE_OFF, CAVE_LEN) != cb:
        _write(dll, ORIGINAL_SIZE + CAVE_OFF, b"\xcc" * CAVE_LEN, cb)
    for h in HOOKS:                                                     # 6) 후크 연결 (마지막)
        if hookstate(dll, h) == "orig":
            _write(dll, h[1], bytes.fromhex(h[2]), bytes.fromhex(h[3]))
    k2 = state(dll)
    if k2 != ("ok", FULL):
        sys.exit("중단: 쓴 뒤 검증에 실패했습니다 (%s). 'revert' 로 되돌리거나 GameAssembly.dll.bak 으로 복원하세요." % (k2,))
    print("발걸음 소리 토글(코드) 적용: %d/%d 단계 (검증 완료)" % (FULL, FULL))


def cmd_revert(dll):
    if not os.path.isfile(dll):
        return
    try:
        k = state(dll)
    except SystemExit:
        return          # 이 패치가 만들어진 게임 빌드가 아니면 건드리지 않고 조용히 끝낸다
    if k[0] is None or k[1] == 0:
        return          # 알 수 없는 파일이거나 건드리지 않은 파일이면 조용히 끝낸다
    if game_running():
        sys.exit("게임이 실행 중입니다. 게임을 완전히 끄고 다시 시도하세요 (발걸음 소리 토글(코드)를 되돌리지 못했습니다).")
    for h in reversed(HOOKS):                                           # 후크 먼저 (코드가 있는 동안에)
        if hookstate(dll, h) == "final":
            _write(dll, h[1], bytes.fromhex(h[3]), bytes.fromhex(h[2]))
    if cave_kind(dll) == "final":                                       # 우리 코드 자리만 0xCC 로
        cur = read_at(dll, ORIGINAL_SIZE + CAVE_OFF, CAVE_LEN)
        _write(dll, ORIGINAL_SIZE + CAVE_OFF, cur, b"\xcc" * CAVE_LEN)
    shared = (not page_rest_clean(dll)) or os.path.getsize(dll) == ORIGINAL_SIZE + PAGE + PAGE2
    if not shared:                                                      # 다른 패치가 이 구역을 안 쓰면 구역/페이지도 제거
        for _n, off, orig, new in reversed(HEADER):
            if read_at(dll, off, len(orig) // 2).hex() == new:
                _write(dll, off, bytes.fromhex(new), bytes.fromhex(orig))
        with open(dll, "r+b") as f:
            if os.fstat(f.fileno()).st_size == ORIGINAL_SIZE + PAGE and read_at(dll, ORIGINAL_SIZE, PAGE) == b"\xcc" * PAGE:
                f.truncate(ORIGINAL_SIZE)
                f.flush()
                os.fsync(f.fileno())
    k2 = state(dll)
    if k2 != ("ok", 0):
        sys.exit("중단: 되돌린 뒤 검증에 실패했습니다 (%s). GameAssembly.dll.bak 으로 복원하세요." % (k2,))
    print("발걸음 소리 토글(코드)를 되돌렸습니다." + (" (새 구역은 다른 패치가 쓰고 있어 남겨 뒀습니다.)" if shared else " (원래 크기로 복구)"))


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("check", "apply", "revert", "status"):
        sys.exit(__doc__)
    {"check": cmd_check, "apply": cmd_apply, "revert": cmd_revert, "status": cmd_status}[sys.argv[1]](sys.argv[2])
