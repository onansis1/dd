"""itdp_edit3.py - SerializedFile v23 전체 재조립기 (itdp_edit/itdp_edit2 의 확장): 타입 표 / 스크립트 표 / 외부 파일 표를 '중간 삽입' 까지 할 수 있다.
호출하는 쪽이 최종 객체 목록, 타입 항목(원시 바이트) 목록, 스크립트 표, 외부 항목(원시 바이트) 목록을 모두 만들어서 넘긴다. 아무것도 안 바꾸고 넘기면 원본과 같은 바이트가 나온다 (selftest)."""
import struct
import itdp_ser as S


def types_raw(s):
    return [bytearray(s.data[t.start:t.end]) for t in s.types]


def externals_raw(s):
    return [e['empty'].encode() + b'\0' + e['guid'] + struct.pack('<i', e['type']) + e['path'].encode() + b'\0' for e in s.externals]


def external_entry(path):
    return b'\0' + b'\0' * 16 + struct.pack('<i', 0) + path.encode() + b'\0'


def assemble(orig, objects, types, scripts, externals):
    """objects: [(pid, tid, bytes)] 최종 순서 / types: [bytes] / scripts: [(fileid, localid)] / externals: [bytes]"""
    s = S.Ser(orig); d = orig
    objs = []; data = bytearray()
    for pid, tid, b in objects:
        pos = len(data); data.extend(b); data.extend(b'\0' * ((-len(data)) % 16)); objs.append((pid, pos, len(b), tid))
    if objs:
        del data[objs[-1][1] + objs[-1][2]:]
    meta = bytearray(d[48:s.types_count_pos])
    meta += struct.pack('<i', len(types))
    for t in types:
        meta += bytes(t)
    meta += struct.pack('<i', len(objs))
    meta += b'\0' * ((-(48 + len(meta))) % 4)
    for pid, bs, bsz, tid in objs:
        meta += struct.pack('<qqIi', pid, bs, bsz, tid)
    meta += struct.pack('<i', len(scripts))
    for fi, li in scripts:
        meta += struct.pack('<iq', fi, li)
    meta += struct.pack('<i', len(externals))
    for e in externals:
        meta += e
    meta += d[s.externals_end:s.meta_end]
    data_offset = (48 + len(meta) + 15) // 16 * 16
    file_size = data_offset + len(data)
    hdr = struct.pack('>IIII', 0, 0, 23, 0) + bytes([s.endian, 0, 0, 0]) + struct.pack('>Iqqq', len(meta), file_size, data_offset, s.unknown)
    assert len(hdr) == 48
    out = bytes(hdr) + bytes(meta) + b'\0' * (data_offset - 48 - len(meta)) + bytes(data)
    assert len(out) == file_size
    return out


def selftest(orig):
    s = S.Ser(orig)
    out = assemble(orig, [(o[0], o[3], s.object_bytes(i)) for i, o in enumerate(s.objects)], [bytes(t) for t in types_raw(s)], list(s.scripts), externals_raw(s))
    return out == orig
