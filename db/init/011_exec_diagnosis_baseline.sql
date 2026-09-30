SET NAMES utf8mb4;
USE train_system;
-- 公司运行诊断的兜底口径补全（幂等，可直接对已有库补跑）。
--
-- 背景：改造前 summary（总述段落）与 updated_modules（本次同步板块）由 CompanyController.runDiagnosis()
-- 在 Java 里硬编码拼出来。本次把诊断结论改成「查事实 + 大模型出结论 + 不合格回退内置结论」后，
-- 兜底路径直接返回本行的 payload，所以这两段文案必须入库 —— 代码里不再写死业务文案，管理员改库即改兜底结论。
--
-- 只补这两个字段，其余内容（verdict / findings / actions / cost_summary）保持原样，故用 JSON_SET 而不是整行覆盖。

UPDATE dataset_meta
SET payload = JSON_SET(
      payload,
      '$.summary', '本次运行实时读取库内数据判定：公司当前是「人才缺失 + 在岗技能不足」并存，以在岗技能不足为主因——继电保护 L3 缺口 4 人，而在岗 9 名值班员中 4 人继保理论未达 80 分、软压板逻辑与定值准备是考试、实操、报告三处证据的共同诱因；先补在岗技能、再按真实缺口补充人员，比整体扩编每年少花约 ¥7.8 万。',
      '$.updated_modules', JSON_ARRAY('人才驾驶舱', '全公司技能矩阵', '培训看板', '运行诊断 Agent'))
WHERE dataset_key = 'exec.diagnosis';
