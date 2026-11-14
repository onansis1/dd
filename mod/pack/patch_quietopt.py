"""게임 옵션(접근성)에 '발걸음 소리 무음' 토글 한 줄을 추가한다 (data_user_settings 번들 수정, 일반판 전용).
사용: python patch_quietopt.py <작업 폴더>   (작업 폴더 안의 data_user_settings 를 제자리에서 고친다. 원본은 호출하는 쪽이 백업해 둔다)
 - 접근성 옵션 목록 끝에 기본 '끔' 인 켜기/끄기 항목 1개를 더한다 (키 drs.accessibility.quiet_footsteps). 번역 문구는 patch_quietloc.py, 값을 읽어 실제로 발소리를 끄는 코드는 patch_quietfoot.py(DLL).
 - 이미 항목이 있거나 파일 구조가 예상과 다르면 아무것도 바꾸지 않고 중단한다. 쓴 뒤에는 다시 읽어 검증(itdp_optverify)하고 통과해야 파일을 바꾼다.
"""
import os, sys
HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    pth = os.path.join(sys.argv[1], "data_user_settings")
    if not os.path.isfile(pth):
        sys.exit("data_user_settings 를 찾을 수 없습니다: %s" % pth)
    import itdp_opt as O, itdp_optverify as V
    try:
        c, new_ser, info = O.plan_build(pth)
    except AssertionError as e:
        sys.exit("중단: data_user_settings 가 예상한 구조가 아니거나 이미 수정돼 있습니다 (%s). 게임 버전이 달라졌을 수 있습니다. 아무것도 바꾸지 않았습니다." % (str(e)[:160],))
    out = c.b.build(c.node, new_ser)
    tmp = pth + ".new"
    with open(tmp, "wb") as f:
        f.write(out)
    try:
        res = V.verify(pth, tmp, info)
        bad = [n for n, ok, _ in res if not ok]
    except Exception as e:
        bad = ["검증 중 오류: %r" % (e,)]
    if bad:
        os.remove(tmp)
        sys.exit("중단: data_user_settings 편집 결과 검증 실패 (%s). 아무것도 바꾸지 않았습니다." % "; ".join(b[:80] for b in bad[:3]))
    import gc; gc.collect()
    os.replace(tmp, pth)
    print("옵션 항목 추가: 접근성 '발걸음 소리 무음' (data_user_settings, 검증 %d개 통과)." % len(res))


if __name__ == "__main__":
    main()
