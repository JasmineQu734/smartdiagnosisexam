SET NAMES utf8mb4;
-- 后台展示数据集的口径补充（在 003 之后执行，用于修正与新增口径字段）
USE train_system;

-- ---------- 标准依据：官网核对字段（标准号、状态、日期与详情页链接取自国家标准全文公开系统） ----------
UPDATE standard_ref SET page_standard = std_no, http_code = 200,
  date_note = IF(std_no = 'GB 26860-2011', '实施日期取自该系统标准查询列表页（详情页未单列）', '')
WHERE page_standard = '' OR page_standard IS NULL;

-- ---------- 系统管理员：员工档案台账（展示口径，随平台数据维护） ----------
INSERT INTO dataset_meta (dataset_key, payload) VALUES
  ('admin.employees', '[{"emp_no":"E1001","name":"张伟","team":"变电运维一班","position":"变电运维值班员","account_role":"员工","skill_level":"继保 L1 / 倒闸 L3","certificates":2,"status":"在职","last_active":"2026-09-19"},{"emp_no":"E1002","name":"李民","team":"变电运维一班","position":"班组长","account_role":"组长（员工）","skill_level":"继保 L3 / 高压 L2","certificates":3,"status":"在职","last_active":"2026-09-19"},{"emp_no":"E1003","name":"周强","team":"变电运维一班","position":"值班员","account_role":"员工","skill_level":"倒闸 L2","certificates":1,"status":"在职","last_active":"2026-09-18"},{"emp_no":"E2001","name":"王总","team":"中心管理层","position":"分管老总","account_role":"公司上级","skill_level":"-","certificates":0,"status":"在职","last_active":"2026-09-15"},{"emp_no":"E9001","name":"系统管理员","team":"信息中心","position":"系统管理员","account_role":"系统管理员","skill_level":"-","certificates":0,"status":"在职","last_active":"2026-09-20"},{"emp_no":"E1004","name":"刘洋","team":"变电运维一班","position":"值班员","account_role":"员工","skill_level":"继保 L2","certificates":2,"status":"在职","last_active":"2026-09-17"}]')
ON DUPLICATE KEY UPDATE payload = VALUES(payload);

-- ---------- 班组口径：补上待确认报告数（组长侧「待确认」卡片） ----------
UPDATE dataset_meta SET payload = JSON_SET(payload, '$.pending_confirm', 1) WHERE dataset_key = 'team.profile';

-- ---------- 平台服务状态：数据库只用 MySQL，不再依赖对象存储与消息队列 ----------
UPDATE dataset_meta SET payload = JSON_SET(payload, '$.service_status', '运行正常（API / MySQL 数据库）')
WHERE dataset_key = 'admin.overview';

