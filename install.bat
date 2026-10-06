@echo off
title Terminal-RPG setup
cd /d "%~dp0"
echo.
echo  Checking for Python...
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -c "import sys; print('  Found Python', sys.version.split()[0]); sys.exit(sys.version_info < (3, 8))" || goto old
    goto ok
)
python -c "import sys; print('  Found Python', sys.version.split()[0]); sys.exit(sys.version_info < (3, 8))" 2>nul || goto missing
goto ok
:old
echo  Your Python is older than 3.8 - please update it from https://www.python.org/downloads/
goto end
:missing
echo  Python was not found. Install Python 3.8+ from https://www.python.org/downloads/
echo  and tick "Add python.exe to PATH" during setup, then run this again.
goto end
:ok
echo.
echo  All set! Terminal-RPG has no extra packages to install.
echo  Double-click play.bat to start your adventure.
:end
echo.
pause
