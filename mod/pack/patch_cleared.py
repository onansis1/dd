"""Into the Dead: Our Darkest Days - 소탕한 거점(쉘터)이 다시 채워지지 않게 한다 (GameAssembly.dll 패치, 이 게임 빌드 전용).
사용: python patch_cleared.py <check|apply|revert|status> <GameAssembly.dll 경로>
 - NpcSpawnPopulator.TryPopulateLocation 에서 '레이아웃 목록이 바뀌어 다시 채움'으로 가는 분기를, (그 장소의 소탕 상태 Cleared 가 참) 이고 (장소 모델이 ShelterLocationModel) 일 때만 건너뛴다. 소탕하지 않은 곳, 상인/스토리/일반 장소는 원래대로다.
   게임 안에서 확인됨: 소탕한 거점은 날짜가 지나도 다시 언데드가 차지 않고 다른 맵의 해골(위협)은 평소대로 오른다. 소탕한 거점에서는 이후 생기는 스토리/플랜 NPC 레이아웃도 막힐 수 있다(되돌리면 밀린 변경이 한꺼번에 반영됨).
 - 게임의 실행 파일(GameAssembly.dll)을 바꾸는 도구다(서서 문 엿보기와 같은 파일, 서로 독립). 4단계(PE 헤더 1 + 코드 동굴 1 + 후크 1 + 실제 코드 1)로 나뉘어 있고, 항상 순서대로 쓰고 거꾸로 되돌린다.
 - 이 게임 빌드(SHA-256 3F45B1F9...)에서만 적용한다. 다르면 아무것도 쓰지 않고 중단한다.
 - 쓰기 전에 GameAssembly.dll.bak 이 원본과 같은지 확인하고(없으면 원본일 때만 만든다), 단계마다 대상 바이트가 예상과 같은지 확인하고, 쓴 뒤 읽어서 검증한다.
 - 게임이 실행 중이면 중단한다. check 는 아무것도 쓰지 않고 적용 가능한지만 본다.
 - revert 는 적용된 단계를 거꾸로 되돌려 원본 해시와 같아지는지 확인한다. 적용된 것이 없으면 조용히 끝난다.
(개발 중 도구 itd_cleared_patch.py 와 같은 단계 표를 쓴다. 단계 표를 바꾸면 안 된다.)
"""
import hashlib, json, os, shutil, struct, subprocess, sys

ORIGINAL_SHA256 = "3F45B1F9FA8B5F28AD4A0ECAAA87DB1A1D711BC559DBB1A3672855D82F9061C8"
ORIGINAL_SIZE = 103912960
GAME_EXE = "IntoTheDeadOurDarkestDays.exe"
STEPS = json.loads(r'''[{"name": "0-pe-il2cpp-virtualsize", "desc": "il2cpp section VirtualSize 0x3E4F96E -> 0x3E4FA00 (its zero tail becomes part of the mapped image; SHARED with itd_lootlock_patch.py: same value)", "file_off": 600, "rva": null, "orig": "6ef9e403", "new": "00fae403", "hdr": "il2cpp"}, {"name": "1a-cave-noop", "desc": "cave (no-op) @0x45C69C0: displaced mov r9,[rsp+0x50] + jmp 0xC0B493", "file_off": 73161664, "rva": 73165248, "orig": "00000000000000000000", "new": "4c8b4c2450e9c94a64fc"}, {"name": "1b-hook", "desc": "TryPopulateLocation @0xC0B48E: mov r9,[rsp+0x50] -> jmp cave", "file_off": 12625550, "rva": 12629134, "orig": "4c8b4c2450", "new": "e92db59b03"}, {"name": "2a-cave-real", "desc": "cave: skip the layout-change repopulation when (Cleared && shelter)", "file_off": 73161664, "rva": 73165248, "orig": "4c8b4c2450e9c94a64fc00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000", "new": "4584e4742f498b47484885c07426807820007420488b8424a8010000488b4010488b08488b153edb51014839d17505e9f74f64fc4c8b4c2450e9954a64fc"}]''')

