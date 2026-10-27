"""data_config 의 시체 회수 칸 수(InventoryData_EmptyWithCapacity.m_maxSize)를 바꾼다.
사용: python patch_config.py <원본 data_config> <칸수> <출력 파일>
"""
import sys
import UnityPy.helpers.TypeTreeNode as T
_orig = T.TypeTreeNode.parse_blob.__func__
def _pb(cls, reader, version):
    reader.Position = reader.Position + 28
    return _orig(cls, reader, version)
T.TypeTreeNode.parse_blob = classmethod(_pb)
import UnityPy
from UnityPy.streams import EndianBinaryReader
SRC,NEW,OUT=sys.argv[1],int(sys.argv[2]),sys.argv[3]
env=UnityPy.load(SRC); bundle=env.file
sfs={n:f for n,f in bundle.files.items() if hasattr(f,'types')}
assert len(sfs)==1,list(bundle.files)
name,sf=next(iter(sfs.items()))
raw=bytearray(sf.reader.bytes); flags=sf.flags
for o in env.objects:
    if o.type.name!="MonoBehaviour": continue
    try: tt=o.read_typetree()
    except: continue
    if tt.get("m_Name")=="InventoryData_EmptyWithCapacity":
        st=o.byte_start; seg=bytes(raw[st:st+o.byte_size]); old=tt["m_maxSize"]; tt["m_maxSize"]=NEW
        new=o.save_typetree(tt); assert len(new)==len(seg)
        d=[i for i in range(len(seg)) if seg[i]!=new[i]]; assert d and max(d)<d[0]+4
        raw[st+d[0]:st+d[0]+4]=bytes(new[d[0]:d[0]+4]); print("m_maxSize",old,"->",NEW)
r=EndianBinaryReader(bytes(raw)); r.flags=flags; bundle.files[name]=r
open(OUT,"wb").write(bundle.save(packer="lz4"))
