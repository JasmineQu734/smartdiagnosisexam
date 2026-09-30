# 规则引擎设计（第 6 步）

本文是规则引擎的实现口径。约束与背景见根目录 `AGENTS.md`，接口总账以 `docs/api-catalog.md` 为准，需求以 `策划书.md` 为准。

**设计目标**：一套**声明式、可解释、可审计**的数据库 JSON 规则引擎，服务三个 Agent 场景；不引入外部规则框架，不引入 ORM，不新增数据库。

---

## 1. 总体结构

```text
                    facts（场景事实，JSON）
                              │
                     RuleFactsProvider        按 scene 从库里组装事实
                              │
                          RuleEngine          取 enabled=1 的规则，按 priority 降序匹配
                              │
                        RuleCondition          白名单算子求值 condition_json
                              │
              ┌───────────────┴───────────────┐
        verdict（合并结论）              hits（逐条命中 + 解释）
              │                               │
      RuleResultStore                  rule_result 表（执行留痕）
              │
      RuleSuggestionService            → agent_suggestion → 人工确认 → decision_log
```

**三层职责必须分开，不能混**：

| 层 | 表 | 回答的问题 |
|---|---|---|
| 规则层 | `rule` | 配置了什么规则 |
| 计算层 | `rule_result` | 这次算出了什么、命中哪条、为什么 |
| 决策层 | `agent_suggestion` + `decision_log` | 给了谁建议、人怎么决定的 |

规则引擎**只写 `rule_result`**，绝不直接改业务数据；转成建议是 `RuleSuggestionService` 的事。

---

## 2. 规则表：`rule`

现有结构（`db/init/001_schema.sql`）：

```sql
rule (rule_code, scene, condition_json, action_json, priority, enabled, remark)
```

**新增列**（向后兼容，全部有默认值）：

| 列 | 类型 | 说明 |
|---|---|---|
| `rule_name` | `VARCHAR(64)` | 规则名，管理员列表里给人看的（`remark` 是说明，不是名字） |
| `stop_on_match` | `TINYINT(1)` 默认 `1` | 命中后是否停止匹配。默认「最高优先级命中即用」；需要合并多条动作的场景显式设为 0 |
| `rule_group` | `VARCHAR(32)` 默认 `''` | 匹配分组。同场景里「定档」和「关键词补充」必须各判各的，否则一条 `stop_on_match` 命中就把整场结束、关键词永远轮不到。空串＝默认组 |
| `max_hits` | `INT` 默认 `0` | 本组最多命中几条（0＝不限）。关键词组用 `max_hits=3` 表达「最多补 3 条原因」 |
| `status` | `VARCHAR(16)` 默认 `ENABLED` | 策划书要求的公共字段，与 `enabled` 并存：`enabled` 是实际开关，`status` 留作草稿/归档扩展 |
| `created_by` / `created_at` / `updated_by` / `updated_at` | | 策划书第 6 章要求的公共字段；库里改规则要能查到谁改的 |

> 注：MySQL 8 **不支持** `ADD COLUMN IF NOT EXISTS`（那是 MariaDB 的语法）。补列脚本要用 `information_schema.columns` 判断后再动态 `ALTER`，否则重复执行会报错。补列脚本：`db/init/008_rule_engine.sql`（`rule_name` / `stop_on_match` / `status` / 公共字段 + `rule_result`）与 `db/init/009_report_gas_rules.sql`（`rule_group` / `max_hits` + `REPORT_GAS` 规则），当前脚本编号到 `009`。

**匹配语义**：

1. 取 `enabled = 1` 且 `scene` 相符的规则，按 `priority` **降序**。
2. `priority` 相同时按 `rule_code` 升序，保证结果稳定可复现（不要依赖 InnoDB 的返回顺序）。
3. 逐条求值 `condition_json`：命中则收进 `hits`。
4. **按 `rule_group` 分组收敛**：`stop_on_match = 1` 只结束**本组**；`max_hits` 达到上限也只关**本组**。
   未分组的规则同属默认组（空串），所以单人场景「最高优先级命中即出结果」的老语义一字未变。
