"""Into the Dead: Our Darkest Days - 스테이션 휠에서 '지금 조작 중인 생존자의 특기와 맞는 작업'을 금색으로 강조 (GameAssembly.dll 패치, 이 게임 빌드 전용).
사용: python patch_wheelgold.py <check|apply|revert|status> <GameAssembly.dll 경로>
 - 은신처에서 F 길게 누름으로 여는 스테이션(작업) 휠의 칸 아이콘을, (a) 지금 조작 중인 생존자가 그 작업의 특기 특성(m_relevantTraits)을 가졌고 (b) 아직 자리가 남아 있을 때만 금색으로 칠한다.
   '나쁜' 특성(Trait-BadCook 등 9개)은 겹쳐도 세지 않는다. 자리가 꽉 찬 칸은 원래의 회색을 그대로 둔다.
 - 구현: ① 실행 파일에 코드를 넣을 새 실행 구역 '.itdx'(4096바이트)를 추가한다(파일 끝 + 구역 헤더 + SizeOfImage + 구역 수). ② 그 구역에 동굴 코드(색 선택, 특기 겹침 계산, 부정 특성 표)를 쓴다.
   ③ 후크 둘: GoToStationWheel(0xA59546) -> 겹침 계산 동굴, StationWheelIconUI.PopulateBuilt(0xD7277E) -> 색 동굴. 새 코드는 call 없이 점프로 들어갔다 나온다.
 - 이 게임 빌드(SHA-256 3F45B1F9...)에서만 적용한다. 쓰기 전에 GameAssembly.dll.bak 이 원본인지 확인하고(없으면 파일이 원본일 때만 만든다), 후크 앞뒤 20바이트가 예상과 같은지 확인하고, 쓴 뒤 읽어서 확인한다.
 - 개발 중 도구(itd_space_patch.py + itd_goldicon_patch.py v2)로 이미 적용한 파일도 알아본다(중간 시험 단계의 후크도 마지막 단계로 옮긴다). 되돌리기는 후크 -> 코드 -> 구역 순서다.
 - 게임이 실행 중이면 중단한다. check 는 아무것도 쓰지 않고 적용 가능한지만 본다.
"""
import hashlib, os, shutil, struct, subprocess, sys

ORIGINAL_SHA256 = "3F45B1F9FA8B5F28AD4A0ECAAA87DB1A1D711BC559DBB1A3672855D82F9061C8"
ORIGINAL_SIZE = 103912960
PAGE = 4096
GAME_EXE = "IntoTheDeadOurDarkestDays.exe"
PAGE_RVA = 0x65E5000

# --- PE 헤더 3곳 (구역 .itdx 추가): (이름, 파일 위치, 원래 바이트, 바꿀 바이트)
HEADER = [
    ("구역 헤더 .itdx (VA 0x65E5000, 크기 0x1000, 특성 0x60000020)", 832, "00" * 40,
     "2e697464780000000010000000505e06001000000096310600000000000000000000000020000060"),
    ("SizeOfImage 0x65E5000 -> 0x65E6000", 368, "00505e06", "00605e06"),
    ("NumberOfSections 7 -> 8", 294, "0700", "0800"),
]
# --- 새 구역 안에 쓰는 코드 조각 (구역 시작에서의 위치, 바이트). 나머지는 0xCC 그대로.
CAVE_A = "837e240175164585f67e0a4439b424a80000007d070f100544000000660f7f442440e95dd678fa"       # 0x65E5100: 색 동굴(플래그 1 && 안 꽉 참 -> 금색)
GOLD = "0000803f9a99593fcdcc4c3e0000803f"                                                         # 0x65E5160: 금색 float 4개 (1.0, 0.85, 0.2, 1.0)
CAVE_B = ("488b75204885f60f84810100008b7e1883ff010f8c7501000081ff000100000f8769010000488b76104885f60f845c0100003b7e180f87530100004883c620488d3cfe4989f0488b064885c07407c7"
          "4024000000004883c6084839fe72e84c89c6488b4d304885c90f8420010000488b89c80000004885c90f8410010000488b49504885c90f84030100004c8b89900000004d85c90f84f3000000458b5118"
          "4183fa010f8ce50000004181fa000100000f87d80000004d8b49104d85c90f84cb000000453b51180f87c1000000498d49204e8d14d1488b064885c00f8495000000488b50384885d20f8488000000"
          "488b52284885d2747f448b42184183f8017c754181f800010000776c488b52104885d27463443b4218775d4883c22041c1e0044e8d04024989c94d8b394d85ff743d498b5f104d8b7f184c8d1dc1"
          "01000049833b00741149391b75064d397b08741d4983c310ebe94989d649391e75064d397e0874214983c6104d39c672ec4983c1084d39d172b24883c6084839fe0f8252ffffffeb09c740240100"
          "0000ebe8488b15cb0a47ffe9b33f47fa")                                                      # 0x65E5400: 특기 겹침 계산 (B-real2, 410바이트)
