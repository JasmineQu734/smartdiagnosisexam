<script setup>
import { onMounted, ref } from 'vue';
import { getData } from '../api';
import '../roles.css';
import AgentStrip from './AgentStrip.vue';

const props = defineProps({ diagnosis: { type: Object, default: null } });

const data = ref(null);
const barClass = (score) => (score >= 85 ? 'bar' : score >= 70 ? 'bar warn' : 'bar bad');
const levelChip = (level, required) => (level >= required ? 'chip ok' : 'chip warn');

onMounted(async () => {
  data.value = await getData('/personal/abilities', null);
});
</script>

<template>
  <section class="role-page">
    <p v-if="!data" class="empty-tip">数据加载中，或后端服务未启动…</p>
    <template v-else>
      <AgentStrip :diagnosis="diagnosis" />

      <div class="panel">
        <div class="panel-title"><h2>硬技能</h2><span class="metric-note">等级对照与判定证据</span></div>
        <div class="table-wrap">
          <table class="role-table">
            <thead>
              <tr><th>技能</th><th class="num">当前</th><th class="num">岗位要求</th><th>状态</th><th>判定证据</th></tr>
            </thead>
            <tbody>
              <tr v-for="item in data.hard_skills" :key="item.name">
                <td><b>{{ item.name }}</b></td>
                <td class="num">{{ item.level_label }}（{{ item.level }} 级）</td>
                <td class="num">L{{ item.required_level }}</td>
                <td><span :class="levelChip(item.level, item.required_level)">{{ item.level >= item.required_level ? '已达标' : '差 ' + (item.required_level - item.level) + ' 级' }}</span></td>
                <td>{{ item.evidence }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="grid-2">
        <div class="panel">
          <div class="panel-title"><h2>软技能</h2><span class="metric-note">沟通 / 协作 / 带教 / 应急</span></div>
          <div style="display: flex; flex-direction: column; gap: 12px">
            <div v-for="item in data.soft_skills" :key="item.name">
              <div style="display: flex; justify-content: space-between; font-size: 13.5px; font-weight: 600; color: #334155; margin-bottom: 6px">
                <span>{{ item.name }}</span><span>{{ item.score }} 分</span>
              </div>
              <div :class="barClass(item.score)"><i :style="{ width: item.score + '%' }"></i></div>
              <p class="role-note">{{ item.note }}</p>
            </div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-title"><h2>安全能力</h2><span :class="data.safety.veto ? 'chip bad' : 'chip ok'">{{ data.safety.veto ? '存在一票否决' : '无一票否决' }}</span></div>
          <div class="info-list">
            <div class="info-item"><label>安全记录</label><span>{{ data.safety.record_days }} 天无违章</span></div>
            <div class="info-item"><label>违章 / 事故</label><span>{{ data.safety.violations }} 次 / {{ data.safety.incidents }} 起</span></div>
            <div class="info-item"><label>最近安全培训</label><span>{{ data.safety.last_training }}</span></div>
            <div class="info-item"><label>结论</label><span>{{ data.safety.note }}</span></div>
          </div>
        </div>
      </div>

      <div class="grid-3">
        <div class="panel">
          <div class="panel-title"><h2>实操能力</h2></div>
          <div class="info-list" style="grid-template-columns: minmax(0, 1fr)">
            <div class="info-item"><label>工单量 / 平均工时</label><span>{{ data.practice.ticket_count }} 单 · {{ data.practice.avg_hours }} 小时</span></div>
            <div class="info-item"><label>任务完成率</label><span>{{ data.practice.completion_rate }}%</span></div>
            <div class="info-item"><label>超时率（{{ data.practice.overtime_count }} 次超时）</label><span>{{ data.practice.timeout_rate }}%</span></div>
            <div class="info-item"><label>最近超时</label><span>{{ data.practice.last_timeout }}</span></div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-title"><h2>考试能力</h2><span class="metric-note">合格线 {{ data.exams.pass_line }} 分</span></div>
          <div class="info-list" style="grid-template-columns: minmax(0, 1fr)">
            <div class="info-item"><label>理论</label><span>{{ data.exams.theory }} 分</span></div>
            <div class="info-item"><label>实操</label><span>{{ data.exams.practice }} 分</span></div>
            <div class="info-item"><label>仿真</label><span>{{ data.exams.simulation }} 分</span></div>
            <div class="info-item"><label>备注</label><span>{{ data.exams.note }}</span></div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-title"><h2>证书能力</h2><span class="metric-note">{{ data.certificates.length }} 本</span></div>
          <div style="display: flex; flex-direction: column; gap: 10px">
            <div class="info-item" v-for="cert in data.certificates" :key="cert.name">
              <label>{{ cert.name }} · {{ cert.level }}</label>
              <span>{{ cert.issued_at }} → {{ cert.expires_at }}</span>
              <span class="role-note">复审提醒：{{ cert.review_note }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>