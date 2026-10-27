@echo off
chcp 65001 >nul
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY goto nopython
%PY% -X utf8 "%~dp0launcher.py"
goto end
:nopython
echo Python 3 was not found. Install it from https://www.python.org/downloads/ and CHECK "Add python.exe to PATH" in the installer.
echo Then run this file again.
pause
:end
