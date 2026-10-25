<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { api, getData } from '../api';
import '../roles.css';

const props = defineProps({ mode: { type: String, default: 'overview' } });
const overview = ref(null);
const matrix = ref(null);
const training = ref(null);
const diagnosis = ref(null);
const report = ref(null);
const running = ref(false);
const runError = ref('');

// 点击运行诊断：实时生成公司运行诊断报告（后端返回诊断编号与生成时间）
const runDiagnosis = async () => {
  running.value = true;
  runError.value = '';
  try {
    const response = await api.post('/exec/agent-diagnose');
    report.value = response.data.data;
  } catch (error) {
    runError.value = '诊断失败：请确认后端服务已启动（8080）。';
  } finally {
    running.value = false;
  }
};

const money = (value) => `¥${Number(value || 0).toLocaleString('zh-CN')}`;
const priorityClass = (priority) => ({ HIGH: 'chip bad', MEDIUM: 'chip warn', LOW: 'chip ok' }[priority] || 'chip');
// 达标率/完成率配色：>=85 正常，70-84 关注，<70 需重点跟进
const barClass = (rate) => (rate >= 85 ? 'bar' : rate >= 70 ? 'bar warn' : 'bar bad');
const rateClass = (rate) => (rate >= 85 ? 'good' : rate >= 70 ? 'warn' : 'warn');

// —— 驾驶舱动效进度：数据到达后统一跑一次 0→1 的缓动（驱动仪表盘扫掠 / 饼图展开 / 数字滚动），数据刷新时会重放 ——
const dashProgress = ref(0);
const reduceMotion = typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
let dashRaf = 0;
const runDash = () => {
  cancelAnimationFrame(dashRaf);
  if (reduceMotion) { dashProgress.value = 1; return; }
  const start = performance.now();
  const duration = 900;
  const step = (now) => {
    const t = Math.min(1, (now - start) / duration);
    dashProgress.value = 1 - Math.pow(1 - t, 3); // easeOutCubic
    if (t < 1) dashRaf = requestAnimationFrame(step);
  };
  dashRaf = requestAnimationFrame(step);
};
// 数据到达后重放动效，并重新挂一次折线画布的尺寸监听（v-if 分支渲染完成后才有 svg 元素）
watch(overview, (value) => { if (value) { runDash(); nextTick(() => observeCost()); } });

// 驾驶舱悬浮提示：整块驾驶舱共用一枚固定定位提示框，跟随鼠标、贴边自动翻转
const dashTip = ref({ show: false, x: 0, y: 0, title: '', rows: [] });
const showDashTip = (event, title, rows) => {
  dashTip.value = { show: true, x: event.clientX, y: event.clientY, title, rows };
};
const moveDashTip = (event) => {
  if (dashTip.value.show) { dashTip.value.x = event.clientX; dashTip.value.y = event.clientY; }
};
const hideDashTip = () => { dashTip.value.show = false; };
const dashTipStyle = computed(() => {
  const tip = dashTip.value;
  const flipX = tip.x > window.innerWidth - 320;
  const flipY = tip.y > window.innerHeight - 200;
  const dx = flipX ? 'calc(-100% - 14px)' : '14px';
  const dy = flipY ? 'calc(-100% - 14px)' : '14px';
  return { left: `${tip.x}px`, top: `${tip.y}px`, transform: `translate(${dx}, ${dy})` };
});

// 漏斗图：在岗全员 → 证书有效 → 技能达标 → L3 带教主力（全部由总览真实指标换算，逐层收窄）
const funnelStages = computed(() => {
  const data = overview.value;
  if (!data) return [];
  const headcount = Number(data.headcount) || 0;
  return [
    { label: '在岗全员', value: headcount, note: `${data.teams} 个班组 · 一线队伍总规模` },
    { label: '证书有效', value: Math.round(headcount * (Number(data.cert_valid_rate) || 0) / 100), note: `证书有效率 ${data.cert_valid_rate}%` },
    { label: '技能达标', value: Math.round(headcount * (Number(data.skill_pass_rate) || 0) / 100), note: `达标率 ${data.skill_pass_rate}% · 目标 85%` },
    { label: 'L3 带教主力', value: Number(data.level_l3) || Math.round(headcount * 0.16), note: '高级技能人才 · 带教与关键岗备份主力' }
  ];
});
// 漏斗多边形：宽度按人数占比收窄，末层再做收口
const FUNNEL = { width: 320, cx: 160, bandH: 47, gap: 7, maxHalf: 138 };
const funnelBands = computed(() => {
  const stages = funnelStages.value;
  const top = Number(stages[0] && stages[0].value) || 1;
  const halves = stages.map((stage) => Math.max(14, FUNNEL.maxHalf * (Number(stage.value) || 0) / top));
  return stages.map((stage, index) => {
    const yTop = index * (FUNNEL.bandH + FUNNEL.gap);
    const yBot = yTop + FUNNEL.bandH;
    const halfTop = halves[index];
    const halfBot = index < stages.length - 1 ? halves[index + 1] : halfTop * 0.72;
    return { ...stage, yTop, index, points: `${FUNNEL.cx - halfTop},${yTop} ${FUNNEL.cx + halfTop},${yTop} ${FUNNEL.cx + halfBot},${yBot} ${FUNNEL.cx - halfBot},${yBot}` };
  });
});
const funnelShare = (stage) => {
  const top = Number(funnelStages.value[0] && funnelStages.value[0].value) || 1;
  return (Math.round((Number(stage.value) || 0) / top * 1000) / 10).toFixed(1);
};

// 环形仪表盘：三块核心率值，270° 刻度盘 + HUD 刻线
const gauges = computed(() => {
  const data = overview.value;
  if (!data) return [];
  return [
    { key: 'skill', label: '技能达标率', value: Number(data.skill_pass_rate) || 0, target: 85, color: 'var(--role-accent)' },
    { key: 'cert', label: '证书有效率', value: Number(data.cert_valid_rate) || 0, target: 95, color: 'var(--gold)' },
    { key: 'train', label: '培训完成率', value: Number(data.training_completion) || 0, target: 80, color: 'var(--green)' }
  ];
});
const GAUGE_R = 48;
const GAUGE_C = 2 * Math.PI * GAUGE_R;
const GAUGE_ARC = GAUGE_C * 0.75;
const gaugeTicks = Array.from({ length: 9 }, (_, index) => {
  const angle = (135 + 270 * index / 8) * Math.PI / 180;
  return { x1: 60 + Math.cos(angle) * 40, y1: 60 + Math.sin(angle) * 40, x2: 60 + Math.cos(angle) * 45, y2: 60 + Math.sin(angle) * 45 };
});
const gaugeRows = (gauge) => [
  ['当前', `${gauge.value}%`],
  ['目标', `${gauge.target}%`],
  ['差距', `${Math.max(0, gauge.target - gauge.value)} 个百分点`]
];

// 用人成本结构（饼图）：四类支出占比，中心显示年度累计或悬停项
const costItems = computed(() => {
  const data = overview.value;
  if (!data || !data.cost) return [];
  return [
    { key: 'training', name: '培训投入', amount: data.cost.training, color: 'var(--gold)' },
    { key: 'overtime', name: '加班成本', amount: data.cost.overtime, color: 'var(--amber)' },
    { key: 'hiring', name: '招聘成本', amount: data.cost.hiring, color: 'var(--role-accent)' },
    { key: 'outsourcing', name: '外委支出', amount: data.cost.outsourcing, color: 'var(--green)' }
  ];
});
const PIE_R = 64;
const PIE_C = 2 * Math.PI * PIE_R;
const costSlices = computed(() => {
  const total = costItems.value.reduce((sum, item) => sum + (Number(item.amount) || 0), 0) || 1;
  let acc = 0;
  return costItems.value.map((item) => {
    const share = (Number(item.amount) || 0) / total;
    const slice = { ...item, share: Math.round(share * 1000) / 10, start: acc };
    acc += share;
    return slice;
  });
});
const costTotal = computed(() => (overview.value && overview.value.cost ? overview.value.cost.total : 0));
const pieFocus = ref(-1);

