#requires -Version 5.1
<#
  打「Windows 免安装一键部署包」：产出 dist\PowerTrain-Win-<版本>\（可选 zip）。
  收件人解压后双击 start.bat 即可，不需要 Docker、不需要装 Java / Node / MySQL、不需要联网。

  包里的东西：
    app\backend.jar     预构建后端（含全部依赖）
    app\webapp\         预构建前端静态文件（无路由单页，直接由后端托管，不需要 nginx）
    app\db-init\        建库建表脚本
    runtime\jre\        jlink 裁出来的精简 JRE
    runtime\mysql\      绿色版 MySQL（mysqld / mysql / mysqladmin + 运行必需的 dll / share / plugins）
    tools\              启动与停止脚本
    start.bat stop.bat  双击入口
    .env                随包预置一份（随机数据库口令 + 随机令牌密钥；AI_API_KEY 留空，由收件人填）

  用法（在仓库根目录执行）：
    .\tools\launcher-native\make-package.ps1
    .\tools\launcher-native\make-package.ps1 -Zip
    .\tools\launcher-native\make-package.ps1 -MySqlHome "D:\MySQL"   绿色版 MySQL 的来源目录
    .\tools\launcher-native\make-package.ps1 -SkipWebBuild           前端已构建过，跳过 npm run build
#>
[CmdletBinding()]
param(
    [string]$Version = '1.0.0',
    [switch]$Zip,
    [string]$MySqlHome = 'D:\MySQL',
    [switch]$SkipWebBuild,
    [string]$JdkHome = ''
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$Root  = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Name  = "PowerTrain-Win-$Version"
$Dist  = Join-Path $Root 'dist'
$Stage = Join-Path $Dist $Name

function Say  ($m) { Write-Host $m }
function Step ($m) { Write-Host ''; Write-Host "== $m" -ForegroundColor Cyan }
function Ok   ($m) { Write-Host "   [OK]   $m" -ForegroundColor Green }
function Warn ($m) { Write-Host "   [注意] $m" -ForegroundColor Yellow }
function Die  ($m) { Write-Host ''; Write-Host "打包中止：$m" -ForegroundColor Red; exit 1 }

# PS 5.1 在 ErrorActionPreference=Stop 下有个坑：只要原生命令的 stderr 被并进管道
# （例如维护者用 "make-package.ps1 *>&1 | Tee-Object 日志"），npm / jlink / mysqld 往
# stderr 写的普通提示就会被当成终止错误，整个打包莫名其妙地中断。所有外部命令走这层包装。
# 返回对象而不是裸退出码：直接 return $code 会把命令自己的 stdout 一并返回，
# 调用方拿到的是数组，"-ne 0" 变成了过滤，判断必然错。
function Invoke-Native([string]$exe, [string[]]$arguments) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $out = @(& $exe @arguments 2>&1); $code = $LASTEXITCODE }
    finally { $ErrorActionPreference = $old }
    return [pscustomobject]@{ Code = $code; Out = @($out | ForEach-Object { $_.ToString() }) }
}

function Get-NativeOutput([string]$exe, [string[]]$arguments) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $out = @(& $exe @arguments 2>&1) }
    finally { $ErrorActionPreference = $old }
    return @($out | ForEach-Object { $_.ToString() })
}

Set-Location $Root

Write-Host ''
Write-Host '============================================================' -ForegroundColor White
Write-Host "  制作 Windows 免安装部署包  ·  $Name" -ForegroundColor White
Write-Host '============================================================' -ForegroundColor White

# ---------------------------------------------------------------- 0 前置检查
Step '0/8 前置检查'

