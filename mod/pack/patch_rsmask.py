"""'무술가 포함 뽑기'의 후보 마스크 계산 (읽기 전용: 아무것도 쓰지 않고 16진수 마스크 한 줄만 출력한다).
사용: python patch_rsmask.py <data_balancing> <data_config>
 - 랜덤 시작 후보 18명(patch_randstart.py 후보표 순서) 중 다음에 해당하는 생존자의 비트를 켠다 (비트 i = 후보 i):
   (a) 시작 특성에 Trait+MartialArtist  (b) 시작 특성에 Trait+ProfessionalWrestler  (c) 스킬 트리 4티어(선택지 둘 중 하나)에 Trait+HandToHandExpert
 - 앱이 특성 섞기/맨손격투 보정까지 모두 적용한 data_balancing 으로 계산하므로, 섞은 결과의 보유자가 후보가 된다.
 - 출력 마지막 줄: 'MASK <5자리 16진수>'. 읽지 못하면 'MASK 00000'(= 새 버튼도 일반 랜덤과 같음)과 이유를 출력한다.
"""
import re, sys
CANDS = [("Cooper", "82337d2c8974352cd8d06591cc51a066"), ("Isaiah", "a22f941783815a93893969457239a80c"), ("Charlie", "c1d1a2c8bebdbf2c66a7bc190a9f587a"),
         ("Hao", "81bf9c6e419efd226658e79e6feba745"), ("Kayla", "fd3d73e1705564575bc290f167ba6127"), ("Mei", "b0fa8cc2fd756664eaf460a5486d3ad9"),
         ("Daphne", "92f95004d5cd545ceff34de1beb17dba"), ("Dianne", "9009741c2f52d4f67c3b44ceba0c4ca9"), ("Hector", "5af15ed5ce0822d93ab498278dbf1ffa"),
         ("Tracy", "592b54ee6c3955f45d003ce69c0d973c"), ("Otto", "cd9eb970912466300b45ab94aee8115b"), ("Leo", "792422e9862224ff3b780bd9b8cb9395"),
         ("Sebastian", "898e061e9d2165c50b05a3cfeb968161"), ("Taylor", "e7bc45fff9465a2fa297a5b41cb3552b"), ("Wayne", "e72e95db55eab0eee2d1e394c74b250e"),
         ("Eva", "62921bb0081574f73758bc6ed584185a"), ("Penny", "a9768b67619548f91a54d201b8da2a8d"), ("Darrel", "27ac7f7378f9c84ba9ec99ac032992b3")]
START_TRAITS = ("Trait+MartialArtist", "Trait+ProfessionalWrestler")
TIER4_TRAITS = ("Trait+HandToHandExpert",)
TIER = 4


def compute(bal_path, cfg_path):
    import UnityPy.helpers.TypeTreeNode as T
    import UnityPy.helpers.TypeTreeHelper as H
    _o = T.TypeTreeNode.parse_blob.__func__
    T.TypeTreeNode.parse_blob = classmethod(lambda c, r, v: (setattr(r, "Position", r.Position + 28), _o(c, r, v))[1])
    H.read_typetree_boost = None
    import UnityPy

    def g(x):
        while isinstance(x, dict) and "m_guid" in x:
            x = x["m_guid"]
        return bytes(x["bytes[%d]" % i] for i in range(16))
    guids = [bytes.fromhex(h) for _n, h in CANDS]
    cfg = UnityPy.load(cfg_path)
    pid_name, guid_name = {}, {}
    for o in cfg.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            t = o.read_typetree()
        except Exception:
            continue
        n = t.get("m_Name") or ""
        if n in START_TRAITS + TIER4_TRAITS and "m_guid" in t:
            pid_name[o.path_id] = n
            guid_name[g(t["m_guid"])] = n
    if len(pid_name) != len(START_TRAITS) + len(TIER4_TRAITS):
        raise RuntimeError("특성 정의를 찾지 못했습니다: %s" % sorted(pid_name.values()))
    bal = UnityPy.load(bal_path)
    objs = {o.path_id: o for o in bal.objects}
    why = {}
    for o in bal.objects:
        if o.type.name != "MonoBehaviour":
            continue
        try:
            t = o.read_typetree()
        except Exception:
            continue
        n = t.get("m_Name") or ""
        if not re.fullmatch(r"Survivor_\w+", n) or "m_skillTreeData" not in t or "m_guid" not in t:
            continue
        sg = g(t["m_guid"])
        if sg not in guids:
            continue
        i = guids.index(sg)
        r = []
        for x in t["m_startingTraits"]:
            if pid_name.get(x["m_PathID"]) in START_TRAITS:
                r.append("start:" + pid_name[x["m_PathID"]])
        lv = objs[t["m_skillTreeData"]["m_PathID"]].read_typetree()["m_skillTreeLevels"]
        if len(lv) >= TIER:
            for ch in ("m_firstChoice", "m_secondChoice"):
                nm = guid_name.get(g(lv[TIER - 1][ch]))
                if nm in TIER4_TRAITS:
                    r.append("tier%d:%s" % (TIER, nm))
        if r:
            why[i] = r
    return sum(1 << i for i in why), why


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    try:
        mask, why = compute(sys.argv[1], sys.argv[2])
    except Exception as e:  # noqa: BLE001
        print("무술가 후보를 계산하지 못했습니다(%r). 새 버튼은 일반 랜덤 시작과 같게 동작합니다." % (e,))
        print("MASK 00000")
        return
    names = [n for n, _h in CANDS]
    print("무술가 후보(랜덤 시작 후보 18명 중): " + (", ".join(names[i] for i in sorted(why)) if why else "없음 (새 버튼은 일반 랜덤과 같음)"))
    print("MASK %05X" % mask)


if __name__ == "__main__":
    main()
