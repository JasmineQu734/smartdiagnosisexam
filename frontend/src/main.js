import { createApp } from 'vue';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
/* Element Plus 官方暗色变量：配合 index.html 上的 <html class="dark"> 生效，
   让 el-table / el-dialog / el-select 等组件跟随全局深色科技风 */
import 'element-plus/theme-chalk/dark/css-vars.css';
import './style.css';
import './theme-light.css';
import './dialogs.css';
import App from './App.vue';
createApp(App).use(ElementPlus).mount('#app');