# 每次重打都从干净目录开始：否则上一次演练留下的 data\（含已初始化的数据库和 .env）
# 会混进包里。只删 dist 下这一个子目录，且先确认绝对路径确实在 dist 里面。
$distFull  = [System.IO.Path]::GetFullPath($Dist)
$stageFull = [System.IO.Path]::GetFullPath($Stage)
if (-not $stageFull.StartsWith($distFull + [System.IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    Die "暂存目录不在 dist 下，拒绝删除：$stageFull"
}
if (Test-Path $Stage) {
    Say "   清理上一次的 $Name …"
    Remove-Item -LiteralPath $Stage -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path $Stage) { Die "清不掉 $Stage：可能还有进程占着里面的文件，先运行包里的 stop.bat 再重打。" }
}

if (-not (Test-Path 'frontend\package.json')) { Die '不在仓库根目录执行，或仓库不完整。' }
if (-not (Test-Path (Join-Path $MySqlHome 'bin\mysqld.exe'))) { Die "在 $MySqlHome 找不到 bin\mysqld.exe，用 -MySqlHome 指定绿色版 MySQL 目录。" }

if (-not $JdkHome) {
    if ($env:JAVA_HOME -and (Test-Path (Join-Path $env:JAVA_HOME 'bin\jlink.exe'))) { $JdkHome = $env:JAVA_HOME }
    else {
        $j = Get-Command jlink -ErrorAction SilentlyContinue
        if ($j) { $JdkHome = Split-Path -Parent (Split-Path -Parent $j.Source) }
    }
}
if (-not $JdkHome -or -not (Test-Path (Join-Path $JdkHome 'bin\jlink.exe'))) { Die '找不到带 jlink 的 JDK，用 -JdkHome 指定（JDK 17 或更高，且要有 jmods 目录）。' }
if (-not (Test-Path (Join-Path $JdkHome 'jmods'))) { Die "$JdkHome 下没有 jmods 目录，jlink 需要完整 JDK（不是 JRE）。" }
Ok "JDK：$JdkHome"

$mysqlVer = ((Get-NativeOutput (Join-Path $MySqlHome 'bin\mysqld.exe') @('--version')) -join ' ').Trim()
Ok "MySQL：$mysqlVer"
if ($mysqlVer -notmatch 'Ver 8\.') { Warn '官方口径是 MySQL 8；当前不是 8.x。建库脚本只用到 8.0 起的语法，能跑，但交付前建议换成 8.4 LTS 的绿色版。' }

# ---------------------------------------------------------------- 1 前端构建
Step '1/8 构建前端'

$webSrc = Join-Path $Root 'frontend\dist'
if ($SkipWebBuild) {
    if (-not (Test-Path (Join-Path $webSrc 'index.html'))) { Die '-SkipWebBuild 但 frontend\dist 里没有 index.html。' }
    Ok '按 -SkipWebBuild 跳过构建，复用现有 frontend\dist'
} else {
    if (-not (Test-Path 'frontend\node_modules')) {
        Say '   第一次构建需要装前端依赖（走 npm 配置的镜像）…'
        Push-Location 'frontend'
        try {
            $r = Invoke-Native 'npm.cmd' @('install')
            if ($r.Code -ne 0) { Say ($r.Out -join [Environment]::NewLine); Die 'npm install 失败。' }
        } finally { Pop-Location }
    }
    Say '   正在构建前端（vite build）…'
    Push-Location 'frontend'
    try {
        $r = Invoke-Native 'npm.cmd' @('run', 'build')
        if ($r.Code -ne 0) { Say ($r.Out -join [Environment]::NewLine); Die 'npm run build 失败。' }
        $built = @($r.Out | Where-Object { $_ -match 'built in' })
        if ($built.Count -gt 0) { Say ('   ' + $built[0]) }
    } finally { Pop-Location }
    if (-not (Test-Path (Join-Path $webSrc 'index.html'))) { Die '构建完仍没有 frontend\dist\index.html。' }
    Ok '前端已构建'
}

# ---------------------------------------------------------------- 2 后端 jar
Step '2/8 准备后端 jar'

$jar = Get-ChildItem (Join-Path $Root 'backend\target') -Filter '*.jar' -ErrorAction SilentlyContinue |
       Where-Object { $_.Name -notlike '*sources*' -and $_.Name -notlike '*plain*' } |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $jar) { Die 'backend\target 下没有 jar。先构建后端（backend 下 mvn -DskipTests package，或用 docker compose build backend）。' }

$newestSrc = Get-ChildItem (Join-Path $Root 'backend\src') -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($newestSrc -and $newestSrc.LastWriteTime -gt $jar.LastWriteTime) {
    Warn "jar 比源码旧（源码最新改动 $($newestSrc.LastWriteTime)，jar 构建于 $($jar.LastWriteTime)）"
    Say  '   先重新构建后端再打包，否则包里是旧代码。'
    Die 'jar 已过期'
}
Ok "后端 jar：$($jar.Name)  $([math]::Round($jar.Length / 1MB, 1)) MB"

