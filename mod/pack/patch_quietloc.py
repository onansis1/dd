"""'발걸음 소리 무음' 옵션 줄의 이름/설명 문구를 모든 언어 번역 번들(loc.*)에 넣는다 (일반판 전용).
사용: python patch_quietloc.py <작업 폴더>   (작업 폴더 안의 loc.* 를 제자리에서 고친다)
 - 새 번역 키를 만들지 않고 게임이 쓰지 않는 기존 두 키의 값만 바꾼다: 이름 LABEL_VITALS, 설명 LABEL_DEMO_TITLE. 한국어/영어는 지정 문구, 나머지 언어는 영어 문구(원래 값이 엉뚱한 문구라 그대로 두면 새 줄에 그게 뜬다).
 - patch_lootnote.py 의 검증된 번들 편집 함수를 쓰고, 쓴 뒤 다시 읽어 의도한 두 키만 바뀌었는지 확인한다.
"""
import glob, os, sys
HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import patch_lootnote as L

K_NAME, K_DESC = "LABEL_VITALS", "LABEL_DEMO_TITLE"
EN = ("Silent Footsteps", "When on, survivors make no footstep noise while walking or running.")
TEXT = {"loc.korean": ("발걸음 소리 무음", "켜면 생존자가 걷거나 달릴 때 발소리가 나지 않습니다."), "loc.english": EN}


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    files = sorted(p for p in glob.glob(os.path.join(sys.argv[1], "loc.*")) if not p.endswith((".new", ".tmp")))
    if not files:
        sys.exit("loc.* 를 찾을 수 없습니다: %s" % sys.argv[1])
    done = 0
    for pth in files:
        nm = os.path.basename(pth)
        want = TEXT.get(nm, EN)
        data = open(pth, "rb").read()
        _, strs = L.unityfs_objects(data)
        if not strs or K_NAME not in strs or K_DESC not in strs:
            sys.exit("중단: %s 에서 번역 키(%s/%s)를 읽지 못했습니다 (게임 버전이 달라졌을 수 있습니다). 아무것도 바꾸지 않았습니다." % (nm, K_NAME, K_DESC))
        if (strs[K_NAME], strs[K_DESC]) == want:
            continue
        new, changed = L.edit_bundle(data, {K_NAME: want[0], K_DESC: want[1]})
        _, back = L.unityfs_objects(new)
        exp = dict(strs); exp[K_NAME], exp[K_DESC] = want
        if changed != 2 or back != exp:
            sys.exit("중단: %s 편집 결과 검증에 실패했습니다. 아무것도 바꾸지 않았습니다." % nm)
        tmp = pth + ".new"
        open(tmp, "wb").write(new)
        os.replace(tmp, pth)
        done += 1
    print("옵션 문구 '발걸음 소리 무음': 번역 번들 %d개 수정 (한국어/영어 지정, 나머지 영어)." % done)


if __name__ == "__main__":
    main()
