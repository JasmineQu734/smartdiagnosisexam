<script setup>
/* 登录页：三维全息城市背景（login3dScene.js，原样移植 login-3d-demo.html）
   + 玻璃质感登录卡（账号 / 密码 / 图形验证码）。
   表单只做本地校验与验证码，真正登录由 App.vue 调 /auth/login，错误信息经 error prop 回显。 */
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { mountLoginScene } from './login3dScene.js';

const props = defineProps({
  error: { type: String, default: '' },
  loading: { type: Boolean, default: false }
});
const emit = defineEmits(['submit']);

const bgCanvas = ref(null);
const capCanvas = ref(null);
let disposeScene = null;

const username = ref('');
const password = ref('');
const capInput = ref('');
const capCode = ref('');
const capMsg = ref({ text: '', cls: '' });

/* 图形验证码：本地绘制（演示环境，防机器人占位实现） */
function drawCaptcha() {
  const cv = capCanvas.value;
  if (!cv) return;
  const chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';
  let code = '';
  for (let i = 0; i < 4; i++) code += chars[(Math.random() * chars.length) | 0];
  capCode.value = code;
  if (import.meta.env.DEV) window.__capCode = code; /* 仅开发环境：供自动化截图/测试读取 */
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#0d1a33';
  ctx.fillRect(0, 0, 96, 44);
  for (let i = 0; i < 5; i++) {
    ctx.strokeStyle = `rgba(90,150,255,${0.15 + Math.random() * 0.3})`;
    ctx.beginPath();
    ctx.moveTo(Math.random() * 96, Math.random() * 44);
    ctx.lineTo(Math.random() * 96, Math.random() * 44);
    ctx.stroke();
  }
  const colors = ['#4d8dff', '#37d0ff', '#8fb4ff', '#3ddcff'];
  code.split('').forEach((ch, i) => {
    ctx.save();
    ctx.translate(14 + i * 21, 29);
    ctx.rotate((Math.random() - 0.5) * 0.5);
    ctx.font = 'bold 24px Consolas, monospace';
    ctx.fillStyle = colors[i % 4];
    ctx.fillText(ch, 0, 0);
    ctx.restore();
  });
}

const show = (text, cls) => { capMsg.value = { text, cls }; };

function submit() {
  show('', '');
  if (!username.value.trim()) return show('请输入账号', 'err');
  if (!password.value) return show('请输入密码', 'err');
  if (capInput.value.trim().toUpperCase() !== capCode.value) {
    drawCaptcha();
    capInput.value = '';
    return show('验证码不正确', 'err');
  }
  emit('submit', { username: username.value.trim(), password: password.value });
}

onMounted(() => {
  disposeScene = mountLoginScene(bgCanvas.value);
  drawCaptcha();
});
onBeforeUnmount(() => { if (disposeScene) disposeScene(); });
</script>

<template>
  <div class="hlogin">
    <canvas ref="bgCanvas" class="bg"></canvas>
    <div class="vignette"></div>
    <div class="brand">变电运维 · 技能与考试管理平台</div>

    <div class="page">
      <form class="login-card" autocomplete="off" @submit.prevent="submit">
        <h1>管理控制台</h1>
        <div class="subtitle">Substation Operation &amp; Training Management Platform</div>

        <div class="field">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8fb0e8" stroke-width="2">
            <circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-6 8-6s8 2 8 6"/>
          </svg>
          <input v-model="username" type="text" placeholder="账号（如 zhangwei）" />
        </div>

        <div class="field next">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8fb0e8" stroke-width="2">
            <rect x="4" y="10" width="16" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>
          </svg>
          <input v-model="password" type="password" placeholder="密码" />
        </div>

        <div class="field-row">
          <div class="field">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8fb0e8" stroke-width="2">
              <path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z"/>
            </svg>
            <input v-model="capInput" type="text" placeholder="验证码" maxlength="4" />
          </div>
          <canvas ref="capCanvas" class="captcha" width="96" height="44" title="点击刷新验证码" @click="drawCaptcha"></canvas>
        </div>

        <div class="msg" :class="capMsg.cls || (props.error ? 'err' : '')" v-text="capMsg.text || props.error"></div>
        <button class="btn" type="submit" :disabled="props.loading">{{ props.loading ? '登录中…' : '立即登录' }}</button>
        <div class="hint">初始密码：123456 · 点击验证码可刷新</div>
      </form>
    </div>
  </div>
