# 规则增强个性化 Agent —— 离线回放评测流程

本目录是论文实验部分的数据来源。它**不修改任何业务代码**，只读取仓库里已有的
真实规则定义与真实语料，按 `docs/rule-engine-design.md` 的口径回放，产出可复现的指标。

## 目录

```text
eval/
├── ruleeng.py         DSL v1 参考求值器 + 规则引擎（分组收敛 / verdict 合并 / *_from 引用事实）
│                      + 从 db/init/*.sql 抽取 rule 定义
├── adapters.py        事实适配层：150 条档案文本 -> PERSONAL_GAP / EXAM_RESULT / REPORT_ANALYSIS facts
│                      + 气体场景 200 组参数网格
├── run_eval.py        6 组实验，产出 results/metrics.json 与 results/tables.md
├── run_api_eval.py    同一批事实走真实 `/api/v1/rules/execute` 的在线复核
├── run_model_eval.py  真实模型实测：直连 8000 端口的 OpenAI 兼容服务，对留出样本打分
├── freeze_eval_set.py 把 26 条评测样本冻结成 jsonl，并校验与已发表结果逐条一致
├── run_baseline_template.py  基线 A：规则结论 + 固定模板叙述，不调用模型
├── compare_baselines.py      三组基线并表（模板 / 微调 3B / 未微调 3B），带精确 95% 区间
├── BASELINE.md        基线对照的跑法与结果判读口径
├── data/my_data15.json  语料快照（150 条，Alpaca 格式 SFT 样本，来自 LLaMA-Factory 训练数据）
├── data/eval_set_26.jsonl  冻结的评测样本（20 留出 + 6 训练原样）
└── results/           评测产物
```

## 运行

```bash
# 离线回放（无需数据库、无需启动后端）
python eval/run_eval.py

# 在线复核（需先起后端：docker compose up -d，或 backend 下 mvn spring-boot:run）
python eval/run_api_eval.py --base http://localhost:8080 --user admin --sample 30

# 真实模型实测（需先起推理服务：桌面 启动Agent.bat，端口 8000）
python eval/run_model_eval.py --heldout 20 --train 6

# 基线对照（三组并表，详见 eval/BASELINE.md）
python eval/freeze_eval_set.py                      # 冻结样本并校验可复现性
python eval/run_baseline_template.py                # 基线 A：规则+固定模板，秒级
python eval/run_model_eval.py --eval-set eval/data/eval_set_26.jsonl \
       --out eval/results/model_eval_base.json      # 基线 B：未微调基座，需换服务权重
python eval/compare_baselines.py                    # 并表
```

## 实验清单

| 编号 | 实验 | 数据来源 |
|---|---|---|
| E1 | 规则集盘点与场景覆盖回放（150 档案 × 3 场景 = 450 次执行） | `db/init/*.sql` + `my_data15.json` |
| E2 | 确定性与幂等性（重复执行逐字节比对 + 规则物理顺序打乱） | 同上 |
| E3 | 模型风格金标输出护栏审计（契约 / 层级算术 / 优先级序 / 数字可溯源 / 安全边界 / 事实一致） | `my_data15.json` 的 `output` |
| E4 | 规则层求值延迟（p50 / p95） | 同上 |
| E5 | 气体场景分组语义验证（定档阶梯 / `max_hits` / 严重度合并 / `_from` 引用事实 / 不可达规则） | `db/init/009_report_gas_rules.sql` |
| E6 | 消融对照（模型直出 vs 规则层） | 综合 E1 / E3 |
| E7 | 真实模型实测（20 条留出 + 6 条训练原样，契约 / 事实 / 排期 / 溯源 / 安全 + 延迟） | `my_data16.json` + 本机推理服务 |

## 口径说明（写论文时要如实交代）

1. **离线回放的合法边界**：`ruleeng.py` 是 DSL v1 的**参考实现**，语义严格对齐
   `docs/rule-engine-design.md`。它复现的是「同一份规则定义 + 同一份事实 → 同一结论」，
   不替代对 Java 引擎的验证。指标须用 `run_api_eval.py` 在线复核后引用。
2. **事实适配层是本文的方法之一，不是既有实现**：档案文本 → facts 的解析规则写在
   `adapters.py` 里，全部只读输入、不依赖任何模型输出（保证「归因输入不含上一轮结论」）。
   论文中必须作为一个可复现的适配层规格给出，不能声称它是生产代码。
3. **延迟口径**：E4 只测**进程内规则层求值**，不含 MySQL 取规则、事实组装、模型推理与网络往返。
   端到端时延需在联调环境另测，不可把 0.008 ms 当成系统响应时间。
4. **金标输出不是模型实测输出**：`my_data15.json` 的 `output` 是 SFT 训练目标（人工构造的高质量答案），
   论文里应称其为 "structured reference outputs" 或 "gold outputs"，不能称其为基线模型输出；
   E6 的「无护栏基线」严格说是「未经校验的结构化参考输出」，不是 M1 纯大模型的实测表现。

## 已知发现（供论文与整改使用）

- `REPORT_GAS_WITHIN` 在 200 组网格中**一次都未命中**：上位规则 `REPORT_GAS_WITHIN_NEAR`
  的条件只写了 `ratio <= 0.10`、未写下界，组内首条命中即停，导致远低于阈值的读数被误升档为「中」。
- `EXAM_LOW_SCORE` 的条件把合格线写死为 60，而业务合格线是 80 / 85，150 条语料中 120 条低于合格线却未触发。
- `SKILL_GAP_L3` 的 `required_level eq 3` 把等级门槛写死为 L3，94 条存在等级差距的档案被漏报。
- 规则集没有任何一条消费安全事实，而语料里 125 条档案带安全负例（其中 75 条为授权类违规）。
