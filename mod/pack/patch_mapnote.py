"""Into the Dead: Our Darkest Days - [시험] 지도 화면 오른쪽 패널(장소 설명)에 '탐색 유리 특성' 문구를 서식/이미지 태그와 함께 붙여 본다 (loc.korean / loc.english 번들 수정).
사용: python patch_mapnote.py <작업 폴더>   (작업 폴더 안의 loc.korean, loc.english 를 제자리에서 고친다. 원본은 호출하는 쪽이 백업해 둔다)
 - 지도 스테이션 화면에서 '슈레더 스트리트 319번지'를 고르면 오른쪽 패널 설명문 끝에 아래가 붙는다. 한 곳(LOCATION_RESIDENTIAL_MIDDLECLASS_02_DESC)만 바꾼다.
     굵은 제목 + 노란색 한 줄(탐색에 유리한 특성 15개) + 이미지 태그 시험 줄(<img=Pip_Full/> 등)
 - 확인하려는 것: (1) 설명문 칸에서 여러 줄/굵게/색이 되는지, (2) 이미지 세트가 연결되지 않은 칸에서 <img=이름/> 태그가 그림으로 나오는지/글자로 보이는지/무시되는지, (3) 패널이 늘어나도 화면에 들어가는지.
 - 문자열 길이가 바뀌므로 patch_lootnote 의 번들 편집(오브젝트 위치 보정, 쓴 뒤 다시 읽어 검증)을 그대로 쓴다. 다른 키는 바뀌지 않는다.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "_MEIPASS", None):
    HERE = sys._MEIPASS
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import patch_lootnote as L

KEY = "LOCATION_RESIDENTIAL_MIDDLECLASS_02_DESC"
KO = ("\n\n<b>탐색 유리 특성</b>\n<c=#FFD060>은밀함 · 은밀 · 민첩 · 강한 어깨 · 체계적 · 락픽 전문가 · 열쇠고리 · 치프웨이즈 직원 · 불굴 · 터프 가이 · 회피 기질 · 튼튼함 · 동요하지 않음 · 생의 의지 · 꼼꼼한 수색꾼</c>\n"
      "이미지 태그 시험: <img=Pip_Full/><img=Pip_Empty/> <img=Night/> <img=Daytime/>")
EN = ("\n\n<b>Scavenging-friendly traits</b>\n<c=#FFD060>Sneaky · Stealthy · Agile · Strong Shoulders · Organised · Lockpick Expert · Keyring · Chiefways Employee · Fortitude · Tough · Evasive · Sturdy · Unfazed · Will to Live · Meticulous Scavenger</c>\n"
      "Image tag test: <img=Pip_Full/><img=Pip_Empty/> <img=Night/> <img=Daytime/>")

def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    stage = sys.argv[1]
    langs = [("ko", "loc.korean", KO), ("en", "loc.english", EN)]
    data, strs = {}, {}
    for lang, fn, _t in langs:
        p = os.path.join(stage, fn)
        if not os.path.isfile(p):
            sys.exit("%s 를 찾을 수 없습니다: %s" % (fn, p))
        data[lang] = open(p, "rb").read()
        _o, strs[lang] = L.unityfs_objects(data[lang])
        if not strs[lang] or KEY not in strs[lang]:
            sys.exit("중단: %s 에서 %s 를 찾지 못했습니다 (게임 버전이 달라졌을 수 있습니다). 아무것도 바꾸지 않았습니다." % (fn, KEY))
    out = {}
    for lang, fn, text in langs:
        new, changed = L.edit_bundle(data[lang], {KEY: strs[lang][KEY] + text})
        assert changed == 1, (fn, changed)
        _o, back = L.unityfs_objects(new)
        want = dict(strs[lang]); want[KEY] = strs[lang][KEY] + text
        if back != want:
            sys.exit("중단: %s 편집 결과 검증에 실패했습니다. 아무것도 바꾸지 않았습니다." % fn)
        out[fn] = new
    for fn, new in out.items():
        tmp = os.path.join(stage, fn + ".new")
        open(tmp, "wb").write(new)
        os.replace(tmp, os.path.join(stage, fn))
    print("[시험] 슈레더 스트리트 319번지 설명문에 서식/이미지 태그 시험 문구를 붙였습니다 (한국어/영어, 검증 완료).")

if __name__ == "__main__":
    main()
