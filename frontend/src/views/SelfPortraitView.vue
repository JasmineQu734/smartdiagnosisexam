<script setup>
import { onMounted, ref } from 'vue';
import { getData } from '../api';
import '../roles.css';

const data = ref(null);
const barClass = (score) => (score >= 85 ? 'bar' : score >= 70 ? 'bar warn' : 'bar bad');

onMounted(async () => {
  data.value = await getData('/personal/self-portrait', null);
});
</script>

<template>
  <section class="role-page">
    <p v-if="!data" class="empty-tip">数据加载中，或后端服务未启动…</p>
    <template v-else>
      <div class="panel">
        <div class="panel-title"><h2>基本信息</h2><span class="metric-note">{{ data.basic.org }}</span></div>
        <div class="info-list">
          <div class="info-item"><label>姓名 / 岗位</label><span>{{ data.basic.name }} · {{ data.basic.position }}</span></div>
          <div class="info-item"><label>部门 / 班组</label><span>{{ data.basic.org }}</span></div>
          <div class="info-item"><label>工龄 / 入职时间</label><span>{{ data.basic.years }} 年 · {{ data.basic.joined_at }}</span></div>
          <div class="info-item"><label>学历</label><span>{{ data.basic.education }}</span></div>
          <div class="info-item" style="grid-column: 1 / -1"><label>证书</label><span>{{ data.basic.certificates.join('；') }}</span></div>
        </div>
      </div>

      <div class="panel-stack">
        <div class="panel">
          <div class="panel-title"><h2>职业目标</h2><span class="metric-note">想往哪个方向发展</span></div>
          <ul class="timeline">
            <li class="timeline-item" v-for="goal in data.goals" :key="goal.direction">
              <div class="timeline-head">
                <b>{{ goal.direction }}</b>
                <span class="chip info">目标 {{ goal.target_level }}</span>
                <span class="chip">{{ goal.horizon }}</span>
              </div>
              <p>{{ goal.note }}</p>
            </li>
          </ul>
        </div>
        <div class="panel">
          <div class="panel-title"><h2>发展意愿</h2><span class="metric-note">转岗 / 带教 / 出差 / 班次</span></div>
          <div class="info-list">
            <div class="info-item"><label>转岗意愿</label><span>{{ data.willingness.transfer }}</span></div>
            <div class="info-item"><label>带教意愿</label><span>{{ data.willingness.mentoring }}</span></div>
            <div class="info-item"><label>出差意愿</label><span>{{ data.willingness.business_trip }}</span></div>
            <div class="info-item"><label>班次安排</label><span>{{ data.willingness.shift }}</span></div>
          </div>
        </div>
      </div>

      <div class="panel-stack">
        <div class="panel">
          <div class="panel-title"><h2>自我评价</h2><span class="metric-note">本人填写</span></div>
          <div class="info-list" style="grid-template-columns: minmax(0, 1fr)">
            <div class="info-item"><label>我擅长什么</label><span>{{ data.self_review.strength }}</span></div>
            <div class="info-item"><label>我想补什么</label><span>{{ data.self_review.to_improve }}</span></div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-title"><h2>师傅评价</h2><span class="chip warn">{{ data.mentor_review.score }} 分</span></div>
          <div class="info-list" style="grid-template-columns: minmax(0, 1fr)">
            <div class="info-item"><label>带教师傅</label><span>{{ data.mentor_review.mentor }}</span></div>
            <div class="info-item"><label>评价（{{ data.mentor_review.scored_at }}）</label><span>{{ data.mentor_review.comment }}</span></div>
          </div>
        </div>
      </div>

      <div class="panel-stack">
        <div class="panel">
          <div class="panel-title"><h2>协作评价</h2><span class="metric-note">{{ data.peer_review.team }}</span></div>
          <div style="display: flex; flex-direction: column; gap: 12px">
            <div v-for="item in [
              { label: '班组协作', value: data.peer_review.collaboration },
              { label: '安全意识', value: data.peer_review.safety },
              { label: '责任心', value: data.peer_review.responsibility }
            ]" :key="item.label">
              <div style="display: flex; justify-content: space-between; font-size: 13.5px; font-weight: 600; color: #334155; margin-bottom: 6px">
                <span>{{ item.label }}</span><span>{{ item.value }} 分</span>
              </div>
              <div :class="barClass(item.value)"><i :style="{ width: item.value + '%' }"></i></div>
            </div>
            <p class="role-note">{{ data.peer_review.comment }}</p>
          </div>
        </div>
        <div class="panel">
          <div class="panel-title"><h2>岗位匹配度</h2><span class="metric-note">当前岗位 vs 目标岗位</span></div>
          <div style="display: flex; flex-direction: column; gap: 12px">
            <div>
              <div style="display: flex; justify-content: space-between; font-size: 13.5px; font-weight: 600; color: #334155; margin-bottom: 6px">
                <span>{{ data.match.current_post }}</span><span>{{ data.match.current_score }}%</span>
              </div>
              <div :class="barClass(data.match.current_score)"><i :style="{ width: data.match.current_score + '%' }"></i></div>
              <p class="role-note">{{ data.match.current_note }}</p>
            </div>
            <div>
              <div style="display: flex; justify-content: space-between; font-size: 13.5px; font-weight: 600; color: #334155; margin-bottom: 6px">
                <span>{{ data.match.target_post }}</span><span>{{ data.match.target_score }}%</span>
              </div>
              <div :class="barClass(data.match.target_score)"><i :style="{ width: data.match.target_score + '%' }"></i></div>
              <p class="role-note">{{ data.match.target_note }}</p>
            </div>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>