"""data_config 수정.
사용: python patch_config.py <원본 data_config> <시체 회수 칸수> <출력 파일> [crossbow|s12riot]
 - 시체 회수 칸 수(InventoryData_EmptyWithCapacity.m_maxSize)를 바꾼다.
 - 미스터 베일의 신규 판매 품목 순서를 바꾼다. 마지막 인자가 '첫 번째로 열릴 품목'이고, 이후는 석궁/샷건(S12 Riot)이 번갈아 열린다.
   R77 권총은 나오지 않는다. 인자를 생략하면 미스터 베일은 건드리지 않는다.
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
FIRST=sys.argv[4].lower() if len(sys.argv)>4 and sys.argv[4].lower() in ('crossbow','s12riot') else None
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
if FIRST:
    # 미스터 베일 신규 판매 품목 순서: 20사이클 단위 구간(window)을 석궁/S12 가 번갈아 쓰게 다시 배정한다.
    #  원래: 구간 1..9(20-40,40-60,...,180+)를 R77 -> 석궁 -> S12 순으로 돌아가며 사용 (품목 CycleRange 가 재고와 이벤트를 모두 결정)
    #  변경: 구간 1,3,5,7(,9) = 첫 품목 X, 구간 2,4,6 = 다른 품목 Y. R77 권총은 이벤트/재고 모두 끈다.
    #  CycleRange 는 OrCondition 이라 칸이 3개뿐이라, 쓰지 않는 R77 의 CycleRange 를 X 의 하위 조건으로 끼워 넣는다.
    objs={}
    for o in env.objects:
        if o.type.name!="MonoBehaviour": continue
        try: tt=o.read_typetree()
        except: continue
        n=tt.get("m_Name")
        if n and n.startswith(("CycleBetween","IsCycle","Trader_MrVale_","MrVale_TraderData")): objs.setdefault(n,o)
    def need(n):
        if n not in objs: sys.exit("미스터 베일 데이터에서 %s 를 찾지 못했습니다 (게임 업데이트로 구조가 바뀌었을 수 있음)" % n)
        return objs[n]
    pid=lambda n: need(n).path_id
    def edit(n,fn):
        o=need(n); tt=o.read_typetree(); st=o.byte_start; seg=bytes(raw[st:st+o.byte_size])
        fn(tt); new=o.save_typetree(tt); assert len(new)==len(seg),n+": 크기가 달라짐"
        raw[st:st+len(seg)]=new
        return sum(1 for i in range(len(seg)) if seg[i]!=new[i])
    def setconds(ids):
        def f(tt):
            assert len(tt["m_conditions"])==len(ids)
            for c,p in zip(tt["m_conditions"],ids): c["m_PathID"]=p
        return f
    X,Y={"crossbow":("Crossbow","S12Riot"),"s12riot":("S12Riot","Crossbow")}[FIRST]
    CR=lambda k:"Trader_MrVale_NewItemSale_%s_CycleRange"%k
    H=CR("R77RapidFirePistol")
    W=["CycleBetween20AND40","CycleBetween40AND60","CycleBetween60AND80","CycleBetween80AND100","CycleBetween100AND120",
       "CycleBetween120AND140","CycleBetween140AND160","CycleBetween160AND180","IsCycleGreaterOrEqual180"]
    w=[pid(n) for n in W]
    sk="Trader_MrVale_R77RapidFire_%s_SharedKnowledgeValueComparison"
    plan=[(CR(X),[w[0],w[2],pid(H)]),(H,[w[4],w[6],w[8]]),(CR(Y),[w[1],w[3],w[5]]),
          ("Trader_MrVale_NewItemSale_R77RapidFirePistol_PrepareForSale",None),
          ("Trader_MrVale_CrossbowBolt_CycleRange",[pid("IsCycleGreaterOrEqual20")])]
    nb=0
    for n,ids in plan:
        if n.endswith("_PrepareForSale"):   # R77 이벤트는 '이미 판매 중(Available)' 일 때만 -> 영영 안 일어남
            def f(tt):
                tt["m_conditions"][1]["m_PathID"]=pid(sk%"Available")
            nb+=edit(n,f)
        else:
            nb+=edit(n,setconds(ids))
    # R77 권총 재고 끄기 (H 가 이제 X 의 구간이므로 그대로 두면 권총이 팔린다)
    o=need("MrVale_TraderData"); tt=o.read_typetree(); st=o.byte_start; seg=bytes(raw[st:st+o.byte_size]); hit=0
    for ent in tt["m_traderStockData"]:
        for cv in ent["m_conditionalValueData"]:
            if any(c["m_PathID"]==pid(H) for c in cv["m_conditions"]):
                cv["m_conditionalObject"]["AmountOnHand"]=0; hit+=1
    assert hit==1,"R77 재고 항목을 찾지 못함"
    new=o.save_typetree(tt); assert len(new)==len(seg); raw[st:st+len(seg)]=new
    print("미스터 베일 신규 판매 순서: 사이클 20-40 %s, 40-60 %s, 60-80 %s, 80-100 %s, 100-120 %s, 120-140 %s, 140-160 %s, (160-180 신규 없음), 180 이후 %s 상시 (R77 권총 없음)" % (X,Y,X,Y,X,Y,X,X))
r=EndianBinaryReader(bytes(raw)); r.flags=flags; bundle.files[name]=r
open(OUT,"wb").write(bundle.save(packer="lz4"))
