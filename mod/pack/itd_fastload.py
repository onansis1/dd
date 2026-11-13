"""UnityPy 로드 속도 개선 (읽기 전용 변경: 파일 내용은 바뀌지 않는다).
UnityPy 는 번들을 열 때마다 AssetBundle 오브젝트(에셋 경로 목록, data_config 는 항목이 약 1만 6천 개)를 통째로 파싱해 container 를 만든다. 이 도구의 단계들은
container 를 쓰지 않는데도 단계마다(약 15번) 10초 안팎을 여기에 쓰고 있었다. 여기서는 그 파싱만 건너뛴다. 다른 오브젝트의 읽기/쓰기에는 영향이 없다.
사용: 하위 스크립트를 실행하기 전에 apply() 를 한 번 부른다 (exe_main 의 --run-script, 개발 모드의 itd_fastload.py <script> <args...>).
"""
import os, runpy, sys


def apply():
    import UnityPy.files.SerializedFile, UnityPy.files.ObjectReader  # noqa  (모듈과 같은 이름의 클래스가 패키지에 다시 내보내져 있으므로 sys.modules 에서 모듈을 꺼낸다)
    SF = sys.modules["UnityPy.files.SerializedFile"]
    OR = sys.modules["UnityPy.files.ObjectReader"]
    from UnityPy.enums import ClassIDType
    if getattr(SF, "_itd_fastload", False):
        return
    orig = OR.ObjectReader.parse_as_object

    def parse_as_object(self, *a, **k):
        if self.type == ClassIDType.AssetBundle:
            return None                      # container 용 AssetBundle 파싱 생략
        return orig(self, *a, **k)
    OR.ObjectReader.parse_as_object = parse_as_object
    CH = SF.ContainerHelper
    SF.ContainerHelper = lambda ab: CH([]) if ab is None else CH(ab)
    SF._itd_fastload = True


if __name__ == "__main__":
    # 개발 모드(스크립트 직접 실행): python itd_fastload.py <script.py> <args...>
    script = sys.argv[1]
    sys.argv = sys.argv[1:]
    sys.path.insert(0, os.path.dirname(os.path.abspath(script)))
    apply()
    runpy.run_path(script, run_name="__main__")
