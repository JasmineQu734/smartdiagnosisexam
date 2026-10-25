/* 登录页三维全息城市背景。
   场景代码原样移植自 login-3d-demo.html（Bloom 辉光 + 悬浮城市 + 车流 + 光轨 + 涟漪），
   由 LoginStage.vue 在 onMounted 时传入 canvas 调用 mountLoginScene，返回卸载清理函数。
   three 由 npm 依赖提供（与 demo 的 0.160.0 同版本），离线打包，不走 CDN。 */
import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

export function mountLoginScene(canvas) {
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x02040c);
scene.fog = new THREE.Fog(0x02040c, 40, 110);

const camera = new THREE.PerspectiveCamera(40, innerWidth / innerHeight, 0.1, 300);
const CAM_BASE = new THREE.Vector3(8.2, 13.5, 20.5);   // 等轴测感视角
camera.position.copy(CAM_BASE);
const LOOK_AT = new THREE.Vector3(-4.0, 3.6, 0);       // 场景中心
const RIGHT = new THREE.Vector3(0.813, 0, -0.583);     // 屏幕右方向（随当前机位近似）
let camShift = 0;                                      // 相机向右平移量 = 场景在画面中向左的偏移

/* ---------- 后期：Bloom 辉光（画面质感的钥匙） ---------- */
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.42, 0.45, 0.30);
composer.addPass(bloom);
composer.addPass(new OutputPass());

scene.add(new THREE.AmbientLight(0x44577a, 1.6));
const pt = new THREE.PointLight(0x4fa9ff, 220, 60);
pt.position.set(-3, 16, 2);
scene.add(pt);
const dir = new THREE.DirectionalLight(0x88aaff, 1.2);
dir.position.set(10, 18, 8);
scene.add(dir);

const world = new THREE.Group();
world.position.set(-4.0, -1.6, 0);
scene.add(world);

/* ---------- 常用材质 / 纹理工具 ---------- */
const EDGE = new THREE.LineBasicMaterial({ color: 0x5fd8ff, transparent: true, opacity: 0.85 });

function canvasTex(w, h, draw) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/* 楼体亮窗纹理：一栋一个，窗格随机点亮 */
function buildingTexture() {
  return canvasTex(128, 256, (x) => {
    x.fillStyle = '#0a1c3f';
    x.fillRect(0, 0, 128, 256);
    const cols = 6, rows = 16, cw = 128 / cols, ch = 256 / rows;
    for (let i = 0; i < cols; i++) {
      for (let j = 0; j < rows; j++) {
        if (Math.random() < 0.40) {
          const r = Math.random();
          x.fillStyle = r < 0.08 ? 'rgba(255,205,140,.95)'      // 少量暖色窗，打破纯蓝
                      : r < 0.60 ? 'rgba(150,205,255,.95)'
                      : r < 0.88 ? 'rgba(80,160,255,.9)'
                                 : 'rgba(225,245,255,.95)';
          x.fillRect(i * cw + cw * 0.22, j * ch + ch * 0.26, cw * 0.56, ch * 0.4);
        }
      }
    }
  });
}

/* 数据面板纹理：表头 + 柱状图 + 折线 */
function panelTexture(title) {
  return canvasTex(256, 160, (x) => {
    x.fillStyle = 'rgba(6,18,42,.92)';
    x.fillRect(0, 0, 256, 160);
    const grad = x.createLinearGradient(0, 0, 0, 26);
    grad.addColorStop(0, 'rgba(60,130,255,.55)');
    grad.addColorStop(1, 'rgba(30,80,200,.2)');
    x.fillStyle = grad;
    x.fillRect(2, 2, 252, 26);
    x.strokeStyle = '#3ea8ff';
    x.lineWidth = 2;
    x.strokeRect(2, 2, 252, 156);
    x.fillStyle = '#cfe8ff';
    x.font = 'bold 14px sans-serif';
    x.fillText(title, 12, 20);
    x.strokeStyle = 'rgba(90,150,230,.18)';
    x.lineWidth = 1;
    for (let i = 1; i < 4; i++) {
      x.beginPath(); x.moveTo(10, 32 + i * 30); x.lineTo(246, 32 + i * 30); x.stroke();
    }
    const hs = [40, 66, 52, 88, 62, 80, 46];
    hs.forEach((h, i) => {
      const g2 = x.createLinearGradient(0, 142 - h, 0, 142);
      g2.addColorStop(0, 'rgba(120,220,255,.95)');
      g2.addColorStop(1, 'rgba(40,110,255,.45)');
      x.fillStyle = g2;
      x.fillRect(18 + i * 32, 142 - h, 16, h);
    });
    x.strokeStyle = '#6ff3ff';
    x.lineWidth = 2.5;
    x.shadowColor = '#6ff3ff';
    x.shadowBlur = 6;
    x.beginPath();
    hs.forEach((h, i) => {
      const px = 26 + i * 32, py = 142 - h - 10;
      i ? x.lineTo(px, py) : x.moveTo(px, py);
    });
    x.stroke();
  });
}

/* 光轨纹理：亮头 → 拖尾 */
function trailTexture() {
  return canvasTex(256, 16, (x) => {
    const g = x.createLinearGradient(0, 0, 256, 0);
    g.addColorStop(0, 'rgba(70,170,255,0)');
    g.addColorStop(0.75, 'rgba(100,195,255,.65)');
    g.addColorStop(1, 'rgba(230,250,255,1)');
    x.fillStyle = g;
    x.fillRect(0, 0, 256, 16);
  });
}

/* 大范围环境辉光（贴在场景后面的蓝色光晕） */
function glowSpriteTexture() {
  return canvasTex(256, 256, (x) => {
    const g = x.createRadialGradient(128, 128, 0, 128, 128, 128);
    g.addColorStop(0, 'rgba(45,115,235,.50)');
    g.addColorStop(0.45, 'rgba(28,75,170,.20)');
    g.addColorStop(1, 'rgba(0,0,20,0)');
    x.fillStyle = g;
    x.fillRect(0, 0, 256, 256);
  });
}

/* 车辆：车身 + 座舱 + 四轮 + 头灯/尾灯 + 路面光斑（车头朝局部 +x） */
function makeCar(color, opts = {}) {
  const g = new THREE.Group();
  const L = opts.bus ? 0.52 : 0.3;
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(L, 0.07, 0.15),
    new THREE.MeshBasicMaterial({ color })
  );
  body.position.y = 0.05;
  g.add(body);
  const cabin = new THREE.Mesh(
    new THREE.BoxGeometry(opts.bus ? L * 0.85 : L * 0.5, 0.05, 0.13),
    new THREE.MeshBasicMaterial({ color: 0x14294d })
  );
  cabin.position.set(opts.bus ? -0.02 : -0.03, 0.10, 0);
  g.add(cabin);
  const wheelMat = new THREE.MeshBasicMaterial({ color: 0x05080f });
  [[-1, 1], [1, 1], [-1, -1], [1, -1]].forEach(([sx, sz]) => {
    const w = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.05, 0.03), wheelMat);
    w.position.set(sx * (L * 0.32), 0.025, sz * 0.08);
    g.add(w);
  });
  const headMat = new THREE.MeshBasicMaterial({ color: 0xfff6d8 });
  const tailMat = new THREE.MeshBasicMaterial({ color: 0xff5a4d });
  [-1, 1].forEach((sz) => {
    const h = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.02, 0.03), headMat);
    h.position.set(L * 0.5, 0.05, sz * 0.05);
    g.add(h);
    const t = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.02, 0.03), tailMat);
    t.position.set(-L * 0.5, 0.05, sz * 0.05);
    g.add(t);
  });
  const pool = new THREE.Mesh(
    new THREE.PlaneGeometry(0.5, 0.28),
    new THREE.MeshBasicMaterial({ color: 0xfff2c0, transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending, depthWrite: false })
  );
  pool.rotation.x = -Math.PI / 2;
  pool.position.set(L * 0.5 + 0.22, 0.005, 0);
  g.add(pool);
  return g;
}

