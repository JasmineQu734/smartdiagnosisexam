import { buildPptx, box, textBox, tableFrame, P, inch, SLIDE_W, INK, NAVY, BLUE, ACCENT, MUTED, LIGHT, LINE } from './pptx-kit.mjs';
import { writeFileSync } from 'node:fs';

const ML = inch(0.8);
const CW = SLIDE_W - 2 * ML;
const TOP = inch(1.5);

function newSlide(background) {
  const shapes = [];
  let counter = 2;
  return {
    shapes,
    background: background || 'FFFFFF',
    id: () => counter++,
  };
}

function head(ctx, title, subtitle) {
  const paras = [P(title, { size: 2600, bold: true, color: NAVY, after: 60 })];
  if (subtitle) paras.push(P(subtitle, { size: 1250, color: MUTED, before: 0 }));
  ctx.shapes.push(textBox({ id: ctx.id(), name: 'Title', x: ML, y: inch(0.36), w: CW, h: inch(0.9), anchor: 't', paras }));
  ctx.shapes.push(box({ id: ctx.id(), name: 'AccentBar', x: ML, y: inch(1.26), w: inch(1.0), h: inch(0.055), fill: ACCENT }));
  ctx.shapes.push(box({ id: ctx.id(), name: 'Rule', x: ML, y: inch(1.335), w: CW, h: inch(0.012), fill: LINE }));
}

function footer(ctx, index, label) {
  ctx.shapes.push(textBox({
    id: ctx.id(), name: 'Footer', x: ML, y: inch(6.98), w: inch(8.0), h: inch(0.28), anchor: 't',
    paras: [P(label, { size: 900, color: MUTED, after: 0 })],
  }));
  ctx.shapes.push(textBox({
    id: ctx.id(), name: 'PageNo', x: SLIDE_W - ML - inch(1.2), y: inch(6.98), w: inch(1.2), h: inch(0.28), anchor: 't',
    paras: [P(String(index), { size: 900, color: MUTED, align: 'r', after: 0 })],
  }));
}

function card(ctx, spec) {
  ctx.shapes.push(box({
    id: ctx.id(), name: spec.name || 'Card', x: spec.x, y: spec.y, w: spec.w, h: spec.h, prst: 'roundRect', radius: 6000,
    fill: spec.fill || LIGHT, line: spec.line || LINE, lineWidth: 9525, padX: inch(0.18), padY: inch(0.16), anchor: 't',
    paras: [
      P(spec.title, { size: spec.size || 1400, bold: true, color: NAVY, after: spec.body ? 90 : 0 }),
      ...(spec.body ? [P(spec.body, { size: spec.bodySize || 1150, color: INK, after: 0, lineSpacingPct: 92000 })] : []),
    ],
  }));
}

function kpi(ctx, spec) {
  ctx.shapes.push(box({
    id: ctx.id(), name: 'Kpi', x: spec.x, y: spec.y, w: spec.w, h: spec.h, prst: 'roundRect', radius: 5000,
    fill: 'FFFFFF', line: LINE, padX: inch(0.12), padY: inch(0.1), anchor: 'ctr',
    paras: [
      P(spec.value, { size: 2200, bold: true, color: NAVY, align: 'c', after: 60 }),
      P(spec.label, { size: 1000, color: MUTED, align: 'c', after: 0 }),
    ],
  }));
}

function stepRow(ctx, spec) {
  const gap = spec.gap === undefined ? inch(0.55) : spec.gap;
  const w = (spec.width - gap * (spec.steps.length - 1)) / spec.steps.length;
  spec.steps.forEach((step, index) => {
    const x = spec.x + index * (w + gap);
    ctx.shapes.push(box({
      id: ctx.id(), name: `Step${index + 1}`, x, y: spec.y, w, h: spec.h, prst: 'roundRect', radius: 7000,
      fill: LIGHT, line: LINE, padX: inch(0.14), padY: inch(0.14), anchor: 't',
      paras: [
        P(step.no, { size: 1100, bold: true, color: ACCENT, after: 50 }),
        P(step.title, { size: 1350, bold: true, color: NAVY, after: 70 }),
        P(step.body, { size: 1050, color: INK, after: 0, lineSpacingPct: 92000 }),
      ],
    }));
    if (index < spec.steps.length - 1) {
      const arrowW = Math.min(inch(0.28), Math.max(inch(0.16), gap - inch(0.16)));
      ctx.shapes.push(box({
        id: ctx.id(), name: `Arrow${index + 1}`, prst: 'rightArrow',
        x: x + w + (gap - arrowW) / 2, y: spec.y + spec.h / 2 - inch(0.11), w: arrowW, h: inch(0.22), fill: ACCENT,
      }));
    }
  });
}

const slides = [];
const T = '三层人才技能培训与考试管理系统';
// 1 封面
{
  const ctx = newSlide(NAVY);
  ctx.shapes.push(box({ id: ctx.id(), name: 'Bar', x: ML, y: inch(2.05), w: inch(1.5), h: inch(0.06), fill: ACCENT }));
  ctx.shapes.push(textBox({
    id: ctx.id(), name: 'CoverTitle', x: ML, y: inch(2.3), w: inch(10.6), h: inch(1.2), anchor: 't',
    paras: [P('三层人才技能培训与考试管理系统', { size: 4000, bold: true, color: 'FFFFFF', after: 0 })],
  }));
  ctx.shapes.push(textBox({
    id: ctx.id(), name: 'CoverSub', x: ML, y: inch(3.62), w: inch(10.6), h: inch(0.6), anchor: 't',
    paras: [P('项目技术方案汇报', { size: 2000, color: 'A8C8EE', after: 0 })],
  }));
  ctx.shapes.push(textBox({
    id: ctx.id(), name: 'CoverMeta', x: ML, y: inch(4.6), w: inch(10.6), h: inch(1.2), anchor: 't',
    paras: [
      P('变电运维中心人才培养平台', { size: 1250, color: 'C6DAF2', after: 90 }),
      P('Spring Boot 3.5 · Vue 3 · MySQL 8+ · Docker Compose', { size: 1150, color: '8FB4DC', after: 90 }),
      P('2026 年 9 月', { size: 1150, color: '8FB4DC', after: 0 }),
    ],
  }));
  ctx.shapes.push(box({ id: ctx.id(), name: 'FootBar', x: 0, y: inch(7.36), w: SLIDE_W, h: inch(0.14), fill: ACCENT }));
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}

