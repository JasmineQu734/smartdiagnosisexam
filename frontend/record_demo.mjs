/* 天元杯演示视频录制：真实浏览器走完整演示动线，CDP 屏幕流逐帧捕获 → mp4。
   用法（必须在 frontend 目录下运行）：node record_demo.mjs
   产物：frontend/tmp/record/frames/*.jpg + frontend/tmp/record/demo_raw.mp4 */
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

const BASE = 'http://localhost:5199';
const OUT = path.resolve('tmp/record');
const FRAMES = path.join(OUT, 'frames');
fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(FRAMES, { recursive: true });

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PASS = '123456';

const browser = await puppeteer.launch({
  executablePath: EDGE,
  headless: 'new',
  args: ['--window-size=1680,980', '--disable-gpu-sandbox', '--no-sandbox', '--use-gl=angle', '--enable-unsafe-swiftshader', '--autoplay-policy=no-user-gesture-required']
});
const page = await browser.newPage();
await page.setViewport({ width: 1600, height: 900, deviceScaleFactor: 1 });

/* ---------- 屏幕流捕获 ---------- */
const frames = []; // {t: Date.now(), file}
let frameIdx = 0;
const cdp = await page.target().createCDPSession();
cdp.on('Page.screencastFrame', async (e) => {
  const f = path.join(FRAMES, String(frameIdx++).padStart(6, '0') + '.jpg');
  fs.writeFileSync(f, Buffer.from(e.data, 'base64'));
  frames.push({ t: Date.now(), file: f });
  try { await cdp.send('Page.screencastFrameAck', { sessionId: e.sessionId }); } catch {}
});
await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 68, maxWidth: 1600, maxHeight: 900, everyNthFrame: 1 });

/* ---------- 虚拟光标 + 场景字幕 ---------- */
await page.evaluateOnNewDocument(() => {
  document.addEventListener('DOMContentLoaded', () => {
    const cur = document.createElement('div');
    cur.id = '__vc';
    cur.style.cssText = 'position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483647;pointer-events:none;transition:transform .45s cubic-bezier(.4,0,.2,1);filter:drop-shadow(0 2px 4px rgba(0,0,0,.6));';
    cur.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2 L4 20 L9.5 15 L13 22 L16 20.5 L12.5 14 L20 13.5 Z" fill="#fff" stroke="#111" stroke-width="1.2"/></svg>';
    document.body.appendChild(cur);
    const bar = document.createElement('div');
    bar.id = '__scenebar';
    bar.style.cssText = 'position:fixed;left:50%;top:18px;transform:translateX(-50%) translateY(-8px);z-index:2147483647;pointer-events:none;padding:9px 26px;border-radius:999px;background:rgba(10,14,24,.82);color:#ffd76a;font:600 17px/1 "Microsoft YaHei",sans-serif;letter-spacing:1px;box-shadow:0 4px 18px rgba(0,0,0,.45);opacity:0;transition:all .5s ease;border:1px solid rgba(255,215,106,.35);';
    document.body.appendChild(bar);
    window.__moveCursor = (x, y) => { cur.style.transform = `translate(${x - 2}px,${y - 2}px)`; };
    window.__showScene = (t) => { bar.textContent = t; bar.style.opacity = '1'; bar.style.transform = 'translateX(-50%) translateY(0)'; };
  });
});
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
async function cursorTo(sel, pad = 0.5) {
  const box = await (await page.$(sel)).boundingBox();
  if (!box) return;
  const x = box.x + box.width * pad, y = box.y + box.height * pad;
  await page.evaluate(([x, y]) => window.__moveCursor(x, y), [x, y]);
  await sleep(500);
}
async function clickAt(sel, pad = 0.5) { await cursorTo(sel, pad); await page.click(sel); }
async function scene(t) { await page.evaluate((t) => window.__showScene(t), t); }
/* 心跳：静止时也保持出帧 */
const heartbeat = setInterval(() => {
  page.evaluate(() => window.__moveCursor && window.__moveCursor(innerWidth / 2, innerHeight / 2)).catch(() => {});
}, 450);

