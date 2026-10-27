"""data_config 수정.
사용: python patch_config.py <원본 data_config> <시체 회수 칸수> <출력 파일> [미스터 베일 상시 판매 품목, 쉼표로 구분]
 - 시체 회수 칸 수(InventoryData_EmptyWithCapacity.m_maxSize)를 바꾼다.
 - 미스터 베일(MrVale_TraderData)의 이벤트 전용 상품은 기본 재고가 0 이고 이벤트 기간에만 재고/가격이 생긴다.
   품목을 지정하면 그 상품의 기본 재고를 이벤트 때의 재고/가격으로 바꿔 항상 팔게 한다. 예: S12Riot_Def,R77Rapid_Def,Crossbow_Def
"""
import sys
import UnityPy.helpers.TypeTreeNode as T
_orig = T.TypeTreeNode.parse_blob.__func__
def _pb(cls, reader, version):
    reader.Position = reader.Position + 28
    return _orig(cls, reader, version)
T.TypeTreeNode.parse_blob = classmethod(_pb)
# Windows + Python 3.14 에서 UnityPy 의 C 가속 모듈(UnityPyBoost)이 접근 위반(access violation)으로 죽는 문제 대응:
# 가속 모듈을 끄고 순수 파이썬 읽기 경로를 쓴다 (느리지만 결과는 같다).
try:
    import UnityPy.helpers.TypeTreeHelper as _TTH
    _TTH.read_typetree_boost = None
except Exception:
    pass
import UnityPy
from UnityPy.streams import EndianBinaryReader
SRC,NEW,OUT=sys.argv[1],int(sys.argv[2]),sys.argv[3]
VALE=[x.strip() for x in sys.argv[4].split(',') if x.strip()] if len(sys.argv)>4 else []
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
if VALE:
    gid=lambda g:bytes(g["m_guid"]["bytes[%d]"%i] for i in range(16)).hex() if isinstance(g,dict) and "m_guid" in g else None
    names={}
    for o in env.objects:
        if o.type.name=="MonoBehaviour":
            try: tt=o.read_typetree()
            except: continue
            if isinstance(tt.get("m_guid"),dict) and "m_guid" in tt["m_guid"]: names[gid(tt["m_guid"])]=tt["m_Name"]
    done=set()
    for o in env.objects:
        if o.type.name!="MonoBehaviour": continue
        try: tt=o.read_typetree()
        except: continue
        if tt.get("m_Name")!="MrVale_TraderData": continue
        st=o.byte_start; seg=bytes(raw[st:st+o.byte_size]); changed=False
        for ent in tt["m_traderStockData"]:
            nm=names.get(gid(ent["m_itemId"]),"")
            if nm in VALE and ent["m_conditionalValueData"]:
                ev=ent["m_conditionalValueData"][0]["m_conditionalObject"]
                ent["m_defaultStockValueData"]={"AmountOnHand":ev["AmountOnHand"],"Value":ev["Value"]}
                done.add(nm); changed=True
                print("미스터 베일 상시 판매: %s  재고 %d, 가격 %d" % (nm,ev["AmountOnHand"],ev["Value"]))
        if changed:
            new=o.save_typetree(tt); assert len(new)==len(seg)
            dd=[i for i in range(len(seg)) if seg[i]!=new[i]]
            assert dd and max(dd)-min(dd)<=64*len(done)+64,"예상과 다른 변경 범위"
            raw[st:st+len(seg)]=new
    missing=[v for v in VALE if v not in done]
    if missing: sys.exit("미스터 베일 상점에서 찾지 못한 품목: %s (이름이 틀렸거나 이벤트 전용 상품이 아닙니다)" % ", ".join(missing))
r=EndianBinaryReader(bytes(raw)); r.flags=flags; bundle.files[name]=r
open(OUT,"wb").write(bundle.save(packer="lz4"))