# 다른 DLL 패치(서서 문 엿보기 patch_peek.py 등)가 건드리는 자리의 '원래' 바이트. 이 파일이 이 게임 빌드의 원본인지 해시로 볼 때, 그쪽 패치는 없는 것으로 쳐서 계산한다.
PEEK_PRISTINE = [(600, '6ef9e403'), (73161584, '00' * 42), (12586706, '0f10b7b8000000'), (14815280, '74ce'), (560, '205c7700'), (7823392, '00' * 135), (7823536, '00' * 312), (11556276, '488b55504d85ed'), (11558493, '4c8b642460')]


def pe_sections(path):
    with open(path, "rb") as f:
        hdr = f.read(0x1000)
    pe = struct.unpack_from("<I", hdr, 0x3C)[0]
    if hdr[pe:pe + 4] != b"PE\0\0":
        sys.exit("PE 파일이 아닙니다: " + path)
    nsec = struct.unpack_from("<H", hdr, pe + 6)[0]
    optsz = struct.unpack_from("<H", hdr, pe + 20)[0]
    tab = pe + 24 + optsz
    out = []
    for i in range(nsec):
        e = tab + 40 * i
        name = hdr[e:e + 8].rstrip(b"\0").decode("latin1")
        vsize, va, rsize, ptr = struct.unpack_from("<IIII", hdr, e + 8)
        out.append(dict(name=name, vsize=vsize, va=va, rsize=rsize, ptr=ptr, entry=e))
    return out


def verify_layout(dll):
    """모든 단계의 파일 위치를 이 파일의 PE 섹션 표로 다시 계산해서 표와 다르면 중단한다."""
    secs = pe_sections(dll)
    hdrsec = next((s for s in secs if s["name"] == "il2cpp"), None)
    if hdrsec is None:
        sys.exit("중단: il2cpp 섹션을 찾지 못했습니다 (다른 빌드이거나 파일이 다릅니다).")
    for st in STEPS:
        n = len(st["orig"]) // 2
        if st.get("rva") is None:
            want = hdrsec["entry"] + 8
        else:
            sec = next((s for s in secs if s["va"] <= st["rva"] < s["va"] + max(s["vsize"], s["rsize"])), None)
            if sec is None:
                sys.exit("중단: %s 의 위치가 어떤 섹션에도 없습니다." % st["name"])
            want = st["rva"] - sec["va"] + sec["ptr"]
            if not (sec["ptr"] <= want and want + n <= sec["ptr"] + sec["rsize"]):
                sys.exit("중단: %s 가 섹션 %s 의 실제 데이터 밖입니다." % (st["name"], sec["name"]))
        if want != st["file_off"]:
            sys.exit("중단: %s 의 위치가 PE 섹션 표와 다릅니다 (표 0x%X, 파일 0x%X)." % (st["name"], st["file_off"], want))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


# 스테이션 휠 특기 강조(patch_wheelgold.py)/거점 이동(patch_shelter.py)/랜덤 시작(patch_randstart.py) 패치가 건드리는 자리의 '원래' 상태 (그쪽이 적용돼 있어도 원본 판정이 되게): 파일 끝 4096바이트 페이지는 떼고, 헤더 3곳/후크 2곳은 원래 바이트로
WHEEL_PAGE = 4096
WHEEL_PAGE2 = 0xA00                                                  # 지도 패널 코드(.itd2 구역)
WHEEL_PRISTINE = [(10894685, "488b5818488d4c2450"), (832, "00" * 40), (368, "00505e06"), (294, "0700"), (0xD7197E, "660f7f442440"), (0xA58746, "488b1513cbff04"), (12575881, "84c00f8470020000"), (14570465, "84c0742233d2"), (14569023, "84c0742033d2"), (14730755, "488b8e08010000"), (14730519, "32d2"), (14764036, "32d2"), (0xDE4FF3, "4533c0488d542438"), (872, "00" * 40)]