</template>

<style scoped>
* { margin: 0; padding: 0; box-sizing: border-box; }
.hlogin { position: relative; width: 100%; height: 100vh; height: 100dvh; overflow: hidden;
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; color: #e8f1ff; background: #02040c; }
.bg { position: absolute; inset: 0; width: 100%; height: 100%; display: block; cursor: grab; }
.bg:active { cursor: grabbing; }

.vignette { position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(ellipse at 42% 46%, rgba(0,0,0,0) 38%, rgba(1,3,12,.62) 100%); }

.page { position: absolute; inset: 0; display: flex; align-items: center; justify-content: flex-end;
  padding: 0 9vw 0 4vw; pointer-events: none; }

.login-card { position: relative; width: 384px; padding: 42px 38px 34px; border-radius: 14px;
  background: linear-gradient(160deg, rgba(24, 42, 80, .55), rgba(9, 18, 38, .72));
  border: 1px solid rgba(110, 170, 255, .30);
  box-shadow: 0 0 60px rgba(30, 90, 210, .30), inset 0 0 30px rgba(50, 110, 255, .07);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); pointer-events: auto; }

.login-card h1 { text-align: center; font-size: 24px; letter-spacing: 6px; text-indent: 6px; font-weight: 700;
  color: #f4f7ff; text-shadow: none; }
.login-card h1::first-letter { color: inherit; }
.subtitle { text-align: center; margin: 8px 0 30px; font-size: 10.5px; letter-spacing: 2.2px; text-indent: 2.2px;
  color: #8794ad; text-transform: uppercase; font-weight: 600; }

.field { display: flex; align-items: center; gap: 10px; background: rgba(9, 20, 42, .72);
  border: 1px solid rgba(80, 130, 225, .38); border-radius: 8px; padding: 0 12px; height: 44px;
  transition: border-color .2s, box-shadow .2s; }
.field.next { margin-top: 16px; }
.field:focus-within { border-color: #3d7fff; box-shadow: 0 0 10px rgba(61, 127, 255, .40); }
.field svg { flex: none; opacity: .65; }
.field input { flex: 1; min-width: 0; background: none; border: none; outline: none;
  color: #dce8ff; font-size: 14px; }
.field input::placeholder { color: #587099; }

.field-row { display: flex; gap: 12px; margin-top: 16px; }
.field-row .field { flex: 1; }
.captcha { flex: none; width: 96px; height: 44px; border-radius: 8px; cursor: pointer;
  border: 1px solid rgba(80, 130, 225, .38); }

.msg { height: 20px; font-size: 12px; margin: 4px 2px 6px; }
.msg.err { color: #ff7d7d; }
.msg.ok { color: #4de0a5; }

.btn { width: 100%; height: 44px; border: none; border-radius: 2px; font-size: 16px; color: #0a1226;
  cursor: pointer; letter-spacing: 8px; text-indent: 8px; font-weight: 800;
  background: linear-gradient(90deg, #b9964f, #d9bd8a);
  box-shadow: 0 4px 22px rgba(217, 189, 138, .35); transition: filter .2s, transform .1s; }
.btn:hover { filter: brightness(1.14); }
.btn:active { transform: translateY(1px); }
.btn:disabled { filter: saturate(.5) brightness(.8); cursor: wait; }

.hint { margin-top: 14px; text-align: center; font-size: 11px; color: #46608f; }

.brand { position: absolute; left: 34px; bottom: 28px; font-size: 14px; letter-spacing: 3px;
  color: #9db8e8; text-shadow: 0 0 12px rgba(60, 130, 255, .55); pointer-events: none; }

@media (max-width: 900px) {
  .page { justify-content: center; padding: 0 20px; }
  .brand { display: none; }
}
</style>
