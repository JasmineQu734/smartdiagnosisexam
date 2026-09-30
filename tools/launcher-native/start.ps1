#requires -Version 5.1
<#
  三层人才技能培训与考试管理系统 —— Windows 一键启动（免 Docker、免装 Java/MySQL）

  收件人：解压后双击包根目录的 start.bat。脚本自己做完：
    1/7 检测运行环境（Java、MySQL 优先用包内 runtime\ 里的绿色版，缺什么说清楚）
    2/7 准备配置（端口、数据库口令、令牌密钥，只在没有时生成）
    3/7 抓本机局域网 IP，服务监听 0.0.0.0
    4/7 初始化数据库（首次建数据目录 + 跑 db-init 里的建库建表脚本）
    5/7 启动 MySQL 与后端（后端同一个进程同时提供网页与接口）
    6/7 等就绪并自动打开浏览器
    7/7 打印本机与局域网访问地址

  本脚本放在 <包根>\tools\ 下，包根下按约定有 app\ runtime\ data\ 三个目录。

  用法：
    start.bat                 正常启动
    start.bat -Check          只体检、只报告，不改动任何东西
    start.bat -Stop           停止服务（数据保留）
    start.bat -Port 9000      指定网页端口
    start.bat -NoBrowser      不自动打开浏览器
    start.ps1 -InitEnv        只生成 .env 就退出（打包时预置包内配置用，收件人用不到）
#>
[CmdletBinding()]
param(
    [int]$Port = 0,
    [switch]$Check,
    [switch]$Stop,
    [switch]$NoBrowser,
    [switch]$InitEnv
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

# ---------------------------------------------------------------- 路径
$Root     = Split-Path -Parent $PSScriptRoot        # 包根目录
$AppDir   = Join-Path $Root 'app'
$RtDir    = Join-Path $Root 'runtime'
$DataDir  = Join-Path $Root 'data'
$LogDir   = Join-Path $DataDir 'logs'
$EnvFile  = Join-Path $Root '.env'
$Jar      = Join-Path $AppDir 'backend.jar'
$WebApp   = Join-Path $AppDir 'webapp'
$DbInit   = Join-Path $AppDir 'db-init'
$JreJava  = Join-Path $RtDir 'jre\bin\java.exe'
$MySqlBin = Join-Path $RtDir 'mysql\bin'
$MySqlExe = Join-Path $MySqlBin 'mysqld.exe'
$MyCli    = Join-Path $MySqlBin 'mysql.exe'
$MyAdmin  = Join-Path $MySqlBin 'mysqladmin.exe'
$MyIni    = Join-Path $DataDir 'my.ini'
$MyData   = Join-Path $DataDir 'mysql-data'
$AppPid   = Join-Path $DataDir 'backend.pid'
$MyPid    = Join-Path $DataDir 'mysql.pid'
$StampFile= Join-Path $DataDir 'db-init.stamp'
$AppLog   = Join-Path $LogDir 'backend.log'
$AppErr   = Join-Path $LogDir 'backend-error.log'
$MyLog    = Join-Path $LogDir 'mysql-error.log'
$MyOut    = Join-Path $LogDir 'mysql.out.log'
$InitOut  = Join-Path $LogDir 'db-init.out.log'
$InitErr  = Join-Path $LogDir 'db-init.err.log'

# ---------------------------------------------------------------- 输出
function Say  ($m) { Write-Host $m }
function Step ($m) { Write-Host ''; Write-Host "== $m" -ForegroundColor Cyan }
function Ok   ($m) { Write-Host "   [OK]   $m" -ForegroundColor Green }
function Warn ($m) { Write-Host "   [注意] $m" -ForegroundColor Yellow }
function Bad  ($m) { Write-Host "   [问题] $m" -ForegroundColor Red }
function Die  ($m) {
    Write-Host ''
    Write-Host "启动中止：$m" -ForegroundColor Red
    Write-Host ''
    if (-not $Check -and -not $InitEnv) { Read-Host '按回车关闭' | Out-Null }
    exit 1
}

# ---------------------------------------------------------------- 小工具
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

# 按端口号找出正在监听的进程 PID（停服务时的兜底用）
function Get-PidByPort([int]$port) {
    foreach ($line in (netstat -ano | Select-String 'LISTENING')) {
        if ($line.Line -match ":$port\s+\S+\s+LISTENING\s+(\d+)") { return [int]$Matches[1] }
    }
    return 0
}

# 真实局域网地址：虚拟网卡（VMware / Hyper-V / WSL / 手机热点）也各有一个 IP，
# 随便挑一个别人连不上。判据是路由表：只有「有默认网关的那张网卡」能出网。
# 读 route print -4 里 0.0.0.0 那几条，取 metric 最小的 Interface 列；不依赖 ipconfig 的中文标签。
function Get-LanIp {
    $best = $null
    $bestMetric = [int]::MaxValue
    foreach ($line in @(route print -4)) {
        if ($line -match '^\s*0\.0\.0\.0\s+0\.0\.0\.0\s+\d+\.\d+\.\d+\.\d+\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+)\s*$') {
            $ip = $Matches[1]
            $m  = [int]$Matches[2]
            if ($m -lt $bestMetric -and $ip -notlike '127.*') { $bestMetric = $m; $best = $ip }
        }
    }
    return $best
}

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

function Read-EnvFile($path) {
    $map = [ordered]@{}
    if (-not (Test-Path $path)) { return $map }
    foreach ($line in (Get-Content $path -Encoding UTF8)) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(.*)$') { $map[$Matches[1]] = $Matches[2].Trim() }
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
        Start-Sleep -Seconds 2
    }
    return $false
}

