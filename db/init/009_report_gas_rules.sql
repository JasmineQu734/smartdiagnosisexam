SET NAMES utf8mb4;
-- 气体检测归因（场景 REPORT_GAS）：给 rule 表补「匹配分组」与「组内命中上限」，并把归因判定从 Java 硬编码搬进 rule 表。
-- 与 db/init/001_schema.sql 中的定义一致；这里再写一次，便于对已有数据库单独补跑本文件（幂等）。
-- 注意：MySQL 8 没有 ADD COLUMN IF NOT EXISTS（那是 MariaDB 的语法），补列前必须先查 information_schema。
USE train_system;

-- ---------- 1. rule 表补「匹配分组」与「组内命中上限」 ----------
-- 为什么要有分组：同一场景里「取值定档」和「关键词补充」必须各判各的。
-- 一条 stop_on_match 规则命中就把整场结束的话，关键词规则永远轮不到（原实现靠 Java 里两段代码绕开这个问题）。
SET @add_rule_columns := (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE rule
       ADD COLUMN rule_group VARCHAR(32) NOT NULL DEFAULT '''',
       ADD COLUMN max_hits INT NOT NULL DEFAULT 0',
    'SELECT 1'
  )
  FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'rule' AND column_name = 'rule_group'
);
PREPARE add_rule_columns FROM @add_rule_columns;
EXECUTE add_rule_columns;
DEALLOCATE PREPARE add_rule_columns;

-- ---------- 2. 气体检测归因规则 ----------
-- 迁移自 ReportAnalysisService.ruleAnalyze() 里的硬编码判定。原实现边算边往 rule_refs 里塞
-- RULE-GAS-ABOVE / RULE-VALUE-NEAR / RULE-SEV-ESCALATE 这类编号，而它们在 rule 表里根本不存在 ——
-- 报告上写着「命中规则」，规则库里却查不到，复盘就断在这里。现在全部落成表里的真规则，编号即留痕。
--
-- 分组分工：
--   VALUE   定档：是否超阈值 + 余量档位，组内首条命中即停，归因与措施由 action_json 的 *_from 引用 gas_rule 的配置；
--   KEYWORD 补充：从报告正文里补原因与措施，最多 3 条（max_hits=3），命中「持续恶化 / 人员不适」的规则自己声明 高。
-- 严重度合并规则是「更严重者胜」：定档给基准档，关键词规则命中即抬档，不需要 Java 再做一档升级。
--
-- 定义归脚本、运行状态归管理员：ON DUPLICATE KEY UPDATE 只覆盖规则定义，
-- 不动 enabled / status，避免重跑脚本把管理员手工停用的规则又打开。
INSERT INTO rule (rule_code, rule_name, scene, rule_group, condition_json, action_json, priority, enabled, stop_on_match, max_hits, remark) VALUES
  ('REPORT_GAS_OVER_MARGIN_HIGH', '超阈值且余量≥20%', 'REPORT_GAS', 'VALUE',
   '{"all":[{"fact":"over_threshold","op":"is_true"},{"fact":"ratio","op":"gte","value":0.20}]}',
   '{"severity":"高","cause_from":"gas_attribution","actions_from":"gas_actions"}',
   150, 1, 1, 0, '检测值超出报警阈值 20% 以上判高；归因与措施取 gas_rule 里该气体的配置，不为每种气体各写一条'),
  ('REPORT_GAS_OVER_MARGIN_MID', '超阈值且余量 5%-20%', 'REPORT_GAS', 'VALUE',
   '{"all":[{"fact":"over_threshold","op":"is_true"},{"fact":"ratio","op":"gte","value":0.05}]}',
   '{"severity":"中","cause_from":"gas_attribution","actions_from":"gas_actions"}',
   140, 1, 1, 0, '超出阈值 5%-20% 判中'),
  ('REPORT_GAS_OVER_MARGIN_LOW', '超阈值且余量<5%', 'REPORT_GAS', 'VALUE',
   '{"all":[{"fact":"over_threshold","op":"is_true"}]}',
   '{"severity":"低","cause_from":"gas_attribution","actions_from":"gas_actions"}',
   130, 1, 1, 0, '刚过阈值判低；上面两条都没命中才轮到它'),
  ('REPORT_GAS_WITHIN_NEAR', '未超阈值但余量≤10%', 'REPORT_GAS', 'VALUE',
   '{"all":[{"fact":"over_threshold","op":"is_false"},{"fact":"ratio","op":"lte","value":0.10}]}',
   '{"severity":"中","cause":"读数已接近阈值，存在上行风险","actions":["按周期复测并留存检测记录","将该点位纳入加密监测（每 2 小时一次）并复测趋势"]}',
   120, 1, 1, 0, '余量不足 10% 时不给「正常」结论，判中并加密监测'),
  ('REPORT_GAS_WITHIN', '未超阈值', 'REPORT_GAS', 'VALUE',
   '{"all":[{"fact":"over_threshold","op":"is_false"}]}',
   '{"severity":"低","cause":"检测值处于标准阈值范围内，未发现异常","actions":["按周期复测并留存检测记录"]}',
   110, 1, 1, 0, '未超阈值且余量充足：判低，按周期复测'),
  ('RULE-KW-LEAK', '现象含泄漏关键词', 'REPORT_GAS', 'KEYWORD',
   '{"fact":"document_text","op":"contains_any","value":["泄漏","漏气","压力下降","压降","降压"]}',
   '{"cause":"密封件老化或法兰面密封失效（与现场泄漏描述一致）","actions":["使用检漏仪逐点定位泄漏点，记录泄漏率并跟踪闭环"]}',
   100, 1, 0, 3, '关键词规则：一个编号挂一组同义关键词，命中任意一个即补原因与措施'),
  ('RULE-KW-DECOMP', '现象含分解产物关键词', 'REPORT_GAS', 'KEYWORD',
   '{"fact":"document_text","op":"contains_any","value":["异味","刺激性","气味","分解","刺鼻"]}',
   '{"cause":"SF6 分解产物（SO2、H2S 类）超标，存在放电或局部过热","actions":["带电检测分解产物并安排气体处理，作业时佩戴防毒面具"]}',
   99, 1, 0, 3, NULL),
  ('RULE-KW-HEAT', '现象含过热关键词', 'REPORT_GAS', 'KEYWORD',
   '{"fact":"document_text","op":"contains_any","value":["发热","温度","烫","过热","温升"]}',
   '{"cause":"接触面氧化或接触不良导致局部过热","actions":["红外测温确认过热点，安排停电检修并复紧连接面"]}',
   98, 1, 0, 3, NULL),
  ('RULE-KW-PD', '现象含局部放电关键词', 'REPORT_GAS', 'KEYWORD',
   '{"fact":"document_text","op":"contains_any","value":["异响","放电","闪络","电晕","滋滋"]}',
   '{"cause":"存在局部放电，可能为绝缘缺陷或悬浮电位","actions":["开展超声波、特高频局放检测并申请停电检查"]}',
   97, 1, 0, 3, NULL),
  ('RULE-KW-MOISTURE', '现象含受潮关键词', 'REPORT_GAS', 'KEYWORD',
   '{"fact":"document_text","op":"contains_any","value":["渗水","潮气","受潮","积水","凝露"]}',
   '{"cause":"受潮或排水不畅导致绝缘性能下降","actions":["检查密封与吸附剂，处理积水并复测微水含量"]}',
   96, 1, 0, 3, NULL),
  ('RULE-KW-HEALTH', '现象含人员不适关键词', 'REPORT_GAS', 'KEYWORD',
   '{"fact":"document_text","op":"contains_any","value":["头晕","恶心","不适","呛","窒息"]}',
   '{"cause":"人员出现身体不适，存在中毒或缺氧风险","actions":["立即撤离人员并就医，通风检测合格前禁止再次进入"],"severity":"高"}',
   95, 1, 0, 3, '人员不适必须判高：命中即把严重度抬到最高档，不依赖基准档'),
  ('RULE-KW-WORSENING', '现象含持续恶化关键词', 'REPORT_GAS', 'KEYWORD',
   '{"fact":"document_text","op":"contains_any","value":["持续","未恢复","扩大","加剧","继续上升","未回升"]}',
   '{"cause":"现象持续未恢复，缺陷可能正在发展","actions":["提高监测频次至每 2 小时一次，并升级上报至技术负责人"],"severity":"高"}',
   94, 1, 0, 3, '持续恶化判高；排在关键词组最后，与迁移前的顺序一致')
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
  updated_by = '009_report_gas_rules',
  updated_at = CURRENT_TIMESTAMP;
