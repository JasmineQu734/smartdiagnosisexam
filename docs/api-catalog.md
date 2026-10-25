# API、页面与初始数据清单

统一前缀 `/api/v1`，响应 `{ code, message, data, trace_id }`。列表接口预留 `page`、`size`、`sort`。

## 认证与主数据

`POST /auth/login`、`POST /auth/logout`、`GET /auth/me`；`/users`、`/roles`、`/orgs`、`/positions`、`/skills`、`/position-skills`、`/employee-skills`、`/courses`、`/course-skills`。

`POST /auth/login` body `{username, password}`，成功返回 `data.token`（服务端 HMAC 签名的令牌，默认 12 小时有效）+`data.token_type=Bearer`+`data.user`（`username` / `display_name` / `role` / `role_name` / `position` / `team` / `org` / `page_scope`）；账号不存在或密码错误统一返回 `401 账号或密码不正确`，账号 `status != ACTIVE` 返回 `403`。口令校验口径：`SHA-256(username + ':' + password)` 十六进制与 `app_user.password_hash` 比对，初始口令由 `db/init/013_login_password.sql` 写入（`123456`）。此后所有 `/api/v1/**` 请求（除登录、登出与 `/health`）都要带 `Authorization: Bearer <token>`，缺失或过期返回 `401`；请求头里的 `X-User` / `X-Role` 不再被采信。

## 个人系统

`GET /personal/profile`、`/skill-radar`、`/learning-summary`、`/gaps`、`/resources`、`/course-search`、`/learning-plan`、`/learning-records`、`/tasks`、`/tasks/{taskId}/reports`、`/exams`、`/certificates`。

### 员工六大板块（仅本人可见）

- 技能雷达：`GET /personal/skill-radar`，每项技能给出当前等级、岗位要求、公司未来需求与 `state`（达标 / 缺口 / 未来缺口）、`priority`、`note`。
- 个人自画像：`GET /personal/self-portrait`，基本信息 / 职业目标 / 发展意愿 / 自我评价 / 师傅评价 / 协作评价 / 岗位匹配度。
- 个人能力：`GET /personal/abilities`，硬技能 / 软技能 / 安全能力 / 实操能力 / 考试能力 / 证书能力。
- 记忆展示：`GET /personal/memories`，学习 / 错误 / 实操 / 考试 / 安全 / 带教 / 复盘七类记忆时间线。
- 成长轨迹：`GET /personal/growth`，技能等级、证书、考试、任务、培训、安全记录与晋升准备度。
- 差距与建议：`GET /personal/advice`（基线）+ `POST /personal/agent-diagnose`（实时个性化诊断：结论、差距、学习路径、复合型人才路线）、`GET /personal/agent-diagnose/latest`（读取最近一次结论）；诊断结果回写记忆库，记忆展示 / 成长轨迹等板块随即同步。
  - 结论来源：`source` 为 `rule`（内置规则结论兜底）或 `model`（大模型，配置 `ai.*` 后启用）；大模型未配置 / 调用失败 / 返回不符合输出契约时自动回退，并在 `fallback_note` 写明原因；`evidence_count` 为本次读取的事实条数，运行时字段（编号 / 时间 / 来源 / 证据数 / 同步板块）一律由后端写死，不采用模型输出。
  - 事实与校验：事实来自 MySQL（岗位技能要求、技能雷达、考试与错题、记忆库、学习计划、练习统计、证书、安全记录、实操报告）；结论正文中查不到出处的数字列在 `unverified_numbers`（软校验留痕，不拦截结论，同时把 `confidence` 压到 0.6 以内）。输出契约见 `docs/diagnosis_schema.json`。
