"""ufs2.py - UnityFS reader/writer for COPY-ONLY tools: supports blocks-info at the END of the file (flags 0x80, e.g. data_user_settings, flags 0xC2) and the usual layout (blocks-info after the header).
Writer keeps the original header fields, recompresses all data blocks (LZ4HC, 128 KiB chunks) and writes blocks-info at the same place as the source layout."""
import struct, lz4.block, hashlib
BLOCK = 131072
def _cs(b, p): e = b.index(b'\0', p); return b[p:e].decode(), e + 1
def align16(n): return (n + 15) & ~15
class Bundle2:
    def __init__(self, path):
        d = open(path, 'rb').read(); self.raw = d; self.path = path
        sig, p = _cs(d, 0); assert sig == 'UnityFS', sig
        self.version, = struct.unpack_from('>I', d, p); p += 4
        self.player, p = _cs(d, p); self.engine, p = _cs(d, p)
        self.size, self.cbi, self.ubi, self.flags = struct.unpack_from('>qIII', d, p); p += 20
        assert self.size == len(d), (self.size, len(d)); self.at_end = bool(self.flags & 0x80)
        hdr_end = align16(p) if self.version >= 7 else p
        comp = self.flags & 0x3f; assert comp in (0, 2, 3), 'blocks-info compression %d' % comp
        bi_pos = len(d) - self.cbi if self.at_end else hdr_end
        bi = d[bi_pos:bi_pos + self.cbi]; biu = lz4.block.decompress(bi, uncompressed_size=self.ubi) if comp else bi
        self.bi_hash = biu[:16]; q = 16; nb, = struct.unpack_from('>i', biu, q); q += 4; self.blocks = []
        for _ in range(nb): u, c, f = struct.unpack_from('>IIH', biu, q); q += 10; self.blocks.append((u, c, f))
        nn, = struct.unpack_from('>i', biu, q); q += 4; self.nodes = []
        for _ in range(nn):
            off, sz, fl = struct.unpack_from('>qqI', biu, q); q += 20; nm, q = _cs(biu, q); self.nodes.append((off, sz, fl, nm))
        assert q == len(biu)
        self.data_start = hdr_end if self.at_end else align16(hdr_end + self.cbi) if (self.flags & 0x200) else hdr_end + self.cbi
        x = self.data_start; self.block_pos = []
        for u, c, f in self.blocks: self.block_pos.append(x); x += c
        assert x == (bi_pos if self.at_end else len(d)), (x, bi_pos, len(d))
        self._dec = None
    def dec_block(self, i):
        u, c, f = self.blocks[i]; b = self.raw[self.block_pos[i]:self.block_pos[i] + c]; cm = f & 0x3f
        return b if cm == 0 else lz4.block.decompress(b, uncompressed_size=u)
    def decompress(self):
        if self._dec is None: self._dec = b''.join(self.dec_block(i) for i in range(len(self.blocks)))
        return self._dec
    def node_data(self, name):
        dec = self.decompress()
        for off, sz, fl, nm in self.nodes:
            if nm == name: return dec[off:off + sz]
        raise KeyError(name)
    def build(self, node_name, new_bytes, level=12):
        """new bundle bytes with node `node_name` replaced (other nodes byte-identical, shifted if sizes change)"""
        dec = self.decompress(); parts = []; nodes = []; pos = 0
        for off, sz, fl, nm in self.nodes:
            data = new_bytes if nm == node_name else dec[off:off + sz]; parts.append(data); nodes.append((pos, len(data), fl, nm)); pos += len(data)
        stream = b''.join(parts); blocks = []; comp = []
        for i in range(0, len(stream), BLOCK):
            ch = stream[i:i + BLOCK]; c = lz4.block.compress(ch, mode='high_compression', compression=level, store_size=False)
            if len(c) >= len(ch): blocks.append((len(ch), len(ch), 0)); comp.append(ch)
            else: blocks.append((len(ch), len(c), 3 if self.blocks[0][2] & 0x3f == 3 else 2)); comp.append(c)
        bi = bytearray(self.bi_hash) + struct.pack('>i', len(blocks))
        for u, c, f in blocks: bi += struct.pack('>IIH', u, c, f)
        bi += struct.pack('>i', len(nodes))
        for off, sz, fl, nm in nodes: bi += struct.pack('>qqI', off, sz, fl) + nm.encode() + b'\0'
        bic = lz4.block.compress(bytes(bi), mode='high_compression', compression=level, store_size=False) if self.flags & 0x3f else bytes(bi)
        hdr = b'UnityFS\0' + struct.pack('>I', self.version) + self.player.encode() + b'\0' + self.engine.encode() + b'\0'
        def mk(total): h = hdr + struct.pack('>qIII', total, len(bic), len(bi), self.flags); return h + b'\0' * (align16(len(h)) - len(h)) if self.version >= 7 else h
        body = b''.join(comp)
        if self.at_end:
            total = len(mk(0)) + len(body) + len(bic); return mk(total) + body + bic
        h0 = mk(0); pre = h0 + bic; pad = (align16(len(pre)) - len(pre)) if self.flags & 0x200 else 0
        total = len(pre) + pad + len(body); return mk(total) + bic + b'\0' * pad + body
