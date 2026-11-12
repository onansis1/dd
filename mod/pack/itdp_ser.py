"""ser.py - SerializedFile v23 (Unity 6000.5) structure parser that keeps byte ranges (read-only study + copy tools)."""
import struct

class R:
    def __init__(s, d, p=0): s.d = d; s.p = p
    def u32(s): v, = struct.unpack_from('<I', s.d, s.p); s.p += 4; return v
    def i32(s): v, = struct.unpack_from('<i', s.d, s.p); s.p += 4; return v
    def i16(s): v, = struct.unpack_from('<h', s.d, s.p); s.p += 2; return v
    def i64(s): v, = struct.unpack_from('<q', s.d, s.p); s.p += 8; return v
    def u8(s): v = s.d[s.p]; s.p += 1; return v
    def raw(s, n): v = s.d[s.p:s.p + n]; s.p += n; return v
    def cstr(s):
        e = s.d.index(b'\0', s.p); v = s.d[s.p:e].decode('utf8'); s.p = e + 1; return v
    def align(s, n=4): s.p = (s.p + n - 1) // n * n

class SType:
    pass

class Ser:
    def __init__(self, data):
        self.data = data
        d = data
        h = struct.unpack_from('>IIII', d, 0)
        assert h[2] == 23, h
        self.endian = d[16]
        self.metadata_size, self.file_size, self.data_offset, self.unknown = struct.unpack_from('>Iqqq', d, 20)
        assert self.endian == 0
        r = R(d, 48)
        self.unity_version = r.cstr()
        self.target_platform = r.u32()
        self.enable_typetree = r.u8()
        self.types_start = None
        n = r.i32(); self.types_count_pos = r.p - 4; self.types = []
        for _ in range(n):
            t = SType(); t.start = r.p
            t.class_id = r.i32(); t.stripped = r.u8(); t.script_index = r.i16()
            t.script_id = r.raw(16) if t.class_id == 114 else None
            t.old_hash = r.raw(16)
            t.hash2 = r.raw(16)               # v23 extra #1 (16 bytes)
            t.x1, t.x2, t.x3 = struct.unpack_from('<III', d, r.p); r.p += 12   # v23 extra #2 (12 bytes)
            t.nodes_pos = r.p
            nn = r.i32(); sb = r.i32()
            t.node_count = nn; t.strbuf_size = sb
            t.nodes_raw = r.raw(nn * 32); t.strbuf = r.raw(sb)
            dn = r.i32(); t.deps = [r.i32() for _ in range(dn)]
            t.end = r.p
            self.types.append(t)
        self.types_end = r.p
        self.objects_count_pos = r.p
        n = r.i32(); self.objects = []
        self.objects_start = r.p
        for _ in range(n):
            r.align(4)
            pid = r.i64(); bs = r.i64(); bsz = r.u32(); tid = r.i32()
            self.objects.append([pid, bs, bsz, tid])
        self.objects_end = r.p
        n = r.i32(); self.scripts = []
        for _ in range(n):
            fi = r.i32(); r.align(4); li = r.i64(); self.scripts.append((fi, li))
        self.scripts_end = r.p
        n = r.i32(); self.externals_count_pos = r.p - 4; self.externals = []
        self.externals_start = r.p
        for _ in range(n):
            e = {}; e['empty'] = r.cstr(); e['guid'] = r.raw(16); e['type'] = r.i32(); e['path'] = r.cstr()
            self.externals.append(e)
        self.externals_end = r.p
        n = r.i32(); self.reftypes_count = n; self.reftypes_pos = r.p - 4; self.reftypes = []
        for _ in range(n):
            t = SType(); t.start = r.p
            t.class_id = r.i32(); t.stripped = r.u8(); t.script_index = r.i16()
            t.script_id = r.raw(16) if t.script_index >= 0 else None
            t.old_hash = r.raw(16)
            t.hash2 = r.raw(16); t.x1, t.x2, t.x3 = struct.unpack_from('<III', d, r.p); r.p += 12
            nn = r.i32(); sb = r.i32(); t.node_count = nn; t.strbuf_size = sb
            t.nodes_raw = r.raw(nn * 32); t.strbuf = r.raw(sb)
            t.cls = r.cstr(); t.ns = r.cstr(); t.asm = r.cstr(); t.end = r.p
            self.reftypes.append(t)
        self.user_info = r.cstr()
        self.meta_end = r.p
        self.metadata_end_expected = 48 + self.metadata_size
        self.ref_pos = self.externals_end

    def object_bytes(self, i):
        pid, bs, bsz, tid = self.objects[i]
        return self.data[self.data_offset + bs: self.data_offset + bs + bsz]

    def by_pid(self):
        return {o[0]: i for i, o in enumerate(self.objects)}

