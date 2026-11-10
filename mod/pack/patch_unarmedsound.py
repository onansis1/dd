"""Into the Dead: Our Darkest Days - 맨손 스텔스 처형 효과음을 하오/허드슨/이사야가 아닌 생존자도 들을 수 있게 한다 (data_visual 번들 수정).
사용: python patch_unarmedsound.py <data_visual 원본> <출력 파일>
 - 맨손 스텔스 처형 3종(기본 맨손/무술/브루탈)의 효과음 에셋(ConditionalCharacterAudioEvent)은 '현재 생존자가 허드슨/하오/이사야인가' 조건이 참일 때만 소리를 낸다.
   그 조건 포인터 12바이트(fileID 2 + pathID)를 data_config 의 '항상 참' 조건(ReturnTrueCondition)을 가리키게 바꾼다. 효과음 이벤트 하나에 타격음과 목소리가 함께 들어 있고
   목소리는 생존자의 CharacterType 값으로 고르므로, 처형하는 생존자마다 자기 목소리로 난다. (게임이 처형 때 CharacterType 을 실제로 넣는지는 게임에서 확인해야 한다)
 - 같은 조건 객체를 쓰는 다른 에셋(크리티컬/다운 처형 등)은 건드리지 않으려고, 값 검색이 아니라 확인된 위치(블록 번호 + 블록 안 오프셋)만 고친다.
   위치마다 원래 12바이트와 앞뒤 16바이트가 예상과 같을 때만 고치고, 하나라도 다르면(게임 업데이트 등) 아무것도 쓰지 않고 중단한다.
 - 번들은 블록(131072바이트) 압축이라, 바뀐 블록 3개만 다시 압축하고 블록 표를 고쳐 쓴다. 나머지 블록은 그대로 복사한다. 쓴 뒤 다시 읽어서 확인한다.
"""
import hashlib, os, struct, sys

# (효과음 에셋, 블록 번호, 블록 안 오프셋, 원래 12바이트, 앞 16바이트, 뒤 16바이트)
OLD_HAO = bytes.fromhex("020000006895e7ff49ff3fa5")
OLD_HUD = bytes.fromhex("02000000edf0369a04dbf9f4")
OLD_ISA = bytes.fromhex("020000007b69466ea6ca3454")
NEW = bytes.fromhex("02000000c2739a9fb8bece34")          # data_config 의 ReturnTrueCondition (AlwaysTrueCondition)
TARGETS = [
    ("UnarmedMartialArtsStealthExecution01_AudioData (하오)", 2490, 0x2414, OLD_HAO,
     bytes.fromhex("5f417564696f44617461000001000000"), bytes.fromhex("964f74f765292344b27cdac1742ccf59")),
    ("UnarmedStealthExecution01_AudioData (허드슨)", 2219, 0x146c8, OLD_HUD,
     bytes.fromhex("315f417564696f446174610001000000"), bytes.fromhex("a804cfdf87776542979f061095b4162a")),
    ("UnarmedBrutalStealthExecution01_AudioData (이사야)", 3028, 0x1f0, OLD_ISA,
     bytes.fromhex("417564696f4461746100000001000000"), bytes.fromhex("8e7d1e2eaeb5e04dafd642ac12db85e2")),
]
BLK = 131072


def _lz4():
    import lz4.block
    return lz4.block


