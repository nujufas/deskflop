@echo off
rem Run this machine as the client, with the server positioned to its LEFT
rem (i.e. this machine's RIGHT edge borders the server -- pair with
rem server-left.bat on the other machine).
rem Requires --host; extra args are forwarded, e.g.:
rem   client-right.bat --host 192.168.1.10 --password secret
set DIR=%~dp0..\
"%DIR%deskflop.bat" client --edge right %*