- 推荐资源：`GET /personal/resources`，站内条目带 `jump` 跳转板块，外网条目带 `url` / `site`，新窗口打开公开资料站。
- 外网课程搜索（推荐资源窗口顶部）：`GET /personal/course-search?q=&platform=&skill=&level=`，四个条件都可空。返回 `external`（外网课程库命中，逐条带 `platform` / `site` / `type` / `duration` / `skill` / `level` / `tags` / `match_hits` / `score` / `gap_match` / `url`，最多 12 条）、`internal`（站内命中的推荐资源与 `course` 库课程，带 `jump`）、`platforms`（`external_course_source.search_url` 里的 `{kw}` 换成关键词后的实时检索直达链接，未填关键词时给 `home_url`）、`hot_keywords`（按本人技能缺口排序的检索词）、`gap_skills`、`catalog_size` / `external_total` / `took_ms` 与平台核验口径（`checked_at` / `platform_ok` / `platform_total`）。打分口径：标题 6 分 → 检索词 4 分 → 标签 / 技能 3 分 → 平台栏目 2 分 → 匹配理由 1 分；关键词为空时按技能缺口（`employee_skill`：`level < required_level`）排序。平台与课程来自 `external_course_source` / `external_course`（种子：`db/init/006_external_course.sql`，由 `tools/fetch-courses.mjs` 生成并核验各平台检索地址的 HTTP 状态）。
- 练习题：`GET /personal/practice/overview`（题库规模、按技能分布、我的正确率、练习记录）、`POST /personal/practice/draw`（Agent 按“技能缺口权重 × 历史正确率”分配题量并抽题，返回不含答案的题目与抽题说明）、`POST /personal/practice/submit`（判分、返回标准答案与解析，错题写入记忆库并调整下次抽题权重）。

以上接口只返回当前身份本人数据；令牌里的角色为 `EXECUTIVE` / `ADMIN` 时返回 `403 / code=40301`。

## 考试与实操

考试（管理员统一开考 ↔ 员工进入考试，共用同一份 `exam/ExamCenter` 状态）：`GET /personal/exams`（考试清单 + 本人记录，每场带 `open` / `can_enter` / `round_submitted` / `gate_status` / `status_note`）、`POST /exams/{examId}/start`（进入考试：管理员开考前返回 `opened=false`、`gate=NOT_OPEN` 不发卷；已交卷返回 `gate=SUBMITTED`）、`POST /exams/{examId}/submit`（body `{answers:{题号:"A"}}`，返回 `score` / `passed` / `wrong_points` 与逐题 `details`：题干 / 选项 / 我的作答 / 正确答案 / 解析 / 出处）。

- 门禁：员工「进入考试」读的就是管理员「考试配置」里的同一份状态，管理员未开考则前端按钮为不可点击的「等待管理员开考」，接口侧也直接拒绝发卷；`/exams/**` 仅员工 + 组长可调用，老总与管理员不参与答题。
- 前端三处入口：① 管理员「考试配置 → 考试清单」点「开始考试」；② 员工「学习与考试 → 考试中心」的「进入考试」按钮（管理员开考后出现，页面顶部另有开考横幅直接进第一场）；③ 进入后是整屏作答页：顶部答题卡显示每题作答状态、可跳题，剩余时间到点自动交卷，手动交卷若有未作答题目会先确认，交卷后同一页切到成绩与逐题解析。
- 前端对旧后端接口做了兜底：`can_enter` 缺失时按 `open` / `gate_status` / `status` 推导能否进入答题，避免升级过程中出现「管理员已开考但员工端没有进入考试按钮」。
- 组卷：题量取考试配置的 `question_count`，题目从题库按该场考试的技能抽取；题库不足时按实际题量发卷（响应里 `configured_count` 为配置值、`question_count` 为实际发卷数），`GET /admin/exams` 的 `available_questions` 即该范围内可抽题量。
- 现状题量：MVP 题库按技能分池（继电保护 / 倒闸操作 / 高压试验 / 安全规程 / 故障录波），故「继电保护理论考试」配置 20 题实际发 6 题、「高压试验安全规程考试」配置 15 题实际发 4 题。

实操任务与检测报告（已实现，MVP 为内存态，字段与 `task_report` 对齐）：

