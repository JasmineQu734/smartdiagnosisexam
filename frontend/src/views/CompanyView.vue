<script setup>
import { computed, onMounted, ref, watch } from 'vue';
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
// 折线画布：viewBox 固定 760×220，横向按月均分，纵向按「整数好读」的刻度上限拉伸
const costChart = { left: 20, right: 740, top: 18, bottom: 204, width: 760, height: 220 };
const toWan = (value) => (Number(value) || 0) / 10000;
const wanText = (value) => toWan(value).toFixed(1);
const costTop = computed(() => {
  const peak = Math.max(...costTrend.value.map((item) => toWan(item.total)), 0);
  return [4, 6, 8, 10, 12, 14, 16, 20, 24, 30, 40, 50, 60, 80, 100].find((tick) => tick >= peak) || Math.ceil(peak / 10) * 10;
});
// 刻度线（上限 / 半值 / 0）：左侧刻度文字与图内刻度线共用同一套 y 坐标，保证文字压线对齐
const costGrid = computed(() => {
  const max = costTop.value;
  return [0, 1, 2].map((index) => {
    const y = costChart.top + (index * (costChart.bottom - costChart.top)) / 2;
    return { y, top: `${(y / costChart.height) * 100}%`, label: String((max * (2 - index)) / 2) };
  });
});
const costAxisX = (index) => {
  const span = costChart.right - costChart.left;
  return costChart.left + (costTrend.value.length > 1 ? (index / (costTrend.value.length - 1)) * span : span / 2);
};
const costPointY = (value) => costChart.bottom - (toWan(value) / (costTop.value || 1)) * (costChart.bottom - costChart.top);
const costPoints = computed(() => costTrend.value.map((item, index) => ({ x: costAxisX(index), y: costPointY(item.total), item })));
const costLinePoints = computed(() => costPoints.value.map((point) => `${point.x},${point.y}`).join(' '));
const costAreaPoints = computed(() => {
  const points = costPoints.value;
  return `${points[0].x},${costChart.bottom} ${costLinePoints.value} ${points[points.length - 1].x},${costChart.bottom}`;
});
// 悬停命中区按相邻中点切分 x 轴：鼠标落在任意月份列上都能读出当月结构与累计
const costHit = (index) => {
  const points = costPoints.value;
  const left = index === 0 ? costChart.left : (points[index - 1].x + points[index].x) / 2;
  const right = index === points.length - 1 ? costChart.right : (points[index].x + points[index + 1].x) / 2;
  return { x: left, width: Math.max(8, right - left) };
};
const activeCostMonth = ref(-1);
// 没有悬停时默认聚焦成本最高的月份，保证不悬停也能看到结构数字
const peakCostMonth = computed(() => costPoints.value.reduce((best, point, index) => (point.item.total > costTrend.value[best].total ? index : best), 0));
const peakCost = computed(() => costTrend.value[peakCostMonth.value]);
const focusCostIndex = computed(() => (activeCostMonth.value >= 0 ? activeCostMonth.value : peakCostMonth.value));
const focusCost = computed(() => costTrend.value[focusCostIndex.value]);
const costCaption = computed(() => {
  const item = focusCost.value;
  if (activeCostMonth.value >= 0) {
    return `${item.month}：合计 ${wanText(item.total)} 万元 · 培训 ${wanText(item.training)} / 加班 ${wanText(item.overtime)} / 招聘 ${wanText(item.hiring)} / 外委 ${wanText(item.outsourcing)} · 累计 ${wanText(item.cumulative)} 万元`;
  }
  return `月度发生额（万元）· 最高 ${peakCost.value.month} ${wanText(peakCost.value.total)} 万元 · 悬停看当月结构`;
});
const costLabelLeft = (index) => `${(costAxisX(index) / costChart.width) * 100}%`;

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

        <div class="grid-2">
          <div class="panel cost-panel">
            <div class="panel-title">
              <div>
                <h2>用人成本</h2>
                <small class="chart-caption">{{ costCaption }}</small>
              </div>
              <span class="metric-note">2026 年度累计</span>
            </div>
            <div class="grid-4">
              <div class="info-item"><label>培训投入</label><span>{{ money(overview.cost.training) }}</span></div>
              <div class="info-item"><label>加班成本</label><span>{{ money(overview.cost.overtime) }}</span></div>
              <div class="info-item"><label>招聘成本</label><span>{{ money(overview.cost.hiring) }}</span></div>
              <div class="info-item"><label>外委支出</label><span>{{ money(overview.cost.outsourcing) }}</span></div>
            </div>
            <div class="line-chart cost-chart">
              <div class="chart-y">
                <span v-for="line in costGrid" :key="line.label" :style="{ top: line.top }">{{ line.label }}</span>
              </div>
              <svg viewBox="0 0 760 220" role="img" :aria-label="'用人成本月度折线图（万元）：2026 年 1—' + costTrend.length + ' 月，累计 ' + money(overview.cost.total)" preserveAspectRatio="none">
                <line v-for="line in costGrid" :key="'grid' + line.y" :x1="costChart.left" :x2="costChart.right" :y1="line.y" :y2="line.y"/>
                <polygon class="cost-area" :points="costAreaPoints"/>
                <polyline class="cost-line" :points="costLinePoints"/>
                <circle class="cost-dot" v-for="(point, index) in costPoints" :key="'dot' + index" :class="{ focus: focusCostIndex === index }" :cx="point.x" :cy="point.y" :r="focusCostIndex === index ? 7 : 5"/>
                <rect class="cost-hit" v-for="(point, index) in costPoints" :key="'hit' + index" :x="costHit(index).x" y="0" :width="costHit(index).width" height="220" @mouseenter="activeCostMonth = index" @mouseleave="activeCostMonth = -1"/>
              </svg>
              <div class="chart-x">
                <span v-for="(item, index) in costTrend" :key="item.month" :class="{ active: focusCostIndex === index }" :style="{ left: costLabelLeft(index) }">{{ item.month }}</span>
              </div>
            </div>
            <p class="role-note" style="margin-top: 10px">合计 <b>{{ money(overview.cost.total) }}</b>；降本方向与培训投入产出去「运行诊断 Agent」与「培训看板」查看。</p>
          </div>
          <div class="panel panel-fill">
            <div class="panel-title"><h2>人才风险与稳定性</h2><span class="metric-note">安全 · 稳定性 · 证书</span></div>
            <div class="info-list" style="grid-template-columns: minmax(0, 1fr)">
              <div class="info-item"><label>安全风险班组（{{ overview.talent_risk.safety_teams }} 个）</label><span>{{ overview.talent_risk.safety_note }}</span></div>
              <div class="info-item"><label>离职风险（{{ overview.talent_risk.retention_people }} 人 / 关键岗 {{ overview.talent_risk.retention_posts }} 个）</label><span>{{ overview.talent_risk.retention_note }}</span></div>
              <div class="info-item"><label>证书到期提醒（{{ overview.talent_risk.cert_expiring }} 本）</label><span>{{ overview.talent_risk.cert_note }}</span></div>
            </div>
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
  </section>
</template>