def pristine_sha(path):
    """엿보기 패치 자리를 원래 바이트로 되돌려 놓고 계산한 SHA-256 (엿보기 패치가 적용돼 있어도 원본 판정이 되게)."""
    with open(path, "rb") as f:
        data = bytearray(f.read())
    if len(data) in (ORIGINAL_SIZE + WHEEL_PAGE, ORIGINAL_SIZE + WHEEL_PAGE + WHEEL_PAGE2):
        del data[ORIGINAL_SIZE:]
    for off, hx in WHEEL_PRISTINE:
        b = bytes.fromhex(hx)
        if off + len(b) <= len(data):
            data[off:off + len(b)] = b
    for off, hx in PEEK_PRISTINE:
        b = bytes.fromhex(hx)
        if off + len(b) <= len(data):
            data[off:off + len(b)] = b
    return hashlib.sha256(bytes(data)).hexdigest().upper()


def _expected(k):
    pristine = {}
    for st in STEPS:
        for i, b in enumerate(bytes.fromhex(st["orig"])):
            pristine.setdefault(st["file_off"] + i, b)
    cur = dict(pristine)
    for st in STEPS[:k]:
        for i, b in enumerate(bytes.fromhex(st["new"])):
            cur[st["file_off"] + i] = b
    return cur


def detect_k(path):
    """지금 몇 단계까지 적용돼 있는지 (단계는 순서대로만 적용된다). 어느 상태와도 안 맞으면 None."""
    offs = sorted(_expected(0))
    runs, start, prev = [], None, None
    for o in offs:
        if start is None:
            start = prev = o
        elif o == prev + 1:
            prev = o
        else:
            runs.append((start, prev)); start = prev = o
    runs.append((start, prev))
    cur = {}
    with open(path, "rb") as f:
        for a, b in runs:
            f.seek(a)
            blob = f.read(b - a + 1)
            for i, v in enumerate(blob):
                cur[a + i] = v
    for k in range(len(STEPS) + 1):
        if _expected(k) == cur:
            return k
    return None


def game_running():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + GAME_EXE], capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return GAME_EXE.lower() in out.lower()
    except Exception:
        return False


def need_dll(dll):
    if not os.path.isfile(dll):
        sys.exit("GameAssembly.dll 을 찾을 수 없습니다: " + dll)


def check_original(dll, k):
    """k==0(수정 없음)이면 이 게임 빌드의 원본이어야 한다."""
    if k == 0 and (os.path.getsize(dll) not in (ORIGINAL_SIZE, ORIGINAL_SIZE + WHEEL_PAGE, ORIGINAL_SIZE + WHEEL_PAGE + WHEEL_PAGE2) or pristine_sha(dll) != ORIGINAL_SHA256):
        sys.exit("소탕 거점 재생성 방지를 적용하지 못했습니다: 이 게임 버전의 GameAssembly.dll 이 아닙니다 (게임이 업데이트되었거나 다른 도구로 바뀐 파일).\n"
                 "이 패치는 특정 게임 빌드에서만 쓸 수 있습니다. 이 항목을 끄고 다시 적용하세요.")


def ensure_backup(dll, k):
    bak = dll + ".bak"
    if os.path.exists(bak):
        if os.path.getsize(bak) != ORIGINAL_SIZE or sha256(bak) != ORIGINAL_SHA256:
            sys.exit("중단: %s 가 원본이 아닙니다 (크기/해시 불일치). 이 파일을 확인하거나 이름을 바꿔 두고 다시 시도하세요." % bak)
    elif k == 0:
        shutil.copy2(dll, bak)
        print("백업 생성:", bak)
    else:
        print("안내: %s 가 없습니다. 이미 일부 적용된 상태라 백업은 만들지 않고, 되돌릴 때는 단계 표로 원상 복구합니다." % os.path.basename(bak))


