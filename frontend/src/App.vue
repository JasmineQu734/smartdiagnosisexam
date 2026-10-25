<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { api, downloadFile, getData, postData, setApiUser } from './api';
import './layout.css';
import './roles.css';
/* 深色科技工业风全局覆盖层（视觉基准 = 3D 数字孪生页）：
   必须放在 layout/roles 之后引入，同权重选择器后到先胜 */
import './twin-dark.css';
import './refine.css';
import SelfPortraitView from './views/SelfPortraitView.vue';
import AbilityView from './views/AbilityView.vue';
import MemoryView from './views/MemoryView.vue';
import GrowthView from './views/GrowthView.vue';
import AdviceView from './views/AdviceView.vue';
import TeamReportView from './views/TeamReportView.vue';
import CompanyView from './views/CompanyView.vue';
import AdminView from './views/AdminView.vue';
import AgentStrip from './views/AgentStrip.vue';
import LoginStage from './views/LoginStage.vue';
import DigitalTwinView from './views/DigitalTwinView.vue';
const navItems = computed(() => NAV_BY_ROLE[currentUser.value.role] || EMPLOYEE_NAV);
const active = ref('skills');

/* 全局昼夜主题：night = 深夜航蓝（默认），day = 浅色工作台。
   通过 html 根元素类切换（day/dark），dark 类同时驱动 Element Plus 深色变量。 */
const theme = ref(localStorage.getItem('wb-theme') === 'day' ? 'day' : 'night');
watch(theme, (t) => {
  const day = t === 'day';
  const el = document.documentElement;
  el.classList.toggle('day', day);
  el.classList.toggle('dark', !day);
  localStorage.setItem('wb-theme', t);
  // 3D 孪生 iframe 同步：白天换 UI 浅色 + 场景日照，黑夜反之
  const frame = document.querySelector('.twin-frame');
  if (frame && frame.contentWindow) {
    try { frame.contentWindow.postMessage({ type: 'wb-theme', theme: t }, '*'); } catch (err) { /* 跨域降级 */ }
  }
}, { immediate: true });
const toggleTheme = () => { theme.value = theme.value === 'day' ? 'night' : 'day'; };
const loggedIn = ref(false);
const loginError = ref('');
const loggingIn = ref(false);
const currentUser = ref({ username: '', display_name: '', role: '', position: '' });
const demoUsers = [
  { username: 'zhangwei', display_name: '张伟', role: 'EMPLOYEE', roleName: '员工', position: '变电运维值班员', team: '变电运维一班' },
  { username: 'limin', display_name: '李民', role: 'TEAM_LEAD', roleName: '组长', position: '变电运维一班班组长', team: '变电运维一班' },
  { username: 'wangzong', display_name: '王总', role: 'EXECUTIVE', roleName: '公司上级（老总）', position: '分管老总', team: '中心管理层' },
  { username: 'admin', display_name: '系统管理员', role: 'ADMIN', roleName: '系统管理员', position: '平台管理员', team: '信息中心' }
];

// 四个身份的识别色与视图说明：同一套设计系统，只换主色、徽标与头像形态，保证一眼看出当前是谁在看
const ROLE_THEME = {
  EMPLOYEE: { key: 'employee', view: '员工视图', scope: '仅本人数据', hint: '一线成长视角：只看自己的技能雷达、个人画像与考试成绩' },
  TEAM_LEAD: { key: 'teamLead', view: '组长视图', scope: '本人 + 班组数据', hint: '班组带教视角：班组管理 + 检测报告填报与审核' },
  EXECUTIVE: { key: 'executive', view: '老总视图', scope: '全公司数据', hint: '经营决策视角：全公司人才总览、技能矩阵与运行诊断' },
  ADMIN: { key: 'admin', view: '管理员视图', scope: '平台数据', hint: '平台运维视角：只管数据、权限与考试配置，不看个人画像' }
};
const themeOf = (role) => ROLE_THEME[role] || ROLE_THEME.EMPLOYEE;
const roleTheme = computed(() => themeOf(currentUser.value.role));
const shellClass = computed(() => 'role-' + roleTheme.value.key);
// 登录卡跟随所选身份换色：选谁就是谁的配色
// 登录页已换成账号口令制（3D 全息城市登录卡），登录阶段统一用员工主题色
const loginTheme = computed(() => ROLE_THEME.EMPLOYEE);
// 身份色同时挂到 <body>：下拉、二次确认、轻提示这些被送到 body 下的浮层也在主壳之外，
// 靠 body 上的身份类同样能拿到当前身份的主色，换身份整页（含浮层）一起换色。
const ROLE_KEYS = ['employee', 'teamLead', 'executive', 'admin'];
watch(
  () => (loggedIn.value ? roleTheme.value.key : loginTheme.value.key),
  (key) => { for (const name of ROLE_KEYS) document.body.classList.toggle('role-' + name, name === key); },
  { immediate: true }
);

// 角色决定导航：员工与组长是个人页面（组长多一个班组报告），老总看全公司，管理员只做平台数据
const SELF_PORTRAIT_ITEM = { key: 'selfPortrait', icon: '', label: '个人自画像' };
const TWIN_ITEM = { key: 'twin', icon: '', label: '3D 数字孪生' };
const EMPLOYEE_NAV = [
  { key: 'skills', icon: '', label: '技能雷达' },
  { key: 'abilities', icon: '', label: '个人能力' },
  { key: 'memories', icon: '', label: '记忆展示' },
  { key: 'growth', icon: '', label: '成长轨迹' },
  { key: 'advice', icon: '', label: '差距与建议' },
  { key: 'learning', icon: '', label: '学习与考试' },
  { key: 'tasks', icon: '', label: '实操任务' },
  TWIN_ITEM
];
const NAV_BY_ROLE = {
  EMPLOYEE: [...EMPLOYEE_NAV, SELF_PORTRAIT_ITEM],
  TEAM_LEAD: [...EMPLOYEE_NAV, { key: 'team', icon: '', label: '班组报告' }, SELF_PORTRAIT_ITEM],
  EXECUTIVE: [
    { key: 'company', icon: '', label: '人才驾驶舱' },
    { key: 'skillMatrix', icon: '', label: '全公司技能矩阵' },
    { key: 'training', icon: '', label: '培训看板' },
    { key: 'diagnosis', icon: '', label: '运行诊断 Agent' }
  ],
  ADMIN: [
    { key: 'adminIam', icon: '', label: '用户与权限' },
    { key: 'adminContent', icon: '', label: '技能与课程' },
    { key: 'adminExam', icon: '', label: '考试配置' },
    { key: 'adminAudit', icon: '', label: '审计日志' }
  ]
};
const LANDING_BY_ROLE = { EMPLOYEE: 'twin', TEAM_LEAD: 'twin', EXECUTIVE: 'company', ADMIN: 'adminIam' };

// 演示兜底数据：接口不可用时保证页面结构完整，接口返回后会被覆盖
const demoProfile = { name: '张伟', position: '变电运维值班员', org: '变电运维中心', years: 6, readiness: 68 };
const demoGaps = [
  { type: '技能缺失', title: '继电保护 L1 -> L3', reason: '考试 62 分，定值核对任务超时', priority: 'HIGH' },
  { type: '经验缺失', title: '软压板逻辑', reason: '实操报告未提前准备定值单', priority: 'MEDIUM' }
];
const demoTasks = [{ id: 1, title: '110kV 线路保护定值核对与投退', planned_hours: 4, actual_hours: 6, status: '待评分', due_at: '2026-09-20' }];
const demoSections = [
  { skill: '继电保护', current: 1, required: 3, future: 3 },
  { skill: '倒闸操作', current: 3, required: 3, future: 3 },
  { skill: '高压试验', current: 1, required: 2, future: 3 }
];
const demoLearningSummary = { month_hours: 18, target_hours: 25, completion: 72, required_done: 6, required_total: 9, streak_days: 4, mentor_sessions: 2, focus_skill: '继电保护', last_exam_name: '继电保护理论考试', last_exam_score: 62, last_exam_pass_score: 80 };
const demoLearningPlan = [
  { course_code: 'PROTECTION_LOGIC', course_name: '软压板逻辑', course_type: 'ONLINE', hours: 4, progress: 45, required: true, skill: '继电保护', target_level: 2, due_at: '2026-09-30' },
  { course_code: 'SETTING_CHECK', course_name: '继保定值核对与投退', course_type: 'PRACTICE', hours: 8, progress: 20, required: true, skill: '继电保护', target_level: 3, due_at: '2026-10-12' },
  { course_code: 'HV_SAFETY', course_name: '高压试验安全规程', course_type: 'ONLINE', hours: 6, progress: 0, required: false, skill: '高压试验', target_level: 2, due_at: '2026-10-20' }
];
const demoLearningRecords = [
  { id: 3, course_name: '软压板逻辑', progress: 45, hours: 1.8, studied_at: '2026-09-17', status: 'IN_PROGRESS', remark: '错题回顾：软压板投退顺序' },
  { id: 2, course_name: '继保定值核对与投退', progress: 20, hours: 1.6, studied_at: '2026-09-15', status: 'IN_PROGRESS', remark: '跟师傅完成 1 次现场核对' },
  { id: 1, course_name: '安全规程（月度必修）', progress: 100, hours: 2.5, studied_at: '2026-09-08', status: 'COMPLETED', remark: '考试成绩合格' }
];
const demoResources = [
  { id: 1, title: '《软压板逻辑》微课', type: '视频', duration: '32 分钟', skill: '继电保护', level: '入门', match_reason: '对应当前重点提升项' },
  { id: 2, title: '定值核对标准作业卡（SOP）', type: '文档', duration: '8 页', skill: '继电保护', level: '进阶', match_reason: '实操报告暴露的准备不足' },
  { id: 3, title: '110kV 线路保护定值核对实操演示', type: '视频', duration: '46 分钟', skill: '高压试验', level: '进阶', match_reason: '未来需求 L3 提前准备' }
];
// 考试清单由后端 ExamCenter 提供（与管理员「统一开考」共用同一份状态），此处仅作接口未启动时的兜底演示
const demoExams = {
  summary: { total: 3, open: 0, note: '当前没有开考的考试，请等待管理员在考试配置中统一开考。' },
  items: [
    { exam_id: '1', name: '继电保护理论考试', exam_type: '理论', pass_score: 80, duration_minutes: 60, question_count: 20, attempts: 1, score: 62, status: 'FAILED', open: false, can_enter: false, round_submitted: false, gate_status: 'NOT_OPEN', gate_note: '等待管理员统一开考', status_note: '上次成绩 62 分（合格线 80 分），管理员再次开考后可补考', occurred_at: '2026-09-10 10:20' },
    { exam_id: '2', name: '倒闸操作实操考核', exam_type: '实操', pass_score: 80, duration_minutes: 45, question_count: 12, attempts: 1, score: 92, status: 'PASSED', open: false, can_enter: false, round_submitted: false, gate_status: 'NOT_OPEN', gate_note: '等待管理员统一开考', status_note: '上次成绩 92 分（合格线 80 分），管理员再次开考后可重考', occurred_at: '2026-08-28 15:40' },
    { exam_id: '3', name: '高压试验安全规程考试', exam_type: '安全', pass_score: 90, duration_minutes: 30, question_count: 15, attempts: 0, score: null, status: 'PENDING', open: false, can_enter: false, round_submitted: false, gate_status: 'NOT_OPEN', gate_note: '等待管理员统一开考', status_note: '管理员尚未开始本场考试，开考后可进入答题', occurred_at: null }
  ]
};
const demoCertificates = [
  { id: 2, name: '倒闸操作 L3 资格', level: 'L3', issued_at: '2026-08-28', status: 'VALID' },
  { id: 1, name: '变电运维安全规程（年度）', level: '-', issued_at: '2026-03-15', status: 'VALID' }
];

const demoGrowthEvents = [
  { dot: 'blue', title: '继电保护考试', note: '2026-09-10 · 理论考试 62 分，错题归因至软压板逻辑', badge: 'L1' },
  { dot: 'pink', title: '实操任务完成', note: '2026-09-15 · 110kV 线路保护定值核对，实际用时 6 小时', badge: '复盘' },
  { dot: 'teal', title: '师傅带教记录', note: '2026-09-16 · 王师傅带教定值核对 2 次', badge: '+经验' },
  { dot: 'purple', title: '系统学习建议', note: '2026-09-20 · 推荐《软压板逻辑》课程与模拟考试', badge: '计划' }
];

