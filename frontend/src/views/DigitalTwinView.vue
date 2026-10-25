<script setup>
// 3D 数字孪生驾驶舱：iframe 内嵌原型页（?embed=1）。
// 嵌入页与独立打开完全一致——顶栏状态、巡检任务、演练中心、园区设备面板全保留；
// 宿主只在其上方提供一条页面导航（twin-floatnav，见 App.vue / twin-dark.css）。
// 主题协同：src 带初始 theme；运行中由 App.vue postMessage {type:'wb-theme'} 实时切换。
const props = defineProps({ initialTheme: { type: String, default: 'night' } });
const src = `/twin/3d-substation-campus.html?embed=1&theme=${props.initialTheme}`;
</script>

<template>
  <div class="twin-stage">
    <iframe
      class="twin-frame"
      :src="src"
      title="110kV 城东变电站 · 三维数字孪生园区"
      allow="fullscreen"
    ></iframe>
  </div>
</template>

<style scoped>
/* 全幅舞台：填满顶部导航条以下的全部空间，铺满屏幕 */
.twin-stage {
  position: relative;
  flex: 1 1 0;
  min-height: 0;
  overflow: hidden;
  background: #0a1226;
}
.twin-frame { width: 100%; height: 100%; border: 0; display: block; }
</style>