5. `verdict` 合并口径：`actions` / `causes` 去重保序（`cause` 取第一条），
   `severity` 取所有命中里**最严重**的一个（低 < 中 < 高，认不出的取值按 0 兜底）——
   这样「基准档由定档组给、关键词规则命中即抬档」不用引擎认识业务词汇。
6. `hits` 为空时返回**兜底结论**（`matched: false` + `unmatched_reason`），不报错。

---

## 3. `condition_json` 表达式（白名单 DSL）

**绝不使用** SpEL、`eval`、脚本引擎、字符串拼 SQL。条件是一棵纯数据结构树，算子由 Java 按白名单实现。

```jsonc
// 组合器：all = 与，any = 或，not = 非；可嵌套
{ "all": [ <条件>, <条件> ] }
{ "any": [ <条件>, <条件> ] }
{ "not": <条件> }

// 叶子：单事实比较
{ "fact": "current_level", "op": "lt", "value": 3 }
{ "fact": "current_level", "op": "lt", "other_fact": "required_level" }   // 事实之间比较
{ "fact": "skill_missing", "op": "is_true" }

// 文本命中清单里任意一项（关键词规则用：一条规则挂一组同义关键词）
{ "fact": "document_text", "op": "contains_any", "value": ["泄漏", "漏气", "压力下降"] }
```

**算子白名单（v1）**：

| 类别 | 算子 |
|---|---|
| 比较 | `eq` `ne` `gt` `gte` `lt` `lte` `between` |
| 集合 | `in` `not_in` |
| 文本 | `contains` `not_contains` `contains_any` `starts_with` `ends_with` |
| 布尔/存在 | `is_true` `is_false` `exists` `missing` |

**求值规则**：

- 数值比较统一走 `BigDecimal`，不要用 `double` 比大小（现有 `ReportAnalysisService` 也是 `BigDecimal`，保持一致）。
- `different type` / 未知 `op` / `fact` 不存在 / `value` 缺失 → 该条规则判定为**「不可判定」**，记进 `hits[].skipped_reason` 并**跳过**，不能抛异常把整个 `/rules/execute` 打挂，也不能当成「命中」。
- 未在 facts 里出现且算子需要该 fact 的规则 → 跳过 + 记原因。这是排障最需要的信息。

**现有 6 条种子的迁移**（`002_seed.sql:181`，形状与新 DSL 不同，`008` 里按新形状重写，`ON DUPLICATE KEY UPDATE` 幂等）：

| rule_code | 新 `condition_json` |
|---|---|
| `SKILL_GAP_L3` | `{"all":[{"fact":"current_level","op":"lt","other_fact":"required_level"},{"fact":"required_level","op":"eq","value":3}]}` |
| `EXAM_LOW_SCORE` | `{"all":[{"fact":"score","op":"lt","value":60}]}` |
| `BACKUP_SHORTAGE` | `{"all":[{"fact":"backup_count","op":"lt","value":2}]}` |
| `FUTURE_DEMAND_GAP` | `{"all":[{"fact":"future_demand","op":"gt","other_fact":"current_supply"}]}` |
| `PRACTICE_SKILL_CAUSE` | `{"all":[{"fact":"actual_hours_ratio","op":"gt","value":1.2},{"fact":"skill_missing","op":"is_true"}]}` |
| `PRACTICE_HUMAN_CAUSE` | `{"all":[{"fact":"sop_preparation","op":"is_false"}]}` |

`action_json` 形状：`{"actions":[...]}`、`{"cause":"SKILL","severity":"中","actions":[...]}`；
以 `_from` 结尾的字段是**引用事实**，输出时换成该事实的当前值：

```jsonc
// 一条规则就够，不必为「3 种气体 × 6 个档位」写 18 条
{ "severity": "高", "cause_from": "gas_attribution", "actions_from": "gas_actions" }
```

取不到时把 `_from` 原样留在输出里并写进 `explanation`（排障时一眼看出是哪个事实没给到，不会悄悄少一个字段）；
`action_json` 里同时写了同名键（如 `cause`）时显式值优先。

---

## 4. 执行结果表：`rule_result`

**一次执行一行**（一个 `scene` + 一份 facts = 一个 `run_id`），命中明细放 JSON。

