@echo off
setlocal
rem Usage:
rem   deskflop.bat server [--port 24800] [--edge left^|right] [--password SECRET]
rem   deskflop.bat client --host <server-ip> [--port 24800] [--password SECRET]
rem
rem Creates/reuses a local .venv next to this script and installs
rem requirements.txt into it automatically -- no manual setup needed.

set DIR=%~dp0
set VENV_DIR=%DIR%.venv
set PYTHON=python

where python3 >nul 2>nul
if %ERRORLEVEL%==0 set PYTHON=python3

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [deskflop] setting up virtual environment ^(first run only^)...
    "%PYTHON%" -m venv "%VENV_DIR%"
)

set VENV_PYTHON=%VENV_DIR%\Scripts\python.exe
set STAMP=%VENV_DIR%\.deps-installed

if not exist "%STAMP%" (
    echo [deskflop] installing dependencies ^(first run only^)...
    "%VENV_PYTHON%" -m pip install --quiet --upgrade pip
    "%VENV_PYTHON%" -m pip install --quiet -r "%DIR%requirements.txt"
    type nul > "%STAMP%"
)

set PYTHONUNBUFFERED=1
"%VENV_PYTHON%" "%DIR%deskflop.py" %*
