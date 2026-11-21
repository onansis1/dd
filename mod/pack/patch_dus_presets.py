"""data_user_settings: 프리셋 도구로 설정한 시나리오 프리셋 칸(쉬움/보통/어려움)을 새로 만든 작업 파일에 다시 얹는다.
사용: python patch_dus_presets.py <작업 폴더> <AssetBundles 폴더>
 - apply_all 이 옵션 줄('발걸음 소리 무음')을 원본 백업에서 다시 계산할 때, 설치된 파일에 들어 있던 프리셋 값이 사라지지 않게 한다.
   설치된 파일의 세 칸 값(preset_tool.current_slot_values)을 읽어 작업 파일에 같은 값으로 써 넣는다(preset_tool.patch_bundle).
 - 프리셋 도구의 상태 파일(_mods_backup/data_user_settings.state.json)과 원본 백업(.orig)도 맞춰, 다음에 프리셋 도구를 써도 우리 결과를 '게임 업데이트'로 착각하지 않게 한다.
"""
import hashlib, json, os, shutil, sys
HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    stage, ab = sys.argv[1], sys.argv[2]
    sp = os.path.join(stage, "data_user_settings")
    if not os.path.isfile(sp):
        sys.exit("작업 폴더에 data_user_settings 가 없습니다: " + sp)
    import preset_tool as P
    try:
        values = P.current_slot_values(ab)
        data = open(sp, "rb").read()
        new, report = P.patch_bundle(data, values)
    except Exception as e:
        sys.exit("중단: 프리셋 칸을 다시 적용하지 못했습니다 (%r). 아무것도 바꾸지 않았습니다." % (e,))
    tmp = sp + ".new"
    with open(tmp, "wb") as f:
        f.write(new)
    os.replace(tmp, sp)
    cur_p, orig_p, st_p = P._paths(ab)
    bak = os.path.join(ab, "_mods_backup", "data_user_settings")        # 앱 백업(옵션 줄 없는 원본)
    try:
        if os.path.isfile(bak):
            if os.path.isfile(orig_p) and open(orig_p, "rb").read() != open(bak, "rb").read():
                shutil.copy2(orig_p, orig_p + ".old")
            shutil.copy2(bak, orig_p)
            json.dump({"out": hashlib.sha256(new).hexdigest(), "orig": hashlib.sha256(open(bak, "rb").read()).hexdigest()}, open(st_p, "w", encoding="utf-8"))
    except OSError:
        pass
    print("프리셋 칸 유지: 쉬움/보통/어려움 칸의 값을 새 파일에 다시 적용했습니다.")


if __name__ == "__main__":
    main()