# java -version 把版本写到 stderr，而 PS 5.1 在 ErrorActionPreference=Stop 下会把原生命令的
# stderr 当成终止错误（这正是包内 JRE 明明正常、却判成 0 版的原因），所以这里临时放宽。
function Get-JavaMajor([string]$exe) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = (& $exe '-version' 2>&1 | Out-String)
        if ($out -match 'version "(\d+)') { return [int]$Matches[1] }
    } catch { } finally { $ErrorActionPreference = $old }
    return 0
}

# 跑 mysql 客户端，统一处理两个坑：
#   1) mysql 一定会往 stderr 写「命令行带密码不安全」这类提示，Stop 模式下会被当终止错误；
#   2) 成败只看退出码，不看有没有输出。
function Invoke-MySqlClient([string[]]$myArgs, [string]$Exe = '') {
    if (-not $Exe) { $Exe = $MyCli }
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = @(& $Exe @myArgs 2>&1)
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $old }
    # mysql 的报错走 stderr，只在失败时打印：不打印就没法定位，全打又太吵
    $lines = @(); $errs = @()
    foreach ($item in $out) {
        if ($item -is [System.Management.Automation.ErrorRecord]) { $errs += $item.ToString() }
        else { $lines += $item.ToString() }
    }
    return [pscustomobject]@{ Code = $code; Lines = $lines; Err = $errs }
}

# 执行一个 .sql 文件。这里有三条路，只有一条是对的：
#   - mysql 客户端的 source 命令：这个客户端版本不认，会原样发给服务器报 1064，不能用；
#   - PowerShell 管道喂进去：PS 5.1 给原生命令的管道默认按 ASCII 编码，中文种子数据会变问号，不能用；
#   - Start-Process 的 stdin 重定向：字节级透传，不受编码影响（db-init 下的脚本确认无 BOM），用这条。
function Invoke-SqlFile([string]$file, [string]$password) {
    $myArgs = @('--host=127.0.0.1', "--port=$script:mysqlPort", '-uroot', '--default-character-set=utf8mb4')
    if ($password) { $myArgs += "-p$password" }
    $p = Start-Process -FilePath $MyCli -ArgumentList $myArgs -RedirectStandardInput $file `
         -RedirectStandardOutput $InitOut -RedirectStandardError $InitErr -NoNewWindow -Wait -PassThru
    return $p.ExitCode
}

# 跑一段 SQL（用包内 mysql 客户端连本机 MySQL）
function Invoke-Sql([string]$sql, [string]$password) {
    $myArgs = @('--host=127.0.0.1', "--port=$script:mysqlPort", '-uroot', '--default-character-set=utf8mb4')
    if ($password) { $myArgs += "-p$password" }
    $myArgs += @('-B', '-e', $sql)
    $r = Invoke-MySqlClient $myArgs
    if ($r.Code -ne 0) { Die "执行 SQL 失败（退出码 $($r.Code)）：$sql`n$($r.Err -join "`n")" }
}

