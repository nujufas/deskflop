@echo off
rem Run this machine as the client, with the server positioned to its RIGHT
rem (i.e. this machine's LEFT edge borders the server -- pair with
rem server-right.bat on the other machine).
rem Requires --host; extra args are forwarded, e.g.:
rem   client-left.bat --host 192.168.1.10 --password secret
set DIR=%~dp0..\
"%DIR%deskflop.bat" client --edge left %*