BAD_TABLE = ("0580bb36449e30bf169ee81d835b028e" "07cf7f40a744a1065dfee1f2f6bb708d" "13371991e6511b6981e4036c0eb51128" "2eefb6a7599c6d2e49f9b8f6083805f5" "315a6c476e12cd8eff233f7a0a64715a" "619bcdc76398b9420122e3cb027c2327" "aa8983f4bd2738c65ba8668fc9236678" "bafc968b4250fa3c27e8f5fd0d072864" "f20593f99bca412c6ff89a88da69a04b" "e3eda00e041f6cefaf85d9e1a74548dc" "00000000000000000000000000000000")   # 0x65E5700: 부정 특성 GUID 9개 + 사교적(Sociable, 공동구역에서는 작업 특기가 아님) + 종료 항목
OLD_BAD_TABLE = ("0580bb36449e30bf169ee81d835b028e" "07cf7f40a744a1065dfee1f2f6bb708d" "13371991e6511b6981e4036c0eb51128" "2eefb6a7599c6d2e49f9b8f6083805f5" "315a6c476e12cd8eff233f7a0a64715a" "619bcdc76398b9420122e3cb027c2327" "aa8983f4bd2738c65ba8668fc9236678" "bafc968b4250fa3c27e8f5fd0d072864" "f20593f99bca412c6ff89a88da69a04b" "00000000000000000000000000000000" "cccccccccccccccccccccccccccccccc")      # 이전 버전(Sociable 제외 전)이 쓰던 표 + 그 뒤 0xCC. 이 상태도 알아보고 새 표로 바꿔 쓴다
SHELTER_OFF, SHELTER_LEN = 0xA00, 0x360                                    # patch_shelter.py(0xA00~0xAA0)/patch_randstart.py(0xAA0~0xD60)가 같은 구역의 이 자리를 쓴다 (겹치지 않음)
CODE = [("색 동굴 A", 0x100, CAVE_A), ("금색 상수", 0x160, GOLD), ("겹침 계산 동굴 B", 0x400, CAVE_B), ("부정 특성 표", 0x700, BAD_TABLE)]
ALT = {"부정 특성 표": OLD_BAD_TABLE}                                   # 코드 조각의 알려진 이전 버전
# --- 후크 둘: (이름, 파일 위치, 원래 바이트, 마지막 단계 바이트, 개발 중 시험 단계 바이트들, 앞 20바이트, 뒤 20바이트)
HOOKS = [
    ("후크 B GoToStationWheel(0xA59546) -> 겹침 계산", 0xA58746, "488b1513cbff04", "e9b5beb8059090", ["e935bcb8059090"],
     "4518ffc38bcb4885c00f84f8000000e9fcfeffff", "488b5d2083bae400000000750f488bcae84eebc4"),
    ("후크 A PopulateBuilt(0xD7277E) -> 색 선택", 0xD7197E, "660f7f442440", "e97d29870590", ["e97d28870590"],
     "4360eb040f1043704885c90f84be0000004c8b01", "498b80a80200004d8b80b0020000488d542440ff"),
]


