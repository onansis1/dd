@echo off
setlocal
rem ===== Edit AB below if your game is installed somewhere else =====
set "AB=C:\Program Files (x86)\Steam\steamapps\common\Into the Dead Our Darkest Days\IntoTheDeadOurDarkestDays_Data\StreamingAssets\AssetBundles"
rem ===================================================================

if not exist "%AB%\data_levels.shufflebak" goto nobak
tasklist 2>nul | find /I "IntoTheDead" >nul && goto running

echo.
echo This puts the map back to the state before shuffling (your radius x1.5 stays).
choice /C YN /M "Restore the map now"
if errorlevel 2 goto cancelled

copy /Y "%AB%\data_levels.shufflebak" "%AB%\data_levels" >nul
if errorlevel 1 goto failed
echo.
echo Restored.
goto end

:cancelled
echo Cancelled. Nothing was changed.
goto end

:running
echo The game seems to be running. Close the game and Steam, then run this again.
goto end

:nobak
echo No backup found (data_levels.shufflebak). Nothing to restore.
goto end

:failed
echo Copy failed. Close the game and Steam and try again.

:end
echo.
pause
