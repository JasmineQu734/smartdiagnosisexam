<script setup>
import { onMounted, ref } from 'vue';
import { api, getData } from '../api';
import '../roles.css';

const props = defineProps({ diagnosis: { type: Object, default: null } });
const emit = defineEmits(['diagnosed']);

const data = ref(null);
const result = ref(props.diagnosis && props.diagnosis.ran_at ? props.diagnosis : null);
const running = ref(false);
const error = ref('');

const severityClass = (severity) => ({ HIGH: 'chip bad', MEDIUM: 'chip warn', LOW: 'chip ok' }[severity] || 'chip');
const kindClass = (kind) => ({ 课程: 'chip info', 带教: 'chip warn', 模拟考: 'chip ok' }[kind] || 'chip');

const runDiagnosis = async () => {
  running.value = true;
  error.value = '';
  try {
    const response = await api.post('/personal/agent-diagnose');
    result.value = response.data.data;
    emit('diagnosed', result.value);
  } catch (e) {
    error.value = '诊断失败：请确认后端服务已启动（8080）。';
  } finally {
    running.value = false;
  }
};

onMounted(async () => {
  data.value = await getData('/personal/advice', null);
});
</script>

<template>
  <section class="role-page">
    <p v-if="!data" class="empty-tip">数据加载中，或后端服务未启动…</p>
    <template v-else>
      <div class="panel role-banner">
        <p>{{ data.summary }}</p>
        <div class="role-toolbar">
          <span class="chip info">{{ data.source_label }}</span>
          <span class="chip">置信度 {{ Math.round(data.confidence * 100) }}%</span>
          <span :class="data.need_human_confirm ? 'chip warn' : 'chip ok'">{{ data.need_human_confirm ? '需班组长确认后生效' : '可直接执行' }}</span>
        </div>
      </div>

      <div class="panel agent-panel">
        <div class="panel-title">
          <div>
            <h2>个性化 Agent 诊断</h2>
            <small class="chart-caption">实时读取技能雷达、考试错题、实操超时、师傅评价与记忆库，判断“是缺人还是缺技能”，并给出复合型人才扩展路线</small>
          </div>
          <button type="button" class="action-button primary" :disabled="running" @click="runDiagnosis">
            {{ running ? '诊断中…' : (result ? '重新运行诊断' : '运行个性化 Agent 诊断') }}
          </button>
        </div>

        <p v-if="error" class="empty-note">{{ error }}</p>

        <div v-if="!result" class="agent-placeholder">
          <b>还没有生成诊断结论</b>
          <p>点右上角按钮，Agent 会立刻按当前数据出结论：现在差在哪、先做什么、往哪个方向扩展学习能成为复合型人才。结论会自动写入“记忆展示”，并同步到技能雷达、个人能力、成长轨迹等板块。</p>
        </div>

        <template v-else>
          <div class="agent-verdict">
            <span class="chip info">结论</span>
            <b>{{ result.verdict.headline }}</b>
            <span class="metric-note">{{ result.ran_at }} · 证据 {{ result.evidence_count }} 条 · {{ result.source_label }}</span>
          </div>
          <ul class="agent-reasons">
            <li v-for="reason in result.verdict.reasons" :key="reason">{{ reason }}</li>
          </ul>

          <div class="agent-block">
            <h3>差距清单（按优先级）</h3>
            <div class="table-wrap">
              <table class="role-table">
                <thead><tr><th>优先级</th><th>技能</th><th class="num">当前</th><th class="num">岗位要求</th><th class="num">未来需求</th><th>影响</th><th>怎么做</th></tr></thead>
                <tbody>
                  <tr v-for="gap in result.gaps" :key="gap.skill">
                    <td><span :class="severityClass(gap.severity)">{{ gap.priority }}</span></td>
                    <td><b>{{ gap.skill }}</b></td>
                    <td class="num">L{{ gap.current }}</td>
                    <td class="num">L{{ gap.required }}</td>
                    <td class="num">L{{ gap.future }}</td>
                    <td>{{ gap.impact }}</td>
                    <td>{{ gap.action }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="agent-block">
            <h3>学习路径（实时生成）</h3>
            <ul class="timeline">
              <li class="timeline-item" v-for="step in result.plan" :key="step.step">
                <div class="timeline-head">
                  <span class="chip info">第 {{ step.step }} 步</span>
                  <span :class="kindClass(step.kind)">{{ step.kind }}</span>
                  <b>{{ step.title }}</b>
                  <time>截止 {{ step.due_at }}</time>
                </div>
                <p>目标：{{ step.target_skill }} → {{ step.to_level }}；理由：{{ step.reason }}</p>
              </li>
            </ul>
          </div>

          <div class="agent-block">
            <h3>{{ result.compound_path.title }}</h3>
            <p class="role-note">{{ result.compound_path.why }}</p>
            <div class="grid-4 compound-grid">
              <div class="info-item" v-for="stage in result.compound_path.stages" :key="stage.phase">
                <label>{{ stage.phase }}</label>
                <span>{{ stage.focus }}</span>
                <span class="role-note">学什么：{{ stage.skills }}</span>
                <span class="role-note">达标标志：{{ stage.milestone }}</span>
              </div>
            </div>
            <p class="role-note"><b>收益：</b>{{ result.compound_path.benefit }}</p>
          </div>

          <div class="agent-block">
            <h3>本次诊断已同步的板块</h3>
            <div class="tag-row">
              <span class="chip ok" v-for="item in result.updated_modules" :key="item">{{ item }}</span>
            </div>
          </div>
        </template>
      </div>

      <div class="panel">
        <div class="panel-title"><h2>欠缺口径基线</h2><span class="metric-note">来自技能雷达与岗位要求，供上面 Agent 诊断比对</span></div>
        <div class="table-wrap">
          <table class="role-table">
            <thead><tr><th>技能</th><th class="num">当前</th><th class="num">岗位要求</th><th class="num">未来需求</th><th>缺口类型</th><th>判定证据</th></tr></thead>
            <tbody>
              <tr v-for="gap in data.gaps" :key="gap.skill">
                <td><b>{{ gap.skill }}</b></td>
                <td class="num">L{{ gap.current }}</td>
                <td class="num">L{{ gap.required }}</td>
                <td class="num">L{{ gap.future }}</td>
                <td><span :class="severityClass(gap.severity)">{{ gap.gap_type }}</span></td>
                <td>{{ gap.evidence }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </section>
</template>