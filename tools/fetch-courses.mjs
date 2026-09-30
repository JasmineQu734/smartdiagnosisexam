// 生成 db/init/006_external_course.sql（平台「外网课程搜索」的数据源，落在 MySQL 的
// external_course_source / external_course 两张表）。
// 运行： node tools/fetch-courses.mjs   （需要外网访问下列公开课程平台的检索页）
// 说明：只收录各平台公开的检索入口与检索关键词，不复制平台课程正文；
//       运行时会实际请求每个平台的检索地址，把该地址的 HTTP 状态码写入 external_course_source.http_code 留痕；
//       库里每门课的 url 都是「该平台检索该关键词」的实时结果页，点击后在新窗口打开。
import { writeFileSync } from 'node:fs';

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36';

// 平台检索入口：search 里的 {kw} 会被替换成课程关键词，probe 用于核验该检索地址是否可访问。
const PLATFORMS = [
  {
    code: 'ICOURSE163', name: '中国大学 MOOC', site: 'icourse163.org', category: '慕课',
    home: 'https://www.icourse163.org/', search: 'https://www.icourse163.org/search.htm?search={kw}', probe: '继电保护',
    note: '高校电气类慕课，适合系统补理论与整定计算'
  },
  {
    code: 'XUETANGX', name: '学堂在线', site: 'xuetangx.com', category: '慕课',
    home: 'https://www.xuetangx.com/', search: 'https://www.xuetangx.com/search?query={kw}', probe: '电力系统继电保护',
    note: '名校公开课与工程类课程，可按课程名检索'
  },
  {
    code: 'SMARTEDU_VOC', name: '国家职业教育智慧教育平台', site: 'vocational.smartedu.cn', category: '职教',
    home: 'https://vocational.smartedu.cn/', search: 'https://vocational.smartedu.cn/search?keyword={kw}', probe: '电力安全工作规程',
    note: '教育部国家级职教平台，技能培训与安全规程资源可直接引用'
  },
  {
    code: 'BILIBILI', name: '哔哩哔哩 · 技术区', site: 'search.bilibili.com', category: '视频',
    home: 'https://www.bilibili.com/', search: 'https://search.bilibili.com/all?keyword={kw}', probe: '继电保护',
    note: '现场作业视频讲解，适合入门补课与动作顺序模仿'
  },
  {
    code: 'CEC', name: '中国电力企业联合会', site: 'cec.org.cn', category: '行业',
    home: 'https://www.cec.org.cn/', search: 'https://www.cec.org.cn/search?keyword={kw}', probe: '继电保护',
    note: '行业协会口径：技能等级评价、培训规范与安全政策'
  },
  {
    code: 'WANFANG', name: '万方数据', site: 's.wanfangdata.com.cn', category: '学术',
    home: 'https://www.wanfangdata.com.cn/', search: 'https://s.wanfangdata.com.cn/paper?q={kw}', probe: '电气设备 状态检修',
    note: '学术论文与标准文献，支撑进阶分析与状态检修'
  },
  {
    code: 'CNKI', name: '中国知网 · 期刊论文', site: 'kns.cnki.net', category: '学术',
    home: 'https://www.cnki.net/', search: 'https://kns.cnki.net/kns8s/search?kw={kw}', probe: '故障录波 分析',
    note: '期刊论文与事故案例，用于难题归因与复盘'
  }
];

