# 规则引擎与归因业务的集成契约

规则引擎本身的实现口径见 `docs/rule-engine-design.md`；本文只讲**引擎怎么接进三块归因业务**：
谁是消费者、谁是提供者、事实怎么给、结论怎么接、留痕怎么串。

---

## 1. 先分清：这里的「归因」其实是三件事

三块业务都叫「归因」，但对象、消费者、数据来源完全不同，混在一起就会出现「A 的规则拿 B 的事实去判」。

| | A 运营归因 | B 资料 / SOP 校验 | C 气体检测归因 |
|---|---|---|---|
| 场景（scene） | `OPS_ATTRIBUTION` | `MATERIAL_CHECK` | `REPORT_GAS` |
| 回答什么问题 | 公司层面：这些缺口是**人工问题**还是**技能问题**，运营上该补人还是该补课 | 组长上传的资料 / SOP 模板本身**对不对、全不全** | 这一份检测报告**为什么超限**、要采取什么措施 |
| 消费者 | 老总（`/exec/**`） | 班组长 + 管理员（`/team/**`、`/admin/**`） | 班组长（报告填报与确认） |
| 输入对象 | 员工数据 + 考试 + 报告汇总 + 成本 | 上传的原件与抽取结果 | 一份 `task_report` + `gas_rule` |
| 结论去向 | 老总的运营建议（建议性，不阻断业务） | 审核提示（**建议性，不拦截入库**） | 写进报告的 `analysis`，需班组长确认 |
| 当前状态 | 未接引擎（结论是硬编码文案） | 未接引擎（只有抽取，没有校验） | **已接引擎（本轮完成）** |

落地顺序按约定是 **C → A → B**：C 有真实数据、改动面清晰，先把链路与留痕跑通，A / B 复用同一套适配层模式。

---

## 2. 三条通用契约（A / B / C 都适用）

### 2.1 调用关系

- 业务侧是**消费者**，规则引擎是**提供者**。业务侧负责组装事实、接住结论；引擎不读业务表、不写业务表。
- 引擎只写 `rule_result`（这次算出了什么）；业务侧负责把结论落到自己的数据流上。
- 结论要变成「建议」时才写 `agent_suggestion`；人造动作才写 `decision_log`。三层不能互相越权。

### 2.2 一次归因的留痕链：一个编号串到底

```text
run_id（R-yyyyMMdd-HHmmss-XXXX）
   ├── rule_result.run_id        这次执行命中哪几条规则、事实是什么、为什么这么判
   ├── agent_suggestion.suggestion_id = run_id   给了谁什么建议、待谁确认
   └── decision_log.suggestion_id = run_id       人在什么时候采纳 / 驳回 / 修改，理由是什么
```

建议编号**就是**执行编号：拿到一条建议能直接反查到命中的规则；报告上还写着 `run_id`，从报告也能一路查回来。

### 2.3 结论来源 source：只有 `rule` 和 `model` 两个取值

- `rule`：走规则引擎，`model` 字段填 `内置规则引擎 v1`；
- `model`：走大模型，结论结构必须与规则路完全一致；
- 不传按配置自动选（`ai.enabled` + `ai.api-key` 配好就走大模型）；大模型失败一律回退规则引擎并写 `fallback_note`；
- 以后训练出自己的模型，只换 `ReportAnalysisService` 里 model 分支的实现，Controller / DTO / 路径 / 前端一律不动。

---

## 3. 场景 C：`REPORT_GAS`（本轮已完成）

### 3.1 调用链

```text
POST /api/v1/reports/{reportId}/analyze[?source=rule|model]
        │
   ReportService            组装 run_id，收结论落 task_report.analysis，发布待确认建议
        │
   ReportAnalysisService    选路：rule 走规则引擎 / model 走大模型（失败回退规则）
        │
   ReportAttributionService 适配层：组装 facts → engine.execute(REPORT_GAS) → 映射回 analysis
        │
      RuleEngine  ──→  rule 表（scene=REPORT_GAS）
      RuleResultStore ──→ rule_result
   RuleSuggestionService ──→ agent_suggestion ──(人工确认)──→ decision_log
```

### 3.2 入参：facts 清单（管理员试算时照这份给）

| fact | 类型 | 含义 |
|---|---|---|
| `report_id` / `task_id` | 文本 / 数字 | 报告与任务标识 |
| `gas_type` / `gas_label` / `unit` | 文本 | 气体编码 / 名称 / 单位 |
| `value` / `threshold` | 数值 | 检测值 / 报警阈值 |
| `direction` / `high_direction` | 文本 / 布尔 | 报警方向（`HIGH` 高于阈值报警 / `LOW` 低于阈值报警） |
| `ratio` | 数值 | 余量比例 = \|检测值 − 阈值\| ÷ 阈值（4 位小数） |
| `over_threshold` | 布尔 | 是否超出阈值（按报警方向判断） |
| `standard` | 文本 | 执行依据（取自 `gas_rule`） |
| `gas_attribution` | 文本 | 该气体的运维归因（取自 `gas_rule`） |
| `gas_actions` | 数组 | 该气体的处置措施（取自 `gas_rule`） |
| `phenomenon` / `measures` | 文本 | 现场现象描述 / 已采取措施 |
| `document_text` | 文本 | **报告本体正文**（基础信息 / 检测数据 / 异常现象描述） |

