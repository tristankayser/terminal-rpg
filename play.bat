@echo off
title Terminal-RPG
cd /d "%~dp0"
rem Prefer the official "py" launcher, then python on PATH
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 main.py
    goto end
)
python --version >nul 2>nul
if %errorlevel%==0 (
    python main.py
    goto end
)
echo.
echo  Python 3.8 or newer is needed to play Terminal-RPG.
echo  Download it from https://www.python.org/downloads/
echo  and tick "Add python.exe to PATH" during setup.
echo.
:end
pause