```sql
CREATE TABLE IF NOT EXISTS rule_result (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id VARCHAR(48) NOT NULL,
  scene VARCHAR(64) NOT NULL,
  target_id VARCHAR(64),
  input_json JSON NOT NULL,          -- 归一化后的 facts（脱敏后）
  matched TINYINT(1) NOT NULL DEFAULT 0,
  hits_json JSON,                    -- [{rule_code, rule_name, priority, output, explanation, skipped_reason}]
  verdict_json JSON,                 -- 合并后的结论：actions / cause / severity / confidence
  explanation VARCHAR(600) NOT NULL, -- 一句话说清「命中了哪条、依据哪个数据点」
  confidence DECIMAL(5,4) NOT NULL DEFAULT 0,
  source VARCHAR(16) NOT NULL DEFAULT 'rule',
  suggestion_id VARCHAR(64),         -- 已转成建议时回填，打通到 agent_suggestion
  executed_by VARCHAR(64),           -- 管理员测试传 admin，业务调用传触发人
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_rule_result_run (run_id),
  KEY idx_rule_result_scene (scene, id),
  KEY idx_rule_result_target (target_id, id)
) ENGINE=InnoDB;
```

**为什么一次执行一行**：`/rules/results` 的管理员列表要按执行批次读，一行一次最直观；`suggestion_id` 回填后能一条链走到决策留痕。

**已知代价**：算「单条规则历史命中几次」要解析 `hits_json`。MySQL 8 有 `JSON_TABLE`，要做规则命中率统计时够用；真成为瓶颈再拆 `rule_hit` 明细表，现在不提前拆。

**写入策略**：

- 管理员测试（`options.persist=false`，默认）：只算不落库，返回 `run_id` 供排障。
- 业务 / Agent 调用：落库。
- `input_json` 里的心理、关怀等敏感事实必须先脱敏；`rule_result` 不是给管理端看个人明细的地方。

---

## 5. 接口

统一走 `{ code, message, data, trace_id }` 外层；**只给管理员测试，前端不直接调用**。`/api/v1/rules/**` 已补进 `rbac/RoleInterceptor`（限 ADMIN，越权 `403 / 40301`）。

### `GET /api/v1/rules`

规则清单（管理员）。支持 `scene` / `enabled` 过滤，返回 `rule_code` / `rule_name` / `scene` / `condition_json` / `action_json` / `priority` / `enabled` / `stop_on_match` / `remark` / 公共字段。

### `POST /api/v1/rules/execute`

```jsonc
// 请求
{
  "scene": "PERSONAL_GAP",
  "target_id": "zhangwei",
  "facts": { "current_level": 1, "required_level": 3, "skill": "继电保护" },
  "options": { "persist": false, "top_n": 3 }
}
```

```jsonc
// 响应 data
{
  "run_id": "R-20260921-0001",
  "scene": "PERSONAL_GAP",
  "target_id": "zhangwei",
  "matched": true,
  "hits": [
    {
      "rule_code": "SKILL_GAP_L3",
      "rule_name": "技能等级低于岗位要求",
      "priority": 100,
      "condition_hit": ["current_level(1) lt required_level(3)", "required_level(3) eq 3"],
      "actions": ["COURSE", "MENTORING", "SIMULATION"],
      "explanation": "技能等级 1 低于岗位要求 3，命中 SKILL_GAP_L3"
    }
  ],
  "skipped": [
    { "rule_code": "EXAM_LOW_SCORE", "skipped_reason": "facts 缺少 score" }
  ],
  "verdict": { "actions": ["COURSE", "MENTORING", "SIMULATION"], "causes": [], "cause": null, "severity": null, "rule_refs": ["SKILL_GAP_L3"], "confidence": 0.9 },
  "unmatched_reason": null,
  "source": "rule",
  "need_human_confirm": true,
  "executed_at": "2026-09-21T10:00:00Z"
}
```

- 无规则命中时 `matched=false`、`hits=[]`、`unmatched_reason` 写明原因（场景无规则 / 条件不满足 / facts 不足）。
- `facts` 缺字段、算子不支持等**不返回 5xx**，在 `skipped` 里讲清楚。
- `options.persist=true` 时才写 `rule_result`。

