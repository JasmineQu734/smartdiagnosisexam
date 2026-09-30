<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { api, getData } from '../api';
import '../roles.css';

const props = defineProps({ tab: { type: String, default: 'iam' } });
const current = ref(props.tab);

const overview = ref(null);
const iam = ref(null);
const orgs = ref([]);
const positions = ref([]);
const permissions = ref([]);
const employees = ref([]);
const skills = ref([]);
const positionSkills = ref(null);
const standards = ref(null);
const courseData = ref(null);
const links = ref([]);
const banks = ref([]);
const materialData = ref(null);
const exams = ref(null);
const examConfig = ref(null);
const papers = ref([]);
const audit = ref(null);

const uploadForm = ref({ file_name: '', target: '课程库', note: '' });
const uploadErrors = ref({});
const uploadResult = ref(null);
const uploadBusy = ref(false);
const uploadDialog = ref({ visible: false });
const issueForm = ref({ exam_id: '', scope: '', count: '', deadline: '' });
// 发放对象改成下拉：常用范围 / 班组中心 / 岗位都可直接选，选到有在册人数的范围时自动带出份数
let scopeAutoCount = '';
const issueErrors = ref({});
const issueResult = ref(null);
const issueDialog = ref({ visible: false });
const examMessage = ref('');
const examBusy = ref('');
const reviewMessage = ref('');
const reviewBusy = ref('');
const materialDialog = ref({ visible: false, loading: false, busy: false, detail: null, message: '' });
const search = ref({ category: '', keyword: '' });
const auditMessage = ref('');
const clearArmed = ref(false);

const riskClass = (risk) => ({ HIGH: 'chip bad', MEDIUM: 'chip warn', LOW: 'chip ok' }[risk] || 'chip');
const statusClass = (status) => ({
  已上线: 'chip ok', 待审核: 'chip warn', 已驳回: 'chip bad', 已审核: 'chip ok',
  未开始: 'chip', 进行中: 'chip ok',
  已结束: 'chip warn',
  已回收: 'chip ok', 回收中: 'chip warn', 已发放: 'chip info'
}[status] || 'chip');
const categoryClass = (category) => ({
  登录: 'chip info', 修改: 'chip warn', 审批: 'chip info', 决策: 'chip info', 执行: 'chip ok', 回滚: 'chip bad', 访问: 'chip'
}[category] || 'chip');
const resultClass = (result) => (String(result).includes('拒绝') ? 'chip bad' : 'chip ok');

const loadCourses = async () => { courseData.value = await getData('/admin/courses', null); };
const loadMaterials = async () => { materialData.value = await getData('/admin/course-materials', null); };
const loadBanks = async () => { banks.value = await getData('/admin/question-banks', []); };
const loadExams = async () => { exams.value = await getData('/admin/exams', null); };
const loadPapers = async () => { papers.value = await getData('/admin/papers', []); };

const loadAudit = async () => {
  const query = new URLSearchParams();
  if (search.value.category) query.set('category', search.value.category);
  if (search.value.keyword) query.set('keyword', search.value.keyword);
  const suffix = query.toString() ? '?' + query.toString() : '';
  audit.value = await getData('/admin/audit' + suffix, null);
};

const load = async () => {
  const key = current.value;
  if (key === 'iam') {
    if (!overview.value) overview.value = await getData('/admin/overview', null);
    if (!iam.value) iam.value = await getData('/admin/iam', null);
    if (!orgs.value.length) orgs.value = await getData('/admin/orgs', []);
    if (!positions.value.length) positions.value = await getData('/admin/positions', []);
    if (!permissions.value.length) permissions.value = await getData('/admin/permissions', []);
    if (!employees.value.length) employees.value = await getData('/admin/employees', []);
  }
  if (key === 'content') {
    if (!skills.value.length) skills.value = await getData('/admin/skills', []);
    if (!positionSkills.value) positionSkills.value = await getData('/admin/position-skills', null);
    if (!standards.value) standards.value = await getData('/admin/standards', null);
    if (!links.value.length) links.value = await getData('/admin/course-skill-links', []);
    await loadCourses();
    await loadBanks();
    await loadMaterials();
  }
  if (key === 'examConfig') {
    if (!examConfig.value) examConfig.value = await getData('/admin/exam-config', null);
    if (!orgs.value.length) orgs.value = await getData('/admin/orgs', []);
    if (!positions.value.length) positions.value = await getData('/admin/positions', []);
    await loadExams();
    await loadPapers();
  }
  if (key === 'audit') await loadAudit();
};
watch(() => props.tab, (value) => { current.value = value; load(); });
// 考试配置页：员工陆续进入 / 交卷时自动刷新「已进入 / 已交卷」，管理员不必手动刷新
let examPoll = null;
watch(current, (value) => {
  load();
  if (examPoll) { clearInterval(examPoll); examPoll = null; }
  if (value === 'examConfig') examPoll = setInterval(loadExams, 10000);
});
onMounted(load);

const readError = (error, fallback) => {
  const payload = error && error.response && error.response.data ? error.response.data : null;
  if (payload && payload.code === 40001 && payload.data && payload.data.field_errors) {
    return { fields: payload.data.field_errors, message: payload.message };
  }
  return { fields: {}, message: fallback };
};

const uploadMaterial = async () => {
  uploadBusy.value = true;
  uploadErrors.value = {};
  uploadResult.value = null;
  try {
    const response = await api.post('/admin/course-materials', { ...uploadForm.value });
    const payload = response.data || {};
    if (payload.code !== 0) {
      uploadErrors.value = (payload.data && payload.data.field_errors) || {};
      uploadResult.value = { ok: false, message: payload.message };
      return;
    }
    uploadResult.value = { ok: true, message: payload.data.message, material: payload.data.material };
    uploadForm.value = { file_name: '', target: uploadForm.value.target, note: '' };
    await loadMaterials();
  } catch (error) {
    const info = readError(error, '上传失败，请确认后端服务已启动（8080）。');
    uploadErrors.value = info.fields;
    uploadResult.value = { ok: false, message: info.message };
  } finally {
    uploadBusy.value = false;
  }
};

