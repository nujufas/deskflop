@echo off
rem Run this machine as the server, with the client positioned to its LEFT
rem (i.e. this machine's LEFT edge borders the client).
rem Extra args are forwarded, e.g.: server-left.bat --password secret
set DIR=%~dp0..\
"%DIR%deskflop.bat" server --edge left %*
