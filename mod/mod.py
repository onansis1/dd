import sys,re
from patch import *
from UnityPy.streams import EndianBinaryReader
FACTOR=int(sys.argv[1]); OUT=sys.argv[2]
env=UnityPy.load(P)
bundle=env.file
name,sf=[(n,f) for n,f in bundle.files.items() if not n.endswith(".resS")][0]
raw=bytearray(sf.reader.bytes)
flags=sf.flags
changes=[]
for o in env.objects:
    if o.type.name!="MonoBehaviour": continue
    try: t=o.read()
    except: continue
    if not re.fullmatch(r"\w*Ammo(_\w+)?_Recipe",t.m_Name) or "Dismantle" in t.m_Name: continue
    tt=o.read_typetree()
    outs=[r for r in tt["references"]["RefIds"] if r["rid"]==tt["m_exchangeData"]["m_outputs"][0]["rid"]][0]["data"]["m_items"]
    g=outs[0]["m_itemDefinitionGuid"]["m_guid"]
    gb=bytes(g["bytes[%d]"%i] for i in range(16))
    cnt=outs[0]["m_count"]
    start=o.byte_start
    seg=raw[start:start+o.byte_size]
    idx=seg.find(gb+cnt.to_bytes(4,"little"))
    assert idx>=0 and seg.count(gb+cnt.to_bytes(4,"little"))==1,t.m_Name
    p=start+idx+16
    raw[p:p+4]=(cnt*FACTOR).to_bytes(4,"little")
    changes.append((t.m_Name,cnt,cnt*FACTOR))
for c in changes: print(*c)
r=EndianBinaryReader(bytes(raw)); r.flags=flags
bundle.files[name]=r
open(OUT,"wb").write(bundle.save(packer="lz4"))
