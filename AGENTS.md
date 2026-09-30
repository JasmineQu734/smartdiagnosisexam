# AGENTS.md — 项目背景与约束

本文件是本仓库的长期上下文：**先读这里，再动代码**。内容分四块——项目背景、规则引擎的既定契约、现状真相（基线）、硬约束与验证方式。

---

## 1. 项目背景

**是什么**：变电运维中心的「三层人才技能培训与考试管理系统」MVP。三层指 员工 → 组长（部长）→ 老总，管理员在旁边做平台配置与审计。

**现在做到哪**：按 `策划书.md` 第八章的开发顺序落地，1~5 步（主数据与权限、考试、个人系统、管理板块、实操任务）已完成，**当前正在做第 6 步：规则引擎**；第 7 步是 Agent 接口桩，第 8 步是种子数据跑通全流程。

**角色与数据边界**（改动任何接口前先确认没越界）：

| 账号 | 角色 | 范围 |
|---|---|---|
| `zhangwei` | EMPLOYEE | 只本人 |
| `limin` | TEAM_LEAD | 本人 + 本班组 |
| `wangzong` | EXECUTIVE | 全公司汇总 |
| `admin` | ADMIN | 平台数据与审计，不做业务决策 |

- 心理 / 关怀数据默认本人可见，授权心理专员可看，管理端只返回脱敏聚合。
- 安全不合格在人才决策中拥有最高优先级，并触发一票否决。
- 组长导入文档 / SOP 填报生成的候选题，必须经管理员审核后才入库。

**技术栈（不要替换）**：

- 后端：Spring Boot 3.5.16 + `spring-boot-starter-jdbc`（**JdbcTemplate，无 ORM**）+ SpringDoc OpenAPI，包名 `com.power.train`，`java.version=25`（本机 JDK 17 时构建加 `-Djava.version=17`）。
- 前端：Vue 3 + Vite + Element Plus，前端用相对路径 `/api/v1` 调接口，由 nginx 反代到 `backend:8080`。
- 数据库：**MySQL 8 一套库**（`train_system`），主数据、业务数据、Agent 结果、审计留痕、后台展示数据全部落库。
- 部署：`docker-compose.yml`（MySQL + API + Web）。

**目录**：

```text
backend/src/main/java/com/power/train/   Spring Boot 源码（按业务分包：report / material / persona / exam / rbac / store …）
backend/src/main/resources/application.yml
frontend/                                Vue 源码
db/init/                                 001_schema.sql 建库建表 → 002~007 种子，必须按序执行
docs/api-catalog.md                      接口总账（改接口必须同步这里）
docs/技术报告-现状核对与完善建议.md        文档与实现的差异清单、待办与优先级
策划书.md                                 原始需求，需求冲突时以它为准
README.md                                启动、建库、部署的唯一口径
```

启动、建库、部署、字体等细节**不要在别处复述**，只认 `README.md`。

---

## 2. 规则引擎的既定契约（只能实现，不能改）

这些是 `策划书.md` 与 `docs/api-catalog.md` 已经对外承诺的，属于契约；实现方式自由，但对外形状不能动。

**规则存储**——数据库 JSON 规则表，**不引入 Drools / Easy Rules 等外部规则框架**：

```sql
rule (rule_code, rule_name, scene, rule_group, condition_json, action_json,
      priority, enabled, stop_on_match, max_hits, status, remark, created_by/at, updated_by/at)
```

- `scene` 是规则适用的场景：`PERSONAL_GAP` / `EXAM_RESULT` / `TALENT_GAP`（个人与人才）+
  `REPORT_GAS`（气体检测归因，已接）+ `OPS_ATTRIBUTION` / `MATERIAL_CHECK`（待接）。
- 同一场景多条规则按 `priority` 从高到低匹配，`enabled=0` 的不参与。
- `rule_group` 是匹配分组：`stop_on_match` 只结束**本组**、`max_hits` 只限制**本组**命中条数；
  未分组的规则同属默认组（空串），老场景语义不变。分组是为了让「定档」和「关键词补充」各判各的。
- 条件算子白名单：比较 `eq/ne/gt/gte/lt/lte/between`、集合 `in/not_in`、
  文本 `contains/not_contains/contains_any/starts_with/ends_with`、布尔 `is_true/is_false/exists/missing`。
  **绝不使用 SpEL / eval / 脚本引擎 / 拼 SQL**（规则内容当不可信输入）。
- `action_json` 里以 `_from` 结尾的字段是「引用事实」，输出时换成该事实当前值
  （`{"cause_from":"gas_attribution"}`），这样一条规则能服务所有气体与档位。
