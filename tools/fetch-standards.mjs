// 抓取国家市场监督管理总局「国家标准全文公开系统」的真实标准数据，生成
// db/init/005_standard_ref.sql（平台「标准依据库」的数据源，系统只用 MySQL，标准落在 standard_ref 表）。
// 运行： node tools/fetch-standards.mjs   （需要外网访问 openstd.samr.gov.cn）
// 说明：只抓取标准号/名称/状态/发布-实施日期/详情页链接，不复制标准正文内容。
import { writeFileSync } from 'node:fs';

const BASE = 'https://openstd.samr.gov.cn/bzgk/gb/';
const SOURCE = '国家标准全文公开系统（国家市场监督管理总局）';
const CURATED = [
  'GB 26860-2011', 'GB/T 14285-2023', 'GB/T 40599-2021', 'GB/T 40584-2021', 'GB/T 45568-2025',
  'GB/T 7261-2026', 'GB/T 45906.1-2025', 'GB/T 45906.5-2025', 'GB/T 45906.8-2025', 'GB/T 45906.10-2025',
  'GB/T 16927.1-2011', 'GB/T 16927.2-2013', 'GB/T 16927.3-2010', 'GB/T 7354-2018', 'GB/T 2900.19-2022',
  'GB/T 22390.6-2026', 'GB 46768-2025', 'GB/T 40096.6-2024', 'GB/T 40096.7-2024', 'GB/T 42150.1-2022'
];
const OVERRIDES = {
  'GB 26860-2011': { implemented: '2012-06-01', date_note: '实施日期取自该系统标准查询列表页（详情页未单列）' }
};
const TERMS = ['继电保护', '变电站', '高电压试验', '故障录波', '有限空间', 'GB 26860', '电工术语', '就地化继电保护'];

const index = new Map();
for (const term of TERMS) {
  const url = BASE + 'std_list?p.p1=0&p.p90=circulation_date&p.p91=desc&p.p2=' + encodeURIComponent(term);
  const html = await (await fetch(url)).text();
  for (const block of html.split('<tr>').slice(1)) {
    const std = block.match(/showInfo\('([0-9A-F]{32})'\);">([^<]+)<\/a><\/td>/);
    const name = block.match(/class="mytxt"[\s\S]{0,240}?showInfo\('([0-9A-F]{32})'\);">([^<]+)<\/a>/);
    if (!std || !name) continue;
    const key = std[2].trim();
    if (!index.has(key)) {
      const listDates = [...block.matchAll(/(\d{4}-\d{2}-\d{2})\s+00:00:00/g)].map((m) => m[1]);
      const listStatus = (block.match(/text-success[^>]*>([^<]+)</) || [])[1] || '';
      index.set(key, {
        standard: key, hcno: std[1], search_name: name[2].trim().replace(/\s+/g, ' '),
        list_status: listStatus.replace(/<[^>]*>/g, '').trim(), list_published: listDates[0] || '', list_implemented: listDates[1] || ''
      });
    }
  }
}
console.log('检索到标准条目=' + index.size);

const clean = (s) => (s || '').replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
const out = [];
const problems = [];
for (const std of CURATED) {
  const hit = index.get(std);
  if (!hit) { problems.push(std + ' 未在检索结果中找到'); continue; }
  const url = BASE + 'newGbInfo?hcno=' + hit.hcno;
  const res = await fetch(url);
  const html = await res.text();
  const flat = html.replace(/\s+/g, ' ');
  const cn = clean((flat.match(/中文标准名称[\s\S]{0,160}?>\s*([^<]{4,140})</) || [])[1]);
  let status = clean((flat.match(/(现行|即将实施|废止)/) || [])[1]) || hit.list_status || '';
  let dates = [...flat.matchAll(/(\d{4}-\d{2}-\d{2})/g)].map((m) => m[1]);
  let note = '';
  if (dates.length < 2) {
    const merged = [dates[0] || hit.list_published, hit.list_implemented].filter(Boolean);
    dates = merged;
    if (hit.list_implemented) note = '发布/实施日期按该系统查询页显示（详情页未单列发布日期）';
  }
  const pageStd = (flat.match(/GB(?:\s?\/T)?\s?\d+(?:\.\d+)?-\d{4}/) || [])[0] || '';
  const ok = cn && status && dates.length >= 2;
  if (!ok) problems.push(std + ' 详情解析不完整');
  const ov = OVERRIDES[std] || {};
  out.push({
    standard: std,
    name: cn || hit.search_name,
    status,
    published: dates[0] || '',
    implemented: ov.implemented || dates[1] || '',
    url,
    page_standard: pageStd.replace(/\s+/g, ' '),
    http: res.status,
    date_note: ov.date_note || note
  });
}
console.log('\n标准号 | 名称 | 状态 | 发布 | 实施 | http');
for (const r of out) console.log(r.standard + ' | ' + r.name + ' | ' + r.status + ' | ' + r.published + ' | ' + r.implemented + ' | ' + r.http);
console.log('\nPROBLEMS=' + (problems.length ? problems.join(' ;; ') : 'none'));

// 输出 MySQL 种子脚本：重新抓取后覆盖执行本文件即可刷新平台的标准依据库（幂等）。
const q = (v) => "'" + String(v == null ? '' : v).replace(/\\/g, '\\\\').replace(/'/g, "''") + "'";
const fetchedAt = new Date().toISOString().slice(0, 10);
const note = '标准号、名称、状态与发布/实施日期均取自国家市场监督管理总局「国家标准全文公开系统」查询结果，链接为该系统的标准详情页，可点开核对。';
const sql = [];
sql.push('-- 由 tools/fetch-standards.mjs 抓取生成，写入 MySQL 的 standard_ref / standard_source 表。');
sql.push('-- 平台「标准依据库」的数据源；重新抓取后覆盖执行本文件即可刷新（幂等）。');
sql.push('USE train_system;');
sql.push('');
sql.push('INSERT INTO standard_source (id, source, source_url, fetched_at, note) VALUES');
sql.push('  (1, ' + q(SOURCE) + ', ' + q(BASE + 'std_list') + ', ' + q(fetchedAt) + ', ' + q(note) + ')');
sql.push('  ON DUPLICATE KEY UPDATE source=VALUES(source), source_url=VALUES(source_url), fetched_at=VALUES(fetched_at), note=VALUES(note);');
sql.push('');
sql.push('INSERT INTO standard_ref (std_no, name, status, published, implemented, detail_url, page_standard, http_code, date_note, sort_no) VALUES');
sql.push(out.map((r, i) => '  (' + [
  q(r.standard), q(r.name), q(r.status), q(r.published || '—'), q(r.implemented || '—'),
  q(r.url), q(r.page_standard), String(Number(r.http) || 200), q(r.date_note), String((i + 1) * 10)
].join(', ') + ')').join(',\n'));
sql.push('  ON DUPLICATE KEY UPDATE name=VALUES(name), status=VALUES(status), published=VALUES(published), implemented=VALUES(implemented), detail_url=VALUES(detail_url), page_standard=VALUES(page_standard), http_code=VALUES(http_code), date_note=VALUES(date_note), sort_no=VALUES(sort_no);');
sql.push('');
writeFileSync(new URL('../db/init/005_standard_ref.sql', import.meta.url), sql.join('\n'), 'utf8');

console.log('\n写入 db/init/005_standard_ref.sql 条数=' + out.length);