-- ---------- 个性化 Agent 诊断的基线口径（诊断接口只补诊断编号、时间与实时证据条数） ----------
INSERT INTO dataset_meta (dataset_key, payload) VALUES
  ('personal.diagnosis.core', '{"source":"rule","source_label":"个人学习 Agent（规则引擎 v1）","confidence":0.86,"need_human_confirm":true,"summary":"结合技能雷达、考试错题、实操超时、师傅评价与记忆库实时判断：当前属于“在岗技能不足”而不是“能力空白”——继电保护 L1→L3 是最大缺口，软压板逻辑是考试、实操、带教三处证据的共同诱因；高压试验 L1 缺独立开展记录，是复合型发展的第二块拼图。","verdict":{"headline":"在岗技能不足为主：继电保护 L1→L3 是最大缺口，软压板逻辑是共同诱因","reasons":["继电保护岗位要求 L3，当前 L1；理论考试 62 分，低于合格线 80 分","110kV 定值核对超时 2 小时，问题指向定值准备与软压板投退顺序","师傅评价：动手能力强、二次回路查线快，但软压板逻辑偏弱","高压试验仅参与 2 次、未独立开展，而公司未来需求是 L3"]},"gaps":[{"skill":"继电保护","current":1,"required":3,"future":3,"severity":"HIGH","priority":"P1","impact":"定值类工作仍需师傅把关，无法独立跟班","action":"补《软压板逻辑》微课 → 带教 2 次 → 模拟考 ≥80 分 → 报名补考"},{"skill":"高压试验","current":1,"required":2,"future":3,"severity":"MEDIUM","priority":"P2","impact":"高压试验依赖外委，班组排班机动性差","action":"安全规程考试 → 跟班 2 次 → 独立开展 SF6 微水与气体检测"},{"skill":"故障录波","current":1,"required":2,"future":2,"severity":"MEDIUM","priority":"P3","impact":"能读波形但不能独立分析原因，事故复盘参与度低","action":"精读 3 份典型录波案例 → 参与 1 次故障分析会"}],"plan":[{"step":1,"kind":"课程","title":"《软压板逻辑》微课 + 定值核对 SOP","target_skill":"继电保护","to_level":"L2","due_at":"2026-09-30","reason":"考试错题与实操超时同源，先把认知补上"},{"step":2,"kind":"带教","title":"王建国师傅带教定值核对 2 次并独立复核 1 次","target_skill":"继电保护","to_level":"L2","due_at":"2026-10-12","reason":"薄弱点已明确，必须现场带教闭环"},{"step":3,"kind":"模拟考","title":"继电保护理论模拟考 ≥80 分后报名补考","target_skill":"继电保护","to_level":"L3","due_at":"2026-10-20","reason":"补考机会仅 1 次，先达标再报名"},{"step":4,"kind":"课程","title":"高压试验安全规程考试 + 跟班实操 2 次","target_skill":"高压试验","to_level":"L2","due_at":"2026-11-15","reason":"为复合型路线铺第二技能"}],"compound_path":{"title":"复合型人才路线：继电保护（主）+ 高压试验（辅）","why":"班组继保只有 2 人能独立工作、高压试验 1 人即将退休；只补继保只能顶一个岗，继保 + 高压双线发展才能同时覆盖两类停电检修任务，这也是“复合型人才”在本班组的落地形态。","stages":[{"phase":"第 1 阶段 · 0-2 个月","focus":"补继保 L2 基础","skills":"软压板逻辑 / 定值核对 SOP","milestone":"模拟考 ≥80 分，师傅复核 1 次独立完成"},{"phase":"第 2 阶段 · 2-6 个月","focus":"继保 L2 → L3","skills":"二次回路分析 / 故障录波读图","milestone":"补考通过，独立跟班 2 次"},{"phase":"第 3 阶段 · 6-12 个月","focus":"高压试验 L1 → L2","skills":"SF6 微水 / 气体检测 / 有限空间作业","milestone":"独立开展高压试验 2 次并出具报告"},{"phase":"第 4 阶段 · 12 个月后","focus":"复合型值班员","skills":"继保 + 高压试验双岗覆盖","milestone":"覆盖两类停电检修任务，减少外委 2 人次/月"}],"benefit":"预计每年减少外委与加班成本约 ¥3.6 万，班组排班机动性提升"},"updated_modules":["技能雷达","个人能力","记忆展示","成长轨迹","学习与考试","差距与建议"]}')
ON DUPLICATE KEY UPDATE payload = VALUES(payload);

-- ---------- 练习题抽题策略：技能缺口权重与理由（Agent 按此分配题量） ----------
INSERT INTO dataset_item (dataset_key, item_key, sort_no, payload) VALUES
  ('practice.gap-rules', '继电保护', 1, '{"skill":"继电保护","weight":3.0,"reason":"缺口 P1：岗位要求 L3、当前 L1，理论考试未过线"}'),
  ('practice.gap-rules', '高压试验', 2, '{"skill":"高压试验","weight":2.0,"reason":"缺口 P2：公司未来需求 L3，当前未独立开展"}'),
  ('practice.gap-rules', '故障录波', 3, '{"skill":"故障录波","weight":2.0,"reason":"缺口 P3：能读波形但不能独立分析原因"}'),
  ('practice.gap-rules', '倒闸操作', 4, '{"skill":"倒闸操作","weight":1.0,"reason":"已达标 L3，按巩固节奏少量出题"}'),
  ('practice.gap-rules', '安全规程', 5, '{"skill":"安全规程","weight":1.0,"reason":"已达标，防遗忘巩固"}')
ON DUPLICATE KEY UPDATE sort_no = VALUES(sort_no), payload = VALUES(payload);

-- ---------- 技能雷达只展示岗位关键技能：故障录波只在个人能力的硬技能里出现 ----------
UPDATE employee_skill SET in_radar = 0 WHERE skill = '故障录波';