def pe_geometry(path):
    with open(path, "rb") as f:
        hdr = f.read(0x1000)
    pe = struct.unpack_from("<I", hdr, 0x3C)[0]
    if hdr[pe:pe + 4] != b"PE\0\0":
        sys.exit("PE 파일이 아닙니다: " + path)
    fh = pe + 4
    nsec = struct.unpack_from("<H", hdr, fh + 2)[0]
    optsz = struct.unpack_from("<H", hdr, fh + 16)[0]
    opt = fh + 20
    g = dict(nsec=nsec, nsec_off=fh + 2, soi_off=opt + 56, soi=struct.unpack_from("<I", hdr, opt + 56)[0],
             sa=struct.unpack_from("<I", hdr, opt + 32)[0], fa=struct.unpack_from("<I", hdr, opt + 36)[0],
             checksum=struct.unpack_from("<I", hdr, opt + 64)[0], tab=opt + optsz)
    secs = []
    for i in range(nsec):
        e = g["tab"] + 40 * i
        vs, va, rs, rp = struct.unpack_from("<IIII", hdr, e + 8)
        secs.append(dict(name=hdr[e:e + 8].rstrip(b"\0").decode("latin1"), vs=vs, va=va, rs=rs, rp=rp))
    g["secs"] = secs
    return g