/* ====================================================================
   底部基座（设备台）+ 同心光环 + 投射光束
==================================================================== */
const base = new THREE.Group();

const baseBody = new THREE.Mesh(
  new THREE.BoxGeometry(6.8, 1.1, 6.8),
  new THREE.MeshStandardMaterial({ color: 0x070d1c, metalness: 0.85, roughness: 0.28 })
);
baseBody.position.y = 0.55;
const baseTop = new THREE.Mesh(
  new THREE.BoxGeometry(7.5, 0.18, 7.5),
  new THREE.MeshStandardMaterial({ color: 0x0b1830, metalness: 0.7, roughness: 0.3 })
);
baseTop.position.y = 1.19;
const baseEdgesTop = new THREE.LineSegments(new THREE.EdgesGeometry(baseTop.geometry), EDGE);
baseEdgesTop.position.y = 1.19;
const baseEdgesBody = new THREE.LineSegments(
  new THREE.EdgesGeometry(baseBody.geometry),
  new THREE.LineBasicMaterial({ color: 0x2f8fd8, transparent: true, opacity: 0.55 })
);
baseEdgesBody.position.y = 0.55;

/* 基座侧面的发光饰条 */
const trimMat = new THREE.MeshBasicMaterial({ color: 0x35c8ff, transparent: true, opacity: 0.9 });
[[7.0, 0.035, 0.03, 0, 3.51], [7.0, 0.035, 0.03, 0, -3.51], [0.03, 0.035, 7.0, 3.51, 0], [0.03, 0.035, 7.0, -3.51, 0]]
  .forEach(([w, h, d, x, z]) => {
    const t = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), trimMat);
    t.position.set(x, 1.02, z);
    base.add(t);
  });

base.add(baseBody, baseTop, baseEdgesTop, baseEdgesBody);

/* 同心光环：一圈比一圈大，厚度用 Torus 才有参考图那种"实体圈"感 */
const rings = [];
[[2.45, 0.055], [1.85, 0.045], [1.25, 0.04]].forEach(([r, tube], i) => {
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(r, tube, 12, 96),
    new THREE.MeshBasicMaterial({ color: i === 0 ? 0x5ff0ff : 0x35d0ff, transparent: true, opacity: 0.95 })
  );
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 1.30;
  rings.push(ring);
  base.add(ring);
});
const coreGlow = new THREE.Mesh(
  new THREE.CircleGeometry(1.05, 48),
  new THREE.MeshBasicMaterial({ color: 0x1f9dff, transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false })
);
coreGlow.rotation.x = -Math.PI / 2;
coreGlow.position.y = 1.31;
base.add(coreGlow);

/* 投射光束：外层宽 + 内层亮 */
function beamCylinder(rTop, rBot, opacity) {
  const m = new THREE.Mesh(
    new THREE.CylinderGeometry(rTop, rBot, 3.4, 48, 1, true),
    new THREE.MeshBasicMaterial({ color: 0x35b4ff, transparent: true, opacity, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false })
  );
  m.position.y = 1.3 + 1.7;
  return m;
}
const beamOuter = beamCylinder(2.7, 1.15, 0.05);
const beamInner = beamCylinder(1.7, 0.65, 0.06);
base.add(beamOuter, beamInner);
world.add(base);

/* ====================================================================
   悬浮城市沙盘（上半部分）
==================================================================== */
const city = new THREE.Group();
city.position.y = 5.2;
world.add(city);
const CITY_TOP = 0.35;   // 沙盘面板顶面(相对 city)

/* 玻璃沙盘：两层错位的半透明板 + 亮边 */
const slabLower = new THREE.Mesh(
  new THREE.BoxGeometry(10.3, 0.22, 10.3),
  new THREE.MeshBasicMaterial({ color: 0x123363, transparent: true, opacity: 0.30, depthWrite: false })
);
slabLower.position.y = -0.28;
const slabUpper = new THREE.Mesh(
  new THREE.BoxGeometry(9.5, 0.30, 9.5),
  new THREE.MeshBasicMaterial({ color: 0x173a70, transparent: true, opacity: 0.5, depthWrite: false })
);
slabUpper.position.y = 0.05;
const slabEdges = new THREE.LineSegments(new THREE.EdgesGeometry(slabUpper.geometry), EDGE);
slabEdges.position.y = 0.05;
city.add(slabLower, slabUpper, slabEdges);

/* ---------- 道路：沥青贴图（边线+虚线）+ 路缘石 ---------- */
function roadTexture() {
  const t = canvasTex(256, 32, (x) => {
    x.fillStyle = '#0a1526';
    x.fillRect(0, 0, 256, 32);
    x.fillStyle = 'rgba(140,200,255,.7)';       // 两侧实线边线
    x.fillRect(0, 2, 256, 2);
    x.fillRect(0, 28, 256, 2);
    x.fillStyle = 'rgba(170,220,255,.8)';       // 中央虚线
    for (let i = 0; i < 256; i += 32) x.fillRect(i, 15, 16, 2);
  });
  t.wrapS = THREE.RepeatWrapping;
  t.repeat.set(4, 1);
  return t;
}
const curbMat = new THREE.MeshBasicMaterial({ color: 0x182c4e });
function roadAlongX(z) {
  const g = new THREE.Group();
  const r = new THREE.Mesh(
    new THREE.PlaneGeometry(9.2, 0.95),
    new THREE.MeshBasicMaterial({ map: roadTexture() })
  );
  r.rotation.x = -Math.PI / 2;
  r.position.set(0, CITY_TOP + 0.004, z);
  g.add(r);
  [-0.55, 0.55].forEach((dz) => {
    const curb = new THREE.Mesh(new THREE.BoxGeometry(9.2, 0.045, 0.1), curbMat);
    curb.position.set(0, CITY_TOP + 0.022, z + dz);
    g.add(curb);
  });
  return g;
}
function roadAlongZ(x) {
  const g = new THREE.Group();
  g.rotation.y = Math.PI / 2;                  // 复用横向道路，整体转 90°
  const r = new THREE.Mesh(
    new THREE.PlaneGeometry(9.2, 0.95),
    new THREE.MeshBasicMaterial({ map: roadTexture() })
  );
  r.rotation.x = -Math.PI / 2;
  r.position.set(0, CITY_TOP + 0.004, 0);
  g.add(r);
  [-0.55, 0.55].forEach((dx) => {
    const curb = new THREE.Mesh(new THREE.BoxGeometry(9.2, 0.045, 0.1), curbMat);
    curb.position.set(0, CITY_TOP + 0.022, dx);
    g.add(curb);
  });
  g.position.x = x;
  return g;
}
city.add(roadAlongX(1.7), roadAlongZ(1.7));

