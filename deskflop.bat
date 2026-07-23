@echo off
setlocal
rem Usage:
rem   deskflop.bat server [--port 24800] [--edge left^|right] [--password SECRET]
rem   deskflop.bat client --host <server-ip> [--port 24800] [--password SECRET]

set DIR=%~dp0
set PYTHON=python

where python3 >nul 2>nul
if %ERRORLEVEL%==0 set PYTHON=python3

"%PYTHON%" "%DIR%deskflop.py" %*