const openUploadDialog = () => {
  uploadErrors.value = {};
  uploadResult.value = null;
  uploadDialog.value.visible = true;
};

const closeUploadDialog = () => {
  uploadDialog.value.visible = false;
  uploadErrors.value = {};
  uploadResult.value = null;
};

const reviewCourse = async (item, action) => {
  reviewBusy.value = item.code;
  reviewMessage.value = '';
  try {
    const response = await api.post('/admin/courses/review', { course_code: item.code, action });
    reviewMessage.value = response.data.data.reviewed
      ? item.code + ' 已' + (action === 'approve' ? '通过（已上线）' : '驳回')
      : response.data.data.message;
    await loadCourses();
  } catch (error) {
    reviewMessage.value = '审核失败，请确认后端服务已启动（8080）。';
  } finally {
    reviewBusy.value = '';
  }
};

// 待审核弹窗：先看原件信息、原件摘录与 Agent 检索结果，核对无误再点「确认入库」
const openMaterial = async (item) => {
  materialDialog.value = { visible: true, loading: true, busy: false, detail: null, message: '' };
  try {
    const response = await api.get('/admin/course-materials/' + item.code);
    materialDialog.value.detail = response.data.data;
  } catch (error) {
    materialDialog.value.message = '读取资料详情失败，请确认后端服务已启动（8080）。';
  } finally {
    materialDialog.value.loading = false;
  }
};

const storeMaterial = async (action) => {
  const detail = materialDialog.value.detail;
  if (!detail) return;
  materialDialog.value.busy = true;
  materialDialog.value.message = '';
  try {
    const response = await api.post('/admin/course-materials/review', { code: detail.material.code, action });
    const data = response.data.data;
    materialDialog.value.message = data.reviewed ? data.message : data.message;
    await loadMaterials();
    await loadCourses();
    await loadBanks();
    const refreshed = await api.get('/admin/course-materials/' + detail.material.code);
    materialDialog.value.detail = refreshed.data.data;
  } catch (error) {
    materialDialog.value.message = '审核失败，请确认后端服务已启动（8080）。';
  } finally {
    materialDialog.value.busy = false;
  }
};

const startExam = async (exam) => {

  examBusy.value = exam.exam_id;
  examMessage.value = '';
  try {
    const response = await api.post('/admin/exams/start', { exam_id: String(exam.exam_id) });
    const data = response.data.data;
    examMessage.value = data.started
      ? '已统一开考：' + exam.name + '（' + data.scope + '，' + data.participants + ' 人，可抽 ' + data.available_questions + ' 题）员工端已可进入答题'
      : data.message;
    await loadExams();
  } catch (error) {
    examMessage.value = '开考失败，请确认后端服务已启动（8080）。';
  } finally {
    examBusy.value = '';
  }
};

// 结束本场：员工端随即不能再进入；需要重考时再点一次「开始考试」开启新一轮并重新发卷
const closeExam = async (exam) => {
  examBusy.value = exam.exam_id;
  examMessage.value = '';
  try {
    const response = await api.post('/admin/exams/close', { exam_id: String(exam.exam_id) });
    const data = response.data.data;
    examMessage.value = data.message || '已结束本场考试';
    await loadExams();
  } catch (error) {
    examMessage.value = '结束考试失败，请确认后端服务已启动（8080）。';
  } finally {
    examBusy.value = '';
  }
};

// 发放对象：常用范围 / 班组中心 / 岗位都直接选，选到有在册人数的范围时自动带出份数，仍可手工改
const scopeGroups = computed(() => [
  {
    key: 'common',
    label: '常用范围',
    items: ['全体值班员', '全体员工', '全体班组长'].map((name) => ({ value: name, label: name, hint: '全部相关班组' }))
  },
  {
    key: 'org',
    label: '班组 / 中心',
    items: orgs.value
      .filter((org) => org.type !== '公司')
      .map((org) => ({ value: org.name, label: org.name, hint: org.type + ' · 在册 ' + org.headcount + ' 人', people: org.headcount }))
  },
  {
    key: 'post',
    label: '岗位',
    items: positions.value
      .map((post) => ({ value: post.name, label: post.name, hint: post.org + ' · 在册 ' + post.headcount + ' 人', people: post.headcount }))
  }
].filter((group) => group.items.length));

const onScopeChange = (value) => {
  const picked = scopeGroups.value.flatMap((group) => group.items).find((item) => item.value === value);
  const count = String(issueForm.value.count || '').trim();
  // 只在份数为空或还是上一次自动带出的值时覆盖，避免冲掉管理员手填的份数
  if (!picked || !picked.people || (count !== '' && count !== scopeAutoCount)) return;
  issueForm.value.count = String(picked.people);
  scopeAutoCount = String(picked.people);
};

// 发放弹窗：和「上传课程 / 题库资料」一致，点按钮打开弹窗填表，提交结果留在弹窗里
const openIssueDialog = () => {
  issueErrors.value = {};
  issueResult.value = null;
  issueDialog.value.visible = true;
};

const closeIssueDialog = () => {
  issueDialog.value.visible = false;
  issueErrors.value = {};
  issueResult.value = null;
};

const issuePaper = async () => {
  issueErrors.value = {};
  issueResult.value = null;
  try {
    const response = await api.post('/admin/papers/issue', { ...issueForm.value });
    const payload = response.data || {};
    if (payload.code !== 0) {
      issueErrors.value = (payload.data && payload.data.field_errors) || {};
      issueResult.value = { ok: false, message: payload.message };
      return;
    }
    issueResult.value = { ok: true, message: payload.data.message + '（批次 ' + payload.data.paper.batch_no + '）', paper: payload.data.paper };
    scopeAutoCount = '';
    issueForm.value = { exam_id: '', scope: '', count: '', deadline: '' };
    await loadPapers();
    await loadExams();
  } catch (error) {
    const info = readError(error, '发放失败，请确认后端服务已启动（8080）。');
    issueErrors.value = info.fields;
    issueResult.value = { ok: false, message: info.message };
  }
};

