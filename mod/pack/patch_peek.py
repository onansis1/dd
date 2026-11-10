"""Into the Dead: Our Darkest Days - 서 있는 상태에서도 문 엿보기 (GameAssembly.dll 패치, 이 게임 빌드 전용).
사용: python patch_peek.py <check|apply|revert|status> <GameAssembly.dll 경로>
 - 게임의 실행 파일(GameAssembly.dll)을 바꾸는 유일한 도구다. 7단계(PE 헤더 1 + 코드 동굴 2 + 후크 2 + 실제 코드 2)로 나뉘어 있고, 항상 순서대로 쓰고 거꾸로 되돌린다.
 - 이 게임 빌드(SHA-256 3F45B1F9...)에서만 적용한다. 다르면 아무것도 쓰지 않고 중단한다.
 - 쓰기 전에 GameAssembly.dll.bak 이 원본과 같은지 확인하고(없으면 원본일 때만 만든다), 단계마다 대상 바이트가 예상과 같은지 확인하고, 쓴 뒤 읽어서 검증한다.
 - 게임이 실행 중이면 중단한다. check 는 아무것도 쓰지 않고 적용 가능한지만 본다.
 - revert 는 적용된 단계를 거꾸로 되돌려 원본 해시와 같아지는지 확인한다. 적용된 것이 없으면 조용히 끝난다.
(개발 중 도구 itd_peek_patch.py 와 같은 단계 표를 쓴다. 단계 표를 바꾸면 안 된다.)
"""
import hashlib, json, os, shutil, struct, subprocess, sys

ORIGINAL_SHA256 = "3F45B1F9FA8B5F28AD4A0ECAAA87DB1A1D711BC559DBB1A3672855D82F9061C8"
ORIGINAL_SIZE = 103912960
GAME_EXE = "IntoTheDeadOurDarkestDays.exe"
STEPS = json.loads(r'''[{"name": "0-pe-virtualsize", "desc": ".text VirtualSize 0x775C20 -> 0x775E00 (cave padding becomes part of the mapped image)", "file_off": 560, "rva": null, "orig": "205c7700", "new": "005e7700"}, {"name": "1a-cave1-noop", "desc": "cave #1 (no-op): displaced instructions + jmp back", "file_off": 7823392, "rva": 7826464, "orig": "000000000000000000000000", "new": "488b55504d85ede98ff73800"}, {"name": "1b-cave2-noop", "desc": "cave #2 (no-op): displaced instruction + jmp back", "file_off": 7823536, "rva": 7826608, "orig": "00000000000000000000", "new": "4c8b642460e9a8ff3800"}, {"name": "1c-hook1", "desc": "StandingState.SetupHierarchyInternal @0xB063B4: jmp cave #1 (+2 nops)", "file_off": 11556276, "rva": 11559860, "orig": "488b55504d85ed", "new": "e96708c7ff9090"}, {"name": "1d-hook2", "desc": "StandingState.SetupHierarchyInternal @0xB06C5D: jmp cave #2", "file_off": 11558493, "rva": 11562077, "orig": "4c8b642460", "new": "e94e00c7ff"}, {"name": "2a-cave1-real", "desc": "cave #1: look up DoorPeekingParentState and AddChildState it", "file_off": 7823392, "rva": 7826464, "orig": "488b55504d85ede98ff73800000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000", "new": "4883ec4048c745f000000000488d0d95f33105e8b80df3ff488b0d89f3310531d2e81a10980248894424304885ff7447488b1521c6310541b8010000004889f9e85b89f3ff4c8b104c8b48084c8d45f0488b5424304889f941ffd284c074184c8b4df0b908000000488b15915534054d89f8e849b488ff4883c440488b55504d85ede914f73800"}, {"name": "2b-cave2-real", "desc": "cave #2: add the 3 transitions L->D, D->L, D->I", "file_off": 7823536, "rva": 7826608, "orig": "4c8b642460e9a8ff38000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000", "new": "488b75f04885f60f8421010000488b5d40488b7dd8488d0dacb53105e81f0df3ff488d0d40e12b05e8130df3ff488d0d3ce22b05e8070df3ff488b0d88b5310583b9e4000000007505e8b213f3ff488b0d73b53105488b81a00000004c8b20488b0d6ab82c05e88512f3ff4989c54889c14c89e24c8b05ede02b054531c9e8cd9e3700b909000000488b15e15434054d89f84989d948897424204c896c2428e83cf588ff488b0d25b82c05e84012f3ff4989c54889c14c89e24c8b05b0e12b054531c9e8889e3700b909000000488b159c5434054d89f84989f148895c24204c896c2428e8f7f488ff488b0de0b72c05e8fb11f3ff4989c54889c14889fa4c8b05fbbe31054531c9e8439e3700b909000000488b15575434054d89f84989f148897c24204c896c2428e8b2f488ff4c8b642460e97afe3800"}]''')


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
    text = next((s for s in secs if s["name"] == ".text"), None)
    if text is None:
        sys.exit("중단: .text 섹션을 찾지 못했습니다 (다른 빌드이거나 파일이 다릅니다).")
    for st in STEPS:
        n = len(st["orig"]) // 2
        if st.get("rva") is None:
            want = text["entry"] + 8
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