- `GET /personal/tasks`：个人任务列表，含填报状态（`report_id`、`judgment`、`severity`）。
- `GET /tasks/{taskId}/report-template`：报告模板框格定义（基础信息 / 检测数据 / 异常现象描述 / SOP 执行情况），每格含必填标记、填写示例、格式要求与气体阈值规则目录。
- `POST /tasks/{taskId}/submit-report`：按框格提交。校验失败返回 `code=40001` 与 `data.field_errors`（字段名与框格同名）；成功后生成 PDF/Word 文档、执行归因分析并返回报告详情。
- `GET /reports`、`GET /reports/{reportId}`：我的报告列表与详情（含 `analysis`、`document_text`、`sop_status` / `sop_deviation`）。
- `POST /reports/{reportId}/analyze`：重新执行归因分析。可选参数 `source=rule|model`（不传按配置自动选：配了 `ai.enabled` + `ai.api-key` 走大模型，否则走规则引擎）；取值非法返回 `code=40003`，强制 `model` 但没配大模型时回退规则引擎并在 `analysis.fallback_note` 说明。结论里带 `run_id`（本次执行编号）与 `suggestion_id`（待确认建议编号），可从报告反查到命中的规则与人工决定。
- `POST /tasks/reports/{reportId}/attribution/confirm`：人工确认归因结论（仅班组长）。body `{decision, reason}`，`decision` = `accept` 采纳 / `reject` 驳回 / `modify` 修改后采纳（缺失返回 `code=40001` + `data.field_errors`，取值非法返回 `code=40003`，驳回或修改不给 `reason` 也返回 `code=40003`）；没有待确认结论时返回 `404` 与 `code=40004`。效果是把 `agent_suggestion` 状态流转为 `ACCEPTED` / `REJECTED` / `MODIFIED` 并写一条 `decision_log`（留痕 `suggestion_id` / `decision_user` / `decision` / `reason` / 结论快照），**只改建议状态，不改业务数据**。
- `GET /reports/{reportId}/document?format=pdf|docx`：下载按框格渲染的报告文档；报告不存在时返回 `404` 与 `code=40004`（前端弹提示，不会存下内容损坏的文件）。文档每页都带页脚与「第 n 页 / 共 N 页」，归因列表按条目分行渲染。

文本框格约束：异常现象描述必填、15-300 字且必须包含具体时间或数值；检测地点需写到站所与设备间隔；已采取措施选填且不超过 200 字。SOP 执行情况必填且只接受 `FOLLOWED`（已按 SOP）/ `DEVIATED`（未按 SOP）/ `NOT_APPLICABLE`（本次无对应 SOP）三个取值，选「未按 SOP 执行」时偏差说明必填（≤200 字），取值与必填校验失败都返回 `code=40001` + `data.field_errors`（键为 `sop_status` / `sop_deviation`）。前端弹窗与后端校验使用同一套规则，保证 AI 读到的文本结构一致。

## 管理、规则、Agent、审计

管理看板：`/management/dashboard`、`/skill-matrix`、`/training`、`/exams`、`/tasks`、`/costs`、`/talent-gap`、`/succession`、`/key-position-backup`、`/safety`、`/care`、`/decisions`。

规则引擎（只给管理员，前端不直接调用；规则是 MySQL `rule` 表里的声明式 JSON，条件算子白名单与优先级语义见 `docs/rule-engine-design.md`）：

