SET NAMES utf8mb4;
-- 三层人才技能培训与考试管理系统 · MySQL 8+ 结构（系统唯一数据库）
-- 主数据、业务数据、Agent 结果、审计留痕与后台展示数据集全部落在 MySQL。
CREATE DATABASE IF NOT EXISTS train_system
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;
USE train_system;

-- ---------- 1. 主数据：用户 / 角色 / 组织 / 岗位 / 技能 ----------
CREATE TABLE IF NOT EXISTS app_user (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL UNIQUE,
  display_name VARCHAR(64) NOT NULL,
  password_hash VARCHAR(200) NOT NULL DEFAULT '',
  role_code VARCHAR(32) NOT NULL DEFAULT 'EMPLOYEE',
  role_name VARCHAR(64) NOT NULL DEFAULT '员工',
  position VARCHAR(128) NOT NULL DEFAULT '',
  team VARCHAR(128) NOT NULL DEFAULT '',
  org VARCHAR(128) NOT NULL DEFAULT '',
  page_scope VARCHAR(32) NOT NULL DEFAULT 'PERSONAL',
  status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
  last_login VARCHAR(32) NOT NULL DEFAULT '—',
  remark TEXT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS role (
  code VARCHAR(32) PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  scope VARCHAR(64) NOT NULL,
  modules INT NOT NULL DEFAULT 0,
  members INT NOT NULL DEFAULT 0,
  note TEXT,
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS org (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(128) NOT NULL UNIQUE,
  org_type VARCHAR(16) NOT NULL,
  parent VARCHAR(128) NOT NULL DEFAULT '—',
  headcount INT NOT NULL DEFAULT 0,
  leader VARCHAR(64) NOT NULL DEFAULT '—',
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS position (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(128) NOT NULL UNIQUE,
  org VARCHAR(128) NOT NULL,
  required_level VARCHAR(64) NOT NULL,
  key_post TINYINT(1) NOT NULL DEFAULT 0,
  headcount INT NOT NULL DEFAULT 0,
  backup_count INT NOT NULL DEFAULT 0,
  risk VARCHAR(16) NOT NULL DEFAULT 'LOW',
  note TEXT,
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS skill (
  code VARCHAR(32) PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  levels VARCHAR(200) NOT NULL,
  course_count INT NOT NULL DEFAULT 0,
  requirement_count INT NOT NULL DEFAULT 0,
  note TEXT,
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

-- 员工技能：技能雷达与个人能力硬技能共用（level/required/future + 结论与证据）
CREATE TABLE IF NOT EXISTS employee_skill (
  username VARCHAR(64) NOT NULL,
  skill VARCHAR(128) NOT NULL,
  level INT NOT NULL DEFAULT 0,
  required_level INT NOT NULL DEFAULT 0,
  future_level INT NOT NULL DEFAULT 0,
  level_label VARCHAR(8) NOT NULL DEFAULT '',
  required_label VARCHAR(8) NOT NULL DEFAULT '',
  future_label VARCHAR(8) NOT NULL DEFAULT '',
  state VARCHAR(32) NOT NULL DEFAULT '',
  priority VARCHAR(8) NOT NULL DEFAULT '',
  radar_note VARCHAR(300),
  trend VARCHAR(16) NOT NULL DEFAULT 'FLAT',
  evidence VARCHAR(300),
  in_radar TINYINT(1) NOT NULL DEFAULT 1,
  sort_no INT NOT NULL DEFAULT 0,
  PRIMARY KEY (username, skill)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS position_skill_requirement (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  position VARCHAR(128) NOT NULL,
  skill VARCHAR(128) NOT NULL,
  required_level VARCHAR(16) NOT NULL,
  future_level VARCHAR(16) NOT NULL,
  basis_role VARCHAR(32) NOT NULL,
  standard_no VARCHAR(64) NOT NULL,
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS standard_ref (
  std_no VARCHAR(64) PRIMARY KEY,
  name VARCHAR(300) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT '现行',
  published VARCHAR(32) NOT NULL DEFAULT '—',
  implemented VARCHAR(32) NOT NULL DEFAULT '—',
  detail_url VARCHAR(300) NOT NULL DEFAULT '',
  page_standard VARCHAR(64) NOT NULL DEFAULT '',
  http_code INT NOT NULL DEFAULT 200,
  date_note VARCHAR(200) NOT NULL DEFAULT '',
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS standard_source (
  id TINYINT PRIMARY KEY,
  source VARCHAR(128) NOT NULL,
  source_url VARCHAR(300) NOT NULL,
  fetched_at VARCHAR(32) NOT NULL,
  note TEXT
) ENGINE=InnoDB;

-- ---------- 2. 课程 / 题库 ----------
CREATE TABLE IF NOT EXISTS course (
  code VARCHAR(64) PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  course_type VARCHAR(32) NOT NULL,
  hours DECIMAL(6,2) NOT NULL DEFAULT 0,
  skill VARCHAR(128) NOT NULL,
  target_level VARCHAR(16) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT '已上线',
  materials INT NOT NULL DEFAULT 0,
  source_file VARCHAR(300),
  reviewed_by VARCHAR(64),
  reviewed_at VARCHAR(32),
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS course_skill_link (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  course VARCHAR(200) NOT NULL,
  skill VARCHAR(128) NOT NULL,
  target_level VARCHAR(16) NOT NULL,
  link_type VARCHAR(16) NOT NULL,
  weight VARCHAR(8) NOT NULL,
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS course_material (
  code VARCHAR(32) PRIMARY KEY,
  title VARCHAR(200) NOT NULL,
  skill VARCHAR(128) NOT NULL,
  skill_code VARCHAR(32) NOT NULL,
  target VARCHAR(16) NOT NULL,
  material_type VARCHAR(32) NOT NULL,
  file_name VARCHAR(300) NOT NULL,
  file_type VARCHAR(16) NOT NULL,
  target_level VARCHAR(16) NOT NULL,
  version VARCHAR(16) NOT NULL,
  hours DECIMAL(6,2),
  recognized_items INT NOT NULL DEFAULT 0,
  agent_confidence DECIMAL(4,2) NOT NULL DEFAULT 0,
  agent_note VARCHAR(500),
  status VARCHAR(16) NOT NULL DEFAULT '待审核',
  submitted_by VARCHAR(64) NOT NULL,
  submitted_at VARCHAR(32) NOT NULL,
  file_url VARCHAR(400),
  source VARCHAR(64),
  note VARCHAR(300),
  stored_result VARCHAR(300),
  reviewed_by VARCHAR(64),
  reviewed_at VARCHAR(32),
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS question_bank (
  code VARCHAR(32) PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  skill VARCHAR(128) NOT NULL,
  questions INT NOT NULL DEFAULT 0,
  types VARCHAR(200) NOT NULL,
  difficulty VARCHAR(16) NOT NULL,
  updated_at VARCHAR(32) NOT NULL,
  used_by INT NOT NULL DEFAULT 0,
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

-- 练习题题库：内置题与组长 SOP 生成的题目共用一张表
CREATE TABLE IF NOT EXISTS question (
  id VARCHAR(32) PRIMARY KEY,
  skill VARCHAR(128) NOT NULL,
  level INT NOT NULL DEFAULT 1,
  qtype VARCHAR(16) NOT NULL,
  stem TEXT NOT NULL,
  options JSON NOT NULL,
  answer VARCHAR(8) NOT NULL,
  explanation TEXT,
  source VARCHAR(200) NOT NULL,
  used_count INT NOT NULL DEFAULT 0,
  sort_no INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_question_skill (skill)
) ENGINE=InnoDB;

-- 资料解析台账：组长上传文档 / 按 SOP 模板填报后，原件信息与 Agent 读到的正文（摘录）落在这里，
-- 管理员审核时逐条核对「Agent 读到的原文」与「识别出的题目」是否对得上。
CREATE TABLE IF NOT EXISTS material_doc (
  material_code VARCHAR(32) PRIMARY KEY,
  file_name VARCHAR(300) NOT NULL,
  file_type VARCHAR(16) NOT NULL,
  pages INT NOT NULL DEFAULT 0,
  size_kb INT NOT NULL DEFAULT 0,
  char_count INT NOT NULL DEFAULT 0,
  stored_path VARCHAR(400),
  extract_note VARCHAR(300),
  agent_mode VARCHAR(32) NOT NULL,
  text_excerpt TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Agent 识别出的候选题 / 候选章节：状态为「待审核」时只挂在资料台账上，
-- 管理员审核通过才写入 question（题库）或 course（课程库），普通员工随后即可抽到。
CREATE TABLE IF NOT EXISTS material_item (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  material_code VARCHAR(32) NOT NULL,
  seq INT NOT NULL,
  kind VARCHAR(8) NOT NULL,
  qtype VARCHAR(16),
  skill VARCHAR(128) NOT NULL,
  level INT NOT NULL DEFAULT 1,
  stem VARCHAR(800),
  options JSON,
  answer VARCHAR(8),
  explanation TEXT,
  chapter VARCHAR(200),
  points VARCHAR(800),
  hours DECIMAL(4,1),
  source_ref VARCHAR(200),
  confidence DECIMAL(4,2) NOT NULL DEFAULT 0,
  status VARCHAR(16) NOT NULL DEFAULT '待审核',
  question_id VARCHAR(32),
  reviewed_by VARCHAR(64),
  reviewed_at VARCHAR(32),
  KEY idx_material_item_code (material_code, seq),
  KEY idx_material_item_status (status)
) ENGINE=InnoDB;

-- 上传资料的知识点池（Agent 检索结果的来源内容）
CREATE TABLE IF NOT EXISTS knowledge_point (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  skill VARCHAR(128) NOT NULL,
  point VARCHAR(200) NOT NULL,
  statement VARCHAR(600) NOT NULL,
  sort_no INT NOT NULL DEFAULT 0,
  KEY idx_knowledge_skill (skill)
) ENGINE=InnoDB;

-- ---------- 3. 考试 ----------
CREATE TABLE IF NOT EXISTS exam (
  exam_id VARCHAR(16) PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  exam_type VARCHAR(16) NOT NULL,
  skill VARCHAR(128) NOT NULL,
  pass_score INT NOT NULL DEFAULT 60,
  question_count INT NOT NULL DEFAULT 10,
  duration_minutes INT NOT NULL DEFAULT 30,
  bank VARCHAR(200) NOT NULL,
  scope VARCHAR(200) NOT NULL,
  participants INT NOT NULL DEFAULT 0,
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  status VARCHAR(16) NOT NULL DEFAULT '未开始',
  started_at VARCHAR(32) NOT NULL DEFAULT '—',
  started_by VARCHAR(64) NOT NULL DEFAULT '—',
  ended_at VARCHAR(32),
  paper_batches INT NOT NULL DEFAULT 0,
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

-- 本轮考试状态：管理员开考后员工进入答题，关闭本场即清空；历史成绩另存 exam_history
CREATE TABLE IF NOT EXISTS exam_round (
  username VARCHAR(64) NOT NULL,
  exam_id VARCHAR(16) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'IN_PROGRESS',
  question_ids JSON NOT NULL,
  session_id VARCHAR(64) NOT NULL,
  started_at VARCHAR(32) NOT NULL,
  total INT NOT NULL DEFAULT 0,
  score INT,
  correct INT,
  result VARCHAR(16),
  submitted_at VARCHAR(32),
  wrong_points JSON,
  PRIMARY KEY (username, exam_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS exam_history (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL,
  exam_id VARCHAR(16) NOT NULL,
  exam_name VARCHAR(200) NOT NULL,
  score INT NOT NULL,
  pass_score INT NOT NULL,
  result VARCHAR(16) NOT NULL,
  submitted_at VARCHAR(32) NOT NULL,
  wrong_points JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_history_user (username, id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS paper_batch (
  batch_no VARCHAR(32) PRIMARY KEY,
  exam_id VARCHAR(16) NOT NULL,
  exam_name VARCHAR(200) NOT NULL,
  issued_to VARCHAR(200) NOT NULL,
  paper_count INT NOT NULL DEFAULT 0,
  issued_at VARCHAR(32) NOT NULL,
  deadline VARCHAR(16) NOT NULL,
  collected INT NOT NULL DEFAULT 0,
  status VARCHAR(16) NOT NULL DEFAULT '已发放',
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

-- ---------- 4. 学习 / 任务 / 报告 ----------
CREATE TABLE IF NOT EXISTS learning_summary (
  username VARCHAR(64) PRIMARY KEY,
  month_hours DECIMAL(6,1) NOT NULL DEFAULT 0,
  target_hours DECIMAL(6,1) NOT NULL DEFAULT 0,
  completion INT NOT NULL DEFAULT 0,
  required_done INT NOT NULL DEFAULT 0,
  required_total INT NOT NULL DEFAULT 0,
  streak_days INT NOT NULL DEFAULT 0,
  last_exam_name VARCHAR(200),
  last_exam_score INT,
  last_exam_pass_score INT,
  focus_skill VARCHAR(128),
  mentor_sessions INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS learning_plan (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL,
  course_code VARCHAR(64) NOT NULL,
  course_name VARCHAR(200) NOT NULL,
  course_type VARCHAR(32) NOT NULL,
  hours DECIMAL(6,1) NOT NULL DEFAULT 0,
  progress INT NOT NULL DEFAULT 0,
  required TINYINT(1) NOT NULL DEFAULT 1,
  skill VARCHAR(128) NOT NULL,
  target_level INT NOT NULL DEFAULT 1,
  due_at VARCHAR(16) NOT NULL,
  sort_no INT NOT NULL DEFAULT 0,
  KEY idx_plan_user (username)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS learning_record (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL,
  course_name VARCHAR(200) NOT NULL,
  progress INT NOT NULL DEFAULT 0,
  hours DECIMAL(6,1) NOT NULL DEFAULT 0,
  studied_at VARCHAR(16) NOT NULL,
  status VARCHAR(16) NOT NULL,
  remark VARCHAR(200),
  sort_no INT NOT NULL DEFAULT 0,
  KEY idx_record_user (username)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS resource_item (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(200) NOT NULL,
  item_type VARCHAR(16) NOT NULL,
  duration VARCHAR(32) NOT NULL,
  skill VARCHAR(128) NOT NULL,
  level VARCHAR(16) NOT NULL,
  origin VARCHAR(16) NOT NULL,
  site VARCHAR(64) NOT NULL,
  match_reason VARCHAR(300) NOT NULL,
  jump_to VARCHAR(32),
  url VARCHAR(400),
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

-- 外网课程搜索：平台检索入口（search_url 里 {kw} 为关键词占位）+ 外网课程库；
-- 数据由 tools/fetch-courses.mjs 生成 db/init/006_external_course.sql 落库，接口是 /personal/course-search。
CREATE TABLE IF NOT EXISTS external_course_source (
  code VARCHAR(32) PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  site VARCHAR(128) NOT NULL,
  category VARCHAR(16) NOT NULL,
  home_url VARCHAR(300) NOT NULL,
  search_url VARCHAR(400) NOT NULL,
  probe_keyword VARCHAR(64) NOT NULL DEFAULT '',
  http_code INT NOT NULL DEFAULT 200,
  checked_at VARCHAR(16) NOT NULL DEFAULT '',
  note VARCHAR(300) NOT NULL DEFAULT '',
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS external_course (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(200) NOT NULL,
  source_code VARCHAR(32) NOT NULL,
  course_type VARCHAR(16) NOT NULL,
  duration VARCHAR(32) NOT NULL,
  skill VARCHAR(128) NOT NULL,
  level VARCHAR(16) NOT NULL,
  org VARCHAR(128) NOT NULL DEFAULT '',
  search_keyword VARCHAR(128) NOT NULL,
  url VARCHAR(400) NOT NULL,
  tags VARCHAR(200) NOT NULL DEFAULT '',
  match_reason VARCHAR(300) NOT NULL DEFAULT '',
  sort_no INT NOT NULL DEFAULT 0,
  KEY idx_external_course_skill (skill)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS certificate (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL,
  name VARCHAR(200) NOT NULL,
  level VARCHAR(16) NOT NULL,
  issued_at VARCHAR(16) NOT NULL,
  expires_at VARCHAR(16),
  review_note VARCHAR(200),
  status VARCHAR(16) NOT NULL DEFAULT 'VALID',
  sort_no INT NOT NULL DEFAULT 0,
  KEY idx_cert_user (username)
) ENGINE=InnoDB;

-- 能力记忆库：种子记忆 + Agent 诊断 / 练习判分实时写入的记忆
CREATE TABLE IF NOT EXISTS memory_item (
  memory_id VARCHAR(64) PRIMARY KEY,
  username VARCHAR(64) NOT NULL,
  type VARCHAR(16) NOT NULL,
  type_label VARCHAR(32) NOT NULL,
  occurred_at VARCHAR(32) NOT NULL,
  title VARCHAR(300) NOT NULL,
  detail TEXT,
  tags JSON NOT NULL,
  source VARCHAR(16) NOT NULL,
  source_label VARCHAR(64) NOT NULL,
  sort_no INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_memory_user (username, sort_no)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS task (
  id BIGINT PRIMARY KEY,
  title VARCHAR(200) NOT NULL,
  username VARCHAR(64) NOT NULL,
  skill VARCHAR(128) NOT NULL,
  planned_hours DECIMAL(6,1) NOT NULL DEFAULT 0,
  actual_hours DECIMAL(6,1),
  status VARCHAR(16) NOT NULL DEFAULT '待执行',
  due_at VARCHAR(16) NOT NULL,
  requirement VARCHAR(300),
  publisher VARCHAR(64),
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS task_report (
  report_id VARCHAR(32) PRIMARY KEY,
  task_id BIGINT NOT NULL,
  task_title VARCHAR(200) NOT NULL,
  member VARCHAR(64) NOT NULL DEFAULT '',
  reporter VARCHAR(64) NOT NULL,
  reporter_position VARCHAR(64) NOT NULL,
  detected_at VARCHAR(32) NOT NULL,
  shift VARCHAR(32) NOT NULL,
  location VARCHAR(200) NOT NULL,
  gas_type VARCHAR(16) NOT NULL,
  gas_label VARCHAR(32) NOT NULL,
  unit VARCHAR(16) NOT NULL,
  gas_value DECIMAL(14,4) NOT NULL,
  threshold_value DECIMAL(14,4) NOT NULL,
  direction VARCHAR(8) NOT NULL,
  judgment VARCHAR(8) NOT NULL,
  severity VARCHAR(8) NOT NULL,
  phenomenon TEXT NOT NULL,
  measures TEXT,
  -- SOP 执行情况：'' 未填报（字段上线前的历史数据）/ FOLLOWED 已按 SOP / DEVIATED 未按 SOP / NOT_APPLICABLE 本次无对应 SOP
  sop_status VARCHAR(16) NOT NULL DEFAULT '',
  sop_deviation VARCHAR(200) NOT NULL DEFAULT '',
  document_text MEDIUMTEXT,
  analysis JSON,
  submitted_at DATETIME(3) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_report_task (task_id)
) ENGINE=InnoDB;

-- 气体检测规则目录：驱动前端表单、后端判定、文档渲染与 AI 归因
CREATE TABLE IF NOT EXISTS gas_rule (
  code VARCHAR(16) PRIMARY KEY,
  label VARCHAR(32) NOT NULL,
  unit VARCHAR(16) NOT NULL,
  threshold_value DECIMAL(14,4) NOT NULL,
  direction VARCHAR(8) NOT NULL,
  standard VARCHAR(300) NOT NULL,
  attribution VARCHAR(400) NOT NULL,
  actions JSON NOT NULL,
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS report_template_section (
  section_key VARCHAR(32) PRIMARY KEY,
  title VARCHAR(64) NOT NULL,
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS report_template_field (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  section_key VARCHAR(32) NOT NULL,
  name VARCHAR(64) NOT NULL,
  label VARCHAR(64) NOT NULL,
  field_type VARCHAR(16) NOT NULL,
  required TINYINT(1) NOT NULL DEFAULT 0,
  example VARCHAR(300) NOT NULL,
  hint VARCHAR(300) NOT NULL,
  sort_no INT NOT NULL DEFAULT 0,
  KEY idx_field_section (section_key)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS report_document_meta (
  id TINYINT PRIMARY KEY,
  document_title VARCHAR(64) NOT NULL,
  notice VARCHAR(400) NOT NULL,
  sign_boxes JSON NOT NULL
) ENGINE=InnoDB;

-- 【历史遗留，运行期不再读取】报告归因关键词规则曾放在这里，现已迁进 rule 表
-- （scene=REPORT_GAS、rule_group=KEYWORD，见 db/init/009_report_gas_rules.sql）：
-- 规则内容只留一份，避免「改了这张表却不生效」。表与种子数据保留，不做破坏性删除。
CREATE TABLE IF NOT EXISTS analysis_keyword_rule (
  rule_code VARCHAR(32) PRIMARY KEY,
  keywords JSON NOT NULL,
  cause VARCHAR(300) NOT NULL,
  action VARCHAR(300) NOT NULL,
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;

-- ---------- 5. 练习 ----------
CREATE TABLE IF NOT EXISTS practice_session (
  session_id VARCHAR(64) PRIMARY KEY,
  username VARCHAR(64) NOT NULL,
  skill VARCHAR(128),
  question_count INT NOT NULL DEFAULT 0,
  question_ids JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_session_user (username)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS practice_stat (
  username VARCHAR(64) NOT NULL,
  skill VARCHAR(128) NOT NULL,
  answered INT NOT NULL DEFAULT 0,
  correct INT NOT NULL DEFAULT 0,
  PRIMARY KEY (username, skill)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS practice_history (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL,
  ran_at VARCHAR(32) NOT NULL,
  score INT NOT NULL DEFAULT 0,
  correct INT NOT NULL DEFAULT 0,
  total INT NOT NULL DEFAULT 0,
  source VARCHAR(64) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_practice_user (username, id)
) ENGINE=InnoDB;

-- ---------- 6. Agent / 规则 / 审计 ----------
-- 规则内容表。scene=场景；rule_group=匹配分组（同场景里定档、关键词补充各判各的，空串＝默认组）；
-- stop_on_match=命中后是否停止本组匹配；max_hits=本组最多命中几条（0=不限）。
-- action_json 里以 _from 结尾的字段是「引用事实」：值写事实名，输出时换成该事实当前值（见 RuleEngine.resolve）。
CREATE TABLE IF NOT EXISTS rule (
  rule_code VARCHAR(64) PRIMARY KEY,
  rule_name VARCHAR(64) NOT NULL DEFAULT '',
  scene VARCHAR(64) NOT NULL,
  rule_group VARCHAR(32) NOT NULL DEFAULT '',
  condition_json JSON NOT NULL,
  action_json JSON NOT NULL,
  priority INT NOT NULL DEFAULT 0,
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  stop_on_match TINYINT(1) NOT NULL DEFAULT 1,
  max_hits INT NOT NULL DEFAULT 0,
  status VARCHAR(16) NOT NULL DEFAULT 'ENABLED',
  remark TEXT,
  created_by VARCHAR(64) NOT NULL DEFAULT 'system',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_by VARCHAR(64) NOT NULL DEFAULT 'system',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_rule_scene (scene, enabled, priority)
) ENGINE=InnoDB;

-- 规则执行留痕：一次执行一行，hits_json 存命中的规则清单与判定依据，便于说明「为什么这么判」
CREATE TABLE IF NOT EXISTS rule_result (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id VARCHAR(48) NOT NULL,
  scene VARCHAR(64) NOT NULL,
  target_id VARCHAR(64),
  input_json JSON NOT NULL,
  matched TINYINT(1) NOT NULL DEFAULT 0,
  hits_json JSON,
  verdict_json JSON,
  explanation VARCHAR(600) NOT NULL,
  confidence DECIMAL(5,4) NOT NULL DEFAULT 0,
  source VARCHAR(16) NOT NULL DEFAULT 'rule',
  suggestion_id VARCHAR(64),
  executed_by VARCHAR(64),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_rule_result_run (run_id),
  KEY idx_rule_result_scene (scene, id),
  KEY idx_rule_result_target (target_id, id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS agent_suggestion (
  suggestion_id VARCHAR(64) PRIMARY KEY,
  agent_type VARCHAR(64) NOT NULL,
  target_id VARCHAR(64),
  input_json JSON,
  output_json JSON,
  confidence DECIMAL(5,4) NOT NULL DEFAULT 0,
  source VARCHAR(16) NOT NULL DEFAULT 'rule',
  need_human_confirm TINYINT(1) NOT NULL DEFAULT 1,
  status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS decision_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  suggestion_id VARCHAR(64),
  decision_user VARCHAR(64),
  decision VARCHAR(32) NOT NULL,
  reason TEXT,
  result_json JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Agent 诊断结论（员工个性化诊断 / 公司运行诊断），重启后仍可读回
CREATE TABLE IF NOT EXISTS diagnosis_result (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  diagnosis_id VARCHAR(48) NOT NULL,
  scope VARCHAR(16) NOT NULL,
  ran_at VARCHAR(32) NOT NULL,
  payload JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_diagnosis_scope (scope, id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS audit_log (
  id BIGINT PRIMARY KEY,
  occurred_at VARCHAR(32) NOT NULL,
  actor VARCHAR(64) NOT NULL,
  actor_role VARCHAR(64) NOT NULL,
  category VARCHAR(16) NOT NULL,
  action VARCHAR(200) NOT NULL,
  target VARCHAR(300) NOT NULL,
  result VARCHAR(32) NOT NULL,
  ip VARCHAR(64) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_audit_category (category),
  KEY idx_audit_occurred (occurred_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS safety_record (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL,
  record_type VARCHAR(32),
  severity VARCHAR(16),
  veto TINYINT(1) NOT NULL DEFAULT 0,
  occurred_at VARCHAR(32),
  description TEXT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS cost_record (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  org VARCHAR(128),
  cost_type VARCHAR(32),
  amount DECIMAL(14,2) NOT NULL DEFAULT 0,
  occurred_on VARCHAR(16)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS care_record (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL,
  pressure_level INT,
  mental_state TEXT,
  counselor VARCHAR(64),
  visibility VARCHAR(16) NOT NULL DEFAULT 'PRIVATE'
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS notification (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  receiver VARCHAR(64) NOT NULL,
  title VARCHAR(200),
  content TEXT,
  read_at VARCHAR(32),
  status VARCHAR(16) NOT NULL DEFAULT 'UNREAD'
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS file_object (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  owner VARCHAR(64),
  object_key VARCHAR(400) NOT NULL,
  file_name VARCHAR(300),
  content_type VARCHAR(128),
  size_kb INT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ---------- 7. 后台展示数据集与口径（老总 / 管理员页面的维护清单） ----------
CREATE TABLE IF NOT EXISTS dataset_item (
  dataset_key VARCHAR(64) NOT NULL,
  item_key VARCHAR(64) NOT NULL,
  sort_no INT NOT NULL DEFAULT 0,
  payload JSON NOT NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (dataset_key, item_key)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS dataset_meta (
  dataset_key VARCHAR(64) PRIMARY KEY,
  payload JSON NOT NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS permission_matrix (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  module VARCHAR(128) NOT NULL,
  employee VARCHAR(32) NOT NULL,
  team_lead VARCHAR(32) NOT NULL,
  executive VARCHAR(32) NOT NULL,
  admin VARCHAR(32) NOT NULL,
  note VARCHAR(300),
  sort_no INT NOT NULL DEFAULT 0
) ENGINE=InnoDB;