> `document_text` 刻意**不含「四、AI 归因分析」那一节**：归因不能把上一轮的结论当依据，
> 否则关键词规则会在自己上次的结论里再匹配一遍，越跑原因越多（`ReportDocumentService.extractSourceText`）。

### 3.3 规则清单（`db/init/009_report_gas_rules.sql`，共 12 条）

`VALUE` 组：定档。组内 `stop_on_match=1`，首条命中即停；归因与措施用 `*_from` 引用 `gas_rule` 的配置，
所以 3 种气体 × 6 个档位不需要写 18 条规则。

| 优先级 | rule_code | 条件 | 输出 |
|---|---|---|---|
| 150 | `REPORT_GAS_OVER_MARGIN_HIGH` | 超阈值 且 余量 ≥ 20% | severity 高 + 引用气体归因与措施 |
| 140 | `REPORT_GAS_OVER_MARGIN_MID` | 超阈值 且 余量 ≥ 5% | severity 中 + 同上 |
| 130 | `REPORT_GAS_OVER_MARGIN_LOW` | 超阈值 | severity 低 + 同上 |
| 120 | `REPORT_GAS_WITHIN_NEAR` | 未超阈值 且 余量 ≤ 10% | severity 中 + 接近阈值的原因与加密监测措施 |
| 110 | `REPORT_GAS_WITHIN` | 未超阈值 | severity 低 + 按周期复测 |

`KEYWORD` 组：从报告正文里补原因与措施。`stop_on_match=0`、`max_hits=3`（最多补 3 条）。
关键词就是条件里的 `contains_any` 清单，改库即改关键词，不再有第二张关键词表。

| 优先级 | rule_code | 关键词 | 备注 |
|---|---|---|---|
| 100 ~ 96 | `RULE-KW-LEAK` / `_DECOMP` / `_HEAT` / `_PD` / `_MOISTURE` | 泄漏类 / 分解产物类 / 过热类 / 局放类 / 受潮类 | 命中补原因 + 措施 |
| 95 | `RULE-KW-HEALTH` | 头晕 / 恶心 / 不适 / 呛 / 窒息 | **直接声明 severity 高** |
| 94 | `RULE-KW-WORSENING` | 持续 / 未恢复 / 扩大 / 加剧 / 继续上升 / 未回升 | **直接声明 severity 高** |

严重度合并是「**更严重者胜**」：定档组给基准档，关键词规则命中即抬档。原来 Java 里的「一档升级」
（低→中→高）改成了规则自己声明档位 —— 好处是「为什么判高」直接落在具体那条规则上，可查、可改。

### 3.4 出参：引擎结论 → `task_report.analysis`

```jsonc
{
  "source": "rule",                    // 只有 rule / model
  "model": "内置规则引擎 v1",
  "source_label": "内置规则引擎 v1",     // 报告与文档上展示的名字
  "run_id": "R-20260921-133504-ED17",  // 本次执行编号，可反查 rule_result
  "suggestion_id": "R-20260921-...",   // 待人工确认的建议编号（= run_id）
  "abnormal": true,
  "severity": "高",
  "conclusion": "…判定为：…。严重度：高。",
  "causes": ["…"],                     // 引擎 verdict.causes：每条命中各给一条
  "actions": ["…"],                    // 去重保序
  "rule_refs": ["REPORT_GAS_OVER_MARGIN_HIGH", "RULE-KW-DECOMP", "RULE-KW-WORSENING"],
  "standard": "GB/T 11022 / DL/T 596 电力设备预防性试验规程",
  "confidence": 0.84,                  // 引擎口径：0.72 + 0.04 × 命中条数，上限 0.95
  "need_human_confirm": true,
  "input_excerpt": "…",
  "generated_at": "…",
  "skipped_rules": [{"rule_code": "…", "skipped_reason": "…"}]   // 只在有「判不了」的规则时出现
}
```

结构没变（键名与顺序沿用旧实现），前端与 PDF / Word 渲染都不用改。

### 3.5 与旧实现的差异（都是有意改的）

| 项 | 旧实现 | 现在 |
|---|---|---|
| 规则编号 | `RULE-GAS-ABOVE` / `RULE-VALUE-NEAR` / `RULE-SEV-ESCALATE` 是 Java 里拼的字符串，**rule 表里根本不存在** | 全部换成表里的真规则编号，报告上写的规则都查得到 |
| 关键词数据 | `analysis_keyword_rule` 表（另有一份） | 迁进 `rule`（`REPORT_GAS` + `RULE-KW-*`）；旧表保留但运行期不再读取 |
| 严重度抬档 | Java 里写死的「升一档」 | 关键词规则自己声明档位，合并按「更严重者胜」 |
| 置信度 | 0.72 + 0.10（超限）+ 0.04 × min(关键词数,3) | 引擎统一口径 0.72 + 0.04 × 命中条数（上限 0.95） |
| 归因输入 | `extractText(report)` 含上一轮归因结论 | `extractSourceText(report)` 只含报告本体 |
| 结论句子 | Java 里两个 `String.format` | 仍在适配层（展示层），但除超限两档外**补了「未超阈值但有风险」的说法**，不再出现「暂判定为正常范围；严重度：高」 |

