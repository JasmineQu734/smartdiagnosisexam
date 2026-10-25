# 规则缺陷 issue 索引

三条缺陷来自 `eval/results/v1/` 的离线回放（450 次规则执行 + 200 组气体网格 + 150 条金标审计），
全部有可复现证据，不是主观判断。

| 编号 | 标题 | 严重度 | 影响面 | 预期指标变化 | 工作量 |
|---|---|---|---|---|---|
| [#001](001-exam-threshold-drift.md) | 考试阈值写死 60，对 80/85 合格线静默漏报 80% | P1 | 个人诊断 / 考试回流 | 召回 9.09% → ≥95% | 0.5 人日 |
| [#002](002-skill-gap-level-hardcoded.md) | `SKILL_GAP_L3` 写死 required_level=3，漏掉 94 条缺口 | P1 | 个人诊断 / 学习计划 | 漏报 62.7% → <5% | 0.5 人日 |
| [#003](003-gas-within-unreachable.md) | `ratio` 两套口径（后端取绝对值 / 评测用有符号），「`WITHIN` 不可达」结论只在评测口径下成立 | P1 | 气体归因 / 论文结论 | 统一口径后：误升档 0%、定档意图准确率 100% | 0.5 + 0.5 人日 |
| [#004](004-talent-gap-future-demand-proxy.md) | `TALENT_GAP` 的「未来需求」无数据源，当前用关键岗位编制总数近似 | P2 | 组织人才建议 | 按技能给出需求/现有/缺口，与沙盘同源 | 1 人日 |

## 建议修复顺序

1. **#003**（最独立、影响面最小，改完立刻能在 200 组网格上验证）
2. **#002**（只改条件，不涉及新事实源）
3. **#001**（需要先定「谁产生 `exam_pass_line`」，涉及考试回流链路，风险最高）

## 统一验收口径

修完三条后重跑：

```bash
python eval/run_eval.py
```

结果另存 `eval/results/v2/`，断言：

- `E1.exam_threshold_drift.recall_vs_business_pass_line >= 0.95`
- `E1.level_hardcoding.missed_because_level_not_3 == 0`
- `E2.determinism_rate == 1.0`（确定性不能因为改规则而退化）
- `E5.false_escalation_rate == 0.0`
- `E5.unreachable_rules == []`

> 注意 #003 有前置条件：必须先决定 `ratio` 用有符号还是非负。口径没统一之前，
> `E5` 的这两条断言没有意义——改的是评测口径，不是规则。

## 关于 GitHub issue

当前环境的 `gh` CLI 未安装。若要在仓库
`JasmineQu734/smartdiagnosisexam` 上建真实 issue，安装 gh 并登录后逐条执行：

```bash
gh issue create --repo JasmineQu734/smartdiagnosisexam \
  --title "[规则缺陷] 考试阈值写死 60，对 80/85 合格线静默漏报 80%" \
  --body-file docs/issues/001-exam-threshold-drift.md
```

三条文档本身就是 issue 正文，可直接用。