### `GET /api/v1/rules/results`

执行历史（管理员）：`?scene=&target_id=&from=&to=&page=&size=`，倒序分页，返回 `run_id` / `scene` / `target_id` / `matched` / 命中条数 / `confidence` / `explanation` / `suggestion_id` / `executed_by` / `created_at`。

### 业务侧的人工确认接口

`POST /api/v1/tasks/reports/{reportId}/attribution/confirm`（`/tasks/**` → 班组长），body `{decision, reason}`：
`accept` / `reject` / `modify`（后两者必须给 `reason`）。效果是 `agent_suggestion.status` 流转 + 写一条 `decision_log`，
**只改建议状态，不改业务数据**。建议编号即规则执行编号（`run_id`），所以「报告 → 命中规则 → 建议 → 人工决定」是一条链。

> 规则本身的新增 / 修改 / 启停（`POST /rules`、`POST /rules/{code}/toggle`）策划书没点名，但第 4 章「规则管理：维护规则表，包括条件、动作、优先级、启停、测试」有要求。建议同轮一起做，否则管理员改规则只能进库手写 SQL —— 这点需要你确认是否纳入本轮范围。

---

## 6. facts 从哪来

事实由**每个场景自己的适配层**组装（不引入单独的 Provider 类，避免又一层转发），业务路径不接受外部传入的 `facts`：

| scene | facts 组装处 | 来源 |
|---|---|---|
| `PERSONAL_GAP` | 待接 | 员工岗位技能要求 vs 现有等级、考试记录、实操任务工时、评价 |
| `EXAM_RESULT` | 待接 | 考试成绩、及格线、错题知识点 |
| `TALENT_GAP` | 待接 | 关键岗位在岗数、备份人数、未来需求 vs 现有供给、成本 |
| `REPORT_GAS` | `ReportAttributionService.facts()` | 报告字段 + `gas_rule` 配置 + 报告本体正文（清单见 `docs/rule-engine-integration.md`） |

管理员测试走 `POST /rules/execute` 直传 `facts` —— **同一个 scene 只允许一个事实来源**，避免「同一场景两套口径」这个项目已经踩过的坑。

**归因输入不能用上一轮的结论**：`document_text` 取 `ReportDocumentService.extractSourceText()`（基础信息 / 检测数据 / 异常现象描述），
不含「四、AI 归因分析」那一节；否则关键词规则会在自己上次的结论里再匹配一遍，越跑原因越多。

**`gas_rule` 阈值不进 `rule` 表**：它是**可配置的知识目录**（`ReportTemplate` 启动装载，规则目录 `ruleCatalog()` 同时喂给 AI 做上下文），不是「规则」。`REPORT_GAS` 的 `rule` 规则负责**归因与动作**（用 `*_from` 引用 `gas_rule` 的归因与措施），阈值继续留在 `gas_rule`。两者都要保留，不要合并。

---

## 7. 落地到业务（三个场景）

**引擎的消费者是业务，不是那三个 Agent 桩**：`/api/v1/agent/**` 目前仍是返回固定文案的桩，
按约定**先不动**（等模型训练好再接：只换 Service 实现、只把 `source` 从 `rule` 换成 `model`，
Controller / DTO / 路径 / 前端都不动）。规则引擎先接真实业务数据。

三块归因业务的对象、消费者与当前状态见 `docs/rule-engine-integration.md`（本文只管引擎，那份管接线）：

| 场景 | 消费者 | 状态 |
|---|---|---|
| `REPORT_GAS`（气体检测归因） | 报告填报 / 人工确认（`/reports/**`、`/tasks/**`） | **已接**：`ReportAttributionService` 适配层 + 12 条规则（`009`） |
| `OPS_ATTRIBUTION`（运营归因：人工问题 vs 技能问题） | 老总（`/exec/agent-diagnose`） | 未接（结论仍是硬编码文案）；有一个口径待拍板 |
| `MATERIAL_CHECK`（资料 / SOP 校验） | 班组长 + 管理员（`/team/materials/**`、`/admin/course-materials/**`） | 未接（只有抽取，没有校验）；结论只做提示、不拦截入库 |

