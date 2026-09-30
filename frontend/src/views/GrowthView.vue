<script setup>
import { onMounted, ref } from 'vue';
import { getData } from '../api';
import '../roles.css';
import AgentStrip from './AgentStrip.vue';

const props = defineProps({ diagnosis: { type: Object, default: null } });

const data = ref(null);
const badgeClass = (badge) => {
  if (['已达标', '已闭环', '安全良好', '有效'].includes(badge)) return 'chip ok';
  if (['需改进', '待补考'].includes(badge)) return 'chip bad';
  return 'chip warn';
};

onMounted(async () => {
  data.value = await getData('/personal/growth', null);
});
</script>

<template>
  <section class="role-page">
    <p v-if="!data" class="empty-tip">数据加载中，或后端服务未启动…</p>
    <template v-else>
      <AgentStrip :diagnosis="diagnosis" />

      <div class="grid-3">
        <div class="panel metric">
          <small>晋升准备度</small>
          <div class="metric-value"><b class="small">{{ data.readiness }}</b><em>%</em></div>
          <span class="warn">{{ data.readiness_label }}</span>
        </div>
        <div class="panel" style="grid-column: span 2">
          <div class="panel-title"><h2>下一步</h2><span class="chip info">按此顺序推进</span></div>
          <p class="role-note">{{ data.next_step }}</p>
        </div>
      </div>

      <div class="panel">
        <div class="panel-title"><h2>成长时间线</h2><span class="metric-note">技能等级 · 证书 · 考试 · 任务 · 培训 · 安全</span></div>
        <ul class="timeline">
          <li class="timeline-item" v-for="event in data.timeline" :key="event.occurred_at + event.title">
            <div class="timeline-head">
              <time>{{ event.occurred_at }}</time>
              <span class="chip info">{{ event.category }}</span>
              <b>{{ event.title }}</b>
              <span :class="badgeClass(event.badge)">{{ event.badge }}</span>
            </div>
            <p>{{ event.detail }}</p>
          </li>
        </ul>
      </div>

      <div class="panel">
        <div class="panel-title"><h2>技能等级变化</h2><span class="metric-note">按时间点记录</span></div>
        <div class="table-wrap">
          <table class="role-table">
            <thead><tr><th>时间</th><th class="num">继电保护</th><th class="num">倒闸操作</th><th class="num">高压试验</th></tr></thead>
            <tbody>
              <tr v-for="row in data.level_curve" :key="row.period">
                <td>{{ row.period }}</td>
                <td class="num">{{ row['继电保护'] }} 级</td>
                <td class="num">{{ row['倒闸操作'] }} 级</td>
                <td class="num">{{ row['高压试验'] }} 级</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </section>
</template>