/* ---------- 通用动作 ---------- */
async function gotoLogin() {
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('input[placeholder^="账号"]', { timeout: 30000 });
  await sleep(2500); // 等 3D 场景起来
}
async function login(user) {
  await gotoLogin();
  await scene(user === 'zhangwei' ? '登录 · 员工视角（3D 数字孪生登录页）' : `切换账号 · ${user}`);
  await sleep(2500);
  // 拖拽 3D 登录场景 360° 旋转
  await page.mouse.move(1100, 420); await page.mouse.down();
  for (let i = 1; i <= 14; i++) { await page.mouse.move(1100 + i * 16, 420 + Math.sin(i) * 6); await sleep(90); }
  await page.mouse.up();
  await sleep(1200);
  await page.evaluate(() => window.__showScene('登录 · 输入账号与验证码'));
  const code = await page.evaluate(() => window.__capCode || '');
  await cursorTo('input[placeholder^="账号"]'); await page.type('input[placeholder^="账号"]', user, { delay: 60 });
  await cursorTo('input[placeholder^="密码"]'); await page.type('input[placeholder^="密码"]', PASS, { delay: 40 });
  await cursorTo('input[placeholder^="验证码"]'); await page.type('input[placeholder^="验证码"]', code, { delay: 40 });
  await clickAt('button.btn');
  await page.waitForSelector('aside nav button', { timeout: 30000 });
  await sleep(1800);
}
async function nav(label) {
  await page.evaluate((label) => {
    const btns = [...document.querySelectorAll('aside nav button')];
    const b = btns.find(x => x.textContent.trim() === label);
    if (b) b.click();
  }, label);
  await sleep(2200);
}
async function scrollBody(dy, ms = 900) {
  await page.evaluate((dy) => { const m = document.querySelector('main') || document.scrollingElement; (m.scrollTo ? m.scrollBy({ top: dy, behavior: 'smooth' }) : window.scrollBy({ top: dy, behavior: 'smooth' })); }, dy);
  await sleep(ms);
}

/* ---------- 场景动线 ---------- */
// 1. 员工登录
await login('zhangwei');

// 2. 技能雷达
await scene('① 技能雷达 —— 我会什么、缺什么，量化呈现');
await nav('技能雷达'); await sleep(1500);
await cursorTo('.radar, canvas, .panel', 0.4).catch(() => {}); await sleep(1500);
await scrollBody(500); await sleep(1500); await scrollBody(-500);

// 3. 个人能力
await scene('② 个人能力 —— 硬技能 / 软技能 / 安全 / 实操 / 考试 / 证书');
await nav('个人能力'); await sleep(1500);
await scrollBody(600); await sleep(1600); await scrollBody(-600);

// 4. 个人自画像
await scene('③ 个人自画像 —— 职业目标、师傅评价与岗位匹配度');
await nav('个人自画像'); await sleep(1500);
await scrollBody(600); await sleep(1600); await scrollBody(-600);

// 5. 记忆展示
await scene('④ 记忆展示 —— 学习 / 错误 / 实操 / 考试记忆按时间线留存');
await nav('记忆展示'); await sleep(1500);
await scrollBody(600); await sleep(1800);

// 6. 成长轨迹
await scene('⑤ 成长轨迹 —— 技能等级、证书、任务与晋升准备度');
await nav('成长轨迹'); await sleep(1500);
await scrollBody(600); await sleep(1800); await scrollBody(-600);

// 7. 差距与建议
await scene('⑥ 差距与建议 —— AI 智能体给出课程、带教与模拟考计划');
await nav('差距与建议'); await sleep(1800);
await scrollBody(700); await sleep(1800);