def read_header(f):
    """UnityFS(format 8) 머리 + 블록 정보를 읽는다. (블록 표는 목록으로, 그 뒤의 노드 정보는 그대로 둔다)"""
    L = _lz4()
    f.seek(0)
    head = f.read(512)
    i = head.index(b"\0")
    assert head[:i] == b"UnityFS", head[:i]
    i += 1
    fmt, = struct.unpack(">I", head[i:i + 4]); i += 4
    uv_end = head.index(b"\0", i); uv = head[i:uv_end]; i = uv_end + 1
    rv_end = head.index(b"\0", i); rv = head[i:rv_end]; i = rv_end + 1
    size, cbi, ubi, flags = struct.unpack(">qIII", head[i:i + 20]); i += 20
    if fmt != 8:
        raise ValueError("지원하지 않는 번들 형식 %d" % fmt)
    if flags & 0x80:
        raise ValueError("블록 정보가 파일 끝에 있는 번들은 지원하지 않습니다")
    pos = i
    if flags & 0x200:
        pos = (pos + 15) // 16 * 16
    f.seek(pos)
    raw = f.read(cbi)
    comp = flags & 0x3f
    if comp not in (0, 2, 3):
        raise ValueError("지원하지 않는 블록 정보 압축 %d" % comp)
    info = raw if comp == 0 else L.decompress(raw, uncompressed_size=ubi)
    assert len(info) == ubi
    nb, = struct.unpack(">i", info[16:20])
    blocks = []
    p = 20
    for _ in range(nb):
        u, c, fl = struct.unpack(">IIH", info[p:p + 10]); p += 10
        blocks.append([u, c, fl])
    data_start = pos + cbi
    if flags & 0x200:
        data_start = (data_start + 15) // 16 * 16
    return dict(prefix=head[:i - 20], size=size, flags=flags, cbi=cbi, ubi=ubi, info=info, nb=nb,
                blocks=blocks, tail=info[p:], data_start=data_start, pos=pos)


def block_offsets(h):
    offs = []
    o = h["data_start"]
    for u, c, fl in h["blocks"]:
        offs.append(o)
        o += c
    return offs, o


def read_block(f, h, offs, k):
    L = _lz4()
    u, c, fl = h["blocks"][k]
    f.seek(offs[k])
    raw = f.read(c)
    assert len(raw) == c
    t = fl & 0x3f
    if t == 0:
        return raw
    if t not in (2, 3):
        raise ValueError("지원하지 않는 블록 압축 %d (블록 %d)" % (t, k))
    return L.decompress(raw, uncompressed_size=u)


