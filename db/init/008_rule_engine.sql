SET NAMES utf8mb4;
-- 规则引擎：rule 表补公共字段与匹配开关 → 建 rule_result 执行留痕表 → 把 6 条种子规则改写成声明式条件。
-- 与 db/init/001_schema.sql 中的定义一致；这里再写一次，便于对已有数据库单独补跑本文件（幂等）。
-- 注意：MySQL 8 没有 ADD COLUMN IF NOT EXISTS（那是 MariaDB 的语法），补列前必须先查 information_schema。
USE train_system;

-- ---------- 1. rule 表补齐公共字段与匹配语义开关 ----------
SET @add_rule_columns := (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE rule
       ADD COLUMN rule_name VARCHAR(64) NOT NULL DEFAULT '''',
       ADD COLUMN stop_on_match TINYINT(1) NOT NULL DEFAULT 1,
       ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT ''ENABLED'',
       ADD COLUMN created_by VARCHAR(64) NOT NULL DEFAULT ''system'',
       ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
       ADD COLUMN updated_by VARCHAR(64) NOT NULL DEFAULT ''system'',
       ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
    'SELECT 1'
  )
  FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'rule' AND column_name = 'stop_on_match'
);
PREPARE add_rule_columns FROM @add_rule_columns;
EXECUTE add_rule_columns;
DEALLOCATE PREPARE add_rule_columns;

SET @add_rule_index := (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE rule ADD KEY idx_rule_scene (scene, enabled, priority)',
    'SELECT 1'
  )
  FROM information_schema.statistics
  WHERE table_schema = DATABASE() AND table_name = 'rule' AND index_name = 'idx_rule_scene'
);
PREPARE add_rule_index FROM @add_rule_index;
EXECUTE add_rule_index;
DEALLOCATE PREPARE add_rule_index;

-- ---------- 2. 规则执行留痕：一次执行一行，hits_json 存命中的规则与判定依据 ----------
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

-- ---------- 3. 6 条种子规则改写成声明式条件（原形状 {"xxx_lt": 2} 无法表达组合与事实间比较） ----------
-- 定义归脚本、运行状态归管理员：ON DUPLICATE KEY UPDATE 只覆盖规则定义，
-- 不动 enabled / status，避免重跑脚本把管理员手工停用的规则又打开。
INSERT INTO rule (rule_code, rule_name, scene, condition_json, action_json, priority, enabled, stop_on_match, remark) VALUES
  ('SKILL_GAP_L3', '技能等级低于岗位要求', 'PERSONAL_GAP',
   '{"all":[{"fact":"current_level","op":"lt","other_fact":"required_level"},{"fact":"required_level","op":"eq","value":3}]}',
   '{"actions":["COURSE","MENTORING","SIMULATION"],"course":"PROTECTION_LOGIC"}', 100, 1, 1,
   '技能等级低于岗位要求时优先补课 + 带教 + 模拟'),
  ('EXAM_LOW_SCORE', '考试低于合格线', 'EXAM_RESULT',
   '{"all":[{"fact":"score","op":"lt","value":60}]}',
   '{"actions":["WRONG_KNOWLEDGE_REVIEW"]}', 90, 1, 1,
   '考试低于合格线写入错题复盘记忆'),
  ('BACKUP_SHORTAGE', '关键岗位备份不足', 'TALENT_GAP',
   '{"all":[{"fact":"backup_count","op":"lt","value":2}]}',
   '{"actions":["ALERT"]}', 80, 1, 0,
   '关键岗位备份不足触发预警；同场景还要看未来需求缺口，命中后继续匹配'),
  ('FUTURE_DEMAND_GAP', '未来需求高于现有人才', 'TALENT_GAP',
   '{"all":[{"fact":"future_demand","op":"gt","other_fact":"current_supply"}]}',
   '{"actions":["INTERNAL_TRANSFER","RECRUITMENT","OUTSOURCE"]}', 70, 1, 0,
   '公司未来需求高于在岗能力时给出转岗 / 招聘 / 外委建议'),
  ('PRACTICE_SKILL_CAUSE', '实操超时且技能缺失', 'REPORT_ANALYSIS',
   '{"all":[{"fact":"actual_hours_ratio","op":"gt","value":1.2},{"fact":"skill_missing","op":"is_true"}]}',
   '{"cause":"SKILL","severity":"中","actions":["COURSE","MENTORING"]}', 100, 1, 1,
   '实操超时且技能缺失时归因为技能原因'),
  ('PRACTICE_HUMAN_CAUSE', '未按 SOP 准备', 'REPORT_ANALYSIS',
   '{"all":[{"fact":"sop_preparation","op":"is_false"}]}',
   '{"cause":"HUMAN_OR_PROCESS","actions":["SOP_UPDATE"]}', 110, 1, 1,
   '未按 SOP 准备时归因为人为 / 流程原因')
ON DUPLICATE KEY UPDATE
  rule_name = VALUES(rule_name),
  scene = VALUES(scene),
  condition_json = VALUES(condition_json),
  action_json = VALUES(action_json),
  priority = VALUES(priority),
  stop_on_match = VALUES(stop_on_match),
  remark = VALUES(remark),
  updated_by = '008_rule_engine',
  updated_at = CURRENT_TIMESTAMP;
