#requires -Version 5.1
<#
  打「一键启动分发包」：只挑运行需要的东西进 dist\，收件人双击「启动.bat」即可，不需要 Java / Node / MySQL。

  用法（在仓库根目录执行）：
    .\tools\launcher\make-package.ps1                生成 dist\PowerTrain-1.0.0\
    .\tools\launcher\make-package.ps1 -Zip           再打成 dist\PowerTrain-1.0.0.zip
    .\tools\launcher\make-package.ps1 -WithImages    连 Docker 镜像一起导出（完全离线可用，约 2 GB）

  .env 永远不进包（里面有数据库密码、令牌密钥、大模型 key）：脚本会主动排除，并在发现漏网时中止。
#>
[CmdletBinding()]
param(
    [string]$Version = '1.0.0',
    [switch]$Zip,
    [switch]$WithImages
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$Root  = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Name  = "PowerTrain-$Version"
$Dist  = Join-Path $Root 'dist'
$Stage = Join-Path $Dist $Name

function Say  ($m) { Write-Host $m }
function Step ($m) { Write-Host ''; Write-Host "== $m" -ForegroundColor Cyan }
function Ok   ($m) { Write-Host "   [OK]   $m" -ForegroundColor Green }
function Warn ($m) { Write-Host "   [注意] $m" -ForegroundColor Yellow }
function Die  ($m) { Write-Host ''; Write-Host "打包中止：$m" -ForegroundColor Red; exit 1 }

Set-Location $Root

Write-Host ''
Write-Host '============================================================' -ForegroundColor White
Write-Host "  制作一键启动分发包  ·  $Name" -ForegroundColor White
Write-Host '============================================================' -ForegroundColor White

# ---------------------------------------------------------------- 1 暂存目录
Step '1/4 准备暂存目录'

# 只删 dist 下面的这个子目录：先算绝对路径并确认它确实在 dist 里面，避免手滑删到别处
$distFull  = [System.IO.Path]::GetFullPath($Dist)
$stageFull = [System.IO.Path]::GetFullPath($Stage)
if (-not $stageFull.StartsWith($distFull + [System.IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    Die "暂存目录不在 dist 下，拒绝删除：$stageFull"
}
if (Test-Path $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
New-Item -ItemType Directory -Path $Stage -Force | Out-Null
Ok "暂存目录 $Stage"

# ---------------------------------------------------------------- 2 复制文件
Step '2/4 复制运行需要的文件'

$files = @('启动.bat', '停止.bat', 'docker-compose.yml', 'README.md', '使用说明.txt', '.env.example', '策划书.md')
foreach ($f in $files) {
    if (-not (Test-Path $f)) { Die "缺少 $f，仓库不完整，先确认在仓库根目录执行。" }
    Copy-Item -LiteralPath $f -Destination $Stage -Force
    Ok "文件 $f"
}

# 排除项：构建产物、依赖、开发机私有状态、密钥。
# /XD 只写目录名，robocopy 会在任意层级排除同名目录（frontend\node_modules、backend\target、deliverables\build …）。
$dirs = @('db\init', 'tools\launcher', 'backend', 'frontend', 'docs', 'deliverables')
$xd = @('target', 'node_modules', 'dist', '.git', '.idea', '.vscode', 'build', '.github', 'tmp')
$xf = @('.env', '*.log', '*.tar')

foreach ($d in $dirs) {
    if (-not (Test-Path $d)) { Die "缺少目录 $d，仓库不完整。" }
    $rcArgs = @($d, (Join-Path $Stage $d), '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/R:1', '/W:1')
    $rcArgs += '/XD'; $rcArgs += $xd
    $rcArgs += '/XF'; $rcArgs += $xf
    & robocopy @rcArgs | Out-Null
    # robocopy 退出码 >= 8 才算失败（0=没变化，1=有复制，2/4/8 都可能是正常情况）
    if ($LASTEXITCODE -ge 8) { Die "复制 $d 失败（robocopy 退出码 $LASTEXITCODE）。" }
    Ok "目录 $d"
}

# ---------------------------------------------------------------- 3 镜像
Step '3/4 Docker 镜像'

if ($WithImages) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Die '没找到 docker 命令，无法导出镜像。' }
    Say '正在构建镜像（已有构建缓存时很快）…'
    docker compose build
    if ($LASTEXITCODE -ne 0) { Die 'docker compose build 失败，请先修好本机构建再打包。' }

    $imgDir = Join-Path $Stage 'images'
    New-Item -ItemType Directory -Path $imgDir -Force | Out-Null
    $tar = Join-Path $imgDir 'powertrain-images.tar'
    # 镜像名从 compose 里读，不在这里再抄一遍：抄了就会和 docker-compose.yml 漂移
    $images = @(docker compose config --images | Where-Object { $_ })
    if ($images.Count -eq 0) { Die '没能从 docker-compose.yml 读出镜像名。' }
    Say "正在导出镜像（约 1.8 GB，几分钟）：$($images -join ' / ')"
    $saveArgs = @('save', '-o', $tar) + $images
    & docker @saveArgs
    if ($LASTEXITCODE -ne 0) { Die 'docker save 失败（磁盘空间不够？）。' }
    Ok "已导出 images\powertrain-images.tar（$([math]::Round((Get-Item $tar).Length / 1GB, 2)) GB）"
} else {
    Warn '未导出镜像：收件人首次启动需要联网拉基础镜像并构建（约 5-15 分钟）。'
    Say  '   要让对方完全离线可用，加 -WithImages 重新打包。'
}

# ---------------------------------------------------------------- 4 校验与打包
Step '4/4 校验与打包'

$leak = @(Get-ChildItem $Stage -Recurse -Force -Filter '.env' -ErrorAction SilentlyContinue)
if ($leak.Count -gt 0) { Die "包里出现了 .env（含数据库密码与密钥），已中止：$($leak.FullName -join '; ')" }
Ok '确认包内没有 .env，密钥不会外流'

$sizeMB = [math]::Round(((Get-ChildItem $Stage -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
Ok "解压后 $sizeMB MB"

if ($Zip) {
    $zipPath = Join-Path $Dist "$Name.zip"
    if (Test-Path $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
    Say '正在压缩…'
    Compress-Archive -Path $Stage -DestinationPath $zipPath -CompressionLevel Optimal
    Ok "已生成 $zipPath（$([math]::Round((Get-Item $zipPath).Length / 1MB, 1)) MB）"
} else {
    Say '没有加 -Zip，只生成了文件夹（直接拷这个文件夹给对方即可）。'
}

Say ''
Write-Host '------------------------------------------------------------' -ForegroundColor White
Say  " 打包完成：$Stage"
Say  ''
Say  ' 收件人要做的事：'
Say  '   1. 装好 Docker Desktop，并等它显示绿色 Engine running'
Say  '   2. 双击 启动.bat'
Say  '   3. 把屏幕打印的「同一局域网的其他电脑」地址发给同事'
Say  ''
Write-Host '------------------------------------------------------------' -ForegroundColor White
Say ''