### 3.6 人工确认

`POST /api/v1/tasks/reports/{reportId}/attribution/confirm`，body `{decision, reason}`：

- `decision`：`accept` 采纳 / `reject` 驳回 / `modify` 修改后采纳；缺失 → `40001` + `field_errors`，取值非法 → `40003`；
- `reject` 与 `modify` **必须给 reason**（没有理由的驳回，过一阵没人知道当时为什么否掉）；
- 效果：`agent_suggestion.status` 流转为 `ACCEPTED` / `REJECTED` / `MODIFIED`，并写一条 `decision_log`；
- 同一报告重新归因时，旧的待确认建议自动转 `SUPERSEDED`，人只确认最新那份；
- 该接口在 `/tasks/**` 下，只有班组长可调；**只改建议状态，不改业务数据**。

---

## 4. 场景 A：`OPS_ATTRIBUTION`（下一轮）

### 4.1 现状

`POST /exec/agent-diagnose`（`CompanyController.runDiagnosis`）现在**完全没走引擎**：
`inputs` 里 5 条有 4 条是硬编码文案（只有「系统内 N 份」是实时数），`summary` 整段是写死的结论，
`evidence_count` 用 `3 + 报告数` 凑。表里那两条 `REPORT_ANALYSIS` 规则（`PRACTICE_SKILL_CAUSE`、
`PRACTICE_HUMAN_CAUSE`）用的 `sop_preparation` 这个事实**全系统没有任何地方产生**。

### 4.2 要做的

1. 事实从库里真取：员工技能缺口、考试低分人数、关键岗位备份、未来需求、报告超限/缺报、人工成本与外委支出；
2. 规则组拆开：`GAP`（技能缺口定档）、`CAUSE`（人工 / 技能归因）、`ACTION`（补人 / 补课 / 外委建议）；
3. `inputs` 与 `summary` 由引擎结论渲染，不再写死；
4. 结论同样写 `rule_result` + `agent_suggestion`，老总确认后写 `decision_log`。

### 4.3 待定的一个口径（需要拍板）

A 想用「有没有按 SOP 执行」作为判 **人工问题** 的证据，但：

- B 校验的是**上传的资料 / SOP 模板本身**（准备阶段）；
- A 需要的是**这次任务到底有没有按 SOP 干**（执行阶段）；
- 两者对象不同，B 的结论**不能直接喂给 A**；而系统里目前**没有任何「任务是否按 SOP 执行」的记录**
  （报告只有自由文本 `phenomenon` / `measures`，`task` 只有计划/实际工时）。

三个选项（推荐第 1 个）：

1. 在报告填报里加一个结构化字段（如「本次作业是否按 SOP 卡执行 + 偏差说明」），A 只认这个字段，
   不去猜 SOP 语义；B 继续只管资料本身；
2. 把 B 的范围从「资料」扩到「执行记录」，B 产出执行合规结论供 A 引用（B 的职责会变重）；
3. A 放弃 SOP 证据，只用现象描述 + 措施 + 工时超时来判断人工 / 技能原因（最省事，但「人工问题」的说服力最弱）。

**拍板前不动 A 的实现。**

---

## 5. 场景 B：`MATERIAL_CHECK`（再下一轮）

现状：`MaterialAgent` + `MaterialImportService` 只做**抽取**（把资料整理成候选题 / 课程章节），
对「答案对不对、SOP 全不全」**没有任何自动判断**。

要做：给 `material_item` / `material_doc` 的抽取结果加一层 `MATERIAL_CHECK` 校验结论，
按建议性输出（`need_human_confirm=true`）：

- 结构完整性：题干 / 选项 / 答案 / 解析是否齐全，选项数量与答案是否自洽；
- 答案可核性：答案能否在原件出处（页码 / 段落）里对上；
- SOP 模板：作业步骤 / 判定标准 / 考核要点 / 风险点是否缺项，是否与本专业标准冲突。

**校验结论只做提示，不拦截入库**（人工审核仍是唯一的入库闸门），避免规则误判把正确资料挡在外面。

---

## 6. 验证方式

- 空库跑 `001`–`009` → 结构、规则、留痕表齐全，日志无 ERROR；
- `008` / `009` 重复执行幂等，且不会重开管理员手工停用的规则；
- `POST /rules/execute` 用事实试算：命中、判不了（缺事实 / 不支持的算子）、无规则三种情况都要给得出原因；
- 报告重新归因两次，`rule_refs` 必须稳定（关键词不得因上一轮结论而增多）；
- 走一次 `analyze` → `confirm`，在库里核对 `rule_result` / `agent_suggestion` / `decision_log` 三张表用同一个 `run_id` 串起来。