// 风险告警列表：由人才风险与组长报告信号汇出，按严重度标色
const alerts = computed(() => {
  const data = overview.value;
  if (!data) return [];
  const risk = data.talent_risk || {};
  const signal = data.report_signal || {};
  const list = [];
  if (risk.safety_teams) list.push({ level: 'bad', title: `安全风险班组 ${risk.safety_teams} 个`, detail: risk.safety_note });
  if (signal.missing_reports > 0) list.push({ level: 'bad', title: `本月缺报 ${signal.missing_reports} 份`, detail: signal.note });
  if (risk.retention_people) list.push({ level: 'warn', title: `离职风险 ${risk.retention_people} 人 / 关键岗 ${risk.retention_posts} 个`, detail: risk.retention_note });
  if (risk.cert_expiring) list.push({ level: 'warn', title: `证书到期 ${risk.cert_expiring} 本`, detail: risk.cert_note });
  if (Number(signal.abnormal_rate) >= 20) list.push({ level: 'warn', title: `报告超限占比 ${signal.abnormal_rate}%`, detail: '超限集中在定值准备与有限空间气体检测，已在运行诊断中跟踪' });
  return list;
});

// 告警面板控高：面板里只铺前三条，其余收进「查看全部」弹窗。
// 否则告警条目会把整行撑高，同排的饼图与折线图底下就会积一大片空白。
const ALERT_PREVIEW = 3;
const alertsPreview = computed(() => alerts.value.slice(0, ALERT_PREVIEW));
const alertsMore = computed(() => Math.max(0, alerts.value.length - ALERT_PREVIEW));
const alertModal = ref(false);
const openAlertModal = () => { hideDashTip(); alertModal.value = true; };
const closeAlertModal = () => { alertModal.value = false; };
// 弹窗打开时锁定 Esc 关闭；遮罩点击同样关闭
const onAlertKey = (event) => { if (event.key === 'Escape' && alertModal.value) closeAlertModal(); };
onMounted(() => window.addEventListener('keydown', onAlertKey));
onBeforeUnmount(() => window.removeEventListener('keydown', onAlertKey));

// 用人成本折线画布：坐标按 SVG 的**真实像素尺寸**算，viewBox 也设成实际宽高（1:1）。
// 之前用固定 viewBox 760×220 配 preserveAspectRatio="none" 填满窄列，x 被压、y 被拉，
// 数据点压成细竖条、线也显粗，整张图像被硬拽长。改成实际像素后就只缩放不形变。
const costSvg = ref(null);
const costBox = ref({ width: 320, height: 190 });
const costChart = computed(() => {
  const width = Math.max(120, Math.round(costBox.value.width));
  const height = Math.max(80, Math.round(costBox.value.height));
  return { left: 5, right: width - 5, top: 12, bottom: height - 6, width, height };
});
let costObserver = null;
const syncCostBox = () => {
  const el = costSvg.value;
  if (!el) return;
  const rect = el.getBoundingClientRect();
  const width = Math.round(rect.width);
  const height = Math.round(rect.height);
  if (width > 0 && height > 0 && (width !== costBox.value.width || height !== costBox.value.height)) {
    costBox.value = { width, height };
  }
};
const observeCost = () => {
  syncCostBox();
  if (typeof ResizeObserver === 'undefined' || !costSvg.value) return;
  if (costObserver) costObserver.disconnect();
  costObserver = new ResizeObserver(syncCostBox);
  costObserver.observe(costSvg.value);
};
onMounted(() => { nextTick(observeCost); });
onBeforeUnmount(() => { if (costObserver) costObserver.disconnect(); });
// 用人成本折线图：接口 trend 给的是月度发生额（元），统一换算成万元读数，否则坐标轴数字太长、看不出月度波动
const demoCostTrend = [
  { month: '1月', training: 62000, overtime: 14000, hiring: 12000, outsourcing: 18000, total: 106000, cumulative: 106000 },
  { month: '2月', training: 28000, overtime: 9000, hiring: 8000, outsourcing: 16000, total: 61000, cumulative: 167000 },
  { month: '3月', training: 58000, overtime: 16000, hiring: 22000, outsourcing: 30000, total: 126000, cumulative: 293000 },
  { month: '4月', training: 40000, overtime: 15000, hiring: 28000, outsourcing: 26000, total: 109000, cumulative: 402000 },
  { month: '5月', training: 35000, overtime: 18000, hiring: 18000, outsourcing: 24000, total: 95000, cumulative: 497000 },
  { month: '6月', training: 55000, overtime: 26000, hiring: 16000, outsourcing: 28000, total: 125000, cumulative: 622000 },
  { month: '7月', training: 30000, overtime: 34000, hiring: 14000, outsourcing: 32000, total: 110000, cumulative: 732000 },
  { month: '8月', training: 38000, overtime: 32000, hiring: 20000, outsourcing: 34000, total: 124000, cumulative: 856000 },
  { month: '9月', training: 74000, overtime: 22000, hiring: 22000, outsourcing: 32000, total: 150000, cumulative: 1006000 }
];
// 接口未返回 trend 时用演示兜底数据：四类支出逐月合计与上方卡片的年度累计口径一致（9 个月合计 1,006,000）
const costTrend = computed(() => {
  const trend = overview.value && overview.value.cost ? overview.value.cost.trend : null;
  return Array.isArray(trend) && trend.length ? trend : demoCostTrend;
});
const toWan = (value) => (Number(value) || 0) / 10000;
const wanText = (value) => toWan(value).toFixed(1);
const costTop = computed(() => {
  const peak = Math.max(...costTrend.value.map((item) => toWan(item.total)), 0);
  return [4, 6, 8, 10, 12, 14, 16, 20, 24, 30, 40, 50, 60, 80, 100].find((tick) => tick >= peak) || Math.ceil(peak / 10) * 10;
});
// 刻度线（上限 / 半值 / 0）：左侧刻度文字与图内刻度线共用同一套 y 坐标，保证文字压线对齐
// 刻度线按 4 等分铺满（0 / 1/4 / 1/2 / 3/4 / 上限）：格线密一些，纵向不会显得空荡
const costGrid = computed(() => {
  const max = costTop.value;
  const chart = costChart.value;
  return [0, 1, 2, 3, 4].map((index) => {
    const y = chart.top + (index * (chart.bottom - chart.top)) / 4;
    return { y, top: `${(y / chart.height) * 100}%`, label: String(Math.round((max * (4 - index)) / 4)) };
  });
});
const costAxisX = (index) => {
  const chart = costChart.value;
  const span = chart.right - chart.left;
  return chart.left + (costTrend.value.length > 1 ? (index / (costTrend.value.length - 1)) * span : span / 2);
};
const costPointY = (value) => {
  const chart = costChart.value;
  return chart.bottom - (toWan(value) / (costTop.value || 1)) * (chart.bottom - chart.top);
};
const costPoints = computed(() => costTrend.value.map((item, index) => ({ x: costAxisX(index), y: costPointY(item.total), item })));
const costLinePoints = computed(() => costPoints.value.map((point) => `${point.x},${point.y}`).join(' '));
const costAreaPoints = computed(() => {
  const points = costPoints.value;
  return `${points[0].x},${costChart.bottom} ${costLinePoints.value} ${points[points.length - 1].x},${costChart.bottom}`;
});
// 悬停命中区按相邻中点切分 x 轴：鼠标落在任意月份列上都能读出当月结构与累计
const costHit = (index) => {
  const points = costPoints.value;
  const chart = costChart.value;
  const left = index === 0 ? chart.left : (points[index - 1].x + points[index].x) / 2;
  const right = index === points.length - 1 ? chart.right : (points[index].x + points[index + 1].x) / 2;
  return { x: left, width: Math.max(8, right - left) };
};
const activeCostMonth = ref(-1);
// 没有悬停时默认聚焦成本最高的月份，保证不悬停也能看到结构数字
const peakCostMonth = computed(() => costPoints.value.reduce((best, point, index) => (point.item.total > costTrend.value[best].total ? index : best), 0));
const focusCostIndex = computed(() => (activeCostMonth.value >= 0 ? activeCostMonth.value : peakCostMonth.value));
const costLabelLeft = (index) => `${(costAxisX(index) / costChart.value.width) * 100}%`;
// 折线悬浮明细：当月发生额结构 + 年内累计（万元读数）
const costTipRows = (item) => [
  ['当月合计', `${wanText(item.total)} 万元`],
  ['培训 / 加班', `${wanText(item.training)} / ${wanText(item.overtime)} 万元`],
  ['招聘 / 外委', `${wanText(item.hiring)} / ${wanText(item.outsourcing)} 万元`],
  ['年内累计', `${wanText(item.cumulative)} 万元`]
];