- `GET /rules?scene=&enabled=`：规则清单，返回 `rule_code` / `rule_name` / `scene` / `rule_group`（匹配分组） / `condition` / `action` / `priority` / `enabled` / `stop_on_match`（只停本组） / `max_hits`（本组命中上限，0=不限） / `status` / `remark`。
- `POST /rules/execute`：规则试算。body `{scene, target_id, facts, options}`，`scene` 与 `facts` 必填（校验失败 `code=40001` + `data.field_errors`）。返回 `run_id`、`matched`、`hits`（每条含 `rule_code` / `priority` / `condition_hit` / `actions` / `explanation`）、`skipped`（判不了的规则 + `skipped_reason`）、`verdict`（`actions` / `causes` / `cause` / `severity`（取命中里最严重的一个） / `rule_refs` / `confidence`）、`explanation`、`unmatched_reason`、`source=rule`、`need_human_confirm=true`。`options.persist=true` 时才写 `rule_result` 留痕，默认只算不落库。
- `GET /rules/results?scene=&target_id=&from=&to=&page=&size=`：执行留痕倒序分页，返回 `total` / `page` / `size` / `items`（`run_id` / `matched` / `hit_count` / `matched_rules` / `verdict` / `explanation` / `confidence` / `suggestion_id` / `executed_by` / `created_at`）。

建议管理：`/agent/suggestions`、`/agent/suggestions/{id}`、`/accept`、`/reject`、`/confirm`、`/execute`、`/rollback`。决策与审计：`/decisions`、`/audit/logs`。文件与通知：`/files/upload`、`/files/{id}`、`/notifications`、`/notifications/read`、`/notifications/send`。

### 角色数据边界

- 组长导入文档生成练习资料（与 SOP 填报同一条审核链）：`GET /team/materials/template`（导入说明：可识别格式 / 上限 20MB / 入库目标 / 四步流程）、`POST /team/materials/upload`（multipart：`file` + `target`（题库 / 课程库）+ `skill` / `level` / `version` / `title` / `note`；Agent 读原件正文，题库目标识别「题干 + 选项 + 答案 + 解析」并带出处（第 N 页 / 段 / 工作表行），课程库目标整理知识章节与学时；校验失败返回 `code=40001` 与 `data.field_errors`）、`GET /team/materials`（本班组导入台账：`summary` 待审核 / 已入库计数 + `items` 每批 `pending_items` / `stored_items` / `status`）、`GET /team/materials/{code}`（批次详情：`material` 台账 + `file` 原件信息与留档路径 + `doc_excerpt` 正文摘录 + `extracted.items` 候选题逐条状态与入库题号）。导入只生成「待审核」候选题，管理员审核通过后才写入题库 / 课程库，员工抽题才抽得到。
- 组长：`GET /team/overview`（班组人员、技能达标与缺报清单）、`GET /team/reports`（实操报告台账：库里的历史台账 + `task_report` 实时报告，同一报告编号只出现一行；台账行引用的报告若不在库中则不下发 `document_pdf`，避免下载链接指向不存在的报告）、`GET /team/sop/template`（SOP 生成练习资料的规定模板：基础信息 / 作业步骤 / 判定标准 / 考核要点 / 风险点）、`POST /team/sop/generate`（校验必填后由 Agent 解析成候选题并提交管理员审核，返回 `material_code` / `status=待审核` / 候选题与题库总量）。
- 老总（人才驾驶舱）：`GET /exec/company-overview`（关键指标 6 项 + `cost` 用人成本（四类支出年度累计 + `trend` 月度发生额趋势） + `talent_gap` 人才缺口 + `by_team` 班组概览 + `report_signal` 组长报告信号 + `talent_risk` 安全/稳定性/证书风险）、`GET /exec/skill-matrix`（`level_distribution` 等级分布、`skills` 技能达标矩阵、`teams` 班组维度、`key_posts` 关键岗位备份 + `single_point_posts` 单点依赖岗位数、`strong` / `focus` 强弱名单）、`GET /exec/training-board`（`completion` 完成率、`cost` 成本结构、`effect` 培训效果、`roi` 投入产出测算、`departments` 部门对比、`plans` 个人学习计划执行）、`GET /exec/diagnosis`（输入口径基线）、`POST /exec/agent-diagnose`（点击运行实时生成报告：`diagnosis_id`、`ran_at`、`verdict` 归因、`findings` 问题清单、`actions` 建议措施、`cost_summary` 降本测算、`updated_modules` 同步板块，`need_human_confirm=true`）、`GET /exec/agent-diagnose/latest`（读回最近一次结论，未运行过返回 `has_diagnosis=false` 与引导）。
  - 结论来源与校验：`source` 为 `rule`（内置规则结论兜底）或 `model`（大模型）；大模型未配置 / 调用失败 / 返回不符合输出契约时自动回退并在 `fallback_note` 写明原因；`inputs` 由本次事实来源反推（不再硬编码），`evidence_count` 为本次事实条数；结论正文中查不到出处的数字列在 `unverified_numbers` 并把 `confidence` 压到 0.6 以内。输出契约见 `docs/diagnosis_schema.json`。
