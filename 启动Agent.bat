@echo off
REM Wrapper: start the locally fine-tuned model agent (LLaMA-Factory api mode).
REM Keep this file ASCII-only: the Chinese messages live in tools\agent\start-agent.ps1.
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\agent\start-agent.ps1" %*
echo.
pause