const demoShiftOptions = ['白班（08:00-16:00）', '中班（16:00-24:00）', '夜班（00:00-08:00）'];
const demoGasRules = [
  { code: 'O2', label: '氧气', unit: '%VOL', threshold: 19.5, direction: 'LOW', direction_label: '低于阈值报警' },
  { code: 'SF6', label: '六氟化硫', unit: 'ppm', threshold: 1000, direction: 'HIGH', direction_label: '高于阈值报警' },
  { code: 'SF6_H2O', label: 'SF6 微水', unit: 'μL/L', threshold: 150, direction: 'HIGH', direction_label: '高于阈值报警' },
  { code: 'H2S', label: '硫化氢', unit: 'ppm', threshold: 10, direction: 'HIGH', direction_label: '高于阈值报警' },
  { code: 'CO', label: '一氧化碳', unit: 'ppm', threshold: 30, direction: 'HIGH', direction_label: '高于阈值报警' },
  { code: 'CH4', label: '可燃气', unit: '%LEL', threshold: 10, direction: 'HIGH', direction_label: '高于阈值报警' }
];
const demoReportFields = [
  { name: 'detected_at', label: '检测时间', required: true, example: '2026-09-19 09:20', hint: '现场实际检测时间，精确到分钟' },
  { name: 'shift', label: '班次', required: true, example: '白班（08:00-16:00）', hint: '与当日排班表一致' },
  { name: 'location', label: '检测地点', required: true, example: '110kV 城北变电所 · 1 号主变本体间隔', hint: '站所 + 设备间隔，需可定位到具体点位' },
  { name: 'gas_type', label: '气体类型', required: true, example: 'SF6（六氟化硫）', hint: '选择后自动带出单位与标准阈值' },
  { name: 'gas_value', label: '检测数值', required: true, example: '1250', hint: '按仪器读数填写，精度与仪器一致' },
  { name: 'threshold', label: '报警阈值', required: true, example: '1000', hint: '默认取标准阈值，可按现场规程调整' },
  { name: 'phenomenon', label: '异常现象描述', required: true, example: '2026-09-19 09:20 在 1 号主变本体压力表处发现 SF6 压力由 0.42MPa 降至 0.35MPa，持续 2 小时未回升，已关闭补气阀并上报班组长。', hint: '按“时间 + 位置 + 现象 + 数值 + 已采取措施”顺序描述，15-300 字且必须包含时间或数值' },
  { name: 'measures', label: '已采取措施', required: false, example: '已关闭补气阀、设置警戒围栏并上报班组长', hint: '没有处置动作时填写“无”，不超过 200 字' },
  { name: 'sop_status', label: 'SOP 执行情况', required: true, example: '已按 SOP 执行', hint: '本次实操是否按对应作业指导书（SOP）执行；选「未按 SOP 执行」时必须写明偏差' },
  { name: 'sop_deviation', label: 'SOP 偏差说明', required: false, example: '作业人员先行进入检查井后才检测氧含量，未执行“先检测、后进入”的有限空间作业程序', hint: '仅选「未按 SOP 执行」时必填：写清哪一步没按规程做，不超过 200 字' }
];
const demoTemplate = {
  document_title: '实操任务检测报告',
  notice: '带 * 的框格为必填；文本类框格需按示例格式填写（含具体时间与数值），否则提交时校验不通过。',
  sign_boxes: ['填报人签字', '班组长确认', '技术负责人审核'],
  gas_rules: demoGasRules,
  sections: [
    { key: 'base', title: '基础信息', fields: [...demoReportFields.slice(0, 3), { name: 'member', label: '执行组员', type: 'text', required: false, example: '周强', hint: '本次实操的实际执行组员；班组长代组员填报时填写组员姓名，本人执行可留空' }] },
    { key: 'gas', title: '检测数据', fields: demoReportFields.slice(3, 6) },
    { key: 'abnormal', title: '异常现象描述', fields: demoReportFields.slice(6, 8) },
    { key: 'sop', title: 'SOP 执行情况', fields: demoReportFields.slice(8) }
  ]
};
const demoTaskBoard = [
  { id: 1, title: '110kV 线路保护定值核对与投退', skill: '继电保护', planned_hours: 4, actual_hours: 6, status: '进行中', due_at: '2026-09-22', requirement: '按标准作业卡执行并回传定值单', report_id: null, report_status: 'NONE', judgment: null, severity: null },
  { id: 2, title: '城北变电所电缆沟气体检测', skill: '高压试验', planned_hours: 2, actual_hours: null, status: '待执行', due_at: '2026-09-21', requirement: '有限空间作业，先通风检测后进入', report_id: null, report_status: 'NONE', judgment: null, severity: null },
  { id: 3, title: '1 号主变 SF6 气室微水检测', skill: '高压试验', planned_hours: 3, actual_hours: 3.5, status: '已完成', due_at: '2026-09-18', requirement: '检测数据需与上次试验记录对比', report_id: 'RPT-DEMO-0001', report_status: 'SUBMITTED', judgment: '超限', severity: '高' }
];
const demoReports = [{
  report_id: 'RPT-DEMO-0001', task_id: 3, task_title: '1 号主变 SF6 气室微水检测', member: '李民', reporter: '李民', reporter_position: '变电运维一班班组长',
  detected_at: '2026-09-18 15:40', shift: '白班（08:00-16:00）', location: '110kV 城北变电所 · 1 号主变本体间隔',
  gas_type: 'SF6_H2O', gas_label: 'SF6 微水', unit: 'μL/L', gas_value: 186, threshold: 150, direction: 'HIGH',
  judgment: '超限', severity: '高',
  phenomenon: '2026-09-18 15:40 在 1 号主变本体气室取样阀处测得 SF6 微水 186μL/L，超过标准 150μL/L，较上次试验记录（128μL/L）持续上升，已停止取样并上报班组长。',
  measures: '已停止取样、恢复取样阀并上报班组长，等待安排气体处理',
  sop_status: 'FOLLOWED', sop_deviation: '',
  submitted_at: '2026-09-18T07:40:00Z',
  analysis: { source: 'rule', source_label: '内置规则引擎 v1', severity: '高', abnormal: true, confidence: 0.80, need_human_confirm: true, run_id: 'R-20260918-154000-0001',
    conclusion: 'SF6 微水（SF6_H2O）检测值 186 μL/L 超过报警阈值 150 μL/L（超出 24.0%），结合现场现象描述判定为：气室受潮或吸附剂失效，导致 SF6 气体微水含量升高。严重度：高。',
    causes: ['气室受潮或吸附剂失效，导致 SF6 气体微水含量升高', '现象持续未恢复，缺陷可能正在发展'],
    actions: ['核查吸附剂更换与气室补气记录，判断受潮来源', '安排气体处理（再生/置换）并同步检测分解产物', '处理后 24 小时复测微水，合格后更新设备台账', '提高监测频次至每 2 小时一次，并升级上报至技术负责人'],
    rule_refs: ['REPORT_GAS_OVER_MARGIN_HIGH', 'RULE-KW-WORSENING'] },
  document_text: '一、基础信息\n报告编号：RPT-DEMO-0001\n二、检测数据\n检测数值：186 μL/L\n报警阈值：150 μL/L',
  document_pdf: '', document_docx: ''
}];

const profile = ref(demoProfile);
const skills = ref([]);
const gaps = ref(demoGaps);
const tasks = ref(demoTasks);
const learningTab = ref('summary');
const learningSummary = ref(demoLearningSummary);
const learningPlan = ref(demoLearningPlan);
const learningRecords = ref(demoLearningRecords);
const resources = ref(demoResources);
const exams = ref(demoExams.items);
const examSummary = ref(demoExams.summary);
const certificates = ref(demoCertificates);
const growthEvents = ref(demoGrowthEvents);
const taskList = ref(demoTaskBoard);
const reportList = ref(demoReports);
const reportTemplate = ref(demoTemplate);
const shiftOptions = demoShiftOptions;
const emptyReportForm = () => ({ member: '', detected_at: '', shift: '', location: '', gas_type: '', gas_value: null, threshold: null, phenomenon: '', measures: '', sop_status: '', sop_deviation: '' });
const reportForm = ref(emptyReportForm());
const reportFormTask = ref(null);
const reportFormErrors = ref({});
const reportFormVisible = ref(false);
const reportFormRunning = ref(false);
const reportDialogVisible = ref(false);
const reportDialogRunning = ref(false);
const templateDialogVisible = ref(false);
const activeReport = ref(null);
const examDialog = ref({ visible: false, title: '', subtitle: '', rows: [], item: null });
const notifyOpen = ref(false);

// 技能雷达：接口未返回数据时用演示数据兜底，保证图表与卡片口径一致
const radarSkills = computed(() => (skills.value.length ? skills.value : demoSections));
const chartAxis = { left: 20, right: 740, width: 760, levels: { 0: 198, 1: 138, 2: 78, 3: 18 } };
const clampLevel = (level) => Math.min(3, Math.max(0, Math.round(Number(level) || 0)));
const metSkills = computed(() => radarSkills.value.filter((item) => clampLevel(item.current) >= clampLevel(item.required)));
const gapSkills = computed(() => radarSkills.value.filter((item) => clampLevel(item.current) < clampLevel(item.required)));
const skillNames = (list, emptyText) => (list.length ? list.map((item) => item.skill).join(' · ') : emptyText);
const axisX = (index) => {
  const items = radarSkills.value;
  const span = chartAxis.right - chartAxis.left;
  return chartAxis.left + (items.length > 1 ? (index / (items.length - 1)) * span : span / 2);
};
const radarSeries = (key) => radarSkills.value.map((item, index) => ({ x: axisX(index), y: chartAxis.levels[clampLevel(item[key])] }));
const radarLine = (key) => radarSeries(key).map((point) => `${point.x},${point.y}`).join(' ');
// X 轴标签用与数据点相同的几何位置定位（百分比 + 居中），保证与数据点中心垂直对齐
const labelLeft = (index) => `${(axisX(index) / chartAxis.width) * 100}%`;
const skillTag = (item) => (clampLevel(item.current) >= clampLevel(item.required) ? 'success' : 'warning');
const skillState = (item) => (clampLevel(item.current) >= clampLevel(item.required) ? '已达标' : `差 ${clampLevel(item.required) - clampLevel(item.current)} 级`);
// 能力明细与雷达图的联动高亮
const activeSkill = ref(-1);

// 个性化 Agent 诊断结果由 App 统一持有：一次运行，技能雷达 / 个人能力 / 记忆展示 / 成长轨迹 / 差距与建议 同步可见
const agentDiagnosis = ref(null);
const applyDiagnosis = (payload) => { agentDiagnosis.value = payload; };
// 检测报告只由班组长填报；普通员工只查看报告
const canFillReport = computed(() => currentUser.value.role === 'TEAM_LEAD');
const externalResourceCount = computed(() => resources.value.filter((item) => item.url).length);

// 外网课程搜索：后端 /personal/course-search 按关键词在外网课程库（由 tools/fetch-courses.mjs 生成）里打分检索，
// 并给出公开课程平台的实时检索直达链接；接口没起来时用同一份课程库的本地副本兜底，保证离线演示也能搜出结果。
const demoCourseSources = [
  { code: 'ICOURSE163', name: '中国大学 MOOC', site: 'icourse163.org', category: '慕课', home_url: 'https://www.icourse163.org/', search_url: 'https://www.icourse163.org/search.htm?search={kw}', http_code: 200, checked_at: '2026-09-20' },
  { code: 'XUETANGX', name: '学堂在线', site: 'xuetangx.com', category: '慕课', home_url: 'https://www.xuetangx.com/', search_url: 'https://www.xuetangx.com/search?query={kw}', http_code: 200, checked_at: '2026-09-20' },
  { code: 'SMARTEDU_VOC', name: '国家职业教育智慧教育平台', site: 'vocational.smartedu.cn', category: '职教', home_url: 'https://vocational.smartedu.cn/', search_url: 'https://vocational.smartedu.cn/search?keyword={kw}', http_code: 200, checked_at: '2026-09-20' },
  { code: 'BILIBILI', name: '哔哩哔哩 · 技术区', site: 'search.bilibili.com', category: '视频', home_url: 'https://www.bilibili.com/', search_url: 'https://search.bilibili.com/all?keyword={kw}', http_code: 200, checked_at: '2026-09-20' },
  { code: 'CEC', name: '中国电力企业联合会', site: 'cec.org.cn', category: '行业', home_url: 'https://www.cec.org.cn/', search_url: 'https://www.cec.org.cn/search?keyword={kw}', http_code: 200, checked_at: '2026-09-20' },
  { code: 'WANFANG', name: '万方数据', site: 's.wanfangdata.com.cn', category: '学术', home_url: 'https://www.wanfangdata.com.cn/', search_url: 'https://s.wanfangdata.com.cn/paper?q={kw}', http_code: 200, checked_at: '2026-09-20' },
  { code: 'CNKI', name: '中国知网 · 期刊论文', site: 'kns.cnki.net', category: '学术', home_url: 'https://www.cnki.net/', search_url: 'https://kns.cnki.net/kns8s/search?kw={kw}', http_code: 200, checked_at: '2026-09-20' }
];
// 与 external_course 表同源的课程行：标题 / 平台 / 类型 / 时长 / 技能 / 等级 / 栏目 / 检索词 / 标签 / 匹配理由
const demoCourseRows = [
  ['继电保护原理与整定计算 · 高校慕课', 'ICOURSE163', '慕课', '按课程', '继电保护', '入门', '高校慕课 · 电气类', '继电保护 整定计算', '继电保护,整定计算,原理', '理论考试 62 分未通过，先补原理与整定计算'],
  ['电力系统继电保护（名校公开课）', 'XUETANGX', '慕课', '按课程', '继电保护', '进阶', '名校公开课 · 电气工程', '电力系统继电保护', '继电保护,二次回路,保护配置', '继保 L1→L3 缺口最大，系统学保护配置与二次回路'],
  ['继电保护装置定值整定与校验实操', 'BILIBILI', '视频', '按视频', '继电保护', '进阶', '技术区 · 现场实操', '继电保护 定值整定', '定值,整定,校验', '定值核对与投退需师傅复核，先看现场实操'],
  ['软压板投退逻辑与顺序讲解', 'BILIBILI', '视频', '按视频', '继电保护', '入门', '技术区 · 装置逻辑', '软压板 投退顺序', '软压板,压板投退,逻辑', '错题集中在软压板投退顺序'],
  ['继电保护技能等级评价与培训规范', 'CEC', '行业', '按需检索', '继电保护', '精通', '行业协会 · 技能评价', '继电保护 技能等级 评价', '技能等级,评价规范,岗位', '岗位 L1-L3 评价口径的权威出处'],
  ['继电保护定值配合与整定计算论文', 'CNKI', '学术', '按需检索', '继电保护', '精通', '学术期刊 · 继电保护', '继电保护 定值配合', '定值配合,论文,案例', '定值配合类难题的进阶依据'],
  ['变电站倒闸操作规范与实操演示', 'BILIBILI', '视频', '按视频', '倒闸操作', '入门', '技术区 · 现场实操', '倒闸操作 步骤', '倒闸操作,实操,顺序', '已达标技能，保持手感并作为带教素材'],
  ['电力安全工作规程（变电站部分）解读', 'SMARTEDU_VOC', '职教', '按课程', '倒闸操作', '入门', '国家级职教平台 · 电力类', '电力安全工作规程 变电站', '安规,变电站,红线', '操作票与安规条款逐条对照学习'],
  ['变电运维值班员岗位技能实训', 'SMARTEDU_VOC', '职教', '按课程', '倒闸操作', '进阶', '国家级职教平台 · 电力类', '变电运维 实训', '变电运维,实训,岗位', '变电运维一班岗位技能标准化训练'],
  ['高电压技术（绝缘与试验基础）', 'ICOURSE163', '慕课', '按课程', '高压试验', '进阶', '高校慕课 · 电气类', '高电压技术 绝缘试验', '高压试验,绝缘,试验', '高压试验 L1→L2 缺口，系统补试验原理'],
  ['SF6 气体检测与微水试验作业演示', 'BILIBILI', '视频', '按视频', '高压试验', '入门', '技术区 · 现场实操', 'SF6 微水 检测', 'SF6,微水,气体检测', '实操报告暴露取样与读数细节不足'],
  ['电气设备状态检修与试验案例分析', 'WANFANG', '学术', '按需检索', '高压试验', '进阶', '学术文献 · 状态检修', '电气设备 状态检修', '状态检修,试验数据,案例', '用试验数据比对判断设备状态'],
  ['电力系统故障分析与录波图识读', 'ICOURSE163', '慕课', '按课程', '故障录波', '进阶', '高校慕课 · 电气类', '电力系统故障分析', '故障录波,故障分析,波形', '故障录波 L1→L2 缺口，补分析方法'],
  ['录波波形与开关变位识读入门', 'BILIBILI', '视频', '按视频', '故障录波', '入门', '技术区 · 二次回路', '故障录波 波形识读', '录波,波形,变位', '能读波形但不能独立归因，先练识读'],
  ['继电保护故障录波典型案例分析', 'CNKI', '学术', '按需检索', '故障录波', '进阶', '学术期刊 · 继电保护', '故障录波 案例分析', '录波,案例,论文', '典型录波案例，支撑录波 L2 判定'],
  ['电力安全生产法规与一票否决条款', 'CEC', '行业', '按需检索', '安全规程', '入门', '行业协会 · 安全政策', '电力安全 一票否决', '安全规程,一票否决,政策', '安全规程月度必修的政策出处'],
  ['有限空间作业安全与气体检测规定', 'SMARTEDU_VOC', '职教', '按课程', '安全规程', '入门', '国家级职教平台 · 安全类', '有限空间作业 气体检测', '有限空间,气体检测,通风', '电缆沟作业先通风检测后再进入'],
  ['电力事故案例与责任追溯专题', 'CNKI', '学术', '按需检索', '安全规程', '进阶', '学术期刊 · 电力安全', '电力 事故案例 责任追溯', '事故案例,责任,复盘', '班组安全学习与案例通报素材'],
  ['电气工程基础与电工原理补课', 'XUETANGX', '慕课', '按课程', '继电保护', '入门', '名校公开课 · 电气工程', '电气工程 电工基础', '电工,基础,入门', '基础薄弱时先补电工原理再上继保'],
  ['变电检修与高压试验作业安全', 'SMARTEDU_VOC', '职教', '按课程', '高压试验', '入门', '国家级职教平台 · 电力类', '变电检修 高压试验 安全', '高压试验,检修,安全', '试验作业安全措施与监护要求']
];
const demoExternalCourses = demoCourseRows.map((row, index) => {
  const platform = demoCourseSources.find((item) => item.code === row[1]) || {};
  return {
    id: index + 1, title: row[0], platform_code: row[1], platform: platform.name || row[1], site: platform.site || '',
    type: row[2], duration: row[3], skill: row[4], level: row[5], org: row[6], search_keyword: row[7],
    tags: row[8].split(','), match_reason: row[9],
    url: (platform.search_url || '').replace('{kw}', encodeURIComponent(row[7])),
    gap_match: ['继电保护', '高压试验', '故障录波'].includes(row[4])
  };
});
const demoHotCourseKeywords = ['继电保护 整定计算', '电力系统继电保护', '软压板 投退顺序', '高电压技术 绝缘试验', 'SF6 微水 检测', '故障录波 案例分析'];
const courseSkillOptions = ['继电保护', '倒闸操作', '高压试验', '故障录波', '安全规程'];
const courseLevelOptions = ['入门', '进阶', '精通'];

