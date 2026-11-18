"""itdp_edit2.py - itdp_edit.rebuild() 의 확장판: 객체 교체/추가/외부 파일 추가에 더해 '타입 항목'과 '스크립트 표 항목'도 추가한다 (v23 SerializedFile).
기존 itdp_edit.rebuild 는 타입 표를 건드리지 않으므로, 이 장면에 아직 없는 컴포넌트(MonoBehaviour 타입)를 새로 넣을 수 없다.
 - new_types   : 이미 완성된 타입 항목 바이트(다른 장면 파일에서 그대로 복사한 것) 목록. 새 타입 번호 = 기존 타입 수 + 인덱스
 - new_scripts : 스크립트 표에 덧붙일 (외부 파일 번호, 로컬 id) 목록 (12바이트씩). 타입 항목 안의 script_index 는 호출하는 쪽이 맞춰 둔다.
 나머지(객체 자료 영역의 16바이트 정렬 순차 배치, 객체 표, 외부 표, 참조 타입, 사용자 정보)는 itdp_edit.rebuild 와 같다."""
import struct
import itdp_ser as S


def rebuild_ext(orig_bytes, replace=None, append=None, new_externals=None, new_types=None, new_scripts=None):
    replace = replace or {}; append = append or []; new_externals = new_externals or []
    new_types = new_types or []; new_scripts = new_scripts or []
    s = S.Ser(orig_bytes); d = orig_bytes
    existing = {o[0] for o in s.objects}
    for p in replace:
        assert p in existing, 'replace: unknown pid %d' % p
    ntypes = len(s.types) + len(new_types)
    for p, t, b in append:
        assert p not in existing, 'append: pid %d exists' % p
        assert 0 <= t < ntypes, 'append: type id %d out of range' % t
    objs = []; data = bytearray()

    def put(pid, tid, b):
        pos = len(data); data.extend(b); data.extend(b'\0' * ((-len(data)) % 16)); objs.append((pid, pos, len(b), tid))

    for i, (pid, bs, bsz, tid) in enumerate(s.objects):
        put(pid, tid, replace.get(pid, s.object_bytes(i)))
    for pid, tid, b in append:
        put(pid, tid, b)
    if objs:                                                       # 마지막 객체 뒤의 정렬 패딩은 두지 않는다 (게임 번들의 원본 파일도 두지 않음)
        del data[objs[-1][1] + objs[-1][2]:]
    # ---- metadata: unity version .. end of type table (types count patched, new type entries appended)
    meta = bytearray(d[48:s.objects_count_pos])
    if new_types:
        struct.pack_into('<i', meta, s.types_count_pos - 48, ntypes)
        for tb in new_types:
            meta += tb
    abspos = lambda: 48 + len(meta)
    meta += struct.pack('<i', len(objs))
    meta += b'\0' * ((-abspos()) % 4)
    for pid, bs, bsz, tid in objs:
        meta += struct.pack('<qqIi', pid, bs, bsz, tid)
    # ---- script table (count patched, new entries appended)
    sc = bytearray(d[s.objects_end:s.externals_count_pos])
    assert struct.unpack_from('<i', sc, 0)[0] == len(s.scripts) and len(sc) == 4 + 12 * len(s.scripts), 'unexpected script table layout'
    if new_scripts:
        struct.pack_into('<i', sc, 0, len(s.scripts) + len(new_scripts))
        for fi, li in new_scripts:
            sc += struct.pack('<iq', fi, li)
    meta += sc
    meta += struct.pack('<i', len(s.externals) + len(new_externals))
    meta += d[s.externals_start:s.externals_end]
    for path in new_externals:
        meta += b'\0' + b'\0' * 16 + struct.pack('<i', 0) + path.encode() + b'\0'
    meta += d[s.externals_end:s.meta_end]
    data_offset = (48 + len(meta) + 15) // 16 * 16
    file_size = data_offset + len(data)
    hdr = struct.pack('>IIII', 0, 0, 23, 0) + bytes([s.endian, 0, 0, 0]) + struct.pack('>Iqqq', len(meta), file_size, data_offset, s.unknown)
    assert len(hdr) == 48
    out = bytes(hdr) + bytes(meta) + b'\0' * (data_offset - 48 - len(meta)) + bytes(data)
    assert len(out) == file_size
    return out