/* ---------- 斑马线（长边顺着车行方向，横排铺过路面） ---------- */
const zebraMat = new THREE.MeshBasicMaterial({ color: 0xd8ecff, transparent: true, opacity: 0.85 });
function crosswalk(alongX, at) {
  for (let i = -2; i <= 2; i++) {
    const s = new THREE.Mesh(
      new THREE.PlaneGeometry(alongX ? 0.55 : 0.09, alongX ? 0.09 : 0.55),
      zebraMat
    );
    s.rotation.x = -Math.PI / 2;
    if (alongX) s.position.set(at, CITY_TOP + 0.012, 1.7 + i * 0.19);
    else s.position.set(1.7 + i * 0.19, CITY_TOP + 0.012, at);
    city.add(s);
  }
}
crosswalk(true, 0.2);
crosswalk(true, 3.2);
crosswalk(false, 0.2);
crosswalk(false, 3.2);

/* ---------- 路灯（弯臂 + 暖白灯头） ---------- */
const lampPoleMat = new THREE.MeshBasicMaterial({ color: 0x33507c });
const lampGlowMat = new THREE.MeshBasicMaterial({ color: 0xfff0c0 });
function lamp(x, z, dx, dz) {
  const g = new THREE.Group();
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.032, 0.6, 6), lampPoleMat);
  pole.position.y = CITY_TOP + 0.3;
  const arm = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.02, 0.02), lampPoleMat);
  arm.position.set(dx * 0.12, CITY_TOP + 0.58, dz * 0.12);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.05, 8, 8), lampGlowMat);
  head.position.set(dx * 0.24, CITY_TOP + 0.56, dz * 0.24);
  g.add(pole, arm, head);
  g.position.set(x, 0, z);
  city.add(g);
}
[[-3.6, 1.0, 0, 1], [-1.2, 1.0, 0, 1], [3.2, 2.4, 0, -1], [4.4, 1.0, 0, 1],
 [1.0, -3.6, 1, 0], [1.0, -1.2, 1, 0], [2.4, 3.2, -1, 0], [1.0, 4.4, 1, 0]
].forEach(([x, z, dx, dz]) => lamp(x, z, dx, dz));

/* ---------- 楼群（带亮窗纹理） ---------- */
const roofMat = new THREE.MeshBasicMaterial({ color: 0x0b1e42 });
/* 城市亮窗大楼已全部移除：登录沙盘改为「变电站园区」主题，
   原大楼位置改建设备区（GIS 舱 / 电容器组 / 避雷器，见下方园区扩建段）。 */

/* ---------- 路灯（园区道路照明，保留） ---------- */

/* ---------- 路边树 ---------- */
const treeLeaf = new THREE.MeshBasicMaterial({ color: 0x1f7a5e });
const treeTrunk = new THREE.MeshBasicMaterial({ color: 0x27415c });
[[-4.0, 0.4], [-4.0, 1.0], [0.4, -4.0], [1.0, -4.0], [4.1, 1.0], [4.1, 1.6],
 [-4.1, 3.9], [-3.6, 4.3], [0.4, 4.2], [1.0, 4.2], [4.2, -3.4], [-0.4, -4.1], [3.4, -4.1]
].forEach(([x, z]) => {
  const t = new THREE.Group();
  const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.16, 6), treeTrunk);
  trunk.position.y = CITY_TOP + 0.08;
  const leaf = new THREE.Mesh(new THREE.SphereGeometry(0.13, 10, 10), treeLeaf);
  leaf.position.y = CITY_TOP + 0.24;
  leaf.scale.y = 1.25;
  t.add(trunk, leaf);
  t.position.set(x, 0, z);
  city.add(t);
});

/* ---------- 输电铁塔 + 导线 + 变压器（变电运维项目元素，暖色点缀） ---------- */
const steelMat = new THREE.MeshBasicMaterial({ color: 0x4a6f9e });
function pylon(h) {
  const g = new THREE.Group();
  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.16, h, 6), steelMat);
  mast.position.y = CITY_TOP + h / 2;
  g.add(mast);
  [0.55, 0.72, 0.89].forEach((f, i) => {
    const armW = 1.5 - i * 0.4;
    const arm = new THREE.Mesh(new THREE.BoxGeometry(armW, 0.035, 0.035), steelMat);
    arm.position.y = CITY_TOP + h * f;
    g.add(arm);
  });
  const tip = new THREE.Mesh(
    new THREE.SphereGeometry(0.05, 8, 8),
    new THREE.MeshBasicMaterial({ color: 0xff6b5a })
  );
  tip.position.y = CITY_TOP + h + 0.06;
  g.add(tip);
  return g;
}
const PYLON_H = 2.5;
const pylonA = pylon(PYLON_H); pylonA.position.set(-3.7, 0, -3.7);
const pylonB = pylon(PYLON_H); pylonB.position.set(3.8, 0, -3.7);
city.add(pylonA, pylonB);

/* 导线：三点插值出弧垂，暖橙色在蓝色场景里做颜色对比 */
function wire(from, to, sag = 0.35) {
  const pts = [];
  for (let i = 0; i <= 24; i++) {
    const k = i / 24;
    const p = new THREE.Vector3().lerpVectors(from, to, k);
    p.y -= Math.sin(k * Math.PI) * sag;
    pts.push(p);
  }
  return new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color: 0xffb45a, transparent: true, opacity: 0.85 })
  );
}
const wireY = CITY_TOP + PYLON_H * 0.55;
[-0.55, 0, 0.55].forEach((off) => {
  city.add(wire(
    new THREE.Vector3(-3.7 + off, wireY, -3.7),
    new THREE.Vector3(3.8 + off, wireY, -3.7)
  ));
});

/* 主变：油箱 + 三支套管（套管顶亮暖色） */
(function transformer() {
  const g = new THREE.Group();
  const tank = new THREE.Mesh(
    new THREE.BoxGeometry(0.55, 0.34, 0.42),
    new THREE.MeshBasicMaterial({ color: 0x2a4a70 })
  );
  tank.position.y = CITY_TOP + 0.17;
  g.add(tank);
  for (let i = -1; i <= 1; i++) {
    const bush = new THREE.Mesh(
      new THREE.CylinderGeometry(0.028, 0.04, 0.24, 8),
      new THREE.MeshBasicMaterial({ color: 0x8fb0d8 })
    );
    bush.position.set(i * 0.16, CITY_TOP + 0.44, 0);
    g.add(bush);
    const cap = new THREE.Mesh(
      new THREE.SphereGeometry(0.035, 8, 8),
      new THREE.MeshBasicMaterial({ color: 0xffc36b })
    );
    cap.position.set(i * 0.16, CITY_TOP + 0.58, 0);
    g.add(cap);
  }
  g.position.set(0.9, 0, -4.1);
  city.add(g);
})();

