# [P1] 考试阈值写死 60，对 80/85 合格线静默漏报 80%

- **编号**：ISSUE-001
- **状态**：待修复
- **严重度**：P1（影响个人诊断与考试回流的正确性）
- **位置**：`db/init/008_rule_engine.sql:70-72`（`EXAM_LOW_SCORE`）
- **发现方式**：`eval/run_eval.py` 离线回放，见 `eval/results/v1/metrics.json` → `E1.exam_threshold_drift`

## 现象

规则条件把及格线写成了常量 60：

```json
{"all":[{"fact":"score","op":"lt","value":60}]}
```

而业务合格线存在 `exam_history.pass_score` 里，种子数据是 80 / 85。
结果是：**62 分的考试在业务上不合格，在规则层却一条建议都不给。**

## 证据

| 指标 | 数值 |
|---|---|
| 低于业务合格线的档案 | 132 |
| 其中规则命中 | 12 |
| 假阴性 | 120 |
| 静默漏报率 | **80.0%** |
| 相对业务合格线的召回率 | **9.09%** |
| 精确率 | 100% |

精确率 100% 说明规则「说的都对」——问题在于它**只覆盖了 9% 该说的话**。这类缺陷比误报危险，因为页面上看不出异常。

## 根因

1. **阈值是历史遗留**：早期「60 分及格」的假设被写进了条件，后来合格线按岗位/考试类型上调到 80/85，规则没跟着改。
2. **规则没有使用事实间比较**：`RuleCondition` 支持 `other_fact`（`008` 里 `FUTURE_DEMAND_GAP` 已经在用），但这条规则写成了字面量。
3. **线上没有消费方**：`EXAM_RESULT` 场景目前只被评测脚本消费，考试交卷后没有接规则引擎，所以错了也没人发现——这是更深的根因，修条件的同时必须把消费方补上。

## 改法

### 1. 规则条件改为事实间比较

```json
{"all":[{"fact":"score","op":"lt","other_fact":"exam_pass_line"}]}
```

保留 `rule_code = EXAM_LOW_SCORE` 与 `rule_name`，不改编号——评测脚本、文档、前端都可能按编号引用。

### 2. 补齐事实组装

由考试交卷链路（或 `AgentDispatchService` 的 exam 分支，目前尚未接入）组装：

```java
facts.put("score", score);                 // exam_history.score
facts.put("exam_pass_line", passScore);    // exam_history.pass_score
facts.put("exam_type", type);              // 理论 / 实操 / 仿真
```

派生事实由调用方算好再传（引擎不做算术，这是既有约定）：

```java
facts.put("score_gap", passScore - score); // 用于后续按差距分档给不同动作
```

### 3. 建议量控制（可选但建议同批做）

改完后命中从 12 涨到 132，同一套「错题知识点复盘」会刷屏。建议按 `score_gap` 分两档：

| 差距 | 动作 |
|---|---|
| ≥ 10 分 | 错题复盘 + 补课 + 带教 + 复考 |
| 1~9 分 | 仅错题复盘 + 复考 |

## 预期指标

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 真阳性 | 12 | 132 |
| 假阴性 | 120 | 0 |
| 召回率 | 9.09% | **100%** |
| 静默漏报率 | 80.0% | 0% |
| 精确率 | 100% | 100%（条件更严，不会引入误报） |

## 验收

1. 规则试算：`score=62, exam_pass_line=80` → `matched=true`，`rule_refs` 含 `EXAM_LOW_SCORE`。
2. 规则试算：`score=85, exam_pass_line=80` → `matched=false`。
3. 事实缺失（没有 `exam_pass_line`）时返回 `UNDECIDABLE`，不静默放过；`skipped_reason` 要能看出缺哪个事实。
4. 重跑评测并断言 `recall_vs_business_pass_line >= 0.95`。
5. `enabled=0` 时仍不参与匹配（重跑 `008` 不得把手工停用的规则打开）。

## 风险与回滚

- **风险**：建议量 11 倍增长，个人页与部长页需要折叠/分页；若某场考试 `pass_score` 为空，事实组装要兜底到 `exam.pass_score`，再退 60，避免整场判不了。
- **回滚**：规则条件在 `rule` 表里，改回 `{"all":[{"fact":"score","op":"lt","value":60}]}` 即恢复；不涉及数据迁移。
- **不要做**：不要改 `exam_history` 的历史分数或合格线来「凑」评测结果。

## 工作量

0.5 人日（改条件 0.1 + 事实接线 0.3 + 重跑与文档 0.1）。
