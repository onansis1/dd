@echo off
setlocal
rem ===== Edit AB below if your game is installed somewhere else =====
set "AB=C:\Program Files (x86)\Steam\steamapps\common\Into the Dead Our Darkest Days\IntoTheDeadOurDarkestDays_Data\StreamingAssets\AssetBundles"
rem ===================================================================

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY goto nopython

if not exist "%AB%\_mods_backup\manifest.json" goto nobak
tasklist 2>nul | find /I "IntoTheDead" >nul && goto running

echo.
echo This puts ALL game files back to the original (no mods at all).
choice /C YN /M "Restore the originals now"
if errorlevel 2 goto cancelled

%PY% "%~dp0apply_all.py" "%AB%" --restore
if errorlevel 1 goto failed
goto end

:cancelled
echo Cancelled. Nothing was changed.
goto end

:running
echo The game seems to be running. Close the game and Steam, then run this again.
goto end

:nobak
echo No backup found (_mods_backup). Nothing to restore.
goto end

:nopython
echo Python 3 was not found. Install it from https://www.python.org and check "Add Python to PATH".
goto end

:failed
echo Something went wrong. Close the game and Steam and try again.

:end
echo.
pause
