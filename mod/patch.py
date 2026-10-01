import UnityPy.helpers.TypeTreeNode as T
_orig=T.TypeTreeNode.parse_blob.__func__
def _pb(cls,reader,version):
    p=reader.Position
    reader.Position=p+28
    return _orig(cls,reader,version)
T.TypeTreeNode.parse_blob=classmethod(_pb)
import UnityPy
P="/root/.claude/uploads/fe2a6e89-3196-5bb4-9001-dc8e5c151021/e712bc87-data_balancing"
