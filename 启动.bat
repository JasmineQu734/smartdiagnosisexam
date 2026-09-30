@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\launcher\start.ps1" %*
echo.
pause