function Get-Scalar([string]$sql, [string]$password) {
    $myArgs = @('--host=127.0.0.1', "--port=$script:mysqlPort", '-uroot', '--default-character-set=utf8mb4')
    if ($password) { $myArgs += "-p$password" }
    $myArgs += @('-N', '-B', '-e', $sql)
    $r = Invoke-MySqlClient $myArgs
    if ($r.Code -ne 0) { Die "查询失败（退出码 $($r.Code)）：$sql`n$($r.Err -join "`n")" }
    if ($r.Lines.Count -eq 0) { return '' }
    return ($r.Lines[0] -as [string]).Trim()
}

# 把带空格的一整个参数用引号裹起来（Start-Process 不会自己加引号）
function Quote-Arg([string]$a) {
    if ($a -match '\s' -or $a -match '"') { return '"' + ($a -replace '"', '\"') + '"' }
    return $a
}

# 探一次大模型，把「连不通」的原因直接摆在屏幕上：否则诊断会静默回退成规则结论，
# 收件人只看到结论不是大模型写的，分不清是没填 key、连不上外网，还是 key/地址不对。
# 只发一次最小请求（max_tokens 很小），失败不影响启动，也不改任何配置。
function Test-AiEndpoint([string]$BaseUrl, [string]$Model, [string]$ApiKey, [int]$TimeoutSec) {
    $base = ''
    if ($BaseUrl) { $base = $BaseUrl.Trim().TrimEnd('/') }
    if (-not $base) { return [pscustomobject]@{ Ok = $false; Note = 'AI_BASE_URL 是空的' } }
    # PS 5.1 默认不协商 TLS 1.2，不设这一句会连不上 HTTPS 服务（报错看着像网络不通）
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }
    $lower = $base.ToLower()
    $body = @{
        model      = $Model
        max_tokens = 16
        messages   = @(@{ role = 'user'; content = 'ping' })
    } | ConvertTo-Json -Depth 6
    # 与后端同一套口径：Anthropic 形状的地址走 /v1/messages，其余按 OpenAI 兼容走 /chat/completions
    if ($lower.EndsWith('/anthropic') -or $lower.Contains('anthropic.com')) {
        $uri = "$base/v1/messages"
        $headers = @{ 'x-api-key' = $ApiKey; 'anthropic-version' = '2023-06-01' }
    } else {
        $uri = "$base/chat/completions"
        $headers = @{ 'Authorization' = "Bearer $ApiKey" }
    }
    # 中文提示词要按 UTF-8 字节发出去（PS 5.1 默认按本地代码页编码，服务端会收到乱码）
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $null = Invoke-RestMethod -Uri $uri -Method Post -Headers $headers `
                -ContentType 'application/json; charset=utf-8' -Body $bytes -TimeoutSec $TimeoutSec
        return [pscustomobject]@{ Ok = $true; Note = "$Model 有响应" }
    } catch {
        $ex = $_.Exception
        # 网关把原因写在响应体里（401 key 不对 / 404 模型不存在 / 400 参数不支持），尽量带出来
        try {
            $resp = $ex.Response
            if ($resp) {
                $code = [int]$resp.StatusCode
                $reader = New-Object System.IO.StreamReader($resp.GetResponseStream(), [System.Text.Encoding]::UTF8)
                $detail = $reader.ReadToEnd()
                $reader.Dispose()
                $detail = ($detail -replace '\s+', ' ').Trim()
                if ($detail.Length -gt 200) { $detail = $detail.Substring(0, 200) + '…' }
                return [pscustomobject]@{ Ok = $false; Note = "HTTP $code $detail" }
            }
        } catch { }
        if ($ex -is [System.Net.WebException]) {
            $st = $ex.Status
            if ($st -eq [System.Net.WebExceptionStatus]::Timeout) { return [pscustomobject]@{ Ok = $false; Note = "超过 $TimeoutSec 秒没有响应（超时）" } }
            if ($st -eq [System.Net.WebExceptionStatus]::NameResolutionFailure) { return [pscustomobject]@{ Ok = $false; Note = '域名解析失败：这台电脑上不了外网，或 DNS 不可用' } }
            if ($st -eq [System.Net.WebExceptionStatus]::ConnectFailure) { return [pscustomobject]@{ Ok = $false; Note = '连不上服务地址：被防火墙 / 代理 / 内网策略拦住了' } }
        }
        return [pscustomobject]@{ Ok = $false; Note = $ex.Message }
    } finally { $ErrorActionPreference = $old }
}

# ---------------------------------------------------------------- 抬头
Set-Location $Root

Write-Host ''
Write-Host '============================================================' -ForegroundColor White
Write-Host '  三层人才技能培训与考试管理系统  ·  Windows 一键启动' -ForegroundColor White
Write-Host '============================================================' -ForegroundColor White
if ($Check) { Warn '当前是 -Check 模式：只检测、只报告，不会改动任何文件和进程。' }

# ================================================================ 1/7 环境
Step '1/7 检测运行环境'

if (-not (Test-Path $Jar))        { Die "缺少 app\backend.jar，包不完整（是不是只复制了 start.ps1？）。" }
if (-not (Test-Path $WebApp))     { Die "缺少 app\webapp\，包不完整。" }
if (-not (Test-Path $DbInit))     { Die "缺少 app\db-init\，包不完整。" }

$arch = if ([Environment]::Is64BitOperatingSystem) { '64 位' } else { '32 位（需要 64 位系统）' }
Ok "Windows $arch · PowerShell $($PSVersionTable.PSVersion)"

# --- Java：包内绿色 JRE 优先，其次 JAVA_HOME，最后 PATH（本项目只需要 Java，不需要 Python / Node）
$java = $null
$javaFrom = ''
if (Test-Path $JreJava) { $java = $JreJava; $javaFrom = '包内绿色 JRE' }
elseif ($env:JAVA_HOME -and (Test-Path (Join-Path $env:JAVA_HOME 'bin\java.exe'))) {
    $java = Join-Path $env:JAVA_HOME 'bin\java.exe'; $javaFrom = '本机 JAVA_HOME'
} else {
    $cmd = Get-Command java -ErrorAction SilentlyContinue
    if ($cmd) { $java = $cmd.Source; $javaFrom = '本机 PATH' }
}
if (-not $java) {
    Bad '没找到 Java 运行时。'
    Say  '   这个包里应该自带 runtime\jre\，请确认解压完整。'
    Die '缺少 Java 运行时'
}
$javaMajor = Get-JavaMajor $java
if ($javaMajor -lt 17) {
    Bad "找到的 Java 是 $javaMajor 版，本项目要求 17 及以上（$javaFrom：$java）。"
    Die 'Java 版本过低'
}
Ok "Java $javaMajor（$javaFrom）"