// 2 背景
{
  const ctx = newSlide();
  head(ctx, '业务背景与现状问题', '变电运维中心的人才培养与用人决策，目前分散在三套口径里');
  const gap = inch(0.3);
  const w = (CW - 2 * gap) / 3;
  const items = [
    { title: '能力差距说不清', body: '岗位要求与个人实际等级之间缺少量化依据，判断主要依赖师傅的经验。' },
    { title: '数据不回流', body: '考试、实操任务与检测报告分散在不同载体，问题暴露后没有回到培训。' },
    { title: '决策没有口径', body: '公司层面的技能缺口与用人成本缺少可核对的数字，计划只能凭估算。' },
  ];
  items.forEach((item, index) => card(ctx, {
    x: ML + index * (w + gap), y: TOP, w, h: inch(2.3), title: item.title, body: item.body, size: 1600, bodySize: 1250,
  }));
  ctx.shapes.push(box({
    id: ctx.id(), name: 'SceneBox', x: ML, y: inch(4.2), w: CW, h: inch(1.15), prst: 'roundRect', radius: 5000,
    fill: 'FFFFFF', line: LINE, padX: inch(0.24), padY: inch(0.16), anchor: 'ctr',
    paras: [P('落地场景：某市供电公司变电运维中心，覆盖继电保护、倒闸操作、高压试验、故障录波与安全规程五类技能。', { size: 1300, color: INK, after: 0 })],
  }));
  ctx.shapes.push(textBox({
    id: ctx.id(), name: 'Goal', x: ML, y: inch(5.62), w: CW, h: inch(0.7), anchor: 't',
    paras: [P('建设目标：用一套平台回答“谁差在哪、怎么补、人和钱怎么配”。', { size: 1400, bold: true, color: BLUE, after: 0 })],
  }));
  footer(ctx, 2, T);
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}

// 3 目标
{
  const ctx = newSlide();
  head(ctx, '建设目标', '业务闭环优先，智能能力以统一接口预留');
  const gapX = inch(0.34);
  const gapY = inch(0.3);
  const w = (CW - gapX) / 2;
  const h = inch(1.85);
  const items = [
    { no: '01', title: '能力可量化', body: '技能雷达同时对比当前等级、岗位要求与公司未来需求，缺口逐条给出依据。' },
    { no: '02', title: '培养成闭环', body: '考试、练习、实操任务与检测报告的结论回流到个人欠缺与学习建议。' },
    { no: '03', title: '管理有口径', body: '班组报告与公司看板提供人才缺口、培训成本与关键岗位备份的可核对数据。' },
    { no: '04', title: '智能可替换', body: '三个 Agent 接口稳定，现阶段走规则引擎，模型上线后前端与接口不变。' },
  ];
  items.forEach((item, index) => {
    const x = ML + (index % 2) * (w + gapX);
    const y = TOP + Math.floor(index / 2) * (h + gapY);
    ctx.shapes.push(box({
      id: ctx.id(), name: `Card${index}`, x, y, w, h, prst: 'roundRect', radius: 6000,
      fill: LIGHT, line: LINE, padX: 0, padY: 0,
    }));
    ctx.shapes.push(textBox({
      id: ctx.id(), name: `Body${index}`, x: x + inch(0.2), y: y + inch(0.18), w: w - inch(0.4), h: h - inch(0.36), anchor: 't',
      paras: [
        P(item.no, { size: 1100, bold: true, color: ACCENT, after: 60 }),
        P(item.title, { size: 1700, bold: true, color: NAVY, after: 100 }),
        P(item.body, { size: 1250, color: INK, after: 0, lineSpacingPct: 95000 }),
      ],
    }));
  });
  ctx.shapes.push(textBox({
    id: ctx.id(), name: 'Principle', x: ML, y: inch(6.15), w: CW, h: inch(0.6), anchor: 't',
    paras: [P('设计原则：先做系统后训 Agent，接口冻结，所有建议必须人工确认。', { size: 1350, bold: true, color: BLUE, after: 0 })],
  }));
  footer(ctx, 3, T);
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}

