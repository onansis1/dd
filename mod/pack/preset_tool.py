"""Into the Dead: Our Darkest Days - 사용자 지정 시나리오(난이도) 프리셋 도구.

게임의 '사용자 지정 시나리오' 화면에는 쉬움/보통/어려움 프리셋이 있고, 그 값은 data_user_settings 번들에 데이터로 들어 있다.
이 도구는
  1) 세이브 파일(gamesave_*.sav)에서 내가 설정한 시나리오 값을 읽어 이름을 붙여 보관하고,
  2) 보관한 프리셋을 게임의 프리셋 칸(쉬움/보통/어려움) 중 하나에 써 넣는다.
그러면 게임 화면에서 그 칸을 고르는 것만으로 내 설정이 한 번에 불러와진다. (칸의 표시 이름은 그대로 쉬움/보통/어려움이다.)

사용: python preset_tool.py <명령> ...
  menu <AssetBundles 폴더>            대화형 메뉴
  extract <세이브.sav>                세이브의 시나리오 값을 JSON 으로 출력
  apply <AssetBundles 폴더> <easy|normal|hard>=<프리셋 이름> ...
  restore <AssetBundles 폴더>         프리셋 칸을 원래대로
원본은 <AssetBundles>/_mods_backup/data_user_settings.orig 에 한 번 백업하고, 항상 거기서 다시 계산한다 (여러 번 실행해도 쌓이지 않음).
게임을 끈 상태에서 실행할 것.
"""
import hashlib, json, os, re, shutil, struct, sys, time

import UnityPy.helpers.TypeTreeNode as T
if not getattr(T.TypeTreeNode, "_itd_patched", False):
    _orig_pb = T.TypeTreeNode.parse_blob.__func__
    def _pb(cls, reader, version):
        reader.Position = reader.Position + 28
        return _orig_pb(cls, reader, version)
    T.TypeTreeNode.parse_blob = classmethod(_pb)
    T.TypeTreeNode._itd_patched = True
# Windows + Python 3.14 에서 UnityPy 의 C 가속 모듈이 접근 위반으로 죽는 문제 대응 (다른 스크립트와 동일)
try:
    import UnityPy.helpers.TypeTreeHelper as _TTH
    _TTH.read_typetree_boost = None
except Exception:
    pass
import UnityPy
from UnityPy.files import ObjectReader as _ORcls
from UnityPy.streams import EndianBinaryReader

ENTRY = {}
if not getattr(_ORcls, "_itd_patched", False):
    _orig_fr = _ORcls.from_reader.__func__
    def _fr(cls, assets_file, reader):
        before = reader.Position
        obj = _orig_fr(cls, assets_file, reader)
        ENTRY[obj.path_id] = (before + 3) // 4 * 4
        return obj
    _ORcls.from_reader = classmethod(_fr)
    _ORcls._itd_patched = True

PREFIX = "drs.difficulty."
SLOTS = {"easy": "EasyDifficultyPreset", "normal": "NormalDifficultyPreset", "hard": "HardDifficultyPreset"}
SLOT_KO = {"easy": "쉬움", "normal": "보통", "hard": "어려움"}
BUNDLE = "data_user_settings"
FROZEN = getattr(sys, "frozen", False)


def base_dir():
    """프리셋(JSON)을 보관하는 폴더의 위치 = 실행 파일(exe 또는 스크립트) 옆 presets 폴더."""
    if os.environ.get("ITD_PRESET_DIR"):
        return os.environ["ITD_PRESET_DIR"]
    root = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(root, "presets")


# ---------------------------------------------------------------- MessagePack (필요한 부분만)
class Ext:
    def __init__(self, code, data):
        self.code, self.data = code, data


