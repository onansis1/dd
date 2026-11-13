"""Into the Dead: Our Darkest Days - 사용자 지정 시나리오 '랜덤 시작' (GameAssembly.dll 패치, 이 게임 빌드 전용).
사용: python patch_randstart.py <check|apply|revert|status> <GameAssembly.dll 경로>
 - 사용자 지정 시나리오 화면에서 생존자를 한 명도 고르지 않고 시작을 누르면, 후보 18명(Survivor Draw 후보에서 Bowman 제외: Cooper, Isaiah, Charlie, Hao, Kayla, Mei, Daphne, Dianne, Hector, Tracy,
   Otto, Leo, Sebastian, Taylor, Wayne, Eva, Penny, Darrel) 중 잠기지 않은 생존자를 중복 없이 3명 뽑아 선택 집합에 채우고, 시작 거점은 빈 값으로 써서 게임이 무작위 거점을 고르게 한다.
   1명 이상 직접 고르면 아무것도 바꾸지 않는다(원래 동작). 후보가 전부 잠겨 있으면 잠금을 무시하고 18명 전체에서 뽑는다.
   [v2] 화면의 새 버튼 '무술가 포함 뽑기'(patch_scnbtn.py)를 누르고 시작하면 같은 랜덤 시작이되, 뽑는 3명 안에 '무술가 후보'(표의 마스크, apply_all 이 적용할 때 계산해서 환경변수 ITD_RS_MASK 로 넘김)가 한 명 반드시 들어간다.
 - 구현: 스테이션 휠/거점 이동 패치와 같은 새 실행 구역 '.itdx'(없으면 만든다)의 RVA 0x65E5AA0(파일 0x631A0A0)부터 704바이트(동굴 414바이트 + 후보표 288바이트)를 쓰고, 후크 3개를 연결한다.
   (2) StartGameWithParameters(0xE0D403): 선택 집합을 읽기 직전에 동굴로 점프 (게임 함수 OnSurvivorClicked/IsSurvivorLocked 를 부른다. 호출이 있는 첫 패치)
   (3) OnStateChanged(0xE0D317)와 (4) 화면을 열 때 도는 같은 로직의 인라인 복사본(0xE15604): 0명일 때 시작 버튼 비활성 값(xor dl,dl)을 활성(mov dl,1)으로. 반드시 마지막.
 - 게임 파일 안의 다른 것은 건드리지 않는다. 개발 중 도구(itd_random_start_patch.py)로 적용한 파일도 같은 최종 상태로 알아본다.
   적용 순서: 코드 -> StartGame -> OnStateChanged -> OnShowInline, 되돌리기는 반대(후크 먼저). 3/4만 먼저 적용되면 0명으로 시작될 수 있어 항상 이 순서로만 쓴다.
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
CAVE_OFF = 0xAA0                      # 새 구역 안의 위치 (파일: ORIGINAL_SIZE + 0xAA0 = 0x631A0A0)
OLD_CAVE = "4883ec4048895c24304989c6488b8e080100004885c90f846a010000488b81f80000004885c00f845a010000837820000f85500100004883b900010000000f84420100004883b980000000000f84340100004883be18010000000f842601000031ff31db488b8e08010000488d052e0100004889da48c1e2040f1004100f11442420488d5424204531c0e851aa82fa84c075030fabdfffc383fb1272c785ff7505bfffff03000f3148c1e2204809d04889c5c74424380300000085ff0f84b300000089f831c985c074098d50ff21d0ffc1ebf348b8157c4a7fb979379e4801c54889e84889c248c1ea1e4831d048bab9e5e41c6d4758bf480fafc24889c248c1ea1b4831d048baeb113113bb49d094480fafc24889c248c1ea1f4831d048c1e820480fafc148c1e82089c289f885d274098d48ff21c8ffcaebf30fbcd80fb3df488b8e08010000488d05520000004889da48c1e2040f1004100f11442420488d5424204531c0e805ac82faff4c24380f8545ffffff488b86180100000f57c00f118090000000488b5c24304c89f04883c440488b8e08010000e9cc7782facccc82337d2c8974352cd8d06591cc51a066a22f941783815a93893969457239a80cc1d1a2c8bebdbf2c66a7bc190a9f587a81bf9c6e419efd226658e79e6feba745fd3d73e1705564575bc290f167ba6127b0fa8cc2fd756664eaf460a5486d3ad992f95004d5cd545ceff34de1beb17dba9009741c2f52d4f67c3b44ceba0c4ca95af15ed5ce0822d93ab498278dbf1ffa592b54ee6c3955f45d003ce69c0d973ccd9eb970912466300b45ab94aee8115b792422e9862224ff3b780bd9b8cb9395898e061e9d2165c50b05a3cfeb968161e7bc45fff9465a2fa297a5b41cb3552be72e95db55eab0eee2d1e394c74b250e62921bb0081574f73758bc6ed584185aa9768b67619548f91a54d201b8da2a8d27ac7f7378f9c84ba9ec99ac032992b3"        # 이전 버전(v1, 704바이트: 코드 414 + 후보표 288 + 여백). 새 버전으로 교체 대상
CAVE = "4883ec5048895c24304989c6c7442444000000004889f1e804bdbbfd4885c0747f488378100074784889c34889d9e8ad94bdfd83f80675684889d9ba05000000e8bb70bdfd4885c074564883781000744f4889c1e8e7bbbbfd4885c074424883781000743b4889c74889f931d2e86e18bcfd84c0742a4889f931d24531c0e87d11bcfd48837f100074164889f931d2e84c18bcfd84c07508c744244401000000488b8e080100004885c90f84a1010000488b81f80000004885c00f8491010000837820000f85870100004883b900010000000f84790100004883b980000000000f846b0100004883be18010000000f845d01000031ff31db488b8e08010000488d056a0100004889da48c1e2040f1004100f11442420488d5424204531c0e8bda982fa84c075030fabdfffc383fb1272c785ff7505bfffff03000f3148c1e2204809d04889c5c744243803000000c744244000000000837c244400740c8b052d02000021f88944244085ff0f84cf0000004189f98b44244085c0740fc74424400000000021f874034189c14489c831c985c074098d50ff21d0ffc1ebf348b8157c4a7fb979379e4801c54889e84889c248c1ea1e4831d048bab9e5e41c6d4758bf480fafc24889c248c1ea1b4831d048baeb113113bb49d094480fafc24889c248c1ea1f4831d048c1e820480fafc148c1e82089c24489c885d274098d48ff21c8ffcaebf30fbcd80fb3df488b8e08010000488d05570000004889da48c1e2040f1004100f11442420488d5424204531c0e83aab82faff4c24380f8529ffffff488b86180100000f57c00f118090000000488b5c24304c89f04883c450488b8e08010000e9017782facccccccccccccc82337d2c8974352cd8d06591cc51a066a22f941783815a93893969457239a80cc1d1a2c8bebdbf2c66a7bc190a9f587a81bf9c6e419efd226658e79e6feba745fd3d73e1705564575bc290f167ba6127b0fa8cc2fd756664eaf460a5486d3ad992f95004d5cd545ceff34de1beb17dba9009741c2f52d4f67c3b44ceba0c4ca95af15ed5ce0822d93ab498278dbf1ffa592b54ee6c3955f45d003ce69c0d973ccd9eb970912466300b45ab94aee8115b792422e9862224ff3b780bd9b8cb9395898e061e9d2165c50b05a3cfeb968161e7bc45fff9465a2fa297a5b41cb3552be72e95db55eab0eee2d1e394c74b250e62921bb0081574f73758bc6ed584185aa9768b67619548f91a54d201b8da2a8d27ac7f7378f9c84ba9ec99ac032992b300000000000000000000000000000000"            # v2 (928바이트: 코드 617 + 후보표 288 + 무술가 마스크 4 + 여백). 마스크 자리(MASK_OFF)는 0 으로 두고 적용할 때 값을 쓴다
MASK_OFF = 912                       # CAVE 안의 u32(little-endian) 위치 = 파일 0x631A430: 비트 i = 후보 i (후보표 순서)가 '무술가 후보'
CAVE_LEN = len(CAVE) // 2
OLD_LEN = len(OLD_CAVE) // 2

# --- PE 헤더 3곳 (구역 .itdx 추가; 스테이션 휠 패치와 같은 값)
HEADER = [
    ("구역 헤더 .itdx", 832, "00" * 40, "2e697464780000000010000000505e06001000000096310600000000000000000000000020000060"),
    ("SizeOfImage 0x65E5000 -> 0x65E6000", 368, "00505e06", "00605e06"),
    ("NumberOfSections 7 -> 8", 294, "0700", "0800"),
]
# --- 후크 (적용 순서; 마지막 둘은 시작 버튼 활성이라 코드와 첫 후크가 먼저여야 한다): (이름, 파일 위치, 원래 바이트, 바꿀 바이트, 앞 20바이트, 뒤 20바이트)
HOOKS = [
    ('2-hook-StartGame', 14730755, '488b8e08010000', 'e998867d056690',
     '8bcfe8ca218aff4c8b00488bcf488b500841ffd0', '488bf84885c90f84140100004c8bb1f800000048'),
    ('3-hook-OnStateChanged', 14730519, '32d2', 'b201',
     '0401488b83f80000004885c07434837820007f04', 'eb0c488bc88b43483941200f9ec2488b8f100100'),
    ('4-hook-OnShowInline', 14764036, '32d2', 'b201',
     '87f80000004885c00f8425010000837820007f21', 'eb290fb7c94803c9496344c80848c1e004480538'),
]


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


def cave_kind(dll):
    """새 구역의 우리 코드 자리: 'cc'(비어 있음) | 'final'(v2, 마스크 값은 무시) | 'old'(v1 704바이트) | 'other'"""
    cur = read_at(dll, ORIGINAL_SIZE + CAVE_OFF, CAVE_LEN)
    if cur == b"\xcc" * CAVE_LEN:
        return "cc"
    if cur[:MASK_OFF] + b"\0\0\0\0" + cur[MASK_OFF + 4:] == bytes.fromhex(CAVE):
        return "final"
    if cur[:OLD_LEN] == bytes.fromhex(OLD_CAVE) and cur[OLD_LEN:] == b"\xcc" * (CAVE_LEN - OLD_LEN):
        return "old"
    return "other"


def want_mask():
    """apply_all 이 적용할 때 계산해 환경변수 ITD_RS_MASK(16진수)로 넘기는 '무술가 후보' 마스크. 없으면 None."""
    v = os.environ.get("ITD_RS_MASK", "").strip()
    return (int(v, 16) & 0x3FFFF) if v else None


def cur_mask(dll):
    return struct.unpack("<I", read_at(dll, ORIGINAL_SIZE + CAVE_OFF + MASK_OFF, 4))[0]


def new_blob(dll, kind):
    m = want_mask()
    if m is None:
        m = cur_mask(dll) if kind == "final" else 0
    b = bytearray.fromhex(CAVE)
    b[MASK_OFF:MASK_OFF + 4] = struct.pack("<I", m)
    return bytes(b)


def refresh_mask(dll):
    m = want_mask()
    if m is not None and cave_kind(dll) == "final" and cur_mask(dll) != m:
        _write(dll, ORIGINAL_SIZE + CAVE_OFF + MASK_OFF, read_at(dll, ORIGINAL_SIZE + CAVE_OFF + MASK_OFF, 4), struct.pack("<I", m))
        print("무술가 후보 마스크 갱신: 0x%05X" % m)


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


def state(dll):
    """('ok', k) k = 0(수정 없음) / 1(코드만) / 2~4(후크 n-1개) / 'partial'(순서가 다른 알려진 중간 상태), 알 수 없으면 (None, 이유)"""
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
        sec = "none"                                 # 페이지만 붙은 중간 상태 (스테이션 휠 패치와 같음)
    else:
        return None, "구역 헤더 상태가 알려진 어떤 단계와도 맞지 않습니다: %s" % h3
    cave = cave_kind(dll)
    if cave == "other":
        return None, "새 구역의 우리 코드 자리가 0xCC 도, 우리 코드도 아닙니다"
    if any(x == "final" for x in hs) and (cave not in ("final", "old") or sec != "new"):
        return None, "후크는 연결돼 있는데 새 구역에 우리 코드가 없습니다 (그대로 두면 게임이 멈춥니다)"
    if cave == "cc":
        return "ok", 0                               # 코드가 없으면 우리 패치는 적용 전 (구역이 있든 없든)
    nfin = hs.count("final")
    if cave == "old":
        return "ok", "old"                           # v1 코드: 새 버전으로 교체 대상
    if hs == ["final"] * nfin + ["orig"] * (3 - nfin):
        return "ok", 1 + nfin
    return "ok", "partial"


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
    if k[0] is None:
        print("상태: 알 수 없음 -", k[1])
    else:
        print("상태:", ("%d/4 단계" % k[1]) if isinstance(k[1], int) else "알려진 중간 단계(적용하면 마지막 단계로 이동)")


def cmd_check(dll):
    need_dll(dll)
    k = state(dll)
    if k[0] is None:
        sys.exit("랜덤 시작: GameAssembly.dll 의 패치 위치가 알려진 어떤 상태와도 맞지 않습니다. 건드리지 않았습니다.\n(%s)\n"
                 "(원본으로 되돌리려면 GameAssembly.dll.bak 을 GameAssembly.dll 로 덮어쓰거나 스팀에서 '게임 파일 무결성 검사'를 하세요.)" % k[1])
    check_hook_context(dll)
    need_bak(dll, k[1] if isinstance(k[1], int) else 4, create=False)
    if game_running():
        sys.exit("게임이 실행 중입니다. 게임을 완전히 끄고 다시 시도하세요.")
    print("랜덤 시작: 적용 가능 (현재 %s)" % (("%d/4 단계" % k[1]) if isinstance(k[1], int) else "중간 단계"))


def cmd_apply(dll):
    need_dll(dll)
    k = state(dll)
    if k[0] is None:
        sys.exit("랜덤 시작: 알 수 없는 상태입니다 (%s). 건드리지 않았습니다." % k[1])
    if k[1] == 4:
        refresh_mask(dll)
        print("랜덤 시작: 이미 적용되어 있습니다.")
        return
    check_hook_context(dll)
    if game_running():
        sys.exit("게임이 실행 중입니다. 게임을 완전히 끄고 다시 시도하세요.")
    need_bak(dll, k[1] if isinstance(k[1], int) else 4)
    if k[1] == "old":                                                   # v1 -> v2: 후크를 먼저 걷고(반대 순서) 코드를 바꾼 뒤 다시 연결한다
        for h in reversed(HOOKS):
            if hookstate(dll, h) == "final":
                _write(dll, h[1], bytes.fromhex(h[3]), bytes.fromhex(h[2]))
        print("이전 버전 랜덤 시작 코드를 새 버전(무술가 포함 뽑기 지원)으로 교체합니다.")
    if os.path.getsize(dll) == ORIGINAL_SIZE:                           # 1) 새 페이지(0xCC) 붙이기 (스테이션 휠 패치가 이미 만들었으면 건너뜀)
        with open(dll, "ab") as f:
            f.write(b"\xcc" * PAGE)
            f.flush()
            os.fsync(f.fileno())
    for _n, off, orig, new in HEADER:                                   # 2~4) 구역 헤더, SizeOfImage, 구역 수 (순서대로)
        if read_at(dll, off, len(orig) // 2).hex() not in (new, HDR_ALT.get(off)):
            _write(dll, off, bytes.fromhex(orig), bytes.fromhex(new))
    cur = read_at(dll, ORIGINAL_SIZE + CAVE_OFF, CAVE_LEN)              # 5) 동굴 코드 (점프는 아직 없음)
    cb = new_blob(dll, cave_kind(dll))
    if cur != cb:
        _write(dll, ORIGINAL_SIZE + CAVE_OFF, cur, cb)
    for h in HOOKS:                                                     # 6~8) 후크 연결 (StartGame 먼저, 시작 버튼 활성 후크는 마지막)
        if hookstate(dll, h) == "orig":
            _write(dll, h[1], bytes.fromhex(h[2]), bytes.fromhex(h[3]))
    k2 = state(dll)
    if k2 != ("ok", 4):
        sys.exit("중단: 쓴 뒤 검증에 실패했습니다 (%s). 'revert' 로 되돌리거나 GameAssembly.dll.bak 으로 복원하세요." % (k2,))
    print("랜덤 시작 적용: 4/4 단계 (검증 완료)")
    if want_mask() is not None:
        print("무술가 후보 마스크: 0x%05X" % cur_mask(dll))


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
        sys.exit("게임이 실행 중입니다. 게임을 완전히 끄고 다시 시도하세요 (랜덤 시작을 되돌리지 못했습니다).")
    for h in reversed(HOOKS):                                           # 후크 먼저 (코드가 있는 동안에), 반대 순서
        if hookstate(dll, h) == "final":
            _write(dll, h[1], bytes.fromhex(h[3]), bytes.fromhex(h[2]))
    if cave_kind(dll) in ("final", "old"):                              # 우리 코드 자리만 0xCC 로
        cur = read_at(dll, ORIGINAL_SIZE + CAVE_OFF, CAVE_LEN)
        _write(dll, ORIGINAL_SIZE + CAVE_OFF, cur, b"\xcc" * CAVE_LEN)
    shared = (not page_rest_clean(dll)) or os.path.getsize(dll) == ORIGINAL_SIZE + PAGE + PAGE2
    if not shared:                                                      # 스테이션 휠 패치가 이 구역을 안 쓰면 구역/페이지도 제거
        for _n, off, orig, new in reversed(HEADER):                     # 구역 수 -> SizeOfImage -> 구역 헤더
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
    print("랜덤 시작을 되돌렸습니다." + (" (새 구역은 스테이션 휠 패치가 쓰고 있어 남겨 뒀습니다.)" if shared else " (원래 크기로 복구)"))


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("check", "apply", "revert", "status"):
        sys.exit(__doc__)
    {"check": cmd_check, "apply": cmd_apply, "revert": cmd_revert, "status": cmd_status}[sys.argv[1]](sys.argv[2])
