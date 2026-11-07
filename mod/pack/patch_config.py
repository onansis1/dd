"""data_config 수정.
사용: python patch_config.py <원본 data_config> <시체 회수 칸수> <출력 파일> [crossbow|s12riot [시작 사이클 0|10|20]]
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
FIRST=sys.argv[4].lower() if len(sys.argv)>4 and sys.argv[4].lower() in ('crossbow','s12riot','s12only') else None
START=int(sys.argv[5]) if len(sys.argv)>5 else 20
if START not in (0,10,20): sys.exit('베일 시작 사이클은 0, 10, 20 중 하나여야 합니다')
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
        if n and n.startswith(("CycleBetween","IsCycle","Trader_MrVale_","Trader_FeatureFlag","MrVale_TraderData")): objs.setdefault(n,o)
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
    X,Y={"crossbow":("Crossbow","S12Riot"),"s12riot":("S12Riot","Crossbow"),"s12only":("S12Riot","Crossbow")}[FIRST]
    CR=lambda k:"Trader_MrVale_NewItemSale_%s_CycleRange"%k
    H=CR("R77RapidFirePistol")
    W=["CycleBetween20AND40","CycleBetween40AND60","CycleBetween60AND80","CycleBetween80AND100","CycleBetween100AND120",
       "CycleBetween120AND140","CycleBetween140AND160","CycleBetween160AND180","IsCycleGreaterOrEqual180"]
    w=[pid(n) for n in W]
    sk="Trader_MrVale_R77RapidFire_%s_SharedKnowledgeValueComparison"
    if START==20:
        # 원래 일정: 구간 20-40(X) 40-60(Y) 60-80(X) 80-100(Y) 100-120(X) 120-140(Y) 140-160(X) 160-180(없음) 180+(X)
        x_ids=[w[0],w[2],pid(H)]; h_ids=[w[4],w[6],w[8]]; y_ids=[w[1],w[3],w[5]]
        sched="20-40 %s, 40-60 %s, 60-80 %s, 80-100 %s, 100-120 %s, 120-140 %s, 140-160 %s, (160-180 신규 없음), 180 이후 %s 상시"%(X,Y,X,Y,X,Y,X,X)
        crossbow_first=20 if X=="Crossbow" else 40
    else:
        # 일정을 앞당긴다: 첫 구간을 [0,20) (또는 [10,20)) 으로 하고 두 번째 품목이 바로 20-40 에 나오게 한다.
        # '사이클 20 미만' 같은 기본 조건 객체는 구간 목록(OrCondition)에 그대로 넣을 수 있어서 새 구간 객체가 필요 없다.
        first_id=pid("IsCycleLessThan20") if START==0 else pid("CycleBetween10AND20")
        x_ids=[first_id,w[1],pid(H)]; h_ids=[w[3],w[5],w[8]]; y_ids=[w[0],w[2],w[4]]
        sched="%s %s, 20-40 %s, 40-60 %s, 60-80 %s, 80-100 %s, 100-120 %s, 120-140 %s, (140-180 신규 없음), 180 이후 %s 상시"%("0-20" if START==0 else "10-20",X,Y,X,Y,X,Y,X,X)
        crossbow_first=START if X=="Crossbow" else 20
    if FIRST=="s12only":
        # S12 샷건만 판다: S12 구간은 시작 시점부터 계속 참, 석궁/R77/석궁 볼트 구간은 계속 거짓.
        #  항상 거짓 = Trader_FeatureFlagDefinedCondition_Inverted, 항상 참 = Trader_FeatureFlagDefinedCondition (둘 다 기존 객체)
        t=pid("Trader_FeatureFlagDefinedCondition"); f_=pid("Trader_FeatureFlagDefinedCondition_Inverted")
        s_id={0:t,10:pid("IsCycleGreaterOrEqual10"),20:pid("IsCycleGreaterOrEqual20")}[START]
        x_ids=[s_id,s_id,s_id]; h_ids=[f_,f_,f_]; y_ids=[f_,f_,f_]
        sched="%s 사이클부터 S12Riot 만 계속 판매 (석궁/R77 없음)"%START
        crossbow_first=99
    plan=[(CR(X),x_ids),(H,h_ids),(CR(Y),y_ids),
          ("Trader_MrVale_NewItemSale_R77RapidFirePistol_PrepareForSale",None)]
    if FIRST=="s12only":
        plan.append(("Trader_MrVale_CrossbowBolt_CycleRange",[pid("Trader_FeatureFlagDefinedCondition_Inverted")]))
    # 석궁 볼트: 석궁이 처음 팔리기 시작하는 시점부터 판다 (석궁보다 먼저 볼트만 팔리는 일이 없게). 원래는 사이클 40.
    if FIRST!="s12only" and crossbow_first<40:
        plan.append(("Trader_MrVale_CrossbowBolt_CycleRange",[pid("IsCycleGreaterOrEqual20" if crossbow_first>=20 else "IsCycleGreaterOrEqual10")]))
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
    if FIRST=="s12only":
        print("미스터 베일 신규 판매: 사이클 %d 부터 S12 라이엇(샷건)만 계속 판매, 석궁/석궁 볼트/R77 권총은 판매 안 함" % START)
    else:
        print("미스터 베일 신규 판매 순서: 사이클 %s (R77 권총 없음) / 석궁 볼트는 사이클 %s 부터" % (sched, ("판매 안 함" if FIRST=="s12only" else "40(원래)") if crossbow_first>=40 else ("20" if crossbow_first>=20 else "10")))
r=EndianBinaryReader(bytes(raw)); r.flags=flags; bundle.files[name]=r
open(OUT,"wb").write(bundle.save(packer="lz4"))