def mp_unpack(b, i=0):
    c = b[i]
    i += 1
    if c <= 0x7f:
        return c, i
    if c >= 0xe0:
        return c - 256, i
    if 0x80 <= c <= 0x8f:
        return _mp_map(b, i, c & 0x0f)
    if 0x90 <= c <= 0x9f:
        return _mp_arr(b, i, c & 0x0f)
    if 0xa0 <= c <= 0xbf:
        n = c & 0x1f
        return b[i:i + n].decode("utf-8"), i + n
    if c == 0xc0:
        return None, i
    if c == 0xc2:
        return False, i
    if c == 0xc3:
        return True, i
    if c in (0xc4, 0xc5, 0xc6):
        w = {0xc4: 1, 0xc5: 2, 0xc6: 4}[c]
        n = int.from_bytes(b[i:i + w], "big")
        i += w
        return bytes(b[i:i + n]), i + n
    if c in (0xc7, 0xc8, 0xc9):
        w = {0xc7: 1, 0xc8: 2, 0xc9: 4}[c]
        n = int.from_bytes(b[i:i + w], "big")
        i += w
        code = b[i]
        i += 1
        return Ext(code, bytes(b[i:i + n])), i + n
    if c == 0xca:
        return struct.unpack_from(">f", b, i)[0], i + 4
    if c == 0xcb:
        return struct.unpack_from(">d", b, i)[0], i + 8
    if 0xcc <= c <= 0xcf:
        w = 1 << (c - 0xcc)
        return int.from_bytes(b[i:i + w], "big"), i + w
    if 0xd0 <= c <= 0xd3:
        w = 1 << (c - 0xd0)
        return int.from_bytes(b[i:i + w], "big", signed=True), i + w
    if c in (0xd9, 0xda, 0xdb):
        w = {0xd9: 1, 0xda: 2, 0xdb: 4}[c]
        n = int.from_bytes(b[i:i + w], "big")
        i += w
        return b[i:i + n].decode("utf-8"), i + n
    if c in (0xdc, 0xdd):
        w = 2 if c == 0xdc else 4
        return _mp_arr(b, i + w, int.from_bytes(b[i:i + w], "big"))
    if c in (0xde, 0xdf):
        w = 2 if c == 0xde else 4
        return _mp_map(b, i + w, int.from_bytes(b[i:i + w], "big"))
    raise ValueError("지원하지 않는 MessagePack 코드 0x%02x" % c)


def _mp_arr(b, i, n):
    out = []
    for _ in range(n):
        v, i = mp_unpack(b, i)
        out.append(v)
    return out, i


def _mp_map(b, i, n):
    out = {}
    for _ in range(n):
        k, i = mp_unpack(b, i)
        v, i = mp_unpack(b, i)
        out[k] = v
    return out, i


# ---------------------------------------------------------------- 세이브 파일 읽기
def _decode_payload(payload):
    import lz4.block
    arr, _ = mp_unpack(payload)
    if not (isinstance(arr, list) and arr and isinstance(arr[0], Ext) and arr[0].code == 0x62):
        raise ValueError("알 수 없는 압축 형식")
    lens, p = [], 0
    while p < len(arr[0].data):
        v, p = mp_unpack(arr[0].data, p)
        lens.append(v)
    blocks = arr[1:]
    if len(blocks) != len(lens):
        raise ValueError("압축 블록 수가 맞지 않음")
    data = b"".join(lz4.block.decompress(bytes(bl), uncompressed_size=ln) for bl, ln in zip(blocks, lens))
    obj, _ = mp_unpack(data)
    return obj[0] if isinstance(obj, list) and obj else obj


def values_from_save(path):
    """세이브 파일 안의 'drs.difficulty.*' 설정을 {짧은 키: 값} 으로 읽는다. 못 찾으면 ValueError."""
    d = open(path, "rb").read()
    if len(d) < 50:
        raise ValueError("세이브 파일이 아닙니다")
    pos = 4
    while pos + 5 < len(d):
        n = d[pos]
        if not 0 < n <= 64:
            break
        pos += 1 + n
        ln = struct.unpack_from("<i", d, pos)[0]
        pos += 4
        if ln < 0 or pos + ln > len(d):
            break
        payload = d[pos:pos + ln]
        pos += ln + 4
        try:
            obj = _decode_payload(payload)
        except Exception:
            continue
        if isinstance(obj, dict) and any(isinstance(k, str) and k.startswith(PREFIX) for k in obj):
            out = {}
            for k, v in obj.items():
                if not k.startswith(PREFIX):
                    continue
                try:
                    tid, val = v[0], v[1][0]
                except Exception:
                    continue
                if tid == 0:
                    val = bool(val)
                elif tid == 4:
                    val = int(val)
                elif tid == 8:
                    val = round(float(val), 6)
                elif tid == 11:
                    val = str(val)
                else:
                    continue
                out[k[len(PREFIX):]] = val
            return out
    raise ValueError("이 파일에서 시나리오 설정을 찾지 못했습니다")


