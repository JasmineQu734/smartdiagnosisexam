#requires -Version 5.1
<#
  本地微调模型 Agent（LLaMA-Factory api 模式）启动脚本

  为什么必须是 api 模式：llamafactory-cli webui 只提供网页界面（7860），没有任何 HTTP 接口，
  后端按 AI_BASE_URL 调不到它；api 模式提供 OpenAI 兼容的 /v1/chat/completions，
  本系统的「个性化诊断」与「公司运行诊断」正是按这个形状调用的。

  用法（推荐双击根目录的 启动Agent.bat）：
    powershell -ExecutionPolicy Bypass -File tools\agent\start-agent.ps1
    powershell -ExecutionPolicy Bypass -File tools\agent\start-agent.ps1 -Port 8000 -Check

  启动成功会打印 Uvicorn running on http://0.0.0.0:8000；这个窗口就是 agent 本体，关掉即停止。
#>
[CmdletBinding()]
param(
    [int]$Port = 0,
    [switch]$Check,
    # 公司运行诊断 Agent（sft17_exec 专用模型）：端口 8002，与个人诊断（8000）并存
    [switch]$Exec
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

# =============================== 换模型只改这一段 ===============================
# LLaMA-Factory 源码目录（llamafactory-cli 在这个目录下跑）
$LlamaHome = 'D:\anaconda\LlamaFactory-main\LlamaFactory-main'
# 装了 LLaMA-Factory 的 conda 环境
$CondaEnv  = 'E:\conda\envs\llama311'
# 基座模型（8G 显存实测：7B 无法容纳 4096 上下文训练，故改用 3B；推理同样更省显存）
$BaseModel = 'E:/models/models/Qwen--Qwen2.5-3B-Instruct'
# 两个 Agent 各挂各的 LoRA 适配器、各占一个端口：
#   默认（不带 -Exec）＝ 个人学习诊断 sft16_3b，端口 8000；
#   -Exec             ＝ 公司运行诊断 sft17_exec，端口 8002（后端 .env 的 AI_EXEC_BASE_URL 对准它）。
$AdapterDefault = 'sft16_3b'
$PortDefault    = 8000
$NameDefault    = 'qwen2.5-3b-lora'
if ($Exec) {
    $AdapterDefault = 'sft17_exec'
    $PortDefault    = 8002
    $NameDefault    = 'qwen2.5-3b-exec'
}
$Adapter   = Join-Path $LlamaHome ("saves\Qwen2.5-3B-Instruct\lora\" + $AdapterDefault)
$Port      = if ($Port -gt 0) { $Port } else { $PortDefault }
# 单次生成上限：一份完整诊断 JSON 约 800-1200 tokens，给低了会被截断成不合格结论
$MaxNewTokens = 4096
# 报给 /v1/models 的模型名，与后端 .env 的 AI_MODEL / AI_EXEC_MODEL 保持一致
$ModelName = $NameDefault
# ==============================================================================

function Say  ($m) { Write-Host $m }
function Step ($m) { Write-Host ''; Write-Host "== $m" -ForegroundColor Cyan }
function Ok   ($m) { Write-Host "   [OK]   $m" -ForegroundColor Green }
function Warn ($m) { Write-Host "   [注意] $m" -ForegroundColor Yellow }
function Bad  ($m) { Write-Host "   [问题] $m" -ForegroundColor Red }
function Die  ($m) {
    Write-Host ''
    Write-Host "启动中止：$m" -ForegroundColor Red
    Write-Host ''
    if (-not $Check) { Read-Host '按回车关闭' | Out-Null }
    exit 1
}

function Get-PidByPort([int]$port) {
    foreach ($line in (netstat -ano | Select-String 'LISTENING')) {
        if ($line.Line -match ":$port\s+\S+\s+LISTENING\s+(\d+)") { return [int]$Matches[1] }
    }
    return 0
}

$Cli = Join-Path $CondaEnv 'Scripts\llamafactory-cli.exe'

Step '1/4 检查运行环境'
if (-not (Test-Path $Cli)) {
    Bad "找不到 $Cli"
    Say '         把脚本顶部的 CondaEnv 改成装了 LLaMA-Factory 的 conda 环境目录。'
    Die 'conda 环境不对'
}
Ok "LLaMA-Factory：$Cli"
if (-not (Test-Path (Join-Path $BaseModel 'config.json'))) { Die "找不到基座模型：$BaseModel" }
Ok "基座模型：$BaseModel"
if (-not (Test-Path (Join-Path $Adapter 'adapter_model.safetensors'))) {
    Bad "找不到 LoRA 适配器：$Adapter"
    Say "         可用适配器在 $LlamaHome\saves\Qwen2.5-3B-Instruct\lora\ 下，"
    Say '         挑带 adapter_model.safetensors 的目录，把顶部的 Adapter 改成它。'
    Die 'LoRA 适配器不对'
}
Ok "LoRA 适配器：$Adapter"

Step "2/4 检查端口 $Port"
$existing = Get-PidByPort $Port
if ($existing -gt 0) {
    Warn "端口已被占用（PID $existing）：大概率另一个窗口里 agent 已经在跑了。"
    Say  '         直接用它即可；要重开请先关掉那个窗口，或双击 停止Agent.bat。'
    Say  "         接口地址：http://127.0.0.1:$Port/v1/chat/completions"
    if ($Check) { exit 0 }
    Read-Host '按回车关闭' | Out-Null
    exit 0
}
Ok '端口空闲'

Step '3/4 显存提醒'
$webui = Get-PidByPort 7860
if ($webui -gt 0) {
    Warn "7860 上还有 llamafactory-cli webui 在跑（PID $webui）。8G 显存装不下两份 7B 模型，"
    Say  '         请先关掉那个 webui 窗口再启动 api，否则会 OOM。'
    Die '显存冲突'
}
Ok '没有同时开 webui'

Step '4/4 启动模型（首次加载约 20-40 秒）'
Say  "   基座：  $BaseModel"
Say  "   适配器：$Adapter"
Say  "   接口：  http://127.0.0.1:$Port/v1/chat/completions"
Say  ''
Say  '   这个窗口就是 agent 本体，别关；关掉窗口 = 停止 agent。'
Say  '   看到 “Uvicorn running on http://0.0.0.0:…”，就可以回员工端点「运行个性化 Agent 诊断」了。'
Say  ''
if ($Check) { Say '   （-Check 只体检，不启动）'; exit 0 }

$env:API_PORT = "$Port"
$env:API_MODEL_NAME = $ModelName
Push-Location $LlamaHome
try {
    & $Cli api --model_name_or_path $BaseModel --adapter_name_or_path $Adapter --template qwen `
        --finetuning_type lora --quantization_bit 4 --quantization_method bnb --max_new_tokens $MaxNewTokens
} finally {
    Pop-Location
}
