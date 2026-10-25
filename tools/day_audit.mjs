/* 昼夜主题逐页审计：真实浏览器登录每个角色，遍历全部导航页，
   白天模式下扫描所有元素的背景亮度，揪出「白底上残留深色」的组件。
   用法：node tools/day_audit.mjs [baseUrl]  （默认 http://localhost:5199，需 DEV 模式取验证码） */
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.argv[2] || 'http://localhost:5199';
const OUT = path.resolve('tmp/audit');
fs.mkdirSync(OUT, { recursive: true });

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const ACCOUNTS = [
  { user: 'zhangwei', pass: '123456', role: 'EMPLOYEE' },
  { user: 'limin', pass: '123456', role: 'TEAM_LEAD' },
  { user: 'wangzong', pass: '123456', role: 'EXECUTIVE' },
  { user: 'admin', pass: '123456', role: 'ADMIN' }
];

/* 亮度（0-255）：解析 rgb()/rgba() */
function lum(color) {
  const m = color.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/);
  if (!m) return null;
  const a = m[4] === undefined ? 1 : parseFloat(m[4]);
  if (a < 0.25) return null;                      // 近乎透明，不算
  return 0.2126 * +m[1] + 0.7152 * +m[2] + 0.0722 * +m[3];
}

const browser = await puppeteer.launch({
  executablePath: EDGE,
  headless: 'new',
  args: ['--window-size=1680,950', '--disable-gpu', '--no-sandbox']
});
const page = await browser.newPage();
await page.setViewport({ width: 1600, height: 900 });
await page.evaluateOnNewDocument(() => {
  localStorage.setItem('wb-theme', 'day');       // 强制白天模式
});

const report = [];

async function login(acc) {
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('input[placeholder="账号"]', { timeout: 20000 });
  await new Promise(r => setTimeout(r, 800));    // 等 onMounted 画验证码
  const code = await page.evaluate(() => window.__capCode || '');
  await page.type('input[placeholder="账号"]', acc.user, { delay: 10 });
  await page.type('input[placeholder="密码"]', acc.pass, { delay: 10 });
  await page.type('input[placeholder="验证码"]', code, { delay: 10 });
  await page.click('button.btn');
  await page.waitForSelector('aside nav button', { timeout: 20000 });
  await new Promise(r => setTimeout(r, 1500));
}

/* 扫当前页：深背景元素 + 深背景上的浅色文字 */
async function scanPage(role, label) {
  const offenders = await page.evaluate(() => {
    const lum = (c) => {
      const m = c.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/);
      if (!m) return null;
      const a = m[4] === undefined ? 1 : parseFloat(m[4]);
      if (a < 0.25) return null;
      return 0.2126 * +m[1] + 0.7152 * +m[2] + 0.0722 * +m[3];
    };
    const out = [];
    const scope = document.querySelector('main') || document.body;
    scope.querySelectorAll('*').forEach((el) => {
      if (el.closest('aside') || ['CANVAS', 'IFRAME', 'SCRIPT', 'STYLE'].includes(el.tagName)) return;
      const cs = getComputedStyle(el);
      const L = lum(cs.backgroundColor);
      if (L !== null && L < 110) {
        // 元素自身有内容面积才算（宽高 > 20px）
        const r = el.getBoundingClientRect();
        if (r.width > 20 && r.height > 12) {
          out.push({
            cls: (el.className && el.className.toString().slice(0, 80)) || el.tagName,
            bg: cs.backgroundColor,
            text: (el.innerText || '').slice(0, 60).replace(/\n/g, ' ')
          });
        }
      }
    });
    return out;
  });
  if (offenders.length) {
    const shot = path.join(OUT, `${role}-${label}.png`);
    await page.screenshot({ path: shot });
    report.push({ role, page: label, count: offenders.length, offenders: offenders.slice(0, 12), shot });
  }
}

for (const acc of ACCOUNTS) {
  try {
    await login(acc);
  } catch (e) {
    report.push({ role: acc.role, error: '登录失败: ' + e.message.slice(0, 120) });
    continue;
  }
  const labels = await page.$$eval('aside nav button', (btns) => btns.map((b) => b.innerText.trim()));
  for (let i = 0; i < labels.length; i++) {
    const label = labels[i].replace(/\s+/g, '');
    await page.click(`aside nav button:nth-of-type(${i + 1})`).catch(() => {});
    await new Promise(r => setTimeout(r, 1400));
    await scanPage(acc.role, `${i}-${label}`);
  }
}

await browser.close();
fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(report, null, 2));
console.log(report.map((r) => r.error ? `${r.role}: ${r.error}` : `${r.role}/${r.page}: ${r.count} 个深色块`).join('\n') || '无问题');