// 4 架构
{
  const ctx = newSlide();
  head(ctx, '系统总体架构', '五层结构，鉴权前置，能力层与 Web 框架解耦');
  const rightW = inch(3.1);
  const leftW = CW - rightW - inch(0.3);
  const bands = [
    { name: '展示层', desc: 'Vue 3 + Element Plus 按角色渲染导航与页面，只调用业务接口与 Agent 接口' },
    { name: '接入层', desc: 'RoleInterceptor 按路径前缀鉴权，越权统一返回 403 与 code=40301' },
    { name: '应用层', desc: '6 个 Controller 与 ExamCenter，承载个人、班组、公司、管理员四类业务' },
    { name: '能力层', desc: '规则引擎、报告框格与文档渲染、智能抽题、能力记忆库、标准依据库' },
    { name: '数据层', desc: 'MySQL 8+，52 张表承载主数据、业务数据、规则、记忆、Agent 结果与审计留痕' },
  ];
  const h = inch(0.82);
  const gap = inch(0.14);
  bands.forEach((band, index) => {
    const y = TOP + index * (h + gap);
    ctx.shapes.push(box({
      id: ctx.id(), name: band.name, x: ML + inch(0.075), y, w: leftW - inch(0.075), h, prst: 'roundRect', radius: 5000,
      fill: LIGHT, line: LINE, padX: inch(0.2), padY: inch(0.08), anchor: 'ctr',
      paras: [P(band.name + '　' + band.desc, { size: 1150, color: INK, after: 0, lineSpacingPct: 95000 })],
    }));
    ctx.shapes.push(box({ id: ctx.id(), name: band.name + 'Chip', x: ML, y, w: inch(0.075), h, fill: ACCENT }));
  });
  const totalH = bands.length * h + (bands.length - 1) * gap;
  ctx.shapes.push(box({
    id: ctx.id(), name: 'Infra', x: ML + leftW + inch(0.3), y: TOP, w: rightW, h: totalH, prst: 'roundRect', radius: 4000,
    fill: 'FFFFFF', line: LINE, padX: inch(0.2), padY: inch(0.2), anchor: 't',
    paras: [
      P('基础设施', { size: 1500, bold: true, color: NAVY, after: 130 }),
      P('Docker Compose 统一编排', { size: 1150, color: INK, after: 130 }),
      P('MySQL 8+ 一套库', { size: 1100, color: MUTED, after: 70 }),
      
      
      
      P('API 8080 · Web 5173', { size: 1100, color: MUTED, after: 0 }),
    ],
  }));
  footer(ctx, 4, T);
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}
// 5 选型
{
  const ctx = newSlide();
  head(ctx, '技术选型', '单体优先，依赖精简，文档导出与鉴权自研');
  ctx.shapes.push(tableFrame({
    id: ctx.id(), name: 'Stack', x: ML, y: TOP, w: CW, rowH: inch(0.44), bodyH: inch(0.5), size: 1150,
    colW: [16, 30, 54], header: ['领域', '选型与版本', '用途'],
    rows: [
      ['后端', 'Spring Boot 3.5.16 · Java 25', 'Web、Validation 与 JDBC 三个 Starter，鉴权由拦截器实现'],
      ['前端', 'Vue 3 · Vite · Element Plus', '单页应用，表格、表单与弹窗统一交互'],
      ['数据库', 'MySQL 8+', '结构化扩展字段使用 JSON，时间列使用 DATETIME(3)'],
      ['文档导出', 'PDFBox 3.0.3 · POI 5.4.1', 'PDF 与 Word 由同一套报告框格模型渲染'],
      ['接口文档', 'springdoc-openapi 2.6.0', '生成 OpenAPI 3.0，Swagger UI 位于 /swagger-ui.html'],
      ['部署', 'Docker Compose', '一条命令启动 MySQL、API 与 Web'],
    ],
  }));
  ctx.shapes.push(box({
    id: ctx.id(), name: 'Choice', x: ML, y: inch(5.05), w: CW, h: inch(1.7), prst: 'roundRect', radius: 5000,
    fill: LIGHT, line: LINE, padX: inch(0.24), padY: inch(0.18), anchor: 't',
    paras: [
      P('选型取舍', { size: 1400, bold: true, color: NAVY, after: 110 }),
      P('规则引擎直接使用数据库 JSON 规则表，不引入重型规则框架。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 100 }),
      P('未引入 Spring Security、JPA 与消息中间件，编译与启动开销小。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 100 }),
      P('后端约 3 900 行、前端约 3 400 行，规模适合单体部署。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 0 }),
    ],
  }));
  footer(ctx, 5, T);
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}

// 6 角色权限
{
  const ctx = newSlide();
  head(ctx, '角色与数据可见范围', '四类身份对应四套页面范围，权限在服务端强制判定');
  ctx.shapes.push(tableFrame({
    id: ctx.id(), name: 'Roles', x: ML, y: TOP, w: CW, rowH: inch(0.44), bodyH: inch(0.95), size: 1100,
    colW: [16, 16, 68], header: ['账号 / 角色', '页面范围', '可见内容'],
    rows: [
      ['zhangwei\n员工', 'PERSONAL', '本人技能雷达、自画像、能力、记忆、成长、差距建议、学习与考试、实操任务，全部只返回本人数据'],
      ['limin\n班组长', 'PERSONAL\n+ 班组', '员工全部板块，外加班组报告：每次实操活动一份检测报告，作为运行诊断 Agent 的输入之一'],
      ['wangzong\n公司上级', 'COMPANY', '公司总览与运行诊断 Agent，查看全体员工汇总数据，没有个人画像页面'],
      ['admin\n系统管理员', 'PLATFORM', '数据与运维、审计日志：员工档案、考试配置、试卷发放与审计，不参与业务决策'],
    ],
  }));
  ctx.shapes.push(textBox({
    id: ctx.id(), name: 'Note', x: ML, y: inch(5.8), w: CW, h: inch(0.8), anchor: 't',
    paras: [P('员工之间互不可见；班组长本身也是员工，只多一份班组视角；管理员既看不到个人画像，也看不到公司决策页面。', { size: 1200, color: MUTED, after: 0 })],
  }));
  footer(ctx, 6, T);
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}

// 7 员工六板块
{
  const ctx = newSlide();
  head(ctx, '员工个人系统：能力画像六大板块', '只返回本人数据，员工之间互不可见');
  const gapX = inch(0.26);
  const gapY = inch(0.26);
  const w = (CW - 2 * gapX) / 3;
  const h = inch(1.62);
  const items = [
    { title: '技能雷达', body: '当前等级对比岗位要求与公司未来需求，逐项给出状态与优先级' },
    { title: '个人自画像', body: '基本信息、职业目标、发展意愿、师傅与协作评价、岗位匹配度' },
    { title: '个人能力', body: '硬技能、软技能、安全、实操、考试与证书六类能力分项' },
    { title: '记忆展示', body: '学习、错误、实操、考试、安全、带教、复盘七类记忆按时间线留存' },
    { title: '成长轨迹', body: '技能等级、证书、考试、任务、培训与晋升准备度' },
    { title: '差距与建议', body: '汇总个人欠缺，由个人学习 Agent 给出课程、带教与模拟考计划' },
  ];
  items.forEach((item, index) => card(ctx, {
    x: ML + (index % 3) * (w + gapX),
    y: TOP + Math.floor(index / 3) * (h + gapY),
    w, h, title: item.title, body: item.body, size: 1500, bodySize: 1100,
  }));
  ctx.shapes.push(textBox({
    id: ctx.id(), name: 'Note', x: ML, y: inch(5.95), w: CW, h: inch(0.8), anchor: 't',
    paras: [P('配套模块：学习与考试（12 条站内资源与外网公开资料站）、练习题（按缺口权重抽题）、考试中心（管理员统一开考后方可进入）。', { size: 1200, color: MUTED, after: 0 })],
  }));
  footer(ctx, 7, T);
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}

// 8 考试闭环
{
  const ctx = newSlide();
  head(ctx, '考试与练习闭环', '管理员统一开考，员工进入考试，成绩与错题回流培训');
  stepRow(ctx, {
    x: ML, y: TOP, width: CW, h: inch(2.25),
    steps: [
      { no: 'STEP 1', title: '配置与开考', body: '设定题库范围、题量、限时与及格线，执行统一开考。' },
      { no: 'STEP 2', title: '门禁校验', body: '未开考时按钮不可点击且接口拒绝发卷，已交卷显示已提交。' },
      { no: 'STEP 3', title: '限时作答', body: '弹窗内倒计时答题，到点自动交卷，交卷即出分数与逐题解析。' },
      { no: 'STEP 4', title: '成绩回流', body: '成绩写入考试记忆，错题归因到知识点并调整后续抽题权重。' },
    ],
  });
  ctx.shapes.push(box({
    id: ctx.id(), name: 'RuleBox', x: ML, y: inch(4.05), w: (CW - inch(0.3)) / 2, h: inch(2.35), prst: 'roundRect', radius: 5000,
    fill: LIGHT, line: LINE, padX: inch(0.2), padY: inch(0.18), anchor: 't',
    paras: [
      P('组卷规则', { size: 1400, bold: true, color: NAVY, after: 110 }),
      P('题量取考试配置的 question_count，从该场考试对应的技能范围抽题。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 110 }),
      P('题库不足时按实际题量发卷，配置值与实际发卷数在响应中分别返回。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 110 }),
      P('管理员清单中直接暴露该范围可抽题量，避免静默发空卷。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 0 }),
    ],
  }));
  ctx.shapes.push(box({
    id: ctx.id(), name: 'PracticeBox', x: ML + (CW + inch(0.3)) / 2, y: inch(4.05), w: (CW - inch(0.3)) / 2, h: inch(2.35), prst: 'roundRect', radius: 5000,
    fill: LIGHT, line: LINE, padX: inch(0.2), padY: inch(0.18), anchor: 't',
    paras: [
      P('练习与抽题', { size: 1400, bold: true, color: NAVY, after: 110 }),
      P('题库按继电保护、倒闸操作、高压试验、安全规程、故障录波五个技能分池。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 110 }),
      P('Agent 按技能缺口权重与历史正确率分配题量，薄弱项分到更多题。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 110 }),
      P('答错写入记忆库，并调整下一次抽题的权重。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 0 }),
    ],
  }));
  footer(ctx, 8, T);
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}

// 9 报告闭环
{
  const ctx = newSlide();
  head(ctx, '实操检测报告闭环', '框格填报、文档生成与异常归因串成一条可确认的链路');
  stepRow(ctx, {
    x: ML, y: TOP, width: CW, h: inch(2.2), gap: inch(0.4),
    steps: [
      { no: 'STEP 1', title: '框格填报', body: '基础信息、检测数据与异常现象三段共九格。' },
      { no: 'STEP 2', title: '后端校验', body: '必填与文本格式双重校验，失败返回字段级错误。' },
      { no: 'STEP 3', title: '文档渲染', body: 'PDFBox 与 POI 按同一份框格模型输出 PDF 与 Word。' },
      { no: 'STEP 4', title: '异常归因', body: '气体阈值、现象关键词与严重度升级三组条件判定。' },
      { no: 'STEP 5', title: '人工确认', body: '结论带 need_human_confirm，班组长确认后闭环。' },
    ],
  });
  ctx.shapes.push(box({
    id: ctx.id(), name: 'Check', x: ML, y: inch(4.0), w: (CW - inch(0.3)) / 2, h: inch(2.4), prst: 'roundRect', radius: 5000,
    fill: LIGHT, line: LINE, padX: inch(0.2), padY: inch(0.18), anchor: 't',
    paras: [
      P('校验与格式要求', { size: 1400, bold: true, color: NAVY, after: 110 }),
      P('异常现象描述必填，15 至 300 字，且必须包含具体时间或数值。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 110 }),
      P('检测地点需写到站所与设备间隔，已采取措施不超过 200 字。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 110 }),
      P('校验失败返回 code=40001 与 field_errors，字段名与前端框格同名。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 0 }),
    ],
  }));
  ctx.shapes.push(box({
    id: ctx.id(), name: 'Analyze', x: ML + (CW + inch(0.3)) / 2, y: inch(4.0), w: (CW - inch(0.3)) / 2, h: inch(2.4), prst: 'roundRect', radius: 5000,
    fill: LIGHT, line: LINE, padX: inch(0.2), padY: inch(0.18), anchor: 't',
    paras: [
      P('归因与降级', { size: 1400, bold: true, color: NAVY, after: 110 }),
      P('默认使用内置规则引擎，可重复执行重新分析。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 110 }),
      P('配置大模型后自动切换到 AI，超时或不可用时回落规则兜底。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 110 }),
      P('报告填报人为班组长，普通员工只查看报告，不进入填报通道。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 0 }),
    ],
  }));
  footer(ctx, 9, T);
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}
// 10 公司板块
{
  const ctx = newSlide();
  head(ctx, '公司管理板块', '全公司视角的人才、成本与缺口口径，只有授权高管可见');
  const gapX = inch(0.28);
  const gapY = inch(0.26);
  const w = (CW - gapX) / 2;
  const h = inch(1.35);
  const items = [
    { title: '人才驾驶舱', body: '员工规模、培训完成率、安全风险与关键岗位缺口的统一入口' },
    { title: '全公司技能矩阵', body: '按部门、岗位与技能等级展示人才分布，标出谁强谁弱与备份情况' },
    { title: '培训看板', body: '完成率、成本结构、培训效果、投入产出测算与部门对比' },
    { title: '运行诊断 Agent', body: '结合学习、证书、技能与班组报告，判定人才缺失还是技能不足' },
  ];
  items.forEach((item, index) => card(ctx, {
    x: ML + (index % 2) * (w + gapX),
    y: TOP + Math.floor(index / 2) * (h + gapY),
    w, h, title: item.title, body: item.body, size: 1500, bodySize: 1150,
  }));
  const kpiTop = TOP + 2 * h + 2 * gapY + inch(0.12);
  const gapK = inch(0.24);
  const kw = (CW - 3 * gapK) / 4;
  [
    { value: '86', label: '在册员工' },
    { value: '72%', label: '培训完成率' },
    { value: '7', label: '关键技能缺口' },
    { value: '4 / 3', label: '继保与高压试验缺口' },
  ].forEach((item, index) => kpi(ctx, { x: ML + index * (kw + gapK), y: kpiTop, w: kw, h: inch(1.25), value: item.value, label: item.label }));
  ctx.shapes.push(textBox({
    id: ctx.id(), name: 'Note', x: ML, y: kpiTop + inch(1.4), w: CW, h: inch(0.6), anchor: 't',
    paras: [P('驾驶舱与诊断数据来自演示数据；正式运行后由真实考试、任务、成本与安全记录驱动。', { size: 1150, color: MUTED, after: 0 })],
  }));
  footer(ctx, 10, T);
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}

// 11 管理员
{
  const ctx = newSlide();
  head(ctx, '管理员后台', '主数据、考试配置与审计，不参与业务决策');
  const gapX = inch(0.28);
  const w = (CW - gapX) / 2;
  const h = inch(1.45);
  const items = [
    { title: '用户与权限', body: '用户、角色、组织、岗位与权限矩阵，附员工档案与平台数据规模' },
    { title: '技能与课程', body: '技能字典、岗位技能要求、课程与题库，岗位技能依据真实国家标准' },
    { title: '考试配置', body: '组卷规则、防作弊、评分规则与及格线，统一开考并发放试卷' },
    { title: '审计与审核', body: '登录、修改、审批、决策、执行、回滚六类留痕，支持条件检索' },
  ];
  items.forEach((item, index) => card(ctx, {
    x: ML + (index % 2) * (w + gapX),
    y: TOP + Math.floor(index / 2) * (h + gapX),
    w, h, title: item.title, body: item.body, size: 1500, bodySize: 1150,
  }));
  stepRow(ctx, {
    x: ML, y: inch(4.72), width: CW, h: inch(1.6), gap: inch(0.5),
    steps: [
      { no: 'STEP 1', title: '上传资料', body: '命名须符合技能编码、名称、等级与版本四段格式。' },
      { no: 'STEP 2', title: 'Agent 识别', body: '检索并整理题目或知识章节，只检索不入库。' },
      { no: 'STEP 3', title: '管理员核对', body: '查看原件信息、原件摘录与检索结果。' },
      { no: 'STEP 4', title: '确认入库', body: '通过后写入课程库或累加题库题量。' },
    ],
  });
  footer(ctx, 11, T);
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}

// 12 规则与 Agent
{
  const ctx = newSlide();
  head(ctx, '规则引擎与 Agent 演进', '接口与前端冻结，模型上线只替换 Service 实现');
  const halfW = (CW - inch(0.36)) / 2;
  const rightX = ML + halfW + inch(0.36);
  ctx.shapes.push(box({
    id: ctx.id(), name: 'Contract', x: ML, y: TOP, w: halfW, h: inch(2.5), prst: 'roundRect', radius: 4000,
    fill: LIGHT, line: LINE, padX: inch(0.2), padY: inch(0.18), anchor: 't',
    paras: [
      P('统一 Agent 契约', { size: 1400, bold: true, color: NAVY, after: 120 }),
      P('请求  { agent_type, target_id, context, options }', { size: 1000, color: BLUE, after: 90 }),
      P('响应  { suggestion_id, agent_type, target_id,', { size: 1000, color: BLUE, after: 0 }),
      P('        suggestions, confidence, source,', { size: 1000, color: BLUE, after: 0 }),
      P('        need_human_confirm, status }', { size: 1000, color: BLUE, after: 130 }),
      P('当前 source 固定为 rule；模型上线后改为 model，请求与响应字段不变。', { size: 1100, color: INK, after: 0 }),
    ],
  }));
  ctx.shapes.push(box({
    id: ctx.id(), name: 'Rules', x: ML, y: inch(4.23), w: halfW, h: inch(2.15), prst: 'roundRect', radius: 4000,
    fill: 'FFFFFF', line: LINE, padX: inch(0.2), padY: inch(0.18), anchor: 't',
    paras: [
      P('规则模型', { size: 1400, bold: true, color: NAVY, after: 110 }),
      P('规则以数据形式存放在数据库，新增判断通常只需插入规则记录。', { size: 1100, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 100 }),
      P('六个字段：rule_code、scene、condition_json、action_json、priority、enabled。', { size: 1100, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 100 }),
      P('设计上执行结果写入 rule_result 以便复盘；该表未建，命中过程只体现在归因结果的规则引用里。', { size: 1100, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 0 }),
    ],
  }));
  ctx.shapes.push(box({
    id: ctx.id(), name: 'Agents', x: rightX, y: TOP, w: halfW, h: inch(2.5), prst: 'roundRect', radius: 4000,
    fill: LIGHT, line: LINE, padX: inch(0.2), padY: inch(0.18), anchor: 't',
    paras: [
      P('三个 Agent 接口（当前为桩实现，输出固定建议）', { size: 1400, bold: true, color: NAVY, after: 110 }),
      P('/agent/personal/recommend', { size: 1050, color: BLUE, after: 40 }),
      P('员工个人学习：课程、带教与模拟考建议。', { size: 1050, color: INK, after: 110 }),
      P('/agent/management/decision', { size: 1050, color: BLUE, after: 40 }),
      P('组织人才：招聘、转岗、外包与培养建议。', { size: 1050, color: INK, after: 110 }),
      P('/agent/report/analyze', { size: 1050, color: BLUE, after: 40 }),
      P('报告分析：技能原因或人为原因与 SOP 更新建议。', { size: 1050, color: INK, after: 0 }),
    ],
  }));
  ctx.shapes.push(box({
    id: ctx.id(), name: 'Confirm', x: rightX, y: inch(4.23), w: halfW, h: inch(2.15), prst: 'roundRect', radius: 4000,
    fill: 'FFFFFF', line: LINE, padX: inch(0.2), padY: inch(0.18), anchor: 't',
    paras: [
      P('人工确认与留痕', { size: 1400, bold: true, color: NAVY, after: 110 }),
      P('Agent 只给建议，不能直接执行，建议默认处于待确认状态。', { size: 1100, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 100 }),
      P('建议写入 agent_suggestion；decision_log 表已建，采纳与驳回链路待补。', { size: 1100, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 100 }),
      P('记录建议编号、决策人、结论、原因与执行结果，形成责任链。', { size: 1100, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 0 }),
    ],
  }));
  footer(ctx, 12, T);
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}
// 13 推荐建议依据
{
  const ctx = newSlide();
  head(ctx, '推荐建议参考哪些数据、怎么给出', '四条链路共用一份数据底座，每条结论都挂证据、口径与置信度');
  const halfW = (CW - inch(0.36)) / 2;
  const rightX = ML + halfW + inch(0.36);
  const bl = (t, last) => P(t, { size: 1100, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: last ? 0 : 100 });
  ctx.shapes.push(box({
    id: ctx.id(), name: 'DataSource', x: ML, y: TOP, w: halfW, h: inch(2.5), prst: 'roundRect', radius: 4000,
    fill: LIGHT, line: LINE, padX: inch(0.2), padY: inch(0.18), anchor: 't',
    paras: [
      P('读哪些数据', { size: 1400, bold: true, color: NAVY, after: 110 }),
      bl('技能主数据与员工技能等级'),
      bl('岗位要求等级与公司未来需求'),
      bl('考试分数、错题知识点与练习正确率'),
      bl('实操任务的计划工时与实际工时'),
      bl('检测报告的气体数值、阈值与现象描述'),
      bl('带教评语、证书有效期、成本与外委台账'),
      bl('能力记忆库事件与规则表', true),
    ],
  }));
  ctx.shapes.push(box({
    id: ctx.id(), name: 'Pipeline', x: rightX, y: TOP, w: halfW, h: inch(2.5), prst: 'roundRect', radius: 4000,
    fill: LIGHT, line: LINE, padX: inch(0.2), padY: inch(0.18), anchor: 't',
    paras: [
      P('怎么给出来', { size: 1400, bold: true, color: NAVY, after: 110 }),
      bl('采集：读取上述记录，不引入外部推测数据'),
      bl('定性：区分能力空白与在岗技能不足'),
      bl('排序：按缺口、未来需求与证据条数排 P1 到 P3'),
      bl('成稿：课程、带教、模拟考、补考四步计划'),
      bl('回写：结论入记忆库，可追溯到规则版本'),
      bl('确认：建议默认待确认，不自动执行', true),
    ],
  }));
  ctx.shapes.push(box({
    id: ctx.id(), name: 'Formula', x: ML, y: inch(4.23), w: halfW, h: inch(2.15), prst: 'roundRect', radius: 4000,
    fill: 'FFFFFF', line: LINE, padX: inch(0.2), padY: inch(0.18), anchor: 't',
    paras: [
      P('计算口径', { size: 1400, bold: true, color: NAVY, after: 110 }),
      bl('个人缺口 = 岗位要求等级 - 当前等级'),
      bl('题量 = 总题量 × 权重 × max(0.2, 1.6 - 历史正确率) 归一化分配'),
      bl('报告置信度 = 0.72 + 异常 0.10 + 命中关键词数 × 0.04'),
      bl('公司缺口 = 需求人数 - 实际人数，附节省测算', true),
    ],
  }));
  ctx.shapes.push(box({
    id: ctx.id(), name: 'Trust', x: rightX, y: inch(4.23), w: halfW, h: inch(2.15), prst: 'roundRect', radius: 4000,
    fill: 'FFFFFF', line: LINE, padX: inch(0.2), padY: inch(0.18), anchor: 't',
    paras: [
      P('可信度控制', { size: 1400, bold: true, color: NAVY, after: 110 }),
      bl('置信度上限 0.95，不把统计结论说成确定事实'),
      bl('每条结论带 source 与 rule_refs，可展开核对依据'),
      bl('need_human_confirm 恒为 true，确认与驳回全部留痕'),
      bl('模型不可用时自动回落规则引擎并说明原因', true),
    ],
  }));
  footer(ctx, 13, T);
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}
// 14 数据与安全
{
  const ctx = newSlide();
  head(ctx, '数据模型与权限隔离', '52 张表承载主数据、业务数据、规则、记忆与留痕，权限在接入层强制判定');
  const halfW = (CW - inch(0.36)) / 2;
  const rightX = ML + halfW + inch(0.36);
  ctx.shapes.push(textBox({
    id: ctx.id(), name: 'ModelTitle', x: ML, y: TOP, w: halfW, h: inch(0.36), anchor: 't',
    paras: [P('数据表分组', { size: 1400, bold: true, color: NAVY, after: 0 })],
  }));
  ctx.shapes.push(tableFrame({
    id: ctx.id(), name: 'Tables', x: ML, y: inch(1.88), w: halfW, rowH: inch(0.36), bodyH: inch(0.52), size: 950,
    colW: [30, 70], header: ['分组', '数据表'],
    rows: [
      ['身份与主数据', 'app_user、role、org、position、skill、position_skill、employee_skill'],
      ['课程与考试', 'course、course_skill、learning_record、question、exam、exam_question、exam_record'],
      ['任务与报告', 'task、task_report'],
      ['规则与智能', 'rule、agent_suggestion、decision_log、diagnosis_result'],
      ['经营与安全', 'cost_record、safety_record、care_record'],
      ['平台支撑', 'notification、file、audit_log'],
    ],
  }));
  ctx.shapes.push(box({
    id: ctx.id(), name: 'Common', x: ML, y: inch(5.46), w: halfW, h: inch(1.0), prst: 'roundRect', radius: 5000,
    fill: LIGHT, line: LINE, padX: inch(0.18), padY: inch(0.14), anchor: 'ctr',
    paras: [P('公共字段：id、created_at、updated_at、created_by、updated_by、status、remark。', { size: 1050, color: INK, after: 0 })],
  }));
  ctx.shapes.push(textBox({
    id: ctx.id(), name: 'AuthTitle', x: rightX, y: TOP, w: halfW, h: inch(0.36), anchor: 't',
    paras: [P('路径前缀鉴权', { size: 1400, bold: true, color: NAVY, after: 0 })],
  }));
  ctx.shapes.push(tableFrame({
    id: ctx.id(), name: 'Auth', x: rightX, y: inch(1.88), w: halfW, rowH: inch(0.36), bodyH: inch(0.44), size: 1000,
    colW: [58, 42], header: ['路径前缀', '允许角色'],
    rows: [
      ['/personal/**、/exams/**', '员工 · 班组长'],
      ['/team/**', '班组长'],
      ['/tasks/**', '班组长（报告填报）'],
      ['/management/**、/exec/**', '公司上级'],
      ['/admin/**', '系统管理员'],
    ],
  }));
  ctx.shapes.push(box({
    id: ctx.id(), name: 'Guard', x: rightX, y: inch(4.6), w: halfW, h: inch(1.88), prst: 'roundRect', radius: 5000,
    fill: 'FFFFFF', line: LINE, padX: inch(0.2), padY: inch(0.16), anchor: 't',
    paras: [
      P('隔离与留痕', { size: 1400, bold: true, color: NAVY, after: 100 }),
      P('越权返回 403 与 code=40301，data 携带 role 与 scope。', { size: 1050, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 90 }),
      P('心理与关怀数据仅本人与授权专员可见，管理端只返回脱敏聚合。', { size: 1050, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 90 }),
      P('安全记录一票否决晋升、评优与关键岗位任命。', { size: 1050, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 0 }),
    ],
  }));
  footer(ctx, 14, T);
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}

// 15 部署
{
  const ctx = newSlide();
  head(ctx, '部署与运行', '一条命令启动全部服务，默认离线可用');
  ctx.shapes.push(tableFrame({
    id: ctx.id(), name: 'Compose', x: ML, y: TOP, w: CW, rowH: inch(0.42), bodyH: inch(0.44), size: 1100,
    colW: [18, 32, 16, 34], header: ['服务', '镜像 / 来源', '端口', '用途'],
    rows: [
      ['mysql', 'mysql:8.4', '3306', '业务库，首次启动按序执行 db/init 下的 DDL 与种子数据'],
      
      
      
      ['backend', 'backend/Dockerfile', '8080', 'Spring Boot API 与 Swagger UI'],
      ['frontend', 'frontend/Dockerfile', '5173 → 80', 'Nginx 托管的静态站点'],
    ],
  }));
  const halfW = (CW - inch(0.3)) / 2;
  ctx.shapes.push(box({
    id: ctx.id(), name: 'Font', x: ML, y: inch(4.72), w: halfW, h: inch(2.12), prst: 'roundRect', radius: 5000,
    fill: LIGHT, line: LINE, padX: inch(0.2), padY: inch(0.18), anchor: 't',
    paras: [
      P('中文字体解析顺序', { size: 1400, bold: true, color: NAVY, after: 110 }),
      P('显式配置路径、jar 内 classpath:fonts、本机 Windows 字体、容器 CJK 字体依次探测。', { size: 1100, color: INK, after: 100 }),
      P('镜像已安装 fonts-wqy-zenhei 与 fonts-droid-fallback，可用环境变量强制指定字体文件。', { size: 1100, color: INK, after: 0 }),
    ],
  }));
  ctx.shapes.push(box({
    id: ctx.id(), name: 'Offline', x: ML + halfW + inch(0.3), y: inch(4.72), w: halfW, h: inch(2.12), prst: 'roundRect', radius: 5000,
    fill: LIGHT, line: LINE, padX: inch(0.2), padY: inch(0.18), anchor: 't',
    paras: [
      P('离线降级', { size: 1400, bold: true, color: NAVY, after: 110 }),
      P('AI_ENABLED 默认为 false，归因走内置规则引擎，系统不依赖外部服务。', { size: 1100, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 100 }),
      P('题库、课程与标准依据库随构建产物打包，内网与断网环境均可完整演示。', { size: 1100, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 0 }),
    ],
  }));
  footer(ctx, 15, T);
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}

// 16 实施计划
{
  const ctx = newSlide();
  head(ctx, '实施计划与进度', '策划书约定的八个阶段已全部落地，端到端演示数据可跑通');
  const gapX = inch(0.24);
  const gapY = inch(0.26);
  const w = (CW - 3 * gapX) / 4;
  const h = inch(1.55);
  const steps = [
    ['主数据与权限', '用户、角色、组织、岗位与技能字典，路径前缀鉴权'],
    ['考试系统', '题库分池、组卷、统一开考门禁、判分与逐题解析'],
    ['个人系统', '能力画像六大板块、记忆库、成长轨迹与建议'],
    ['老总管理板块', '人才驾驶舱、技能矩阵、培训看板与运行诊断'],
    ['实操任务与班组', '框格填报、文档生成、归因分析与班组报告'],
    ['规则引擎', '六条初始规则、执行结果留痕与报告归因规则集'],
    ['Agent 接口桩', '三个稳定接口，统一契约，source 固定为 rule'],
    ['端到端演示数据', '四类角色完整流程数据，覆盖考试与报告链路'],
  ];
  steps.forEach((item, index) => {
    const x = ML + (index % 4) * (w + gapX);
    const y = TOP + Math.floor(index / 4) * (h + gapY);
    ctx.shapes.push(box({
      id: ctx.id(), name: `Phase${index + 1}`, x, y, w, h, prst: 'roundRect', radius: 6000,
      fill: LIGHT, line: LINE, padX: inch(0.14), padY: inch(0.14), anchor: 't',
      paras: [
        P(String(index + 1).padStart(2, '0'), { size: 1000, bold: true, color: ACCENT, after: 50 }),
        P(item[0], { size: 1300, bold: true, color: NAVY, after: 80 }),
        P(item[1], { size: 1000, color: INK, after: 0, lineSpacingPct: 92000 }),
      ],
    }));
  });
  ctx.shapes.push(box({
    id: ctx.id(), name: 'Next', x: ML, y: inch(4.98), w: CW, h: inch(1.76), prst: 'roundRect', radius: 5000,
    fill: 'FFFFFF', line: LINE, padX: inch(0.24), padY: inch(0.18), anchor: 't',
    paras: [
      P('下一阶段重点', { size: 1400, bold: true, color: NAVY, after: 110 }),
      P('数据已全部落库 MySQL，重启不丢；下一步补齐真实身份源与备份恢复预案。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 100 }),
      P('第二优先：接入真实身份源与令牌机制，替换演示 JWT 与默认口令。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 100 }),
      P('第三优先：按 Agent 类型灰度切换模型版实现，规则引擎保留为兜底。', { size: 1150, color: INK, bullet: true, marL: inch(0.24), indent: -inch(0.24), after: 0 }),
    ],
  }));
  footer(ctx, 16, T);
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}

// 17 验收
{
  const ctx = newSlide();
  head(ctx, '验收标准对照', '八项标准中四项完全满足，四项部分实现：接口内容、职责调整、决策留痕、安全数据');
  ctx.shapes.push(tableFrame({
    id: ctx.id(), name: 'Accept', x: ML, y: TOP, w: CW, rowH: inch(0.4), bodyH: inch(0.5), size: 1050,
    colW: [6, 42, 52], header: ['#', '策划书验收标准', '实现情况'],
    rows: [
      ['1', 'Swagger 打开能看到全部接口', '已实现，覆盖 75 个接口'],
      ['2', 'Agent 接口返回规则结果且 source=rule', '部分实现：结构完整，内容为固定建议'],
      ['3', '前端只能调业务接口与 /agent/*', '已实现，规则接口不对外暴露'],
      ['4', '员工能查欠缺、拿建议、考试、提交报告', '按职责调整，报告填报由班组长完成'],
      ['5', '班组长能发任务、评分、触发报告分析', '已实现，班组报告与归因链路完整'],
      ['6', '老总能看缺口、取建议、写入 decision_log', '部分实现：缺口与建议可读，决策留痕未打通'],
      ['7', '替换 Agent 模型只改 Service 实现', '已满足，路径与出入参冻结'],
      ['8', '心理数据隔离、安全一票否决、决策留痕', '心理隔离已实现；安全与关怀数据无录入接口'],
    ],
  }));
  footer(ctx, 17, T);
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}

// 18 结束
{
  const ctx = newSlide(NAVY);
  ctx.shapes.push(box({ id: ctx.id(), name: 'Bar', x: ML, y: inch(2.55), w: inch(1.5), h: inch(0.06), fill: ACCENT }));
  ctx.shapes.push(textBox({
    id: ctx.id(), name: 'EndTitle', x: ML, y: inch(2.8), w: inch(10.6), h: inch(0.9), anchor: 't',
    paras: [P('先做系统，后训 Agent', { size: 3200, bold: true, color: 'FFFFFF', after: 0 })],
  }));
  ctx.shapes.push(textBox({
    id: ctx.id(), name: 'EndBody', x: ML, y: inch(3.95), w: inch(10.6), h: inch(1.6), anchor: 't',
    paras: [
      P('业务闭环与接口契约已经固化，智能能力可以按节奏替换。', { size: 1400, color: 'C6DAF2', after: 140 }),
      P('下一步补齐真实身份源与备份恢复预案，随后灰度上线模型版 Agent。', { size: 1400, color: 'C6DAF2', after: 0 }),
    ],
  }));
  ctx.shapes.push(box({ id: ctx.id(), name: 'FootBar', x: 0, y: inch(7.36), w: SLIDE_W, h: inch(0.14), fill: ACCENT }));
  slides.push({ shapes: ctx.shapes, background: ctx.background });
}

const buffer = buildPptx({ title: '三层人才技能培训与考试管理系统技术方案', author: '项目技术组', slides });
const target = new URL('../三层人才技能培训与考试管理系统-项目介绍.pptx', import.meta.url);
writeFileSync(target, buffer);
console.log('slides', slides.length, 'bytes', buffer.length);
