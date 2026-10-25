<template>
  <section class="role-page">
    <div class="panel role-banner">
      <p>
        <b>{{ overview ? overview.team_name : '本班组' }} 实操报告台账</b>：{{
          overview ? overview.note : '每次实操活动都要上传一份检测报告。'
        }}
      </p>
      <div class="role-toolbar">
        <button class="action-button" @click="load">{{ loading ? '刷新中…' : '刷新台账' }}</button>
        <button class="action-button primary" @click="emit('go', 'tasks')">去实操任务填报 →</button>
      </div>
    </div>

    <div class="metrics five-metrics">
      <div v-for="item in metrics" :key="item.label" class="metric panel">
        <small>{{ item.label }}</small>
        <div class="metric-value">
          <b :class="{ warn: item.warn }">{{ item.value }}</b>
          <em>{{ item.unit }}</em>
        </div>
        <span :class="item.tone">{{ item.note }}</span>
      </div>
    </div>

    <div class="panel">
      <div class="panel-title">
        <h2>班组报告明细</h2>
        <span class="metric-note">{{ overview ? overview.leader : '' }}</span>
      </div>
      <div class="table-wrap">
        <table class="role-table">
          <thead>
            <tr>
              <th>执行组员</th>
              <th>填报人</th>
              <th>实操任务</th>
              <th>检测时间</th>
              <th>判定</th>
              <th>报告状态</th>
              <th>SOP 执行</th>
              <th>归因摘要</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in reports" :key="row.id">
              <td><b>{{ row.member }}</b></td>
              <td>{{ row.reporter || '李民（班组长填报）' }}</td>
              <td>{{ row.task_title }}</td>
              <td class="num">{{ row.detected_at }}</td>
              <td class="judge-cell">
                <span v-if="row.judgment" :class="judgeChipClass(row)">
                  <b>{{ row.judgment }}</b>
                  <em v-if="row.severity">{{ row.severity }}</em>
                </span>
                <span v-else class="judge-empty">—</span>
              </td>
              <td><span :class="statusClass(row.status)">{{ row.status === 'SUBMITTED' ? '已提交' : '缺报' }}</span></td>
              <td>
                <span v-if="row.sop_status" :class="sopClass(row.sop_status)">{{ sopText(row.sop_status) }}</span>
                <span v-else class="judge-empty">—</span>
              </td>
              <td>{{ row.summary }}</td>
              <td>
                <button
                  v-if="row.document_pdf"
                  type="button"
                  class="action-button"
                  :disabled="downloading === row.report_id"
                  @click="downloadDocument(row)"
                >
                  {{ downloading === row.report_id ? '下载中…' : '下载 PDF' }}
                </button>
                <button
                  v-else-if="row.status === 'MISSING'"
                  type="button"
                  class="action-button primary"
                  @click="emit('fill', row)"
                >
                  去补交
                </button>
                <span v-else class="metric-note">文档未归档</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="panel">
      <div class="panel-title">
        <div>
          <h2>{{ importTemplate ? importTemplate.title : '导入文档生成练习资料' }}</h2>
          <small class="chart-caption">
            {{ importTemplate ? importTemplate.notice : '组长导入 PDF / Word / 文本 / 表格 / 演示文稿，Agent 读正文识别题干与答案，管理员审核通过后写入题库。' }}
          </small>
        </div>
        <div class="role-toolbar">
          <button type="button" class="action-button primary" @click="openImportDialog">导入文档</button>
        </div>
      </div>
      <div class="template-summary">
        <span class="chip">可识别 {{ acceptHint }}</span>
        <span class="chip info">单文件 ≤ {{ limitMb }}MB</span>
        <span class="chip info">入库目标 题库 / 课程库</span>
        <span class="chip warn">审核通过才进题库</span>
      </div>
      <ol class="doc-excerpt">
        <li v-for="step in importSteps" :key="step">{{ step }}</li>
      </ol>

      <div class="section-title">
        <h3>导入台账与审核进度</h3>
        <span class="metric-note">{{ batchSummary ? batchSummary.note : '' }}</span>
      </div>
      <div v-if="batchSummary" class="template-summary">
        <span class="chip">共 {{ batchSummary.total }} 批</span>
        <span class="chip warn">待审核 {{ batchSummary.pending_review }} 批</span>
        <span class="chip ok">已入库 {{ batchSummary.stored_items }} 条</span>
      </div>
      <div class="table-wrap">
        <table class="role-table">
          <thead>
            <tr>
              <th>资料编号</th>
              <th>标题</th>
              <th>入库目标</th>
              <th>识别条目</th>
              <th>状态</th>
              <th>提交时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in batchRows" :key="row.code">
              <td><b>{{ row.code }}</b></td>
              <td>{{ row.title }}</td>
              <td>{{ row.target }}<small class="metric-note"> · {{ row.material_type }}</small></td>
              <td class="num">待审 {{ row.pending_items ?? 0 }} / 已入库 {{ row.stored_items ?? 0 }}</td>
              <td><span :class="batchStatusClass(row.status)">{{ row.status }}</span></td>
              <td class="num">{{ row.submitted_at }}</td>
              <td><button type="button" class="action-button" @click="openBatch(row)">查看识别结果</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="!batchRows.length" class="empty-tip">
        还没有导入过资料：点右上角「导入文档」上传试卷或培训资料，Agent 会先识别候选题，等管理员审核后才进题库。
      </p>
    </div>

    <div v-if="resultView" class="panel import-result">
      <div class="panel-title">
        <div>
          <h2>最近一次 Agent 识别结果（待审核）</h2>
          <small class="chart-caption">审核通过前这些题只在台账里，普通员工刷题抽不到；管理员通过后会自动写进{{ resultViewTarget }}</small>
        </div>
        <div class="role-toolbar">
          <span class="chip warn">待审核 {{ resultCount }} 条</span>
        </div>
      </div>
      <div class="agent-verdict">
        <span :class="resultView.agent_mode === 'SOP 模板' ? 'chip info' : 'chip'">{{ resultView.agent_mode }}</span>
        <b>{{ resultView.material_code }} · {{ resultView.source }}</b>
        <span class="metric-note">题库总量 {{ resultView.bank_total }} 题 · {{ resultView.file.file_name }}</span>
      </div>
      <p class="role-note">{{ resultView.note }}</p>
      <div v-if="!resultChapterMode" class="material-question-list">
        <div v-for="row in resultView.generated" :key="row.index" class="practice-item">
          <div class="practice-head">
            <span class="chip">第 {{ row.index }} 题</span>
            <span class="chip info">{{ row.type }}</span>
            <span class="chip">{{ row.skill }} · L{{ row.level }}</span>
            <span class="chip">{{ row.status }}</span>
            <span class="metric-note">出处 {{ row.source_ref }}</span>
          </div>
          <p class="practice-stem">{{ row.question }}</p>
          <ul class="material-options">
            <li
              v-for="option in row.options"
              :key="option"
              :class="{ 'is-answer': option.startsWith(row.answer + '.') }"
            >
              {{ option }}
            </li>
          </ul>
          <p class="material-answer">标准答案：{{ row.answer_text }}</p>
          <p class="material-analysis">解析：{{ row.analysis }}</p>
        </div>
      </div>
      <div v-else class="table-wrap">
        <table class="role-table">
          <thead><tr><th>序号</th><th>章节</th><th>学习要点</th><th class="num">学时</th><th>出处</th></tr></thead>
          <tbody>
            <tr v-for="row in resultView.generated" :key="row.index">
              <td class="num">{{ row.index }}</td>
              <td><b>{{ row.chapter }}</b></td>
              <td>{{ row.points }}</td>
              <td class="num">{{ row.hours }}</td>
              <td class="num">{{ row.source_ref }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="panel">
      <div class="panel-title">
        <div>
          <h2>{{ sopTemplate ? sopTemplate.title : 'SOP 练习资料生成模板' }}</h2>
          <small class="chart-caption">
            {{ sopTemplate ? sopTemplate.notice : '按模板填入 SOP 内容，Agent 解析后提交管理员审核。' }}
          </small>
        </div>
        <div class="role-toolbar">
          <button type="button" class="action-button primary" @click="sopDialogVisible = true">填写 SOP 模板</button>
        </div>
      </div>
      <div class="template-summary">
        <span class="chip">模板字段 {{ sopFields.length }} 项</span>
        <span class="chip info">对应技能 {{ sopForm.skill }}</span>
        <span class="chip info">适用等级 {{ sopForm.level }}</span>
        <span class="chip">作业步骤 {{ sopStepCount }} 条</span>
      </div>
      <small class="chart-caption">SOP 填报与导入文档走同一条审核链：先由 Agent 生成候选题，管理员通过后才写进题库。</small>
    </div>
    <!-- 导入文档弹窗：选原件 + 填入库目标 / 技能 / 等级 / 版本，提交后 Agent 读正文识别候选题 -->
    <el-dialog
      v-model="importDialogVisible"
      :title="importTemplate ? importTemplate.title : '导入文档生成练习资料'"
      width="min(980px, 94vw)"
      top="6vh"
      class="practice-dialog"
    >
      <p class="form-notice">
        {{ importTemplate ? importTemplate.notice : '上传 PDF / Word / 文本 / 表格 / 演示文稿，Agent 读正文识别题干与答案。' }}
      </p>
      <div class="sop-grid">
        <div class="sop-field">
          <label>选择文档 <i>*</i></label>
          <input class="file-input" type="file" :accept="fileAccept" @change="pickFile" />
          <small>支持 {{ acceptHint }}；单文件不超过 {{ limitMb }}MB，超过请拆分或压缩</small>
          <small v-if="importErrors.file" class="field-error">{{ importErrors.file }}</small>
        </div>
        <div class="sop-field">
          <label>入库目标 <i>*</i></label>
          <el-select v-model="importForm.target" style="width: 100%">
            <el-option v-for="item in importTargets" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <small v-if="importErrors.target" class="field-error">{{ importErrors.target }}</small>
          <small>题库：识别题干 + 选项 + 答案；课程库：整理知识章节与学时</small>
        </div>
        <div class="sop-field">
          <label>对应技能 <i>*</i></label>
          <el-select v-model="importForm.skill" style="width: 100%">
            <el-option v-for="item in sopSkills" :key="item" :label="item" :value="item" />
          </el-select>
          <small v-if="importErrors.skill" class="field-error">{{ importErrors.skill }}</small>
        </div>
        <div class="sop-field">
          <label>适用等级 <i>*</i></label>
          <el-select v-model="importForm.level" style="width: 100%">
            <el-option v-for="item in ['L1', 'L2', 'L3']" :key="item" :label="item" :value="item" />
          </el-select>
          <small v-if="importErrors.level" class="field-error">{{ importErrors.level }}</small>
        </div>
        <div class="sop-field">
          <label>资料标题</label>
          <el-input v-model="importForm.title" placeholder="留空则用文件名作为标题" />
          <small>教程库 / 题库台账里显示的是这个标题</small>
        </div>
        <div class="sop-field">
          <label>版本</label>
          <el-input v-model="importForm.version" placeholder="例如：v1" />
        </div>
        <div class="sop-field">
          <label>备注</label>
          <el-input v-model="importForm.note" placeholder="例如：外委试卷扫描版" />
          <small>备注会写进审核台账，便于管理员核对来源</small>
        </div>
      </div>
      <p v-if="importResult && !importResult.ok" class="review-result">{{ importResult.message }}</p>
      <template #footer>
        <button class="action-button" @click="importDialogVisible = false">取消</button>
        <button class="action-button primary" :disabled="importRunning" @click="importDocument">
          {{ importRunning ? 'Agent 识别中…' : '上传并执行 Agent 识别' }}
        </button>
      </template>
    </el-dialog>

    <!-- SOP 填报弹窗：字段由后端模板下发，填入后提交审核 -->
    <el-dialog
      v-model="sopDialogVisible"
      :title="sopTemplate ? sopTemplate.title : 'SOP 练习资料生成模板'"
      width="min(1160px, 94vw)"
      top="4vh"
      class="practice-dialog sop-dialog"
    >
      <p class="form-notice">
        {{ sopTemplate ? sopTemplate.notice : '按模板填入 SOP 内容，Agent 会逐条判定标准与考核要点，生成候选题并提交管理员审核。' }}
      </p>
      <div class="sop-grid">
        <div v-for="field in sopFields" :key="field.name" class="sop-field">
          <label>{{ field.label }} <i v-if="field.required">*</i></label>
          <small>{{ field.hint }}</small>
          <el-input
            v-if="field.name === 'sop_name'"
            v-model="sopForm[field.name]"
            :placeholder="field.example"
          />
          <el-select v-else-if="field.name === 'skill'" v-model="sopForm[field.name]" style="width: 100%">
            <el-option v-for="item in sopSkills" :key="item" :label="item" :value="item" />
          </el-select>
          <el-select v-else-if="field.name === 'level'" v-model="sopForm[field.name]" style="width: 100%">
            <el-option v-for="item in ['L1', 'L2', 'L3']" :key="item" :label="item" :value="item" />
          </el-select>
          <el-input
            v-else
            v-model="sopForm[field.name]"
            type="textarea"
            :rows="4"
            :placeholder="field.example"
          />
          <small v-if="sopErrors[field.name]" class="field-error">{{ sopErrors[field.name] }}</small>
          <code>示例：{{ field.example }}</code>
        </div>
      </div>
      <template #footer>
        <button class="action-button" @click="sopDialogVisible = false">取消</button>
        <button class="action-button" @click="fillSample">填入模板示例</button>
        <button class="action-button primary" :disabled="sopRunning" @click="generateSop">
          {{ sopRunning ? 'Agent 解析中…' : '生成候选题并提交审核' }}
        </button>
      </template>
    </el-dialog>

    <!-- 批次详情：原件信息 + 正文摘录 + Agent 识别的候选题与每条审核状态 -->
    <el-dialog
      v-model="batchDetail.visible"
      :title="batchTitle"
      width="min(1040px, 94vw)"
      top="4vh"
      class="practice-dialog"
    >
      <p v-if="batchDetail.loading" class="empty-tip">正在读取原件与 Agent 识别结果…</p>
      <template v-else-if="batchDetail.data && batchDetail.data.found">
        <div class="material-banner">
          <span :class="batchDetail.data.pending_items ? 'chip warn' : 'chip ok'">
            {{ batchDetail.data.pending_items ? '待审核 ' + batchDetail.data.pending_items + ' 条' : '已入库 ' + batchDetail.data.stored_items + ' 条' }}
          </span>
          <span class="chip info">{{ batchDetail.data.extracted.mode }}</span>
          <span class="chip">Agent 置信度 {{ batchDetail.data.material.agent_confidence }}</span>
          <span class="metric-note">{{ batchDetail.data.material.agent_note }}</span>
        </div>
        <div class="section-title">
          <h3>原件信息</h3>
          <span class="metric-note">审核在管理员侧「技能与课程 · 上传资料」里完成</span>
        </div>
        <div class="grid-4">
          <div class="info-item"><label>文件名</label><span>{{ batchDetail.data.file.file_name }}</span></div>
          <div class="info-item">
            <label>类型 / 页数 / 大小</label>
            <span>{{ batchDetail.data.file.file_type }} · {{ batchDetail.data.file.pages }} 页 · {{ batchDetail.data.file.size_kb }} KB</span>
          </div>
          <div class="info-item">
            <label>提交人 / 时间</label>
            <span>{{ batchDetail.data.file.uploaded_by }} · {{ batchDetail.data.file.uploaded_at }}</span>
          </div>
          <div class="info-item">
            <label>技能 / 等级 / 版本</label>
            <span>{{ batchDetail.data.material.skill }} · {{ batchDetail.data.material.target_level }} · {{ batchDetail.data.material.version }}</span>
          </div>
        </div>
        <p class="role-note">原件留档：<code>{{ batchDetail.data.file.url }}</code>；{{ batchDetail.data.file.preview_note }}</p>

        <div class="section-title">
          <h3>原件摘录</h3>
          <span class="metric-note">Agent 读到的正文，用来核对它的理解是否准确</span>
        </div>
        <ol class="doc-excerpt">
          <li v-for="(line, index) in batchDetail.data.doc_excerpt" :key="index">{{ line }}</li>
        </ol>

        <div class="section-title">
          <h3>{{ batchDetail.data.extracted.chapter_mode ? 'Agent 识别结果（知识章节）' : 'Agent 识别结果（题目 + 答案 + 解析）' }}</h3>
          <span class="metric-note">共 {{ batchDetail.data.extracted.total }} 条，本页列出 {{ batchDetail.data.extracted.listed }} 条</span>
        </div>
        <p class="role-note">{{ batchDetail.data.extracted.summary }}</p>

        <div v-if="!batchDetail.data.extracted.chapter_mode" class="material-question-list">
          <div v-for="row in batchDetail.data.extracted.items" :key="row.index" class="practice-item">
            <div class="practice-head">
              <span class="chip">第 {{ row.index }} 题</span>
              <span class="chip info">{{ row.type }}</span>
              <span :class="row.status === '已入库' ? 'chip ok' : row.status === '已驳回' ? 'chip bad' : 'chip warn'">{{ row.status }}</span>
              <span v-if="row.question_id" class="chip info">{{ row.question_id }}</span>
              <span class="metric-note">出处 {{ row.source_ref }}</span>
            </div>
            <p class="practice-stem">{{ row.question }}</p>
            <ul class="material-options">
              <li
                v-for="option in row.options"
                :key="option"
                :class="{ 'is-answer': option.startsWith(row.answer + '.') }"
              >
                {{ option }}
              </li>
            </ul>
            <p class="material-answer">标准答案：{{ row.answer_text }}</p>
            <p class="material-analysis">解析：{{ row.analysis }}</p>
          </div>
        </div>
        <div v-else class="table-wrap">
          <table class="role-table">
            <thead><tr><th>序号</th><th>章节</th><th>学习要点</th><th class="num">学时</th><th>状态</th><th>出处</th></tr></thead>
            <tbody>
              <tr v-for="row in batchDetail.data.extracted.items" :key="row.index">
                <td class="num">{{ row.index }}</td>
                <td><b>{{ row.chapter }}</b></td>
                <td>{{ row.points }}</td>
                <td class="num">{{ row.hours }}</td>
                <td><span :class="row.status === '已入库' ? 'chip ok' : row.status === '已驳回' ? 'chip bad' : 'chip warn'">{{ row.status }}</span></td>
                <td class="num">{{ row.source_ref }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
      <p v-else class="empty-tip">{{ batchMessage }}</p>
      <template #footer>
        <button class="action-button" @click="batchDetail.visible = false">关闭</button>
      </template>
    </el-dialog>
  </section>
</template>
<script setup>
import { computed, nextTick, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { api, downloadFile, getData } from '../api';
import '../roles.css';

const emit = defineEmits(['go', 'fill']);
const overview = ref(null);
const reports = ref([]);
const loading = ref(false);
const downloading = ref('');

// 组长侧两条出题路径（导入文档 / SOP 填报）都只生成「待审核」候选题：
// 管理员审核通过后才写进题库 / 课程库，普通员工抽题时才抽得到
const resultView = ref(null);
const resultCount = computed(() => (resultView.value && resultView.value.generated ? resultView.value.generated.length : 0));
const resultChapterMode = computed(() => {
  const generated = resultView.value && resultView.value.generated;
  return Array.isArray(generated) && generated.length > 0 && generated[0].kind === '章节';
});
const resultViewTarget = computed(() => (resultChapterMode.value ? '课程库' : '题库'));
const scrollToResult = async () => {
  await nextTick();
  document.querySelector('.import-result')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
};

// ---- SOP 模板填报：字段由后端模板下发 ----
const sopSkills = ['继电保护', '倒闸操作', '高压试验', '故障录波', '安全规程'];
const sopTemplate = ref(null);
const sopDialogVisible = ref(false);
const sopRunning = ref(false);
const sopErrors = ref({});
const emptySop = () => ({ sop_name: '', skill: '继电保护', level: 'L2', steps: '', criteria: '', points: '', risks: '' });
const sopForm = ref(emptySop());
const sopFields = computed(() => (sopTemplate.value ? sopTemplate.value.sections.flatMap((section) => section.fields) : []));
const sopStepCount = computed(() => (sopForm.value.steps || '').split('\n').filter((line) => line.trim()).length);
const fillSample = () => {
  const next = emptySop();
  sopFields.value.forEach((field) => { next[field.name] = field.example; });
  sopForm.value = next;
  sopErrors.value = {};
};
const generateSop = async () => {
  sopRunning.value = true;
  sopErrors.value = {};
  try {
    const body = (await api.post('/team/sop/generate', sopForm.value)).data;
    if (body.code === 40001) {
      sopErrors.value = body.data.field_errors || {};
      return;
    }
    resultView.value = body.data;
    sopDialogVisible.value = false;
    await loadBatches();
    await scrollToResult();
  } catch (error) {
    const payload = error && error.response ? error.response.data : null;
    sopErrors.value = payload && payload.data && payload.data.field_errors
      ? payload.data.field_errors
      : { sop_name: '提交失败：请确认后端服务已启动（8080）。' };
  } finally {
    sopRunning.value = false;
  }
};

// ---- 导入文档：Agent 读原件正文（PDF / Word / 文本 / 表格 / 演示文稿）识别题干与答案 ----
const importTemplate = ref(null);
const importDialogVisible = ref(false);
const importRunning = ref(false);
const importFile = ref(null);
const importErrors = ref({});
const importResult = ref(null);
const importForm = ref({ target: '题库', skill: '继电保护', level: 'L2', version: 'v1', title: '', note: '' });
const batchRows = ref([]);
const batchSummary = ref(null);
const batchDetail = ref({ visible: false, loading: false, data: null });
const acceptHint = computed(() => (importTemplate.value && importTemplate.value.accept)
  || 'pdf / docx / txt / md / csv / xlsx / pptx');
const limitMb = computed(() => (importTemplate.value && importTemplate.value.limit_mb) || 20);
const importSteps = computed(() => (importTemplate.value && importTemplate.value.steps) || []);
const importTargets = computed(() => (importTemplate.value && importTemplate.value.targets)
  || [{ value: '题库', label: '题库（识别题目 + 答案）' }, { value: '课程库', label: '课程库（整理知识章节）' }]);
const fileAccept = computed(() => acceptHint.value.split('/').map((item) => '.' + item.trim()).join(','));

const pickFile = (event) => {
  const files = event && event.target && event.target.files ? event.target.files : [];
  importFile.value = files.length ? files[0] : null;
  importErrors.value = {};
};
const openImportDialog = () => {
  importErrors.value = {};
  importResult.value = null;
  importDialogVisible.value = true;
};
const importDocument = async () => {
  if (!importFile.value) {
    importErrors.value = { file: '请选择要导入的文档（' + acceptHint.value + '）' };
    return;
  }
  importRunning.value = true;
  importErrors.value = {};
  importResult.value = null;
  try {
    const form = new FormData();
    form.append('file', importFile.value);
    form.append('target', importForm.value.target);
    form.append('skill', importForm.value.skill);
    form.append('level', importForm.value.level);
    form.append('version', importForm.value.version || 'v1');
    form.append('title', importForm.value.title || '');
    form.append('note', importForm.value.note || '');
    const response = await api.post('/team/materials/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } });
    const body = response.data || {};
    if (body.code !== 0) {
      importErrors.value = (body.data && body.data.field_errors) || {};
      importResult.value = { ok: false, message: body.message };
      return;
    }
    importResult.value = { ...body.data, ok: true };
    resultView.value = body.data;
    importDialogVisible.value = false;
    importFile.value = null;
    await loadBatches();
    await scrollToResult();
  } catch (error) {
    const payload = error && error.response ? error.response.data : null;
    const fieldErrors = payload && payload.data && payload.data.field_errors ? payload.data.field_errors : null;
    const status = error && error.response ? error.response.status : 0;
    if (fieldErrors) {
      importErrors.value = fieldErrors;
      importResult.value = { ok: false, message: payload.message };
    } else if (payload && payload.message) {
      importErrors.value = { file: payload.message };
      importResult.value = { ok: false, message: payload.message };
    } else if (status === 413) {
      importErrors.value = { file: '文件超过 ' + limitMb.value + 'MB，请拆分或压缩后再上传' };
      importResult.value = { ok: false, message: '文件超过 ' + limitMb.value + 'MB，后端已拒绝' };
    } else {
      importErrors.value = { file: '导入失败：请确认后端服务（8080）已启动，或文档本身已损坏。' };
      importResult.value = { ok: false, message: '导入失败：请确认后端服务（8080）已启动。' };
    }
  } finally {
    importRunning.value = false;
  }
};

const loadBatches = async () => {
  const data = await getData('/team/materials', null);
  batchRows.value = data && Array.isArray(data.items) ? data.items : [];
  batchSummary.value = data ? data.summary : null;
};
const openBatch = async (item) => {
  batchDetail.value = { visible: true, loading: true, data: null };
  const data = await getData('/team/materials/' + item.code, null);
  batchDetail.value = { visible: true, loading: false, data };
};
const batchStatusClass = (status) => (status === '已审核' ? 'chip ok' : status === '已驳回' ? 'chip bad' : 'chip warn');
const batchTitle = computed(() => {
  const data = batchDetail.value.data;
  return data && data.material ? '资料详情 · ' + data.material.file_name : '资料详情';
});
const batchMessage = computed(() => {
  const data = batchDetail.value.data;
  return data && data.message ? data.message : '没有读到该资料的识别结果。';
});

const metrics = computed(() => {
  const info = overview.value || {};
  const missing = info.reports_missing ?? 0;
  return [
    { label: '应报报告', value: info.reports_required ?? 0, unit: '份', note: '每次实操活动 1 份', tone: 'good' },
    { label: '已提交', value: info.reports_submitted ?? 0, unit: '份', note: '组长确认后归档', tone: 'good' },
    { label: '待确认', value: info.pending_confirm ?? 0, unit: '份', note: '待组长确认后归档', tone: '' },
    { label: '缺报', value: missing, unit: '份', note: '需 3 日内补交', tone: missing > 0 ? 'warn' : 'good', warn: missing > 0 },
    { label: '检测超限', value: info.abnormal ?? 0, unit: '份', note: '已进入诊断输入', tone: 'good' }
  ];
});
const statusClass = (status) => (status === 'SUBMITTED' ? 'chip ok' : 'chip bad');
// SOP 执行情况：未按 SOP 用告警色、已按 SOP 用通过色、本次无对应 SOP 用中性色（历史报告为空则不显示）
const sopText = (status) => ({ FOLLOWED: '已按 SOP', DEVIATED: '未按 SOP', NOT_APPLICABLE: '无对应 SOP' })[status] || status;
const sopClass = (status) => (status === 'DEVIATED' ? 'chip judge warn' : status === 'FOLLOWED' ? 'chip judge ok' : 'chip');
// 判定列：结论与严重度合成同一枚标签，窄列里不再上下堆叠，也不再和旁边的报告状态列撞成一样的白胶囊
const judgeChipClass = (row) => {
  if (!row.judgment) return 'chip judge';
  if (row.judgment !== '超限') return 'chip judge ok';
  return row.severity === '中' ? 'chip judge warn' : 'chip judge bad';
};

// 文档下载统一走接口再落盘：后端查不到报告时给出提示，不再新开一个空白标签页
const downloadDocument = async (row) => {
  if (!row || !row.document_pdf || downloading.value) return;
  downloading.value = row.report_id;
  try {
    await downloadFile(row.document_pdf, (row.report_id || 'report') + '.pdf');
  } catch (error) {
    ElMessage.error('该报告没有可下载的归档文档，请让填报人重新提交生成');
  } finally {
    downloading.value = '';
  }
};

const load = async () => {
  loading.value = true;
  const [info, rows, template, material] = await Promise.all([
    getData('/team/overview', null),
    getData('/team/reports', []),
    getData('/team/sop/template', null),
    getData('/team/materials/template', null)
  ]);
  if (info) overview.value = info;
  if (template) sopTemplate.value = template;
  if (material) importTemplate.value = material;
  reports.value = Array.isArray(rows) ? rows : [];
  await loadBatches();
  loading.value = false;
};

onMounted(load);
</script>

<style scoped>
/* 导入文档的原生文件选择框：与 el-input 的观感保持一致，避免 Element Plus 自带样式缺失时露出浏览器默认样式 */
.file-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px dashed rgba(90, 130, 200, .45);
  border-radius: 2px;
  background: rgba(10, 20, 42, .8);
  color: #d7e2f6;
  font-size: 14px;
  cursor: pointer;
}
.file-input::file-selector-button {
  margin-right: 12px;
  padding: 6px 14px;
  border: 0;
  border-radius: 2px;
  background: #b9964f;
  color: #0a1226;
  font-size: 13.5px;
  font-weight: 700;
  cursor: pointer;
}
</style>