const load = async () => {
  if (props.mode === 'overview') {
    if (!overview.value) overview.value = await getData('/exec/company-overview', null);
  } else if (props.mode === 'matrix') {
    if (!matrix.value) matrix.value = await getData('/exec/skill-matrix', null);
  } else if (props.mode === 'training') {
    if (!training.value) training.value = await getData('/exec/training-board', null);
  } else if (!diagnosis.value) {
    diagnosis.value = await getData('/exec/diagnosis', null);
    const latest = await getData('/exec/agent-diagnose/latest', null);
    if (latest && latest.has_diagnosis) report.value = latest;
  }
};
watch(() => props.mode, load);
onMounted(load);
</script>

<template>
  <section class="role-page">
    <!-- 人才驾驶舱：全公司人才总览 -->
    <template v-if="props.mode === 'overview'">
      <p v-if="!overview" class="empty-tip">数据加载中，或后端服务未启动…</p>
      <template v-else>
        <div class="panel role-banner">
          <p><b>{{ overview.company }}</b>：全公司在岗 {{ overview.headcount }} 人、{{ overview.teams }} 个班组，数据截至 {{ overview.as_of }}。</p>
          <span class="chip info">人才驾驶舱 · 全公司视图</span>
        </div>

        <div class="metrics">
          <div class="metric panel"><small>在岗人数 / 班组</small><div class="metric-value"><b>{{ overview.headcount }}</b><em>人</em></div><span class="good">{{ overview.teams }} 个班组</span></div>
          <div class="metric panel"><small>技能达标率</small><div class="metric-value"><b class="warn">{{ overview.skill_pass_rate }}</b><em>%</em></div><span class="warn">低于目标 85%</span></div>
          <div class="metric panel"><small>证书有效率</small><div class="metric-value"><b>{{ overview.cert_valid_rate }}</b><em>%</em></div><span class="good">复审提醒已推送</span></div>
          <div class="metric panel"><small>培训完成率</small><div class="metric-value"><b>{{ overview.training_completion }}</b><em>%</em></div><span class="warn">9 月目标 80%</span></div>
          <div class="metric panel"><small>安全风险班组</small><div class="metric-value"><b class="warn">{{ overview.safety_risk_teams }}</b><em>个</em></div><span class="warn">需重点跟踪</span></div>
          <div class="metric panel"><small>离职风险人数</small><div class="metric-value"><b class="warn">{{ overview.retention_risk_people }}</b><em>人</em></div><span class="warn">关键岗单点依赖 {{ overview.retention_risk_posts }} 个</span></div>
        </div>

        <!-- 驾驶舱六宫格：漏斗 / 仪表盘 / 进度条 / 饼图 / 折线 / 告警，全部沿用现有配色与字体 -->
        <div class="dash-grid" :class="{ 'no-anim': reduceMotion }">
          <!-- 人才梯队漏斗 -->
          <div class="panel dash-panel">
            <div class="panel-title"><h2>人才梯队漏斗</h2><span class="metric-note">全员 → 达标 → L3</span></div>
            <svg class="funnel-svg" viewBox="0 0 320 209" role="img" aria-label="人才梯队漏斗图：在岗全员、证书有效、技能达标、L3 带教主力">
              <polygon v-for="band in funnelBands" :key="'fb' + band.index" :class="'funnel-band funnel-band-' + band.index"
                :points="band.points" :style="{ animationDelay: band.index * 0.09 + 's' }"
                @mouseenter="showDashTip($event, band.label, [['人数', band.value + ' 人'], ['占全员', funnelShare(band) + '%'], ['说明', band.note]])"
                @mousemove="moveDashTip" @mouseleave="hideDashTip" />
              <text v-for="band in funnelBands" :key="'ft' + band.index" class="funnel-num" :x="FUNNEL.cx" :y="band.yTop + 30">{{ band.value }}</text>
            </svg>
            <ul class="funnel-legend">
              <li v-for="band in funnelBands" :key="'fl' + band.index">
                <i :class="'legend-dot ld-' + band.index"></i>
                <span>{{ band.label }}</span>
                <b>{{ band.value }} 人</b>
                <small>{{ funnelShare(band) }}%</small>
              </li>
            </ul>
          </div>

          <!-- 核心指标仪表盘 -->
          <div class="panel dash-panel">
            <div class="panel-title"><h2>核心指标仪表盘</h2><span class="metric-note">率值 · 270° 刻度盘</span></div>
            <div class="dash-gauges">
              <div v-for="(gauge, gi) in gauges" :key="gauge.key" class="dash-gauge"
                @mouseenter="showDashTip($event, gauge.label, gaugeRows(gauge))" @mousemove="moveDashTip" @mouseleave="hideDashTip">
                <svg viewBox="0 0 120 120" role="img" :aria-label="gauge.label + ' ' + gauge.value + '%'">
                  <line v-for="(tick, ti) in gaugeTicks" :key="gi + '-' + ti" class="gauge-tick" :x1="tick.x1" :y1="tick.y1" :x2="tick.x2" :y2="tick.y2" />
                  <circle class="gauge-track" cx="60" cy="60" :r="GAUGE_R" :stroke-dasharray="`${GAUGE_ARC} ${GAUGE_C}`" transform="rotate(135 60 60)" />
                  <circle class="gauge-arc" cx="60" cy="60" :r="GAUGE_R" :stroke="gauge.color"
                    :stroke-dasharray="`${GAUGE_ARC * (gauge.value / 100) * dashProgress} ${GAUGE_C}`" transform="rotate(135 60 60)" />
                </svg>
                <div class="gauge-center"><b>{{ Math.round(gauge.value * dashProgress) }}</b><i>%</i></div>
                <small class="gauge-label">{{ gauge.label }}</small>
              </div>
            </div>
            <p class="dash-footnote">悬停查看各指标目标值与差距；数据刷新后指针与数字自动重放。</p>
          </div>

          <!-- 班组技能达标率：横向进度条 -->
          <div class="panel dash-panel">
            <div class="panel-title"><h2>班组技能达标率</h2><span class="metric-note">悬停看人数与风险</span></div>
            <ul class="dash-bars">
              <li v-for="(team, index) in overview.by_team" :key="team.team"
                @mouseenter="showDashTip($event, team.team, [['在岗', team.members + ' 人'], ['技能达标', team.skill_pass + '%'], ['本月报告', team.reports + ' 份'], ['风险提示', team.risk]])"
                @mousemove="moveDashTip" @mouseleave="hideDashTip">
                <div class="dash-bar-head"><span>{{ team.team }}</span><b>{{ team.skill_pass }}%</b></div>
                <div :class="barClass(team.skill_pass)"><i :style="{ width: team.skill_pass + '%', animationDelay: index * 0.08 + 's' }"></i></div>
              </li>
            </ul>
          </div>

          <!-- 用人成本结构：环形饼图 -->
          <div class="panel dash-panel">
            <div class="panel-title"><h2>用人成本结构</h2><span class="metric-note">2026 年度 · 四类支出</span></div>
            <div class="dash-pie-body">
              <div class="dash-pie">
                <svg viewBox="0 0 200 200" role="img" aria-label="用人成本结构环形图">
                  <circle v-for="(slice, index) in costSlices" :key="slice.key" class="pie-seg" :class="{ focus: pieFocus === index }"
                    :stroke="slice.color" cx="100" cy="100" :r="PIE_R" fill="none" stroke-width="26"
                    :stroke-dasharray="`${PIE_C * slice.share / 100 * dashProgress} ${PIE_C}`" :stroke-dashoffset="-PIE_C * slice.start"
                    transform="rotate(-90 100 100)"
                    @mouseenter="pieFocus = index; showDashTip($event, slice.name, [['金额', money(slice.amount)], ['占比', slice.share + '%']])"
                    @mousemove="moveDashTip" @mouseleave="pieFocus = -1; hideDashTip()" />
                </svg>
                <div class="pie-center">
                  <template v-if="pieFocus >= 0">
                    <small>{{ costSlices[pieFocus].name }}</small>
                    <b>{{ costSlices[pieFocus].share }}%</b>
                    <span>{{ money(costSlices[pieFocus].amount) }}</span>
                  </template>
                  <template v-else>
                    <small>年度累计</small>
                    <b>{{ wanText(costTotal) }}</b>
                    <span>万元</span>
                  </template>
                </div>
              </div>
              <ul class="pie-legend">
                <li v-for="(slice, index) in costSlices" :key="'pl' + slice.key" :class="{ focus: pieFocus === index }"
                  @mouseenter="pieFocus = index; showDashTip($event, slice.name, [['金额', money(slice.amount)], ['占比', slice.share + '%']])"
                  @mousemove="moveDashTip" @mouseleave="pieFocus = -1; hideDashTip()">
                  <i :style="{ background: slice.color }"></i>
                  <span>{{ slice.name }}</span>
                  <b>{{ money(slice.amount) }}</b>
                  <small>{{ slice.share }}%</small>
                </li>
              </ul>
            </div>
          </div>

          <!-- 用人成本月度走势：折线图 -->
          <div class="panel dash-panel">
            <div class="panel-title"><h2>用人成本月度走势</h2><span class="metric-note">万元 · 悬停看当月结构</span></div>
            <div class="line-chart cost-chart dash-cost">
              <div class="chart-y">
                <span v-for="line in costGrid" :key="line.label" :style="{ top: line.top }">{{ line.label }}</span>
              </div>
              <svg ref="costSvg" :viewBox="`0 0 ${costChart.width} ${costChart.height}`" role="img" aria-label="用人成本月度折线图（万元）">
                <line v-for="line in costGrid" :key="'g' + line.y" :x1="costChart.left" :x2="costChart.right" :y1="line.y" :y2="line.y" />
                <polygon class="cost-area dash-area" :points="costAreaPoints" />
                <polyline class="cost-line dash-line-poly" pathLength="1" :points="costLinePoints" />
                <line v-if="activeCostMonth >= 0" class="cost-cross" :x1="costPoints[activeCostMonth].x" :x2="costPoints[activeCostMonth].x" :y1="costChart.top" :y2="costChart.bottom" />
                <circle class="cost-dot" v-for="(point, index) in costPoints" :key="'d' + index" :class="{ focus: focusCostIndex === index }" :cx="point.x" :cy="point.y" :r="focusCostIndex === index ? 6 : 4.5" />
                <rect class="cost-hit" v-for="(point, index) in costPoints" :key="'h' + index" :x="costHit(index).x" y="0" :width="costHit(index).width" :height="costChart.height"
                  @mouseenter="activeCostMonth = index; showDashTip($event, point.item.month + ' · 用人成本', costTipRows(point.item))"
                  @mousemove="moveDashTip" @mouseleave="activeCostMonth = -1; hideDashTip()" />
              </svg>
              <div class="chart-x">
                <span v-for="(item, index) in costTrend" :key="item.month" :class="{ active: focusCostIndex === index }" :style="{ left: costLabelLeft(index) }">{{ item.month }}</span>
              </div>
            </div>
          </div>

          <!-- 风险告警列表：面板内只铺前三条，其余进弹窗，避免撑高整行 -->
          <div class="panel dash-panel">
            <div class="panel-title"><h2>风险与告警</h2><span class="chip bad">{{ alerts.length }} 项待跟踪</span></div>
            <ul class="dash-alerts">
              <li v-for="(alert, index) in alertsPreview" :key="alert.title" :class="'alert-item lv-' + alert.level" :style="{ animationDelay: index * 0.08 + 's' }">
                <i class="alert-dot"></i>
                <div class="alert-body"><b>{{ alert.title }}</b><p>{{ alert.detail }}</p></div>
              </li>
            </ul>
            <button v-if="alertsMore > 0" class="dash-more" type="button" @click="openAlertModal">
              还有 {{ alertsMore }} 项 · 展开查看全部 {{ alerts.length }} 项<em>→</em>
            </button>
          </div>
        </div>

        <div class="grid-2">
          <div class="panel">
            <div class="panel-title"><h2>班组概览</h2><span class="metric-note">技能达标率 / 报告数 / 风险</span></div>
            <div class="table-wrap">
              <table class="role-table">
                <thead><tr><th>班组</th><th class="num">人数</th><th class="num">技能达标</th><th class="num">报告</th><th>风险提示</th></tr></thead>
                <tbody>
                  <tr v-for="team in overview.by_team" :key="team.team">
                    <td><b>{{ team.team }}</b></td>
                    <td class="num">{{ team.members }}</td>
                    <td class="num">{{ team.skill_pass }}%</td>
                    <td class="num">{{ team.reports }}</td>
                    <td>{{ team.risk }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div class="panel">
            <div class="panel-title"><h2>人才缺口</h2><span class="metric-note">岗位要求 vs 实际</span></div>
            <div class="table-wrap">
              <table class="role-table">
                <thead><tr><th>技能</th><th class="num">要求</th><th class="num">实际</th><th class="num">缺口</th><th>建议</th></tr></thead>
                <tbody>
                  <tr v-for="gap in overview.talent_gap" :key="gap.skill">
                    <td><b>{{ gap.skill }}</b></td>
                    <td class="num">{{ gap.required }}</td>
                    <td class="num">{{ gap.current }}</td>
                    <td class="num">{{ gap.gap }}</td>
                    <td>{{ gap.recommendation }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-title"><h2>组长报告信号</h2><span class="chip info">诊断输入之一</span></div>
          <div class="signal-stats">
            <div class="signal-stat">
              <small>本月报告</small>
              <div class="metric-value"><b>{{ overview.report_signal.reports_month }}</b><em>份</em></div>
            </div>
            <div class="signal-stat" :class="{ warn: overview.report_signal.abnormal_rate >= 20 }">
              <small>超限占比</small>
              <div class="metric-value"><b>{{ overview.report_signal.abnormal_rate }}</b><em>%</em></div>
            </div>
            <div class="signal-stat" :class="{ warn: overview.report_signal.missing_reports > 0 }">
              <small>缺报</small>
              <div class="metric-value"><b>{{ overview.report_signal.missing_reports }}</b><em>份</em></div>
            </div>
          </div>
          <p class="signal-note"><span class="signal-note-label">说明</span>{{ overview.report_signal.note }}</p>
        </div>
      </template>
    </template>

    <!-- 全公司技能矩阵 -->
    <template v-else-if="props.mode === 'matrix'">
      <p v-if="!matrix" class="empty-tip">数据加载中，或后端服务未启动…</p>
      <template v-else>
        <div class="panel role-banner">
          <p>{{ matrix.summary }}</p>
          <div class="role-toolbar">
            <span class="chip info">{{ matrix.scope }}</span>
            <span class="chip">数据截至 {{ matrix.as_of }}</span>
          </div>
        </div>

        <div class="metrics four-metrics">
          <div class="metric panel"><small>在册 / 班组</small><div class="metric-value"><b>86</b><em>人 / 9 组</em></div><span class="good">覆盖 5 类核心技能</span></div>
          <div class="metric panel"><small>L3 高级技能人才</small><div class="metric-value"><b>{{ matrix.level_distribution[0].count }}</b><em>人</em></div><span class="good">占比 {{ matrix.level_distribution[0].share }}% · 带教主力</span></div>
          <div class="metric panel"><small>L1 待培养人群</small><div class="metric-value"><b class="warn">{{ matrix.level_distribution[2].count }}</b><em>人</em></div><span class="warn">占比 {{ matrix.level_distribution[2].share }}% · 培训重点</span></div>
          <div class="metric panel"><small>单点依赖岗位</small><div class="metric-value"><b class="warn">{{ matrix.single_point_posts }}</b><em>个</em></div><span class="warn">无备份或备份不足，需继任者培养</span></div>
        </div>

        <div class="panel">
          <div class="panel-title"><h2>全员技能等级分布</h2><span class="metric-note">按主技能口径统计 86 人</span></div>
          <div class="table-wrap">
            <table class="role-table">
              <thead><tr><th>等级</th><th class="num">人数</th><th class="num">占比</th><th style="width: 240px">分布</th><th>说明</th></tr></thead>
              <tbody>
                <tr v-for="level in matrix.level_distribution" :key="level.level">
                  <td><b>{{ level.level }}</b></td>
                  <td class="num">{{ level.count }}</td>
                  <td class="num">{{ level.share }}%</td>
                  <td><div :class="level.level === 'L3' ? 'bar' : level.level === 'L2' ? 'bar' : 'bar warn'"><i :style="{ width: level.share + '%' }"></i></div></td>
                  <td>{{ level.note }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="role-toolbar" style="margin-top: 12px">
            <span class="chip" v-for="legend in matrix.level_legend" :key="legend.level">{{ legend.level }} {{ legend.label }} · {{ legend.note }}</span>
          </div>
        </div>

        <div class="panel">
          <div class="panel-title"><h2>技能达标矩阵</h2><span class="metric-note">要求等级 vs 实有人数 · 谁强谁弱</span></div>
          <div class="table-wrap">
            <table class="role-table">
              <thead><tr><th>技能</th><th>要求</th><th class="num">需求</th><th class="num">实有</th><th class="num">缺口</th><th style="width: 200px">达标率</th><th>班组覆盖</th><th>强班组</th><th>弱班组</th><th>建议</th></tr></thead>
              <tbody>
                <tr v-for="skill in matrix.skills" :key="skill.skill">
                  <td><b>{{ skill.skill }}</b> <span :class="priorityClass(skill.severity)">{{ skill.severity }}</span></td>
                  <td>{{ skill.required_level }}</td>
                  <td class="num">{{ skill.required_people }}</td>
                  <td class="num">{{ skill.actual_people }}</td>
                  <td class="num">{{ skill.need }}</td>
                  <td>
                    <div :class="barClass(skill.met_rate)"><i :style="{ width: skill.met_rate + '%' }"></i></div>
                    <small :class="rateClass(skill.met_rate)">{{ skill.met_rate }}%</small>
                  </td>
                  <td>{{ skill.coverage }}</td>
                  <td>{{ skill.strong_team }}</td>
                  <td>{{ skill.weak_team }}</td>
                  <td>{{ skill.note }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="panel">
          <div class="panel-title"><h2>关键岗位备份情况</h2><span class="metric-note">是否有备份 · 继任者计划</span></div>
          <div class="table-wrap">
            <table class="role-table">
              <thead><tr><th>关键岗位</th><th>要求</th><th class="num">现有人数</th><th class="num">需求</th><th class="num">可备份</th><th>备份状态</th><th>风险</th><th>继任计划</th><th>建议</th></tr></thead>
              <tbody>
                <tr v-for="post in matrix.key_posts" :key="post.post">
                  <td><b>{{ post.post }}</b></td>
                  <td>{{ post.required_level }}</td>
                  <td class="num">{{ post.holders }}</td>
                  <td class="num">{{ post.required }}</td>
                  <td class="num">{{ post.backup_count }}</td>
                  <td>{{ post.backup_label }}</td>
                  <td><span :class="priorityClass(post.risk)">{{ post.risk }}</span></td>
                  <td>{{ post.successor }}</td>
                  <td>{{ post.suggestion }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="panel">
          <div class="panel-title"><h2>班组维度分布</h2><span class="metric-note">9 个班组 · 等级 / 达标 / 强弱项</span></div>
          <div class="table-wrap">
            <table class="role-table">
              <thead><tr><th>班组</th><th class="num">人数</th><th class="num">人均等级</th><th class="num">L2+ 人数</th><th style="width: 190px">达标率</th><th>强项</th><th>弱项</th><th>备份情况</th><th>风险</th></tr></thead>
              <tbody>
                <tr v-for="team in matrix.teams" :key="team.team">
                  <td><b>{{ team.team }}</b></td>
                  <td class="num">{{ team.members }}</td>
                  <td class="num">L{{ team.avg_level }}</td>
                  <td class="num">{{ team.high_level }}</td>
                  <td>
                    <div :class="barClass(team.met_rate)"><i :style="{ width: team.met_rate + '%' }"></i></div>
                    <small :class="rateClass(team.met_rate)">{{ team.met_rate }}%</small>
                  </td>
                  <td>{{ team.strong_skills }}</td>
                  <td>{{ team.weak_skills }}</td>
                  <td>{{ team.backup }}</td>
                  <td><span :class="priorityClass(team.risk)">{{ team.risk }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="grid-2">
          <div class="panel">
            <div class="panel-title"><h2>强项人才（谁强）</h2><span class="metric-note">可带教 / 可跨班组支援</span></div>
            <div class="table-wrap">
              <table class="role-table">
                <thead><tr><th>姓名</th><th>班组</th><th>技能</th><th>等级</th><th>说明</th></tr></thead>
                <tbody>
                  <tr v-for="person in matrix.strong" :key="person.name">
                    <td><b>{{ person.name }}</b></td>
                    <td>{{ person.team }}</td>
                    <td>{{ person.skill }}</td>
                    <td><span class="chip ok">{{ person.level }}</span></td>
                    <td>{{ person.note }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div class="panel">
            <div class="panel-title"><h2>待提升名单（谁弱）</h2><span class="metric-note">已排培训或取证计划</span></div>
            <div class="table-wrap">
              <table class="role-table">
                <thead><tr><th>姓名</th><th>班组</th><th>技能</th><th>等级</th><th>说明</th></tr></thead>
                <tbody>
                  <tr v-for="person in matrix.focus" :key="person.name">
                    <td><b>{{ person.name }}</b></td>
                    <td>{{ person.team }}</td>
                    <td>{{ person.skill }}</td>
                    <td><span class="chip warn">{{ person.level }}</span></td>
                    <td>{{ person.note }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </template>
    </template>

    <!-- 培训看板 -->
    <template v-else-if="props.mode === 'training'">
      <p v-if="!training" class="empty-tip">数据加载中，或后端服务未启动…</p>
      <template v-else>
        <div class="panel role-banner">
          <p>{{ training.summary }}</p>
          <div class="role-toolbar">
            <span class="chip info">统计口径：{{ training.period }}</span>
            <span class="chip">数据截至 {{ training.as_of }}</span>
          </div>
        </div>

        <div class="metrics four-metrics">
          <div class="metric panel"><small>培训完成率</small><div class="metric-value"><b class="warn">{{ training.completion.rate }}</b><em>%</em></div><span class="warn">{{ training.completion.month }} 目标 {{ training.completion.target }}%</span></div>
          <div class="metric panel"><small>培训投入</small><div class="metric-value"><b>{{ money(training.cost.invested) }}</b></div><span class="good">人均 {{ money(training.cost.per_head) }} · 预算已用 {{ training.cost.usage_rate }}%</span></div>
          <div class="metric panel"><small>投入产出比 ROI</small><div class="metric-value"><b>{{ training.roi.label }}</b></div><span class="good">可量化收益 {{ money(training.roi.benefit) }} · 回收 {{ training.roi.payback_months }} 个月</span></div>
          <div class="metric panel"><small>技能达标率提升</small><div class="metric-value"><b class="good">+{{ training.effect.delta }}</b><em>个百分点</em></div><span class="good">{{ training.effect.skill_pass_before }}% → {{ training.effect.skill_pass_after }}%</span></div>
        </div>

        <div class="grid-2">
          <div class="panel">
            <div class="panel-title"><h2>培训成本结构</h2><span class="metric-note">预算 {{ money(training.cost.budget) }}</span></div>
            <div class="table-wrap">
              <table class="role-table">
                <thead><tr><th>投入项</th><th class="num">金额</th><th class="num">占比</th></tr></thead>
                <tbody>
                  <tr v-for="item in training.cost.items" :key="item.name">
                    <td>{{ item.name }}</td>
                    <td class="num">{{ money(item.amount) }}</td>
                    <td class="num">{{ item.share }}%</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p class="role-note" style="margin-top: 10px">{{ training.cost.note }}</p>
          </div>
          <div class="panel">
            <div class="panel-title"><h2>培训效果</h2><span class="metric-note">投入后的可观测变化</span></div>
            <div class="info-list">
              <div class="info-item"><label>技能达标率</label><span>{{ training.effect.skill_pass_before }}% → {{ training.effect.skill_pass_after }}%（+{{ training.effect.delta }} 个百分点）</span></div>
              <div class="info-item"><label>考试通过率</label><span>{{ training.effect.exam_pass_rate }}%</span></div>
              <div class="info-item"><label>师傅带教次数</label><span>{{ training.effect.mentor_sessions }} 次</span></div>
              <div class="info-item"><label>定值核对超时率</label><span>{{ training.effect.timeout_before }}% → {{ training.effect.timeout_after }}%</span></div>
              <div class="info-item"><label>报告缺报率</label><span>{{ training.effect.report_missing_before }}% → {{ training.effect.report_missing_after }}%</span></div>
              <div class="info-item"><label>说明</label><span>{{ training.effect.note }}</span></div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-title"><h2>ROI 测算</h2><span class="metric-note">投入 {{ money(training.roi.invested) }} · {{ training.roi.label }}</span></div>
          <div class="table-wrap">
            <table class="role-table">
              <thead><tr><th>可量化收益项</th><th class="num">金额</th><th>测算依据</th></tr></thead>
              <tbody>
                <tr v-for="item in training.roi.items" :key="item.name">
                  <td><b>{{ item.name }}</b></td>
                  <td class="num">{{ money(item.amount) }}</td>
                  <td>{{ item.basis }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="role-note" style="margin-top: 10px">{{ training.roi.note }}</p>
        </div>

        <div class="panel">
          <div class="panel-title"><h2>部门对比</h2><span class="metric-note">完成率 / 投入 / 效果 / ROI</span></div>
          <div class="table-wrap">
            <table class="role-table">
              <thead><tr><th class="num">排名</th><th>班组</th><th class="num">人数</th><th style="width: 190px">完成率</th><th class="num">投入</th><th class="num">人均投入</th><th>效果</th><th class="num">ROI</th></tr></thead>
              <tbody>
                <tr v-for="team in training.departments" :key="team.team">
                  <td class="num">{{ team.rank }}</td>
                  <td><b>{{ team.team }}</b></td>
                  <td class="num">{{ team.members }}</td>
                  <td>
                    <div :class="barClass(team.completion)"><i :style="{ width: team.completion + '%' }"></i></div>
                    <small :class="rateClass(team.completion)">{{ team.completion }}%</small>
                  </td>
                  <td class="num">{{ money(team.invested) }}</td>
                  <td class="num">{{ money(team.per_head) }}</td>
                  <td>{{ team.effect }}</td>
                  <td class="num">{{ team.roi }} : 1</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="panel">
          <div class="panel-title">
            <div>
              <h2>个人学习计划执行情况</h2>
              <small class="chart-caption">按计划执行、进度滞后两类分开跟踪，滞后项由班组长 3 日内跟进</small>
            </div>
            <div class="role-toolbar">
              <span class="chip info">共 {{ training.plans_summary.total }} 人</span>
              <span class="chip ok">按计划 {{ training.plans_summary.on_track }} 人</span>
              <span class="chip bad">滞后 {{ training.plans_summary.lagging }} 人</span>
            </div>
          </div>
          <div class="table-wrap">
            <table class="role-table">
              <thead><tr><th>姓名</th><th>班组</th><th>学习计划</th><th>必修</th><th style="width: 190px">进度</th><th>状态</th><th>截止</th><th>说明</th></tr></thead>
              <tbody>
                <tr v-for="plan in training.plans" :key="plan.name">
                  <td><b>{{ plan.name }}</b></td>
                  <td>{{ plan.team }}</td>
                  <td>{{ plan.plan }}</td>
                  <td><el-tag :type="plan.required ? 'danger' : 'info'">{{ plan.required ? '必修' : '选修' }}</el-tag></td>
                  <td>
                    <div :class="plan.on_track ? 'bar' : 'bar warn'"><i :style="{ width: plan.progress + '%' }"></i></div>
                    <small>{{ plan.progress }}%</small>
                  </td>
                  <td><span :class="plan.on_track ? 'chip ok' : 'chip bad'">{{ plan.on_track ? '按计划' : '滞后' }}</span></td>
                  <td>{{ plan.due_at }}</td>
                  <td>{{ plan.note }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="role-note" style="margin-top: 10px">{{ training.plans_summary.note }}</p>
        </div>
      </template>
    </template>

    <!-- 运行诊断 Agent：留一个框，点击后实时输出诊断报告 -->
    <template v-else>
      <p v-if="!diagnosis" class="empty-tip">数据加载中，或后端服务未启动…</p>
      <template v-else>
        <div class="panel role-banner">
          <p>{{ diagnosis.source_label }} · 输入包括：{{ diagnosis.inputs.join('、') }}。</p>
          <div class="role-toolbar">
            <span class="chip">置信度 {{ Math.round(diagnosis.confidence * 100) }}%</span>
            <span :class="diagnosis.need_human_confirm ? 'chip warn' : 'chip ok'">{{ diagnosis.need_human_confirm ? '需老总确认后执行' : '可直接执行' }}</span>
          </div>
        </div>

        <div class="panel agent-panel">
          <div class="panel-title">
            <div>
              <h2>公司运行诊断 Agent</h2>
              <small class="chart-caption">点一下按钮，Agent 立刻按当前数据出报告：现在卡在哪、是缺人还是缺技能、先做什么、能省多少钱</small>
            </div>
            <button type="button" class="action-button primary" :disabled="running" @click="runDiagnosis">
              {{ running ? '诊断中…' : (report ? '重新运行诊断' : '点击运行诊断 Agent') }}
            </button>
          </div>

          <p v-if="runError" class="empty-note">{{ runError }}</p>

          <div v-if="!report" class="agent-placeholder">
            <b>还没有生成诊断结论</b>
            <p>点右上角按钮，Agent 会立刻读取上面 {{ diagnosis.inputs.length }} 类输入出结论：主因是人才缺失还是技能不足、缺口集中在哪些岗位、建议措施与降本测算各是多少。结论标注「需老总确认后执行」，不会自动改动公司数据。</p>
          </div>

          <template v-else>
            <div class="agent-verdict">
              <span class="chip info">诊断结论</span>
              <b>{{ report.verdict.headline }}</b>
              <span class="metric-note">{{ report.diagnosis_id }} · {{ report.ran_at }} · 证据 {{ report.evidence_count }} 条 · {{ report.source_label }}</span>
            </div>
            <p class="role-note" style="margin-top: 10px">{{ report.summary }}</p>
            <ul class="agent-reasons">
              <li v-for="(evidence, index) in report.verdict.evidence" :key="index">{{ evidence }}</li>
            </ul>

            <div class="agent-block">
              <h3>问题清单（{{ report.findings.length }} 项）</h3>
              <ul class="timeline">
                <li class="timeline-item" v-for="finding in report.findings" :key="finding.title">
                  <div class="timeline-head"><b>{{ finding.title }}</b></div>
                  <p>影响：{{ finding.impact }}</p>
                  <p>依据：{{ finding.evidence }}</p>
                </li>
              </ul>
            </div>

            <div class="agent-block">
              <h3>降本增效测算（年度口径）</h3>
              <div class="grid-4">
                <div class="info-item"><label>当前用人成本</label><span>{{ money(report.cost_summary.current_total) }}</span></div>
                <div class="info-item"><label>优化后测算</label><span>{{ money(report.cost_summary.optimized_total) }}</span></div>
                <div class="info-item"><label>预计节省</label><span>{{ money(report.cost_summary.saving) }}</span></div>
                <div class="info-item"><label>口径说明</label><span>{{ report.cost_summary.note }}</span></div>
              </div>
            </div>

            <div class="agent-block">
              <h3>建议措施（需人工确认后执行）</h3>
              <div class="table-wrap">
                <table class="role-table">
                  <thead><tr><th>优先级</th><th>责任方</th><th>措施</th><th>成本影响</th><th>预期效果</th></tr></thead>
                  <tbody>
                    <tr v-for="action in report.actions" :key="action.action">
                      <td><span :class="priorityClass(action.priority)">{{ action.priority }}</span></td>
                      <td>{{ action.owner }}</td>
                      <td>{{ action.action }}</td>
                      <td>{{ action.cost_impact }}</td>
                      <td>{{ action.expected }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="agent-block">
              <h3>本次诊断同步的板块</h3>
              <div class="tag-row">
                <span class="chip ok" v-for="item in report.updated_modules" :key="item">{{ item }}</span>
              </div>
              <p class="role-note">报告编号 {{ report.diagnosis_id }}，生成时间 {{ report.ran_at }}；换到别的板块再回来，仍会读回本次结论。</p>
            </div>
          </template>
        </div>
      </template>
    </template>
    <!-- 驾驶舱共享悬浮提示：固定定位跟随鼠标，pointer-events 关闭不挡操作 -->
    <div v-if="dashTip.show" class="dash-tip" :style="dashTipStyle">
      <b>{{ dashTip.title }}</b>
      <p v-for="(row, index) in dashTip.rows" :key="index"><span>{{ row[0] }}</span>{{ row[1] }}</p>
    </div>
    <!-- 风险与告警全量弹窗：面板里只铺前三条，其余在这里看，条目多时列表内滚动 -->
    <Teleport to="body">
      <div v-if="alertModal" class="dash-modal-mask" @click.self="closeAlertModal">
        <div class="dash-modal" role="dialog" aria-modal="true" aria-label="全部风险与告警">
          <div class="dash-modal-head">
            <div>
              <h3>风险与告警</h3>
              <small>共 {{ alerts.length }} 项待跟踪 · 按严重度排序</small>
            </div>
            <button class="dash-modal-x" type="button" aria-label="关闭" @click="closeAlertModal">×</button>
          </div>
          <ul class="dash-modal-list">
            <li v-for="(alert, index) in alerts" :key="'m' + alert.title" :class="'alert-item lv-' + alert.level" :style="{ animationDelay: index * 0.05 + 's' }">
              <i class="alert-dot"></i>
              <div class="alert-body"><b>{{ alert.title }}</b><p>{{ alert.detail }}</p></div>
            </li>
          </ul>
          <p class="dash-modal-foot">数据取自人才驾驶舱总览与组长报告信号；处置与跟踪在「运行诊断 Agent」里闭环。</p>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
/* ============================================================
   老总驾驶舱：漏斗 / 环形仪表 / 横向进度条 / 环形饼图 / 折线 / 告警
   颜色全部走主题 token（--role-accent / --gold / --green / --amber /
   --red / --ink / --sub / --line-soft），黑夜与白天自动跟随，不写死深色。
   ============================================================ */
.dash-grid { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr) minmax(0, 5fr); gap: 16px; align-items: stretch; }
@media (max-width: 1280px) { .dash-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) { .dash-grid { grid-template-columns: minmax(0, 1fr); } }
/* 面板一律撑满格子高度，内部用 flex 分配剩余空间——避免整行被最高的那一格撑开、其余格子底下留白 */
.dash-panel { display: flex; flex-direction: column; gap: 10px; min-width: 0; height: 100%; }
.dash-panel > .panel-title { margin-bottom: 0; }

/* 悬浮提示框 */
.dash-tip { position: fixed; z-index: 60; max-width: 280px; padding: 10px 13px; border-radius: 4px; pointer-events: none;
  background: var(--card-solid, #fff); border: 1px solid var(--goldline, rgba(217, 189, 138, .5)); box-shadow: 0 8px 24px rgba(0, 0, 0, .35); }
.dash-tip b { display: block; margin-bottom: 4px; font-size: 14px; color: var(--ink); }
.dash-tip p { margin: 2px 0; font-size: 13px; color: var(--sub); line-height: 1.55; }
.dash-tip p span { margin-right: 8px; padding: 1px 7px; border-radius: 2px; background: var(--gold-soft, rgba(217, 189, 138, .14)); color: var(--gold); font-size: 12px; font-weight: 700; }

/* ---- 漏斗图 ---- */
/* 图与图例一起在面板剩余空间里均分，末层图例不会悬在底部留白上 */
.funnel-svg { width: 100%; overflow: visible; }
.funnel-band { cursor: pointer; stroke: var(--role-line, rgba(91, 155, 255, .42)); stroke-width: 1; transition: filter .15s; transform-box: fill-box; transform-origin: center;
  animation: funnelIn .7s cubic-bezier(.25, .8, .3, 1) both; }
.funnel-band:hover { filter: brightness(1.18); }
.funnel-band-0 { fill: var(--role-accent); }
.funnel-band-1 { fill: var(--role-accent); opacity: .8; }
.funnel-band-2 { fill: var(--role-accent); opacity: .62; }
.funnel-band-3 { fill: var(--gold); opacity: .85; }
.funnel-num { fill: #ffffff; font-size: 19px; font-weight: 800; text-anchor: middle; font-family: Consolas, monospace; pointer-events: none; }
@keyframes funnelIn { from { opacity: 0; transform: scaleY(.25); } }
.funnel-legend { list-style: none; margin: 2px 0 0; padding: 0; display: grid; gap: 5px; flex: 1; align-content: space-between; }
.funnel-legend li { display: flex; align-items: baseline; gap: 8px; font-size: 13px; color: var(--sub); }
.funnel-legend li span { flex: 1; min-width: 0; }
.funnel-legend li b { color: var(--ink); font-family: Consolas, monospace; }
.legend-dot { flex: 0 0 auto; width: 8px; height: 8px; border-radius: 2px; align-self: center; }
.ld-0 { background: var(--role-accent); }
.ld-1 { background: var(--role-accent); opacity: .8; }
.ld-2 { background: var(--role-accent); opacity: .62; }
.ld-3 { background: var(--gold); }

/* ---- 环形仪表盘 ---- */
.dash-gauges { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; flex: 1; align-content: center; }
@media (max-width: 760px) { .dash-gauges { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
.dash-gauge { position: relative; display: grid; justify-items: center; gap: 2px; padding: 8px 4px 6px; border-radius: 4px; background: rgba(15, 27, 55, .35); border: 1px solid var(--line-soft, rgba(34, 52, 92, .55)); cursor: pointer; transition: border-color .15s, background .15s; }
.dash-gauge:hover { border-color: var(--role-line, rgba(91, 155, 255, .42)); background: var(--role-soft, rgba(91, 155, 255, .08)); }
.dash-gauge svg { width: 128px; height: 128px; }
.gauge-tick { stroke: var(--line-soft, rgba(34, 52, 92, .55)); stroke-width: 1.5; }
.gauge-track { fill: none; stroke: var(--line-soft, rgba(34, 52, 92, .55)); stroke-width: 9; stroke-linecap: round; }
.gauge-arc { fill: none; stroke-width: 9; stroke-linecap: round; transition: stroke-dasharray .1s linear; }
.gauge-center { position: absolute; top: 72px; left: 0; right: 0; text-align: center; pointer-events: none; transform: translateY(-50%); }
.gauge-center b { font-size: 24px; font-weight: 800; color: var(--ink); font-family: Consolas, monospace; }
.gauge-center i { font-style: normal; font-size: 13px; color: var(--sub); margin-left: 1px; }
.gauge-label { font-size: 13px; font-weight: 700; color: var(--sub); }
@media (max-width: 420px) { .dash-gauge svg { width: 96px; height: 96px; } .gauge-center { top: 56px; } .gauge-center b { font-size: 20px; } }
.dash-footnote { margin: 0; font-size: 12.5px; color: var(--sub); line-height: 1.6; }

/* ---- 横向进度条：复用全局 .bar 配色，仅加入入场生长动画 ---- */
.dash-bars { list-style: none; margin: 0; padding: 0; display: grid; gap: 11px; flex: 1; align-content: space-between; }
.dash-bars li { display: grid; gap: 5px; cursor: pointer; }
.dash-bar-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; font-size: 13.5px; color: var(--sub); }
.dash-bar-head b { color: var(--ink); font-family: Consolas, monospace; font-size: 14.5px; }
.dash-bars .bar > i { animation: barGrow .8s cubic-bezier(.25, .8, .3, 1) both; }
@keyframes barGrow { from { width: 0; } }

/* ---- 环形饼图 ---- */
/* 饼图 + 图例整体在面板剩余高度里居中，留白上下均分而不是全堆在底部 */
.dash-pie-body { flex: 1; min-height: 0; display: flex; flex-direction: column; justify-content: center; gap: 12px; }
.dash-pie { position: relative; display: grid; place-items: center; }
.dash-pie svg { width: 178px; height: 178px; }
.pie-seg { fill: none; cursor: pointer; transition: opacity .15s, stroke-width .15s; }
.pie-seg.focus { stroke-width: 30; }
.dash-pie:hover .pie-seg:not(.focus) { opacity: .55; }
.pie-center { position: absolute; display: grid; justify-items: center; gap: 0; pointer-events: none; text-align: center; }
.pie-center small { font-size: 12px; color: var(--sub); }
.pie-center b { font-size: 24px; font-weight: 800; color: var(--ink); font-family: Consolas, monospace; line-height: 1.2; }
.pie-center span { font-size: 12.5px; color: var(--sub); }
.pie-legend { list-style: none; margin: 0; padding: 0; display: grid; gap: 5px; }
.pie-legend li { display: flex; align-items: baseline; gap: 8px; padding: 3px 6px; border-radius: 2px; font-size: 13px; color: var(--sub); cursor: pointer; transition: background .15s; }
.pie-legend li:hover, .pie-legend li.focus { background: var(--hover, rgba(91, 155, 255, .08)); }
.pie-legend li span { flex: 1; min-width: 0; }
.pie-legend li b { color: var(--ink); font-family: Consolas, monospace; }
.pie-legend i { flex: 0 0 auto; width: 8px; height: 8px; border-radius: 2px; align-self: center; }

/* ---- 折线图：描线生长动画 + 悬停十字线 ---- */
/* 图区吃掉面板剩余高度，但 SVG 的 viewBox 跟着实际像素走（1:1），只拉伸布局不拉伸图形 */
.dash-cost { margin-top: 2px; flex: 1; min-height: 150px; grid-template-rows: minmax(0, 1fr) 26px; }
.dash-cost svg { height: 100%; }
.dash-line-poly { stroke-width: 2.5; }
/* 首末月份标签改为内侧对齐，避免贴边被裁掉半个字 */
.dash-cost .chart-x span:first-child { transform: none; }
.dash-cost .chart-x span:last-child { transform: translateX(-100%); }
.dash-line-poly { stroke-dasharray: 1; stroke-dashoffset: 1; animation: lineDraw 1.4s .15s ease-out forwards; }
@keyframes lineDraw { to { stroke-dashoffset: 0; } }
.dash-area { animation: areaIn .9s .9s ease-out both; }
@keyframes areaIn { from { opacity: 0; } }
.cost-cross { stroke: var(--gold, #d9bd8a); stroke-width: 1; stroke-dasharray: 4 3; opacity: .8; }

/* ---- 告警列表 ---- */
/* 面板里只铺前三条：条目在剩余高度内均匀分布，内容再多也只在列表内滚动，不会把整行撑高 */
.dash-alerts { list-style: none; margin: 0; padding: 0 3px 0 0; display: grid; gap: 8px; align-content: space-between;
  flex: 1; min-height: 0; overflow-y: auto; scrollbar-width: thin; scrollbar-color: var(--role-line, rgba(91, 155, 255, .42)) transparent; }
.dash-alerts::-webkit-scrollbar { width: 4px; }
.dash-alerts::-webkit-scrollbar-thumb { border-radius: 2px; background: var(--role-line, rgba(91, 155, 255, .42)); }
.dash-alerts::-webkit-scrollbar-track { background: transparent; }
/* 展开入口：贴面板底部，和另两格底部对齐 */
.dash-more { flex: 0 0 auto; display: flex; align-items: center; justify-content: center; gap: 6px; width: 100%; padding: 7px 12px;
  border: 1px solid var(--line-soft, rgba(34, 52, 92, .55)); border-radius: 4px; background: transparent; color: var(--sub);
  font-size: 13px; font-weight: 700; cursor: pointer; transition: color .15s, border-color .15s, background .15s; }
.dash-more:hover { color: var(--gold); border-color: var(--goldline, rgba(217, 189, 138, .5)); background: var(--gold-soft, rgba(217, 189, 138, .1)); }
.dash-more em { font-style: normal; transition: transform .15s; }
.dash-more:hover em { transform: translateX(3px); }
.alert-item { display: flex; gap: 10px; align-items: flex-start; padding: 9px 11px; border-radius: 4px; background: rgba(15, 27, 55, .35); border: 1px solid var(--line-soft, rgba(34, 52, 92, .55));
  animation: alertIn .5s cubic-bezier(.25, .8, .3, 1) both; transition: border-color .15s, background .15s; }
.alert-item:hover { border-color: var(--role-line, rgba(91, 155, 255, .42)); background: var(--role-soft, rgba(91, 155, 255, .08)); }
.alert-dot { flex: 0 0 auto; width: 8px; height: 8px; margin-top: 6px; border-radius: 50%; }
.lv-bad .alert-dot { background: var(--red); animation: alertPulse 2.2s ease-out infinite; }
.lv-warn .alert-dot { background: var(--amber); }
.alert-body { min-width: 0; }
.alert-body b { display: block; font-size: 14px; color: var(--ink); }
.alert-body p { margin: 2px 0 0; font-size: 12.5px; color: var(--sub); line-height: 1.6; }
.lv-bad .alert-body b { color: var(--red); }
.lv-warn .alert-body b { color: var(--amber); }
@keyframes alertIn { from { opacity: 0; transform: translateX(12px); } }
@keyframes alertPulse { 0% { box-shadow: 0 0 0 0 rgba(239, 83, 80, .4); } 70% { box-shadow: 0 0 0 7px rgba(239, 83, 80, 0); } 100% { box-shadow: 0 0 0 0 rgba(239, 83, 80, 0); } }

/* ---- 告警全量弹窗：列表内滚动，超出可视高度不挤页面 ---- */
.dash-modal-mask { position: fixed; inset: 0; z-index: 90; display: grid; place-items: center; padding: 24px;
  background: rgba(4, 9, 22, .6); backdrop-filter: blur(2px); animation: maskIn .18s ease-out both; }
.dash-modal { width: min(560px, 100%); max-height: min(76vh, 640px); display: flex; flex-direction: column; gap: 12px;
  padding: 18px 20px 16px; border-radius: 4px; background: var(--card-solid, #fff); border: 1px solid var(--line); border-top: 1px solid var(--goldline);
  box-shadow: 0 18px 48px rgba(0, 0, 0, .45); animation: modalIn .22s cubic-bezier(.25, .8, .3, 1) both; }
.dash-modal-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.dash-modal-head h3 { margin: 0; font-size: 17px; font-weight: 800; color: var(--ink); }
.dash-modal-head h3::before { content: ''; display: inline-block; width: 4px; height: 13px; margin-right: 8px; vertical-align: -1px;
  background: linear-gradient(180deg, var(--gold), var(--gold-deep, var(--gold))); }
.dash-modal-head small { display: block; margin-top: 5px; font-size: 12.5px; color: var(--sub); }
.dash-modal-x { flex: 0 0 auto; width: 28px; height: 28px; padding: 0; border: 1px solid var(--line-soft, rgba(34, 52, 92, .55)); border-radius: 2px;
  background: transparent; color: var(--sub); font-size: 18px; line-height: 1; cursor: pointer; transition: color .15s, border-color .15s; }
.dash-modal-x:hover { color: var(--red); border-color: var(--red); }
.dash-modal-list { list-style: none; margin: 0; padding: 0 4px 0 0; display: grid; gap: 8px; overflow-y: auto; min-height: 0;
  scrollbar-width: thin; scrollbar-color: var(--role-line, rgba(91, 155, 255, .42)) transparent; }
.dash-modal-list::-webkit-scrollbar { width: 4px; }
.dash-modal-list::-webkit-scrollbar-thumb { border-radius: 2px; background: var(--role-line, rgba(91, 155, 255, .42)); }
.dash-modal-foot { margin: 0; font-size: 12px; color: var(--sub); line-height: 1.6; }
@keyframes maskIn { from { opacity: 0; } }
@keyframes modalIn { from { opacity: 0; transform: translateY(10px) scale(.985); } }

/* 白天模式：小面板底色回到浅色 */
html.day .dash-gauge, html.day .alert-item { background: #f6f9fd; border-color: #dfe6f2; }
html.day .dash-tip { box-shadow: 0 8px 24px rgba(31, 45, 80, .22); }
html.day .dash-modal { box-shadow: 0 18px 48px rgba(31, 45, 80, .26); }

/* 减弱动态效果：所有入场/循环动画直接关闭 */
.no-anim .funnel-band, .no-anim .dash-bars .bar > i, .no-anim .alert-item,
.no-anim .dash-line-poly, .no-anim .dash-area, .no-anim .lv-bad .alert-dot { animation: none !important; }
.no-anim .dash-line-poly { stroke-dashoffset: 0; }
.no-anim .dash-area { opacity: 1; }
</style>