def verify_layout(dll):
    """구역 표가 이 패치가 만들어진 빌드와 같은 모양인지(헤더 위치, 정렬, 겹침) 본다. 다르면 중단."""
    g = pe_geometry(dll)
    if (g["nsec_off"], g["soi_off"], g["tab"] + 40 * 7) != (294, 368, 832):
        sys.exit("중단: PE 헤더의 모양이 이 패치와 다릅니다 (다른 빌드이거나 파일이 다릅니다).")
    if g["checksum"] != 0 or (g["sa"], g["fa"]) != (0x1000, 0x200):
        sys.exit("중단: PE 정렬/체크섬이 이 패치와 다릅니다.")
    if g["nsec"] not in (7, 8):
        sys.exit("중단: 구역 수(%d)가 예상과 다릅니다." % g["nsec"])
    prev_end = 0
    for s in g["secs"]:
        if s["va"] < prev_end or s["va"] % g["sa"] or s["rp"] % g["fa"] or s["rs"] % g["fa"]:
            sys.exit("중단: 구역 %s 의 순서/정렬이 예상과 다릅니다." % s["name"])
        prev_end = s["va"] + ((max(s["vs"], 1) + g["sa"] - 1) // g["sa"]) * g["sa"]
    return g


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


def hookstate(dll, h):
    """'orig' | 'final' | 'test'(개발 중 시험 단계) | 'other'"""
    _n, off, orig, final, tests, _b, _a = h
    cur = read_at(dll, off, len(orig) // 2).hex()
    if cur == orig:
        return "orig"
    if cur == final:
        return "final"
    if cur in tests:
        return "test"
    return "other"


def check_hook_context(dll):
    for h in HOOKS:
        _n, off, orig, _f, _t, before, after = h
        if read_at(dll, off - 20, 20).hex() != before or read_at(dll, off + len(orig) // 2, 20).hex() != after:
            sys.exit("중단: %s 주변의 코드가 예상과 다릅니다 (게임이 업데이트되었거나 다른 빌드입니다)." % h[0])


def hdrstate(dll):
    out = []
    for _n, off, orig, new in HEADER:
        cur = read_at(dll, off, len(orig) // 2).hex()
        out.append("orig" if cur == orig else "new" if cur == new else "other")
    return out


def pagestate(dll):
    """새 구역 쪽 상태: (size_kind, regions) -- size_kind 'orig'|'page'|None, regions: 코드 조각마다 'cc'|'final'|'other' ('page'일 때만)"""
    size = os.path.getsize(dll)
    if size == ORIGINAL_SIZE:
        return "orig", None
    if size != ORIGINAL_SIZE + PAGE:
        return None, None
    regs = []
    for nm, po, hx in CODE:
        b = bytes.fromhex(hx)
        cur = read_at(dll, ORIGINAL_SIZE + po, len(b))
        regs.append("cc" if cur == b"\xcc" * len(b) else "final" if cur == b else "old" if (nm in ALT and cur == bytes.fromhex(ALT[nm])) else "other")
    return "page", regs


def state(dll):
    """(상태 문자열 집합, 상세). 모두 알려진 상태이면 ('ok', k) 로, k = 0(수정 없음) ~ 7(모두 적용) 또는 'partial'(알려진 중간 상태)."""
    verify_layout(dll)
    sk, regs = pagestate(dll)
    if sk is None:
        return None, "파일 크기 %d 가 원본(%d)도 원본+%d 도 아닙니다" % (os.path.getsize(dll), ORIGINAL_SIZE, PAGE)
    hs = hdrstate(dll)
    if "other" in hs:
        return None, "구역 헤더 값이 원래도 패치된 값도 아닙니다: %s" % hs
    g = pe_geometry(dll)
    if (g["nsec"] == 8) != (hs[2] == "new"):
        return None, "구역 수와 NumberOfSections 가 맞지 않습니다"
    # 헤더는 순서대로만: 구역 헤더 -> SizeOfImage -> NumberOfSections
    kh = 0
    for x in hs:
        if x == "new":
            kh += 1
        else:
            break
    if any(x == "new" for x in hs[kh:]):
        return None, "구역 헤더 단계가 순서대로가 아닙니다: %s" % hs
    if kh and sk != "page":
        return None, "구역 헤더가 바뀌었는데 새 페이지가 없습니다"
    hk = [hookstate(dll, h) for h in HOOKS]
    if "other" in hk:
        return None, "후크 자리가 원래도 패치된 값도 아닙니다: %s" % hk
    if sk == "orig":
        if kh or any(x != "orig" for x in hk):
            return None, "구역이 없는데 헤더/후크가 바뀌어 있습니다"
        return "ok", 0
    if regs and "other" in regs:
        return None, "새 구역 안의 코드 자리가 0xCC 도, 우리 코드도 아닙니다: %s" % regs
    code_final = bool(regs) and all(r in ("final", "old") for r in regs)
    code_old = "old" in (regs or [])
    code_clean = bool(regs) and all(r == "cc" for r in regs)
    if any(x != "orig" for x in hk) and not code_final and not (any(x == "test" for x in hk) and regs):
        return None, "후크는 연결돼 있는데 새 구역에 우리 코드가 없습니다 (그대로 두면 게임이 멈춥니다)"
    if kh == 3 and code_final and hk == ["final", "final"]:
        return "ok", "old" if code_old else 7
    if kh == 0 and code_clean and hk == ["orig", "orig"]:
        return "ok", 1                      # 페이지만 붙은 상태
    if kh == 3 and code_clean and hk == ["orig", "orig"]:
        return "ok", 4                      # 구역 활성화, 코드 없음
    if kh == 3 and code_final and hk == ["orig", "orig"]:
        return "ok", 5
    if kh == 3 and code_final and hk[0] == "final" and hk[1] == "orig":
        return "ok", 6
    return "ok", "partial"


def need_bak(dll, k, create=True):
    bak = dll + ".bak"
    if os.path.exists(bak):
        if os.path.getsize(bak) != ORIGINAL_SIZE or sha256(bak) != ORIGINAL_SHA256:
            sys.exit("중단: %s 가 원본이 아닙니다 (크기/해시 불일치). 이 파일을 확인하거나 이름을 바꿔 두고 다시 시도하세요." % bak)
        return
    if k != 0:
        print("안내: %s 가 없습니다. 이미 일부 적용된 상태라 백업은 만들지 않고, 되돌릴 때는 단계 표로 원상 복구합니다." % os.path.basename(bak))
        return
    if not create:
        return
    if os.path.getsize(dll) != ORIGINAL_SIZE or sha256(dll) != ORIGINAL_SHA256:
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
    if k[0] is None:
        print("상태: 알 수 없음 -", k[1])
    else:
        print("상태:", ("%d/7 단계" % k[1]) if isinstance(k[1], int) else "이전 버전 또는 개발 중 시험 단계(적용하면 마지막 단계로 옮겨짐)")


def cmd_check(dll):
    need_dll(dll)
    k = state(dll)
    if k[0] is None:
        sys.exit("스테이션 휠 특기 강조: GameAssembly.dll 의 패치 위치가 알려진 어떤 상태와도 맞지 않습니다. 건드리지 않았습니다.\n"
                 "(%s)\n(원본으로 되돌리려면 GameAssembly.dll.bak 을 GameAssembly.dll 로 덮어쓰거나 스팀에서 '게임 파일 무결성 검사'를 하세요.)" % k[1])
    check_hook_context(dll)
    if k[1] == 0 and os.path.getsize(dll) != ORIGINAL_SIZE:
        sys.exit("중단: 파일 크기가 원본과 다릅니다.")
    need_bak(dll, k[1] if isinstance(k[1], int) else 7, create=False)
    if game_running():
        sys.exit("게임이 실행 중입니다. 게임을 완전히 끄고 다시 시도하세요.")
    print("스테이션 휠 특기 강조: 적용 가능 (현재 %s)" % (("%d/7 단계" % k[1]) if isinstance(k[1], int) else "이전 버전/시험 단계"))


def cmd_apply(dll):
    need_dll(dll)
    k = state(dll)
    if k[0] is None:
        sys.exit("스테이션 휠 특기 강조: 알 수 없는 상태입니다 (%s). 건드리지 않았습니다." % k[1])
    if k[1] == 7:
        print("스테이션 휠 특기 강조: 이미 적용되어 있습니다.")
        return
    check_hook_context(dll)
    if game_running():
        sys.exit("게임이 실행 중입니다. 게임을 완전히 끄고 다시 시도하세요.")
    need_bak(dll, k[1] if isinstance(k[1], int) else 7)
    sk, _regs = pagestate(dll)
    if sk == "orig":                                                    # 1) 새 페이지(0xCC) 붙이기
        with open(dll, "ab") as f:
            f.write(b"\xcc" * PAGE)
            f.flush()
            os.fsync(f.fileno())
    for name, off, orig, new in HEADER:                                 # 2~4) 구역 헤더, SizeOfImage, 구역 수 (순서대로)
        cur = read_at(dll, off, len(orig) // 2).hex()
        if cur == new:
            continue
        _write(dll, off, bytes.fromhex(orig), bytes.fromhex(new))
    for name, po, hx in CODE:                                           # 5) 새 구역에 코드 쓰기 (점프는 아직 없음)
        b = bytes.fromhex(hx)
        cur = read_at(dll, ORIGINAL_SIZE + po, len(b))
        if cur != b:
            expect = bytes.fromhex(ALT[name]) if name in ALT and cur == bytes.fromhex(ALT[name]) else b"\xcc" * len(b)   # 이전 버전 코드(부정 특성 표)는 새 것으로 바꿔 씀
            _write(dll, ORIGINAL_SIZE + po, expect, b)
    for h in HOOKS:                                                     # 6~7) 후크 연결 (코드가 있어야만)
        _n, off, orig, final, tests, _b, _a = h
        st = hookstate(dll, h)
        if st == "final":
            continue
        cur = bytes.fromhex(orig if st == "orig" else tests[0])
        _write(dll, off, cur, bytes.fromhex(final))
    k2 = state(dll)
    if k2 != ("ok", 7):
        sys.exit("중단: 쓴 뒤 검증에 실패했습니다 (%s). 'revert' 로 되돌리거나 GameAssembly.dll.bak 으로 복원하세요." % (k2,))
    print("스테이션 휠 특기 강조 적용: 7/7 단계 (검증 완료)")


def cmd_revert(dll):
    if not os.path.isfile(dll):
        return
    try:
        k = state(dll)
    except SystemExit:
        return          # 이 패치가 만들어진 게임 빌드가 아니면(업데이트 등) 건드리지 않고 조용히 끝낸다
    if k[0] is None or k[1] == 0:
        return          # 알 수 없는 파일이거나 건드리지 않은 파일이면 조용히 끝낸다
    if game_running():
        sys.exit("게임이 실행 중입니다. 게임을 완전히 끄고 다시 시도하세요 (스테이션 휠 특기 강조를 되돌리지 못했습니다).")
    for h in HOOKS:                                                     # 후크 먼저 (코드가 있는 동안에)
        _n, off, orig, final, tests, _b, _a = h
        st = hookstate(dll, h)
        if st != "orig":
            cur = bytes.fromhex(final if st == "final" else tests[0])
            _write(dll, off, cur, bytes.fromhex(orig))
    sk, _ = pagestate(dll)
    shared = False
    if sk == "page":                                                    # 코드 조각을 0xCC 로 (개발 중 시험 코드가 있어도 페이지 전체를 지움)
        cur = read_at(dll, ORIGINAL_SIZE, PAGE)
        keep = bytearray(b"\xcc" * PAGE)
        if cur[SHELTER_OFF:SHELTER_OFF + SHELTER_LEN] != b"\xcc" * SHELTER_LEN:   # 다른 패치(patch_shelter.py/patch_randstart.py)의 코드가 있으면 그 자리는 남기고 구역도 남긴다
            shared = True
            keep[SHELTER_OFF:SHELTER_OFF + SHELTER_LEN] = cur[SHELTER_OFF:SHELTER_OFF + SHELTER_LEN]
        if cur != bytes(keep):
            _write(dll, ORIGINAL_SIZE, cur, bytes(keep))
        if not shared:
            for name, off, orig, new in reversed(HEADER):               # 구역 수 -> SizeOfImage -> 구역 헤더
                if read_at(dll, off, len(orig) // 2).hex() == new:
                    _write(dll, off, bytes.fromhex(new), bytes.fromhex(orig))
            with open(dll, "r+b") as f:                                 # 페이지 떼어내기
                if os.fstat(f.fileno()).st_size == ORIGINAL_SIZE + PAGE and read_at(dll, ORIGINAL_SIZE, PAGE) == b"\xcc" * PAGE:
                    f.truncate(ORIGINAL_SIZE)
                    f.flush()
                    os.fsync(f.fileno())
    k2 = state(dll)
    if k2 != ("ok", 4 if shared else 0):
        sys.exit("중단: 되돌린 뒤 검증에 실패했습니다 (%s). GameAssembly.dll.bak 으로 복원하세요." % (k2,))
    print("스테이션 휠 특기 강조를 되돌렸습니다 (" + ("새 구역은 다른 패치가 쓰고 있어 남겨 뒀습니다" if shared else "원래 크기로 복구") + ")." + ("" if sha256(dll) == ORIGINAL_SHA256 else " (다른 수정이 남아 있으면 파일 전체 해시는 원본과 다를 수 있습니다.)"))


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("check", "apply", "revert", "status"):
        sys.exit(__doc__)
    {"check": cmd_check, "apply": cmd_apply, "revert": cmd_revert, "status": cmd_status}[sys.argv[1]](sys.argv[2])