/* ====================================================================
   变电站园区一角（右前象限，原高楼区域清空改建）
   设备取自 110kV 园区里真实用到的：门型构架 / 主变（散热片+储油柜）/
   支柱绝缘子设备 / 避雷针 / 值班室 / 围栏，配色沿用场景钢蓝 + 暖金点缀。
==================================================================== */
const porcelainMat = new THREE.MeshBasicMaterial({ color: 0x9db6da });
const capMat = new THREE.MeshBasicMaterial({ color: 0xffc36b });
const YARD = { cx: 3.5, cz: 3.4, hw: 0.95, hd: 1.1 };   // 场地中心与半宽/半深
const gantryH = 1.15;

/* ---------- 场地：碎石面 + 金色描边 ---------- */
(function yardApron() {
  const apron = new THREE.Mesh(
    new THREE.BoxGeometry(YARD.hw * 2, 0.05, YARD.hd * 2),
    new THREE.MeshBasicMaterial({ color: 0x0e2140 })
  );
  apron.position.set(YARD.cx, CITY_TOP + 0.025, YARD.cz);
  const edge = new THREE.LineSegments(
    new THREE.EdgesGeometry(apron.geometry),
    new THREE.LineBasicMaterial({ color: 0xd9bd8a, transparent: true, opacity: 0.55 })
  );
  edge.position.copy(apron.position);
  city.add(apron, edge);
})();

/* ---------- 门型构架：A 型柱 + 双横梁 + 三相绝缘子串 ---------- */
function gantry(z) {
  const g = new THREE.Group();
  [-1, 1].forEach((s) => {
    const px = s * 0.9;
    [-1, 1].forEach((t) => {
      const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.026, 0.04, gantryH, 6), steelMat);
      leg.position.set(px + t * 0.07, gantryH / 2, 0);
      leg.rotation.z = -t * 0.1;
      g.add(leg);
    });
    const foot = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.03, 0.16), steelMat);
    foot.position.set(px, 0.015, 0);
    g.add(foot);
  });
  [gantryH, gantryH - 0.2].forEach((y, i) => {
    const beam = new THREE.Mesh(new THREE.BoxGeometry(2.05, 0.045, i ? 0.05 : 0.07), steelMat);
    beam.position.y = y;
    g.add(beam);
  });
  // 三相绝缘子串挂在横梁下
  [-0.66, 0, 0.66].forEach((ox) => {
    const s = new THREE.Mesh(new THREE.CylinderGeometry(0.016, 0.016, 0.13, 6), porcelainMat);
    s.position.set(ox, gantryH - 0.1, 0);
    g.add(s);
  });
  g.position.set(YARD.cx, CITY_TOP, z);
  city.add(g);
  return g;
}
gantry(2.7);
gantry(4.1);
/* 构架间母线：三相各一条，弧垂收浅 */
const phaseXs = [-0.66, 0, 0.66];
const busY = CITY_TOP + gantryH - 0.18;
phaseXs.forEach((ox) => {
  city.add(wire(
    new THREE.Vector3(YARD.cx + ox, busY, 2.7),
    new THREE.Vector3(YARD.cx + ox, busY, 4.1),
    0.2
  ));
});

/* ---------- 主变：底座 + 油箱 + 两侧散热片 + 储油柜 + 三支套管 ---------- */
function mainTransformer(x, z) {
  const g = new THREE.Group();
  const base = new THREE.Mesh(new THREE.BoxGeometry(0.68, 0.05, 0.5), steelMat);
  base.position.y = 0.025;
  g.add(base);
  const tank = new THREE.Mesh(
    new THREE.BoxGeometry(0.58, 0.32, 0.44),
    new THREE.MeshBasicMaterial({ color: 0x2a4a70 })
  );
  tank.position.y = 0.21;
  g.add(tank);
  g.add(new THREE.LineSegments(new THREE.EdgesGeometry(tank.geometry), EDGE).translateY(0.21));
  // 两侧散热片（每侧 4 片薄板）
  [-1, 1].forEach((s) => {
    for (let i = 0; i < 4; i++) {
      const fin = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.24, 0.34), steelMat);
      fin.position.set(s * 0.315, 0.21, -0.13 + i * 0.088);
      g.add(fin);
    }
  });
  // 储油柜：油箱顶横置圆筒
  const cons = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.4, 10), new THREE.MeshBasicMaterial({ color: 0x3a5c86 }));
  cons.rotation.z = Math.PI / 2;
  cons.position.y = 0.43;
  g.add(cons);
  // 三支高压套管 + 顶帽
  [-0.14, 0, 0.14].forEach((ox) => {
    const bush = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.036, 0.22, 8), porcelainMat);
    bush.position.set(ox, 0.48, 0);
    g.add(bush);
    const cap = new THREE.Mesh(new THREE.SphereGeometry(0.03, 8, 8), capMat);
    cap.position.set(ox, 0.6, 0);
    g.add(cap);
  });
  g.position.set(x, CITY_TOP, z);
  city.add(g);
}
mainTransformer(YARD.cx - 0.42, 3.4);
mainTransformer(YARD.cx + 0.42, 3.4);

/* ---------- 支柱绝缘子设备（隔离开关 / 互感器）：底座 + 瓷裙叠柱 ---------- */
function postEquipment(x, z) {
  const g = new THREE.Group();
  const base = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.07, 0.24), steelMat);
  base.position.y = 0.035;
  g.add(base);
  let y = 0.07;
  for (let i = 0; i < 3; i++) {
    const col = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.022, 0.09, 8), porcelainMat);
    col.position.y = y + 0.045;
    g.add(col);
    const shed = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.028, 0.025, 10), porcelainMat);
    shed.position.y = y + 0.08;
    g.add(shed);
    y += 0.09;
  }
  const top = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.03, 0.1), steelMat);
  top.position.y = y + 0.015;
  g.add(top);
  const tip = new THREE.Mesh(new THREE.SphereGeometry(0.022, 8, 8), capMat);
  tip.position.y = y + 0.05;
  g.add(tip);
  g.position.set(x, CITY_TOP, z);
  city.add(g);
}
[[YARD.cx - 0.66, 3.4], [YARD.cx + 0.66, 3.4], [YARD.cx - 0.66, 2.95], [YARD.cx + 0.66, 2.95]].forEach(([x, z]) => postEquipment(x, z));