- `verdict` 合并口径：`actions` / `causes` 去重保序，`severity` 取命中里**最严重**的一个。
- 规则示例（也是现有 6 条种子）：岗位要求 L3 当前 L1 → 推荐课程 + 带教 + 模拟考；考试 < 60 → 错题知识点复盘；关键岗位备份 < 2 → 预警；未来需求 > 现有人才 → 内部转岗 + 招聘 + 外委；实操超时且技能缺失 → 归因技能原因；未按 SOP 准备 → 归因人为 / 流程原因。

**接口**：

- 规则引擎：`/api/v1/rules`、`POST /api/v1/rules/execute`、`/api/v1/rules/results`，**只给管理员测试，前端不直接调用**。
- 三个 Agent 桩路径固定，一个字都不能改：
  - `POST /api/v1/agent/personal/recommend`
  - `POST /api/v1/agent/management/decision`
  - `POST /api/v1/agent/report/analyze`
- 统一请求 `{ agent_type, target_id, context, options }`；统一响应 `{ suggestion_id, agent_type, target_id, suggestions, confidence, source, need_human_confirm, status }`。
- 统一响应外层仍是 `{ code, message, data, trace_id }`；错误码 0 成功 / 401 未认证 / 403 无权限 / 404 不存在 / 409 状态冲突 / 500 系统错误；校验失败用 `code=40001` + `data.field_errors`。

**两条不可违背的铁律**：

1. **`source=rule` 现在，`source=model` 将来**：替换 Agent 模型时只换 Service 实现，Controller、DTO、接口路径、前端都不动。所以规则引擎必须放在 Service 层、由接口契约隔离，绝不能让 `source`、`agent_type` 等字段的形状随实现漂移。
2. **Agent 只出建议，绝不直接改业务数据**：所有建议写入 `agent_suggestion`（含 `confidence` / `source` / `need_human_confirm` / `status`），人工确认结果写入 `decision_log`；采纳、驳回、修改、执行、回滚全部留痕。结论必须**可解释到数据**——说清命中了哪条 `rule_code`、依据哪个数据点、为什么给这个动作。

---

## 3. 现状真相（动手前先读，别重复劳动也别假设已存在）

`docs/技术报告-现状核对与完善建议.md` 第 5 章列了文档与实现的差异清单。规则引擎相关的几条已被本轮实现修掉，下面是**当前真实状态**：

**已落地**：

- **引擎核心**（`db/init/008_rule_engine.sql` + `com.power.train.rule`）：`rule` 表由 `RuleEngine` 读库驱动，
  `rule_result` 落执行留痕，`/api/v1/rules/**` 已纳入管理员鉴权。
- **气体检测归因已接引擎**（`db/init/009_report_gas_rules.sql` + `ReportAttributionService`）：
  `ReportAnalysisService` 只负责选路（rule / model），规则分支交给适配层；
  报告 `analysis` 结构未变，`rule_refs` 是**真规则编号**（旧实现里的 `RULE-GAS-ABOVE` 之类是 Java 拼的假编号，已清掉）。
- **决策留痕链已通**：一次归因 = 一个 `run_id`，串起 `rule_result` → `agent_suggestion` →（人工确认）`decision_log`；
  确认接口在 `POST /api/v1/tasks/reports/{reportId}/attribution/confirm`（班组长，只改建议状态、不改业务数据）。

还没做的（别误以为已有）：

- **三个 Agent 桩仍是写死的**：`ApiController` 里 `/api/v1/agent/{agentType}/{action}` 返回固定的 3 条建议，
  **尚未接上 `RuleEngine`**。按约定**先不动**，等模型训练好再接（只换 Service 实现 + 把 `source` 从 `rule` 换 `model`）。
- **运营归因与资料校验还没接**：`OPS_ATTRIBUTION`（`CompanyController.runDiagnosis` 的 `inputs` 有 4 条与整段 `summary` 是硬编码文案）、
  `MATERIAL_CHECK`（只有抽取、没有校验）都没走引擎；接线方案见 `docs/rule-engine-integration.md`。
- **鉴权已改成令牌制**：`rbac/AuthToken` 签发 + `rbac/AuthFilter` 校验，`/api/v1/**` 除登录/登出/`/health` 外都要求 `Authorization: Bearer <token>`；
  `X-User` / `X-Role` 请求头不再被采信（`AuthFilter` 会把令牌里的身份投影给下游 `RoleInterceptor` / `Actor`，伪造失效）。
  `/agent/**`（按 `agent_type` 分派角色）与 `/reports/**`（员工+组长）也已纳入前缀鉴权，不再任意身份可调。
  这仍是 MVP：账号没有密码校验、没有刷新令牌，对外部署前必须接内网统一身份。