def find_saves(extra_roots=()):
    """흔한 위치에서 시나리오 설정이 들어 있는 세이브 파일을 찾는다. 최근 수정순."""
    home = os.path.expanduser("~")
    roots = [os.path.join(home, "AppData", "LocalLow"), os.path.join(home, "Documents"),
             os.path.join(home, "AppData", "Roaming"), r"C:\Program Files (x86)\Steam\userdata", r"C:\Program Files\Steam\userdata"]
    roots += list(extra_roots)
    seen, found = set(), []
    skip = re.compile(r"analytics|settings|progression|core|mobile|session", re.I)
    for r in roots:
        if not os.path.isdir(r):
            continue
        base = r.rstrip("\\/").count(os.sep)
        for dp, dn, fn in os.walk(r):
            if dp.count(os.sep) - base > 7:
                dn[:] = []
                continue
            for f in fn:
                if not f.lower().endswith(".sav") or skip.search(f):
                    continue
                p = os.path.join(dp, f)
                if p in seen:
                    continue
                seen.add(p)
                try:
                    if os.path.getsize(p) < 2000:
                        continue
                    values_from_save(p)
                    found.append((os.path.getmtime(p), p))
                except Exception:
                    pass
    found.sort(reverse=True)
    return [p for _, p in found]


# ---------------------------------------------------------------- 프리셋 보관
def _safe_name(name):
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name).strip().strip(".")
    return name[:60]


def list_presets():
    d = base_dir()
    out = []
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.lower().endswith(".json") and not f.startswith("_"):
                out.append(f[:-5])
    return out


def load_preset(name):
    with open(os.path.join(base_dir(), name + ".json"), encoding="utf-8") as f:
        return json.load(f)["values"]


def save_preset(name, values):
    name = _safe_name(name)
    if not name:
        raise ValueError("이름이 비어 있습니다")
    os.makedirs(base_dir(), exist_ok=True)
    with open(os.path.join(base_dir(), name + ".json"), "w", encoding="utf-8") as f:
        json.dump({"name": name, "values": values}, f, ensure_ascii=False, indent=1)
    return name


def delete_preset(name):
    os.remove(os.path.join(base_dir(), name + ".json"))


def _state_path():
    return os.path.join(base_dir(), "_slots.json")


def load_slot_state():
    try:
        return json.load(open(_state_path(), encoding="utf-8"))
    except Exception:
        return {}


