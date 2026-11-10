"""Into the Dead: Our Darkest Days - 맵 정보의 장소 설명 끝에 '락픽/볼트 절단기 필요 개수'를 덧붙인다 (로컬라이제이션 번들 loc.korean / loc.english 수정).
사용: python patch_lootnote.py <작업 폴더>   (작업 폴더 안의 loc.korean, loc.english 를 제자리에서 고친다. 원본은 호출하는 쪽이 백업해 둔다)
 - 개수는 lootnotes.json (게임 데이터에서 장소별로 뽑은 값)에서 온다: 서랍/로커 등 '아이템 잠금' 루트 포인트(항상 활성) + 열쇠가 필요한 문(DoorLocked 계열).
   지식으로 여는 문, 시작부터 잠기지 않는 문은 세지 않는다. 금고/철창 등 도구 종류를 알 수 없는 잠금은 '기타 잠금'으로 따로 적는다.
 - 문자열 길이가 바뀌므로 번들 안의 위치도 함께 고친다(UnityPy 의 저장 기능은 이 게임 파일을 망가뜨려서 쓰지 않는다). 쓴 뒤 다시 읽어서 의도한 키만 바뀌었는지 확인하고, 아니면 아무것도 쓰지 않고 중단한다.
"""
import json, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "_MEIPASS", None):
    HERE = sys._MEIPASS

# ---- UnityFS 컨테이너 읽기/쓰기 (format 8, 복사본에서 검증된 최소 구현) ----
def _lz4():
    import lz4.block
    return lz4.block

def bparse(b):
    L = _lz4()
    i = b.index(b'\0'); sig = b[:i]; i += 1
    assert sig == b'UnityFS', sig
    fmt, = struct.unpack('>I', b[i:i+4]); i += 4
    uv = b[i:b.index(b'\0', i)]; i += len(uv) + 1
    rv = b[i:b.index(b'\0', i)]; i += len(rv) + 1
    size, cbi, ubi, flags = struct.unpack('>qIII', b[i:i+20]); i += 20
    assert fmt == 8 and size == len(b), (fmt, size, len(b))
    if flags & 0x80:
        raise ValueError("블록 정보가 파일 끝에 있는 번들은 지원하지 않습니다")
    if flags & 0x200: i = (i + 15) // 16 * 16
    comp = flags & 0x3f
    raw = b[i:i+cbi]; i += cbi
    if flags & 0x200: i = (i + 15) // 16 * 16
    info = raw if comp == 0 else L.decompress(raw, uncompressed_size=ubi)
    assert comp in (0, 2, 3), comp
    p = 16
    nb, = struct.unpack('>i', info[p:p+4]); p += 4
    blocks = []
    for _ in range(nb):
        u, c, f = struct.unpack('>IIH', info[p:p+10]); p += 10; blocks.append((u, c, f))
    nn, = struct.unpack('>i', info[p:p+4]); p += 4
    nodes = []
    for _ in range(nn):
        off, sz, nf = struct.unpack('>qqI', info[p:p+20]); p += 20
        e = info.index(b'\0', p); name = info[p:e].decode(); p = e + 1
        nodes.append([off, sz, nf, name])
    data = bytearray()
    for u, c, f in blocks:
        raw = b[i:i+c]; i += c
        t = f & 0x3f
        data += raw if t == 0 else L.decompress(raw, uncompressed_size=u)
        assert t in (0, 2, 3), t
    assert i == len(b), (i, len(b))
    return dict(unity=uv, rev=rv, flags=flags, hash=info[:16], nodes=nodes, data=bytes(data))

def bbuild(d, data, nodes):
    L = _lz4()
    BLK = 131072
    blks = []; body = b''
    for o in range(0, len(data), BLK):
        chunk = data[o:o+BLK]
        comp = L.compress(chunk, mode='high_compression', compression=12, store_size=False)
        if len(comp) < len(chunk): blks.append((len(chunk), len(comp), 3)); body += comp; continue
        blks.append((len(chunk), len(chunk), 0)); body += chunk
    info = d['hash'] + struct.pack('>i', len(blks))
    for u, c, f in blks: info += struct.pack('>IIH', u, c, f)
    info += struct.pack('>i', len(nodes))
    for off, sz, nf, name in nodes: info += struct.pack('>qqI', off, sz, nf) + name.encode() + b'\0'
    cinfo = L.compress(info, mode='high_compression', compression=12, store_size=False)
    flags = (d['flags'] & ~0x3f) | 3
    hdr = b'UnityFS\0' + struct.pack('>I', 8) + d['unity'] + b'\0' + d['rev'] + b'\0'
    pos = len(hdr) + struct.calcsize('>qIII')
    pad = pad2 = 0
    if flags & 0x200:
        pad = (-pos) % 16
        pad2 = (-(pos + pad + len(cinfo))) % 16
    total = pos + pad + len(cinfo) + pad2 + len(body)
    return hdr + struct.pack('>qIII', total, len(cinfo), len(info), flags) + b'\0' * pad + cinfo + b'\0' * pad2 + body