- 管理员（系统管理员后台）用户与权限：`GET /admin/overview`、`/admin/employees`、`/admin/iam`（用户 + 角色）、`/admin/orgs`、`/admin/positions`、`/admin/permissions`。
- 管理员技能与课程：`GET /admin/skills`、`/admin/position-skills`（岗位/技能/等级为平台内部刻度；依据标准引用真实国标并可点开官网核对）、`/admin/standards`（标准依据库，数据抓取自国家标准全文公开系统 openstd.samr.gov.cn）、`/admin/courses`、`/admin/course-skill-links`、`/admin/question-banks`。
- 管理员资料上传与审核：`GET /admin/course-materials`、`POST /admin/course-materials`（规定格式 `技能编码_名称_等级_版本.pdf`，校验失败返回 `code=40001` 与 `data.field_errors`；通过后由课程 Agent 识别条目，状态为待审核）、`GET /admin/course-materials/{code}`（待审核详情：原件信息 `file` + 原件摘录 `doc_excerpt` + Agent 检索结果 `extracted`（题库→题目 / 答案 / 解析，课程库→知识章节），仅检索不入库）、`POST /admin/course-materials/review`（body `{code, action, approve_ids?, reject_ids?}`：approve 才写入课程库或累加题库题量，reject 不入库；组长导入 / SOP 填报的批次在 `material_item` 里有逐条台账，可只传勾选的 `approve_ids` 部分通过，未勾选的继续留在待审核，返回 `stored_count` / `pending_items` / `stored_result`）、`POST /admin/courses/review`（待审核课程直接上线或驳回）。
- 管理员考试配置与统一开考：`GET /admin/exam-config`（组卷规则 / 防作弊规则 / 评分规则 / 及格线）、`GET /admin/exams`（考试清单 + `available_questions` 题库可抽 / `entered` 已进入 / `submitted` 已交卷）、`POST /admin/exams/start`（统一开考：把该场置为「进行中」并记录真实开考人，返回 `started` / `started_at` / `started_by`，员工端随即出现可点的「进入考试」；未启用考试返回 `started=false` 并提示先启用）、`GET /admin/papers`、`POST /admin/papers/issue`（按批次发放试卷：`exam_id` / `scope` / `count`（1-9999 份）/ `deadline`（yyyy-MM-dd）均必填，校验失败返回 `code=40001` 与 `data.field_errors`；成功后累加该场 `paper_batches`）。
- 结束本场：`POST /admin/exams/close`（body `{exam_id}`）把进行中的考试置为「已结束」并清空本轮作答记录，员工端随即不再出现「进入考试」；返回 `closed` / `entered` / `submitted`。再次 `POST /admin/exams/start` 即开启新一轮并重新发卷，历史成绩仍保留在考试记忆中。
- 管理员审计与审核：`GET /admin/audit?category&keyword&from&to`（登录 / 修改 / 审批 / 决策 / 执行 / 回滚分类统计与条件搜索）、`POST /admin/audit/clear`（需 `confirm=true`，清空历史留痕并保留 1 条清除记录）。

