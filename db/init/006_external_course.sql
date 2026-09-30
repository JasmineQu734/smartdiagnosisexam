SET NAMES utf8mb4;
-- 由 tools/fetch-courses.mjs 生成，写入 MySQL 的 external_course_source / external_course 表。
-- 平台「学习与考试 → 推荐资源 → 外网课程搜索」的数据源：重新生成后覆盖执行本文件即可刷新（幂等）。
-- 只收录各平台公开的检索入口与检索关键词，不复制平台课程正文；http_code 是核验该平台检索地址时的真实状态码。
USE train_system;

-- 与 db/init/001_schema.sql 中的定义一致；这里再写一次，便于对已有数据库单独补跑本文件。
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

INSERT INTO external_course_source (code, name, site, category, home_url, search_url, probe_keyword, http_code, checked_at, note, sort_no) VALUES
  ('ICOURSE163', '中国大学 MOOC', 'icourse163.org', '慕课', 'https://www.icourse163.org/', 'https://www.icourse163.org/search.htm?search={kw}', '继电保护', 200, '2026-09-20', '高校电气类慕课，适合系统补理论与整定计算', 10),
  ('XUETANGX', '学堂在线', 'xuetangx.com', '慕课', 'https://www.xuetangx.com/', 'https://www.xuetangx.com/search?query={kw}', '电力系统继电保护', 200, '2026-09-20', '名校公开课与工程类课程，可按课程名检索', 20),
  ('SMARTEDU_VOC', '国家职业教育智慧教育平台', 'vocational.smartedu.cn', '职教', 'https://vocational.smartedu.cn/', 'https://vocational.smartedu.cn/search?keyword={kw}', '电力安全工作规程', 200, '2026-09-20', '教育部国家级职教平台，技能培训与安全规程资源可直接引用', 30),
  ('BILIBILI', '哔哩哔哩 · 技术区', 'search.bilibili.com', '视频', 'https://www.bilibili.com/', 'https://search.bilibili.com/all?keyword={kw}', '继电保护', 200, '2026-09-20', '现场作业视频讲解，适合入门补课与动作顺序模仿', 40),
  ('CEC', '中国电力企业联合会', 'cec.org.cn', '行业', 'https://www.cec.org.cn/', 'https://www.cec.org.cn/search?keyword={kw}', '继电保护', 200, '2026-09-20', '行业协会口径：技能等级评价、培训规范与安全政策', 50),
  ('WANFANG', '万方数据', 's.wanfangdata.com.cn', '学术', 'https://www.wanfangdata.com.cn/', 'https://s.wanfangdata.com.cn/paper?q={kw}', '电气设备 状态检修', 200, '2026-09-20', '学术论文与标准文献，支撑进阶分析与状态检修', 60),
  ('CNKI', '中国知网 · 期刊论文', 'kns.cnki.net', '学术', 'https://www.cnki.net/', 'https://kns.cnki.net/kns8s/search?kw={kw}', '故障录波 分析', 200, '2026-09-20', '期刊论文与事故案例，用于难题归因与复盘', 70)
  ON DUPLICATE KEY UPDATE name=VALUES(name), site=VALUES(site), category=VALUES(category), home_url=VALUES(home_url), search_url=VALUES(search_url), probe_keyword=VALUES(probe_keyword), http_code=VALUES(http_code), checked_at=VALUES(checked_at), note=VALUES(note), sort_no=VALUES(sort_no);

