# 基线对照怎么跑

这份说明对应论文 6.2 局限里「缺基线对照」那一条。跑完能得到一张三组并排的表，
把「六键契约 100% 到底是不是模型的功劳」这个问题变成可测量的结论。

## 为什么必须先冻结样本

`run_model_eval.py` 每次都用固定种子现场重建 26 条样本。只要生成器或档案库有任何改动，
重建出来的就是另一批题，此时拿基线与已发表的 M1 结果对比是无效对比。

所以第一步是把样本落成文件 `eval/data/eval_set_26.jsonl`，并校验它和已发表的
`results/model_eval.json` 逐条一致（比对 `prompt_chars`）。

2026-10-21 已执行，结果是 26 条逐条一致，可用于同题对照。**只要生成器和档案库不再改动，
这一步只需做一次；若重建后一致性校验失败，说明样本换了，必须重跑全部三组。**

## 三步

### 第一步：模板基线（不需要显卡，几秒）

```bash
cd "E:/Intrel-Train Industrial"
"C:/Users/admin/AppData/Local/Programs/Python/Python311/python.exe" eval/run_baseline_template.py
```

读冻结样本 → 用规则结论按固定句式填成六键 JSON → 用 `run_model_eval.check` 打分。
产出 `eval/results/baseline_template.json`。

已跑结果（heldout 20 条）：契约、gaps 集合、等级、优先级、排期、事实引用、数值溯源、
安全处置**全部 26/26**，但 action 只有 **1 种句式**、证据引用率 **0%**、action 平均 **20 字**。

### 第二步：未微调基座（约 45–90 分钟，占用显卡）

先停掉正在跑的服务——8 GB 显存装不下两个 3B 服务。**建议仍然用 8000 端口**，
这样除了权重之外一个参数都不用改，出错面最小：

```bash
# 当前 8000 上跑的是微调模型（id 为 qwen2.5-3b-lora），先确认再停
curl -s http://127.0.0.1:8000/v1/models
# 找 PID：Windows 下用
netstat -ano | grep ":8000" | grep LISTENING
# 然后按 PID 结束该 python 进程；确认端口已释放
curl -s -m 3 http://127.0.0.1:8000/v1/models   # 应报连接失败
```

起 base 服务。**关键是不要传 `--adapter_name_or_path`**，其余参数与微调那一轮完全一致
（同模板 `qwen`、同 4-bit bnb、同 `max_new_tokens`）：

```bash
cd "D:/anaconda/LlamaFactory-main/LlamaFactory-main"

API_PORT=8000 API_MODEL_NAME=Qwen2.5-3B-Instruct llamafactory-cli api \
  --model_name_or_path E:/models/models/Qwen--Qwen2.5-3B-Instruct \
  --template qwen \
  --quantization_bit 4 \
  --quantization_method bnb \
  --infer_backend huggingface \
  --max_new_tokens 1800 \
  > "E:/Intrel-Train Industrial/tmp/agent/api_base.log" 2>&1 &
```

确认起来了（`/v1/models` 能返回，日志里出现 `Quantizing model to 4 bit` 且**没有**
`Loaded adapter(s)`）：

```bash
curl -s http://127.0.0.1:8000/v1/models
grep -c "Loaded adapter" "E:/Intrel-Train Industrial/tmp/agent/api_base.log"   # 必须是 0
```

跑评测：

```bash
cd "E:/Intrel-Train Industrial"
AGENT_API=http://127.0.0.1:8000/v1/chat/completions \
AGENT_MODEL=Qwen2.5-3B-Instruct \
AGENT_TEMPERATURE=0.2 \
"C:/Users/admin/AppData/Local/Programs/Python/Python311/python.exe" eval/run_model_eval.py \
  --eval-set eval/data/eval_set_26.jsonl \
  --out eval/results/model_eval_base.json
```

注意**必须带 `--eval-set`**。不带就会重新生成样本，结果与另外两组不可比。

### 第三步：并表

```bash
cd "E:/Intrel-Train Industrial"
"C:/Users/admin/AppData/Local/Programs/Python/Python311/python.exe" eval/compare_baselines.py
```

产出 `eval/results/baseline_compare.json` 与 `baseline_compare.md`，即论文可直接用的三栏表，
每格带 Clopper-Pearson 精确 95% 区间。

## 结果怎么读（先定好口径，别事后挑）

共三种可能，写进论文的方式不一样：

1. **基座也接近满分**——说明「六键契约合规」主要由提示词与护栏保证，微调的贡献被高估。
   此时论文必须把 5.4 的结论从「模型输出质量好」收窄为「模型在契约内完成了叙述具体化」，
   并用叙述层指标（句式种类、证据引用率、action 字数）支撑。
2. **基座大面积不合规**——说明微调的贡献是「按契约表达」。这是当前论证最想要的结果，
   但也要老实写：基座的失败是「不会按契约输出」，不等于「业务判断差」。
3. **基座 JSON 都解不出来**（很可能）——`response_format=json_object` 在 HF 后端对未微调模型
   不保证生效。这时 `json_ok=0` 是真实结果，不要为它补 few-shot 或调提示词，否则变量就不止一个了。

## 三个坑

- **别传 adapter**。传了就不是 base 了，而 `/v1/models` 仍会正常返回，很容易看不出来；
  用 `grep -c "Loaded adapter" 日志` 确认，必须是 0。
- **别改 `--template`**。两边都必须是 `qwen`，chat template 一变，比较的就不只是权重。
- **`AGENT_MODEL` 不影响生成**，只写进结果留痕；`/v1/models` 的 id 由 `API_MODEL_NAME` 决定。

## 延迟不要跨组比较

模板基线 `latency_s` 记为 0，因为它不经过任何推理；基座的延迟与微调模型的延迟可以对比，
但两者都包含 4-bit 推理与网络开销，与规则引擎的 0.012 ms 不同质（见 `docs/issues/003`）。