# ---------------------------------------------------------------- 3 精简 JRE
Step '3/8 生成精简 JRE（jlink）'

$jreOut = Join-Path $Stage 'runtime\jre'
New-Item -ItemType Directory -Path (Split-Path -Parent $jreOut) -Force | Out-Null
# 模块按实际用到的能力挑：Spring Boot/Tomcat（base/logging/naming/management/instrument）、
# JDBC(java.sql)、PDFBox 与 POI 出文档要 java.desktop 与 java.xml、HTTPS 调大模型要 jdk.crypto.ec、
# 若干库依赖 sun.misc.Unsafe 所以要 jdk.unsupported。
$modules = 'java.base,java.logging,java.naming,java.management,java.instrument,java.sql,java.desktop,java.xml,java.net.http,java.security.jgss,java.security.sasl,java.transaction.xa,jdk.crypto.ec,jdk.crypto.cryptoki,jdk.unsupported,jdk.zipfs,jdk.management'
if (Test-Path $jreOut) { Remove-Item -LiteralPath $jreOut -Recurse -Force }
$jlinkArgs = @('--add-modules', $modules, '--output', $jreOut, '--strip-debug', '--no-header-files', '--no-man-pages', '--compress=2')
$r = Invoke-Native (Join-Path $JdkHome 'bin\jlink.exe') $jlinkArgs
if ($r.Code -ne 0) { Say ($r.Out -join [Environment]::NewLine); Die 'jlink 失败。' }
$jreMB = [math]::Round(((Get-ChildItem $jreOut -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
Ok "精简 JRE：$jreMB MB"

# ---------------------------------------------------------------- 4 绿色版 MySQL
Step '4/8 复制绿色版 MySQL'

$myDst = Join-Path $Stage 'runtime\mysql'
New-Item -ItemType Directory -Path (Join-Path $myDst 'bin') -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $MySqlHome 'bin\mysqld.exe')     -Destination (Join-Path $myDst 'bin') -Force
Copy-Item -LiteralPath (Join-Path $MySqlHome 'bin\mysql.exe')      -Destination (Join-Path $myDst 'bin') -Force
Copy-Item -LiteralPath (Join-Path $MySqlHome 'bin\mysqladmin.exe') -Destination (Join-Path $myDst 'bin') -Force
# bin 里的 dll 是 mysqld 的运行时依赖，全带上；但调试版 dll 与 .lib 是开发产物，占地方又用不到
$dlls = @(Get-ChildItem (Join-Path $MySqlHome 'bin') -Filter '*.dll' -File |
          Where-Object { $_.Name -notlike '*-debug.dll' -and $_.Name -notlike '*.lib' })
foreach ($d in $dlls) { Copy-Item -LiteralPath $d.FullName -Destination (Join-Path $myDst 'bin') -Force }
Ok "bin：$($dlls.Count) 个 dll + 3 个 exe"

foreach ($sub in 'share', 'lib\plugin', 'lib\private') {
    $src = Join-Path $MySqlHome $sub
    if (Test-Path $src) {
        Copy-Item -LiteralPath $src -Destination (Join-Path $myDst (Split-Path -Parent $sub)) -Recurse -Force -ErrorAction SilentlyContinue
        Ok "$sub 已复制"
    }
}
$myMB = [math]::Round(((Get-ChildItem $myDst -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
Ok "绿色版 MySQL：$myMB MB"

# ---------------------------------------------------------------- 5 应用与脚本
Step '5/8 放应用与脚本'

New-Item -ItemType Directory -Path (Join-Path $Stage 'app\webapp') -Force | Out-Null
Copy-Item -Path (Join-Path $webSrc '*') -Destination (Join-Path $Stage 'app\webapp') -Recurse -Force
Copy-Item -LiteralPath $jar.FullName -Destination (Join-Path $Stage 'app\backend.jar') -Force
Copy-Item -LiteralPath (Join-Path $Root 'db\init') -Destination (Join-Path $Stage 'app\db-init') -Recurse -Force
$sqlCount = (Get-ChildItem (Join-Path $Stage 'app\db-init') -Filter '*.sql').Count
Ok "app\backend.jar + app\webapp\ + app\db-init\（$sqlCount 个建库脚本）"

New-Item -ItemType Directory -Path (Join-Path $Stage 'tools') -Force | Out-Null
foreach ($s in 'start.ps1', 'stop.ps1') {
    Copy-Item -LiteralPath (Join-Path $Root "tools\launcher-native\$s") -Destination (Join-Path $Stage 'tools') -Force
}
Ok 'tools\start.ps1 + tools\stop.ps1'

# 免安装版有自己的一份说明：根目录那份是给 Docker 版的，照抄过去会让人满世界找 Docker
Copy-Item -LiteralPath (Join-Path $Root 'tools\launcher-native\使用说明.txt') -Destination (Join-Path $Stage '使用说明.txt') -Force
Ok '文件 使用说明.txt（免安装版）'
if (Test-Path (Join-Path $Root 'README.md')) {
    $readmeDst = Join-Path $Stage 'README.md'
    Copy-Item -LiteralPath (Join-Path $Root 'README.md') -Destination $readmeDst -Force
    # 这份 README 是给维护者看的（里面有 Docker 版、5173/8081 端口等章节）。收件人照它找 Docker
    # 会对不上，所以在包内这一份的开头加两行指路，说明本包该看哪份文档。
    $banner = @(
        '> 本目录是 Windows 免安装版：收件人只看「使用说明.txt」，双击 start.bat 即可，不需要 Docker。',
        '> 下面这份 README 是给维护者 / 二次开发看的，其中 Docker、端口 5173/8081 等章节与本包无关。',
        ''
    )
    $readmeBody = @(Get-Content -LiteralPath $readmeDst -Encoding UTF8)
    [System.IO.File]::WriteAllText($readmeDst, (($banner + $readmeBody) -join [char]10) + [char]10, (New-Object System.Text.UTF8Encoding($false)))
    Ok '文件 README.md（已加「免安装版看 使用说明.txt」的指路提示）'
}

# 随包预置一份 .env：大模型开关打开、AI_API_KEY 留空（收件人只填 key 一行就能用大模型），
# 数据库口令与令牌密钥随机生成。内容由包内自己的 tools\start.ps1 -InitEnv 生成，
# 保证「打包预置的配置」和「收件人首次启动会自动生成的配置」永远是同一份口径。
$envLog = Invoke-Native 'powershell.exe' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $Stage 'tools\start.ps1'), '-InitEnv')
if (-not (Test-Path (Join-Path $Stage '.env'))) {
    Say ($envLog.Out -join [Environment]::NewLine)
    Die '没能生成包内 .env（tools\start.ps1 -InitEnv 失败）。'
}
Ok '包内 .env 已预置（大模型开关打开、AI_API_KEY 留空，收件人填 key 即可）'

# ---------------------------------------------------------------- 6 入口 bat
Step '6/8 生成双击入口'

$startBat = @(
    '@echo off',
    'chcp 65001 >nul',
    'title 三层人才技能培训与考试管理系统',
    'cd /d "%~dp0"',
    'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\start.ps1" %*',
    'echo.',
    'pause'
) -join "`r`n"
[System.IO.File]::WriteAllText((Join-Path $Stage 'start.bat'), $startBat + "`r`n", (New-Object System.Text.ASCIIEncoding))

$stopBat = @(
    '@echo off',
    'chcp 65001 >nul',
    'title 停止服务',
    'cd /d "%~dp0"',
    'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\start.ps1" -Stop %*',
    'echo.',
    'pause'
) -join "`r`n"
[System.IO.File]::WriteAllText((Join-Path $Stage 'stop.bat'), $stopBat + "`r`n", (New-Object System.Text.ASCIIEncoding))
Ok 'start.bat + stop.bat'

# ---------------------------------------------------------------- 7 校验
Step '7/8 打包前校验'

# 包里只有根目录那一份 .env 是允许的，且必须「AI_API_KEY 留空」：口令、令牌密钥、大模型 key 都不能夹带出去。
$envFiles = @(Get-ChildItem $Stage -Recurse -Force -Filter '.env' -ErrorAction SilentlyContinue)
if ($envFiles.Count -ne 1 -or $envFiles[0].DirectoryName -ne $Stage.TrimEnd([char]92)) {
    Die "包里的 .env 只允许根目录那一份，实际找到 $($envFiles.Count) 个：$($envFiles.FullName -join '; ')"
}
$envLines = @(Get-Content -LiteralPath $envFiles[0].FullName -Encoding UTF8)
$keyLine  = @($envLines | Where-Object { $_ -match '^\s*AI_API_KEY\s*=' })
if ($keyLine.Count -ne 1 -or $keyLine[0] -notmatch '^\s*AI_API_KEY\s*=\s*$') {
    Die '包内 .env 的 AI_API_KEY 不是空的（会把 key 一起发出去），已中止。'
}
if (@($envLines | Where-Object { $_ -match '^\s*MYSQL_ROOT_PASSWORD\s*=\s*\S+' }).Count -ne 1) {
    Die '包内 .env 缺少 MYSQL_ROOT_PASSWORD。'
}
Ok '包内 .env 干净：大模型开关打开、AI_API_KEY 留空、口令与令牌密钥随机生成'

$need = @('start.bat', 'stop.bat', '使用说明.txt', 'tools\start.ps1', 'tools\stop.ps1', 'app\backend.jar', 'app\webapp\index.html', 'runtime\jre\bin\java.exe', 'runtime\mysql\bin\mysqld.exe')
foreach ($n in $need) { if (-not (Test-Path (Join-Path $Stage $n))) { Die "包内缺少 $n。" } }
$sqlN = (Get-ChildItem (Join-Path $Stage 'app\db-init') -Filter '*.sql').Count
if ($sqlN -lt 5) { Die "建库脚本只有 $sqlN 个，不正常。" }
Ok "必备文件齐全（建库脚本 $sqlN 个）"

$sizeMB = [math]::Round(((Get-ChildItem $Stage -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
Ok "解压后 $sizeMB MB"

# ---------------------------------------------------------------- 8 压缩
Step '8/8 压缩'

if ($Zip) {
    $zipPath = Join-Path $Dist "$Name.zip"
    if (Test-Path $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
    Say '   正在压缩（几百 MB，要几分钟）…'
    # 不用 Compress-Archive：PS 5.1 那个实现把条目名写成 "a\b\c"（反斜杠），
    # 不合 zip 规范，macOS / Linux 的 unzip 解出来会是一堆名字里带反斜杠的文件。
    # 这里自己写，条目名统一用正斜杠，Windows / macOS / Linux 都能正常解。
    # ZipArchiveMode 在 System.IO.Compression 里，ZipFile 在 ...FileSystem 里，两个都要加载
    Add-Type -AssemblyName System.IO.Compression | Out-Null
    Add-Type -AssemblyName System.IO.Compression.FileSystem | Out-Null
    $basePath = $Stage.TrimEnd([char]92)
    # 变量名不能叫 $zip：脚本参数里有 [switch]$Zip，PowerShell 不区分大小写，是同一个变量，
    # 赋值会撞上 switch 的类型约束。
    $archive = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($f in (Get-ChildItem $Stage -Recurse -File)) {
            $rel = $f.FullName.Substring($basePath.Length + 1).Replace([char]92, '/')
            [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $f.FullName, "$Name/$rel", [System.IO.Compression.CompressionLevel]::Optimal)
        }
    } finally { $archive.Dispose() }
    Ok "已生成 $zipPath（$([math]::Round((Get-Item $zipPath).Length / 1MB, 1)) MB）"
} else {
    Say '   没有加 -Zip，只生成了文件夹（直接压缩这个文件夹拷给对方也可以）。'
}

Say ''
Write-Host '------------------------------------------------------------' -ForegroundColor White
Say  " 打包完成：$Stage"
Say  ''
Say  ' 交付前务必在本机先演练一遍：'
Say  '   1. 把整个文件夹拷到另一个路径（路径里带空格最好，能顺带验证引号处理）'
Say  '   2. 双击 start.bat，等它自动建库、起服务、开浏览器'
Say  '   3. 用另一台同网段的电脑访问它打印的局域网地址'
Say  '   4. 双击 stop.bat，再双击 start.bat，确认第二次启动更快且数据还在'
Write-Host '------------------------------------------------------------' -ForegroundColor White
Say ''