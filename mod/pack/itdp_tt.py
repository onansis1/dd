"""tt.py - type-tree driven object reader for Ser (v23). Records field offsets; checks that parse consumes exactly the object bytes."""
import struct
from UnityPy.helpers.Tpk import get_common_strings
COMMON = get_common_strings()

class Node:
    __slots__ = ('ver','level','flags','type','name','size','index','meta','children')

def _s(buf, v):
    if v & 0x80000000: return COMMON.get(v & 0x7FFFFFFF, str(v & 0x7FFFFFFF))
    e = buf.index(b'\0', v); return buf[v:e].decode('utf8')

def build_tree(t):
    """t: SType with nodes_raw, strbuf -> root Node"""
    nodes = []
    for i in range(t.node_count):
        ver, level, flags, ts, ns, size, index, meta, rh = struct.unpack_from('<HBBIIiiiQ', t.nodes_raw, i * 32)
        n = Node(); n.ver, n.level, n.flags = ver, level, flags
        n.type = _s(t.strbuf, ts); n.name = _s(t.strbuf, ns); n.size, n.index, n.meta = size, index, meta; n.children = []
        nodes.append(n)
    stack = []
    for n in nodes:
        while stack and stack[-1].level >= n.level: stack.pop()
        if stack: stack[-1].children.append(n)
        stack.append(n)
    return nodes[0]

PRIM = {'SInt8': 'b', 'UInt8': 'B', 'char': 'B', 'bool': '?', 'SInt16': 'h', 'short': 'h', 'UInt16': 'H', 'unsigned short': 'H',
        'int': 'i', 'SInt32': 'i', 'unsigned int': 'I', 'UInt32': 'I', 'SInt64': 'q', 'long long': 'q', 'UInt64': 'Q', 'unsigned long long': 'Q',
        'float': 'f', 'double': 'd'}

class Walker:
    def __init__(self, data, base, end):
        self.d = data; self.p = base; self.base = base; self.end = end; self.leaves = []
    def align(self):
        self.p = self.base + ((self.p - self.base + 3) // 4) * 4
    def read(self, n, path):
        if n.type in PRIM:
            fmt = '<' + PRIM[n.type]; sz = struct.calcsize(fmt)
            v, = struct.unpack_from(fmt, self.d, self.p); off = self.p - self.base; self.p += sz
            self.leaves.append((path, off, n.type, v))
            if n.meta & 0x4000: self.align()
            return v
        if n.type == 'string':
            ln, = struct.unpack_from('<i', self.d, self.p); off = self.p - self.base; self.p += 4
            s = self.d[self.p:self.p + ln]; self.p += ln
            self.leaves.append((path, off, 'string', s.decode('utf8', 'replace'))); self.align(); return s
        if n.flags & 1 and len(n.children) == 2 and n.children[0].name == 'size':   # array
            cnt, = struct.unpack_from('<i', self.d, self.p); off = self.p - self.base; self.p += 4
            self.leaves.append((path + '.size', off, 'int', cnt))
            el = n.children[1]
            for i in range(cnt): self.read(el, '%s[%d]' % (path, i))
            if n.meta & 0x4000: self.align()
            return cnt
        for c in n.children: self.read(c, path + '.' + c.name if path else c.name)
        if n.meta & 0x4000: self.align()
        return None

def parse_object(ser, i, trees):
    pid, bs, bsz, tid = ser.objects[i]
    base = ser.data_offset + bs
    w = Walker(ser.data, base, base + bsz)
    root = trees[tid]
    w.read(root, '')
    if w.p - base != bsz: raise ValueError('object %d (pid %d type %d) parsed %d of %d bytes' % (i, pid, tid, w.p - base, bsz))
    return w.leaves

def parse_bytes(root, buf):
    """parse one object from raw bytes with its type-tree root; returns leaves [(path, offset, type, value)]"""
    w = Walker(buf, 0, len(buf)); w.read(root, '')
    if w.p != len(buf): raise ValueError('parsed %d of %d bytes' % (w.p, len(buf)))
    return w.leaves
