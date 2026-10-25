@echo off
REM Wrapper: stop the locally fine-tuned model agent.
REM Keep this file ASCII-only: the Chinese messages live in tools\agent\stop-agent.ps1.
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\agent\stop-agent.ps1" %*
echo.
pause