// 外网课程库：一条 = 一个可检索到的公开课程入口，keyword 是放到平台上检索的关键词。
const COURSES = [
  { title: '继电保护原理与整定计算 · 高校慕课', source: 'ICOURSE163', type: '慕课', duration: '按课程', skill: '继电保护', level: '入门', org: '高校慕课 · 电气类', keyword: '继电保护 整定计算', tags: '继电保护,整定计算,原理', reason: '理论考试 62 分未通过，先补原理与整定计算' },
  { title: '电力系统继电保护（名校公开课）', source: 'XUETANGX', type: '慕课', duration: '按课程', skill: '继电保护', level: '进阶', org: '名校公开课 · 电气工程', keyword: '电力系统继电保护', tags: '继电保护,二次回路,保护配置', reason: '继保 L1→L3 缺口最大，系统学保护配置与二次回路' },
  { title: '继电保护装置定值整定与校验实操', source: 'BILIBILI', type: '视频', duration: '按视频', skill: '继电保护', level: '进阶', org: '技术区 · 现场实操', keyword: '继电保护 定值整定', tags: '定值,整定,校验', reason: '定值核对与投退需师傅复核，先看现场实操' },
  { title: '软压板投退逻辑与顺序讲解', source: 'BILIBILI', type: '视频', duration: '按视频', skill: '继电保护', level: '入门', org: '技术区 · 装置逻辑', keyword: '软压板 投退顺序', tags: '软压板,压板投退,逻辑', reason: '错题集中在软压板投退顺序' },
  { title: '继电保护技能等级评价与培训规范', source: 'CEC', type: '行业', duration: '按需检索', skill: '继电保护', level: '精通', org: '行业协会 · 技能评价', keyword: '继电保护 技能等级 评价', tags: '技能等级,评价规范,岗位', reason: '岗位 L1-L3 评价口径的权威出处' },
  { title: '继电保护定值配合与整定计算论文', source: 'CNKI', type: '学术', duration: '按需检索', skill: '继电保护', level: '精通', org: '学术期刊 · 继电保护', keyword: '继电保护 定值配合', tags: '定值配合,论文,案例', reason: '定值配合类难题的进阶依据' },
  { title: '变电站倒闸操作规范与实操演示', source: 'BILIBILI', type: '视频', duration: '按视频', skill: '倒闸操作', level: '入门', org: '技术区 · 现场实操', keyword: '倒闸操作 步骤', tags: '倒闸操作,实操,顺序', reason: '已达标技能，保持手感并作为带教素材' },
  { title: '电力安全工作规程（变电站部分）解读', source: 'SMARTEDU_VOC', type: '职教', duration: '按课程', skill: '倒闸操作', level: '入门', org: '国家级职教平台 · 电力类', keyword: '电力安全工作规程 变电站', tags: '安规,变电站,红线', reason: '操作票与安规条款逐条对照学习' },
  { title: '变电运维值班员岗位技能实训', source: 'SMARTEDU_VOC', type: '职教', duration: '按课程', skill: '倒闸操作', level: '进阶', org: '国家级职教平台 · 电力类', keyword: '变电运维 实训', tags: '变电运维,实训,岗位', reason: '变电运维一班岗位技能标准化训练' },
  { title: '高电压技术（绝缘与试验基础）', source: 'ICOURSE163', type: '慕课', duration: '按课程', skill: '高压试验', level: '进阶', org: '高校慕课 · 电气类', keyword: '高电压技术 绝缘试验', tags: '高压试验,绝缘,试验', reason: '高压试验 L1→L2 缺口，系统补试验原理' },
  { title: 'SF6 气体检测与微水试验作业演示', source: 'BILIBILI', type: '视频', duration: '按视频', skill: '高压试验', level: '入门', org: '技术区 · 现场实操', keyword: 'SF6 微水 检测', tags: 'SF6,微水,气体检测', reason: '实操报告暴露取样与读数细节不足' },
  { title: '电气设备状态检修与试验案例分析', source: 'WANFANG', type: '学术', duration: '按需检索', skill: '高压试验', level: '进阶', org: '学术文献 · 状态检修', keyword: '电气设备 状态检修', tags: '状态检修,试验数据,案例', reason: '用试验数据比对判断设备状态' },
  { title: '电力系统故障分析与录波图识读', source: 'ICOURSE163', type: '慕课', duration: '按课程', skill: '故障录波', level: '进阶', org: '高校慕课 · 电气类', keyword: '电力系统故障分析', tags: '故障录波,故障分析,波形', reason: '故障录波 L1→L2 缺口，补分析方法' },
  { title: '录波波形与开关变位识读入门', source: 'BILIBILI', type: '视频', duration: '按视频', skill: '故障录波', level: '入门', org: '技术区 · 二次回路', keyword: '故障录波 波形识读', tags: '录波,波形,变位', reason: '能读波形但不能独立归因，先练识读' },
  { title: '继电保护故障录波典型案例分析', source: 'CNKI', type: '学术', duration: '按需检索', skill: '故障录波', level: '进阶', org: '学术期刊 · 继电保护', keyword: '故障录波 案例分析', tags: '录波,案例,论文', reason: '典型录波案例，支撑录波 L2 判定' },
  { title: '电力安全生产法规与一票否决条款', source: 'CEC', type: '行业', duration: '按需检索', skill: '安全规程', level: '入门', org: '行业协会 · 安全政策', keyword: '电力安全 一票否决', tags: '安全规程,一票否决,政策', reason: '安全规程月度必修的政策出处' },
  { title: '有限空间作业安全与气体检测规定', source: 'SMARTEDU_VOC', type: '职教', duration: '按课程', skill: '安全规程', level: '入门', org: '国家级职教平台 · 安全类', keyword: '有限空间作业 气体检测', tags: '有限空间,气体检测,通风', reason: '电缆沟作业先通风检测后再进入' },
  { title: '电力事故案例与责任追溯专题', source: 'CNKI', type: '学术', duration: '按需检索', skill: '安全规程', level: '进阶', org: '学术期刊 · 电力安全', keyword: '电力 事故案例 责任追溯', tags: '事故案例,责任,复盘', reason: '班组安全学习与案例通报素材' },
  { title: '电气工程基础与电工原理补课', source: 'XUETANGX', type: '慕课', duration: '按课程', skill: '继电保护', level: '入门', org: '名校公开课 · 电气工程', keyword: '电气工程 电工基础', tags: '电工,基础,入门', reason: '基础薄弱时先补电工原理再上继保' },
  { title: '变电检修与高压试验作业安全', source: 'SMARTEDU_VOC', type: '职教', duration: '按课程', skill: '高压试验', level: '入门', org: '国家级职教平台 · 电力类', keyword: '变电检修 高压试验 安全', tags: '高压试验,检修,安全', reason: '试验作业安全措施与监护要求' }
];