/* ---------- 避雷针：细长杆 + 锥顶 + 亮球 ---------- */
(function lightningMast() {
  const g = new THREE.Group();
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.016, 0.03, 2.3, 6), steelMat);
  pole.position.y = 1.15;
  g.add(pole);
  const cone = new THREE.Mesh(new THREE.ConeGeometry(0.035, 0.16, 8), steelMat);
  cone.position.y = 2.38;
  g.add(cone);
  const ball = new THREE.Mesh(new THREE.SphereGeometry(0.032, 8, 8), capMat);
  ball.position.y = 2.5;
  g.add(ball);
  const foot = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.04, 0.14), steelMat);
  foot.position.y = 0.02;
  g.add(foot);
  g.position.set(YARD.cx - YARD.hw + 0.12, CITY_TOP, YARD.cz + YARD.hd - 0.12);
  city.add(g);
})();

/* ---------- 值班室（控制小楼）：亮窗盒体 + 平顶 ---------- */
(function controlRoom() {
  const g = new THREE.Group();
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(0.62, 0.4, 0.5),
    new THREE.MeshBasicMaterial({ map: buildingTexture() })
  );
  body.position.y = 0.2;
  g.add(body);
  const roof = new THREE.Mesh(new THREE.BoxGeometry(0.68, 0.04, 0.56), new THREE.MeshBasicMaterial({ color: 0x0b1e42 }));
  roof.position.y = 0.42;
  g.add(roof);
  g.add(new THREE.LineSegments(new THREE.EdgesGeometry(roof.geometry), EDGE).translateY(0.42));
  g.position.set(YARD.cx + YARD.hw - 0.38, CITY_TOP, YARD.cz - YARD.hd + 0.32);
  city.add(g);
})();

/* ---------- 围栏：北/东/南三面立柱 + 双横杆（西面留门进车） ---------- */
(function fence() {
  const postGeo = new THREE.CylinderGeometry(0.011, 0.011, 0.24, 5);
  const railMat = steelMat;
  const x0 = YARD.cx - YARD.hw, x1 = YARD.cx + YARD.hw;
  const z0 = YARD.cz - YARD.hd, z1 = YARD.cz + YARD.hd;
  const place = (x, z) => {
    const p = new THREE.Mesh(postGeo, railMat);
    p.position.set(x, CITY_TOP + 0.12, z);
    city.add(p);
  };
  const rail = (x, z, len, alongX) => {
    const r = new THREE.Mesh(new THREE.BoxGeometry(alongX ? len : 0.015, 0.015, alongX ? 0.015 : len), railMat);
    r.position.set(x, CITY_TOP + 0.19, z);
    city.add(r);
  };
  for (let x = x0; x <= x1 + 0.001; x += 0.32) { place(x, z0); place(x, z1); }
  for (let z = z0; z <= z1 + 0.001; z += 0.32) { place(x1, z); }
  // 三根整横杆（北/南/东），西面留门
  rail((x0 + x1) / 2, z0, x1 - x0, true);
  rail((x0 + x1) / 2, z1, x1 - x0, true);
  rail(x1, (z0 + z1) / 2, z1 - z0, false);
})();

/* ---------- 园区扩建 · 左前设备区（原城市大楼位置）：GIS 预制舱 + 电容器组 + 避雷器 ---------- */
(function westYard() {
  const apron = new THREE.Mesh(
    new THREE.BoxGeometry(2.3, 0.05, 2.3),
    new THREE.MeshBasicMaterial({ color: 0x0e2140 })
  );
  apron.position.set(-3.4, CITY_TOP + 0.025, 3.5);
  const edge = new THREE.LineSegments(
    new THREE.EdgesGeometry(apron.geometry),
    new THREE.LineBasicMaterial({ color: 0xd9bd8a, transparent: true, opacity: 0.55 })
  );
  edge.position.copy(apron.position);
  city.add(apron, edge);

  // GIS 预制舱 ×2：长箱体 + 竖棱线 + 端部门板
  const cabinMat = new THREE.MeshBasicMaterial({ color: 0x24406e });
  [[-3.75, 3.1], [-3.75, 3.9]].forEach(([x, z]) => {
    const g = new THREE.Group();
    const body = new THREE.Mesh(new THREE.BoxGeometry(1.25, 0.34, 0.5), cabinMat);
    body.position.y = 0.22;
    g.add(body);
    g.add(new THREE.LineSegments(new THREE.EdgesGeometry(body.geometry), EDGE).translateY(0.22));
    for (let i = 0; i < 6; i++) {
      const rib = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.3, 0.52), steelMat);
      rib.position.set(-0.5 + i * 0.2, 0.22, 0);
      g.add(rib);
    }
    const door = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.22, 0.24), capMat);
    door.position.set(0.64, 0.16, 0);
    g.add(door);
    g.position.set(x, CITY_TOP, z);
    city.add(g);
  });

  // 电容器组：钢架两层 + 三列瓷瓶电容柱
  (function capacitorRack() {
    const g = new THREE.Group();
    const frame = new THREE.Mesh(new THREE.BoxGeometry(0.52, 0.05, 0.4), steelMat);
    frame.position.y = 0.025;
    g.add(frame);
    const beam = new THREE.Mesh(new THREE.BoxGeometry(0.52, 0.03, 0.4), steelMat);
    beam.position.y = 0.3;
    g.add(beam);
    [-0.17, 0, 0.17].forEach((ox) => {
      [-0.1, 0.1].forEach((oz) => {
        const unit = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.26, 8), porcelainMat);
        unit.position.set(ox, 0.19, oz);
        g.add(unit);
        const cap = new THREE.Mesh(new THREE.SphereGeometry(0.028, 8, 8), capMat);
        cap.position.set(ox, 0.34, oz);
        g.add(cap);
      });
    });
    g.position.set(-4.25, CITY_TOP, 2.8);
    city.add(g);
  })();

  // 避雷器 ×2：细高瓷柱 + 均压环 + 顶帽
  [[-2.9, 2.75], [-2.9, 4.25]].forEach(([x, z]) => {
    const g = new THREE.Group();
    const base = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.05, 0.18), steelMat);
    base.position.y = 0.025;
    g.add(base);
    const col = new THREE.Mesh(new THREE.CylinderGeometry(0.028, 0.038, 0.52, 8), porcelainMat);
    col.position.y = 0.31;
    g.add(col);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.06, 0.008, 6, 18), steelMat);
    ring.rotation.x = Math.PI / 2;
    ring.position.y = 0.42;
    g.add(ring);
    const cap = new THREE.Mesh(new THREE.SphereGeometry(0.032, 8, 8), capMat);
    cap.position.y = 0.6;
    g.add(cap);
    g.position.set(x, CITY_TOP, z);
    city.add(g);
  });
})();

/* ====================================================================
   园区升级 v4 · 高阶版：综合主控楼 / 大门门卫 / 旗杆 / 巡检机器人 /
   消防设施 / 泛光灯 / 无功补偿区，把沙盘补成一座完整的高阶变电站园区。
==================================================================== */
const patrols = [];    // 巡逻体（animate 中沿矩形路径推进）
const blinkers = [];   // 周期闪烁的警示灯（animate 中点亮/熄灭）

