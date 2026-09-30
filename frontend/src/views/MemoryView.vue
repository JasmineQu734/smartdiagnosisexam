<script setup>
import { computed, onMounted, ref } from 'vue';
import { getData } from '../api';
import '../roles.css';
import AgentStrip from './AgentStrip.vue';

const props = defineProps({ diagnosis: { type: Object, default: null } });
const emit = defineEmits(['go']);

const data = ref(null);
const filter = ref('ALL');
const typeChip = (type) => ({
  EXAM: 'chip warn', ERROR: 'chip bad', PRACTICE: 'chip info', LEARNING: 'chip info',
  SAFETY: 'chip ok', MENTOR: 'chip', REVIEW: 'chip', ADVICE: 'chip ok'
}[type] || 'chip');
const filters = [
  { key: 'ALL', label: '全部' },
  { key: 'LEARNING', label: '学习记忆' },
  { key: 'ERROR', label: '错误记忆' },
  { key: 'PRACTICE', label: '实操记忆' },
  { key: 'EXAM', label: '考试记忆' },
  { key: 'SAFETY', label: '安全记忆' },
  { key: 'MENTOR', label: '带教记忆' },
  { key: 'REVIEW', label: '复盘记忆' }
];
const items = computed(() => {
  const rows = (data.value && data.value.items) || [];
  return filter.value === 'ALL' ? rows : rows.filter((row) => row.type === filter.value);
});

onMounted(async () => {
  data.value = await getData('/personal/memories', null);
});
</script>

<template>
  <section class="role-page">
    <p v-if="!data" class="empty-tip">数据加载中，或后端服务未启动…</p>
    <template v-else>
      <div class="panel role-banner">
        <p><b>{{ data.owner }} 的能力记忆库</b>：关键事件按时间线留存。这一板块的用处是判断“学没学会、错在哪、有没有复盘”——它既是本人回顾的地方，也是个人学习 Agent 生成建议时读取的原始依据。</p>
        <div class="role-toolbar">
          <span class="chip info">共 {{ data.summary.total }} 条</span>
          <span class="chip warn">考试 {{ data.summary.exam }}</span>
          <span class="chip">带教 {{ data.summary.mentor }}</span>
          <span class="chip ok">安全 {{ data.summary.safety }}</span>
          <button class="action-button" @click="emit('go', 'advice')">用记忆生成诊断 →</button>
        </div>
      </div>

      <AgentStrip :diagnosis="diagnosis" />

      <div class="panel" v-if="data.insight">
        <div class="panel-title"><h2>记忆研判</h2><span class="metric-note">学习记忆情况与复盘结论</span></div>
        <p class="role-note judgement">{{ data.insight.judgement }}</p>
        <div class="grid-2" style="margin-top: 14px">
          <div class="info-list" style="grid-template-columns: minmax(0, 1fr)">
            <div class="info-item"><label>学习记忆</label><span>{{ data.insight.learning_state }}</span></div>
            <div class="info-item"><label>错误记忆</label><span>{{ data.insight.error_state }}</span></div>
            <div class="info-item"><label>复盘记忆</label><span>{{ data.insight.review_state }}</span></div>
            <div class="info-item"><label>系统建议</label><span>{{ data.insight.advice_state }}</span></div>
          </div>
          <div>
            <div class="panel-title" style="margin-bottom: 12px"><h2>风险点</h2></div>
            <ul class="risk-list">
              <li v-for="point in data.insight.risk_points" :key="point">{{ point }}</li>
            </ul>
            <div class="panel-title" style="margin: 18px 0 12px"><h2>Agent 读取的记忆类型</h2></div>
            <div class="tag-row">
              <span class="chip info" v-for="item in data.insight.agent_inputs" :key="item">{{ item }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-title"><h2>记忆时间线</h2><span class="metric-note">按类型筛选</span></div>
        <div class="role-toolbar" style="margin-bottom: 14px">
          <button v-for="item in filters" :key="item.key" class="action-button"
                  :class="{ active: filter === item.key }" @click="filter = item.key">{{ item.label }}</button>
        </div>
        <ul class="timeline">
          <li class="timeline-item" v-for="memory in items" :key="memory.memory_id">
            <div class="timeline-head">
              <time>{{ memory.occurred_at }}</time>
              <span :class="typeChip(memory.type)">{{ memory.type_label }}</span>
              <b>{{ memory.title }}</b>
            </div>
            <p>{{ memory.detail }}</p>
            <div class="tag-row">
              <span class="chip" v-for="tag in memory.tags" :key="tag">{{ tag }}</span>
              <span class="chip info">来源：{{ memory.source_label }}</span>
            </div>
          </li>
        </ul>
      </div>
    </template>
  </section>
</template>