# --- MySQL：包内绿色版优先；本机已装的 MySQL 只报告、不碰
$mysqld = $null
$mysqlFrom = ''
if (Test-Path $MySqlExe) { $mysqld = $MySqlExe; $mysqlFrom = '包内绿色版' }
else {
    $cmd = Get-Command mysqld -ErrorAction SilentlyContinue
    if ($cmd) { $mysqld = $cmd.Source; $mysqlFrom = '本机已安装' }
}
if (-not $mysqld) {
    Bad '没找到 MySQL。'
    Say  '   这个包里应该自带 runtime\mysql\，请确认解压完整。'
    Die '缺少 MySQL'
}
Ok "MySQL（$mysqlFrom：$mysqld）"

$busyAll = Get-BusyPorts
if ($busyAll.ContainsKey(3306)) {
    Warn '本机 3306 上已经有一个 MySQL 在跑（应该是你自己装的）。本系统用独立端口和独立数据目录，不会动它。'
} else {
    Ok '本机没有其它 MySQL 在 3306 上运行'
}

# 数据库要建在包所在盘（data\），所以两个盘都看一眼。用 DriveInfo 而不是 PSDrive：
# 后者在受限权限下会安静地读出 0，把「还有 200 GB」误报成「只剩 0 GB」。
function Get-FreeGB([string]$drive) {
    try {
        $di = New-Object System.IO.DriveInfo($drive)
        if ($di.IsReady) { return [math]::Round($di.AvailableFreeSpace / 1GB, 1) }
    } catch { }
    return -1
}
$pkgDrive   = [System.IO.Path]::GetPathRoot($Root)
$freePkgGB  = Get-FreeGB $pkgDrive
$freeSysGB  = Get-FreeGB $env:SystemDrive
if ($freePkgGB -ge 0) {
    if ($freePkgGB -lt 5) { Warn "包所在盘（$pkgDrive）剩余 $freePkgGB GB，建议留 5 GB 以上（数据库建在这个盘）。" }
    else { Ok "包所在盘（$pkgDrive）剩余 $freePkgGB GB" }
} else { Warn "没能读到包所在盘（$pkgDrive）的剩余空间" }
if ($freeSysGB -lt 5 -and $freeSysGB -ge 0 -and $pkgDrive -ne $env:SystemDrive) { Warn "系统盘剩余 $freeSysGB GB，系统盘太满也会影响性能。" }

# ================================================================ 停止
# 放在生成配置之前：停止服务时进程本来就占着端口，若先跑端口检查就会把这些端口
# 当成「被别的软件占用」而改写 .env，每停一次端口就往上爬一格。
if ($Stop -and -not $Check) {
    Step '停止服务'
    $stopMap   = Read-EnvFile $EnvFile
    $mysqlPort = if ($stopMap['MYSQL_PORT']) { [int]$stopMap['MYSQL_PORT'] } else { 3307 }
    $dbPass    = $stopMap['MYSQL_ROOT_PASSWORD']
    $script:mysqlPort = $mysqlPort
    $stopped = $false

    if (Test-Path $AppPid) {
        $p = Get-Content $AppPid -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($p -and (Get-Process -Id $p -ErrorAction SilentlyContinue)) {
            Say "   停止后端（PID $p）…"
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            $stopped = $true
        }
        Remove-Item -LiteralPath $AppPid -Force -ErrorAction SilentlyContinue
    }

    # 数据库分两步停：先请它自己优雅退出（数据文件才干净），停不掉再按端口找进程强杀。
    # 不能只信 data\mysql.pid：mysqld 在 Windows 上启动后，真正在监听的那个进程
    # 不一定等于 Start-Process 返回的 PID（实测两者不同号，按记录值停会停了个寂寞）。
    if ((Get-BusyPorts).ContainsKey($mysqlPort)) {
        if ($dbPass) {
            Say '   请 MySQL 优雅退出…'
            # 必须用 mysqladmin shutdown：拿 mysql.exe 后面跟 shutdown，客户端会把它当成
            # 「要连的库名」，等于什么都没做，数据文件每次都靠强杀，容易走崩溃恢复。
            $myArgs = @('--host=127.0.0.1', "--port=$mysqlPort", '-uroot', "-p$dbPass", 'shutdown')
            Invoke-MySqlClient -myArgs $myArgs -Exe $MyAdmin | Out-Null
            for ($i = 0; $i -lt 15; $i++) {
                Start-Sleep -Seconds 1
                if (-not (Get-BusyPorts).ContainsKey($mysqlPort)) { break }
            }
        }
        if ((Get-BusyPorts).ContainsKey($mysqlPort)) {
            $mpid = Get-PidByPort $mysqlPort
            $mproc = if ($mpid -gt 0) { Get-Process -Id $mpid -ErrorAction SilentlyContinue } else { $null }
            if ($mproc -and $mproc.ProcessName -eq 'mysqld') {
                Say "   MySQL 没响应，强制停止（PID $mpid）…"
                Stop-Process -Id $mpid -Force -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 3
            } else {
                Warn "端口 $mysqlPort 被别的进程占着（PID $mpid），不是本系统的 MySQL，不动它。"
            }
        }
        if ((Get-BusyPorts).ContainsKey($mysqlPort)) { Warn "端口 $mysqlPort 仍被占用，请手工处理。" } else { $stopped = $true }
    }
    Remove-Item -LiteralPath $MyPid -Force -ErrorAction SilentlyContinue

    if ($stopped) { Ok '已停止。数据都在，下次双击 start.bat 照旧。' } else { Warn '没有发现正在运行的服务。' }
    Say ''
    exit 0
}

