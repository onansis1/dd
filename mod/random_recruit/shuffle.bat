@echo off
rem Close the game before running this. Edit AB below if your install path differs.
set "AB=C:\Program Files (x86)\Steam\steamapps\common\Into the Dead Our Darkest Days\IntoTheDeadOurDarkestDays_Data\StreamingAssets\AssetBundles"

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY goto nopython

%PY% -c "import UnityPy" >nul 2>&1
if errorlevel 1 (
  echo Installing UnityPy, please wait...
  %PY% -m pip install UnityPy
)

%PY% "%~dp0shuffle_recruits.py" "%AB%" %1
goto end

:nopython
echo Python 3 was not found. Install it from https://www.python.org and check "Add Python to PATH".

:end
echo.
pause
