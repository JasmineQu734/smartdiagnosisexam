SET NAMES utf8mb4;
-- 组长上传资料 → Agent 识别题目 → 管理员审核 → 入题库 / 课程库 → 员工刷题可见。
-- 与 db/init/001_schema.sql 中的定义一致；这里再写一次，便于对已有数据库单独补跑本文件（幂等）。
USE train_system;

-- ---------- 资料解析台账：原件留档 + Agent 读到的正文摘录 ----------
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

-- ---------- Agent 识别出的候选题 / 候选章节：审核通过前不入库 ----------
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

-- ---------- SOP 模板口径：生成后先进待审核，管理员通过才写入题库 ----------
UPDATE dataset_meta SET payload = JSON_SET(payload, '$.notice', '组长按模板填入 SOP 内容（或改用「导入文档」直接上传 PDF / Word），Agent 逐条解析判定标准与考核要点并生成练习题，提交管理员审核；审核通过后写入题库，供普通员工抽题时调用。')
WHERE dataset_key = 'team.sop.template';

-- ---------- 页面口径：组长「导入文档」入口说明（与 SOP 模板一样存在库里，可随时维护） ----------
INSERT INTO dataset_meta (dataset_key, payload) VALUES ('team.material.import', '{"title":"导入文档生成练习资料","notice":"组长导入 PDF / Word / 文本 / 表格 / 演示文稿，Agent 读原件正文后识别出题干、选项、答案与解析（或整理成知识章节），提交管理员审核；审核通过写入题库 / 课程库，普通员工刷题即可抽到。","accept":"pdf / docx / txt / md / csv / xlsx / pptx","limit_mb":20,"targets":[{"value":"题库","label":"题库（识别题目 + 答案）"},{"value":"课程库","label":"课程库（整理知识章节）"}],"steps":["选择文档并填技能 / 等级 / 版本","Agent 读正文并识别题目与答案","提交管理员审核（此时还没进题库）","审核通过后写入题库，员工抽题即见"]}')
  ON DUPLICATE KEY UPDATE payload = VALUES(payload);