const courseSearchForm = ref({ keyword: '', platform: '', skill: '', level: '' });
const courseSearchResult = ref(null);
const courseSearchRunning = ref(false);
const courseSearchNote = ref('');
const courseSearchHistory = ref([]);
const courseSearchPlatforms = ref(demoCourseSources.map((item) => ({ ...item })));
const courseHotKeywords = computed(() => {
  const hot = courseSearchResult.value && courseSearchResult.value.hot_keywords;
  return hot && hot.length ? hot : demoHotCourseKeywords;
});

// 与后端同一套打分口径：标题 6 分、检索词 4 分、标签 / 技能 3 分、栏目 2 分、匹配理由 1 分。
const localCourseMatch = (item, terms) => {
  let score = 0;
  const hits = [];
  terms.forEach((term) => {
    let hit = '';
    if (item.title.toLowerCase().includes(term)) { score += 6; hit = '标题命中「' + term + '」'; }
    if (item.search_keyword.toLowerCase().includes(term)) { score += 4; hit = hit || '检索词命中「' + term + '」'; }
    if (item.tags.join(',').toLowerCase().includes(term)) { score += 3; hit = hit || '标签命中「' + term + '」'; }
    if (item.skill.toLowerCase().includes(term)) { score += 3; hit = hit || '技能命中「' + term + '」'; }
    if (item.org.toLowerCase().includes(term)) score += 2;
    if (item.match_reason.toLowerCase().includes(term)) { score += 1; hit = hit || '匹配理由命中「' + term + '」'; }
    if (hit) hits.push(hit);
  });
  return { score, hits };
};
const localCourseSearch = (form) => {
  const keyword = form.keyword.trim();
  const terms = keyword.toLowerCase().split(/[\s,，、]+/).filter(Boolean);
  const gapSkills = ['继电保护', '高压试验', '故障录波'];
  const external = demoExternalCourses
    .filter((item) => (!form.platform || item.platform_code === form.platform) && (!form.skill || item.skill === form.skill) && (!form.level || item.level === form.level))
    .map((item) => ({ ...item, ...localCourseMatch(item, terms), gap_match: gapSkills.includes(item.skill) }))
    .filter((item) => !terms.length || item.score > 0)
    .sort((left, right) => (right.score * 10 + (right.gap_match ? 5 : 0)) - (left.score * 10 + (left.gap_match ? 5 : 0)));
  const internal = terms.length
    ? demoResources
      .filter((item) => terms.some((term) => (item.title + item.match_reason + item.skill).toLowerCase().includes(term)))
      .map((item) => ({ id: 'resource-' + item.id, source: '推荐资源', title: item.title, type: item.type, duration: item.duration, skill: item.skill, level: item.level, origin: item.origin || '站内', site: item.site || '学习总版', jump: item.jump || 'learning', url: item.url || null }))
    : [];
  return {
    keyword, platform: form.platform, skill: form.skill, level: form.level, searched_at: '本地匹配', took_ms: 0,
    catalog_size: demoExternalCourses.length, external_total: external.length, external, internal,
    platforms: demoCourseSources
      .filter((item) => !form.platform || item.code === form.platform)
      .map((item) => ({ ...item, url: keyword ? item.search_url.replace('{kw}', encodeURIComponent(keyword)) : '' })),
    gap_skills: gapSkills, hot_keywords: demoHotCourseKeywords, checked_at: demoCourseSources[0].checked_at,
    platform_ok: demoCourseSources.filter((item) => item.http_code === 200).length, platform_total: demoCourseSources.length,
    note: '未连上后端 API（8080）：下面是同一份外网课程库的本地匹配结果，平台直达链接照常打开。'
  };
};
const runCourseSearch = async () => {
  if (courseSearchRunning.value) return;
  const form = courseSearchForm.value;
  const keyword = form.keyword.trim();
  if (!keyword && !form.platform && !form.skill && !form.level) {
    courseSearchNote.value = '先填关键词，或选一个平台 / 技能 / 等级再检索。';
    return;
  }
  courseSearchRunning.value = true;
  courseSearchNote.value = '';
  const params = new URLSearchParams();
  if (keyword) params.set('q', keyword);
  if (form.platform) params.set('platform', form.platform);
  if (form.skill) params.set('skill', form.skill);
  if (form.level) params.set('level', form.level);
  const payload = await getData('/personal/course-search?' + params.toString(), null);
  courseSearchResult.value = payload || localCourseSearch(form);
  // 下拉里的平台以后端返回的为准（新增平台后不用改前端），带平台筛选时只更新当前平台，避免把下拉缩小成一个选项
  if (payload && payload.platforms && payload.platforms.length && !form.platform) {
    courseSearchPlatforms.value = payload.platforms.map((item) => ({ ...item }));
  }
  courseSearchNote.value = payload ? '' : '后端接口没返回：本次显示的是课程库本地匹配结果，启动后端（8080）后还能看到平台核验状态。';
  if (keyword) {
    courseSearchHistory.value = [keyword, ...courseSearchHistory.value.filter((item) => item !== keyword)].slice(0, 4);
  }
  courseSearchRunning.value = false;
};
const applyHotKeyword = (word) => {
  courseSearchForm.value.keyword = word;
  runCourseSearch();
};
const resetCourseSearch = () => {
  courseSearchResult.value = null;
  courseSearchNote.value = '';
};

// 练习题：Agent 按“技能缺口权重 × 历史正确率”抽题，答错写入记忆库
const practice = ref(null);
const practiceSession = ref('');
const practiceQuestions = ref([]);
const practiceAnswers = ref({});
const practiceResult = ref(null);
const practiceAgent = ref(null);
const practiceRunning = ref(false);
const practiceError = ref('');
const practiceCount = ref(5);
const practiceSkill = ref('');
// 练习全程在弹窗内完成：先作答，交卷后同一个弹窗直接切成解析视图
const practiceSubmitted = ref(false);
const practiceDialog = ref({ visible: false, mode: 'quiz' });
const practiceSkills = computed(() => (practice.value && practice.value.by_skill) || []);
const practicePlan = computed(() => (practiceAgent.value && practiceAgent.value.plan) || []);
const practiceAnswered = computed(() => ((practice.value && practice.value.my_accuracy) || []).reduce((sum, row) => sum + row.answered, 0));
const practiceRate = computed(() => {
  const rows = (practice.value && practice.value.my_accuracy) || [];
  const answered = rows.reduce((sum, row) => sum + row.answered, 0);
  const correct = rows.reduce((sum, row) => sum + row.correct, 0);
  return answered ? Math.round((correct * 100) / answered) : 0;
});
const sopQuestionCount = computed(() => ((practice.value && practice.value.team_sources) || []).reduce((sum, row) => sum + row.count, 0));

// 考试作答（考试模式）：只有管理员统一开考（can_enter=true）后才发卷；整屏作答页 + 答题卡 + 倒计时，交卷后同页切成成绩与逐题解析
const examRoom = ref({ visible: false, mode: 'quiz' });
const examSession = ref(null);
const examQuestions = ref([]);
const examAnswers = ref({});
const examResult = ref(null);
const examRunning = ref(false);
const examError = ref('');
const examApiDown = ref(false);
const examDeadline = ref(0);
const examDeadlines = ref({});
const examNow = ref(Date.now());
let examTimer = null;
const examAnswered = computed(() => Object.values(examAnswers.value).filter((item) => item).length);
const examRemainingMs = computed(() => (examRoom.value.mode === 'quiz' && examDeadline.value ? Math.max(0, examDeadline.value - examNow.value) : 0));
const examRemaining = computed(() => {
  const total = Math.floor(examRemainingMs.value / 1000);
  return String(Math.floor(total / 60)).padStart(2, '0') + ':' + String(total % 60).padStart(2, '0');
});
const stopExamTimer = () => { if (examTimer) { clearInterval(examTimer); examTimer = null; } };
const answeredCount = computed(() => Object.values(practiceAnswers.value).filter((item) => item).length);
const questionCountOf = (skill) => {
  const row = practiceSkills.value.find((item) => item.skill === skill);
  return row ? row.count : 0;
};
// 站内资源「去对应板块」：目标就是当前页时也要给出可见反馈，否则看起来像“点了没反应”
const resourceJumpLabels = { learning: '学习与考试', tasks: '实操任务', advice: '差距与建议', skills: '技能雷达' };
const goResourceBoard = async (item) => {
  const navKeys = (NAV_BY_ROLE[currentUser.value.role] || EMPLOYEE_NAV).map((row) => row.key);
  let target = item.jump || 'learning';
  if (!navKeys.includes(target)) target = 'learning';
  const label = resourceJumpLabels[target] || target;
  if (active.value === target) {
    // 已经在目标板块：切回该板块的概要子页签并把内容滚回顶部，配合提示让用户知道点到了
    if (target === 'learning') learningTab.value = 'summary';
    await scrollMainTop();
    ElMessage.info('当前就在「' + label + '」板块，已定位到板块顶部');
    return;
  }
  active.value = target;
  ElMessage.success('已跳转到「' + label + '」板块');
};
const loadPractice = async () => { practice.value = await getData('/personal/practice/overview', null); };
// 弹窗在“作答 / 解析”之间切换时把内容滚回顶部，保证先看到得分与第一题
const scrollPracticeDialogTop = async () => { await nextTick(); const body = document.querySelector('.practice-dialog .el-dialog__body'); if (body) body.scrollTop = 0; };
// 内容区是独立滚动容器：切换板块或子页签时回到顶部，避免沿用上一页的滚动位置
const scrollMainTop = async () => { await nextTick(); const main = document.querySelector('main'); if (main) main.scrollTop = 0; };
watch([active, learningTab], scrollMainTop);
const openPracticeQuiz = async () => { practiceDialog.value = { visible: true, mode: 'quiz' }; await scrollPracticeDialogTop(); };
const openPracticeResult = async () => { if (practiceResult.value) { practiceDialog.value = { visible: true, mode: 'result' }; await scrollPracticeDialogTop(); } };
const drawPractice = async (skill) => {
  practiceRunning.value = true;
  practiceError.value = '';
  practiceSubmitted.value = false;
  practiceQuestions.value = [];
  practiceAnswers.value = {};
  try {
    const data = await postData('/personal/practice/draw', {
      skill: skill || practiceSkill.value || null,
      count: practiceCount.value
    }, null);
    if (!data || !(data.questions || []).length) {
      practiceError.value = '抽题失败：题库中没有符合条件的题目，或后端服务未启动（8080）。';
      return;
    }
    practiceQuestions.value = data.questions;
    practiceSession.value = data.session_id;
    practiceAgent.value = data.agent;
    learningTab.value = 'practice';
    openPracticeQuiz();
    await loadPractice();
  } finally {
    practiceRunning.value = false;
  }
};
const submitPractice = async () => {
  if (!practiceQuestions.value.length) return;
  practiceRunning.value = true;
  practiceError.value = '';
  try {
    const data = await postData('/personal/practice/submit', { session_id: practiceSession.value, answers: practiceAnswers.value }, null);
    if (!data) {
      practiceError.value = '交卷失败：练习会话已过期或后端服务未启动（8080），请重新抽题。';
      return;
    }
    practiceResult.value = data;
    practiceSubmitted.value = true;
    practiceDialog.value = { visible: true, mode: 'result' };
    await scrollPracticeDialogTop();
    await loadPractice();
  } finally {
    practiceRunning.value = false;
  }
};

const examStats = computed(() => {
  const list = exams.value;
  const scores = list.filter((item) => typeof item.score === 'number').map((item) => item.score);
  return {
    open: list.filter((item) => examCanEnter(item)).length,
    pending: list.filter((item) => item.status === 'PENDING').length,
    retake: list.filter((item) => item.status === 'FAILED').length,
    passed: list.filter((item) => item.status === 'PASSED').length,
    avg: scores.length ? Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length) : 0
  };
});
// 能否进入答题：后端新版返回 can_enter；接口较旧时按「是否开考 + 本轮是否已交卷」兜底推导，
// 保证管理员统一点「开始考试」后，员工端一定出现可点的「进入考试」按钮
const examOpen = (item) => {
  if (!item) return false;
  if (typeof item.open === 'boolean') return item.open;
  if (item.gate_status === 'IN_PROGRESS' || item.gate_status === 'SUBMITTED') return true;
  return item.status === 'IN_PROGRESS';
};
const examCanEnter = (item) => {
  if (!item) return false;
  if (typeof item.can_enter === 'boolean') return item.can_enter;
  return examOpen(item) && !item.round_submitted;
};
const examGateText = (item) => (examCanEnter(item) ? '管理员已统一开考，可进入答题' : (item && item.round_submitted ? '本场已交卷' : '等待管理员统一开考'));
const openExamList = computed(() => exams.value.filter((item) => examCanEnter(item)));
const lastExamGap = computed(() => Math.max(0, (learningSummary.value.last_exam_pass_score || 0) - (learningSummary.value.last_exam_score || 0)));
const examTag = (item) => ({ PASSED: 'success', FAILED: 'danger', IN_PROGRESS: 'warning' }[item.status] || 'info');
const examStatus = (item) => ({ PASSED: '已通过', FAILED: '未通过', IN_PROGRESS: '进行中', PENDING: '待考' }[item.status] || item.status);
const openExamDialog = (title, subtitle, rows, item = null) => { examDialog.value = { visible: true, title, subtitle, rows, item }; };
const formatStamp = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 19).replace('T', ' ');
  const pad = (part) => String(part).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
};
const loadExams = async () => {
  const data = await getData('/personal/exams', null);
  if (data && data.items && data.items.length) {
    exams.value = data.items;
    examSummary.value = data.summary || examSummary.value;
  }
  examApiDown.value = !data;
  return data;
};
// 管理员在另一台设备开考后，员工这边要能自动看到：进入「考试中心」立即刷新，停留期间每 10 秒同步一次
let examPoll = null;
const stopExamPoll = () => { if (examPoll) { clearInterval(examPoll); examPoll = null; } };
watch([active, learningTab], ([page, tab]) => {
  stopExamPoll();
  if (page === 'learning' && tab === 'exams') {
    loadExams();
    examPoll = setInterval(loadExams, 10000);
  }
});

