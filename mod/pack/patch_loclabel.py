"""지도 패널의 '종합' 탭 라벨을 '추천'으로 보이게 한다 (로컬라이제이션 번들 loc.korean 수정).
사용: python patch_loclabel.py <작업 폴더>   (작업 폴더 안의 loc.korean 을 제자리에서 고친다. 원본은 호출하는 쪽이 백업해 둔다)
 - 게임에 한국어 값이 '추천'인 번역 키가 없어서, 탭이 쓰는 키 LABEL_BENCHMARK_RECOMMENDED(그래픽 벤치마크 화면의 '권장')의 값을 '추천'으로 바꾼다.
   '권장' -> '추천' 은 UTF-8 로 같은 바이트 수라 번들 구조는 그대로이고, 영어(Recommended)는 건드리지 않는다.
 - patch_lootnote.py 의 검증된 번들 편집 함수를 쓰고, 쓴 뒤 다시 읽어서 의도한 키만 바뀌었는지 확인한다.
"""
import os, sys
HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import patch_lootnote as L

KEY, OLD, NEW = "LABEL_BENCHMARK_RECOMMENDED", "권장", "추천"

def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    pth = os.path.join(sys.argv[1], "loc.korean")
    if not os.path.isfile(pth):
        sys.exit("loc.korean 을 찾을 수 없습니다: %s" % pth)
    data = open(pth, "rb").read()
    _, strs = L.unityfs_objects(data)
    if not strs:
        sys.exit("loc.korean 에서 문자열 표를 읽지 못했습니다 (게임 버전이 달라졌을 수 있습니다).")
    cur = strs.get(KEY)
    if cur == NEW:
        print("탭 라벨 문구: 이미 '추천' 입니다.")
        return
    if cur != OLD:
        sys.exit("중단: %s 의 값이 예상('%s')과 다릅니다(%r). 게임 버전이 달라졌을 수 있습니다. 아무것도 바꾸지 않았습니다." % (KEY, OLD, cur))
    new, changed = L.edit_bundle(data, {KEY: NEW})
    assert changed == 1, changed
    _, back = L.unityfs_objects(new)
    want = dict(strs); want[KEY] = NEW
    if back != want:
        sys.exit("중단: loc.korean 편집 결과 검증에 실패했습니다. 아무것도 바꾸지 않았습니다.")
    tmp = pth + ".new"
    open(tmp, "wb").write(new)
    os.replace(tmp, pth)
    print("지도 패널 탭 라벨 문구: '권장' -> '추천' (loc.korean, 검증 완료).")

if __name__ == "__main__":
    main()
