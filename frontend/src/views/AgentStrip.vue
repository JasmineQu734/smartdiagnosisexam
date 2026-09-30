<script setup>
import { computed } from 'vue';
import '../roles.css';

const props = defineProps({ diagnosis: { type: Object, default: null } });

const has = computed(() => !!(props.diagnosis && props.diagnosis.ran_at));
const headline = computed(() => {
  if (!props.diagnosis) return '';
  if (props.diagnosis.verdict) return props.diagnosis.verdict.headline;
  return props.diagnosis.hint || '';
});
</script>

<template>
  <div class="agent-strip" :class="{ fresh: has }">
    <span class="agent-strip-icon">✦</span>
    <div class="agent-strip-main">
      <b>{{ has ? '个性化 Agent 最新诊断' : '个性化 Agent 尚未运行' }}</b>
      <p>{{ has ? headline : (headline || '到“差距与建议”点“运行个性化 Agent 诊断”，结论会同步到本板块。') }}</p>
    </div>
    <div v-if="has" class="agent-strip-meta">
      <span class="chip info">{{ diagnosis.ran_at }}</span>
      <span class="chip">置信度 {{ Math.round(diagnosis.confidence * 100) }}%</span>
    </div>
  </div>
</template>