def state(dll):
    verify_layout(dll)
    k = detect_k(dll)
    if k is None:
        sys.exit("소탕 거점 재생성 방지: GameAssembly.dll 의 패치 위치가 알려진 어떤 단계와도 맞지 않습니다. 건드리지 않았습니다.\n"
                 "(원본으로 되돌리려면 GameAssembly.dll.bak 을 GameAssembly.dll 로 덮어쓰거나 스팀에서 '게임 파일 무결성 검사'를 하세요.)")
    return k


def cmd_check(dll):
    need_dll(dll)
    k = state(dll)
    check_original(dll, k)
    if game_running():
        sys.exit("게임이 실행 중입니다. 게임을 완전히 끄고 다시 시도하세요.")
    print("소탕 거점 재생성 방지: 적용 가능 (현재 %d/%d 단계)" % (k, len(STEPS)))


def _write(dll, f_off, expect, new):
    with open(dll, "r+b") as f:
        f.seek(f_off)
        if f.read(len(expect)) != expect:
            sys.exit("중단: 쓰는 도중 원래 바이트가 달라졌습니다.")
        f.seek(f_off)
        f.write(new)
        f.flush()
        os.fsync(f.fileno())


def cmd_apply(dll):
    need_dll(dll)
    k = state(dll)
    if k == len(STEPS):
        print("소탕 거점 재생성 방지: 이미 적용되어 있습니다.")
        return
    check_original(dll, k)
    if game_running():
        sys.exit("게임이 실행 중입니다. 게임을 완전히 끄고 다시 시도하세요.")
    ensure_backup(dll, k)
    for i in range(k, len(STEPS)):
        st = STEPS[i]
        _write(dll, st["file_off"], bytes.fromhex(st["orig"]), bytes.fromhex(st["new"]))
        if detect_k(dll) != i + 1:
            sys.exit("중단: %s 를 쓴 뒤 검증에 실패했습니다. 'revert' 로 되돌리거나 GameAssembly.dll.bak 으로 복원하세요." % st["name"])
    print("소탕 거점 재생성 방지 적용: %d/%d 단계 (검증 완료)" % (len(STEPS), len(STEPS)))


def cmd_revert(dll):
    if not os.path.isfile(dll):
        return
    try:
        verify_layout(dll)
    except SystemExit:
        return          # 이 패치가 만들어진 게임 빌드가 아니면(업데이트 등) 건드리지 않고 조용히 끝낸다
    k = detect_k(dll)
    if k is None or k == 0:
        return          # 건드리지 않은 파일(또는 알 수 없는 파일)이면 조용히 끝낸다
    if game_running():
        sys.exit("게임이 실행 중입니다. 게임을 완전히 끄고 다시 시도하세요 (소탕 거점 재생성 방지를 되돌리지 못했습니다).")
    for i in range(k - 1, -1, -1):
        st = STEPS[i]
        _write(dll, st["file_off"], bytes.fromhex(st["new"]), bytes.fromhex(st["orig"]))
        if detect_k(dll) != i:
            sys.exit("중단: %s 를 되돌린 뒤 검증에 실패했습니다. GameAssembly.dll.bak 으로 복원하세요." % st["name"])
    final = pristine_sha(dll)
    print("소탕 거점 재생성 방지(제거된 기능)를 되돌렸습니다." + ("" if final == ORIGINAL_SHA256 else " (이 패치 영역은 원래대로입니다. 문 엿보기 등 다른 수정이 남아 있으면 파일 전체 해시는 원본과 다를 수 있습니다.)"))


def cmd_status(dll):
    need_dll(dll)
    verify_layout(dll)
    k = detect_k(dll)
    print("파일:", dll)
    print("크기:", os.path.getsize(dll), "(원본 %d)" % ORIGINAL_SIZE)
    print("SHA-256:", sha256(dll))
    print("상태:", "알 수 없음" if k is None else "%d/%d 단계 적용" % (k, len(STEPS)))


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("check", "apply", "revert", "status"):
        sys.exit(__doc__)
    {"check": cmd_check, "apply": cmd_apply, "revert": cmd_revert, "status": cmd_status}[sys.argv[1]](sys.argv[2])