**两条铁律的落点**：

- `source` 只有 `rule` / `model` 两个取值（`RuleSuggestionService.normalizeSource` 强制校验），
  将来换模型只改这个字段的来源与 Service 实现，Controller / DTO / 路径 / 前端都不动。
- `need_human_confirm` 恒为 `1`；`agent_suggestion` 之后必须有人工动作写 `decision_log`。
  现已落地：`POST /tasks/reports/{reportId}/attribution/confirm` → `ACCEPTED` / `REJECTED` / `MODIFIED` + `decision_log`。

**与原实现的衔接**：气体归因替换 `ReportAnalysisService.analyze()` 的规则分支（技术报告 T2 / `docs/技术报告-现状核对与完善建议.md`）。
AI 分支保留，**规则引擎始终是兜底**：AI 超时、输出结构不合法、未配置大模型时自动回退，并附 `fallback_note`。

---

## 8. 实施顺序

1. ✅ `db/init/008_rule_engine.sql`：`rule` 补列（带存在性判断）→ 建 `rule_result` → 6 条种子规范化。同步 `README.md` 脚本清单。
2. ✅ 后端 `com.power.train.rule` 包：`RuleCondition`（DSL 解析 + 求值，算子白名单）、`RuleEngine`（分组匹配 + 兜底）、`RuleResultStore`、`RuleSuggestionService`、`RuleController`。
3. ✅ `rbac/RoleInterceptor` 补 `/api/v1/rules/` → ADMIN。`/api/v1/agent/**` 的鉴权**仍未覆盖**（按约定本轮不动 Agent）。
4. ✅ 气体归因接上：`009_report_gas_rules.sql` + `ReportAttributionService` 适配层，替换 `ReportAnalysisService` 的规则分支。
5. ✅ 建议确认链：`RuleSuggestionService` 写 `agent_suggestion`；`POST /tasks/reports/{reportId}/attribution/confirm` 写 `decision_log`。
   （三个 Agent 桩仍未走引擎，等模型训练好再接。）
6. ✅ 同步 `docs/api-catalog.md`、`README.md`、新增 `docs/rule-engine-integration.md`。
7. ⏳ 运营归因（`OPS_ATTRIBUTION`）：口径待拍板后实施，见 `docs/rule-engine-integration.md` 第 4 节。
8. ⏳ 资料 / SOP 校验（`MATERIAL_CHECK`）：建议性结论，见同文档第 5 节。

---

## 9. 自验清单

- 启停：`enabled=0` 的规则不参与，改回 1 立即生效（读库不缓存，或缓存失效可控）。
- 优先级：同场景两条都命中且 `stop_on_match=1` 时，只出高优先级那条，且顺序稳定可复现。
- 无命中：返回 `matched=false` + `unmatched_reason`，不报 5xx。
- 脏数据：`condition_json` 算子未知 / 类型不匹配 / fact 缺失 → 进 `skipped` 并说明原因，不影响其他规则。
- 事实间比较：`SKILL_GAP_L3` 的 `current_level lt required_level` 走 `other_fact` 分支正确。
- 鉴权：非管理员调 `/api/v1/rules/**` 返回 `403 / 40301`。
- 分组：`VALUE` 组首条命中即定档，`KEYWORD` 组照常补充（关键词不得因为定档组命中而轮不到）。
- 命中上限：`KEYWORD` 组最多 3 条，超出部分不参与合并。
- 引用事实：`cause_from` / `actions_from` 取到值时落到 `cause` / `actions`；取不到时留在输出里并写进 `explanation`。
- 回灌自证：同一份报告连续归因两次，`rule_refs` 必须一致（`document_text` 不含上一轮结论）。
- 铁律：跑一次执行后，业务数据零变更；`agent_suggestion` 有 `source=rule`、`need_human_confirm=1`；人工确认后 `decision_log` 有留痕。
- 留痕链：`rule_result.suggestion_id` = `agent_suggestion.suggestion_id` = `decision_log.suggestion_id` = 报告 `analysis.run_id`。
- 离线：`AI_ENABLED=false` 下全链路可用。
