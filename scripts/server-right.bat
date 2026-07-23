@echo off
rem Run this machine as the server, with the client positioned to its RIGHT
rem (i.e. this machine's RIGHT edge borders the client).
rem Extra args are forwarded, e.g.: server-right.bat --password secret
set DIR=%~dp0..\
"%DIR%deskflop.bat" server --edge right %*