// 弹窗在“作答 / 解析”之间切换时把内容滚回顶部，保证先看到计时与第一题
const scrollExamDialogTop = async () => { await nextTick(); const body = document.querySelector('.exam-dialog .el-dialog__body'); if (body) body.scrollTop = 0; };
// 同一场考试离开后再进入时沿用同一截止时间，避免“稍后再答”等于重置计时
const startExamTimer = (examId, minutes) => {
  stopExamTimer();
  if (!examDeadlines.value[examId]) {
    examDeadlines.value[examId] = Date.now() + Math.max(1, Number(minutes) || 30) * 60 * 1000;
  }
  examDeadline.value = examDeadlines.value[examId];
  examNow.value = Date.now();
  examTimer = setInterval(() => {
    examNow.value = Date.now();
    if (examRemainingMs.value <= 0) { stopExamTimer(); submitExam('timeup'); }
  }, 1000);
};
const closeExamRoom = () => { stopExamTimer(); examRoom.value = { ...examRoom.value, visible: false }; };
// 答题卡：点题号跳到对应题目，交卷前先看清还有哪些题没答
const examUnanswered = computed(() => examQuestions.value.filter((q) => !examAnswers.value[q.id]).length);
const focusExamQuestion = async (id) => {
  await nextTick();
  const node = document.getElementById('exam-q-' + id);
  if (node) node.scrollIntoView({ behavior: 'smooth', block: 'start' });
};

// 进入考试：先向后端要卷。未由管理员统一开考时后端返回 gate=NOT_OPEN 并拒绝发卷，员工无法进入考试模式
const startExam = async (item) => {
  if (!item) return;
  examRunning.value = true;
  examError.value = '';
  try {
    const session = await postData(`/exams/${item.exam_id}/start`, null, null);
    if (!session) {
      examError.value = '进入考试失败：后端没有响应（8080）。请先启动后端 API 再进入考试；若后端是旧版本，请在 backend 目录重新构建并重启。';
      return;
    }
    if (session.opened === undefined) {
      examError.value = '进入考试失败：后端发卷接口未生效（接口版本过旧），请在 backend 目录重新构建并重启后端服务后重试。';
      return;
    }
    if (!session.opened) {
      await loadExams();
      openExamDialog(item.name, '暂不能进入答题', [
        ['状态', session.gate === 'SUBMITTED' ? '本场已交卷' : '等待管理员统一开考'],
        ['说明', session.message || '管理员尚未统一开考，请等开考通知后再进入。'],
        ['合格线', `${item.pass_score} 分`]
      ], item);
      return;
    }
    examSession.value = session;
    examQuestions.value = session.questions || [];
    examAnswers.value = {};
    examResult.value = null;
    examRoom.value = { visible: true, mode: 'quiz' };
    startExamTimer(session.exam_id, session.duration_minutes);
    await scrollExamDialogTop();
  } finally {
    examRunning.value = false;
  }
};

// 交卷：后端判分并返回逐题解析，同时写入考试记忆；手动交卷且仍有未作答题目时先确认一次
const submitExam = async (reason, confirmed = false) => {
  if (!examSession.value || examResult.value) return;
  if (reason === 'manual' && !confirmed && examUnanswered.value > 0) {
    try {
      await ElMessageBox.confirm(`还有 ${examUnanswered.value} 题未作答，交卷后不能再修改。确认交卷？`, '确认交卷', {
        type: 'warning', confirmButtonText: '确认交卷', cancelButtonText: '再检查一下'
      });
    } catch (error) {
      return;
    }
  }
  stopExamTimer();
  examRunning.value = true;
  examError.value = '';
  try {
    const data = await postData(`/exams/${examSession.value.exam_id}/submit`, { answers: examAnswers.value }, null);
    if (!data || !data.submitted) {
      examError.value = (data && data.message) || '交卷失败：后端服务未启动（8080）或答题会话已过期，请重新进入考试。';
      return;
    }
    examResult.value = data;
    delete examDeadlines.value[examSession.value.exam_id];
    examRoom.value = { visible: true, mode: 'result' };
    if (reason === 'timeup') ElMessage.warning('已到考试时限，系统自动交卷');
    await scrollExamDialogTop();
    await loadExams();
  } finally {
    examRunning.value = false;
  }
};

