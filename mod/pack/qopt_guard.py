"""'발걸음 소리 무음' 옵션 줄(data_user_settings)과 프리셋 도구가 같은 파일을 다루기 때문에 생기는 충돌을 막는 도우미.
 - has_option(path): 이 번들에 앱이 넣은 옵션 줄(키 drs.accessibility.quiet_footsteps)이 들어 있는지
 - find_clean(ab): 옵션 줄이 없는 '원본' 백업 후보를 찾는다 (앱 백업, 그 이전본, 프리셋 도구 백업 순). 옵션이 들어간 파일을 원본으로 착각하지 않기 위한 것
"""
import os, sys
HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
KEY = b"drs.accessibility.quiet_footsteps"
BUNDLE = "data_user_settings"


def has_option_bytes(raw):
    """UnityFS 바이트에서 옵션 키가 들어 있는지 (읽을 수 없으면 None)"""
    import itdp_ufs2 as U
    import tempfile
    fd, tmp = tempfile.mkstemp(prefix="itd_qopt_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        b = U.Bundle2(tmp)
        return KEY in b.node_data(b.nodes[0][3])
    except Exception:
        return None
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def has_option(path):
    """True/False, 읽을 수 없으면 None"""
    try:
        import itdp_ufs2 as U
        b = U.Bundle2(path)
        return KEY in b.node_data(b.nodes[0][3])
    except Exception:
        return None


def candidates(ab):
    bdir = os.path.join(ab, "_mods_backup")
    return [os.path.join(bdir, BUNDLE), os.path.join(bdir, BUNDLE + ".prev"), os.path.join(bdir, BUNDLE + ".orig"), os.path.join(bdir, BUNDLE + ".orig.old")]


def find_clean(ab):
    """옵션 줄이 없는 읽을 수 있는 번들 경로 (없으면 None)"""
    for p in candidates(ab):
        if os.path.isfile(p) and has_option(p) is False:
            return p
    return None