# ---- 직렬화 파일(문자열 테이블 MonoBehaviour) 편집 ----
def align(n, a): return (n + a - 1) // a * a

def read_str(buf, p):
    n, = struct.unpack('<i', buf[p:p+4])
    return buf[p+4:p+4+n].decode('utf-8'), p + 4 + align(n, 4)

def enc_str(s):
    b = s.encode('utf-8')
    return struct.pack('<i', len(b)) + b + b'\0' * (align(len(b), 4) - len(b))

_PATCHED = []

def _unitypy():
    """이 게임 번들을 읽기 위한 UnityPy 보정(타입트리 28바이트 건너뛰기)을 한 번만 적용한다."""
    import UnityPy.helpers.TypeTreeNode as T
    import UnityPy.helpers.TypeTreeHelper as H
    if not _PATCHED:
        _o = T.TypeTreeNode.parse_blob.__func__
        T.TypeTreeNode.parse_blob = classmethod(lambda c, r, v: (setattr(r, "Position", r.Position + 28), _o(c, r, v))[1])
        H.read_typetree_boost = None
        _PATCHED.append(1)
    import UnityPy
    return UnityPy

def unityfs_objects(path_or_bytes):
    UnityPy = _unitypy()
    env = UnityPy.load(path_or_bytes)
    objs = [(o.path_id, o.byte_start, o.byte_size, o.type.name) for o in env.objects]
    strings = None
    for o in env.objects:
        if o.type.name == "MonoBehaviour":
            t = o.read_typetree()
            if "Strings" in t:
                strings = {s["Key"]: s["Value"] for s in t["Strings"]}
    return objs, strings

def edit_bundle(data, repl):
    """repl: {key: 새 값}. 반환: (새 번들 바이트, 바꾼 키 수)"""
    d = bparse(data)
    assert len(d['nodes']) == 1
    raw = d['data']
    ver, = struct.unpack('>I', raw[8:12]); assert ver >= 22, ver
    meta_size, file_size, data_off = struct.unpack('>IqQ', raw[20:40])
    objs, _ = unityfs_objects(data)
    objs = sorted((pid, bs - data_off, sz, tn) for pid, bs, sz, tn in objs)
    mbs = [o for o in objs if o[3] == "MonoBehaviour"]
    mb = max(mbs, key=lambda o: o[2])
    ents = {}
    for pid, bs, sz, _t in objs:
        pat = struct.pack('<qqI', pid, bs, sz)
        idx = raw.find(pat, 0, data_off)
        assert idx >= 0 and raw.find(pat, idx + 1, 0 + data_off) < 0, 'object entry not unique/found'
        ents[pid] = idx
    mb_pid, mb_bs, mb_sz, _ = mb
    base = data_off
    mbb = raw[base + mb_bs: base + mb_bs + mb_sz]
    p = 12 + 4 + 12
    _, p = read_str(mbb, p)
    head = mbb[:p]
    cnt, = struct.unpack('<i', mbb[p:p+4]); p += 4
    parts = [head, struct.pack('<i', cnt)]
    changed = 0
    for _ in range(cnt):
        k, p2 = read_str(mbb, p)
        v, p3 = read_str(mbb, p2)
        if k in repl:
            parts.append(mbb[p:p2]); parts.append(enc_str(repl[k])); changed += 1
        else:
            parts.append(mbb[p:p3])
        p = p3
    assert p == len(mbb), "MonoBehaviour 끝이 맞지 않습니다"
    new_mb = b''.join(parts)
    mb_end_old = mb_bs + mb_sz
    new_mb_end = mb_bs + len(new_mb)
    shift = align(new_mb_end, 8) - align(mb_end_old, 8)
    after = [o for o in objs if o[1] >= align(mb_end_old, 8) and o[0] != mb_pid]
    # MonoBehaviour 뒤에 오는 영역은 통째로 옮긴다
    tail_old = raw[base + align(mb_end_old, 8):]
    new_data = raw[base:base + mb_bs] + new_mb + b'\0' * (align(new_mb_end, 8) - new_mb_end) + tail_old
    new_raw = bytearray(raw[:base]) + new_data
    struct.pack_into('<qqI', new_raw, ents[mb_pid], mb_pid, mb_bs, len(new_mb))
    for pid, bs, sz, _t in after:
        struct.pack_into('<qqI', new_raw, ents[pid], pid, bs + shift, sz)
    struct.pack_into('>q', new_raw, 24, len(new_raw))
    nodes = [[0, len(new_raw), d['nodes'][0][2], d['nodes'][0][3]]]
    return bbuild(d, bytes(new_raw), nodes), changed