/* ---------- 综合主控楼：两层退台 + 玻璃幕墙 + 屋顶天线 + 发光站牌 ---------- */
(function mainBuilding() {
  const g = new THREE.Group();
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(1.5, 0.62, 0.85),
    new THREE.MeshBasicMaterial({ map: buildingTexture() })
  );
  body.position.y = 0.31;
  g.add(body, new THREE.LineSegments(new THREE.EdgesGeometry(body.geometry), EDGE).translateY(0.31));
  const top = new THREE.Mesh(
    new THREE.BoxGeometry(1.05, 0.3, 0.58),
    new THREE.MeshBasicMaterial({ map: buildingTexture() })
  );
  top.position.y = 0.77;
  g.add(top, new THREE.LineSegments(new THREE.EdgesGeometry(top.geometry), EDGE).translateY(0.77));
  const roof = new THREE.Mesh(new THREE.BoxGeometry(1.12, 0.04, 0.64), roofMat);
  roof.position.y = 0.94;
  g.add(roof);
  // 屋顶天线 + 航空警示灯（闪烁）
  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.012, 0.4, 6), steelMat);
  mast.position.y = 1.14;
  g.add(mast);
  const beacon = new THREE.Mesh(new THREE.SphereGeometry(0.024, 8, 8), new THREE.MeshBasicMaterial({ color: 0xff5a5a }));
  beacon.position.y = 1.36;
  g.add(beacon);
  blinkers.push(beacon);
  // 发光站牌（canvas 中文纹理，金边金字）
  const plaqueTex = canvasTex(512, 128, (x, w, h) => {
    x.fillStyle = '#0a1a38';
    x.fillRect(0, 0, w, h);
    x.strokeStyle = '#d9bd8a';
    x.lineWidth = 6;
    x.strokeRect(6, 6, w - 12, h - 12);
    x.fillStyle = '#ffd98a';
    x.font = 'bold 56px "Microsoft YaHei", sans-serif';
    x.textAlign = 'center';
    x.textBaseline = 'middle';
    x.fillText('110kV 城东变电站', w / 2, h / 2 + 2);
  });
  const plaque = new THREE.Mesh(
    new THREE.PlaneGeometry(0.92, 0.23),
    new THREE.MeshBasicMaterial({ map: plaqueTex, transparent: true })
  );
  plaque.position.set(0, 1.0, 0.3);
  g.add(plaque);
  // 楼前小广场 + 台阶
  const plaza = new THREE.Mesh(new THREE.BoxGeometry(1.7, 0.03, 0.5), new THREE.MeshBasicMaterial({ color: 0x10254a }));
  plaza.position.set(0, 0.015, 0.66);
  g.add(plaza);
  g.position.set(-3.2, CITY_TOP, -3.2);
  city.add(g);
})();

/* ---------- 大门 + 门卫亭 + 道闸（主设备区西入口） ---------- */
(function mainGate() {
  const gx = YARD.cx - YARD.hw - 0.12, gz = YARD.cz;
  const g = new THREE.Group();
  // 门柱 ×2 + 金色顶帽 + 横梁
  [-0.3, 0.3].forEach((oz) => {
    const post = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.42, 0.07), new THREE.MeshBasicMaterial({ color: 0x1c3862 }));
    post.position.set(0, 0.21, oz);
    g.add(post);
    const cap = new THREE.Mesh(new THREE.SphereGeometry(0.045, 8, 8), capMat);
    cap.position.set(0, 0.44, oz);
    g.add(cap);
  });
  const beam = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, 0.62), capMat);
  beam.position.y = 0.47;
  g.add(beam);
  // 道闸：红白相间升降杆（半抬状态）
  const bar = new THREE.Group();
  for (let i = 0; i < 5; i++) {
    const seg = new THREE.Mesh(new THREE.BoxGeometry(0.09, 0.014, 0.014), new THREE.MeshBasicMaterial({ color: i % 2 ? 0xe8f2ff : 0xd85555 }));
    seg.position.x = 0.05 + i * 0.09;
    bar.add(seg);
  }
  bar.rotation.z = 0.9;
  bar.position.set(-0.04, 0.16, 0.3);
  g.add(bar);
  // 门卫亭：亮窗盒体
  const hut = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.2, 0.2), new THREE.MeshBasicMaterial({ map: buildingTexture() }));
  hut.position.set(0.16, 0.1, 0.52);
  g.add(hut);
  const hutRoof = new THREE.Mesh(new THREE.BoxGeometry(0.26, 0.02, 0.24), roofMat);
  hutRoof.position.set(0.16, 0.21, 0.52);
  g.add(hutRoof);
  g.position.set(gx, CITY_TOP, gz);
  city.add(g);
})();

/* ---------- 旗杆 ×3（中高旁低，金旗面） ---------- */
[[2.35, 0.72, 0.62], [2.65, 0.72, 0.78], [2.95, 0.72, 0.62]].forEach(([x, z, h]) => {
  const g = new THREE.Group();
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.012, h, 6), new THREE.MeshBasicMaterial({ color: 0xbfd4ef }));
  pole.position.y = h / 2;
  g.add(pole);
  const ball = new THREE.Mesh(new THREE.SphereGeometry(0.018, 8, 8), capMat);
  ball.position.y = h + 0.01;
  g.add(ball);
  const flag = new THREE.Mesh(new THREE.PlaneGeometry(0.2, 0.11), new THREE.MeshBasicMaterial({ color: 0xd9bd8a, side: THREE.DoubleSide, transparent: true, opacity: 0.92 }));
  flag.position.set(0.11, h - 0.09, 0);
  g.add(flag);
  const foot = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.045, 0.05, 8), steelMat);
  foot.position.y = 0.025;
  g.add(foot);
  g.position.set(x, CITY_TOP, z);
  city.add(g);
});

/* ---------- 无功补偿区（左后象限）：支柱设备 ×3 + 独立避雷针 ---------- */
[[-2.5, -2.3], [-3.3, -1.85], [-4.15, -2.5]].forEach(([x, z]) => postEquipment(x, z));
(function surgeMast2() {
  const g = new THREE.Group();
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.014, 0.028, 1.9, 6), steelMat);
  pole.position.y = 0.95;
  g.add(pole);
  const cone = new THREE.Mesh(new THREE.ConeGeometry(0.032, 0.14, 8), steelMat);
  cone.position.y = 1.96;
  g.add(cone);
  const ball = new THREE.Mesh(new THREE.SphereGeometry(0.03, 8, 8), new THREE.MeshBasicMaterial({ color: 0xff5a5a }));
  ball.position.y = 2.06;
  g.add(ball);
  blinkers.push(ball);
  g.position.set(-1.5, CITY_TOP, -3.6);
  city.add(g);
})();

/* ---------- 泛光灯杆 ×2（高杆双灯头，暖白发光） ---------- */
[[-1.9, -1.3], [-4.35, -3.5]].forEach(([x, z]) => {
  const g = new THREE.Group();
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.02, 1.35, 6), steelMat);
  pole.position.y = 0.675;
  g.add(pole);
  const arm = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.02, 0.02), steelMat);
  arm.position.set(0.12, 1.34, 0);
  g.add(arm);
  [-0.02, 0.26].forEach((ox) => {
    const head = new THREE.Mesh(new THREE.BoxGeometry(0.09, 0.03, 0.06), new THREE.MeshBasicMaterial({ color: 0xffe9c4 }));
    head.position.set(ox, 1.31, 0);
    g.add(head);
  });
  g.position.set(x, CITY_TOP, z);
  city.add(g);
});

