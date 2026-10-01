@echo off
chcp 65001 >nul
rem 게임을 끈 상태에서 실행하세요. 아래 경로가 다르면 수정하세요.
set "AB=C:\Program Files (x86)\Steam\steamapps\common\Into the Dead Our Darkest Days\IntoTheDeadOurDarkestDays_Data\StreamingAssets\AssetBundles"
python --version >nul 2>&1 || (echo Python 3 이 필요합니다. https://www.python.org 에서 설치하세요. & pause & exit /b 1)
python -c "import UnityPy" >nul 2>&1 || python -m pip install UnityPy
python "%~dp0shuffle_recruits.py" "%AB%" %1
pause
