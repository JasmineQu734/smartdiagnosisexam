SET NAMES utf8mb4;
-- 规则集校准（012）：把写死在条件里的业务常量改成「引用事实」，并补安全否决规则组。
--
-- 背景：008 种子里两条规则把业务口径写成了字面量——
--   EXAM_LOW_SCORE 写 score < 60，而课程的合格线是 80 / 85；
--   SKILL_GAP_L3   写 required_level = 3，而岗位关键任务的授权门槛有 L2 / L3 / L4。
-- 规则本身没错，错在「阈值不跟着数据走」：换一门课、换一个岗位，规则就静默失效。
-- 本脚本不再写死任何数值，改为与事实表里的合格线、要求等级直接比较。
--
-- 同时补「安全优先」分组：安全记录进事实清单之后，必须有一条规则能消费它，
-- 否则安全事实只是摆设。SAFETY 组独立于默认组，命中后只收敛本组，不影响技能差距的判定。
--
-- 与 008 / 009 一致：可重复执行；ON DUPLICATE KEY UPDATE 只覆盖规则定义，
-- 不动 enabled / status，避免重跑把管理员手工停用的规则又打开。
USE train_system;

INSERT INTO rule (rule_code, rule_name, scene, rule_group, condition_json, action_json, priority, enabled, stop_on_match, max_hits, remark) VALUES
  ('SAFETY_VETO_VIOLATION', '安全授权类违规（一票否决）', 'PERSONAL_GAP', 'SAFETY',
   '{"all":[{"fact":"safety_risk","op":"gte","value":2}]}',
   '{"severity":"高","cause":"存在越权、无票或未监护作业，按一票否决处理：暂停独立作业授权，重新培训并考核合格后恢复","actions":["ALERT","SOP_UPDATE"]}',
   200, 1, 1, 0, '授权类违规对应 safety_risk=2；命中即判高，且优先于任何技能类建议'),
  ('SAFETY_DEDUCTION', '安全扣分记录', 'PERSONAL_GAP', 'SAFETY',
   '{"all":[{"fact":"safety_risk","op":"eq","value":1}]}',
   '{"severity":"中","cause":"存在安全扣分记录，需在下一轮培训中复训相关条款","actions":["ALERT","SOP_UPDATE"]}',
   190, 1, 0, 0, '扣分类记录判中；组内不设首条即停，与违规规则各判各的'),
  ('SKILL_BELOW_REQUIRED', '技能等级低于岗位要求', 'PERSONAL_GAP', '',
   '{"all":[{"fact":"current_level","op":"lt","other_fact":"required_level"}]}',
   '{"actions":["COURSE","MENTORING","SIMULATION"],"course":"PROTECTION_LOGIC"}',
   120, 1, 1, 0, '要求等级取自岗位关键任务的授权门槛，不再写死 L3；等级来自事实，规则只负责比较'),
  ('EXAM_BELOW_PASS', '考试低于课程合格线', 'EXAM_RESULT', '',
   '{"all":[{"fact":"score","op":"lt","other_fact":"pass_score"}]}',
   '{"actions":["WRONG_KNOWLEDGE_REVIEW"]}',
   120, 1, 1, 0, '合格线取自课程与档案，不再写死 60；同一份规则适用于 80 / 85 等不同口径'),
  ('REPORT_GAS_WITHIN_NEAR', '未超阈值但余量不足', 'REPORT_GAS', 'VALUE',
   '{"all":[{"fact":"over_threshold","op":"is_false"},{"fact":"ratio","op":"lte","value":0.10},{"fact":"ratio","op":"gt","value":-0.10}]}',
   '{"severity":"中","cause":"读数已接近阈值，存在上行风险","actions":["按周期复测并留存检测记录","将该点位纳入加密监测（每 2 小时一次）并复测趋势"]}',
   120, 1, 1, 0, '补下界 -0.10：只补上界时，有符号口径下的负余量永远满足条件，会把终端规则堵死'),
  ('REPORT_GAS_WITHIN', '未超阈值且余量充足', 'REPORT_GAS', 'VALUE',
   '{"all":[{"fact":"over_threshold","op":"is_false"}]}',
   '{"severity":"低","cause":"检测值处于标准阈值范围内，未发现异常","actions":["按周期复测并留存检测记录"]}',
   110, 1, 1, 0, '阶梯终端：余量超过 10% 才落到这一档，保证「正常」结论可达')
ON DUPLICATE KEY UPDATE
  rule_name = VALUES(rule_name),
  scene = VALUES(scene),
  rule_group = VALUES(rule_group),
  condition_json = VALUES(condition_json),
  action_json = VALUES(action_json),
  priority = VALUES(priority),
  stop_on_match = VALUES(stop_on_match),
  max_hits = VALUES(max_hits),
  remark = VALUES(remark),
  updated_by = '012_rule_calibration',
  updated_at = CURRENT_TIMESTAMP;

-- 被取代的两条：保留定义以便追溯历史结论，但停用，避免与新规则重复触发。
INSERT INTO rule (rule_code, rule_name, scene, rule_group, condition_json, action_json, priority, enabled, stop_on_match, max_hits, remark) VALUES
  ('EXAM_LOW_SCORE', '考试低于合格线（已由 EXAM_BELOW_PASS 取代）', 'EXAM_RESULT', '',
   '{"all":[{"fact":"score","op":"lt","value":60}]}',
   '{"actions":["WRONG_KNOWLEDGE_REVIEW"]}',
   90, 0, 1, 0, '阈值写死为 60，与 80 / 85 的合格线不一致；012 起停用，保留定义供历史结论回溯'),
  ('SKILL_GAP_L3', '技能等级低于岗位要求（已由 SKILL_BELOW_REQUIRED 取代）', 'PERSONAL_GAP', '',
   '{"all":[{"fact":"current_level","op":"lt","other_fact":"required_level"},{"fact":"required_level","op":"eq","value":3}]}',
   '{"actions":["COURSE","MENTORING","SIMULATION"],"course":"PROTECTION_LOGIC"}',
   100, 0, 1, 0, '要求等级写死为 L3，L2 / L4 的差距全部漏判；012 起停用')
ON DUPLICATE KEY UPDATE
  rule_name = VALUES(rule_name),
  scene = VALUES(scene),
  rule_group = VALUES(rule_group),
  condition_json = VALUES(condition_json),
  action_json = VALUES(action_json),
  priority = VALUES(priority),
  stop_on_match = VALUES(stop_on_match),
  max_hits = VALUES(max_hits),
  remark = VALUES(remark),
  updated_by = '012_rule_calibration',
  updated_at = CURRENT_TIMESTAMP;

-- ON DUPLICATE 不动 enabled（沿用 008 的约定：不覆盖管理员的启停状态），
-- 因此这里显式停用被取代的两条。只按 rule_code 精确改，不影响其他规则。
UPDATE rule SET enabled = 0, updated_by = '012_rule_calibration', updated_at = CURRENT_TIMESTAMP
WHERE rule_code IN ('EXAM_LOW_SCORE', 'SKILL_GAP_L3');
