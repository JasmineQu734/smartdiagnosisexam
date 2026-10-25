# [P2] `TALENT_GAP` 的「未来需求」没有数据源，当前用编制总数近似

- **编号**：ISSUE-004
- **状态**：待接入（当前为已知近似，文案已限定）
- **严重度**：P2（结论方向正确，数字口径需要说清）
- **位置**：`backend/src/main/java/com/power/train/agent/AgentDispatchService.java`（`management` 分支）

## 现状

`FUTURE_DEMAND_GAP` 的条件是 `future_demand > current_supply`，但库里没有「未来需求」这个事实。
当前的组装方式是：

```sql
SELECT COALESCE(SUM(headcount), 0) AS demand FROM position WHERE key_post = 1
```

这实际是**当前关键岗位编制总数**（演示库为 44），不是「明年新增两座站之后的需求」。
策划书里真正想要的是：继保 L3 需求 12 人现有 8 人、高压试验需求 6 人现有 3 人。

「现有人才」已改为在岗一线人数：

```sql
SELECT COUNT(*) FROM app_user WHERE status = 'ACTIVE' AND role_code IN ('EMPLOYEE', 'TEAM_LEAD')
```

## 影响

- 规则命中方向正确（编制 44 > 在岗 3，确实缺人），但**数字不能当作「未来需求」引用**。
- 答辩时若被问「44 这个数怎么来的」，只能回答「关键岗位编制总数」；如果说成「未来需求」，会被追问业务规划依据。
- 当前文案已改为「关键岗位编制 44 人 / 库内一线在岗 3 人」，**不要改回「未来需求」**，除非真正接入了规划数据。

## 改法

### 1. 引入规划假设（推荐，和 5.4 的人力沙盘同源）

新增一张只存假设的表（`013_planning.sql`，可重复执行）：

```
planning_assumption (
  code, name, station_add, workload_growth, horizon_months,
  transfer_cost, recruit_cost, outsource_cost_month, updated_by, updated_at
)
```

按技能算需求：

```
未来需求(技能) = 现有编制(技能) × (1 + workload_growth) + 新增站带来的岗位增量
```

派生值在事实组装时算好（引擎不做算术），规则只判 `future_demand > current_supply`。

### 2. 或最小改法：按技能维度组装事实

对每个关键技能各执行一次 `TALENT_GAP`：

```java
facts.put("skill", "继电保护");
facts.put("future_demand", 12);   // 来自规划假设
facts.put("current_supply", 8);   // level >= required_level 的人数
```

这样输出能直接说「继保缺 4 人」，比「编制 44 / 在岗 3」有用得多。

## 预期指标

| 指标 | 当前 | 接入后 |
|---|---|---|
| 建议可解释性 | 编制/在岗，粒度粗 | 按技能给出需求/现有/缺口 |
| 答辩可追问性 | 「44 是什么」需要解释 | 每个数字有规划参数出处 |
| 与沙盘一致性 | 两套口径 | 同一套 planning_assumption |

## 验收

1. 建议文案中的每个数字都能在 `planning_assumption` 或 `employee_skill` 找到出处。
2. 改 `planning_assumption` 的新增站数，建议里的缺口随之变化（不是写死）。
3. 与 `/exec/scenario/simulate`（沙盘）的结果一致，不允许两套算法。

## 工作量

1 人日（建表 + 事实组装 + 按技能拆分）。
