SET NAMES utf8mb4;
-- 报告填报的结构化字段：SOP 执行情况（sop_status）与偏差说明（sop_deviation）。
--
-- 为什么加在报告上：报告归因要区分「技能不够」与「没按规程做」，这两件事在现象描述里都是自然语言，
-- 规则引擎判不了；让组长填报时给出一个可枚举的答案，归因才有结构化证据（管理员侧的资料 / SOP 校对同样读它）。
-- 为什么是三态而不是「是 / 否」：没填与「本次没有对应 SOP」是两回事，
-- 字段缺失只判为「未知」，绝不能默认成「未按 SOP」——否则缺数据会自动变成「人为问题」的结论。
-- 与 001_schema.sql 中的定义一致；这里再写一次，便于对已有数据库单独补跑本文件（幂等）。
USE train_system;

-- ---------- 1. task_report 补两列 ----------
-- MySQL 8 没有 ADD COLUMN IF NOT EXISTS（那是 MariaDB 的语法），补列前先查 information_schema。
-- 默认空串 = 这份报告填报时还没有该字段，读的时候按「未知」处理，不替历史数据猜答案。
SET @add_sop_columns := (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE task_report
       ADD COLUMN sop_status VARCHAR(16) NOT NULL DEFAULT '''',
       ADD COLUMN sop_deviation VARCHAR(200) NOT NULL DEFAULT ''''',
    'SELECT 1'
  )
  FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'task_report' AND column_name = 'sop_status'
);
PREPARE add_sop_columns FROM @add_sop_columns;
EXECUTE add_sop_columns;
DEALLOCATE PREPARE add_sop_columns;

-- ---------- 2. 模板框格：新增「SOP 执行情况」一节（驱动填报表单与模板说明） ----------
INSERT INTO report_template_section (section_key, title, sort_no) VALUES
  ('sop', 'SOP 执行情况', 4)
ON DUPLICATE KEY UPDATE title = VALUES(title), sort_no = VALUES(sort_no);

INSERT INTO report_template_field (id, section_key, name, label, field_type, required, example, hint, sort_no) VALUES
  (10, 'sop', 'sop_status', 'SOP 执行情况', 'radio', 1, '已按 SOP 执行',
   '本次实操是否按对应作业指导书（SOP）执行：已按 SOP 执行 / 未按 SOP 执行 / 本次无对应 SOP；选「未按 SOP 执行」时必须写明偏差', 1),
  (11, 'sop', 'sop_deviation', 'SOP 偏差说明', 'textarea', 0, '作业人员先行进入检查井后才检测氧含量，未执行“先检测、后进入”的有限空间作业程序',
   '仅选「未按 SOP 执行」时必填：写清哪一步没按规程做，不超过 200 字', 2)
ON DUPLICATE KEY UPDATE section_key = VALUES(section_key), name = VALUES(name), label = VALUES(label),
  field_type = VALUES(field_type), required = VALUES(required), example = VALUES(example), hint = VALUES(hint),
  sort_no = VALUES(sort_no);

-- ---------- 3. 演示台账补录（只动本仓库自己的 4 份演示报告，且只在字段为空时补） ----------
-- 已有数据卷是在本字段之前建库的，若不给演示报告补上，同一份种子在不同的库里演示结果会不一样。
-- 取值按其现象描述本身判定，不凭空编造「未按 SOP」：只有 RPT-20260919-0003 的描述里
-- 写明了「先行进入的作业人员出现头晕、胸闷不适」，属于先进入后检测，据实记为未按 SOP。
UPDATE task_report SET sop_status = 'DEVIATED',
    sop_deviation = '作业人员先行进入检查井后才检测氧含量，未执行“先检测、后进入”的有限空间作业程序'
  WHERE report_id = 'RPT-20260919-0003' AND sop_status = '';
UPDATE task_report SET sop_status = 'FOLLOWED'
  WHERE report_id IN ('RPT-20260915-0002', 'RPT-20260918-0001', 'RPT-20260920-0001') AND sop_status = '';