# ================================================================ 2/7 配置
Step '2/7 准备配置'

$busy = Get-BusyPorts
$envMap = Read-EnvFile $EnvFile

if ($envMap.Count -gt 0) {
    Ok '.env 已存在，沿用里面的配置（不会覆盖你的 key）'
} else {
    # 先在内存里把该有的值算齐，再决定要不要落盘：-Check 不写文件，但后面几步
    # 照样要拿端口和口令（之前是先写再读，-Check 下就必然读到空，直接死在第 2 步）。
    $genWeb  = Find-FreePort $busy 8080
    $genMy   = Find-FreePort $busy 3307
    $genPwd  = New-Hex 12
    $genAuth = New-Hex 32
    Warn '没有找到 .env，按下面的值生成一份新的：'
    Say  "   WEB_PORT=$genWeb  MYSQL_PORT=$genMy"
    $gen = @(
        '# 由 start.bat 生成（打包时也预置一份随包交付，收件人首次启动沿用它）。',
        '# 要把这个文件夹转发给别人之前，先把 AI_API_KEY 后面填的 key 删掉。',
        '# 网页端口：本机和局域网都用这个端口访问系统',
        ('WEB_PORT=' + $genWeb),
        '# 内置 MySQL 的端口：刻意用 3307，避开本机可能已经装着的 MySQL(3306)',
        ('MYSQL_PORT=' + $genMy),
        '',
        '# 数据库 root 口令（自动生成）。只在第一次初始化数据库时生效，',
        '# 事后手改这里不会改掉已经建好的库，反而会连不上。',
        ('MYSQL_ROOT_PASSWORD=' + $genPwd),
        '',
        '# 登录令牌的签名密钥：决定令牌能不能被伪造，换掉等于所有人重新登录',
        ('auth.secret=' + $genAuth),
        '',
        '# ---------- 大模型（可选增强：填了 key 就走大模型，不填就走内置规则引擎，照常出结论）----------',
        '# 想让它像 AI 一样给出深度思考的分析：把 key 粘到下面 AI_API_KEY= 的等号后面（不加引号、不留空格），',
        '# 保存后重新双击 start.bat 就生效，个人诊断与公司运行诊断会一起切到大模型。',
        '# 只想离线演示、完全不接大模型：把 AI_ENABLED 改成 false。',
        'AI_ENABLED=true',
        'AI_BASE_URL=https://api.deepseek.com',
        'AI_MODEL=deepseek-flash',
        'AI_API_KEY=',
        'AI_TIMEOUT_SECONDS=120'
    )
    if ($Check) {
        Warn '（-Check 模式：以上配置没有真正写入）'
    } else {
        [System.IO.File]::WriteAllText($EnvFile, ($gen -join "`r`n") + "`r`n", (New-Object System.Text.UTF8Encoding($false)))
        Ok "已写入 $EnvFile"
    }
    $envMap = [ordered]@{
        WEB_PORT            = "$genWeb"
        MYSQL_PORT          = "$genMy"
        MYSQL_ROOT_PASSWORD = $genPwd
        'auth.secret'       = $genAuth
        AI_ENABLED          = 'true'
        AI_BASE_URL         = 'https://api.deepseek.com'
        AI_MODEL            = 'deepseek-flash'
        AI_API_KEY          = ''
        AI_TIMEOUT_SECONDS  = '120'
    }
}

