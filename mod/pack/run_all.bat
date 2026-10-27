@echo off
setlocal
rem ===== Edit AB below if your game is installed somewhere else =====
set "AB=C:\Program Files (x86)\Steam\steamapps\common\Into the Dead Our Darkest Days\IntoTheDeadOurDarkestDays_Data\StreamingAssets\AssetBundles"
rem ===================================================================

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY goto nopython

if not exist "%AB%\data_levels" goto nofolder
if not exist "%~dp0apply_all.py" goto noscript

tasklist 2>nul | find /I "IntoTheDead" >nul && goto running

echo.
echo This applies ALL mods (ammo x5, bag 24, map station 2, corpse 24, radius x1.5) and SHUFFLES the map.
echo Use it BEFORE starting a NEW game. Do NOT run it in the middle of a save you want to keep.
echo It is also the right thing to run again after every game update.
choice /C YN /M "Apply now"
if errorlevel 2 goto cancelled

echo.
%PY% "%~dp0apply_all.py" "%AB%" %*
if errorlevel 1 goto failed
goto end

:cancelled
echo Cancelled. Nothing was changed.
goto end

:running
echo The game seems to be running. Close the game and Steam, then run this again.
goto end

:nofolder
echo Could not find data_levels in the AssetBundles folder. Edit the AB line at the top of this file.
goto end

:noscript
echo apply_all.py must be in the same folder as this file.
goto end

:nopython
echo Python 3 was not found. Install it from https://www.python.org and check "Add Python to PATH".
goto end

:failed
echo Something went wrong. Read the messages above. Your game files were not changed unless a "Done" line appeared.

:end
echo.
pause
