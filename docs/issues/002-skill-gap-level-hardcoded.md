# [P1] `SKILL_GAP_L3` 写死 required_level=3，94 条技能缺口静默漏报

- **编号**：ISSUE-002
- **状态**：待修复
- **严重度**：P1（直接影响学习计划与「个人欠缺」板块）
- **位置**：`db/init/008_rule_engine.sql:66-69`（`SKILL_GAP_L3`）
- **发现方式**：`eval/results/v1/metrics.json` → `E1.level_hardcoding`

## 现象

```json
{"all":[
  {"fact":"current_level","op":"lt","other_fact":"required_level"},
  {"fact":"required_level","op":"eq","value":3}
]}
```

第二个条件是多余的：它把「等级不足」缩小成「岗位要求正好是 L3」。
岗位要求 L2 的技能缺一级、L4 的技能缺两级，全都不报。

## 证据

| 指标 | 数值 |
|---|---|
| 规则命中 | 26 |
| 因 `required_level != 3` 漏报 | **94** |
| 事实不可判定而跳过 | 0 |
| 未来等级轴有差距但无规则覆盖 | 120 |
| 技能等级差距漏报率 | **62.7%（94/150）** |

`missed_because_undecidable = 0` 说明不是事实缺失，是条件主动排除了它们。

## 根因

规则名 `SKILL_GAP_L3` 来自策划书里的举例（「岗位要求 L3、当前 L1」），实现时把举例当成了范围。
一条规则同时承担了两件事：

1. 判定「有没有缺口」——应该适用于所有等级；
2. 判定「缺口值不值得优先处理」——这是优先级问题，不该用等级硬编码表达。

## 改法

### 1. 基础规则：去掉等级门槛

`rule_code` 保持 `SKILL_GAP_L3` 不变（评测脚本、论文、文档都在按这个编号引用），只改条件与名称：

```json
{"all":[{"fact":"current_level","op":"lt","other_fact":"required_level"}]}
```

`rule_name` 改为「技能等级低于岗位要求」（原名带 L3 会继续误导后来人）。

### 2. 新增一条「差距 ≥2 档」的优先规则

```json
{"all":[
  {"fact":"current_level","op":"lt","other_fact":"required_level"},
  {"fact":"level_gap","op":"gte","value":2}
]}
```

- `rule_code`：`SKILL_GAP_CRITICAL`
- `priority`：120（高于基础的 100）
- `stop_on_match = 0`：两条都要命中，动作去重、严重度取高
- 动作在基础动作上追加 `severity = 高`，让排期靠前

`level_gap` 是派生事实，由调用方算好传入（引擎不做算术）：

```java
fact.put("level_gap", required - level);
```

### 3. 不要用 `rule_group` 隔开

两条规则必须都参与匹配才能实现「基础动作 + 高优先标记」。若放进同一组并开 `stop_on_match`，`SKILL_GAP_CRITICAL` 会把基础规则挡掉，反而丢动作。

## 预期指标

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 命中 | 26 | 120 |
| 因等级不是 3 漏报 | 94 | **0** |
| 技能漏报率 | 62.7% | 0% |
| 未来等级轴无规则覆盖 | 120 | 0（若同时补 future 规则） |

## 验收

1. `current=1, required=2` → 命中 `SKILL_GAP_L3`。
2. `current=3, required=3` → 不命中。
3. `current=0, required=3` → 同时命中 `SKILL_GAP_L3` 与 `SKILL_GAP_CRITICAL`，`verdict.rule_refs` 两条都在，动作去重后不重复。
4. 重跑评测并断言 `level_hardcoding.missed_because_level_not_3 == 0`。
5. `E3.level_arithmetic_consistency` 不得从 100% 退化（改规则不能把等级算术带坏）。

## 风险与回滚

- **风险**：建议条数从 26 涨到 120（约 4.6 倍）。个人页必须支持按技能折叠，否则一屏放不下；`AgentDispatchService` 已按技能逐条执行并合并成一条建议，前端展示时仍需分组。
- **风险**：`skill_gap_summary` 这条结论性事实的生成逻辑若也按 L3 过滤，需要同步检查（在 `PersonalDiagnosisService` 里），否则模型拿到的摘要仍只含 L3 缺口。
- **回滚**：恢复原 `condition_json` 即可；`SKILL_GAP_CRITICAL` 可 `enabled=0` 单独停用。

## 工作量

0.5 人日（改两条规则 0.2 + 组装 `level_gap` 0.1 + 重跑与前端折叠确认 0.2）。