# 맵 정보 잠금장치 표시 패치(patch_lootlock.py)가 건드리는 자리의 '원래' 바이트 (그쪽이 적용돼 있어도 원본 판정이 되게)
LOOT_PRISTINE = [(600, '6ef9e403'), (73161584, '000000000000000000000000000000000000000000000000000000000000000000000000000000000000'), (12586706, '0f10b7b8000000'), (14815280, '74ce'), (73161664, '00' * 62), (12625550, '4c8b4c2450')]


def pristine_sha(path):
    with open(path, "rb") as f:
        data = bytearray(f.read())
    for off, hx in LOOT_PRISTINE:
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
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + GAME_EXE], capture_output=True, text=True).stdout
        return GAME_EXE.lower() in out.lower()
    except Exception:
        return False


def need_dll(dll):
    if not os.path.isfile(dll):
        sys.exit("GameAssembly.dll 을 찾을 수 없습니다: " + dll)


def check_original(dll, k):
    """k==0(수정 없음)이면 이 게임 빌드의 원본이어야 한다."""
    if k == 0 and (os.path.getsize(dll) != ORIGINAL_SIZE or pristine_sha(dll) != ORIGINAL_SHA256):
        sys.exit("서서 문 엿보기를 적용하지 못했습니다: 이 게임 버전의 GameAssembly.dll 이 아닙니다 (게임이 업데이트되었거나 다른 도구로 바뀐 파일).\n"
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
        sys.exit("서서 문 엿보기: GameAssembly.dll 의 패치 위치가 알려진 어떤 단계와도 맞지 않습니다. 건드리지 않았습니다.\n"
                 "(원본으로 되돌리려면 GameAssembly.dll.bak 을 GameAssembly.dll 로 덮어쓰거나 스팀에서 '게임 파일 무결성 검사'를 하세요.)")
    return k


def cmd_check(dll):
    need_dll(dll)
    k = state(dll)
    check_original(dll, k)
    if game_running():
        sys.exit("게임이 실행 중입니다. 게임을 완전히 끄고 다시 시도하세요.")
    print("서서 문 엿보기: 적용 가능 (현재 %d/%d 단계)" % (k, len(STEPS)))


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
        print("서서 문 엿보기: 이미 적용되어 있습니다.")
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
    print("서서 문 엿보기 적용: %d/%d 단계 (검증 완료)" % (len(STEPS), len(STEPS)))


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
        sys.exit("게임이 실행 중입니다. 게임을 완전히 끄고 다시 시도하세요 (서서 문 엿보기를 되돌리지 못했습니다).")
    for i in range(k - 1, -1, -1):
        st = STEPS[i]
        _write(dll, st["file_off"], bytes.fromhex(st["new"]), bytes.fromhex(st["orig"]))
        if detect_k(dll) != i:
            sys.exit("중단: %s 를 되돌린 뒤 검증에 실패했습니다. GameAssembly.dll.bak 으로 복원하세요." % st["name"])
    final = pristine_sha(dll)
    print("서서 문 엿보기를 되돌렸습니다." + ("" if final == ORIGINAL_SHA256 else " (주의: 해시가 원본과 다릅니다. GameAssembly.dll.bak 으로 복원하세요.)"))


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