// 8. 学习与考试：摘要 → 练习作答 → 考试列表
await scene('⑦ 学习与考试 —— 先看学习地图');
await nav('学习与考试'); await sleep(2000);
await scrollBody(500); await sleep(1400); await scrollBody(-500);
await scene('⑧ 现场抽题练习 —— 学完就练');
await page.evaluate(() => {
  const els = [...document.querySelectorAll('button, .el-tabs__item, [role="tab"]')];
  const b = els.find(x => x.textContent.includes('练习'));
  if (b) b.click();
});
await sleep(1800);
const practiceBtn = await page.$('button');
await page.evaluate(() => {
  const b = [...document.querySelectorAll('button')].find(x => x.textContent.includes('开始抽题') || x.textContent.includes('开始练习'));
  if (b) b.click();
});
await sleep(2200);
await scene('⑨ 作答与判定 —— 每道题即时反馈');
const opt = await page.$('.practice-option, .el-radio, .option');
if (opt) { await cursorTo('.practice-option, .el-radio, .option'); await page.click('.practice-option, .el-radio, .option'); }
await sleep(2000);
// 关闭练习弹窗，避免遮罩挡住后续导航
await page.evaluate(() => {
  const b = [...document.querySelectorAll('button')].find(x => x.textContent.includes('稍后再答') || x.textContent.includes('取消') || x.textContent.includes('关 闭'));
  if (b) b.click(); else document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
});
await sleep(1200);

// 9. 实操任务
await scene('⑩ 实操任务 —— 现场作业派发与报告闭环');
await nav('实操任务'); await sleep(2000);
await scrollBody(600); await sleep(1800); await scrollBody(-600);

// 10. 3D 数字孪生
await scene('⑪ 3D 数字孪生园区 —— 沉浸式巡检演练');
await nav('3D 数字孪生'); await sleep(6000); // 等 WebGL 场景加载
await page.mouse.move(800, 460); await page.mouse.down();
for (let i = 1; i <= 18; i++) { await page.mouse.move(800 + i * 14, 460 + Math.sin(i / 2) * 10); await sleep(110); }
await page.mouse.up(); await sleep(1000);
for (let i = 1; i <= 8; i++) { await page.mouse.wheel({ deltaY: -160 }); await sleep(150); } // 滚轮推近
await sleep(2000);

// 11. 组长：班组报告
await login('limin');
await scene('⑫ 班组长 —— 班组报告与归因确认');
await nav('班组报告'); await sleep(2200);
await scrollBody(700); await sleep(2000);

// 12. 老总：四个页面全走
await login('wangzong');
await scene('⑬ 人才驾驶舱 —— 梯队 / 达标 / 成本 / 风险一屏总览');
await nav('人才驾驶舱'); await sleep(3500);
await scrollBody(500); await sleep(1800); await scrollBody(-500);
await scene('⑭ 全公司技能矩阵 —— 谁强谁弱、关键岗位有无备份');
await nav('全公司技能矩阵'); await sleep(2500);
await scrollBody(600); await sleep(1800);
await scene('⑮ 培训看板 —— 完成率、成本与 ROI');
await nav('培训看板'); await sleep(2500);
await scrollBody(500); await sleep(1600);
await scene('⑯ 运行诊断 Agent —— 全公司诊断结论可解释');
await nav('运行诊断 Agent'); await sleep(2500);
await scrollBody(600); await sleep(2200);

clearInterval(heartbeat);
await cdp.send('Page.stopScreencast').catch(() => {});
await browser.close();

/* ---------- 帧序列 → mp4（15fps 最近邻采样） ---------- */
frames.sort((a, b) => a.t - b.t);
const t0 = frames[0].t, t1 = frames[frames.length - 1].t;
const durMs = t1 - t0;
const FPS = 15, total = Math.floor(durMs / 1000 * FPS);
let fi = 0;
const seqDir = path.join(OUT, 'seq');
fs.mkdirSync(seqDir, { recursive: true });
for (let i = 0; i < total; i++) {
  const target = t0 + i * 1000 / FPS;
  while (fi + 1 < frames.length && frames[fi + 1].t <= target) fi++;
  fs.copyFileSync(frames[fi].file, path.join(seqDir, String(i).padStart(6, '0') + '.jpg'));
}
console.log(JSON.stringify({ frames: frames.length, durSec: (durMs / 1000).toFixed(1), seq: total }));