INSERT INTO external_course (id, title, source_code, course_type, duration, skill, level, org, search_keyword, url, tags, match_reason, sort_no) VALUES
  (1, '继电保护原理与整定计算 · 高校慕课', 'ICOURSE163', '慕课', '按课程', '继电保护', '入门', '高校慕课 · 电气类', '继电保护 整定计算', 'https://www.icourse163.org/search.htm?search=%E7%BB%A7%E7%94%B5%E4%BF%9D%E6%8A%A4%20%E6%95%B4%E5%AE%9A%E8%AE%A1%E7%AE%97', '继电保护,整定计算,原理', '理论考试 62 分未通过，先补原理与整定计算', 10),
  (2, '电力系统继电保护（名校公开课）', 'XUETANGX', '慕课', '按课程', '继电保护', '进阶', '名校公开课 · 电气工程', '电力系统继电保护', 'https://www.xuetangx.com/search?query=%E7%94%B5%E5%8A%9B%E7%B3%BB%E7%BB%9F%E7%BB%A7%E7%94%B5%E4%BF%9D%E6%8A%A4', '继电保护,二次回路,保护配置', '继保 L1→L3 缺口最大，系统学保护配置与二次回路', 20),
  (3, '继电保护装置定值整定与校验实操', 'BILIBILI', '视频', '按视频', '继电保护', '进阶', '技术区 · 现场实操', '继电保护 定值整定', 'https://search.bilibili.com/all?keyword=%E7%BB%A7%E7%94%B5%E4%BF%9D%E6%8A%A4%20%E5%AE%9A%E5%80%BC%E6%95%B4%E5%AE%9A', '定值,整定,校验', '定值核对与投退需师傅复核，先看现场实操', 30),
  (4, '软压板投退逻辑与顺序讲解', 'BILIBILI', '视频', '按视频', '继电保护', '入门', '技术区 · 装置逻辑', '软压板 投退顺序', 'https://search.bilibili.com/all?keyword=%E8%BD%AF%E5%8E%8B%E6%9D%BF%20%E6%8A%95%E9%80%80%E9%A1%BA%E5%BA%8F', '软压板,压板投退,逻辑', '错题集中在软压板投退顺序', 40),
  (5, '继电保护技能等级评价与培训规范', 'CEC', '行业', '按需检索', '继电保护', '精通', '行业协会 · 技能评价', '继电保护 技能等级 评价', 'https://www.cec.org.cn/search?keyword=%E7%BB%A7%E7%94%B5%E4%BF%9D%E6%8A%A4%20%E6%8A%80%E8%83%BD%E7%AD%89%E7%BA%A7%20%E8%AF%84%E4%BB%B7', '技能等级,评价规范,岗位', '岗位 L1-L3 评价口径的权威出处', 50),
  (6, '继电保护定值配合与整定计算论文', 'CNKI', '学术', '按需检索', '继电保护', '精通', '学术期刊 · 继电保护', '继电保护 定值配合', 'https://kns.cnki.net/kns8s/search?kw=%E7%BB%A7%E7%94%B5%E4%BF%9D%E6%8A%A4%20%E5%AE%9A%E5%80%BC%E9%85%8D%E5%90%88', '定值配合,论文,案例', '定值配合类难题的进阶依据', 60),
  (7, '变电站倒闸操作规范与实操演示', 'BILIBILI', '视频', '按视频', '倒闸操作', '入门', '技术区 · 现场实操', '倒闸操作 步骤', 'https://search.bilibili.com/all?keyword=%E5%80%92%E9%97%B8%E6%93%8D%E4%BD%9C%20%E6%AD%A5%E9%AA%A4', '倒闸操作,实操,顺序', '已达标技能，保持手感并作为带教素材', 70),
  (8, '电力安全工作规程（变电站部分）解读', 'SMARTEDU_VOC', '职教', '按课程', '倒闸操作', '入门', '国家级职教平台 · 电力类', '电力安全工作规程 变电站', 'https://vocational.smartedu.cn/search?keyword=%E7%94%B5%E5%8A%9B%E5%AE%89%E5%85%A8%E5%B7%A5%E4%BD%9C%E8%A7%84%E7%A8%8B%20%E5%8F%98%E7%94%B5%E7%AB%99', '安规,变电站,红线', '操作票与安规条款逐条对照学习', 80),
  (9, '变电运维值班员岗位技能实训', 'SMARTEDU_VOC', '职教', '按课程', '倒闸操作', '进阶', '国家级职教平台 · 电力类', '变电运维 实训', 'https://vocational.smartedu.cn/search?keyword=%E5%8F%98%E7%94%B5%E8%BF%90%E7%BB%B4%20%E5%AE%9E%E8%AE%AD', '变电运维,实训,岗位', '变电运维一班岗位技能标准化训练', 90),
  (10, '高电压技术（绝缘与试验基础）', 'ICOURSE163', '慕课', '按课程', '高压试验', '进阶', '高校慕课 · 电气类', '高电压技术 绝缘试验', 'https://www.icourse163.org/search.htm?search=%E9%AB%98%E7%94%B5%E5%8E%8B%E6%8A%80%E6%9C%AF%20%E7%BB%9D%E7%BC%98%E8%AF%95%E9%AA%8C', '高压试验,绝缘,试验', '高压试验 L1→L2 缺口，系统补试验原理', 100),
  (11, 'SF6 气体检测与微水试验作业演示', 'BILIBILI', '视频', '按视频', '高压试验', '入门', '技术区 · 现场实操', 'SF6 微水 检测', 'https://search.bilibili.com/all?keyword=SF6%20%E5%BE%AE%E6%B0%B4%20%E6%A3%80%E6%B5%8B', 'SF6,微水,气体检测', '实操报告暴露取样与读数细节不足', 110),
  (12, '电气设备状态检修与试验案例分析', 'WANFANG', '学术', '按需检索', '高压试验', '进阶', '学术文献 · 状态检修', '电气设备 状态检修', 'https://s.wanfangdata.com.cn/paper?q=%E7%94%B5%E6%B0%94%E8%AE%BE%E5%A4%87%20%E7%8A%B6%E6%80%81%E6%A3%80%E4%BF%AE', '状态检修,试验数据,案例', '用试验数据比对判断设备状态', 120),
  (13, '电力系统故障分析与录波图识读', 'ICOURSE163', '慕课', '按课程', '故障录波', '进阶', '高校慕课 · 电气类', '电力系统故障分析', 'https://www.icourse163.org/search.htm?search=%E7%94%B5%E5%8A%9B%E7%B3%BB%E7%BB%9F%E6%95%85%E9%9A%9C%E5%88%86%E6%9E%90', '故障录波,故障分析,波形', '故障录波 L1→L2 缺口，补分析方法', 130),
  (14, '录波波形与开关变位识读入门', 'BILIBILI', '视频', '按视频', '故障录波', '入门', '技术区 · 二次回路', '故障录波 波形识读', 'https://search.bilibili.com/all?keyword=%E6%95%85%E9%9A%9C%E5%BD%95%E6%B3%A2%20%E6%B3%A2%E5%BD%A2%E8%AF%86%E8%AF%BB', '录波,波形,变位', '能读波形但不能独立归因，先练识读', 140),
  (15, '继电保护故障录波典型案例分析', 'CNKI', '学术', '按需检索', '故障录波', '进阶', '学术期刊 · 继电保护', '故障录波 案例分析', 'https://kns.cnki.net/kns8s/search?kw=%E6%95%85%E9%9A%9C%E5%BD%95%E6%B3%A2%20%E6%A1%88%E4%BE%8B%E5%88%86%E6%9E%90', '录波,案例,论文', '典型录波案例，支撑录波 L2 判定', 150),
  (16, '电力安全生产法规与一票否决条款', 'CEC', '行业', '按需检索', '安全规程', '入门', '行业协会 · 安全政策', '电力安全 一票否决', 'https://www.cec.org.cn/search?keyword=%E7%94%B5%E5%8A%9B%E5%AE%89%E5%85%A8%20%E4%B8%80%E7%A5%A8%E5%90%A6%E5%86%B3', '安全规程,一票否决,政策', '安全规程月度必修的政策出处', 160),
  (17, '有限空间作业安全与气体检测规定', 'SMARTEDU_VOC', '职教', '按课程', '安全规程', '入门', '国家级职教平台 · 安全类', '有限空间作业 气体检测', 'https://vocational.smartedu.cn/search?keyword=%E6%9C%89%E9%99%90%E7%A9%BA%E9%97%B4%E4%BD%9C%E4%B8%9A%20%E6%B0%94%E4%BD%93%E6%A3%80%E6%B5%8B', '有限空间,气体检测,通风', '电缆沟作业先通风检测后再进入', 170),
  (18, '电力事故案例与责任追溯专题', 'CNKI', '学术', '按需检索', '安全规程', '进阶', '学术期刊 · 电力安全', '电力 事故案例 责任追溯', 'https://kns.cnki.net/kns8s/search?kw=%E7%94%B5%E5%8A%9B%20%E4%BA%8B%E6%95%85%E6%A1%88%E4%BE%8B%20%E8%B4%A3%E4%BB%BB%E8%BF%BD%E6%BA%AF', '事故案例,责任,复盘', '班组安全学习与案例通报素材', 180),
  (19, '电气工程基础与电工原理补课', 'XUETANGX', '慕课', '按课程', '继电保护', '入门', '名校公开课 · 电气工程', '电气工程 电工基础', 'https://www.xuetangx.com/search?query=%E7%94%B5%E6%B0%94%E5%B7%A5%E7%A8%8B%20%E7%94%B5%E5%B7%A5%E5%9F%BA%E7%A1%80', '电工,基础,入门', '基础薄弱时先补电工原理再上继保', 190),
  (20, '变电检修与高压试验作业安全', 'SMARTEDU_VOC', '职教', '按课程', '高压试验', '入门', '国家级职教平台 · 电力类', '变电检修 高压试验 安全', 'https://vocational.smartedu.cn/search?keyword=%E5%8F%98%E7%94%B5%E6%A3%80%E4%BF%AE%20%E9%AB%98%E5%8E%8B%E8%AF%95%E9%AA%8C%20%E5%AE%89%E5%85%A8', '高压试验,检修,安全', '试验作业安全措施与监护要求', 200)
  ON DUPLICATE KEY UPDATE title=VALUES(title), source_code=VALUES(source_code), course_type=VALUES(course_type), duration=VALUES(duration), skill=VALUES(skill), level=VALUES(level), org=VALUES(org), search_keyword=VALUES(search_keyword), url=VALUES(url), tags=VALUES(tags), match_reason=VALUES(match_reason), sort_no=VALUES(sort_no);