def patch(src, out, targets=None, log=print):
    L = _lz4()
    targets = TARGETS if targets is None else targets
    with open(src, "rb") as f:
        h = read_header(f)
        fsize = os.fstat(f.fileno()).st_size
        offs, end = block_offsets(h)
        if h["size"] != fsize or end != fsize:
            raise SystemExit("번들 크기가 예상과 다릅니다 (헤더 %d, 실제 %d, 블록 끝 %d). 게임 업데이트로 구조가 바뀌었을 수 있습니다." % (h["size"], fsize, end))
        changed = {}      # 블록 번호 -> 새 압축 데이터, 새 해제 데이터
        by_block = {}
        for t in targets:
            by_block.setdefault(t[1], []).append(t)
        for k, ts in sorted(by_block.items()):
            if k >= h["nb"]:
                raise SystemExit("블록 %d 이(가) 없습니다 (게임 업데이트로 구조가 바뀌었을 수 있습니다). 아무것도 바꾸지 않았습니다." % k)
            plain = bytearray(read_block(f, h, offs, k))
            for name, _k, off, old, before, after in ts:
                cur = bytes(plain[off:off + 12])
                if cur == NEW and plain[off - 16:off] == before and plain[off + 12:off + 28] == after:
                    log("  %s: 이미 수정돼 있습니다" % name)
                    continue
                if cur != old or bytes(plain[off - 16:off]) != before or bytes(plain[off + 12:off + 28]) != after:
                    raise SystemExit("%s 의 위치(블록 %d, 오프셋 0x%x)의 내용이 예상과 다릅니다 (게임 업데이트로 바뀌었을 수 있습니다). 아무것도 바꾸지 않았습니다." % (name, k, off))
                plain[off:off + 12] = NEW
                log("  %s: 조건 12바이트 교체 (블록 %d, 오프셋 0x%x)" % (name, k, off))
            u = h["blocks"][k][0]
            assert len(plain) == u
            comp = L.compress(bytes(plain), mode="high_compression", compression=12, store_size=False)
            if len(comp) < len(plain):
                changed[k] = (comp, 3, bytes(plain))
            else:
                changed[k] = (bytes(plain), 0, bytes(plain))
        if not changed:
            raise SystemExit("바꿀 것이 없습니다.")
        # 새 블록 표 / 블록 정보
        nblocks = [list(b) for b in h["blocks"]]
        for k, (cdata, fl, _plain) in changed.items():
            nblocks[k][1] = len(cdata)
            nblocks[k][2] = (nblocks[k][2] & ~0x3f) | fl
        info = h["info"][:16] + struct.pack(">i", h["nb"])
        for u, c, fl in nblocks:
            info += struct.pack(">IIH", u, c, fl)
        info += h["tail"]
        assert len(info) == h["ubi"]
        cinfo = L.compress(info, mode="high_compression", compression=12, store_size=False)
        flags = (h["flags"] & ~0x3f) | 3
        pos = len(h["prefix"]) + 20
        pad = pad2 = 0
        if flags & 0x200:
            pad = (-pos) % 16
            pad2 = (-(pos + pad + len(cinfo))) % 16
        body = sum(c for _u, c, _f in nblocks)
        total = pos + pad + len(cinfo) + pad2 + body
        tmp = out + ".tmp"
        with open(tmp, "wb") as g:
            g.write(h["prefix"] + struct.pack(">qIII", total, len(cinfo), len(info), flags))
            g.write(b"\0" * pad + cinfo + b"\0" * pad2)
            for k in range(h["nb"]):
                if k in changed:
                    g.write(changed[k][0])
                else:
                    f.seek(offs[k])
                    left = h["blocks"][k][1]
                    while left:
                        buf = f.read(min(left, 8 << 20))
                        assert buf
                        g.write(buf)
                        left -= len(buf)
    # 쓴 뒤 검증: 머리/블록 표를 다시 읽고, 바뀐 블록은 의도한 내용인지, 안 바뀐 블록은 원본과 바이트가 같은지 확인
    try:
        with open(out + ".tmp", "rb") as g, open(src, "rb") as f:
            h2 = read_header(g)
            offs2, end2 = block_offsets(h2)
            assert end2 == h2["size"] == os.fstat(g.fileno()).st_size, "파일 크기"
            assert h2["nb"] == h["nb"] and h2["tail"] == h["tail"], "블록 수/노드 정보"
            for k in range(h["nb"]):
                assert h2["blocks"][k][0] == h["blocks"][k][0], "해제 크기 %d" % k
                if k in changed:
                    assert read_block(g, h2, offs2, k) == changed[k][2], "바뀐 블록 %d" % k
                else:
                    assert h2["blocks"][k] == h["blocks"][k], "블록 표 %d" % k
                    g.seek(offs2[k]); f.seek(offs[k])
                    c = h["blocks"][k][1]
                    while c:
                        n = min(c, 8 << 20)
                        assert g.read(n) == f.read(n), "블록 %d 내용" % k
                        c -= n
            for name, k, off, old, before, after in targets:
                plain = changed[k][2]
                assert plain[off:off + 12] == NEW and plain[off - 16:off] == before and plain[off + 12:off + 28] == after, name
                # 바뀐 12바이트 밖은 원본과 같아야 한다
            for k in changed:
                a = read_block(f, h, offs, k)
                b = changed[k][2]
                diff = [i for i in range(len(a)) if a[i] != b[i]]
                allowed = set()
                for _n, kk, off, *_r in targets:
                    if kk == k:
                        allowed.update(range(off, off + 12))
                assert set(diff) <= allowed, "예상 밖 바이트가 바뀜 (블록 %d)" % k
        os.replace(out + ".tmp", out)
    except AssertionError as e:
        try:
            os.remove(out + ".tmp")
        except OSError:
            pass
        raise SystemExit("쓴 결과 검증 실패(%s). 아무것도 바꾸지 않았습니다." % (e,))
    log("맨손 스텔스 처형 효과음 조건 %d곳을 '항상 참'으로 변경: 블록 %s 다시 압축 (파일 %d -> %d 바이트)" % (len(targets), "/".join(str(k) for k in sorted(changed)), fsize, total))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    patch(sys.argv[1], sys.argv[2])