$webPort   = if ($envMap['WEB_PORT'])   { [int]$envMap['WEB_PORT'] }   else { 8080 }
$mysqlPort = if ($envMap['MYSQL_PORT']) { [int]$envMap['MYSQL_PORT'] } else { 3307 }
$dbPass    = if ($envMap['MYSQL_ROOT_PASSWORD']) { $envMap['MYSQL_ROOT_PASSWORD'] } else { '' }
if (-not $dbPass) {
    # 有人手改 .env 时把口令那一行删掉或清空：数据库还没建过就补一个新口令写回去；
    # 建过就不能凭空补 —— 老库认的是原口令，乱写一个只会让后端连不上库，所以这时候要人去找回原口令。
    if (Test-Path (Join-Path $MyData 'mysql')) {
        Die '.env 里 MYSQL_ROOT_PASSWORD 是空的，但数据库已经建过了：请把原来的口令填回去（删掉 .env 会连不上老库）。'
    }
    $dbPass = New-Hex 12
    $lines = @()
    $written = $false
    if (Test-Path $EnvFile) {
        foreach ($l in @(Get-Content $EnvFile -Encoding UTF8)) {
            if ($l -match '^\s*MYSQL_ROOT_PASSWORD\s*=') { $lines += ('MYSQL_ROOT_PASSWORD=' + $dbPass); $written = $true }
            else { $lines += $l }
        }
    }
    if (-not $written) { $lines += ('MYSQL_ROOT_PASSWORD=' + $dbPass) }
    if ($Check) {
        Warn '（-Check 模式：补出来的口令没有写回 .env）'
    } else {
        [System.IO.File]::WriteAllText($EnvFile, (($lines -join "`r`n") + "`r`n"), (New-Object System.Text.UTF8Encoding($false)))
        Ok '数据库口令原本是空的，已补写一个新的到 .env'
    }
}
$script:mysqlPort = $mysqlPort

if ($Port -gt 0) { $webPort = $Port }

$aiOn  = $envMap['AI_ENABLED'] -eq 'true'
$aiKey = $envMap['AI_API_KEY']
if ($aiOn -and $aiKey) {
    Ok "大模型已开启：$($envMap['AI_MODEL'])"
    # 直接探一次：连不通就当场说清原因，而不是等诊断静默回退成规则结论
    $probeSec = 20
    if ($envMap['AI_TIMEOUT_SECONDS'] -match '^\d+$') {
        $probeSec = [Math]::Min([int]$envMap['AI_TIMEOUT_SECONDS'], 20)
        if ($probeSec -lt 5) { $probeSec = 5 }
    }
    $probe = Test-AiEndpoint $envMap['AI_BASE_URL'] $envMap['AI_MODEL'] $aiKey $probeSec
    if ($probe.Ok) {
        Ok "大模型连通：$($probe.Note)（个人诊断与公司运行诊断都会由大模型实时生成）"
    } else {
        Warn "大模型连不通：$($probe.Note)"
        Say  '          诊断会自动回退内置规则结论（照常可用）；要让结论由大模型生成，先解决这条连通问题。'
        Say  "          地址：$($envMap['AI_BASE_URL'])　key 长度：$($aiKey.Length) 位"
    }
} elseif ($aiOn) {
    Warn '大模型已开启，但还没填 key：把 key 粘到本目录 .env 的 AI_API_KEY= 后面，重新双击 start.bat 就生效。'
    Say  '          现在个人诊断与公司运行诊断都走内置规则引擎，照常出结论。'
} else {
    Ok '大模型未启用（AI_ENABLED=false）：诊断走内置规则引擎（完全离线可用）'
}

if ($InitEnv) {
    Step '只生成配置'
    Say  '（-InitEnv：.env 已写出，到此为止，不建库、不起服务。）'
    Say ''
    exit 0
}

# ================================================================ 3/7 端口与局域网地址
Step '3/7 检查端口与网络'

$busy = Get-BusyPorts
foreach ($item in @(@('网页', $webPort), @('MySQL', $mysqlPort))) {
    if ($busy.ContainsKey([int]$item[1])) {
        if ($Check) { Warn "$($item[0])端口 $($item[1]) 已被占用（-Check 模式不改配置）" }
        else {
            $alt = Find-FreePort $busy $item[1]
            Warn "$($item[0])端口 $($item[1]) 被占用 → 改用 $alt"
            $busy[[int]$alt] = $true
            $key = if ($item[0] -eq '网页') { 'WEB_PORT' } else { 'MYSQL_PORT' }
            $newPort = $alt
            if ($key -eq 'WEB_PORT') { $script:webPort = $alt } else { $script:mysqlPort = $alt; $mysqlPort = $alt }
            $out = foreach ($l in @(Get-Content $EnvFile -Encoding UTF8)) {
                if ($l -match "^\s*$key\s*=") { "$key=$newPort" } else { $l }
            }
            [System.IO.File]::WriteAllText($EnvFile, (($out -join "`r`n") + "`r`n"), (New-Object System.Text.UTF8Encoding($false)))
        }
    } else {
        Ok "$($item[0])端口 $($item[1]) 空闲"
    }
}
$webPort = $script:webPort
$mysqlPort = $script:mysqlPort

$lanIp = Get-LanIp
if ($lanIp) { Ok "局域网地址：$lanIp（服务会监听 0.0.0.0，同网段都能访问）" }
else { Warn '没能自动识别局域网地址（这台机器可能没连网），局域网访问需要手工查 ipconfig' }

if ($Check) {
    Step '检测完成'
    Say ''
    Say  '（-Check 模式到此为止：没有建库、没有起进程、没有改配置。）'
    Say ''
    exit 0
}