// 核验平台检索地址：请求 {kw} 换成 probe 关键词后的真实地址，记录状态码。
for (const platform of PLATFORMS) {
  const probeUrl = platform.search.replace('{kw}', encodeURIComponent(platform.probe));
  platform.http = 0;
  try {
    const res = await fetch(probeUrl, { redirect: 'follow', headers: { 'User-Agent': UA, 'Accept-Language': 'zh-CN,zh;q=0.9' } });
    platform.http = res.status;
  } catch (error) {
    platform.http = 0;
  }
  platform.probe_url = probeUrl;
  console.log(String(platform.http).padStart(3) + '  ' + platform.code + '  ' + platform.name + '  ' + probeUrl);
}

const failed = PLATFORMS.filter((p) => p.http !== 200);
console.log('\nPROBLEMS=' + (failed.length ? failed.map((p) => p.code + '(' + p.http + ')').join(' ;; ') : 'none'));

const q = (v) => "'" + String(v == null ? '' : v).replace(/\\/g, '\\\\').replace(/'/g, "''") + "'";
const checkedAt = new Date().toISOString().slice(0, 10);
const platformByCode = new Map(PLATFORMS.map((p) => [p.code, p]));
const target = new URL('../db/init/006_external_course.sql', import.meta.url);

const sql = [];
sql.push('SET NAMES utf8mb4;');
sql.push('-- 由 tools/fetch-courses.mjs 生成，写入 MySQL 的 external_course_source / external_course 表。');
sql.push('-- 平台「学习与考试 → 推荐资源 → 外网课程搜索」的数据源：重新生成后覆盖执行本文件即可刷新（幂等）。');
sql.push('-- 只收录各平台公开的检索入口与检索关键词，不复制平台课程正文；http_code 是核验该平台检索地址时的真实状态码。');
sql.push('USE train_system;');
sql.push('');
sql.push('-- 与 db/init/001_schema.sql 中的定义一致；这里再写一次，便于对已有数据库单独补跑本文件。');
sql.push('CREATE TABLE IF NOT EXISTS external_course_source (');
sql.push('  code VARCHAR(32) PRIMARY KEY,');
sql.push('  name VARCHAR(128) NOT NULL,');
sql.push('  site VARCHAR(128) NOT NULL,');
sql.push('  category VARCHAR(16) NOT NULL,');
sql.push('  home_url VARCHAR(300) NOT NULL,');
sql.push('  search_url VARCHAR(400) NOT NULL,');
sql.push("  probe_keyword VARCHAR(64) NOT NULL DEFAULT '',");
sql.push('  http_code INT NOT NULL DEFAULT 200,');
sql.push("  checked_at VARCHAR(16) NOT NULL DEFAULT '',");
sql.push("  note VARCHAR(300) NOT NULL DEFAULT '',");
sql.push('  sort_no INT NOT NULL DEFAULT 0');
sql.push(') ENGINE=InnoDB;');
sql.push('');
sql.push('CREATE TABLE IF NOT EXISTS external_course (');
sql.push('  id BIGINT AUTO_INCREMENT PRIMARY KEY,');
sql.push('  title VARCHAR(200) NOT NULL,');
sql.push('  source_code VARCHAR(32) NOT NULL,');
sql.push('  course_type VARCHAR(16) NOT NULL,');
sql.push('  duration VARCHAR(32) NOT NULL,');
sql.push('  skill VARCHAR(128) NOT NULL,');
sql.push('  level VARCHAR(16) NOT NULL,');
sql.push("  org VARCHAR(128) NOT NULL DEFAULT '',");
sql.push('  search_keyword VARCHAR(128) NOT NULL,');
sql.push('  url VARCHAR(400) NOT NULL,');
sql.push("  tags VARCHAR(200) NOT NULL DEFAULT '',");
sql.push("  match_reason VARCHAR(300) NOT NULL DEFAULT '',");
sql.push('  sort_no INT NOT NULL DEFAULT 0,');
sql.push('  KEY idx_external_course_skill (skill)');
sql.push(') ENGINE=InnoDB;');
sql.push('');
sql.push('INSERT INTO external_course_source (code, name, site, category, home_url, search_url, probe_keyword, http_code, checked_at, note, sort_no) VALUES');
sql.push(PLATFORMS.map((p, i) => '  (' + [
  q(p.code), q(p.name), q(p.site), q(p.category), q(p.home), q(p.search), q(p.probe), String(Number(p.http) || 0), q(checkedAt), q(p.note), String((i + 1) * 10)
].join(', ') + ')').join(',\n'));
sql.push('  ON DUPLICATE KEY UPDATE name=VALUES(name), site=VALUES(site), category=VALUES(category), home_url=VALUES(home_url), search_url=VALUES(search_url), probe_keyword=VALUES(probe_keyword), http_code=VALUES(http_code), checked_at=VALUES(checked_at), note=VALUES(note), sort_no=VALUES(sort_no);');
sql.push('');
sql.push('INSERT INTO external_course (id, title, source_code, course_type, duration, skill, level, org, search_keyword, url, tags, match_reason, sort_no) VALUES');
sql.push(COURSES.map((c, i) => {
  const platform = platformByCode.get(c.source);
  if (!platform) throw new Error('课程来源平台未登记：' + c.source);
  const url = platform.search.replace('{kw}', encodeURIComponent(c.keyword));
  return '  (' + [
    String(i + 1), q(c.title), q(c.source), q(c.type), q(c.duration), q(c.skill), q(c.level), q(c.org), q(c.keyword), q(url), q(c.tags), q(c.reason), String((i + 1) * 10)
  ].join(', ') + ')';
}).join(',\n'));
sql.push('  ON DUPLICATE KEY UPDATE title=VALUES(title), source_code=VALUES(source_code), course_type=VALUES(course_type), duration=VALUES(duration), skill=VALUES(skill), level=VALUES(level), org=VALUES(org), search_keyword=VALUES(search_keyword), url=VALUES(url), tags=VALUES(tags), match_reason=VALUES(match_reason), sort_no=VALUES(sort_no);');
sql.push('');
writeFileSync(target, sql.join('\n'), 'utf8');

console.log('\n写入 db/init/006_external_course.sql：平台=' + PLATFORMS.length + ' 课程=' + COURSES.length + ' 核验日期=' + checkedAt);
