import sys,random,re,collections
from patch import *
from UnityPy.streams import EndianBinaryReader
SRC,SEED,OUT=sys.argv[1],int(sys.argv[2]),sys.argv[3]
D="/root/.claude/uploads/fe2a6e89-3196-5bb4-9001-dc8e5c151021/"
gid=lambda g:bytes(g["m_guid"]["bytes[%d]"%i] for i in range(16))
cfg=UnityPy.load(D+"e437e57e-data_config")
ids={}
for o in cfg.objects:
    if o.type.name=="MonoBehaviour":
        try: n=o.read().m_Name
        except: continue
        if n.startswith("RecruitmentId_"): ids[o.path_id]=n
env=UnityPy.load(SRC); bundle=env.file
name,sf=[(n,f) for n,f in bundle.files.items() if hasattr(f,'types')][0]
raw=bytearray(sf.reader.bytes); flags=sf.flags
surv={}
for o in env.objects:
    if o.type.name=="MonoBehaviour":
        try: tt=o.read_typetree()
        except: continue
        if tt["m_Name"].startswith("Survivor_") and "m_inventorySize" in tt: surv[tt["m_Name"][9:]]=gid(tt["m_guid"])
rows=[]
for o in env.objects:
    if o.type.name!="MonoBehaviour": continue
    try: tt=o.read_typetree()
    except: continue
    if "m_recruitmentId" in tt and tt["m_recruitmentId"]["m_PathID"] in ids:
        rid=ids[tt["m_recruitmentId"]["m_PathID"]][len("RecruitmentId_Scavenging_"):]
        rows.append((o,tt["m_Name"],rid,gid(tt["m_survivorGuid"])))
# 일반 영입 슬롯: 이름==슬롯이고 Hostage/스토리 전용 제외
SPECIAL={"Hector","Kayla","Charlie","Cooper","Isaiah","Taylor","Otto","Eva","Issac","Recruit_Hector_01","Recruit_Kayla_01"}
slots=sorted({r[2] for r in rows if not r[2].startswith(("Hostage","Recruit_")) and r[2] not in SPECIAL and r[2] in surv})
print(len(slots),slots)
rnd=random.Random(SEED)
while True:
    perm=slots[:]; rnd.shuffle(perm)
    if all(a!=b for a,b in zip(slots,perm)): break
newof=dict(zip(slots,perm))
for s in slots: print(f"{s} 장소 -> {newof[s]} 등장")
n=0
for o,nm,rid,g in rows:
    if rid not in newof: continue
    assert g==surv[rid],(nm,rid)
    st=o.byte_start; seg=bytes(raw[st:st+o.byte_size]); assert seg.count(g)==1,nm
    p=st+seg.find(g); raw[p:p+16]=surv[newof[rid]]; n+=1
print("patched",n)
r=EndianBinaryReader(bytes(raw)); r.flags=flags; bundle.files[name]=r
open(OUT,"wb").write(bundle.save(packer="lz4"))
