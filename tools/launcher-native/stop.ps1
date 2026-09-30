#requires -Version 5.1
<#
  停止服务：直接转调 start.ps1 -Stop（服务与数据目录的逻辑都在那边，避免两处维护）。
  双击包根目录的 stop.bat 即可。
#>
[CmdletBinding()]
param()
& (Join-Path $PSScriptRoot 'start.ps1') -Stop