# ================================================================ 4/7 数据库
Step '4/7 初始化数据库'

New-Item -ItemType Directory -Path $DataDir, $LogDir -Force | Out-Null

# my.ini：路径含空格必须带引号；用正斜杠，MySQL 在 Windows 上也认
$basedir = ($MySqlBin | Split-Path -Parent) -replace '\\', '/'
$datadir = $MyData -replace '\\', '/'
$logpath = $MyLog -replace '\\', '/'
$ini = @(
    '[mysqld]',
    "basedir=`"$basedir`"",
    "datadir=`"$datadir`"",
    "port=$mysqlPort",
    'bind-address=127.0.0.1',
    'character-set-server=utf8mb4',
    'collation-server=utf8mb4_0900_ai_ci',
    # 千万不要加 skip-name-resolve：加上之后 MySQL 不再把 127.0.0.1 当成 localhost，
    # 'root'@'localhost' 就匹配不上，任何连接都会报 1130 Host is not allowed to connect。
    'max_connections=200',
    "log-error=`"$logpath`""
)
[System.IO.File]::WriteAllText($MyIni, ($ini -join "`r`n") + "`r`n", (New-Object System.Text.UTF8Encoding($false)))

$freshInstall = -not (Test-Path (Join-Path $MyData 'mysql'))
if ($freshInstall) {
    Say '   首次运行：正在初始化数据库目录（约 10-30 秒）…'
    if (Test-Path $MyData) { Remove-Item -LiteralPath $MyData -Recurse -Force -ErrorAction SilentlyContinue }
    New-Item -ItemType Directory -Path $MyData -Force | Out-Null
    $initArgs = @((Quote-Arg "--defaults-file=$MyIni"), '--initialize-insecure')
    $p = Start-Process -FilePath $mysqld -ArgumentList $initArgs -WorkingDirectory $MySqlBin -WindowStyle Hidden -Wait -PassThru
    if ($p.ExitCode -ne 0) {
        Say ''
        if (Test-Path $MyLog) { Say '---- MySQL 错误日志（末尾 20 行）----'; Get-Content $MyLog -Tail 20 }
        Die "初始化数据库失败（退出码 $($p.ExitCode)）。"
    }
    Ok '数据库目录已建好'
} else {
    Ok '数据库目录已存在，沿用（数据不丢）'
}

# --- 启动 MySQL
$mysqlRunning = $false
if (Test-Path $MyPid) {
    $p = Get-Content $MyPid -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($p -and (Get-Process -Id $p -ErrorAction SilentlyContinue)) { $mysqlRunning = $true }
}
if (-not $mysqlRunning -and $busyAll.ContainsKey($mysqlPort)) { $mysqlRunning = $true }

if (-not $mysqlRunning) {
    Say '   启动 MySQL …'
    $mArgs = @((Quote-Arg "--defaults-file=$MyIni"))
    # 把 mysqld 的 stdout/stderr 也重定向到文件：不重定向的话它会一直攥着控制台句柄，
    # start.bat 的窗口在服务起来后仍然不结束（数据日志本身由 my.ini 的 log-error 管，不受影响）
    $proc = Start-Process -FilePath $mysqld -ArgumentList $mArgs -WorkingDirectory $MySqlBin -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $MyOut -RedirectStandardError $MyLog
    $proc.Id | Set-Content -Path $MyPid -Encoding ASCII
    $ok2 = $false
    for ($i = 1; $i -le 60; $i++) {
        Start-Sleep -Seconds 1
        if ((Get-BusyPorts).ContainsKey($mysqlPort)) { $ok2 = $true; break }
        Write-Host '.' -NoNewline
    }
    Say ''
    if (-not $ok2) {
        if (Test-Path $MyLog) { Say '---- MySQL 错误日志（末尾 20 行）----'; Get-Content $MyLog -Tail 20 }
        Die "MySQL 没能在 60 秒内就绪（见 $MyLog）。"
    }
    Ok 'MySQL 已就绪'
} else {
    Ok 'MySQL 已经在运行'
}

# --- 首次：把 root 空口令改成本机随机口令
if ($freshInstall) {
    Invoke-Sql "ALTER USER 'root'@'localhost' IDENTIFIED BY '$dbPass';" ''
    Ok '数据库 root 口令已设置'
}

# --- 建库建表：脚本清单或内容变了才重跑（升级时自动补跑新脚本）
$scripts = @(Get-ChildItem $DbInit -Filter '*.sql' | Sort-Object Name)
if ($scripts.Count -eq 0) { Die "app\db-init\ 里没有建库脚本。" }
$fingerprint = (($scripts | ForEach-Object { $_.Name + ':' + $_.Length }) -join '|')
$prev = if (Test-Path $StampFile) { (Get-Content $StampFile -Raw).Trim() } else { '' }

$hasDb = (Get-Scalar "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='train_system' AND table_name='app_user';" $dbPass)
if ($hasDb -ne '1' -or $prev -ne $fingerprint) {
    Say "   建库建表：按顺序执行 $($scripts.Count) 个脚本…"
    foreach ($s in $scripts) {
        Write-Host "     $($s.Name) " -NoNewline
        $code = Invoke-SqlFile $s.FullName $dbPass
        if ($code -ne 0) {
            Say ''
            Say '---- 建库脚本报错（末尾 15 行）----'
            if (Test-Path $InitErr) { Get-Content $InitErr -Tail 15 | ForEach-Object { Say "   $_" } }
            Die "建库脚本 $($s.Name) 执行失败（退出码 $code）。"
        }
        Write-Host 'ok' -ForegroundColor Green
    }
    $tables = (Get-Scalar "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='train_system';" $dbPass)
    if ($tables -lt 10) { Die "建表结果异常：只有 $tables 张表，应该是 50 张以上。" }
    Set-Content -Path $StampFile -Value $fingerprint -Encoding ASCII
    Ok "数据库就绪（$tables 张表）"
} else {
    Ok '数据库已初始化过且脚本没变，跳过建库'
}

# ================================================================ 5/7 启动后端
Step '5/7 启动后端与网页'

$url = "http://127.0.0.1:$webPort/"

$backUp = $false
if (Test-Path $AppPid) {
    $p = Get-Content $AppPid -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($p -and (Get-Process -Id $p -ErrorAction SilentlyContinue)) { $backUp = $true }
}

if ($backUp) {
    Ok '后端已经在运行'
} else {
    $staticLoc = 'file:' + (($WebApp -replace '\\', '/').TrimEnd('/')) + '/'
    $jArgs = @(
        '-jar', $Jar,
        '--server.address=0.0.0.0',
        "--server.port=$webPort",
        "--spring.web.resources.static-locations=$staticLoc"
    )
    Say "   启动后端（网页与接口都在 $webPort，监听 0.0.0.0）…"

    $env:SPRING_DATASOURCE_URL      = "jdbc:mysql://127.0.0.1:$mysqlPort/train_system?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&useSSL=false&rewriteBatchedStatements=true"
    $env:SPRING_DATASOURCE_USERNAME = 'root'
    $env:SPRING_DATASOURCE_PASSWORD = $dbPass
    $env:MATERIAL_DIR               = (Join-Path $DataDir 'materials')
    $env:REPORT_OUTPUT_DIR          = (Join-Path $DataDir 'reports')

    $argLine = ($jArgs | ForEach-Object { Quote-Arg $_ }) -join ' '
    $proc = Start-Process -FilePath $java -ArgumentList $argLine -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput $AppLog -RedirectStandardError $AppErr
    $proc.Id | Set-Content -Path $AppPid -Encoding ASCII
    Ok "后端进程已拉起（PID $($proc.Id)）"
}

# ================================================================ 6/7 等就绪
Step '6/7 等待服务就绪'
Say "   正在等待 $url 响应（首次启动后端要初始化，约 10-30 秒）…"
if (Wait-Http $url 180) {
    Ok '服务已就绪'
    if (-not $NoBrowser) {
        Say  '   正在打开浏览器…'
        try { Start-Process $url } catch { Warn '浏览器没能自动打开，手动复制下面的地址即可。' }
    }
} else {
    Warn '等待超时，后端可能还在启动或启动失败。'
    if (Test-Path $AppErr) {
        $tail = @(Get-Content $AppErr -Tail 20 -ErrorAction SilentlyContinue)
        if ($tail.Count -gt 0) { Say '---- 后端错误输出（末尾 20 行）----'; $tail | ForEach-Object { Say "   $_" } }
    }
    Say  "   完整日志：$AppLog"
    Say  '   停止服务：双击 stop.bat'
}

# ================================================================ 7/7 访问方式
Step '7/7 怎么访问'

Write-Host '------------------------------------------------------------' -ForegroundColor White
Write-Host "   本机：   http://localhost:$webPort" -ForegroundColor Green
if ($lanIp) {
    Write-Host "   同一局域网的其他电脑： http://${lanIp}:$webPort" -ForegroundColor Green
} else {
    Say  '   局域网： 在 PowerShell 里执行 ipconfig，找「IPv4 地址」里不是 127.0.0.1 的那一个，拼上端口 ' + $webPort
}
$others = @(Get-AllLanIps | Where-Object { $_ -ne $lanIp })
if ($others.Count -gt 0) {
    Say  "   上面那个地址如果打不开，把 IP 依次换成这些再试：$($others -join ' / ')"
}
Say ''
Say  ' 演示账号（当前版本只认账号名，不校验密码）：'
Say  '   zhangwei   员工 · 个性化诊断'
Say  '   limin      班组长'
Say  '   wangzong   老总 · 公司运行诊断'
Say  '   admin      管理员'
Say ''
Say  ' 常用操作（都在本目录）：'
Say  '   停止服务       双击 stop.bat'
Say  '   只体检不启动   start.bat -Check'
Say  '   换网页端口     start.bat -Port 9000'
Say  "   看后端日志     $AppLog"
Write-Host '------------------------------------------------------------' -ForegroundColor White
Say ''