/* ---------- 消防设施：消防栓 ×2 + 沙箱 ×2（沿道路侧摆放） ---------- */
const hydrantMat = new THREE.MeshBasicMaterial({ color: 0xc74444 });
[[2.2, 2.1], [-1.4, 2.15]].forEach(([x, z]) => {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CylinderGeometry(0.028, 0.034, 0.12, 8), hydrantMat);
  body.position.y = 0.07;
  g.add(body);
  const cap = new THREE.Mesh(new THREE.SphereGeometry(0.026, 8, 8), hydrantMat);
  cap.position.y = 0.14;
  g.add(cap);
  [-0.035, 0.035].forEach((oz) => {
    const nozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.03, 6), hydrantMat);
    nozzle.rotation.x = Math.PI / 2;
    nozzle.position.set(0, 0.08, oz);
    g.add(nozzle);
  });
  g.position.set(x, CITY_TOP, z);
  city.add(g);
});
[[-2.0, 2.2], [1.5, 2.2]].forEach(([x, z]) => {
  const box = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.07, 0.1), new THREE.MeshBasicMaterial({ color: 0xb5915c }));
  box.position.set(x, CITY_TOP + 0.035, z);
  city.add(box);
  const edge = new THREE.LineSegments(new THREE.EdgesGeometry(box.geometry), EDGE);
  edge.position.copy(box.position);
  city.add(edge);
});

/* ---------- 巡检机器人 + 机器人舱（沿主设备区围栏巡逻） ---------- */
(function inspectorRobot() {
  // 机器人舱：小圆顶屋
  const dock = new THREE.Group();
  const base = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.16, 0.08, 12), steelMat);
  base.position.y = 0.04;
  dock.add(base);
  const dome = new THREE.Mesh(
    new THREE.SphereGeometry(0.11, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2),
    new THREE.MeshBasicMaterial({ color: 0x27497c })
  );
  dome.position.y = 0.08;
  dock.add(dome);
  const stripe = new THREE.Mesh(new THREE.TorusGeometry(0.115, 0.006, 6, 20), capMat);
  stripe.rotation.x = Math.PI / 2;
  stripe.position.y = 0.09;
  dock.add(stripe);
  dock.position.set(YARD.cx - YARD.hw + 0.3, CITY_TOP, YARD.cz - YARD.hd + 0.3);
  city.add(dock);

  // 机器人：蓝白车身 + 球形头 + 前部探头 + 顶部警灯
  const robot = new THREE.Group();
  const body = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.06, 0.1), new THREE.MeshBasicMaterial({ color: 0xdde9fb }));
  body.position.y = 0.05;
  robot.add(body, new THREE.LineSegments(new THREE.EdgesGeometry(body.geometry), EDGE).translateY(0.05));
  const skirt = new THREE.Mesh(new THREE.BoxGeometry(0.17, 0.02, 0.11), new THREE.MeshBasicMaterial({ color: 0x2a5f9e }));
  skirt.position.y = 0.02;
  robot.add(skirt);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.035, 10, 8), new THREE.MeshBasicMaterial({ color: 0x9fc4f5 }));
  head.position.set(0.06, 0.11, 0);
  robot.add(head);
  const eye = new THREE.Mesh(new THREE.SphereGeometry(0.014, 8, 8), new THREE.MeshBasicMaterial({ color: 0x67f5ff }));
  eye.position.set(0.095, 0.11, 0);
  robot.add(eye);
  const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.014, 8, 8), new THREE.MeshBasicMaterial({ color: 0xffc36b }));
  lamp.position.y = 0.095;
  robot.add(lamp);
  blinkers.push(lamp);
  // 初始放在围栏东南角，animate 里沿矩形路径巡逻
  robot.position.set(YARD.cx, CITY_TOP, YARD.cz + YARD.hd);
  city.add(robot);
  patrols.push({
    obj: robot,
    x0: YARD.cx - YARD.hw + 0.12, x1: YARD.cx + YARD.hw - 0.12,
    z0: YARD.cz - YARD.hd + 0.12, z1: YARD.cz + YARD.hd - 0.12,
    speed: 0.16
  });
})();

/* ---------- 绿篱（围栏外围一圈矮灌木） ---------- */
[[-4.4, 2.3], [-4.5, 2.9], [-4.45, 4.3], [4.6, 2.6], [4.62, 3.6], [3.1, 4.62], [3.9, 4.65]
].forEach(([x, z]) => {
  const bush = new THREE.Mesh(new THREE.SphereGeometry(0.09, 8, 6), treeLeaf);
  bush.scale.y = 0.7;
  bush.position.set(x, CITY_TOP + 0.06, z);
  city.add(bush);
});

/* ---------- 园区绿化补植（沿道路与设备区周边） ---------- */
[[-2.4, 0.9], [-1.7, 1.1], [2.3, 1.2], [-1.6, 4.3], [-2.5, 4.5], [1.9, 4.4]
].forEach(([x, z]) => {
  const t = new THREE.Group();
  const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.16, 6), treeTrunk);
  trunk.position.y = CITY_TOP + 0.08;
  const leaf = new THREE.Mesh(new THREE.SphereGeometry(0.13, 10, 10), treeLeaf);
  leaf.position.y = CITY_TOP + 0.24;
  leaf.scale.y = 1.25;
  t.add(trunk, leaf);
  t.position.set(x, 0, z);
  city.add(t);
});


/* ---------- 悬浮数据面板 ---------- */
const panels = [];
[["技能达标率分析", -2.6, 3.6, -2.0, 0.45, 2.5],
 ["考试成绩统计", 2.6, 4.6, 1.6, -0.5, 1.9],
 ["安全运行监测", 0.2, 5.6, -3.6, 0.1, 1.6]].forEach(([t, x, y, z, ry, s]) => {
  const p = new THREE.Mesh(
    new THREE.PlaneGeometry(2.6 * s * 0.64, 1.62 * s * 0.64),
    new THREE.MeshBasicMaterial({ map: panelTexture(t), transparent: true, side: THREE.DoubleSide, depthWrite: false })
  );
  p.position.set(x, y, z);
  p.rotation.y = ry;
  p.userData = { baseY: y };
  panels.push(p);
  city.add(p);
});

/* 城市车流已移除：园区沙盘以设备与动效面板为主 */

/* ====================================================================
   地面环境：涟漪 + 光轨 + 星尘 + 背景辉光
==================================================================== */
const GROUND_Y = -2.5;

/* 涟漪：从基座向外扩散的圆环 */
const ripples = [];
for (let i = 0; i < 3; i++) {
  const r = new THREE.Mesh(
    new THREE.RingGeometry(3.6, 3.78, 80),
    new THREE.MeshBasicMaterial({ color: 0x2f9fd8, transparent: true, opacity: 0.4, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false })
  );
  r.rotation.x = -Math.PI / 2;
  r.position.set(-8.0, GROUND_Y + 0.01, 0);
  r.userData = { phase: i / 3 };
  ripples.push(r);
  scene.add(r);
}