鉴权分两层。先认证（`rbac/AuthFilter`）：`/api/v1/**` 除 `POST /auth/login`、`POST /auth/logout`、`GET /health` 外一律要求合法令牌，缺失或过期返回 `401`，身份取自令牌、请求头不再可信。再按路径前缀授权（`rbac/RoleInterceptor`）：`/personal/**` 与 `/exams/**` → 员工 + 组长；`/team/**` → 组长；`/tasks/**` → 仅组长（检测报告填报）；`/reports/**` → 员工 + 组长（查看与下载报告）；`/management/**` 与 `/exec/**` → 老总；`/admin/**` → 管理员；`/rules/**` → 管理员（规则引擎）；`/agent/personal/**` → 员工 + 组长、`/agent/management/**` → 老总、`/agent/report/**` → 组长、其余 `/agent/**` → 管理员。越权统一 `403 / code=40301`，`data` 内含 `role` 与 `scope`。

三个稳定 Agent 桩：

- `POST /api/v1/agent/personal/recommend`
- `POST /api/v1/agent/management/decision`
- `POST /api/v1/agent/report/analyze`

请求统一为 `{ agent_type, target_id, context, options }`，响应包含 `suggestion_id`、`suggestions`、`confidence`、`source`、`need_human_confirm`、`status`。当前 `source=rule`。

实现说明（2026-10-17，契约未变）：`ApiController` 只做一行委托，分派逻辑在 `agent/AgentDispatchService`。
`personal/recommend` 逐技能执行 `PERSONAL_GAP`（事实来自 `employee_skill`，建议文案带 `rule_code`）；
`management/decision` 用 `position.backup_count` / `headcount` 与 `app_user` 在岗一线人数（`EMPLOYEE` + `TEAM_LEAD`）执行 `TALENT_GAP`；
`report/analyze` 按 `target_id` 或 `context.report_id` 复用 `ReportAttributionService` 执行 `REPORT_GAS`。
每次调用都写 `rule_result`（`run_id`）与 `agent_suggestion`（`suggestion_id = run_id`），
无命中时返回 `0.30` 置信度并写明原因，不返回写死文案。

## 前端页面
登录页；员工侧：技能雷达、个人自画像、个人能力、记忆展示、成长轨迹、差距与建议、学习与考试（学习总版 + 考试中心）、实操任务与报告填报（标准化框格表单）；组长侧：员工全部板块 + 班组报告；老总侧：人才驾驶舱、全公司技能矩阵、培训看板、运行诊断 Agent；管理员侧四个板块（左侧导航切换，无页内标签）：用户与权限（平台数据规模、用户与角色、组织、岗位与备份、权限矩阵、员工档案）、技能与课程（上传资料 + Agent 识别 + 资料/课程审核：待审核行点开弹窗查看原件信息、原件摘录与 Agent 检索出的题目（题干 / 选项 / 答案 / 解析）或知识章节，管理员核对后点「确认入库」才写入课程库 / 题库；岗位技能要求（依据真实国标，可点开国家标准全文公开系统核对）、标准依据库（官网抓取）、技能字典、题库、课程技能关联）、考试配置（考试清单统一开考、发放试卷、组卷/防作弊/评分/及格线）、审计与审核（按类别、关键词、时间范围搜索，清除筛选与清除留痕）。

## 初始规则与演示数据

规则见 `db/init/002_seed.sql`（`008` 已把 6 条改写成声明式条件）：技能等级缺口、考试低分、关键岗位备份不足、未来需求缺口、实操技能原因、未按 SOP 的人为/流程原因。
气体检测归因规则见 `db/init/009_report_gas_rules.sql`（场景 `REPORT_GAS`，共 12 条：`VALUE` 组按余量档位定档 5 条 + `KEYWORD` 组按报告正文关键词补原因 7 条）；
关键词规则已迁进 `rule` 表，`analysis_keyword_rule` 表保留但运行期不再读取。演示数据包含张伟的继保 L1、倒闸 L3、高压试验 L1，继保考试 62 分，以及李民组长、王总和四类角色。