const applySearch = async () => { clearArmed.value = false; await loadAudit(); };
const resetSearch = async () => {
  search.value = { category: '', keyword: '' };
  clearArmed.value = false;
  auditMessage.value = '已清除筛选条件';
  await loadAudit();
};
// 类别标签即筛选器：再点一次同一个标签即取消筛选
const filterCategory = async (key) => {
  search.value.category = search.value.category === key ? '' : key;
  clearArmed.value = false;
  await loadAudit();
};
const clearAudit = async () => {
  if (!clearArmed.value) {
    clearArmed.value = true;
    auditMessage.value = '再次点击「清除留痕」确认清空历史记录（会保留 1 条清除记录）';
    return;
  }
  clearArmed.value = false;
  try {
    const response = await api.post('/admin/audit/clear', { confirm: 'true' });
    auditMessage.value = response.data.data.message;
    await loadAudit();
  } catch (error) {
    auditMessage.value = '清除失败，请确认后端服务已启动（8080）。';
  }
};
</script>
<template>
  <section class="role-page">
    <div class="panel role-banner">
      <p><b>系统管理员控制台</b>：维护用户 / 角色 / 组织 / 岗位与权限、技能 / 课程 / 题库（上传资料由 Agent 识别入库并审核）、考试配置与统一开考发卷、审计与审核留痕；不展示员工个人页面与老总页面。</p>
      <span class="chip info">PLATFORM 范围</span>
    </div>

    <!-- 1. 用户与权限 -->
    <template v-if="current === 'iam'">
      <p v-if="!iam" class="empty-tip">数据加载中，或后端服务未启动…</p>
      <template v-else>
        <div class="panel">
          <div class="panel-title"><h2>平台数据规模</h2><span class="metric-note">仅统计数据，不含个人画像；待审核 {{ iam.summary.pending_reviews }} 项</span></div>
          <div class="grid-4" v-if="overview">
            <div class="info-item"><label>员工档案</label><span>{{ overview.employees }} 人 / {{ overview.teams }} 班组</span></div>
            <div class="info-item"><label>课程 / 题库</label><span>{{ overview.courses }} 门 / {{ overview.questions }} 题</span></div>
            <div class="info-item"><label>考试配置 / 已发试卷</label><span>{{ overview.exams }} 套 / {{ overview.papers_issued }} 批</span></div>
            <div class="info-item"><label>实操报告</label><span>{{ overview.reports }} 份</span></div>
            <div class="info-item"><label>审计事件</label><span>{{ overview.audit_events }} 条</span></div>
            <div class="info-item"><label>存储占用</label><span>{{ overview.storage }}</span></div>
            <div class="info-item"><label>最近备份</label><span>{{ overview.last_backup }}</span></div>
            <div class="info-item"><label>服务状态</label><span>{{ overview.service_status }}</span></div>
          </div>
          <p class="role-note">{{ iam.summary.note }}</p>
        </div>

        <div class="panel">
          <div class="panel-title"><h2>用户与角色</h2><span class="metric-note">账号 {{ iam.summary.users }} 人 · {{ iam.summary.roles }} 类角色</span></div>
          <div class="table-wrap">
            <table class="role-table">
              <thead><tr><th>账号</th><th>姓名</th><th>角色</th><th>组织</th><th>岗位</th><th>页面范围</th><th>状态</th><th>最近登录</th></tr></thead>
              <tbody>
                <tr v-for="user in iam.users" :key="user.username">
                  <td class="num">{{ user.username }}</td>
                  <td><b>{{ user.name }}</b></td>
                  <td>{{ user.role_name }}</td>
                  <td>{{ user.org }}</td>
                  <td>{{ user.position }}</td>
                  <td><span class="chip info">{{ user.scope }}</span></td>
                  <td><span :class="user.status === '在职' ? 'chip ok' : 'chip warn'">{{ user.status }}</span></td>
                  <td class="num">{{ user.last_login }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="panel">
          <div class="panel-title"><h2>角色权限</h2><span class="metric-note">按角色统一放行，不按人单独开权</span></div>
          <div class="table-wrap">
            <table class="role-table">
              <thead><tr><th>角色编码</th><th>角色名称</th><th>页面范围</th><th class="num">可见模块</th><th class="num">人数</th><th>说明</th></tr></thead>
              <tbody>
                <tr v-for="role in iam.roles" :key="role.code">
                  <td class="num">{{ role.code }}</td>
                  <td><b>{{ role.name }}</b></td>
                  <td><span class="chip">{{ role.scope }}</span></td>
                  <td class="num">{{ role.modules }}</td>
                  <td class="num">{{ role.members }}</td>
                  <td>{{ role.note }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="grid-2">
          <div class="panel">
            <div class="panel-title"><h2>组织结构</h2><span class="metric-note">{{ orgs.length }} 个节点</span></div>
            <div class="table-wrap">
              <table class="role-table">
                <thead><tr><th>组织</th><th>类型</th><th>上级</th><th class="num">人数</th><th>负责人</th></tr></thead>
                <tbody>
                  <tr v-for="org in orgs" :key="org.name">
                    <td><b>{{ org.name }}</b></td>
                    <td>{{ org.type }}</td>
                    <td>{{ org.parent }}</td>
                    <td class="num">{{ org.headcount }}</td>
                    <td>{{ org.leader }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div class="panel">
            <div class="panel-title"><h2>岗位与备份</h2><span class="metric-note">{{ positions.length }} 个岗位</span></div>
            <div class="table-wrap">
              <table class="role-table">
                <thead><tr><th>岗位</th><th>组织</th><th>岗位技能要求</th><th>关键岗位</th><th class="num">在岗</th><th class="num">备份</th><th>风险</th></tr></thead>
                <tbody>
                  <tr v-for="post in positions" :key="post.name">
                    <td><b>{{ post.name }}</b></td>
                    <td>{{ post.org }}</td>
                    <td>{{ post.required }}</td>
                    <td><span :class="post.key_post ? 'chip warn' : 'chip'">{{ post.key_post ? '是' : '否' }}</span></td>
                    <td class="num">{{ post.headcount }}</td>
                    <td class="num">{{ post.backup }}</td>
                    <td><span :class="riskClass(post.risk)">{{ post.risk }}</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-title"><h2>权限矩阵</h2><span class="metric-note">行=模块，列=角色</span></div>
          <div class="table-wrap">
            <table class="role-table">
              <thead><tr><th>模块</th><th>员工</th><th>组长</th><th>公司上级</th><th>系统管理员</th><th>说明</th></tr></thead>
              <tbody>
                <tr v-for="row in permissions" :key="row.module">
                  <td><b>{{ row.module }}</b></td>
                  <td>{{ row.employee }}</td>
                  <td>{{ row.team_lead }}</td>
                  <td>{{ row.executive }}</td>
                  <td>{{ row.admin }}</td>
                  <td>{{ row.note }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="panel">
          <div class="panel-title"><h2>员工档案</h2><span class="metric-note">{{ employees.length }} 条</span></div>
          <div class="table-wrap">
            <table class="role-table">
              <thead><tr><th>工号</th><th>姓名</th><th>班组</th><th>岗位</th><th>账号身份</th><th>技能等级</th><th class="num">证书</th><th>状态</th><th>最近活跃</th></tr></thead>
              <tbody>
                <tr v-for="item in employees" :key="item.emp_no">
                  <td class="num">{{ item.emp_no }}</td>
                  <td><b>{{ item.name }}</b></td>
                  <td>{{ item.team }}</td>
                  <td>{{ item.position }}</td>
                  <td>{{ item.account_role }}</td>
                  <td>{{ item.skill_level }}</td>
                  <td class="num">{{ item.certificates }}</td>
                  <td><span class="chip ok">{{ item.status }}</span></td>
                  <td class="num">{{ item.last_active }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </template>
    <!-- 2. 技能与课程：上传 → Agent 识别 → 审核入库 -->
    <template v-else-if="current === 'content'">
      <div class="panel">
        <div class="panel-title">
          <div>
            <h2>上传课程 / 题库资料</h2>
            <small class="chart-caption">{{ (materialData && materialData.format_hint) || '规定格式：技能编码_名称_等级_版本.pdf' }}</small>
          </div>
          <div class="panel-title-actions">
            <span class="metric-note">上传后由课程 Agent 识别，管理员审核通过才入库</span>
            <button class="action-button primary" @click="openUploadDialog">上传课程 / 题库资料</button>
          </div>
        </div>

        <p v-if="reviewMessage" class="empty-note">{{ reviewMessage }}</p>

        <div class="table-wrap" style="margin-top: 14px">
          <table class="role-table">
            <thead><tr><th>编号</th><th>文件名</th><th>技能</th><th>入库目标</th><th class="num">识别条目</th><th class="num">等级</th><th>状态</th><th>识别结果</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="item in (materialData ? materialData.items : [])" :key="item.code">
                <td class="num">{{ item.code }}</td>
                <td><b>{{ item.file_name }}</b></td>
                <td>{{ item.skill }}</td>
                <td><span class="chip info">{{ item.target }}</span></td>
                <td class="num">{{ item.recognized_items }}</td>
                <td class="num">{{ item.target_level }}</td>
                <td>
                  <button class="chip-button" :class="statusClass(item.status)" :title="'查看原件与 Agent 检索结果：' + item.code" @click="openMaterial(item)">
                    {{ item.status }}{{ item.status === '待审核' ? ' · 点此审核' : '' }}
                  </button>
                </td>
                <td>{{ item.stored_result || item.agent_note }}</td>
                <td>
                  <button class="action-button" :class="{ active: item.status === '待审核' }" @click="openMaterial(item)">{{ item.status === '待审核' ? '查看并审核' : '查看记录' }}</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-title"><h2>课程库</h2><span class="metric-note">{{ courseData ? courseData.summary.total : 0 }} 门 · 待审核 {{ courseData ? courseData.summary.pending_review : 0 }}</span></div>
        <div class="table-wrap">
          <table class="role-table">
            <thead><tr><th>课程编号</th><th>课程名称</th><th>类型</th><th class="num">学时</th><th>关联技能</th><th class="num">目标等级</th><th>状态</th><th>来源文件</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="course in (courseData ? courseData.items : [])" :key="course.code">
                <td class="num">{{ course.code }}</td>
                <td><b>{{ course.name }}</b></td>
                <td>{{ course.type }}</td>
                <td class="num">{{ course.hours }}</td>
                <td>{{ course.skill }}</td>
                <td class="num">{{ course.target_level }}</td>
                <td><span :class="statusClass(course.status)">{{ course.status }}</span></td>
                <td>{{ course.source_file || '—' }}</td>
                <td>
                  <template v-if="course.status === '待审核'">
                    <button class="action-button active" :disabled="reviewBusy === course.code" @click="reviewCourse(course, 'approve')">通过</button>
                    <button class="action-button" :disabled="reviewBusy === course.code" @click="reviewCourse(course, 'reject')">驳回</button>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-title">
          <h2>岗位技能要求</h2>
          <span class="metric-note">L1-L3 为平台内部刻度；依据标准取自官网，可点开核对</span>
        </div>
        <p v-if="positionSkills && positionSkills.summary" class="role-note">{{ positionSkills.summary.note }}</p>
        <div v-if="positionSkills" class="table-wrap">
          <table class="role-table">
            <thead><tr><th>岗位</th><th>技能</th><th class="num">岗位要求</th><th class="num">未来需求</th><th>依据作用</th><th>依据标准（国家标准全文公开系统）</th><th>状态</th></tr></thead>
            <tbody>
              <tr v-for="row in positionSkills.items" :key="row.position + row.skill + row.basis.standard">
                <td><b>{{ row.position }}</b></td>
                <td>{{ row.skill }}</td>
                <td class="num">{{ row.required }}</td>
                <td class="num">{{ row.future }}</td>
                <td><span class="chip">{{ row.basis_role }}</span></td>
                <td><a class="source-link" :href="row.basis.url" target="_blank" rel="noreferrer">{{ row.basis.standard }} · {{ row.basis.name }}</a></td>
                <td><span :class="row.basis.status === '现行' ? 'chip ok' : 'chip warn'">{{ row.basis.status }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-title">
          <h2>标准依据库（官网抓取）</h2>
          <span class="metric-note">{{ standards ? standards.summary.total : 0 }} 条 · 现行 {{ standards ? standards.summary.current : 0 }} 条</span>
        </div>
        <p v-if="standards" class="role-note">
          来源：<a class="source-link" :href="standards.source_url" target="_blank" rel="noreferrer">{{ standards.source }}</a>
          · 抓取时间 {{ standards.fetched_at }} · {{ standards.note }}
        </p>
        <div v-if="standards" class="table-wrap">
          <table class="role-table">
            <thead><tr><th>标准号</th><th>标准名称</th><th>状态</th><th class="num">发布日期</th><th class="num">实施日期</th><th>官网核对</th></tr></thead>
            <tbody>
              <tr v-for="std in standards.items" :key="std.standard">
                <td><b>{{ std.standard }}</b></td>
                <td>{{ std.name }}</td>
                <td><span :class="std.status === '现行' ? 'chip ok' : 'chip warn'">{{ std.status }}</span></td>
                <td class="num">{{ std.published || '—' }}</td>
                <td class="num">{{ std.implemented || '—' }}</td>
                <td><a class="source-link" :href="std.url" target="_blank" rel="noreferrer">官网核对</a></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-title"><h2>技能字典</h2><span class="metric-note">{{ skills.length }} 项核心技能</span></div>
        <div class="table-wrap">
          <table class="role-table">
            <thead><tr><th>编码</th><th>技能</th><th>等级定义</th><th class="num">关联课程</th><th class="num">岗位要求</th><th>说明</th></tr></thead>
            <tbody>
              <tr v-for="skill in skills" :key="skill.code">
                <td class="num">{{ skill.code }}</td>
                <td><b>{{ skill.name }}</b></td>
                <td>{{ skill.levels }}</td>
                <td class="num">{{ skill.courses }}</td>
                <td class="num">{{ skill.requirements }}</td>
                <td>{{ skill.note }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-title"><h2>题库</h2><span class="metric-note">{{ banks.length }} 个题库</span></div>
        <div class="table-wrap">
          <table class="role-table">
            <thead><tr><th>题库编号</th><th>题库</th><th>关联技能</th><th class="num">题量</th><th>题型分布</th><th>难度</th><th>更新时间</th><th class="num">被考试引用</th></tr></thead>
            <tbody>
              <tr v-for="bank in banks" :key="bank.code">
                <td class="num">{{ bank.code }}</td>
                <td><b>{{ bank.name }}</b></td>
                <td>{{ bank.skill }}</td>
                <td class="num">{{ bank.questions }}</td>
                <td>{{ bank.types }}</td>
                <td>{{ bank.difficulty }}</td>
                <td class="num">{{ bank.updated_at }}</td>
                <td class="num">{{ bank.used_by }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="table-wrap" style="margin-top: 12px">
          <table class="role-table">
            <thead><tr><th>课程</th><th>关联技能</th><th class="num">目标等级</th><th>关联类型</th><th>权重</th></tr></thead>
            <tbody>
              <tr v-for="link in links" :key="link.course + link.skill + link.link_type">
                <td>{{ link.course }}</td>
                <td><b>{{ link.skill }}</b></td>
                <td class="num">{{ link.target_level }}</td>
                <td>{{ link.link_type }}</td>
                <td>{{ link.weight }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
    <!-- 3. 考试配置：统一开考 + 发放试卷 -->
    <template v-else-if="current === 'examConfig'">
      <p v-if="!examConfig" class="empty-tip">数据加载中，或后端服务未启动…</p>
      <template v-else>
        <div class="grid-4">
          <div class="info-item"><label>组卷规则</label><span>{{ examConfig.summary.paper_rules }} 套</span></div>
          <div class="info-item"><label>防作弊规则</label><span>{{ examConfig.summary.anti_cheat }} 项</span></div>
          <div class="info-item"><label>评分规则</label><span>{{ examConfig.summary.scoring }} 项</span></div>
          <div class="info-item"><label>及格线</label><span>{{ examConfig.summary.pass_lines }} 类考试</span></div>
        </div>

        <div class="panel">
          <div class="panel-title"><h2>考试清单（统一开考）</h2><span class="metric-note">{{ exams ? exams.summary.note : '' }} · 点「开始考试」后员工端立即出现可点的「进入考试」，结束本场则关闭入口</span></div>
          <p v-if="examMessage" class="empty-note">{{ examMessage }}</p>
          <div class="table-wrap">
            <table class="role-table">
              <thead><tr><th>ID</th><th>考试名称</th><th>类型</th><th class="num">合格线</th><th class="num">配置题量</th><th class="num">题库可抽</th><th class="num">时长</th><th>发放对象</th><th class="num">参考人数</th><th class="num">已进入</th><th class="num">已交卷</th><th>状态</th><th>开始时间</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="exam in (exams ? exams.items : [])" :key="exam.exam_id">
                  <td class="num">{{ exam.exam_id }}</td>
                  <td><b>{{ exam.name }}</b></td>
                  <td>{{ exam.exam_type }}</td>
                  <td class="num">{{ exam.pass_score }}</td>
                  <td class="num">{{ exam.question_count }}</td>
                  <td class="num">{{ exam.available_questions == null ? "—" : exam.available_questions }}</td>
                  <td class="num">{{ exam.duration_minutes }} 分钟</td>
                  <td>{{ exam.scope }}</td>
                  <td class="num">{{ exam.participants }}</td>
                  <td class="num">{{ exam.entered == null ? 0 : exam.entered }}</td>
                  <td class="num">{{ exam.submitted == null ? 0 : exam.submitted }}</td>
                  <td><span :class="exam.enabled ? statusClass(exam.status) : 'chip'">{{ exam.enabled ? exam.status : '未启用' }}</span></td>
                  <td class="num">{{ exam.started_at }}</td>
                  <td>
                    <div class="role-toolbar">
                      <button class="action-button active" :disabled="!exam.enabled || exam.status === '进行中' || examBusy === exam.exam_id" @click="startExam(exam)">
                        {{ exam.status === '进行中' ? '考试进行中' : '开始考试' }}
                      </button>
                      <button v-if="exam.status === '进行中'" class="action-button" :disabled="examBusy === exam.exam_id" @click="closeExam(exam)">结束本场</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="panel">
          <div class="panel-title">
            <h2>发放试卷</h2>
            <div class="panel-title-actions">
              <span class="metric-note">按批次发放并留痕</span>
              <button class="action-button primary" @click="openIssueDialog">发放试卷</button>
            </div>
          </div>

          <div class="table-wrap" style="margin-top: 14px">
            <table class="role-table">
              <thead><tr><th>批次号</th><th>考试</th><th>发放对象</th><th class="num">份数</th><th>发放时间</th><th>截止</th><th class="num">已回收</th><th>状态</th></tr></thead>
              <tbody>
                <tr v-for="item in papers" :key="item.batch_no">
                  <td class="num">{{ item.batch_no }}</td>
                  <td>{{ item.exam_name }}</td>
                  <td>{{ item.issued_to }}</td>
                  <td class="num">{{ item.count }}</td>
                  <td class="num">{{ item.issued_at }}</td>
                  <td class="num">{{ item.deadline }}</td>
                  <td class="num">{{ item.collected }}</td>
                  <td><span :class="statusClass(item.status)">{{ item.status }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="panel">
          <div class="panel-title"><h2>组卷规则</h2><span class="metric-note">题型配比 + 抽题范围 + 及格线</span></div>
          <div class="table-wrap">
            <table class="role-table">
              <thead><tr><th>规则</th><th>适用考试</th><th>题型配比</th><th>抽题范围</th><th class="num">及格线</th><th>状态</th></tr></thead>
              <tbody>
                <tr v-for="row in examConfig.paper_rules" :key="row.name">
                  <td><b>{{ row.name }}</b></td>
                  <td>{{ row.exam }}</td>
                  <td>{{ row.mix }}</td>
                  <td>{{ row.scope }}</td>
                  <td class="num">{{ row.pass_line }}</td>
                  <td><span :class="row.enabled ? 'chip ok' : 'chip'">{{ row.enabled ? '已启用' : '未启用' }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="grid-2">
          <div class="panel">
            <div class="panel-title"><h2>防作弊规则</h2><span class="metric-note">{{ examConfig.anti_cheat.length }} 项</span></div>
            <div class="table-wrap">
              <table class="role-table">
                <thead><tr><th>项目</th><th>配置值</th><th>说明</th></tr></thead>
                <tbody>
                  <tr v-for="row in examConfig.anti_cheat" :key="row.item">
                    <td><b>{{ row.item }}</b></td>
                    <td>{{ row.value }}</td>
                    <td>{{ row.detail }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div class="panel">
            <div class="panel-title"><h2>评分规则</h2><span class="metric-note">{{ examConfig.scoring.length }} 项</span></div>
            <div class="table-wrap">
              <table class="role-table">
                <thead><tr><th>评分项</th><th>规则</th><th>取值</th><th>说明</th></tr></thead>
                <tbody>
                  <tr v-for="row in examConfig.scoring" :key="row.item">
                    <td><b>{{ row.item }}</b></td>
                    <td>{{ row.rule }}</td>
                    <td>{{ row.value }}</td>
                    <td>{{ row.detail }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-title"><h2>及格线</h2><span class="metric-note">按考试类型分别设定</span></div>
          <div class="table-wrap">
            <table class="role-table">
              <thead><tr><th>考试类型</th><th class="num">及格线</th><th>补考</th><th>说明</th></tr></thead>
              <tbody>
                <tr v-for="row in examConfig.pass_lines" :key="row.exam_type">
                  <td><b>{{ row.exam_type }}</b></td>
                  <td class="num">{{ row.pass_line }}</td>
                  <td>{{ row.retake }}</td>
                  <td>{{ row.detail }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </template>
    <!-- 4. 审计日志与审核：行内关键词搜索 + 清除 -->
    <template v-else-if="current === 'audit'">
      <p v-if="!audit" class="empty-tip">数据加载中，或后端服务未启动…</p>
      <template v-else>
        <div class="panel role-banner">
          <p>{{ audit.summary.note }}</p>
          <div class="role-toolbar">
            <span class="chip info">共 {{ audit.summary.total }} 条</span>
            <span class="chip ok">命中 {{ audit.summary.matched }} 条</span>
            <button
              v-for="(count, key) in audit.categories"
              :key="key"
              type="button"
              class="chip chip-button"
              :class="{ active: search.category === key }"
              :title="'只看「' + key + '」类别，再点一次取消'"
              @click="filterCategory(key)"
            >{{ key }} {{ count }}</button>
          </div>
        </div>

        <div class="panel">
          <div class="panel-title audit-title">
            <h2>操作留痕</h2>
            <div class="audit-search">
              <el-input
                v-model="search.keyword"
                placeholder="搜索操作人 / 操作 / 对象 / IP，回车即搜"
                clearable
                @keyup.enter="applySearch"
                @clear="applySearch"
              />
              <button class="action-button primary" @click="applySearch">搜索</button>
              <button class="action-button" @click="resetSearch">清除筛选</button>
              <button class="action-button" :class="{ active: clearArmed }" @click="clearAudit">{{ clearArmed ? '确认清除留痕' : '清除留痕' }}</button>
            </div>
            <span class="metric-note">{{ audit.items.length }} 条</span>
          </div>
          <p v-if="auditMessage" class="empty-note audit-note">{{ auditMessage }}</p>
          <div class="table-wrap">
            <table class="role-table">
              <thead><tr><th>ID</th><th>时间</th><th>类别</th><th>操作人</th><th>身份</th><th>操作</th><th>对象</th><th>结果</th><th>IP</th></tr></thead>
              <tbody>
                <tr v-for="item in audit.items" :key="item.id">
                  <td class="num">{{ item.id }}</td>
                  <td class="num">{{ item.occurred_at }}</td>
                  <td><span :class="categoryClass(item.category)">{{ item.category }}</span></td>
                  <td><b>{{ item.actor }}</b></td>
                  <td>{{ item.actor_role }}</td>
                  <td>{{ item.action }}</td>
                  <td>{{ item.target }}</td>
                  <td><span :class="resultClass(item.result)">{{ item.result }}</span></td>
                  <td class="num">{{ item.ip }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="!audit.items.length" class="empty-note">没有符合条件的记录，换个关键词或点类别标签再试。</p>
        </div>
      </template>
    </template>
    <!-- 上传弹窗：点页面右上角「上传课程 / 题库资料」按钮后，在这里填文件信息并提交 Agent 识别 -->
    <el-dialog v-model="uploadDialog.visible" title="上传课程 / 题库资料" width="880px" top="8vh" class="practice-dialog" @closed="closeUploadDialog">
      <p class="dialog-note">上传后由课程 Agent 识别章节 / 题目，管理员审核通过才入库。</p>
      <div class="sop-grid">
        <div class="sop-field">
          <label>文件名（含后缀） <i>*</i></label>
          <el-input v-model="uploadForm.file_name" placeholder="例如：SK-REL_软压板逻辑_L2_v1.pdf" :disabled="uploadBusy" />
          <small v-if="uploadErrors.file_name" class="field-error">{{ uploadErrors.file_name }}</small>
          <small>规定格式：技能编码_名称_等级_版本.pdf；允许 pdf / docx / pptx / xlsx / mp4 / zip</small>
        </div>
        <div class="sop-field">
          <label>入库目标 <i>*</i></label>
          <el-select v-model="uploadForm.target" style="width: 100%" :disabled="uploadBusy">
            <el-option label="课程库" value="课程库" />
            <el-option label="题库" value="题库" />
          </el-select>
          <small v-if="uploadErrors.target" class="field-error">{{ uploadErrors.target }}</small>
          <small>课程库：Agent 识别章节后生成课程；题库：Agent 解析题目后累加到题库</small>
        </div>
        <div class="sop-field">
          <label>备注</label>
          <el-input v-model="uploadForm.note" placeholder="例如：含软压板投退顺序图解" :disabled="uploadBusy" />
        </div>
      </div>

      <div v-if="uploadResult" class="role-toolbar" style="margin-top: 12px">
        <span :class="uploadResult.ok ? 'chip ok' : 'chip bad'">{{ uploadResult.message }}</span>
      </div>
      <div v-if="uploadResult && uploadResult.ok" class="grid-4" style="margin-top: 12px">
        <div class="info-item"><label>资料编号</label><span>{{ uploadResult.material.code }}</span></div>
        <div class="info-item"><label>识别技能 / 等级</label><span>{{ uploadResult.material.skill }} · {{ uploadResult.material.target_level }}</span></div>
        <div class="info-item"><label>识别条目</label><span>{{ uploadResult.material.recognized_items }} {{ uploadResult.material.target === '题库' ? '道题' : '个章节' }}</span></div>
        <div class="info-item"><label>状态</label><span>{{ uploadResult.material.status }}（待管理员审核）</span></div>
      </div>
      <p v-if="uploadResult && uploadResult.ok" class="role-note">{{ uploadResult.material.agent_note }}</p>

      <template #footer>
        <button class="action-button" @click="uploadDialog.visible = false">关闭</button>
        <button class="action-button primary" :disabled="uploadBusy" @click="uploadMaterial">{{ uploadBusy ? '上传识别中…' : '上传并执行 Agent 识别' }}</button>
      </template>
    </el-dialog>

    <!-- 待审核弹窗：先看原件信息 + 原件摘录 + Agent 检索结果，核对无误再点「确认入库」 -->
    <el-dialog v-model="materialDialog.visible" :title="materialDialog.detail ? '资料审核 · ' + materialDialog.detail.material.file_name : '资料审核'" width="1040px" top="4vh" class="practice-dialog">
      <p v-if="materialDialog.loading" class="empty-tip">正在读取原件与 Agent 检索结果…</p>
      <template v-else-if="materialDialog.detail">
        <div class="material-banner">
          <span :class="materialDialog.detail.already_stored ? 'chip ok' : 'chip warn'">
            {{ materialDialog.detail.already_stored ? '已入库 · ' + materialDialog.detail.material.status : '待审核 · 未入库' }}
          </span>
          <span class="chip info">{{ materialDialog.detail.extracted.mode }}</span>
          <span class="chip">Agent 置信度 {{ materialDialog.detail.material.agent_confidence }}</span>
          <span class="metric-note">{{ materialDialog.detail.material.agent_note }}</span>
        </div>

        <div class="section-title" style="margin-top: 6px">
          <h3>原件信息</h3>
          <span class="metric-note">入库前请核对文件、技能、等级与目标是否对应</span>
        </div>
        <div class="grid-4">
          <div class="info-item"><label>文件名</label><span>{{ materialDialog.detail.file.file_name }}</span></div>
          <div class="info-item"><label>类型 / 页数 / 大小</label><span>{{ materialDialog.detail.file.file_type }} · {{ materialDialog.detail.file.pages }} 页 · {{ materialDialog.detail.file.size_kb }} KB</span></div>
          <div class="info-item"><label>上传人 / 时间</label><span>{{ materialDialog.detail.file.uploaded_by }} · {{ materialDialog.detail.file.uploaded_at }}</span></div>
          <div class="info-item"><label>技能 / 等级 / 版本</label><span>{{ materialDialog.detail.material.skill }} · {{ materialDialog.detail.material.target_level }} · {{ materialDialog.detail.material.version }}</span></div>
        </div>
        <p class="role-note">原件地址：<code>{{ materialDialog.detail.file.url }}</code>；{{ materialDialog.detail.file.preview_note }}</p>

        <div class="section-title">
          <h3>原件摘录</h3>
          <span class="metric-note">Agent 读到的正文，用来核对它的理解是否准确</span>
        </div>
        <ol class="doc-excerpt">
          <li v-for="(line, index) in materialDialog.detail.doc_excerpt" :key="index">{{ line }}</li>
        </ol>

        <div class="section-title">
          <h3>{{ materialDialog.detail.extracted.mode === '题库' ? 'Agent 检索结果（题目 + 答案 + 解析）' : 'Agent 检索结果（知识章节）' }}</h3>
          <span class="metric-note">共 {{ materialDialog.detail.extracted.total }} 条，本页列出 {{ materialDialog.detail.extracted.listed }} 条{{ materialDialog.detail.extracted.has_more ? '（其余入库后在题库 / 课程库查看）' : '' }}</span>
        </div>
        <p class="role-note">{{ materialDialog.detail.extracted.summary }}</p>

        <div v-if="materialDialog.detail.extracted.mode === '题库'" class="material-question-list">
          <div v-for="row in materialDialog.detail.extracted.items" :key="row.index" class="practice-item">
            <div class="practice-head">
              <span class="chip">第 {{ row.index }} 题</span>
              <span class="chip info">{{ row.type }}</span>
              <span class="chip">{{ row.knowledge }}</span>
              <span v-if="row.difficulty" class="chip">难度 {{ row.difficulty }}</span>
              <span v-if="row.status" :class="row.status === '已入库' ? 'chip ok' : row.status === '已驳回' ? 'chip bad' : 'chip warn'">{{ row.status }}</span>
              <span v-if="row.question_id" class="chip info">{{ row.question_id }}</span>
              <span class="metric-note">{{ row.source_page }}</span>
            </div>
            <p class="practice-stem">{{ row.question }}</p>
            <ul class="material-options">
              <li v-for="option in row.options" :key="option" :class="{ 'is-answer': option.startsWith(row.answer + '.') }">{{ option }}</li>
            </ul>
            <p class="material-answer">标准答案：{{ row.answer_text }}</p>
            <p class="material-analysis">解析：{{ row.analysis }}</p>
          </div>
        </div>
        <div v-else class="table-wrap">
          <table class="role-table">
            <thead><tr><th>序号</th><th>章节</th><th>学习要点</th><th class="num">学时</th><th>出处</th></tr></thead>
            <tbody>
              <tr v-for="row in materialDialog.detail.extracted.items" :key="row.index">
                <td class="num">{{ row.index }}</td>
                <td><b>{{ row.chapter }}</b></td>
                <td>{{ row.points }}</td>
                <td class="num">{{ row.hours }}</td>
                <td class="num">{{ row.source_page }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>

      <p v-if="materialDialog.message" class="review-result">{{ materialDialog.message }}</p>

      <template #footer>
        <span v-if="materialDialog.detail && materialDialog.detail.already_stored" class="metric-note">入库结果：{{ materialDialog.detail.stored_result }}</span>
        <button class="action-button" @click="materialDialog.visible = false">关闭</button>
        <template v-if="materialDialog.detail && !materialDialog.detail.already_stored">
          <button class="action-button" :disabled="materialDialog.busy" @click="storeMaterial('reject')">驳回（不入库）</button>
          <button class="action-button primary" :disabled="materialDialog.busy" @click="storeMaterial('approve')">{{ materialDialog.busy ? '入库中…' : '确认入库' }}</button>
        </template>
      </template>
    </el-dialog>

    <!-- 发放弹窗：点「发放试卷」按钮后，在这里选考试 / 发放对象 / 份数 / 截止日期，提交后按批次留痕 -->
    <el-dialog v-model="issueDialog.visible" title="发放试卷" width="880px" top="8vh" class="practice-dialog" @closed="closeIssueDialog">
      <p class="dialog-note">按批次发放并留痕：选好考试与发放对象后提交，员工端随即生成试卷任务，截止日期前回收。</p>
      <div class="sop-grid">
        <div class="sop-field">
          <label>考试 <i>*</i></label>
          <el-select v-model="issueForm.exam_id" placeholder="选择考试" style="width: 100%">
            <el-option v-for="exam in (exams ? exams.items : [])" :key="exam.exam_id" :label="exam.name" :value="String(exam.exam_id)" />
          </el-select>
          <small v-if="issueErrors.exam_id" class="field-error">{{ issueErrors.exam_id }}</small>
        </div>
        <div class="sop-field">
          <label>发放对象 <i>*</i></label>
          <el-select v-model="issueForm.scope" placeholder="例如：变电运维一班 / 全体值班员" filterable allow-create default-first-option clearable style="width: 100%" @change="onScopeChange">
            <el-option-group v-for="group in scopeGroups" :key="group.key" :label="group.label">
              <el-option v-for="item in group.items" :key="item.value" :label="item.label" :value="item.value">
                <span class="scope-option"><span>{{ item.label }}</span><small>{{ item.hint }}</small></span>
              </el-option>
            </el-option-group>
          </el-select>
          <small v-if="issueErrors.scope" class="field-error">{{ issueErrors.scope }}</small>
          <small>选班组 / 中心 / 岗位会自动带出在册人数；也可以直接输入自定义范围，例如：变电运维一班 / 二班</small>
        </div>
        <div class="sop-field">
          <label>份数 <i>*</i></label>
          <el-input v-model="issueForm.count" placeholder="例如：9" />
          <small v-if="issueErrors.count" class="field-error">{{ issueErrors.count }}</small>
        </div>
        <div class="sop-field">
          <label>截止日期 <i>*</i></label>
          <el-input v-model="issueForm.deadline" placeholder="yyyy-MM-dd，例如：2026-09-30" />
          <small v-if="issueErrors.deadline" class="field-error">{{ issueErrors.deadline }}</small>
        </div>
      </div>

      <div v-if="issueResult" class="role-toolbar" style="margin-top: 12px">
        <span :class="issueResult.ok ? 'chip ok' : 'chip bad'">{{ issueResult.message }}</span>
      </div>
      <div v-if="issueResult && issueResult.ok" class="grid-4" style="margin-top: 12px">
        <div class="info-item"><label>批次号</label><span>{{ issueResult.paper.batch_no }}</span></div>
        <div class="info-item"><label>考试</label><span>{{ issueResult.paper.exam_name }}</span></div>
        <div class="info-item"><label>发放对象</label><span>{{ issueResult.paper.issued_to }}</span></div>
        <div class="info-item"><label>份数 / 截止</label><span>{{ issueResult.paper.count }} 份 · {{ issueResult.paper.deadline }}</span></div>
      </div>

      <template #footer>
        <button class="action-button" @click="issueDialog.visible = false">关闭</button>
        <button class="action-button primary" @click="issuePaper">发放试卷</button>
      </template>
    </el-dialog>
  </section>
</template>
