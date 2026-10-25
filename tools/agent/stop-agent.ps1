#requires -Version 5.1
<#
  停止本地微调模型 Agent：按端口找出监听进程并结束（只动这一个进程，不碰其它 python）。

  用法（推荐双击根目录的 停止Agent.bat）：
    powershell -ExecutionPolicy Bypass -File tools\agent\stop-agent.ps1
#>
[CmdletBinding()]
param(
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

Write-Host ''
Write-Host "== 停止本地微调模型 Agent（端口 $Port）" -ForegroundColor Cyan

$pids = @()
foreach ($line in (netstat -ano | Select-String 'LISTENING')) {
    if ($line.Line -match ":$Port\s+\S+\s+LISTENING\s+(\d+)") { $pids += [int]$Matches[1] }
}

if ($pids.Count -eq 0) {
    Write-Host "   没在跑（端口 $Port 空闲）" -ForegroundColor Yellow
} else {
    foreach ($procId in ($pids | Select-Object -Unique)) {
        Write-Host "   结束进程 PID $procId"
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 500
    if ((netstat -ano | Select-String ":$Port\s+\S+\s+LISTENING")) {
        Write-Host "   端口 $Port 仍在监听，请手动检查" -ForegroundColor Red
    } else {
        Write-Host '   已停止' -ForegroundColor Green
    }
}

Write-Host ''
Write-Host '   诊断接口会自动回退成内置规则结论（界面标注「规则引擎 v1」），页面照常可用。'
Write-Host ''