const showExamDetail = (item) => {
  const rows = [];
  if (item.score != null) {
    rows.push(['上次成绩', `${item.score} 分（合格线 ${item.pass_score} 分）`]);
    rows.push(['考试时间', formatStamp(item.occurred_at)]);
  }
  rows.push(['本场状态', examGateText(item)]);
  rows.push(['考试时长', `${item.duration_minutes} 分钟`]);
  rows.push(['题量', `${item.question_count} 题`]);
  rows.push(['合格线', `${item.pass_score} 分`]);
  openExamDialog(item.name, item.status_note, rows, item);
};const exportRecords = () => {
  const rows = growthEvents.value.map((item, index) => [index + 1, item.title, item.note, item.badge]);
  const cell = (value) => `"${String(value).replace(/"/g, '""')}"`;
  const csv = ['序号,事件,详情,结论', ...rows.map((row) => row.map(cell).join(','))].join('\r\n');
  const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `成长轨迹-${formatStamp(new Date()).slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
};

const templateSections = computed(() => reportTemplate.value.sections ?? []);
const templateFields = computed(() => templateSections.value.flatMap((section) => section.fields ?? []));
const gasRules = computed(() => reportTemplate.value.gas_rules ?? []);
const fieldOf = (name) => templateFields.value.find((field) => field.name === name)
  ?? { name, label: name, required: false, example: '', hint: '' };
const selectedGas = computed(() => gasRules.value.find((rule) => rule.code === reportForm.value.gas_type) ?? null);
const formAbnormal = computed(() => {
  const gas = selectedGas.value;
  const form = reportForm.value;
  if (!gas || form.gas_value == null || form.threshold == null) return false;
  return 'LOW' === String(gas.direction).toUpperCase() ? form.gas_value < form.threshold : form.gas_value > form.threshold;
});
const phenomenonLength = computed(() => reportForm.value.phenomenon.trim().length);
const phenomenonHasNumber = computed(() => /[0-9０-９]/.test(reportForm.value.phenomenon));
// SOP 执行情况：三态而不是「是 / 否」——「本次没有对应 SOP」和「没填」都不是「未按 SOP」
const sopOptions = [
  { value: 'FOLLOWED', label: '已按 SOP 执行', hint: '按对应作业指导书的步骤与顺序执行' },
  { value: 'DEVIATED', label: '未按 SOP 执行', hint: '有步骤没按规程做，必须写明偏差' },
  { value: 'NOT_APPLICABLE', label: '本次无对应 SOP', hint: '该任务没有可对应的作业指导书' }
];
const sopLabel = (status) => (sopOptions.find((option) => option.value === status) || {}).label
  || (status ? status : '未填报（字段上线前的历史报告）');
const sopDeviationRequired = computed(() => reportForm.value.sop_status === 'DEVIATED');
const taskMetrics = computed(() => {
  const pending = taskList.value.filter((task) => !task.report_id).length;
  return {
    pending,
    submitted: taskList.value.length - pending,
    abnormal: reportList.value.filter((report) => report.judgment === '超限').length,
    needConfirm: reportList.value.filter((report) => report.analysis && report.analysis.need_human_confirm).length
  };
});
const taskTag = (task) => (task.report_id ? 'success' : task.status === '进行中' ? 'warning' : 'info');
const reportSourceTag = (report) => (report.analysis && report.analysis.source === 'ai' ? 'success' : 'info');
const reportSourceLabel = (report) => (report.analysis ? report.analysis.source_label || (['model', 'ai'].includes(report.analysis.source) ? 'AI 大模型' : '内置规则引擎 v1') : '未分析');
const reportPreviewSections = computed(() => {
  const report = activeReport.value;
  if (!report) return [];
  return [
    { title: '一、基础信息', rows: [
      ['报告编号', report.report_id], ['任务名称', report.task_title], ['检测时间', report.detected_at],
      ['班次', report.shift], ['检测地点', report.location],
      ['填报人', report.reporter + (report.reporter_position ? ' · ' + report.reporter_position : '')]
    ] },
    { title: '二、检测数据', rows: [
      ['气体类型', report.gas_label + '（' + report.gas_type + '）'],
      ['检测数值', report.gas_value + ' ' + report.unit], ['报警阈值', report.threshold + ' ' + report.unit],
      ['报警方向', report.direction === 'LOW' ? '低于阈值报警' : '高于阈值报警'],
      ['判定结论', report.judgment + '（严重度：' + report.severity + '）']
    ] },
    { title: '三、异常现象描述', rows: [
      ['异常现象描述', report.phenomenon], ['已采取措施', report.measures || '无']
    ] },
    { title: '四、SOP 执行情况', rows: [
      ['SOP 执行情况', sopLabel(report.sop_status)],
      ...(report.sop_deviation ? [['SOP 偏差说明', report.sop_deviation]] : [])
    ] },
    { title: '五、文档与签字', rows: [
      ['生成文档', 'PDF / Word（同一套框格模型渲染）'],
      ['签字框格', (reportTemplate.value.sign_boxes ?? []).join(' · ')]
    ] }
  ];
});
const openReportForm = (task, member = '') => {
  if (!task) return;
  reportFormTask.value = task;
  reportForm.value = emptyReportForm();
  reportForm.value.member = member;
  reportForm.value.shift = shiftOptions[0];
  reportForm.value.detected_at = formatStamp(new Date()).slice(0, 16);
  reportFormErrors.value = {};
  reportFormVisible.value = true;
};
// 台账「缺报」行的去补交：跳到实操任务并打开该任务的填报弹窗，执行组员预填为这位组员
const startRefill = (row) => {
  if (!row || row.task_id == null) return;
  active.value = 'tasks';
  openReportForm({ id: row.task_id, title: row.task_title }, row.member || '');
};
const onGasChange = (code) => {
  const gas = gasRules.value.find((rule) => rule.code === code);
  if (gas) reportForm.value.threshold = Number(gas.threshold);
};
const resetThreshold = () => onGasChange(reportForm.value.gas_type);
const insertPhenomenonExample = () => { reportForm.value.phenomenon = fieldOf('phenomenon').example || ''; };
const insertMeasuresExample = () => { reportForm.value.measures = fieldOf('measures').example || ''; };
const validateReportForm = () => {
  const errors = {};
  const form = reportForm.value;
  if (!form.detected_at) errors.detected_at = '检测时间不能为空';
  if (!form.shift) errors.shift = '班次不能为空';
  if ((form.location || '').trim().length < 4) errors.location = '检测地点需 4-120 字，需写到站所与设备间隔';
  if (!form.gas_type) errors.gas_type = '气体类型不能为空';
  if ((form.member || '').length > 32) errors.member = '执行组员姓名最长 32 字';
  if (form.gas_value == null) errors.gas_value = '检测数值不能为空';
  else if (form.gas_value < 0) errors.gas_value = '检测数值不能为负数';
  if (form.threshold == null) errors.threshold = '报警阈值不能为空';
  else if (form.threshold < 0) errors.threshold = '报警阈值不能为负数';
  const phenomenon = (form.phenomenon || '').trim();
  if (!phenomenon) errors.phenomenon = '异常现象描述不能为空';
  else if (phenomenon.length < 15 || phenomenon.length > 300) errors.phenomenon = '异常现象描述需 15-300 字，按“时间 + 位置 + 现象 + 数值 + 已采取措施”填写';
  else if (!/[0-9０-９]/.test(phenomenon)) errors.phenomenon = '异常现象描述需包含具体时间或数值，例如 09:20、0.35MPa、1250ppm';
  if ((form.measures || '').length > 200) errors.measures = '已采取措施不超过 200 字';
  const deviation = (form.sop_deviation || '').trim();
  if (!form.sop_status) errors.sop_status = '请选择 SOP 执行情况：已按 SOP 执行 / 未按 SOP 执行 / 本次无对应 SOP';
  else if (form.sop_status === 'DEVIATED' && !deviation) errors.sop_deviation = '选「未按 SOP 执行」时必须填写偏差说明，写清哪一步没按规程做';
  else if (deviation.length > 200) errors.sop_deviation = 'SOP 偏差说明不超过 200 字';
  reportFormErrors.value = errors;
  return Object.keys(errors).length === 0;
};
const submitReport = async () => {
  if (!reportFormTask.value) return;
  if (!validateReportForm()) { ElMessage.warning('请按模板框格要求补全必填项后再提交'); return; }
  reportFormRunning.value = true;
  try {
    const response = await api.post('/tasks/' + reportFormTask.value.id + '/submit-report', reportForm.value);
    const body = response.data;
    if (body.code !== 0) {
      reportFormErrors.value = (body.data && body.data.field_errors) || {};
      ElMessage.error(body.message || '提交失败，请检查表单');
      return;
    }
    const report = body.data;
    reportList.value = [report, ...reportList.value.filter((item) => item.report_id !== report.report_id)];
    taskList.value = taskList.value.map((task) => (task.id === report.task_id
      ? { ...task, report_id: report.report_id, report_status: 'SUBMITTED', judgment: report.judgment, severity: report.severity, status: '已完成' } : task));
    reportFormVisible.value = false;
    activeReport.value = report;
    reportDialogVisible.value = true;
    ElMessage.success('报告 ' + report.report_id + ' 已生成，PDF / Word 可下载');
  } catch (error) {
    ElMessage.error('提交失败，请确认后端服务已启动');
  } finally {
    reportFormRunning.value = false;
  }
};
const downloadDocument = async (report, format) => {
  if (!report) return;
  const url = format === 'docx' ? report.document_docx : report.document_pdf;
  if (!url) { ElMessage.warning('该报告暂无可用文档，请重新提交生成'); return; }
  try {
    await downloadFile(url, report.report_id + (format === 'docx' ? '.docx' : '.pdf'));
  } catch (error) {
    ElMessage.error('文档下载失败：该报告没有可用的归档文档，请重新提交生成');
  }
};
const openReportView = (report) => { if (!report) return; activeReport.value = report; reportDialogVisible.value = true; };
const openReportViewById = (reportId) => openReportView(reportList.value.find((item) => item.report_id === reportId) ?? null);
const analyzeReport = async () => {
  const report = activeReport.value;
  if (!report) return;
  reportDialogRunning.value = true;
  try {
    const response = await api.post('/reports/' + report.report_id + '/analyze');
    if (response.data.code === 0) {
      const updated = response.data.data;
      activeReport.value = updated;
      reportList.value = reportList.value.map((item) => (item.report_id === updated.report_id ? updated : item));
      taskList.value = taskList.value.map((task) => (task.id === updated.task_id ? { ...task, judgment: updated.judgment, severity: updated.severity } : task));
      ElMessage.success('已重新执行 AI 归因分析');
    } else {
      ElMessage.error(response.data.message || '分析失败');
    }
  } catch (error) {
    ElMessage.error('分析失败，请确认后端服务已启动');
  } finally {
    reportDialogRunning.value = false;
  }
};

const pageCopy = computed(() => {
  const name = currentUser.value.display_name || '同事';
  switch (active.value) {
    case 'skills':
      return { title: '技能雷达', subtitle: '当前技能等级 vs 岗位要求 vs 公司未来需求：继保 L1→L3 差 2 级，倒闸 L3 已达标，高压试验 L1→L2 待补。' };
    case 'selfPortrait':
      return { title: '个人自画像', subtitle: '职业发展画像：基本信息、职业目标、发展意愿、师傅与协作评价、岗位匹配度。' };
    case 'abilities':
      return { title: '个人能力', subtitle: '硬技能、软技能、安全能力、实操能力、考试能力与证书能力。' };
    case 'memories':
      return { title: '记忆展示', subtitle: '能力记忆库：学习、错误、实操、考试、安全、带教、复盘记忆按时间线留存。' };
    case 'growth':
      return { title: '成长轨迹', subtitle: '技能等级、证书、考试、任务、培训、安全记录与晋升准备度。' };
    case 'advice':
      return { title: '差距与建议', subtitle: '个人学习 Agent：汇总欠缺，给出课程、带教、模拟考计划与复合型人才建议。' };
    case 'team':
      return { title: '班组报告', subtitle: '每次实操活动一份检测报告，缺报会自动进入公司运行诊断的输入。' };
    case 'company':
      return { title: '人才驾驶舱', subtitle: '全公司人才总览：关键指标、人才缺口、培训成本、用人成本、安全风险与离职风险。' };
    case 'skillMatrix':
      return { title: '全公司技能矩阵', subtitle: '按部门、岗位、技能等级看全公司人才分布：谁强谁弱，关键岗位是否有备份。' };
    case 'training':
      return { title: '培训看板', subtitle: '培训完成率、培训成本、培训效果、ROI、部门对比与个人学习计划执行情况。' };
    case 'diagnosis':
      return { title: '运行诊断 Agent', subtitle: '结合员工学习、证书、技能与组长报告，判定人才缺失还是技能不足，并给出降本增效措施。' };
    case 'adminIam':
      return { title: '用户与权限', subtitle: '维护用户、角色、组织、岗位与权限；平台数据规模与员工档案同页查看。' };
    case 'adminContent':
      return { title: '技能与课程', subtitle: '技能字典、岗位技能要求（平台维护）、课程与题库；上传资料由 Agent 识别后经管理员审核入库。' };
    case 'adminExam':
      return { title: '考试配置', subtitle: '组卷规则、防作弊、评分规则与及格线；管理员统一开考并发放试卷。' };

    case 'adminAudit':
      return { title: '审计与审核', subtitle: '登录、修改、审批、决策、执行、回滚全留痕；支持关键词搜索、类别筛选、清除筛选与清除留痕。' };
    case 'learning':
      return { title: '学习与考试', subtitle: '学习总版与考试中心：计划、记录、资源与考试状态，缺口驱动的学习闭环。' };
    case 'twin':
      return { title: '110kV 城东变电站 · 三维数字孪生园区', subtitle: '拖拽环绕视角，点击任意设备查看台账与结构拆解；左 H 面板可切换巡检、演练与教学模式。' };
    case 'tasks':
      return canFillReport.value
        ? { title: '实操任务与报告', subtitle: '你负责填报班组检测报告：按框格填数据与异常现象，提交后自动生成 PDF/Word 并执行 AI 归因。' }
        : { title: '实操任务与报告', subtitle: '值班员负责现场检测与查看报告；检测报告由班组长统一填报，你这边只能查看与下载。' };
    default:
      return { title: '我的总览', subtitle: `欢迎回来，${name}。这里是你的成长快照与当前待办。` };
  }
});

/* 登录：账号 + 口令（LoginStage 表单校验与验证码通过后触发）。
   成功后签发的令牌存进请求头，失败时把后端信息回显到登录卡。 */
const login = async (credentials) => {
  loggingIn.value = true;
  try {
    const response = await api.post('/auth/login', { username: credentials.username, password: credentials.password });
    const result = response.data.data;
    const user = demoUsers.find((item) => item.username === credentials.username);
    // 令牌由后端签发，后续请求靠它认证；界面展示仍用 user 里的字段
    currentUser.value = { ...user, ...result.user, token: result.token };
    setApiUser(currentUser.value);
    loggedIn.value = true;
    active.value = LANDING_BY_ROLE[currentUser.value.role] || 'skills';
    loginError.value = '';
    await load();
  } catch (error) {
    const message = error.response && error.response.data && error.response.data.message;
    loginError.value = message || '登录失败，请确认后端服务已启动。';
  } finally {
    loggingIn.value = false;
  }
};
const logout = async () => {
  await api.post('/auth/logout').catch(() => undefined);
  loggedIn.value = false;
  currentUser.value = { username: '', display_name: '', role: '', position: '' };
  setApiUser(null);
  active.value = 'skills';
};
const load = async () => {
  // 个人画像只有员工与组长（组长本人也是员工）能取；老总与管理员不加载个人数据
  if (!['EMPLOYEE', 'TEAM_LEAD'].includes(currentUser.value.role)) return;
  const [p, s, g, t, summary, plan, records, resourceList, examList, certificateList, taskTemplate, reportRows, latestDiagnosis, practiceOverview] = await Promise.all([
    getData('/personal/profile', null), getData('/personal/skill-radar', []), getData('/personal/gaps', []), getData('/personal/tasks', []),
    getData('/personal/learning-summary', null), getData('/personal/learning-plan', []), getData('/personal/learning-records', []), getData('/personal/resources', []), getData('/personal/exams', null), getData('/personal/certificates', []),
    canFillReport.value ? getData('/tasks/1/report-template', null) : null, getData('/reports', []),
    getData('/personal/agent-diagnose/latest', null), getData('/personal/practice/overview', null)
  ]);
  if (p) profile.value = p;
  if (s.length) skills.value = s;
  if (g.length) gaps.value = g;
  if (t.length) { tasks.value = t; taskList.value = t; }
  if (taskTemplate) reportTemplate.value = taskTemplate;
  if (reportRows.length) reportList.value = reportRows;
  if (summary) learningSummary.value = summary;
  if (plan.length) learningPlan.value = plan;
  if (records.length) learningRecords.value = records;
  if (resourceList.length) resources.value = resourceList;
  if (examList && examList.items && examList.items.length) { exams.value = examList.items; examSummary.value = examList.summary || examSummary.value; }
  if (certificateList.length) certificates.value = certificateList;
  if (latestDiagnosis) agentDiagnosis.value = latestDiagnosis;
  if (practiceOverview) practice.value = practiceOverview;
};
</script>
<template>
  <div v-if="!loggedIn" class="login-host">
    <LoginStage :error="loginError" :loading="loggingIn" @submit="login" />
  </div>

  <div v-else class="app-shell" :class="[shellClass, { 'shell-twin': active === 'twin' }]">
    <aside>
      <div class="brand-mark"><span class="brand-logo" role="img" aria-label="工业智训"></span></div>
      <div class="brand">工业智训</div>
      <div class="brand-sub">INDUSTRIAL INTELLIGENT TRAINING</div>
      <div class="role-badge"><i></i><span>{{ roleTheme.view }}</span><small>{{ roleTheme.scope }}</small></div>
      <nav>
        <button v-for="item in navItems" :key="item.key" :class="{ active: active === item.key }" @click="active = item.key"><span>{{ item.icon }}</span>{{ item.label }}</button>
      </nav>
      <div class="user-mini">
        <div class="avatar">{{ currentUser.display_name.slice(0, 1) }}</div>
        <div><b>{{ currentUser.display_name }}</b><small>{{ currentUser.position }}</small></div>
      </div>
    </aside>

    <main>
      <header>
        <div>
          <div class="greeting-row">
            <p class="greeting">Hello，欢迎回来，<b>{{ currentUser.display_name }}</b></p>
            <span class="eyebrow">2026 · 变电运维中心</span>
          </div>
          <h1>{{ pageCopy.title }}</h1>
          <p class="welcome">{{ pageCopy.subtitle }}</p>
          <p class="role-hint">{{ roleTheme.hint }}</p>
        </div>
        <div class="header-tools">
          <div class="tool-cluster">
            <button class="tool-button theme-button" :title="theme === 'day' ? '切换黑夜模式' : '切换白天模式'" aria-label="切换昼夜主题" @click="toggleTheme">
              <svg v-if="theme === 'day'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z" />
              </svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="4" />
                <path d="M12 2.8v2.4M12 18.8v2.4M2.8 12h2.4M18.8 12h2.4M5.5 5.5l1.7 1.7M16.8 16.8l1.7 1.7M18.5 5.5l-1.7 1.7M7.2 16.8l-1.7 1.7" />
              </svg>
            </button>
            <div class="tool-popover">
              <button
                class="tool-button notification-button"
                :class="{ active: notifyOpen }"
                title="通知"
                aria-label="通知"
                :aria-expanded="notifyOpen ? 'true' : 'false'"
                @click="notifyOpen = !notifyOpen"
                @keydown.esc="notifyOpen = false"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M12 3.6a5.6 5.6 0 0 0-5.6 5.6v3.3c0 .8-.3 1.5-.8 2.1l-1.2 1.5c-.4.6 0 1.5.8 1.5h13.6c.8 0 1.2-.9.8-1.5l-1.2-1.5c-.5-.6-.8-1.3-.8-2.1V9.2A5.6 5.6 0 0 0 12 3.6Z" />
                  <path d="M9.7 17.6a2.3 2.3 0 0 0 4.6 0" />
                </svg>
              </button>
              <div v-if="notifyOpen" class="tool-popover-scrim" @click="notifyOpen = false"></div>
              <div v-if="notifyOpen" class="tool-popover-panel">
                <b>通知</b>
                <p>当前没有新的提醒，开考与待办有更新时会在这里提示。</p>
              </div>
            </div>
            <button class="tool-button logout-button" title="退出登录" aria-label="退出登录" @click="logout">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M13.2 4.8h2.6a1.8 1.8 0 0 1 1.8 1.8v10.8a1.8 1.8 0 0 1-1.8 1.8h-2.6" />
                <path d="M4.8 12h8.4" />
                <path d="M10 8.8 13.2 12 10 15.2" />
              </svg>
            </button>
          </div>
          <span class="role-chip">
            <i class="role-chip-avatar">{{ currentUser.display_name.slice(0, 1) }}</i>
            <span class="role-chip-body">
              <b>{{ currentUser.roleName || roleTheme.view }}</b>
              <small>{{ currentUser.team || roleTheme.scope }}</small>
            </span>
          </span>
        </div>
      </header>

      <section v-if="active === 'learning'" class="learning-page">
        <div class="sub-tabs">
          <button :class="{ active: learningTab === 'summary' }" @click="learningTab = 'summary'">学习总版</button>
          <button :class="{ active: learningTab === 'exams' }" @click="learningTab = 'exams'">考试中心</button>
          <button :class="{ active: learningTab === 'practice' }" @click="learningTab = 'practice'">练习题</button>
        </div>

        <template v-if="learningTab === 'summary'">
          <div class="metrics four-metrics">
            <div class="metric panel readiness-card">
              <small>本月学习</small>
              <div class="metric-value"><b>{{ learningSummary.month_hours }}</b><em>/ {{ learningSummary.target_hours }} 小时</em></div>
              <span class="good">完成率 {{ learningSummary.completion }}%</span>
            </div>
            <div class="metric panel">
              <small>必修完成</small>
              <div class="metric-value"><b>{{ learningSummary.required_done }}</b><em>/ {{ learningSummary.required_total }} 门</em></div>
              <span class="warn">还差 {{ learningSummary.required_total - learningSummary.required_done }} 门</span>
            </div>
            <div class="metric panel">
              <small>连续学习</small>
              <div class="metric-value"><b>{{ learningSummary.streak_days }}</b><em>天</em></div>
              <span class="good">师傅带教 {{ learningSummary.mentor_sessions }} 次</span>
            </div>
            <div class="metric panel">
              <small>最近考试</small>
              <div class="metric-value"><b class="warn">{{ learningSummary.last_exam_score }}</b><em>分</em></div>
              <span class="warn">低于合格线 {{ lastExamGap }} 分</span>
            </div>
          </div>

          <div class="panel wide">
            <div class="panel-title">
              <div><h2>学习计划</h2><small class="chart-caption">按技能缺口生成，优先补齐 {{ learningSummary.focus_skill }}</small></div>
              <button class="action-button" @click="learningTab = 'exams'">去考试中心 →</button>
            </div>
            <div class="plan-row" v-for="item in learningPlan" :key="item.course_code">
              <div class="row-main">
                <b>{{ item.course_name }}</b>
                <small>{{ item.skill }} · {{ item.course_type === 'PRACTICE' ? '实操' : '线上' }} · {{ item.hours }} 小时 · 目标 L{{ item.target_level }} · 截止 {{ item.due_at }}</small>
              </div>
              <div class="plan-meta">
                <div class="progress"><i :style="{ width: item.progress + '%' }"></i></div>
                <small>已学 {{ item.progress }}%</small>
              </div>
              <el-tag :type="item.required ? 'danger' : 'info'">{{ item.required ? '必修' : '选修' }}</el-tag>
            </div>
            <p v-if="!learningPlan.length" class="empty-note">暂无学习计划。</p>
          </div>

          <div class="panel wide">
            <div class="panel-title"><h2>最近学习记录</h2><span class="metric-note">按学习时间倒序</span></div>
            <div class="list-row" v-for="item in learningRecords" :key="item.id">
              <div class="row-main"><b>{{ item.course_name }}</b><small>{{ item.studied_at }} · 学习 {{ item.hours }} 小时 · {{ item.remark }}</small></div>
              <el-tag :type="item.status === 'COMPLETED' ? 'success' : 'warning'">{{ item.status === 'COMPLETED' ? '已完成' : '进行中' }}</el-tag>
            </div>
            <p v-if="!learningRecords.length" class="empty-note">暂无学习记录。</p>
          </div>

          <div class="panel wide">
            <div class="panel-title resource-title">
              <div>
                <h2>推荐资源</h2>
                <small class="chart-caption">按当前缺口匹配：站内资料跳到对应板块，外网资料在新窗口打开公开资料站</small>
              </div>
              <div class="course-search">
                <el-input v-model="courseSearchForm.keyword" placeholder="搜外网课程：继电保护 定值整定 / SF6 微水" clearable @keyup.enter="runCourseSearch" @clear="resetCourseSearch" />
                <el-select v-model="courseSearchForm.platform" placeholder="全部平台" clearable>
                  <el-option v-for="item in courseSearchPlatforms" :key="item.code" :label="item.name" :value="item.code" />
                </el-select>
                <el-select v-model="courseSearchForm.skill" placeholder="全部技能" clearable>
                  <el-option v-for="item in courseSkillOptions" :key="item" :label="item" :value="item" />
                </el-select>
                <el-select v-model="courseSearchForm.level" placeholder="全部等级" clearable>
                  <el-option v-for="item in courseLevelOptions" :key="item" :label="item" :value="item" />
                </el-select>
                <button class="action-button primary" :disabled="courseSearchRunning" @click="runCourseSearch">{{ courseSearchRunning ? '检索中…' : '搜索外网课程' }}</button>
              </div>
              <span class="chip info">共 {{ resources.length }} 条 · 外网 {{ externalResourceCount }} 条</span>
            </div>
            <div class="course-search-strip">
              <span class="metric-note">热门检索：</span>
              <button v-for="word in courseHotKeywords" :key="word" type="button" class="chip chip-button" @click="applyHotKeyword(word)">{{ word }}</button>
              <span v-if="courseSearchHistory.length" class="metric-note course-search-history">最近检索：{{ courseSearchHistory.join(' · ') }}</span>
            </div>
            <div class="course-platform-bar">
              <span class="metric-note">平台直达（新窗口打开）：</span>
              <a v-for="item in courseSearchPlatforms" :key="'home-' + item.code" class="action-button" :href="item.home_url" target="_blank" rel="noopener">{{ item.name }} ↗</a>
            </div>
            <p v-if="courseSearchNote" class="course-search-note">{{ courseSearchNote }}</p>
            <div v-if="courseSearchResult" class="course-search-panel">
              <div class="course-search-head">
                <b>外网课程检索 · {{ courseSearchResult.keyword || '按筛选条件' }}</b>
                <span class="chip warn">外网命中 {{ courseSearchResult.external_total }} 条</span>
                <span class="chip info">站内命中 {{ courseSearchResult.internal.length }} 条</span>
                <span class="metric-note">{{ courseSearchResult.searched_at }} · 用时 {{ courseSearchResult.took_ms }} ms · 外网课程库 {{ courseSearchResult.catalog_size }} 条 · 平台地址核验 {{ courseSearchResult.checked_at }}（{{ courseSearchResult.platform_ok }} / {{ courseSearchResult.platform_total }} 返回 200）</span>
              </div>
              <div class="course-platform-bar">
                <span class="metric-note">到平台检索「{{ courseSearchResult.keyword || '所选条件' }}」：</span>
                <a v-for="item in courseSearchResult.platforms" :key="'go-' + item.code" class="action-button" :href="item.url || item.home_url" target="_blank" rel="noopener">{{ item.name }} ↗</a>
              </div>
              <div class="course-result-grid">
                <article class="resource-card course-result-card" v-for="item in courseSearchResult.external" :key="'external-' + item.id">
                  <div class="resource-head">
                    <b>{{ item.title }}</b>
                    <span :class="item.gap_match ? 'chip warn' : 'chip info'">{{ item.gap_match ? '对口缺口' : item.level }}</span>
                  </div>
                  <small>{{ item.platform }}｜{{ item.type }} · {{ item.duration }} · {{ item.skill }} · {{ item.level }}</small>
                  <p>{{ item.match_reason }}</p>
                  <div class="tag-row">
                    <span class="chip info" v-for="tag in item.tags" :key="'tag-' + item.id + '-' + tag">{{ tag }}</span>
                  </div>
                  <small v-if="item.match_hits && item.match_hits.length" class="course-hit">命中：{{ item.match_hits.join(' · ') }}</small>
                  <div class="resource-foot">
                    <span class="metric-note">{{ item.org }} · 检索词「{{ item.search_keyword }}」</span>
                    <div class="role-toolbar">
                      <button v-if="questionCountOf(item.skill)" type="button" class="action-button" @click="drawPractice(item.skill)">配套练习（{{ questionCountOf(item.skill) }} 题）</button>
                      <a class="action-button" :href="item.url" target="_blank" rel="noopener">去 {{ item.platform }} 学 ↗</a>
                    </div>
                  </div>
                </article>
              </div>
              <p v-if="!courseSearchResult.external.length" class="empty-note">外网课程库里没有命中关键词的课程，点上方平台直达链接到公开平台继续检索。</p>
              <div v-if="courseSearchResult.internal.length" class="course-internal">
                <div class="section-title"><h3>站内命中</h3><span class="metric-note">点「去对应板块」跳到站内位置</span></div>
                <div class="list-row" v-for="item in courseSearchResult.internal" :key="'internal-' + item.id">
                  <div class="row-main"><b>{{ item.title }}</b><small>{{ item.source }} · {{ item.type }} · {{ item.duration }} · {{ item.skill }} · {{ item.level }}</small></div>
                  <div class="row-actions">
                    <a v-if="item.url" class="action-button" :href="item.url" target="_blank" rel="noopener">打开外网资料 ↗</a>
                    <button v-else type="button" class="action-button" @click="goResourceBoard(item)">去对应板块 →</button>
                  </div>
                </div>
              </div>
              <p class="course-search-note">{{ courseSearchResult.note }}</p>
            </div>
            <div class="resource-grid">
              <div class="resource-card" v-for="item in resources" :key="item.id">
                <div class="resource-head">
                  <b>{{ item.title }}</b>
                  <span :class="item.url ? 'chip warn' : 'chip info'">{{ item.origin || '站内' }}</span>
                </div>
                <small>{{ item.type }} · {{ item.duration }} · {{ item.skill }} · {{ item.level }}</small>
                <p>{{ item.match_reason }}</p>
                <div class="resource-foot">
                  <span class="metric-note">来源：{{ item.site }}</span>
                  <div class="role-toolbar">
                    <button v-if="questionCountOf(item.skill)" type="button" class="action-button" @click="drawPractice(item.skill)">配套练习（{{ questionCountOf(item.skill) }} 题）</button>
                    <a v-if="item.url" class="action-button" :href="item.url" target="_blank" rel="noopener">打开外网资料 ↗</a>
                    <button v-else type="button" class="action-button" @click="goResourceBoard(item)">去对应板块 →</button>
                  </div>
                </div>
              </div>
            </div>
            <p v-if="!resources.length" class="empty-note">暂无推荐资源。</p>
          </div>
        </template>

        <template v-else-if="learningTab === 'exams'">
          <div class="metrics four-metrics">
            <div class="metric panel readiness-card">
              <small>可进入考试</small>
              <div class="metric-value"><b>{{ examStats.open }}</b><em>门</em></div>
              <span :class="examStats.open ? 'good' : 'warn'">{{ examStats.open ? '管理员已开考，可进入答题' : '等待管理员统一开考' }}</span>
            </div>
            <div class="metric panel">
              <small>待考 / 补考</small>
              <div class="metric-value"><b>{{ examStats.pending + examStats.retake }}</b><em>门</em></div>
              <span class="warn">{{ examStats.pending }} 门待考 · {{ examStats.retake }} 门未通过</span>
            </div>
            <div class="metric panel">
              <small>已通过</small>
              <div class="metric-value"><b>{{ examStats.passed }}</b><em>门</em></div>
              <span>已考科目均值 {{ examStats.avg }} 分</span>
            </div>
            <div class="metric panel">
              <small>证书</small>
              <div class="metric-value"><b>{{ certificates.length }}</b><em>张</em></div>
              <span class="good">均在有效期内</span>
            </div>
          </div>

          <div class="panel wide">
            <div class="panel-title">
              <div><h2>我的考试</h2><small class="chart-caption">{{ examSummary.note || '只有管理员统一开考后，员工才能进入考试模式答题' }}</small></div>
              <button class="action-button" @click="learningTab = 'summary'">返回学习总版 →</button>
            </div>
            <p v-if="examError && !examRoom.visible" class="empty-note">{{ examError }}</p>
            <p v-if="examApiDown" class="empty-note">未连接后端 API（8080）：下面展示的是演示数据，无法发卷。启动后端后，在管理端「考试配置 → 考试清单」点「开始考试」，这里就会出现可点的「进入考试」。</p>
            <div v-if="openExamList.length" class="exam-open-banner">
              <div class="exam-open-main">
                <b>管理员已统一开考 {{ openExamList.length }} 场考试</b>
                <small>{{ openExamList.map((item) => item.name).join('、') }} · 点「进入考试」发卷作答，交卷后立即出分并给出错题解析</small>
              </div>
              <div class="row-actions">
                <el-button v-for="item in openExamList" :key="'enter-' + item.exam_id" size="small" type="primary"
                           :loading="examRunning" @click="startExam(item)">进入考试 · {{ item.name }}</el-button>
              </div>
            </div>
            <p v-else-if="!examApiDown" class="exam-wait-hint">
              当前没有开考的考试：等管理员在「考试配置 → 考试清单」点「开始考试」后，这里会立刻出现可点的「进入考试」按钮。
            </p>
            <div class="list-row" v-for="item in exams" :key="item.exam_id">
              <div class="row-main">
                <b>{{ item.name }}</b>
                <small>{{ item.exam_type }} · {{ item.duration_minutes }} 分钟 · {{ item.question_count }} 题 · 合格线 {{ item.pass_score }} 分 · {{ item.status_note }}</small>
              </div>
              <div class="row-actions">
                <span class="row-score" :class="{ warn: item.score != null && item.score < item.pass_score }">{{ item.score == null ? '未考' : item.score + ' 分' }}</span>
                <el-tag :type="examTag(item)">{{ examStatus(item) }}</el-tag>
                <el-button v-if="examCanEnter(item)" size="small" type="primary" :loading="examRunning" @click="startExam(item)">进入考试</el-button>
                <el-button v-else-if="item.round_submitted || item.attempts" size="small" @click="showExamDetail(item)">查看成绩</el-button>
                <el-button v-else size="small" disabled>等待管理员开考</el-button>
              </div>
            </div>
            <p v-if="!exams.length" class="empty-note">暂无考试安排。</p>
          </div>
          <div class="panel wide">
            <div class="panel-title"><div><h2>我的证书</h2><small class="chart-caption">通过考核后自动发放，与技能等级挂钩</small></div></div>
            <div class="cert-grid">
              <div class="cert-card" v-for="item in certificates" :key="item.id">
                <b>{{ item.name }}</b>
                <small>等级 {{ item.level }} · 颁发于 {{ item.issued_at }}</small>
                <el-tag type="success" size="small">{{ item.status === 'VALID' ? '有效' : '已过期' }}</el-tag>
              </div>
            </div>
            <p v-if="!certificates.length" class="empty-note">暂无证书。</p>
          </div>
        </template>

        <template v-else>
          <div class="metrics four-metrics">
            <div class="metric panel readiness-card">
              <small>题库总量</small>
              <div class="metric-value"><b>{{ practice ? practice.bank_total : 0 }}</b><em>题</em></div>
              <span class="good">含组长 SOP 入库题目</span>
            </div>
            <div class="metric panel">
              <small>本次抽题</small>
              <div class="metric-value"><b>{{ practiceQuestions.length }}</b><em>题</em></div>
              <span>{{ practiceSubmitted ? '已交卷' : '待作答' }}</span>
            </div>
            <div class="metric panel">
              <small>我的正确率</small>
              <div class="metric-value"><b>{{ practiceRate }}</b><em>%</em></div>
              <span class="warn">{{ practiceAnswered }} 题已练</span>
            </div>
            <div class="metric panel">
              <small>班组长入库</small>
              <div class="metric-value"><b>{{ sopQuestionCount }}</b><em>题</em></div>
              <span class="good">由班组长上传 / SOP 生成</span>
            </div>
          </div>

          <div class="panel wide">
            <div class="panel-title">
              <div>
                <h2>Agent 抽题练习</h2>
                <small class="chart-caption">按“技能缺口优先级 × 历史正确率”抽题：缺口越大、答对率越低的技能出题越多；答错的题会写入记忆库，下次抽题自动调整</small>
              </div>
              <div class="role-toolbar">
                <el-select v-model="practiceCount" size="small" style="width: 108px">
                  <el-option v-for="n in [3, 5, 8, 10]" :key="n" :label="n + ' 题'" :value="n" />
                </el-select>
                <el-select v-model="practiceSkill" size="small" placeholder="全部技能" clearable style="width: 168px">
                  <el-option v-for="item in practiceSkills" :key="item.skill" :label="item.skill + '（' + item.count + '）'" :value="item.skill" />
                </el-select>
                <button type="button" class="action-button primary" :disabled="practiceRunning" @click="drawPractice()">{{ practiceRunning ? '处理中…' : '开始抽题练习' }}</button>
              </div>
            </div>
            <p v-if="practiceError && !practiceDialog.visible" class="empty-note">{{ practiceError }}</p>
            <div v-if="practiceAgent" class="agent-verdict">
              <span class="chip info">Agent 抽题策略</span>
              <b>{{ practiceAgent.note }}</b>
            </div>
            <div class="tag-row" v-if="practicePlan.length">
              <span class="chip" v-for="item in practicePlan" :key="item.skill">{{ item.skill }} {{ item.count }} 题 · 当前正确率 {{ item.accuracy }}</span>
            </div>
            <p v-if="!practiceQuestions.length" class="empty-note">还没抽题：选好题量与技能范围，点“开始抽题练习”会弹出答题窗口；也可以在下面“题库分布”里直接点某个技能做专项练习。</p>
            <div class="role-toolbar" style="margin-top: 12px" v-if="practiceResult">
              <span :class="practiceResult.score >= 80 ? 'chip ok' : 'chip bad'">最近一次练习：{{ practiceResult.score }} 分 · 答对 {{ practiceResult.correct }} / {{ practiceResult.total }}</span>
              <button type="button" class="action-button" @click="openPracticeResult">查看解析</button>
              <span class="metric-note">{{ practiceResult.ran_at }}</span>
            </div>
          </div>

          <div class="panel wide">
            <div class="panel-title"><h2>题库分布</h2><span class="metric-note">点技能即可专项练习</span></div>
            <div class="tag-row">
              <button type="button" class="action-button" v-for="item in practiceSkills" :key="item.skill" @click="drawPractice(item.skill)">{{ item.skill }} · {{ item.count }} 题</button>
            </div>
            <p v-if="practice && practice.team_sources && practice.team_sources.length" class="role-note" style="margin-top: 12px">
              已入库的班组长练习资料（导入文档 / SOP 填报）：{{ practice.team_sources.map((item) => item.source + '（' + item.count + ' 题）').join('；') }}
            </p>
            <p v-if="practice && practice.history && practice.history.length" class="role-note" style="margin-top: 8px">
              最近练习记录：{{ practice.history.map((item) => item.ran_at + ' ' + item.source + ' ' + item.score + ' 分').join('；') }}
            </p>
          </div>
        </template>      </section>

      <section v-if="active === 'skills'" class="skills-page">

        <div class="metrics four-metrics">
          <div class="metric panel readiness-card"><small>岗位匹配度</small><div class="metric-value"><b>{{ profile.readiness }}</b><em>/100</em></div><span class="good">持续成长中</span></div>
          <div class="metric panel"><small>当前达标技能</small><div class="metric-value"><b>{{ metSkills.length }}</b><em>项</em></div><span class="good">{{ skillNames(metSkills, '暂无达标技能') }}</span></div>
          <div class="metric panel"><small>重点提升</small><div class="metric-value"><b class="warn">{{ gapSkills.length }}</b><em>项</em></div><span class="warn">{{ skillNames(gapSkills, '暂无明显缺口') }}</span></div>
          <div class="metric panel"><small>成长阶段</small><div class="metric-value"><b>L2</b></div><span>向关键岗位准备</span></div>
        </div>

        <div class="role-toolbar">
          <span class="chip ok">安全状态：良好（1280 天无违章、无一票否决）</span>
          <span class="chip info">本月学习 {{ learningSummary.month_hours }} 小时 · 完成率 {{ learningSummary.completion }}%</span>
          <span class="chip warn">待补考 1 门 · 待考 {{ examStats.pending }} 门</span>
        </div>

        <AgentStrip :diagnosis="agentDiagnosis" />

        <div class="panel wide">
          <div class="panel-title">
            <div><h2>技能雷达</h2><small class="chart-caption">当前等级 · 岗位要求 · 未来需求（悬停右侧能力明细可定位）</small></div>
            <button class="action-button" @click="active = 'advice'">差距与建议 →</button>
          </div>
          <div class="line-chart">
            <div class="chart-y"><span>L3</span><span>L2</span><span>L1</span><span>L0</span></div>
            <svg viewBox="0 0 760 220" role="img" aria-label="技能等级折线图" preserveAspectRatio="none">
              <line x1="20" y1="18" x2="740" y2="18"/>
              <line x1="20" y1="78" x2="740" y2="78"/>
              <line x1="20" y1="138" x2="740" y2="138"/>
              <line x1="20" y1="198" x2="740" y2="198"/>
              <line class="focus-line" v-if="activeSkill >= 0" :x1="axisX(activeSkill)" y1="18" :x2="axisX(activeSkill)" y2="198"/>
              <polyline class="required-line" :points="radarLine('required')"/>
              <polyline class="future-line" :points="radarLine('future')"/>
              <polyline class="current-line" :points="radarLine('current')"/>
              <circle class="current-dot" v-for="(point, index) in radarSeries('current')" :key="index" :cx="point.x" :cy="point.y" :r="activeSkill === index ? 9 : 6"/>
            </svg>
            <div class="chart-x">
              <span v-for="(item, index) in radarSkills" :key="item.skill" :class="{ active: activeSkill === index }" :style="{ left: labelLeft(index) }">{{ item.skill }}</span>
            </div>
          </div>
          <div class="chart-legend">
            <span><i class="legend-current"/>当前等级</span>
            <span><i class="legend-required"/>岗位要求</span>
            <span><i class="legend-future"/>未来需求</span>
          </div>
        </div>

        <div class="panel">
          <div class="panel-title">
            <div><h2>能力明细</h2><small class="chart-caption">当前等级 / 岗位要求 / 未来需求</small></div>
            <button class="action-button" @click="active = 'learning'">去学习 →</button>
          </div>
          <div class="skill-row" v-for="(item, index) in radarSkills" :key="item.skill" :class="{ active: activeSkill === index }" @mouseenter="activeSkill = index" @mouseleave="activeSkill = -1">
            <div><b>{{ item.skill }}</b><small>当前 L{{ clampLevel(item.current) }} · 岗位要求 L{{ clampLevel(item.required) }} · 未来需求 L{{ clampLevel(item.future) }}</small></div>
            <el-tag :type="skillTag(item)">{{ skillState(item) }}</el-tag>
          </div>
        </div>

        <div class="panel growth-panel">
          <div class="panel-title">
            <div><h2>成长轨迹</h2><small class="chart-caption">能力与职业发展的关键节点</small></div>
            <button class="action-button" @click="exportRecords">导出记录 ↓</button>
          </div>
          <div class="growth-timeline">
            <div class="growth-event" v-for="event in growthEvents" :key="event.title">
              <span class="growth-dot" :class="event.dot"></span>
              <div><b>{{ event.title }}</b><small>{{ event.note }}</small></div>
              <strong>{{ event.badge }}</strong>
            </div>
          </div>
        </div>
      </section>

      <section v-if="active === 'tasks'" class="tasks-page">
        <div class="metrics four-metrics">
          <div class="metric panel readiness-card">
            <small>{{ canFillReport ? '待填报任务' : '我的实操任务' }}</small>
            <div class="metric-value"><b>{{ taskMetrics.pending }}</b><em>项</em></div>
            <span class="warn">{{ canFillReport ? '按截止时间完成检测并填报' : '按截止时间完成现场检测' }}</span>
          </div>
          <div class="metric panel">
            <small>已提交报告</small>
            <div class="metric-value"><b>{{ taskMetrics.submitted }}</b><em>份</em></div>
            <span class="good">PDF / Word 已生成</span>
          </div>
          <div class="metric panel">
            <small>检测超限</small>
            <div class="metric-value"><b class="warn">{{ taskMetrics.abnormal }}</b><em>项</em></div>
            <span class="warn">需归因闭环</span>
          </div>
          <div class="metric panel">
            <small>待人工确认</small>
            <div class="metric-value"><b>{{ taskMetrics.needConfirm }}</b><em>项</em></div>
            <span>AI 结论需班组长确认</span>
          </div>
        </div>

        <div class="panel wide">
          <div class="panel-title">
            <div>
              <h2>实操任务</h2>
              <small class="chart-caption">{{ canFillReport ? '检测报告由你填报：提交后自动生成文档并执行 AI 归因' : '值班员只负责现场检测与查看报告，检测报告由班组长统一填报' }}</small>
            </div>
          </div>
          <div class="list-row" v-for="task in taskList" :key="task.id">
            <div class="row-main">
              <b>{{ task.title }}</b>
              <small>{{ task.skill }} · 计划 {{ task.planned_hours }}h · 截止 {{ task.due_at }} · {{ task.requirement }}</small>
            </div>
            <div class="row-actions">
              <el-tag :type="taskTag(task)">{{ task.status }}</el-tag>
              <el-tag v-if="task.judgment" :type="task.judgment === '超限' ? 'danger' : 'success'" effect="plain">{{ task.judgment }}</el-tag>
              <button v-if="task.report_id" type="button" class="action-button" @click="openReportViewById(task.report_id)">查看报告</button>
              <button v-if="canFillReport" type="button" class="action-button primary" @click="openReportForm(task)">填报报告</button>
            </div>
          </div>
          <p v-if="!taskList.length" class="empty-note">暂无实操任务。</p>
        </div>

        <div class="panel wide">
          <div class="panel-title">
            <div>
              <h2>我的检测报告</h2>
              <small class="chart-caption">{{ canFillReport ? '文档按模板框格渲染，可下载归档' : '检测报告由班组长填报，这里只能查看与下载，不能新增' }}</small>
            </div>
          </div>
          <div class="list-row" v-for="report in reportList" :key="report.report_id">
            <div class="row-main">
              <b>{{ report.report_id }} · {{ report.task_title }}</b>
              <small>{{ report.detected_at }} · {{ report.shift }} · {{ report.location }}</small>
              <small>{{ report.gas_label }} {{ report.gas_value }} {{ report.unit }}（阈值 {{ report.threshold }} {{ report.unit }}） · 归因来源：{{ reportSourceLabel(report) }}</small>
            </div>
            <div class="row-actions">
              <span class="row-score" :class="{ warn: report.judgment === '超限' }">{{ report.judgment }}</span>
              <el-tag :type="report.judgment === '超限' ? 'danger' : 'success'">严重度 {{ report.severity }}</el-tag>
              <el-tag :type="reportSourceTag(report)" effect="plain">{{ report.analysis && report.analysis.source === 'ai' ? 'AI 归因' : '规则归因' }}</el-tag>
              <button type="button" class="action-button" @click="downloadDocument(report, 'pdf')">下载 PDF</button>
              <button type="button" class="action-button primary" @click="openReportView(report)">查看报告</button>
            </div>
          </div>
          <p v-if="!reportList.length" class="empty-note">暂无报告，先在“实操任务”里填报。</p>
        </div>

        <div class="panel wide" v-if="canFillReport">
          <div class="panel-title">
            <div><h2>报告模板框格（规定填写内容）</h2><small class="chart-caption">{{ reportTemplate.notice }}</small></div>
            <div class="row-actions">
              <button type="button" class="action-button" @click="templateDialogVisible = true">查看模板框格</button>
              <button type="button" class="action-button primary" @click="openReportForm(taskList[0])">按模板填报</button>
            </div>
          </div>
          <div class="template-summary">
            <span class="chip info" v-for="section in templateSections" :key="section.key">{{ section.title }} · {{ section.fields.length }} 项</span>
            <span class="chip">签字框格 {{ (reportTemplate.sign_boxes ?? []).length }} 个</span>
          </div>
          <small class="chart-caption">完整填写要求与签字栏在弹窗中查看，页面只保留填报入口。</small>
        </div>
      </section>

      <section v-if="active === 'twin'" class="twin-section">
        <nav class="twin-floatnav" aria-label="页面导航">
          <button v-for="item in navItems" :key="item.key" :class="{ active: active === item.key }" @click="active = item.key"><span>{{ item.icon }}</span>{{ item.label }}</button>
          <button class="nav-theme" :title="theme === 'day' ? '切换黑夜模式' : '切换白天模式'" aria-label="切换昼夜主题" @click="toggleTheme">
            <svg v-if="theme === 'day'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z" />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="4" />
              <path d="M12 2.8v2.4M12 18.8v2.4M2.8 12h2.4M18.8 12h2.4M5.5 5.5l1.7 1.7M16.8 16.8l1.7 1.7M18.5 5.5l-1.7 1.7M7.2 16.8l-1.7 1.7" />
            </svg>
          </button>
        </nav>
        <DigitalTwinView :initial-theme="theme" />
      </section>
      <section v-if="active === 'selfPortrait'" class="role-page"><SelfPortraitView /></section>
      <section v-if="active === 'abilities'" class="role-page"><AbilityView :diagnosis="agentDiagnosis" /></section>
      <section v-if="active === 'memories'" class="role-page"><MemoryView :diagnosis="agentDiagnosis" @go="active = $event" /></section>
      <section v-if="active === 'growth'" class="role-page"><GrowthView :diagnosis="agentDiagnosis" /></section>
      <section v-if="active === 'advice'" class="role-page"><AdviceView :diagnosis="agentDiagnosis" @diagnosed="applyDiagnosis" /></section>
      <section v-if="active === 'team'" class="role-page"><TeamReportView @go="active = $event" @fill="startRefill" /></section>
      <section v-if="active === 'company'" class="role-page"><CompanyView mode="overview" /></section>
      <section v-if="active === 'skillMatrix'" class="role-page"><CompanyView mode="matrix" /></section>
      <section v-if="active === 'training'" class="role-page"><CompanyView mode="training" /></section>
      <section v-if="active === 'diagnosis'" class="role-page"><CompanyView mode="diagnosis" /></section>
      <section v-if="active === 'adminIam'" class="role-page"><AdminView tab="iam" /></section>
      <section v-if="active === 'adminContent'" class="role-page"><AdminView tab="content" /></section>
      <section v-if="active === 'adminExam'" class="role-page"><AdminView tab="examConfig" /></section>

      <section v-if="active === 'adminAudit'" class="role-page"><AdminView tab="audit" /></section>

      <el-dialog v-model="templateDialogVisible" title="报告模板框格（规定填写内容）" width="min(1080px, 94vw)" top="4vh" class="practice-dialog template-dialog">
        <div class="form-notice">{{ reportTemplate.notice }}</div>
        <div class="template-grid">
          <div class="template-section" v-for="section in templateSections" :key="section.key">
            <b>{{ section.title }}</b>
            <div class="template-field" v-for="field in section.fields" :key="field.name">
              <span class="template-label">{{ field.label }}<i v-if="field.required">*</i></span>
              <small>{{ field.hint }}</small>
              <code>示例：{{ field.example }}</code>
            </div>
          </div>
        </div>
        <div class="sign-boxes">
          <span v-for="box in reportTemplate.sign_boxes" :key="box">{{ box }}</span>
        </div>
        <template #footer>
          <el-button @click="templateDialogVisible = false">关闭</el-button>
          <el-button type="primary" @click="templateDialogVisible = false; openReportForm(taskList[0])">按模板填报</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="reportFormVisible" :title="reportFormTask ? '填报检测报告 · ' + reportFormTask.title : '填报检测报告'" width="780px" top="4vh">
        <div class="form-notice">{{ reportTemplate.notice }}</div>
        <el-form label-position="top" class="report-form">
          <div class="form-section">
            <div class="form-section-title">一、基础信息</div>
            <div class="form-grid">
              <el-form-item :label="fieldOf('detected_at').label" required :error="reportFormErrors.detected_at">
                <el-date-picker v-model="reportForm.detected_at" type="datetime" value-format="YYYY-MM-DD HH:mm" format="YYYY-MM-DD HH:mm" placeholder="选择检测时间" style="width: 100%" />
                <small class="field-hint">{{ fieldOf('detected_at').hint }}</small>
              </el-form-item>
              <el-form-item :label="fieldOf('shift').label" required :error="reportFormErrors.shift">
                <el-select v-model="reportForm.shift" placeholder="选择班次" style="width: 100%">
                  <el-option v-for="shift in shiftOptions" :key="shift" :label="shift" :value="shift" />
                </el-select>
                <small class="field-hint">{{ fieldOf('shift').hint }}</small>
              </el-form-item>
              <el-form-item class="span-two" :label="fieldOf('location').label" required :error="reportFormErrors.location">
                <el-input v-model="reportForm.location" :placeholder="'示例：' + fieldOf('location').example" maxlength="120" />
                <small class="field-hint">{{ fieldOf('location').hint }}</small>
              </el-form-item>
              <el-form-item class="span-two" :label="fieldOf('member').label" :error="reportFormErrors.member">
                <el-input v-model="reportForm.member" maxlength="32" :placeholder="'选填，示例：' + fieldOf('member').example" />
                <small class="field-hint">{{ fieldOf('member').hint }}</small>
              </el-form-item>
            </div>
          </div>

          <div class="form-section">
            <div class="form-section-title">二、检测数据</div>
            <div class="form-grid three">
              <el-form-item :label="fieldOf('gas_type').label" required :error="reportFormErrors.gas_type">
                <el-select v-model="reportForm.gas_type" placeholder="选择气体类型" style="width: 100%" @change="onGasChange">
                  <el-option v-for="gas in gasRules" :key="gas.code" :label="gas.label + '（' + gas.code + '）'" :value="gas.code" />
                </el-select>
                <small class="field-hint">{{ fieldOf('gas_type').hint }}</small>
              </el-form-item>
              <el-form-item :label="fieldOf('gas_value').label" required :error="reportFormErrors.gas_value">
                <el-input-number v-model="reportForm.gas_value" :min="0" :controls="false" :placeholder="'示例：' + fieldOf('gas_value').example" style="width: 100%" />
                <small class="field-hint">单位：{{ selectedGas ? selectedGas.unit : '请先选择气体类型' }}</small>
              </el-form-item>
              <el-form-item :label="fieldOf('threshold').label" required :error="reportFormErrors.threshold">
                <el-input-number v-model="reportForm.threshold" :min="0" :controls="false" style="width: 100%" />
                <small class="field-hint">
                  {{ selectedGas ? selectedGas.direction_label + '，标准值 ' + selectedGas.threshold + ' ' + selectedGas.unit : fieldOf('threshold').hint }}
                  <button v-if="selectedGas" type="button" class="inline-link" @click="resetThreshold">恢复标准阈值</button>
                </small>
              </el-form-item>
            </div>
            <div class="judge-row" v-if="selectedGas && reportForm.gas_value != null && reportForm.threshold != null">
              <span>实时判定</span>
              <el-tag :type="formAbnormal ? 'danger' : 'success'">{{ formAbnormal ? '超限' : '正常' }}</el-tag>
              <small>{{ formAbnormal ? '检测值已触发报警，提交后写入异常归因分析' : '检测值在阈值范围内，仍会留存记录' }}（{{ selectedGas.direction_label }}）</small>
            </div>
          </div>

          <div class="form-section">
            <div class="form-section-title">三、异常现象描述</div>
            <el-form-item :label="fieldOf('phenomenon').label" required :error="reportFormErrors.phenomenon">
              <el-input v-model="reportForm.phenomenon" type="textarea" :rows="5" maxlength="300" show-word-limit
                        :placeholder="'填写示例：' + fieldOf('phenomenon').example" />
              <div class="word-check">
                <span :class="{ ok: phenomenonLength >= 15 && phenomenonLength <= 300 }">字数 {{ phenomenonLength }} / 15-300</span>
                <span :class="{ ok: phenomenonHasNumber }">{{ phenomenonHasNumber ? '已包含时间或数值' : '需包含具体时间或数值' }}</span>
                <button type="button" class="action-button" @click="insertPhenomenonExample">插入示例</button>
              </div>
              <small class="field-hint">{{ fieldOf('phenomenon').hint }}</small>
            </el-form-item>
            <el-form-item :label="fieldOf('measures').label" :error="reportFormErrors.measures">
              <el-input v-model="reportForm.measures" type="textarea" :rows="2" maxlength="200" show-word-limit
                        :placeholder="'选填，示例：' + fieldOf('measures').example" />
              <div class="word-check">
                <button type="button" class="action-button" @click="insertMeasuresExample">插入示例</button>
              </div>
            </el-form-item>
          </div>

          <div class="form-section">
            <div class="form-section-title">四、SOP 执行情况</div>
            <el-form-item :label="fieldOf('sop_status').label" required :error="reportFormErrors.sop_status">
              <el-radio-group v-model="reportForm.sop_status">
                <el-radio-button v-for="option in sopOptions" :key="option.value" :value="option.value">{{ option.label }}</el-radio-button>
              </el-radio-group>
              <small class="field-hint">{{ fieldOf('sop_status').hint }}</small>
            </el-form-item>
            <el-form-item :label="fieldOf('sop_deviation').label" :required="sopDeviationRequired" :error="reportFormErrors.sop_deviation">
              <el-input v-model="reportForm.sop_deviation" type="textarea" :rows="2" maxlength="200" show-word-limit
                        :disabled="!sopDeviationRequired"
                        :placeholder="sopDeviationRequired ? '必填：写清哪一步没按规程做' : '选「未按 SOP 执行」时必填，示例：' + fieldOf('sop_deviation').example" />
              <small class="field-hint">{{ fieldOf('sop_deviation').hint }}</small>
            </el-form-item>
          </div>
        </el-form>
        <template #footer>
          <el-button @click="reportFormVisible = false">取消</el-button>
          <el-button type="primary" :loading="reportFormRunning" @click="submitReport">提交并生成报告</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="reportDialogVisible" :title="activeReport ? '检测报告 · ' + activeReport.report_id : '检测报告'" width="800px" top="4vh">
        <template v-if="activeReport">
          <div class="result-banner">
            <div>
              <b>{{ activeReport.task_title }}</b>
              <small>{{ activeReport.detected_at }} · {{ activeReport.shift }} · {{ activeReport.location }}</small>
            </div>
            <div class="row-actions">
              <span class="row-score" :class="{ warn: activeReport.judgment === '超限' }">{{ activeReport.judgment }}</span>
              <el-tag :type="activeReport.judgment === '超限' ? 'danger' : 'success'">严重度 {{ activeReport.severity }}</el-tag>
            </div>
          </div>

          <div class="preview-block">
            <div class="preview-section" v-for="section in reportPreviewSections" :key="section.title">
              <b>{{ section.title }}</b>
              <div class="preview-row" v-for="row in section.rows" :key="row[0]">
                <span class="preview-label">{{ row[0] }}</span>
                <span class="preview-value">{{ row[1] }}</span>
              </div>
            </div>
          </div>

          <div class="analysis-card" v-if="activeReport.analysis">
            <div class="analysis-head">
              <b>AI 归因分析</b>
              <div>
                <el-tag :type="reportSourceTag(activeReport)" effect="plain">{{ reportSourceLabel(activeReport) }}</el-tag>
                <el-tag type="info" effect="plain">置信度 {{ activeReport.analysis.confidence }}</el-tag>
              </div>
            </div>
            <p class="analysis-conclusion">{{ activeReport.analysis.conclusion }}</p>
            <div class="analysis-list">
              <b>可能原因</b>
              <ol><li v-for="cause in activeReport.analysis.causes" :key="cause">{{ cause }}</li></ol>
            </div>
            <div class="analysis-list">
              <b>建议措施</b>
              <ol><li v-for="action in activeReport.analysis.actions" :key="action">{{ action }}</li></ol>
            </div>
            <div class="analysis-tags">
              <span>命中规则</span>
              <el-tag v-for="rule in activeReport.analysis.rule_refs" :key="rule" size="small" effect="plain">{{ rule }}</el-tag>
            </div>
            <small class="analysis-note">{{ activeReport.analysis.need_human_confirm ? '结论需班组长确认后方可闭环（人工负责制）' : '可直接闭环' }}</small>
            <el-collapse class="analysis-collapse">
              <el-collapse-item title="查看 AI 读取的文档正文（检测数值 + 现象描述）" name="doc">
                <pre class="doc-text">{{ activeReport.document_text }}</pre>
              </el-collapse-item>
            </el-collapse>
          </div>
        </template>
        <template #footer>
          <el-button @click="reportDialogVisible = false">关闭</el-button>
          <el-button :loading="reportDialogRunning" @click="analyzeReport">重新分析</el-button>
          <el-button @click="downloadDocument(activeReport, 'docx')">下载 Word</el-button>
          <el-button type="primary" @click="downloadDocument(activeReport, 'pdf')">下载 PDF</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="examDialog.visible" :title="examDialog.title" width="420px">
        <p class="dialog-note">{{ examDialog.subtitle }}</p>
        <div class="dialog-rows">
          <div v-for="rowItem in examDialog.rows" :key="rowItem[0]"><span>{{ rowItem[0] }}</span><b>{{ rowItem[1] }}</b></div>
        </div>
        <template #footer>
          <el-button @click="examDialog.visible = false">关闭</el-button>
          <el-button v-if="examDialog.item && examCanEnter(examDialog.item)" type="primary" :loading="examRunning" @click="examDialog.visible = false; startExam(examDialog.item)">进入考试</el-button>
        </template>
      </el-dialog>
      <!-- 练习作答全屏弹窗：题干与选项需要大版面（与考试作答弹窗同一 fullscreen 口径） -->
      <el-dialog v-model="practiceDialog.visible" :title="practiceDialog.mode === 'result' ? '练习解析' : '练习题作答'" fullscreen class="practice-dialog">
        <div class="practice-note-row">
          <span class="chip info">{{ practiceDialog.mode === 'quiz' ? '共 ' + practiceQuestions.length + ' 题（弹窗内作答，交卷后直接看到解析）' : '本次交卷 ' + practiceResult.total + ' 题' }}</span>
          <span class="metric-note" v-if="practiceDialog.mode === 'quiz'">单选题选字母，判断题选“对 / 错” · 已作答 {{ answeredCount }} / {{ practiceQuestions.length }} 题</span>
        </div>
        <p v-if="practiceError" class="empty-note">{{ practiceError }}</p>
        <template v-if="practiceDialog.mode === 'quiz'">
          <div class="practice-item" v-for="(q, index) in practiceQuestions" :key="q.id">
            <div class="practice-head">
              <span class="chip info">第 {{ index + 1 }} 题</span>
              <span class="chip">{{ q.type }}</span>
              <span class="chip">{{ q.skill }} · L{{ q.level }}</span>
              <span class="metric-note">{{ q.source }}</span>
            </div>
            <p class="practice-stem">{{ q.stem }}</p>
            <div class="practice-options">
              <label v-for="option in q.options" :key="option" class="practice-option"
                     :class="{ picked: practiceAnswers[q.id] === option.slice(0, 1) }">
                <input type="radio" :name="'practice-' + q.id" :value="option.slice(0, 1)" v-model="practiceAnswers[q.id]" />
                <span>{{ option }}</span>
              </label>
            </div>
          </div>
        </template>
        <template v-else>
          <div class="practice-note-row">
            <span :class="practiceResult.score >= 80 ? 'chip ok' : 'chip bad'">得分 {{ practiceResult.score }} · 答对 {{ practiceResult.correct }} / {{ practiceResult.total }}</span>
            <span class="metric-note">{{ practiceResult.ran_at }} · {{ practiceResult.memory_written.note }}</span>
          </div>
          <div class="practice-item" v-for="item in practiceResult.items" :key="item.id">
            <div class="practice-head">
              <span :class="item.correct ? 'chip ok' : 'chip bad'">{{ item.correct ? '答对' : '答错' }}</span>
              <span class="chip">{{ item.type }}</span>
              <span class="chip">{{ item.skill }} · L{{ item.level }}</span>
            </div>
            <p class="practice-stem">{{ item.stem }}</p>
            <p class="role-note">你的作答：<b>{{ item.your_answer }}</b> · 正确答案：<b>{{ item.correct_answer }}</b></p>
            <p class="role-note judgement">解析：{{ item.explanation }}</p>
          </div>
        </template>
        <template #footer>
          <template v-if="practiceDialog.mode === 'quiz'">
            <el-button @click="practiceDialog.visible = false">稍后再答</el-button>
            <el-button type="primary" :loading="practiceRunning" @click="submitPractice">交卷</el-button>
          </template>
          <template v-else>
            <el-button @click="practiceDialog.visible = false">关闭</el-button>
            <el-button type="primary" :loading="practiceRunning" @click="drawPractice()">再练一组</el-button>
          </template>
        </template>
      </el-dialog>

      <el-dialog v-model="examRoom.visible" :title="examRoom.mode === 'result' ? '考试成绩与解析' : (examSession ? examSession.name + ' · 考试进行中' : '考试作答')"
                 :fullscreen="examRoom.mode === 'quiz'" width="880px" top="4vh" class="practice-dialog exam-dialog" @closed="stopExamTimer">
        <div class="practice-note-row">
          <template v-if="examRoom.mode === 'quiz'">
            <span class="chip info" v-if="examSession">共 {{ examQuestions.length }} 题 · 合格线 {{ examSession.pass_score }} 分 · 限时 {{ examSession.duration_minutes }} 分钟</span>
            <span class="chip warn">剩余 {{ examRemaining }}</span>
            <span class="metric-note">管理员统一开考（{{ examSession ? examSession.started_at : '—' }}）· 已作答 {{ examAnswered }} / {{ examQuestions.length }} 题</span>
          </template>
          <template v-else>
            <span :class="examResult.passed ? 'chip ok' : 'chip bad'">得分 {{ examResult.score }} · 答对 {{ examResult.correct }} / {{ examResult.total }}</span>
            <span class="chip info">合格线 {{ examResult.pass_score }} 分</span>
            <span class="metric-note">{{ examResult.submitted_at }} · {{ examResult.message }}</span>
          </template>
        </div>
        <p v-if="examError" class="empty-note">{{ examError }}</p>
        <template v-if="examRoom.mode === 'quiz'">
          <div class="exam-answer-sheet">
            <span class="metric-note">答题卡</span>
            <button v-for="(q, index) in examQuestions" :key="'sheet-' + q.id" type="button"
                    class="exam-sheet-item" :class="{ done: Boolean(examAnswers[q.id]) }"
                    @click="focusExamQuestion(q.id)">{{ index + 1 }}</button>
            <span class="metric-note">未作答 {{ examUnanswered }} 题</span>
            <el-button size="small" type="primary" :loading="examRunning" @click="submitExam('manual')">交卷</el-button>
            <el-button size="small" @click="closeExamRoom">暂时离开（计时继续）</el-button>
          </div>
          <div class="practice-item" v-for="(q, index) in examQuestions" :key="q.id" :id="'exam-q-' + q.id">
            <div class="practice-head">
              <span class="chip info">第 {{ index + 1 }} 题</span>
              <span class="chip">{{ q.type }}</span>
              <span class="chip">{{ q.skill }} · L{{ q.level }}</span>
              <span class="metric-note">{{ q.source }}</span>
            </div>
            <p class="practice-stem">{{ q.stem }}</p>
            <div class="practice-options">
              <label v-for="option in q.options" :key="option" class="practice-option"
                     :class="{ picked: examAnswers[q.id] === option.slice(0, 1) }">
                <input type="radio" :name="'exam-' + q.id" :value="option.slice(0, 1)" v-model="examAnswers[q.id]" />
                <span>{{ option }}</span>
              </label>
            </div>
          </div>
        </template>
        <template v-else>
          <div class="practice-item" v-for="item in examResult.details" :key="item.id">
            <div class="practice-head">
              <span :class="item.right ? 'chip ok' : 'chip bad'">{{ item.right ? '答对' : '答错' }}</span>
              <span class="chip">{{ item.type }}</span>
              <span class="chip">{{ item.skill }} · L{{ item.level }}</span>
            </div>
            <p class="practice-stem">{{ item.stem }}</p>
            <p class="role-note">你的作答：<b>{{ item.my_answer || '未作答' }}</b> · 正确答案：<b>{{ item.answer }}</b></p>
            <p class="role-note judgement">解析：{{ item.explanation }}</p>
            <p v-if="item.source" class="metric-note">出处：{{ item.source }}</p>
          </div>
        </template>
        <template #footer>
          <template v-if="examRoom.mode === 'quiz'">
            <el-button @click="closeExamRoom">暂时离开（计时继续）</el-button>
            <el-button type="primary" :loading="examRunning" @click="submitExam('manual')">交卷</el-button>
          </template>
          <template v-else>
            <el-button @click="closeExamRoom">关闭</el-button>
            <el-button type="primary" @click="closeExamRoom(); learningTab = 'exams'">返回考试中心</el-button>
          </template>
        </template>
      </el-dialog>
    </main>
  </div>
</template>