def _save_slot_state(st):
    os.makedirs(base_dir(), exist_ok=True)
    json.dump(st, open(_state_path(), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- 번들 패치
def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _load(data):
    ENTRY.clear()
    return UnityPy.load(data)


def _monos(env):
    scr = {o.path_id: o.read().m_ClassName for o in env.objects if o.type.name == "MonoScript"}
    by = {}
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            tt = o.read_typetree()
        except Exception:
            continue
        by[tt.get("m_Name")] = (o, tt, scr.get(tt["m_Script"]["m_PathID"]))
    return by


def _allowed_options(by):
    """설정 키 -> 허용 선택지 집합 / 범위. 모르는 키는 검증하지 않는다."""
    out = {}
    for n, (o, tt, cls) in by.items():
        key = tt.get("m_settingKey", "")
        if not key.startswith(PREFIX):
            continue
        k = key[len(PREFIX):]
        if cls and cls.startswith("Adjustable") and "m_settingOptions" in tt:
            refs = {r["rid"]: r for r in tt["references"]["RefIds"]}
            vals = set()
            for ro in tt["m_settingOptions"]:
                v = refs[ro["rid"]]["data"]["m_value"]
                vals.add(v["m_value"] if isinstance(v, dict) else v)
            out[k] = ("set", vals)
        elif cls == "FloatSettingOptionRangeProvider":
            out[k] = ("range", (tt["m_minValue"], tt["m_maxValue"]))
    return out


def validate(values, allowed):
    errs = []
    for k, v in values.items():
        a = allowed.get(k)
        if not a:
            continue
        kind, lim = a
        if kind == "set":
            ok = any((isinstance(v, str) and v == x) or (not isinstance(v, str) and not isinstance(x, str) and abs(float(v) - float(x)) < 1e-4) for x in lim)
            if not ok:
                errs.append("%s = %r (허용: %s)" % (k, v, ", ".join(sorted(str(x) for x in lim))))
        elif kind == "range" and not (lim[0] - 1e-6 <= float(v) <= lim[1] + 1e-6):
            errs.append("%s = %r (허용 범위 %s ~ %s)" % (k, v, lim[0], lim[1]))
    return errs


def _same(a, b):
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    return abs(float(a) - float(b)) < 1e-6


def _edit_slot(tt, values):
    """프리셋 칸(SettingsPresetCollection)의 값을 바꾼다. 바뀐 항목 수와 무시된 키를 돌려준다.
    주의: 여러 설정이 같은 값 객체(참조)를 공유한다. 공유 객체를 직접 고치면 다른 설정까지 바뀌므로,
    값이 다르면 '같은 종류·같은 값'의 기존 객체를 찾아 연결하고, 없으면 새 객체를 만들어 그 키만 연결한다."""
    refs_list = tt["references"]["RefIds"]
    refs = {r["rid"]: r for r in refs_list}
    keys = tt["m_presets"]["m_keys"]
    next_rid = max(refs) + 1
    changed, ignored = 0, []
    for k, v in values.items():
        full = PREFIX + k
        if full not in keys:
            ignored.append(k)
            continue
        slot_entry = tt["m_presets"]["m_values"][keys.index(full)]["m_settingData"]
        cur = refs[slot_entry["rid"]]
        cls = cur["type"]["class"]
        if cls == "FloatSettingData":
            nv = float(v)
        elif cls == "IntSettingsData":
            nv = int(v)
        elif cls == "BoolSettingsData":
            nv = 1 if v else 0
        elif cls == "StringSettingsData":
            nv = str(v)
        else:
            ignored.append(k)
            continue
        if _same(cur["data"]["m_value"], nv):
            continue
        hit = next((r for r in refs_list if r["type"]["class"] == cls and _same(r["data"]["m_value"], nv)), None)
        if hit is None:
            hit = {"rid": next_rid, "type": dict(cur["type"]), "data": {"m_value": nv}}
            next_rid += 1
            refs_list.append(hit)
            refs[hit["rid"]] = hit
        slot_entry["rid"] = hit["rid"]
        changed += 1
    return changed, ignored


def patch_bundle(data, slot_values):
    """data_user_settings 바이트에서 지정한 칸들의 값을 바꾼 새 번들 바이트를 만든다.
    문자열 길이가 달라지면 오브젝트 크기가 바뀌므로, 오브젝트 표/파일 크기를 함께 고친다 (지도 섞기와 같은 방식)."""
    env = _load(data)
    bundle = env.file
    name, sf = [(n, f) for n, f in bundle.files.items() if hasattr(f, "types")][0]
    raw = bytearray(sf.reader.bytes)
    hdr = sf.header
    if hdr.version < 22:
        raise RuntimeError("지원하지 않는 번들 버전입니다: %d" % hdr.version)
    by = _monos(env)
    allowed = _allowed_options(by)
    objs = sorted(env.objects, key=lambda x: x.byte_start)
    order = [x.path_id for x in objs]
    A = 16
    up = lambda n: (n + A - 1) // A * A
    new_bytes, report = {}, {}
    for slot, values in slot_values.items():
        nm = SLOTS[slot]
        if nm not in by:
            raise RuntimeError("프리셋 칸 %s 을 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음)" % nm)
        errs = validate(values, allowed)
        if errs:
            raise ValueError("허용되지 않는 값이 있습니다:\n  " + "\n  ".join(errs))
        o, tt, _ = by[nm]
        changed, ignored = _edit_slot(tt, values)
        nb = bytes(o.save_typetree(tt))
        new_bytes[o.path_id] = nb
        report[slot] = (changed, ignored)
    out = bytearray(raw[:objs[0].byte_start])
    delta_at = {}
    delta = 0
    for i, x in enumerate(objs):
        end = objs[i + 1].byte_start if i + 1 < len(objs) else len(raw)
        span = bytes(raw[x.byte_start:end])
        delta_at[x.path_id] = delta
        if x.path_id in new_bytes:
            if i + 1 < len(objs) and len(span) != up(x.byte_size):
                raise RuntimeError("예상과 다른 오브젝트 배치입니다.")
            nb = new_bytes[x.path_id]
            seg = nb + b"\x00" * (up(len(nb)) - len(nb))
            tail = span[up(x.byte_size):] if i + 1 == len(objs) else b""
            delta += len(seg) + len(tail) - len(span)
            out += seg + tail
        else:
            out += span
    for x in objs:
        e = ENTRY[x.path_id]
        pid, bs, sz = struct.unpack_from("<qqI", raw, e)
        if pid != x.path_id or bs != x.byte_start - hdr.data_offset or sz != x.byte_size:
            raise RuntimeError("오브젝트 표 해석이 예상과 다릅니다. 중단합니다.")
        struct.pack_into("<q", out, e + 8, bs + delta_at[x.path_id])
        if x.path_id in new_bytes:
            struct.pack_into("<I", out, e + 16, len(new_bytes[x.path_id]))
    struct.pack_into(">q", out, 24, len(out))
    r = EndianBinaryReader(bytes(out))
    r.flags = sf.flags
    bundle.files[name] = r
    return bundle.save(packer="lz4"), report


# ---------------------------------------------------------------- 설치 폴더에 적용 / 복원
def _paths(ab):
    bdir = os.path.join(ab, "_mods_backup")
    return os.path.join(ab, BUNDLE), os.path.join(bdir, BUNDLE + ".orig"), os.path.join(bdir, BUNDLE + ".state.json")


def _base_data(ab):
    """다시 계산의 기준이 되는 원본 바이트. 게임 업데이트로 파일이 바뀌었으면 현재 파일을 새 원본으로 삼는다."""
    cur_p, bak_p, st_p = _paths(ab)
    if not os.path.isfile(cur_p):
        raise FileNotFoundError(cur_p + " 이(가) 없습니다")
    cur = open(cur_p, "rb").read()
    os.makedirs(os.path.dirname(bak_p), exist_ok=True)
    st = {}
    try:
        st = json.load(open(st_p, encoding="utf-8"))
    except Exception:
        pass
    if os.path.isfile(bak_p):
        bak = open(bak_p, "rb").read()
        if _sha(cur) == _sha(bak) or _sha(cur) == st.get("out"):
            return bak, cur, "백업(원본)에서 다시 계산합니다"
        shutil.copy2(bak_p, bak_p + ".old")
        note = "게임 업데이트로 파일이 바뀐 것으로 보여 현재 파일을 새 원본으로 백업합니다"
    else:
        note = "원본을 백업했습니다"
    with open(bak_p, "wb") as f:
        f.write(cur)
    return cur, cur, note


def apply_presets(ab, mapping):
    """mapping: {'easy'|'normal'|'hard': 프리셋 이름}. 반환: 메시지 목록."""
    base, cur, note = _base_data(ab)
    cur_p, bak_p, st_p = _paths(ab)
    slot_values = {}
    for slot, pname in mapping.items():
        if slot not in SLOTS:
            raise ValueError("알 수 없는 칸: " + slot)
        slot_values[slot] = load_preset(pname)
    new, report = patch_bundle(base, slot_values)
    # 검증: 새 번들을 다시 읽어 값이 들어갔는지, 다른 프리셋/오브젝트가 그대로인지 확인
    chk = _monos(_load(new))
    for slot, values in slot_values.items():
        tt = chk[SLOTS[slot]][1]
        refs = {r["rid"]: r for r in tt["references"]["RefIds"]}
        keys = tt["m_presets"]["m_keys"]
        for k, v in values.items():
            if PREFIX + k in keys:
                got = refs[tt["m_presets"]["m_values"][keys.index(PREFIX + k)]["m_settingData"]["rid"]]["data"]["m_value"]
                ok = (got == v) if isinstance(v, str) else (abs(float(got) - float(v)) < 1e-4)
                if not ok:
                    raise RuntimeError("검증 실패: %s %r != %r" % (k, got, v))
    tmp = cur_p + ".tmp"
    with open(tmp, "wb") as f:
        f.write(new)
    try:
        os.replace(tmp, cur_p)
    except PermissionError:
        raise PermissionError("파일을 교체하지 못했습니다. 게임/스팀이 실행 중이면 끄고 다시 시도하세요.")
    json.dump({"out": _sha(new), "orig": _sha(base)}, open(st_p, "w", encoding="utf-8"))
    st = load_slot_state()
    for slot, pname in mapping.items():
        st[slot] = pname
    _save_slot_state(st)
    msgs = [note]
    for slot, (changed, ignored) in report.items():
        msgs.append("%s 칸 <- '%s': 바뀐 항목 %d개%s" % (SLOT_KO[slot], mapping[slot], changed,
                                                     (" / 무시한 키: " + ", ".join(ignored)) if ignored else ""))
    return msgs


def restore_presets(ab):
    cur_p, bak_p, st_p = _paths(ab)
    if not os.path.isfile(bak_p):
        return "되돌릴 백업이 없습니다 (프리셋을 적용한 적이 없습니다)."
    cur = open(cur_p, "rb").read()
    bak = open(bak_p, "rb").read()
    try:
        out = json.load(open(st_p, encoding="utf-8")).get("out")
    except Exception:
        out = None
    if _sha(cur) != _sha(bak) and _sha(cur) != out:
        return "현재 파일이 이 도구가 만든 것도 원본도 아닙니다 (게임이 업데이트되었을 수 있음). 건드리지 않았습니다. 스팀의 '게임 파일 무결성 검사'를 쓰세요."
    tmp = cur_p + ".tmp"
    open(tmp, "wb").write(bak)
    try:
        os.replace(tmp, cur_p)
    except PermissionError:
        return "파일을 교체하지 못했습니다. 게임/스팀을 끄고 다시 시도하세요."
    _save_slot_state({})
    try:
        os.remove(st_p)
    except OSError:
        pass
    return "프리셋 칸을 원래대로 되돌렸습니다."


def current_slot_values(ab):
    """(현재 설치된 번들의) 세 칸의 값. 보여주기용."""
    cur_p = os.path.join(ab, BUNDLE)
    by = _monos(_load(open(cur_p, "rb").read()))
    out = {}
    for slot, nm in SLOTS.items():
        tt = by[nm][1]
        refs = {r["rid"]: r for r in tt["references"]["RefIds"]}
        out[slot] = {k[len(PREFIX):]: refs[v["m_settingData"]["rid"]]["data"]["m_value"]
                     for k, v in zip(tt["m_presets"]["m_keys"], tt["m_presets"]["m_values"])}
    return out


# ---------------------------------------------------------------- 대화형 메뉴
def _ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def _pick(items, title):
    for i, it in enumerate(items, 1):
        print("  %d) %s" % (i, it))
    s = _ask(title)
    if s.isdigit() and 1 <= int(s) <= len(items):
        return items[int(s) - 1]
    return None


def _show(values):
    for k, v in values.items():
        print("    %-36s %s" % (k, v))


def menu(ab, game_running=lambda: False):
    while True:
        st = load_slot_state()
        print("\n=== 사용자 지정 시나리오 프리셋 ===")
        print("현재 게임 프리셋 칸에 넣어 둔 것:  " + ", ".join("%s=%s" % (SLOT_KO[s], st.get(s) or "원래 값") for s in SLOTS))
        print("1) 세이브에서 내 설정 가져와 저장하기")
        print("2) 저장한 프리셋 보기 / 삭제")
        print("3) 내 프리셋을 게임의 프리셋 칸(쉬움/보통/어려움)에 넣기")
        print("4) 프리셋 칸을 원래대로 되돌리기")
        print("0) 돌아가기")
        c = _ask("\n번호: ")
        try:
            if c == "1":
                print("\n세이브 파일을 찾는 중...")
                saves = find_saves()
                path = None
                if saves:
                    print("찾은 세이브 (최근 수정순):")
                    for i, p in enumerate(saves[:12], 1):
                        print("  %d) %s   [%s]" % (i, p, time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(p)))))
                    s = _ask("번호 (직접 입력하려면 엔터): ")
                    if s.isdigit() and 1 <= int(s) <= min(12, len(saves)):
                        path = saves[int(s) - 1]
                if not path:
                    path = _ask("세이브 파일(.sav) 경로를 붙여넣으세요 (취소: 엔터): ").strip('"')
                if not path:
                    continue
                vals = values_from_save(path)
                print("읽은 설정 %d개:" % len(vals))
                _show(vals)
                name = _ask("\n이 프리셋의 이름 (취소: 엔터): ")
                if name:
                    print("저장했습니다:", os.path.join(base_dir(), save_preset(name, vals) + ".json"))
            elif c == "2":
                names = list_presets()
                if not names:
                    print("저장한 프리셋이 없습니다. 1번으로 먼저 만드세요.")
                    continue
                n = _pick(names, "번호 (돌아가기: 엔터): ")
                if n:
                    _show(load_preset(n))
                    if _ask("이 프리셋을 삭제할까요? (y/n): ").lower() == "y":
                        delete_preset(n)
                        print("삭제했습니다.")
            elif c == "3":
                names = list_presets()
                if not names:
                    print("저장한 프리셋이 없습니다. 1번으로 먼저 만드세요.")
                    continue
                if game_running():
                    print("게임이 실행 중입니다. 게임과 스팀을 끄고 다시 하세요.")
                    continue
                print("넣을 프리셋을 고르세요:")
                n = _pick(names, "번호: ")
                if not n:
                    continue
                print("\n어느 칸에 넣을까요? (그 칸의 기존 값은 사라지고, 게임 화면의 이름은 그대로 쉬움/보통/어려움입니다)")
                slot = _pick(["쉬움 칸", "보통 칸", "어려움 칸"], "번호: ")
                if not slot:
                    continue
                slot = {"쉬움 칸": "easy", "보통 칸": "normal", "어려움 칸": "hard"}[slot]
                if _ask("'%s' -> %s 칸에 적용할까요? (y/n): " % (n, SLOT_KO[slot])).lower() != "y":
                    continue
                for m in apply_presets(ab, {slot: n}):
                    print(" ", m)
                print("\n완료. 게임을 켜고 새 게임의 '사용자 지정' 설정 화면에서 %s 프리셋을 고르면 값이 한 번에 들어갑니다." % SLOT_KO[slot])
            elif c == "4":
                if game_running():
                    print("게임이 실행 중입니다. 게임과 스팀을 끄고 다시 하세요.")
                    continue
                if _ask("프리셋 칸을 모두 원래대로 되돌릴까요? (y/n): ").lower() == "y":
                    print(restore_presets(ab))
            elif c in ("0", ""):
                return
        except Exception as e:
            print("\n문제가 생겼습니다:", e)


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    cmd = argv[1]
    if cmd == "extract":
        print(json.dumps(values_from_save(argv[2]), ensure_ascii=False, indent=1))
    elif cmd == "apply":
        ab = argv[2]
        mapping = dict(a.split("=", 1) for a in argv[3:])
        for m in apply_presets(ab, mapping):
            print(m)
    elif cmd == "restore":
        print(restore_presets(argv[2]))
    elif cmd == "menu":
        menu(argv[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