/* 地面光轨（模拟远处车流长曝光） */
const trails = [];
const tTex = trailTexture();
for (let i = 0; i < 10; i++) {
  const alongX = i % 2 === 0;
  const t = new THREE.Mesh(
    new THREE.PlaneGeometry(4.2, 0.12),
    new THREE.MeshBasicMaterial({ map: tTex, transparent: true, opacity: 0.65, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide })
  );
  if (!alongX) t.rotation.y = Math.PI / 2;
  const lane = (4.5 + (i >> 1) * 2.6) * (i % 4 < 2 ? 1 : -1);
  t.userData = { alongX, lane, speed: (7 + (i % 4) * 2.2) * (alongX ? 1 : 0.8), offset: i * 9.3, dirv: i % 3 === 0 ? -1 : 1 };
  trails.push(t);
  scene.add(t);
}
/* 光轨所在的地板 */
const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(140, 140),
  new THREE.MeshBasicMaterial({ color: 0x030711 })
);
ground.rotation.x = -Math.PI / 2;
ground.position.y = GROUND_Y - 0.02;
scene.add(ground);

/* 星尘 */
const starGeo = new THREE.BufferGeometry();
const starN = 380;
const pos = new Float32Array(starN * 3);
for (let i = 0; i < starN; i++) {
  pos[i * 3] = (Math.random() - 0.5) * 90;
  pos[i * 3 + 1] = Math.random() * 26 - 3;
  pos[i * 3 + 2] = (Math.random() - 0.5) * 90;
}
starGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
const stars = new THREE.Points(starGeo, new THREE.PointsMaterial({
  color: 0x88bbff, size: 0.06, transparent: true, opacity: 0.45, depthWrite: false
}));
scene.add(stars);

/* 背景大光晕 */
const glow = new THREE.Sprite(new THREE.SpriteMaterial({
  map: glowSpriteTexture(), transparent: true, opacity: 0.5, depthWrite: false, blending: THREE.AdditiveBlending
}));
glow.scale.set(46, 34, 1);
glow.position.set(-8, 6, -14);
scene.add(glow);

/* ---------- 交互与动画 ---------- */
/* ---------- 小范围环绕观察（拖拽只在初始视角附近小幅转动） ---------- */
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;        // 阻尼，转动有惯性更顺滑
controls.dampingFactor = 0.06;
controls.enablePan = false;           // 关闭平移，防止把场景拖丢
controls.minDistance = 10;
controls.maxDistance = 45;
// 初始方位角 atan2(12.2, 20.5) ≈ 0.54 rad，左右各放开约 0.55 rad（±30°）
controls.minAzimuthAngle = -0.05;
controls.maxAzimuthAngle = 1.13;
// 俯仰限制在初始视角附近小幅上下
controls.minPolarAngle = 0.85;
controls.maxPolarAngle = 1.5;
controls.autoRotate = false;          // 不自动转圈，只响应用户拖拽

/* ---------- 响应式布局：宽屏把场景平移到画面左侧，窄屏回中 ---------- */
function layout() {
  const w = innerWidth;
  camShift = w > 1400 ? 9.5 : w > 1100 ? 7.5 : w > 900 ? 4.5 : 0;
  world.position.x = -4.0;
  glow.position.x = -4.0;
  ripples.forEach((r) => { r.position.x = -4.0; });
  // 旋转中心跟随场景当前位置（含相机右移量）
  controls.target.copy(LOOK_AT).addScaledVector(RIGHT, camShift);
}
layout();

addEventListener('resize', onResize);

function onResize() {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  composer.setSize(innerWidth, innerHeight);
  layout();
}
layout();

const clock = new THREE.Clock();
let rafId = 0;
function animate() {
  rafId = requestAnimationFrame(animate);
  const t = clock.getElapsedTime();

  /* 光环脉冲 */
  rings.forEach((r, i) => {
    const s = 1 + 0.045 * Math.sin(t * 1.7 + i * 1.3);
    r.scale.set(s, s, 1);
    r.material.opacity = 0.75 + 0.25 * Math.sin(t * 2.1 + i);
  });
  coreGlow.material.opacity = 0.26 + 0.12 * Math.sin(t * 2.3);
  beamOuter.material.opacity = 0.04 + 0.012 * Math.sin(t * 1.9);
  beamInner.material.opacity = 0.05 + 0.015 * Math.sin(t * 2.4 + 1);

  /* 城市整体轻微悬浮 + 摆动 */
  city.position.y = 5.2 + Math.sin(t * 0.7) * 0.16;
  city.rotation.y = Math.sin(t * 0.12) * 0.10;

  /* 面板浮动 */
  panels.forEach((p, i) => {
    p.position.y = p.userData.baseY + Math.sin(t * 1.0 + i * 2.1) * 0.13;
  });

  /* 巡检机器人沿围栏内侧矩形路径巡逻 */
  patrols.forEach((p) => {
    const w = p.x1 - p.x0, d = p.z1 - p.z0, per = 2 * (w + d);
    let s = ((t * p.speed) % per + per) % per;
    let x, z, ry;
    if (s < w) { x = p.x0 + s; z = p.z0; ry = 0; }
    else if ((s -= w) < d) { x = p.x1; z = p.z0 + s; ry = -Math.PI / 2; }
    else if ((s -= d) < w) { x = p.x1 - s; z = p.z1; ry = Math.PI; }
    else { s -= w; x = p.x0; z = p.z1 - s; ry = Math.PI / 2; }
    p.obj.position.set(x, CITY_TOP, z);
    p.obj.rotation.y = ry;
  });

  /* 警示灯周期闪烁（航空障碍灯 / 机器人警灯） */
  blinkers.forEach((b, i) => {
    b.visible = Math.sin(t * 3.2 + i * 1.9) > -0.35;
  });

  /* 地面涟漪扩散 */
  ripples.forEach((r) => {
    const k = (t * 0.22 + r.userData.phase) % 1;
    const s = 0.4 + k * 2.6;
    r.scale.set(s, s, 1);
    r.material.opacity = 0.42 * (1 - k);
  });

  /* 地面光轨 */
  trails.forEach((tr) => {
    const u = tr.userData;
    const range = 46;
    let p = ((t * u.speed + u.offset) % range);
    if (u.dirv > 0) p = p - range / 2; else p = range / 2 - p;
    if (u.alongX) tr.position.set(p, GROUND_Y + 0.05, u.lane);
    else tr.position.set(u.lane, GROUND_Y + 0.05, p);
  });

  stars.rotation.y = t * 0.006;

  /* 相机视差 */
  /* 相机：交给 OrbitControls（阻尼 + 自转 + 用户拖拽） */
  controls.update();

  composer.render();
}
animate();

/* 卸载清理：登录成功进入主界面后停掉渲染循环并解绑监听，不让后台白跑。 */
return function dispose() {
  cancelAnimationFrame(rafId);
  removeEventListener('resize', onResize);
  controls.dispose();
  renderer.dispose();
};
}