# ---- 문구 만들기 ----
def term(strings, key, fallback):
    return strings.get(key) or fallback

def make_note(e, lang, strings):
    lock = term(strings, "ITEM_LOCKPICK_TITLE", "락픽" if lang == "ko" else "Lockpick")
    bolt = term(strings, "ITEM_BOLTCUTTERS_TITLE", "볼트 절단기" if lang == "ko" else "Bolt Cutters")
    if lang == "ko":
        head, none, trig, other = "[잠금장치]", "없음", "조건부 추가", "기타 잠금 %d"
    else:
        head, none, trig, other = "[Locks]", "none", "conditional extra", "other locks %d"
    s = None
    if e["lp"] or e["bc"]:
        s = "%s %d / %s %d" % (lock, e["lp"], bolt, e["bc"])
    extra = []
    if e["tlp"]: extra.append("%s %d" % (lock, e["tlp"]))
    if e["tbc"]: extra.append("%s %d" % (bolt, e["tbc"]))
    if extra:
        s = (s + " " if s else "") + "(%s: %s)" % (trig, ", ".join(extra))
    if e["other"]:
        s = (s + " / " if s else "") + other % e["other"]
    if not s:
        s = none
    return "\n\n" + head + " " + s

def location_keys(entries, en):
    import re
    inv = {}
    for k, v in en.items():
        if k.startswith("LOCATION") and not k.endswith("_DESC"):
            inv.setdefault(v, []).append(k)
    res = {}
    for e in entries:
        m = re.match(r"^(.*?_\d\d)(?:_|$)", e["asset"])
        k = "LOCATION_" + m.group(1).upper() if m else None
        if not (k in en and en[k] == e["name"]):
            c = [x for x in inv.get(e["name"], []) if not x.startswith(("LOCATION_PAX", "LOCATION_INACCESSIBLE"))]
            k = c[0] if len(c) == 1 else None
        res[e["asset"]] = k
    return res

def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    stage = sys.argv[1]
    entries = json.load(open(os.path.join(HERE, "lootnotes.json"), encoding="utf-8"))
    langs = [("ko", "loc.korean"), ("en", "loc.english")]
    data = {}
    strs = {}
    for lang, fn in langs:
        pth = os.path.join(stage, fn)
        if not os.path.isfile(pth):
            sys.exit("%s 를 찾을 수 없습니다: %s" % (fn, pth))
        data[lang] = open(pth, "rb").read()
        _, strs[lang] = unityfs_objects(data[lang])
        if not strs[lang]:
            sys.exit("%s 에서 문자열 표를 읽지 못했습니다 (게임 버전이 달라졌을 수 있습니다)." % fn)
    keys = location_keys(entries, strs["en"])
    repl = {"ko": {}, "en": {}}
    missing = []
    for e in entries:
        k = keys[e["asset"]]
        dk = (k + "_DESC") if k else None
        if not k or dk not in strs["en"] or dk not in strs["ko"]:
            if k is None or dk in strs["en"] or dk in strs["ko"]:
                missing.append(e["asset"])        # 설명이 없는 거래소 등은 정상이므로 세지 않는다 (키는 있고 설명 키만 없는 경우)
            continue
        for lang in ("ko", "en"):
            repl[lang][dk] = strs[lang][dk] + make_note(e, lang, strs[lang])
    if missing:
        print("주의: 번역 키를 찾지 못한 장소 %d곳은 건너뜁니다: %s" % (len(missing), ", ".join(missing[:5])))
    if len(repl["ko"]) < 40:
        sys.exit("중단: 문구를 붙일 장소가 너무 적습니다 (%d곳). 게임이 업데이트되어 키가 달라진 것 같습니다. 아무것도 바꾸지 않았습니다." % len(repl["ko"]))
    out = {}
    for lang, fn in langs:
        new, changed = edit_bundle(data[lang], repl[lang])
        assert changed == len(repl[lang]), (fn, changed, len(repl[lang]))
        # 검증: 다시 읽어서 의도한 키만, 의도한 값으로 바뀌었는지
        _, back = unityfs_objects(new)
        want = dict(strs[lang]); want.update(repl[lang])
        if back != want:
            diff = [k for k in set(back) | set(want) if back.get(k) != want.get(k)]
            sys.exit("중단: %s 편집 결과 검증에 실패했습니다 (다른 키 %d개). 아무것도 바꾸지 않았습니다." % (fn, len(diff)))
        out[fn] = new
    for fn, new in out.items():
        tmp = os.path.join(stage, fn + ".new")
        open(tmp, "wb").write(new)
        os.replace(tmp, os.path.join(stage, fn))
    print("장소 설명 %d곳에 락픽/볼트 절단기 개수를 붙였습니다 (한국어/영어, 검증 완료)." % len(repl["ko"]))

if __name__ == "__main__":
    main()
