#requires -Version 5.1
<#
  三层人才技能培训与考试管理系统 —— 一键启动（Windows / Docker Desktop）

  做的事：检测环境 → 生成配置 → 拉起容器 → 等就绪 → 打印局域网访问地址。
  端口或密码想固定下来，就先复制 .env.example 成 .env 再运行；不建就自动生成一份随机的。

  收件人只要有 Docker Desktop，双击仓库根目录的「启动.bat」即可，不需要装 Java / Node / MySQL。

  用法：
    .\tools\launcher\start.ps1            检测环境并启动
    .\tools\launcher\start.ps1 -Check     只检测并打印报告，不改任何东西
    .\tools\launcher\start.ps1 -Rebuild   改了后端/前端代码后强制重建镜像
    .\tools\launcher\start.ps1 -Stop      停止服务（保留数据卷）
#>
[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$Rebuild,
    [switch]$Stop
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$EnvFile = Join-Path $Root '.env'

function Say   ($m) { Write-Host $m }
function Step  ($m) { Write-Host ''; Write-Host "== $m" -ForegroundColor Cyan }
function Ok    ($m) { Write-Host "   [OK]   $m" -ForegroundColor Green }
function Warn  ($m) { Write-Host "   [注意] $m" -ForegroundColor Yellow }
function Bad   ($m) { Write-Host "   [问题] $m" -ForegroundColor Red }
function Die   ($m) { Write-Host ''; Write-Host "启动中止：$m" -ForegroundColor Red; Write-Host ''; exit 1 }

function New-Hex([int]$bytes) {
    $buf = New-Object byte[] $bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buf)
    return -join ($buf | ForEach-Object { $_.ToString('x2') })
}

function Get-BusyPorts {
    $busy = @{}
    foreach ($line in (netstat -ano | Select-String 'LISTENING')) {
        if ($line.Line -match ':(\d+)\s+\S+\s+LISTENING') { $busy[[int]$Matches[1]] = $true }
    }
    return $busy
}

function Find-FreePort($busy, [int]$start) {
    $p = $start
    while ($busy.ContainsKey($p)) { $p++ }
    return $p
}

# 真实局域网地址：Windows 上虚拟网卡（VMware / Hyper-V / WSL / 手机热点）也会各给一个 IP，
# 随便挑一个通常是错的——别人连不上。判据是路由表：只有「有默认网关的那张网卡」能出网，
# 别人的请求也才回得来。所以读 route print -4 里 0.0.0.0 那几条，取 metric 最小的 Interface 列。
# 不依赖 ipconfig 的中文标签，也不需要管理员权限。
function Get-LanIp {
    $best = $null
    $bestMetric = [int]::MaxValue
    foreach ($line in @(route print -4)) {
        if ($line -match '^\s*0\.0\.0\.0\s+0\.0\.0\.0\s+\d+\.\d+\.\d+\.\d+\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+)\s*$') {
            $ip = $Matches[1]
            $m = [int]$Matches[2]
            if ($m -lt $bestMetric -and $ip -notlike '127.*') { $bestMetric = $m; $best = $ip }
        }
    }
    return $best
}

# 本机所有可能被局域网访问的 IPv4（去掉回环与 169.254 自动私有地址），
# 用于主地址连不上时的兜底提示——多网卡机器上不一定一次就猜对。
function Get-AllLanIps {
    $out = @()
    foreach ($line in @(ipconfig)) {
        if ($line -match 'IPv4.*?(\d+\.\d+\.\d+\.\d+)') {
            $c = $Matches[1]
            if ($c -notlike '127.*' -and $c -notlike '169.254.*' -and $out -notcontains $c) { $out += $c }
        }
    }
    return $out
}
function Test-Admin {
    return ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Read-EnvFile($path) {
    $map = [ordered]@{}
    if (-not (Test-Path $path)) { return $map }
    foreach ($line in (Get-Content $path -Encoding UTF8)) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $map[$Matches[1]] = $Matches[2].Trim()
        }
    }
    return $map
}

function Wait-Http($url, [int]$timeoutSec) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $timeoutSec) {
        try {
            $r = Invoke-WebRequest -Uri $url -TimeoutSec 5 -UseBasicParsing
            if ($r.StatusCode -eq 200) { return $true }
        } catch { }
        Start-Sleep -Seconds 3
    }
    return $false
}

Set-Location $Root

Write-Host ''
Write-Host '============================================================' -ForegroundColor White
Write-Host '  三层人才技能培训与考试管理系统  ·  一键启动' -ForegroundColor White
Write-Host '============================================================' -ForegroundColor White
if ($Check) { Warn '当前是 -Check 模式：只检测、只报告，不会改动任何文件和容器。' }