- 规则的增删改与启停开关（`POST /rules`、`POST /rules/{code}/toggle`）尚未提供接口，目前只能进库改。
- **`analysis_keyword_rule` 表已不再被运行期读取**（关键词规则迁进 `rule` 的 `REPORT_GAS` + `RULE-KW-*`）。
  表与种子数据保留（不做破坏性删除），但改那张表**不会**有任何效果。
- 表里还留着两条 `REPORT_ANALYSIS` 规则（`PRACTICE_SKILL_CAUSE` / `PRACTICE_HUMAN_CAUSE`），
  其中 `sop_preparation` 这个事实**全系统没有任何地方产生**；给它们补事实（或按新场景重写）是运营归因那一步的事。

已确认可用、可以直接用的基础设施：

- `store/Sql.java` 是统一数据访问助手：`rows` / `row` / `count` / `update` + `json` / `parse` / `parseList` / `parseStrings` / `rawJson` / `bool`。读写 JSON 列、判断布尔都走它，不要自己 new ObjectMapper。
- 模板与阈值类内容（`gas_rule` / `report_template_*`）由 `ReportTemplateLoader` 在启动时装载进 `ReportTemplate`，管理员改库即改模板与阈值——这是「配置入库、代码不硬编码」的既有范式，规则引擎照这个路子做。

---

## 4. 硬约束与验证

**硬约束**：

- **只用 MySQL**：不引入 PostgreSQL / Redis / 对象存储 / 消息队列；规则与结果都放 MySQL 的 JSON 列。
- **不用 ORM**：一律 JdbcTemplate + `Sql` 助手；SQL 写在 Service / Store 里，保持可读的 `SELECT`/`INSERT`。
- **表结构变更走 `db/init`**：新脚本编号往后排（当前到 `009_`），全部写成可重复执行（`CREATE TABLE IF NOT EXISTS` / `ON DUPLICATE KEY UPDATE`），**并同步更新 `README.md` 的脚本清单和 `docs/api-catalog.md`**。已有库补跑要能一次到位，不要要求删卷重建。
- **接口路径 / DTO 字段 / 表名不新增、不改名**：需求里点名要保留的表（含 `rule`、`rule_result`、`agent_suggestion`、`decision_log`）一个都不能少；改接口必须同步 `docs/api-catalog.md`。
- **前端只调业务接口和 `/api/v1/agent/*`**，绝不直连规则引擎。
- **AI 是可选增强**：`AI_ENABLED` 默认 `false`，规则引擎必须在完全离线时独立跑通；有 AI 时也是「AI 失败自动回退规则 + `fallback_note`」的既有模式，不允许把规则路径做成依赖 AI。
- **中文与编码**：注释、文档、`remark` 用中文；SQL 用 `utf8mb4`；PowerShell 读仓库里的中文文件必须带 `-Encoding UTF8`（默认编码会乱码，别据此判断文件内容）。
- **不要为了让流程跑通而绕过校验**：不删种子数据、不跳过必填校验、不硬编码结论冒充规则输出。

**验证方式**（改动规则引擎后按此顺序自验）：

1. 建库脚本：`db/init` 的脚本按序对空库跑一遍能一次到位（`README.md`「验收」一节的 `init-check` 流程），`docker logs` 无 ERROR，表数与脚本定义一致。
2. 后端构建：`backend` 下 `mvn -q -DskipTests package`；要跑起来就 `mvn spring-boot:run`，Swagger 在 `http://localhost:8080/swagger-ui.html`。
3. 规则引擎自验至少覆盖：启用/停用（`enabled`）、优先级覆盖（同场景多条 `priority` 冲突）、
   分组（`rule_group` + `stop_on_match` / `max_hits`）、`*_from` 引用事实、
   无匹配规则时的兜底输出、`condition_json` 字段缺失或类型不对时的行为、结果是否带上命中的 `rule_code` 与依据。
4. 鉴权自验：用非管理员身份调 `/api/v1/rules/**` 必须被拒（`403 / code=40301`）。
5. 幂等自验：`008` / `009` 重复执行不报错，且**不会重开管理员手工停用的规则**。
6. 回灌自验：同一份报告连续归因两次，`rule_refs` 必须一致（归因输入不含上一轮结论）。
7. 留痕自验：走一次 `analyze` → `confirm`，`rule_result` / `agent_suggestion` / `decision_log` 三张表能用同一个 `run_id` 串起来。
