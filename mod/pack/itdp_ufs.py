"""ufs.py - minimal UnityFS (v6-8) reader/writer for COPY-ONLY tools (never touches the game folder).
Block-level writer: keeps all untouched compressed blocks byte-for-byte and re-compresses only from the first changed block."""
import struct, lz4.block, hashlib

BLOCK = 131072

def rd_cstr(b, p):
    e = b.index(b'\0', p); return b[p:e].decode('utf8'), e + 1

def align16(n): return (n + 15) & ~15

class Bundle:
    def __init__(self, path):
        d = open(path, 'rb').read(); self.raw = d; self.path = path
        sig, p = rd_cstr(d, 0); assert sig == 'UnityFS', sig
        self.version, = struct.unpack_from('>I', d, p); p += 4
        self.player, p = rd_cstr(d, p); self.engine, p = rd_cstr(d, p)
        self.size, self.cbi, self.ubi, self.flags = struct.unpack_from('>qIII', d, p); p += 20
        self.hdr_end = p
        if self.version >= 7: p = align16(p)
        assert not (self.flags & 0x80), 'blocks-info-at-end layout not supported by this tool'
        assert self.flags & 0x40, 'separate directory layout not supported by this tool'
        self.bi_pos = p
        bi = d[p:p + self.cbi]
        comp = self.flags & 0x3f
        if comp == 0: biu = bi
        elif comp in (2, 3): biu = lz4.block.decompress(bi, uncompressed_size=self.ubi)
        else: raise Exception('blocks-info compression %d unsupported' % comp)
        self.bi_hash = biu[:16]
        q = 16; nb, = struct.unpack_from('>i', biu, q); q += 4
        self.blocks = []
        for _ in range(nb):
            u, c, f = struct.unpack_from('>IIH', biu, q); q += 10; self.blocks.append((u, c, f))
        nn, = struct.unpack_from('>i', biu, q); q += 4
        self.nodes = []
        for _ in range(nn):
            off, sz, fl = struct.unpack_from('>qqI', biu, q); q += 20
            nm, q = rd_cstr(biu, q); self.nodes.append((off, sz, fl, nm))
        assert q == len(biu)
        ds = p + self.cbi
        self.data_start = align16(ds) if self.flags & 0x200 else ds
        # compressed block file offsets
        self.block_pos = []; x = self.data_start
        for u, c, f in self.blocks: self.block_pos.append(x); x += c
        assert x == len(d), (x, len(d))
        assert self.size == len(d)
        self._dec = None

    def comp_block(self, i):
        u, c, f = self.blocks[i]; return self.raw[self.block_pos[i]:self.block_pos[i] + c]

    def dec_block(self, i):
        u, c, f = self.blocks[i]; b = self.comp_block(i); cm = f & 0x3f
        if cm == 0: return b
        if cm in (2, 3): return lz4.block.decompress(b, uncompressed_size=u)
        raise Exception('block comp %d' % cm)

    def decompress(self):
        if self._dec is None: self._dec = b''.join(self.dec_block(i) for i in range(len(self.blocks)))
        return self._dec

    def node_data(self, name):
        dec = self.decompress()
        for off, sz, fl, nm in self.nodes:
            if nm == name: return dec[off:off + sz]
        raise KeyError(name)

def _chunks(data, level):
    out = []
    for i in range(0, len(data), BLOCK):
        ch = data[i:i + BLOCK]
        c = lz4.block.compress(ch, mode='high_compression', compression=level, store_size=False)
        if len(c) >= len(ch): out.append(((len(ch), len(ch), 0), ch))
        else: out.append(((len(ch), len(c), 3), c))
    return out

def write_bundle(src, node_name, new_bytes, mode='rebuild', level=6):   # level 12 -> 6: 압축 시간 약 7배 단축, 파일 크기 +0.4% (같은 LZ4 블록 형식이라 게임이 읽는 방식은 같다)
    """Return bytes of a new bundle in which node `node_name` has content new_bytes.
    mode 'rebuild': node stays in place, later nodes shift; blocks before the first changed block are reused verbatim.
    mode 'append' : old stream untouched; new node data appended at stream end (old bytes stay as an unreferenced gap)."""
    dec = src.decompress()
    tgt = [i for i, n in enumerate(src.nodes) if n[3] == node_name]; assert len(tgt) == 1
    ti = tgt[0]; toff, tsz, tfl, _ = src.nodes[ti]
    nodes = list(src.nodes)
    if mode == 'rebuild':
        delta = len(new_bytes) - tsz
        nodes[ti] = (toff, len(new_bytes), tfl, node_name)
        for j in range(ti + 1, len(nodes)):
            o, s_, f_, n_ = nodes[j]
            nodes[j] = (o + delta, s_, f_, n_)
        new_stream_tail_from = toff                      # first changed byte in the decompressed stream
        keep = new_stream_tail_from // BLOCK             # blocks [0:keep) are byte-identical
        tail = dec[keep * BLOCK: toff] + new_bytes + dec[toff + tsz:]
    elif mode == 'append':
        nodes[ti] = (len(dec), len(new_bytes), tfl, node_name)
        keep = len(src.blocks) - 1                       # last (partial) block is re-chunked with the appended data
        tail = dec[keep * BLOCK:] + new_bytes
    else: raise ValueError(mode)
    # assert the kept blocks are full-size (needed so that stream offsets == block index * BLOCK)
    assert all(src.blocks[i][0] == BLOCK for i in range(keep)), 'kept blocks must be full'
    tail_blocks = _chunks(tail, level)
    blocks = list(src.blocks[:keep]) + [b for b, _ in tail_blocks]
    comp_parts = [src.comp_block(i) for i in range(keep)] + [c for _, c in tail_blocks]
    bi = bytearray(src.bi_hash)
    bi += struct.pack('>i', len(blocks))
    for u, c, f in blocks: bi += struct.pack('>IIH', u, c, f)
    bi += struct.pack('>i', len(nodes))
    for off, sz, fl, nm in nodes: bi += struct.pack('>qqI', off, sz, fl) + nm.encode() + b'\0'
    bic = lz4.block.compress(bytes(bi), mode='high_compression', compression=level, store_size=False)
    hdr = b'UnityFS\0' + struct.pack('>I', src.version) + src.player.encode() + b'\0' + src.engine.encode() + b'\0'
    body = b''.join(comp_parts)
    def mk(total):
        h = hdr + struct.pack('>qIII', total, len(bic), len(bi), src.flags)
        return h + b'\0' * (align16(len(h)) - len(h)) if src.version >= 7 else h
    h0 = mk(0); pre = h0 + bic
    pad = (align16(len(pre)) - len(pre)) if src.flags & 0x200 else 0
    total = len(pre) + pad + len(body)
    return mk(total) + bic + b'\0' * pad + body