# ---------------------------------------------------------------- 1 环境检测
Step '1/6 检测运行环境'

$arch = if ([Environment]::Is64BitOperatingSystem) { '64 位' } else { '32 位' }
Ok "Windows $arch · PowerShell $($PSVersionTable.PSVersion)"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Bad ' 没有找到 docker 命令。'
    Say  ''
    Say  ' 请先安装 Docker Desktop（装完要重启一次电脑）：'
    Say  '   https://www.docker.com/products/docker-desktop/'
    Say  ''
    Say  ' 安装时保持默认勾选「Use WSL 2 instead of Hyper-V」即可。'
    Die  '缺少 Docker Desktop'
}
Ok "Docker 客户端：$((docker --version) -join '')"

$daemonOk = $false
try {
    docker info --format '{{.ServerVersion}}' *> $null
    if ($LASTEXITCODE -eq 0) { $daemonOk = $true }
} catch { }

if (-not $daemonOk) {
    Warn 'Docker 已安装，但后台服务没在运行，正在尝试启动 Docker Desktop…'
    $dd = @(
        (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Docker\Docker\Docker Desktop.exe')
    ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if ($dd) {
        Start-Process -FilePath $dd -WindowStyle Hidden
        Say '   已拉起 Docker Desktop，等待它就绪（首次启动可能要 1-2 分钟）…'
        for ($i = 1; $i -le 40; $i++) {
            Start-Sleep -Seconds 5
            try { docker info --format '{{.ServerVersion}}' *> $null } catch { }
            if ($LASTEXITCODE -eq 0) { $daemonOk = $true; break }
            Write-Host '.' -NoNewline
        }
        Say ''
    }
}
if (-not $daemonOk) {
    Die 'Docker 服务未就绪。请手动打开 Docker Desktop，等左下角显示绿色「Engine running」后重新运行本脚本。'
}
Ok "Docker 服务：$((docker info --format '{{.ServerVersion}} | {{.OSType}}') -join '')"

try { docker compose version *> $null } catch { }
if ($LASTEXITCODE -ne 0) { Die 'docker compose 不可用。请升级 Docker Desktop 到较新版本（自带 compose v2）。' }
Ok "Docker Compose：$((docker compose version) -join '')"

# -Stop 只停容器、不碰配置：放在生成 .env 之前，免得「停止服务」顺手改端口。
if ($Stop -and -not $Check) {
    Step '停止服务'
    Say '正在停止容器（数据卷保留，下次启动数据照旧）…'
    docker compose down
    if ($LASTEXITCODE -ne 0) { Die 'docker compose down 失败，请把上面的报错发给维护者。' }
    Ok '已停止。'
    Say ''
    exit 0
}

$sysDrive = (Get-Item $env:SystemDrive).PSDrive
$freeGB = [math]::Round($sysDrive.Free / 1GB, 1)
if ($freeGB -lt 10) { Warn "系统盘剩余 $freeGB GB，建议留出 10 GB 以上。" } else { Ok "系统盘剩余 $freeGB GB" }

# ---------------------------------------------------------------- 2 生成配置
Step '2/6 准备配置文件'

$busy = Get-BusyPorts
$isAdmin = Test-Admin
$envMap = Read-EnvFile $EnvFile

if ($envMap.Count -gt 0) {
    Ok ".env 已存在，沿用里面的配置（不会覆盖你的 key）"
} else {
    $pMy = Find-FreePort $busy 3306
    $pApi = Find-FreePort $busy 8080
    $pWeb = Find-FreePort $busy 5173
    Warn '没有找到 .env，按下面的值生成一份新的：'
    Say  "   端口  MySQL=$pMy  API=$pApi  Web=$pWeb"
    $gen = @(
        '# 由「启动.bat」自动生成。重新分发时不要把这个文件带出去（里面有随机密钥）。',
        '# 左侧是宿主机端口，容器内端口固定（MySQL 3306 / API 8080 / Web 80）',
        "MYSQL_PORT=$pMy",
        "API_PORT=$pApi",
        "WEB_PORT=$pWeb",
        '',
        'MYSQL_ROOT_PASSWORD=' + (New-Hex 12),
        'MYSQL_BIND=127.0.0.1',
        '',
        '# 大模型是可选增强：默认关闭，此时全系统离线走内置规则引擎，结论照常产出。',
        '# 想接大模型就填 key 并把 AI_ENABLED 改成 true（DeepSeek 用 deepseek-flash）。',
        'AI_ENABLED=false',
        'AI_BASE_URL=https://api.deepseek.com',
        'AI_MODEL=deepseek-flash',
        'AI_API_KEY=',
        'AI_TIMEOUT_SECONDS=120',
        '',
        'AUTH_SECRET=' + (New-Hex 32)
    )
    if ($Check) {
        Warn '（-Check 模式：以上配置没有真正写入）'
    } else {
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($EnvFile, ($gen -join "`r`n") + "`r`n", $utf8)
        Ok "已写入 $EnvFile"
    }
    $envMap = Read-EnvFile $EnvFile
}

$mysqlPort = if ($envMap['MYSQL_PORT']) { [int]$envMap['MYSQL_PORT'] } else { 3306 }
$apiPort   = if ($envMap['API_PORT'])   { [int]$envMap['API_PORT'] }   else { 8080 }
$webPort   = if ($envMap['WEB_PORT'])   { [int]$envMap['WEB_PORT'] }   else { 5173 }

if ($envMap['AI_ENABLED'] -eq 'true' -and $envMap['AI_API_KEY']) {
    Ok "大模型已启用：$($envMap['AI_MODEL'])"
} else {
    Ok '大模型未启用：诊断走内置规则引擎（完全离线可用）'
}

# ---------------------------------------------------------------- 3 端口检查
Step '3/6 检查端口占用'

$busy = Get-BusyPorts
foreach ($item in @(@('Web', $webPort), @('API', $apiPort), @('MySQL', $mysqlPort))) {
    if ($busy.ContainsKey([int]$item[1])) {
        if ($Check) { Warn "$($item[0]) 端口 $($item[1]) 已被占用（-Check 模式不改配置）" }
        else {
            $alt = Find-FreePort $busy $item[1]
            Warn "$($item[0]) 端口 $($item[1]) 被占用 → 改用 $alt"
            $busy[[int]$alt] = $true
            # 按行改写 .env：整行替换比正则稳，也不会把 CRLF 改坏
            $key = $item[0].ToUpper() + '_PORT'
            $newPort = $alt
            $out = foreach ($l in @(Get-Content $EnvFile -Encoding UTF8)) {
                if ($l -match "^\s*$key\s*=") { "$key=$newPort" } else { $l }
            }
            [System.IO.File]::WriteAllText($EnvFile, (($out -join "`r`n") + "`r`n"), (New-Object System.Text.UTF8Encoding($false)))
            switch ($item[0]) { 'Web' { $webPort = $alt } 'API' { $apiPort = $alt } 'MySQL' { $mysqlPort = $alt } }
        }
    } else {
        Ok "$($item[0]) 端口 $($item[1]) 空闲"
    }
}

$lanIp = Get-LanIp
if ($lanIp) { Ok "局域网地址：$lanIp" } else { Warn ' 没能自动识别局域网地址，稍后请手工查看 ipconfig' }

if ($Check) {
    Step '检测完成'
    Say ''
    Say  '（-Check 模式到此为止，没有启动任何容器。）'
    Say  ''
    exit 0
}

# ---------------------------------------------------------------- 4 启动服务
Step '4/6 启动服务'

$imageDir = Join-Path $Root 'images'
$tars = @()
if (Test-Path $imageDir) { $tars = @(Get-ChildItem $imageDir -Filter '*.tar' -ErrorAction SilentlyContinue) }

if ($tars.Count -gt 0 -and -not $Rebuild) {
    Say "发现离线镜像包 $($tars.Count) 个，正在导入（首次约 1-2 分钟）…"
    foreach ($t in $tars) {
        Write-Host "   loading $($t.Name) …" -NoNewline
        docker load -i $t.FullName *> $null
        if ($LASTEXITCODE -eq 0) { Write-Host ' ok' -ForegroundColor Green } else { Write-Host ' 失败' -ForegroundColor Red }
    }
    Say '启动容器…'
    docker compose up -d
    if ($LASTEXITCODE -ne 0) { Die 'docker compose up 失败，请把上面的报错发给维护者。' }
} else {
    if ($Rebuild) { Say '按 -Rebuild 强制重建镜像（首次约 5-15 分钟，取决于网络）…' }
    else { Say '首次运行需要构建镜像并拉取基础镜像（约 5-15 分钟，取决于网络）…' }
    docker compose up -d --build
    if ($LASTEXITCODE -ne 0) { Die 'docker compose up --build 失败，请把上面的报错发给维护者。' }
}

# ---------------------------------------------------------------- 4.5 启动两个本地 Agent
# 两个 3B 4-bit 推理各占约 2.3GB 显存，8G 卡可以并存；
# 后端 .env 里 AI_BASE_URL / AI_EXEC_BASE_URL 已指向 host.docker.internal:8000 / 8002。
Step '4.5/6 启动两个本地 Agent（8000 个人诊断 / 8002 公司诊断）'

$agentPs1 = Join-Path $Root 'tools\agent\start-agent.ps1'
if (-not (Test-Path $agentPs1)) {
    Warn 'tools\agent\start-agent.ps1 不存在，跳过 Agent 启动（诊断将自动回退内置规则结论，不报错）。'
} else {
    $busyNow = Get-BusyPorts
    $agents = @(
        @{ Title = 'agent-8000-personal'; Name = '个人学习 Agent (sft16_3b)'; Extra = @(); Port = 8000 },
        @{ Title = 'agent-8002-exec';     Name = '公司运行 Agent (sft17_exec)'; Extra = @('-Exec'); Port = 8002 }
    )
    foreach ($a in $agents) {
        if ($busyNow.ContainsKey([int]$a.Port)) {
            Warn "$($a.Name)：端口 $($a.Port) 已被占用，视为已在运行，跳过。"
            continue
        }
        $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $agentPs1) + $a.Extra
        Start-Process -FilePath 'powershell.exe' -WindowStyle Normal -WorkingDirectory $Root -ArgumentList $argList
        Ok "$($a.Name) 已在新窗口启动（端口 $($a.Port)，模型加载约 2 分钟后可用）"
    }
    Warn '两个 Agent 窗口不要关，关掉即停该模型（对应诊断会回退规则结论）。'
}

# ---------------------------------------------------------------- 5 等待就绪
Step '5/6 等待服务就绪'

$url = "http://127.0.0.1:$webPort/"
Say "正在等待 $url 响应（首次启动会初始化数据库并跑完 11 个建库脚本，请耐心等）…"
if (Wait-Http $url 600) {
    Ok '服务已就绪，正在打开浏览器…'
    Start-Process $url
    Ok "已打开 $url"
} else {
    Warn '等待超时，服务可能还在初始化。可以先执行下面命令看日志：'
    Say '   docker compose logs -f --tail 50'
}

# ---------------------------------------------------------------- 6 访问方式
Step '6/6 怎么访问'

$ruleName = "PowerTrain Web $webPort"
if ($isAdmin) {
    try {
        netsh advfirewall firewall delete rule name="$ruleName" *> $null
        netsh advfirewall firewall add rule name="$ruleName" dir=in action=allow protocol=TCP localport=$webPort *> $null
        if ($LASTEXITCODE -eq 0) { Ok "已放行 Windows 防火墙入站 TCP $webPort" }
    } catch { Warn '防火墙规则没加上，局域网可能连不上。' }
} else {
    Warn '当前不是管理员，防火墙没有自动放行。'
    Say  '   如果别的电脑打不开，请用「以管理员身份运行」的 PowerShell 执行一次：'
    Say  "     netsh advfirewall firewall add rule name=`"$ruleName`" dir=in action=allow protocol=TCP localport=$webPort"
}

Say ''
Write-Host '------------------------------------------------------------' -ForegroundColor White
Say  ' 启动完成，用浏览器打开：'
Say  ''
Write-Host "   本机：   http://localhost:$webPort" -ForegroundColor Green
if ($lanIp) {
    Write-Host "   同一局域网的其他电脑： http://${lanIp}:$webPort" -ForegroundColor Green
} else {
    Warn ' 没能自动识别局域网地址（这台机器可能没连网）。其他电脑要访问的话，'
    Say  '   请在 PowerShell 里执行 ipconfig，找「IPv4 地址」里不是 127.0.0.1 的那一个。'
}
$others = @(Get-AllLanIps | Where-Object { $_ -ne $lanIp })
if ($others.Count -gt 0) {
    Say  "   上面那个地址如果打不开，把 IP 依次换成这些再试：$($others -join `" / `")"
}
Say ''
Say  ' 演示账号（当前版本只认账号名，不校验密码）：'
Say  '   zhangwei   员工 · 个性化诊断（看个人能力差距与提升建议）'
Say  '   limin      班组长'
Say  '   wangzong   老总 · 公司运行诊断'
Say  '   admin      管理员'
Say ''
Say  ' 想让诊断结论由大模型生成（不配就走内置规则引擎，照常出结论）：'
Say  '   1. 用记事本打开本目录下的 .env，在 AI_API_KEY= 后面填上 key'
Say  '   2. 把 AI_ENABLED=false 改成 AI_ENABLED=true'
Say  '   3. 执行：docker compose up -d --force-recreate backend'
Say ''
Say  ' 常用操作：'
Say  '   停止服务       双击 停止.bat'
Say  '   改了代码重建   启动.bat -Rebuild'
Say  '   看日志         docker compose logs -f --tail 100'
Write-Host '------------------------------------------------------------' -ForegroundColor White
Say ''