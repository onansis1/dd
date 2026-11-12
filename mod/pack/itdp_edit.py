"""ser_edit.py - rebuild a v23 SerializedFile with replaced / appended objects and appended externals (type table untouched)."""
import struct
import itdp_ser as S

def rebuild(orig_bytes, replace=None, append=None, new_externals=None):
    """replace: {pid: bytes}; append: [(pid, type_id, bytes)]; new_externals: [path strings]"""
    replace = replace or {}; append = append or []; new_externals = new_externals or []
    s = S.Ser(orig_bytes); d = orig_bytes
    existing = {o[0] for o in s.objects}
    for p in replace: assert p in existing, 'replace: unknown pid %d' % p
    for p, t, b in append:
        assert p not in existing, 'append: pid %d exists' % p
        assert 0 <= t < len(s.types)
    # ---- data region: sequential, 16-aligned, table order (verified to reproduce the original layout exactly)
    objs = []; data = bytearray()
    def put(pid, tid, b):
        pos = len(data); data.extend(b); data.extend(b'\0' * ((-len(data)) % 16)); objs.append((pid, pos, len(b), tid))
    for i, (pid, bs, bsz, tid) in enumerate(s.objects):
        put(pid, tid, replace.get(pid, s.object_bytes(i)))
    for pid, tid, b in append: put(pid, tid, b)
    # ---- metadata
    meta = bytearray(d[48:s.objects_count_pos])           # unity version .. end of type table (verbatim)
    abspos = lambda: 48 + len(meta)
    meta += struct.pack('<i', len(objs))
    meta += b'\0' * ((-abspos()) % 4)
    for pid, bs, bsz, tid in objs: meta += struct.pack('<qqIi', pid, bs, bsz, tid)
    meta += d[s.objects_end:s.externals_count_pos]         # script types (verbatim)
    meta += struct.pack('<i', len(s.externals) + len(new_externals))
    meta += d[s.externals_start:s.externals_end]           # existing externals (verbatim)
    for path in new_externals:
        meta += b'\0' + b'\0' * 16 + struct.pack('<i', 0) + path.encode() + b'\0'
    meta += d[s.externals_end:s.meta_end]                  # ref types + user info (verbatim)
    data_offset = (48 + len(meta) + 15) // 16 * 16
    file_size = data_offset + len(data)
    hdr = struct.pack('>IIII', 0, 0, 23, 0) + bytes([s.endian, 0, 0, 0]) + struct.pack('>Iqqq', len(meta), file_size, data_offset, s.unknown)
    assert len(hdr) == 48
    out = bytes(hdr) + bytes(meta) + b'\0' * (data_offset - 48 - len(meta)) + bytes(data)
    assert len(out) == file_size
    return out