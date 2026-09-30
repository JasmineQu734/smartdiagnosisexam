<script setup>
/* 登录页的三维全息沙盘：纯代码绘制，不依赖任何位图素材，所以能一直动。
   整套几何都由等距（isometric）投影算出来：
     屏幕 x = (世界 x − 世界 y) × cos30° × U
     屏幕 y = (世界 x + 世界 y) × 0.5 × U − 世界 z × U
   1 个世界单位 = 12px：x 轴向右下、y 轴向左下、z 轴竖直向上，
   就是参考图那种 45° 斜俯视的“数字孪生沙盘”视角。
   改坐标即改布局，不用手写路径；颜色、发光与动画统一放在 login.css。 */

const U = 12;
const K = 0.866;                                  // cos30°
const viewBox = '-350 -360 800 760';

const round = (n) => Math.round(n * 100) / 100;
const pair = (x, y) => `${round(x)},${round(y)}`;
/* 世界坐标 → 屏幕坐标 */
const ground = (x, y, z = 0) => [(x - y) * K * U, ((x + y) * 0.5 - z) * U];
const pt = (x, y, z = 0) => pair(...ground(x, y, z));
/* 地面上的圆投影后是一枚正椭圆：横半轴 √1.5·U·r，纵半轴 √0.5·U·r */
/* 两点连线：SVG 的 <line> 要 x1/y1/x2/y2，这里把坐标对直接摊开 */
const seg = (a, b) => ({ x1: round(a[0]), y1: round(a[1]), x2: round(b[0]), y2: round(b[1]) });
const ringAt = (cx, cy, z, r) => {
  const [sx, sy] = ground(cx, cy, z);
  return { cx: round(sx), cy: round(sy), rx: round(1.2247 * U * r), ry: round(0.7071 * U * r) };
};
/* 长方体（台面/楼体）只画看得见的三个面：顶面 + 面向 +x、面向 +y 的两侧墙 */
const box = (x, y, w, d, h, z = 0) => {
  const x1 = x + w, y1 = y + d;
  return {
    top: [pt(x, y, z + h), pt(x1, y, z + h), pt(x1, y1, z + h), pt(x, y1, z + h)].join(' '),
    right: [pt(x1, y, z), pt(x1, y1, z), pt(x1, y1, z + h), pt(x1, y, z + h)].join(' '),
    left: [pt(x, y1, z), pt(x1, y1, z), pt(x1, y1, z + h), pt(x, y1, z + h)].join(' ')
  };
};
/* 楼体腰线：静态横条，只负责科技感，不做动画省性能 */
const floors = (t) => {
  const step = t.h / Math.max(2, Math.round(t.h / 3.4));
  const rows = [];
  for (let z = step; z < t.h - 0.5; z += step) {
    rows.push({ right: seg(ground(t.x + t.w, t.y, z), ground(t.x + t.w, t.y + t.d, z)), left: seg(ground(t.x, t.y + t.d, z), ground(t.x + t.w, t.y + t.d, z)) });
  }
  return rows.slice(0, 3);
};
/* 墙面发光窗格：facing 选墙，f 是沿墙起止比例，h0/h1 是高度起止比例 */
const win = (t, facing, f0, f1, h0, h1) => {
  const x1 = t.x + t.w, y1 = t.y + t.d;
  const span = facing === 'right' ? t.d : t.w;
  const a0 = span * f0, a1 = span * f1, z0 = t.h * h0, z1 = t.h * h1;
  return (facing === 'right'
    ? [pt(x1, t.y + a0, z0), pt(x1, t.y + a1, z0), pt(x1, t.y + a1, z1), pt(x1, t.y + a0, z1)]
    : [pt(t.x + a0, y1, z0), pt(t.x + a1, y1, z0), pt(t.x + a1, y1, z1), pt(t.x + a0, y1, z1)]
  ).join(' ');
};
/* 竖直光柱：上下两条水平边之间的梯形，就是从台面射向地面或空中的那道蓝光 */
const beam = (rTop, zTop, rBot, zBot, cx = 0, cy = 1.6) => {
  const [sx] = ground(cx, cy, 0);
  const syTop = ground(cx, cy, zTop)[1];
  const syBot = ground(cx, cy, zBot)[1];
  const rxTop = 1.2247 * U * rTop, rxBot = 1.2247 * U * rBot;
  return [[sx - rxTop, syTop], [sx + rxTop, syTop], [sx + rxBot, syBot], [sx - rxBot, syBot]].map(([x, y]) => pair(x, y)).join(' ');
};
/* ── 台体：一块 34×28 的悬浮基座，上面再叠一层薄甲板 ──────────────── */
const slab = box(-17, -14, 34, 28, 0, -5.4);
const slabEdges = [pt(17, -14, -5.4), pt(17, 14, -5.4), pt(-17, 14, -5.4)].join(' ');
const slabInset = [pt(15.2, -12.2, -5.4), pt(15.2, 12.2, -5.4), pt(-15.2, 12.2, -5.4)].join(' ');
const deck = box(-13.5, -11, 27, 22, 0.7);

/* ── 同心光环：站在甲板上，圆心留给中央光柱，前景留白给动态 ──────── */
const rings = [5.2, 7.6, 10, 12.4].map((r) => ringAt(0, 1.6, 0.78, r));
const deckInset = ringAt(0, 1.6, 0.78, 13.1);

/* ── 路网：沿 x、沿 y 各一条，路口落在台面左前方 ─────────────────── */
const roads = [
  { axis: 'x', from: -15.6, to: 15.6, a: 5.4, b: 9.8 },
  { axis: 'y', from: -12.4, to: 12.4, a: -15.2, b: -11.6 },
  { axis: 'x', from: -5.4, to: 15.6, a: 10.8, b: 13.8 }
];
const along = (axis, al, ac, z = 0) => (axis === 'x' ? ground(al, ac, z) : ground(ac, al, z));
const roadViews = roads.map((r) => ({
  key: r.axis + r.from,
  face: [[r.a, r.from], [r.b, r.from], [r.b, r.to], [r.a, r.to]].map(([ac, al]) => pair(...along(r.axis, al, ac, 0.74))).join(' '),
  dash: seg(along(r.axis, r.from, (r.a + r.b) / 2, 0.74), along(r.axis, r.to, (r.a + r.b) / 2, 0.74))
}));

/* ── 车流：沿路面往复，车尾拖一道灯光 ────────────────────────────── */
const LEN = 2.6, WID = 1.1, TRAIL = 6, SPAN = 30;
const cars = [
  { axis: 'x', ac: 6.5, at: -14, dir: 1, dur: 11, delay: -1 },
  { axis: 'x', ac: 8.7, at: -7, dir: 1, dur: 14, delay: -6 },
  { axis: 'x', ac: 8.7, at: 5, dir: -1, dur: 12, delay: -3 },
  { axis: 'x', ac: 6.5, at: 10, dir: -1, dur: 15, delay: -8 },
  { axis: 'y', ac: -12.6, at: -8, dir: 1, dur: 12, delay: -2 },
  { axis: 'y', ac: -12.6, at: 2, dir: -1, dur: 14, delay: -9 },
  { axis: 'y', ac: -14.2, at: -3, dir: 1, dur: 16, delay: -5 },
  { axis: 'x', ac: 11.4, at: -5, dir: 1, dur: 9, delay: -2 },
  { axis: 'x', ac: 13.0, at: 8, dir: -1, dur: 13, delay: -6 }
];
const carViews = cars.map((c) => {
  const rear = c.dir > 0 ? c.at : c.at + LEN;
  const tail = rear - c.dir * TRAIL;
  const quad = (a0, a1, b0, b1) => [[a0, b0], [a1, b0], [a1, b1], [a0, b1]]
    .map(([al, ac]) => pair(...along(c.axis, al, ac, 0.95))).join(' ');
  return {
    key: `${c.axis}-${c.ac}-${c.at}`,
    body: quad(c.at, c.at + LEN, c.ac, c.ac + WID),
    trail: quad(Math.min(rear, tail), Math.max(rear, tail), c.ac + 0.3, c.ac + WID - 0.3),
    dx: round((c.axis === 'x' ? K * U : -K * U) * c.dir * SPAN),
    dy: round(0.5 * U * c.dir * SPAN),
    style: { animationDuration: `${c.dur}s`, animationDelay: `${c.delay}s` }
  };
});
/* ── 楼群：全部落在甲板半径内，最高那几栋亮起窗格 ────────────────── */
const towers = [
  { x: -8.6, y: -9.4, w: 3.2, d: 3.0, h: 9.4, hot: true },
  { x: -4.4, y: -10.6, w: 2.6, d: 2.4, h: 5.2 },
  { x: -4.6, y: -6.4, w: 3.4, d: 3.4, h: 12.2, hot: true },
  { x: -0.8, y: -10.8, w: 2.4, d: 2.2, h: 3.6 },
  { x: -0.6, y: -6.6, w: 3.0, d: 3.2, h: 7.6 },
  { x: -11.2, y: -6.0, w: 2.8, d: 3.4, h: 4.8 },
  { x: 3.4, y: -9.8, w: 2.8, d: 2.6, h: 5.0 },
  { x: 3.8, y: -5.6, w: 3.2, d: 3.0, h: 8.4, hot: true },
  { x: 8.0, y: -8.2, w: 2.6, d: 2.8, h: 4.0 },
  { x: 8.6, y: -3.6, w: 3.0, d: 2.6, h: 6.2 },
  { x: -3.4, y: -2.6, w: 2.6, d: 2.4, h: 3.0 },
  { x: 3.6, y: -1.6, w: 2.6, d: 2.6, h: 3.6 },
  { x: -9.0, y: -1.4, w: 2.4, d: 2.2, h: 2.6 }
];
const towerViews = towers.map((t, i) => ({
  key: `${t.x}-${t.y}`,
  faces: box(t.x, t.y, t.w, t.d, t.h),
  floors: floors(t),
  hot: !!t.hot,
  wins: t.hot
    ? [
        { points: win(t, 'right', 0.14, 0.4, 0.38, 0.62), delay: round(i * 0.5) },
        { points: win(t, 'right', 0.58, 0.86, 0.66, 0.9), delay: round(i * 0.5 + 1.3) },
        { points: win(t, 'left', 0.2, 0.46, 0.46, 0.7), delay: round(i * 0.5 + 0.7) },
        { points: win(t, 'left', 0.62, 0.88, 0.2, 0.44), delay: round(i * 0.5 + 2.1) }
      ]
    : []
}));

/* ── 地面：沙盘悬空，下方投出一圈光环与水平光带 ──────────────────── */
const floorY = -16;
const floor = ringAt(0, 1.6, floorY, 13);
const floorRings = [7.4, 11, 15].map((r) => ringAt(0, 1.6, floorY, r));
const floorStreak = (axis, dir) => {
  const far = 15 * dir;
  return (axis === 'x'
    ? [along('x', -far, -1.1, floorY + 0.1), along('x', far, -1.1, floorY + 0.1), along('x', far, 1.1, floorY + 0.1), along('x', -far, 1.1, floorY + 0.1)]
    : [along('y', -1.1, -far, floorY + 0.1), along('y', 1.1, -far, floorY + 0.1), along('y', 1.1, far, floorY + 0.1), along('y', -1.1, far, floorY + 0.1)]
  ).map(([x, y]) => pair(x, y)).join(' ');
};

/* ── 悬浮看板：屏幕空间画，只做轻微斜切，文字保持可读 ────────────── */
const panels = [
  { key: 'skills', x: -11.2, y: -11.8, z: 7.2, w: 182, h: 104, title: '技能矩阵', sub: 'SKILL MATRIX', bars: [0.36, 0.6, 0.44, 0.78, 0.52, 0.86, 0.64] },
  { key: 'exam', x: 10.4, y: -3.4, z: 6.0, w: 140, h: 84, title: '考核数据', sub: 'EXAM DATA', bars: [0.5, 0.74, 0.42, 0.88, 0.58] }
];
const panelViews = panels.map((p) => {
  const [tx, ty] = ground(p.x, p.y, p.z);
  const step = (p.w - 42) / p.bars.length;
  return {
    key: p.key,
    tx: round(tx),
    ty: round(ty),
    foot: round(ground(p.x, p.y, 0)[1]),
    w: p.w,
    h: p.h,
    title: p.title,
    sub: p.sub,
    bars: p.bars.map((v, i) => ({ x: round(16 + i * step), y: round(-18 - v * 50), w: 11, h: round(v * 50), delay: round(i * 0.22) }))
  };
});

/* ── 背景流光与尘埃：用固定公式生成，每次渲染都一样，方便截图比对 ── */
const streaks = [-288, -206, -128, 156, 232, 306].map((x, i) => ({ x, delay: round(i * 0.9), dur: round(6 + i * 0.7) }));
const dust = Array.from({ length: 16 }, (_, i) => ({
  key: i,
  cx: round(-300 + ((i * 137) % 640)),
  cy: round(240 - ((i * 91) % 520)),
  r: round(1 + ((i * 7) % 3) * 0.6),
  delay: round((i * 53) % 90) / 10,
  dur: round(7 + ((i * 29) % 50) / 10)
}));

/* ── 玻璃箭头：把沙盘和右侧登录卡连起来，参考图里那道大玻璃三角 ──── */
const bridge = [[286, -132], [432, 0], [286, 132], [286, 78], [376, 0], [286, -78]].map(([x, y]) => pair(x, y)).join(' ');
const signal = ground(13.4, 7.4, 0);
const emitter = [0.8, 1.7, 2.3].map((z, i) => ringAt(0, 1.6, z, [3.4, 2.8, 1.9][i]));
/* 停机坪：台面右前方一块圆形平台，补上前景的空档 */
const helipad = [ringAt(11, 2.2, 0.78, 2.5), ringAt(11, 2.2, 0.9, 1.5)];
</script>
<template>
  <div class="login-stage" aria-hidden="true">
<svg class="holo-svg" :viewBox="viewBox" preserveAspectRatio="xMidYMid meet">

      <defs>
        <linearGradient id="hsSlab" x1="0" y1="0" x2="0.55" y2="1">
          <stop offset="0" stop-color="#123a68" stop-opacity=".95" />
          <stop offset="1" stop-color="#04101f" stop-opacity=".98" />
        </linearGradient>
        <linearGradient id="hsWallX" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#0d2b4e" stop-opacity=".96" />
          <stop offset="1" stop-color="#020a14" stop-opacity=".99" />
        </linearGradient>
        <linearGradient id="hsWallY" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#0a2140" stop-opacity=".96" />
          <stop offset="1" stop-color="#01070f" stop-opacity=".99" />
        </linearGradient>
        <linearGradient id="hsTower" x1="0" y1="0" x2="0.3" y2="1">
          <stop offset="0" stop-color="#1d6394" stop-opacity=".92" />
          <stop offset="1" stop-color="#082036" stop-opacity=".97" />
        </linearGradient>
        <linearGradient id="hsBeam" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#7fe9ff" stop-opacity=".5" />
          <stop offset="0.55" stop-color="#3ea8f0" stop-opacity=".18" />
          <stop offset="1" stop-color="#2f7bff" stop-opacity="0" />
        </linearGradient>
        <linearGradient id="hsBeamUp" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#8ff2ff" stop-opacity="0" />
          <stop offset="0.62" stop-color="#5cc8ff" stop-opacity=".24" />
          <stop offset="1" stop-color="#cff6ff" stop-opacity=".46" />
        </linearGradient>
        <radialGradient id="hsFloor" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stop-color="#2ea8ff" stop-opacity=".48" />
          <stop offset="0.55" stop-color="#1d6fd0" stop-opacity=".14" />
          <stop offset="1" stop-color="#0b2c58" stop-opacity="0" />
        </radialGradient>
        <linearGradient id="hsStreak" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#8ff0ff" stop-opacity="0" />
          <stop offset="0.45" stop-color="#59c2ff" stop-opacity=".3" />
          <stop offset="1" stop-color="#59c2ff" stop-opacity="0" />
        </linearGradient>
        <linearGradient id="hsPane" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#bff0ff" stop-opacity=".22" />
          <stop offset="1" stop-color="#3f9bff" stop-opacity=".06" />
        </linearGradient>
        <linearGradient id="hsBridge" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stop-color="#bcd8f2" stop-opacity=".26" />
          <stop offset="0.6" stop-color="#eaf6ff" stop-opacity=".12" />
          <stop offset="1" stop-color="#7fb6e6" stop-opacity=".05" />
        </linearGradient>
        <linearGradient id="hsSheen" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stop-color="#fff" stop-opacity="0" />
          <stop offset="0.5" stop-color="#fff" stop-opacity=".28" />
          <stop offset="1" stop-color="#fff" stop-opacity="0" />
        </linearGradient>
        <filter id="hsSoft" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="8" /></filter>
        <filter id="hsGlow" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="2.6" /></filter>
      </defs>


      <g class="holo-streaks">
        <rect v-for="s in streaks" :key="s.x" class="streak" :x="s.x" y="-360" width="3.5" height="470" :style="{ animationDelay: s.delay + 's', animationDuration: s.dur + 's' }" />
      </g>

      <g class="holo-floor">
        <ellipse class="floor-glow" :cx="floor.cx" :cy="floor.cy" :rx="round(floor.rx * 1.55)" :ry="round(floor.ry * 1.55)" fill="url(#hsFloor)" />
        <ellipse v-for="(f, i) in floorRings" :key="i" class="floor-ring" :cx="f.cx" :cy="f.cy" :rx="f.rx" :ry="f.ry" :style="{ animationDelay: (i * 1.6) + 's' }" />
        <polygon class="floor-streak" :points="floorStreak('x', 1)" />
        <polygon class="floor-streak" :points="floorStreak('x', -1)" />
        <polygon class="floor-streak" :points="floorStreak('y', 1)" />
        <polygon class="floor-streak" :points="floorStreak('y', -1)" />
      </g>

      <polygon class="holo-beam beam-down" :points="beam(3.6, -5.2, 8.8, floorY)" />

      <g class="holo-slab">
        <polygon class="slab-wall wall-y" :points="slab.left" />
        <polygon class="slab-wall wall-x" :points="slab.right" />
        <polyline class="slab-edge" :points="slabEdges" />
        <polyline class="slab-inset" :points="slabInset" />
        <polygon class="slab-top" :points="slab.top" />
        <polygon class="deck-wall wall-y" :points="deck.left" />
        <polygon class="deck-wall wall-x" :points="deck.right" />
        <polygon class="deck-top" :points="deck.top" />
      </g>

      <g class="holo-rings">
        <ellipse class="deck-inset" :cx="deckInset.cx" :cy="deckInset.cy" :rx="deckInset.rx" :ry="deckInset.ry" />
        <ellipse v-for="(r, i) in rings" :key="i" class="ring" :class="i % 2 ? 'ring-alt' : 'ring-main'" :cx="r.cx" :cy="r.cy" :rx="r.rx" :ry="r.ry" :style="{ animationDelay: (i * 1.4) + 's', animationDuration: (9 + i * 1.5) + 's' }" />
        <ellipse class="helipad" :cx="helipad[0].cx" :cy="helipad[0].cy" :rx="helipad[0].rx" :ry="helipad[0].ry" />
        <ellipse class="helipad-inner" :cx="helipad[1].cx" :cy="helipad[1].cy" :rx="helipad[1].rx" :ry="helipad[1].ry" />
      </g>

      <g class="holo-emitter">
        <ellipse class="emitter-base" :cx="emitter[0].cx" :cy="emitter[0].cy" :rx="emitter[0].rx" :ry="emitter[0].ry" />
        <ellipse class="emitter-mid" :cx="emitter[1].cx" :cy="emitter[1].cy" :rx="emitter[1].rx" :ry="emitter[1].ry" />
        <ellipse class="emitter-core" :cx="emitter[2].cx" :cy="emitter[2].cy" :rx="emitter[2].rx" :ry="emitter[2].ry" />
      </g>


      <g class="holo-roads">
        <polygon v-for="r in roadViews" :key="r.key" class="road" :points="r.face" />
        <line v-for="r in roadViews" :key="r.key + '-dash'" class="road-dash" v-bind="r.dash" />
        <g v-for="c in carViews" :key="c.key" class="car" :style="Object.assign({}, c.style, { '--car-dx': c.dx + 'px', '--car-dy': c.dy + 'px' })">
          <polygon class="car-trail" :points="c.trail" />
          <polygon class="car-body" :points="c.body" />
        </g>
      </g>

      <g class="holo-signal" :transform="'translate(' + signal[0] + ' ' + signal[1] + ')'">
        <rect class="signal-pole" x="-1.6" y="-62" width="3.2" height="62" rx="1.6" />
        <rect class="signal-box" x="-9" y="-88" width="18" height="30" rx="5" />
        <circle class="lamp lamp-red" cx="0" cy="-80" r="3.4" />
        <circle class="lamp lamp-amber" cx="0" cy="-73" r="3.4" />
        <circle class="lamp lamp-green" cx="0" cy="-66" r="3.4" />
      </g>

      <g class="holo-towers">
        <g v-for="t in towerViews" :key="t.key" class="tower" :class="{ hot: t.hot }">
          <polygon class="tower-wall wall-x" :points="t.faces.right" />
          <polygon class="tower-wall wall-y" :points="t.faces.left" />
          <template v-for="(f, i) in t.floors" :key="i">
            <line class="tower-floor" v-bind="f.right" />
            <line class="tower-floor" v-bind="f.left" />
          </template>
          <polygon v-for="(wn, i) in t.wins" :key="i" class="tower-win" :points="wn.points" :style="{ animationDelay: wn.delay + 's' }" />
          <polygon class="tower-top" :points="t.faces.top" />
        </g>
      </g>


      <polygon class="holo-beam beam-up" :points="beam(2.2, 2.4, 5.4, 17)" />
      <line class="beam-core" x1="0" :y1="ground(0, 1.6, 17)[1]" x2="0" :y2="ground(0, 1.6, 2.4)[1]" />

      <g class="holo-panels">
        <g v-for="p in panelViews" :key="p.key" class="panel">
          <line class="panel-tether" :x1="p.tx" :y1="p.ty" :x2="p.tx" :y2="p.foot" />
          <g :transform="'translate(' + p.tx + ' ' + p.ty + ') skewY(-6)'">
            <rect class="panel-face" x="0" :y="-p.h" :width="p.w" :height="p.h" rx="6" fill="url(#hsPane)" />
            <rect class="panel-frame" x="0" :y="-p.h" :width="p.w" :height="p.h" rx="6" />
            <line class="panel-head" x1="0" :y1="30 - p.h" :x2="p.w" :y2="30 - p.h" />
            <text class="panel-title" x="14" :y="21 - p.h">{{ p.title }}</text>
            <text class="panel-sub" x="14" :y="44 - p.h">{{ p.sub }}</text>
            <line class="panel-base" x1="14" y1="-16" :x2="p.w - 14" y2="-16" />
            <rect v-for="(b, i) in p.bars" :key="i" class="panel-bar" :x="b.x" :y="b.y" :width="b.w" :height="b.h" :style="{ animationDelay: b.delay + 's' }" />
            <rect class="panel-scan" x="0" :y="-p.h" :width="p.w" height="9" />
          </g>
        </g>
      </g>

      <g class="holo-dust">
        <circle v-for="d in dust" :key="d.key" class="dust" :cx="d.cx" :cy="d.cy" :r="d.r" :style="{ animationDelay: d.delay + 's', animationDuration: d.dur + 's' }" />
      </g>

      <g class="holo-bridge">
        <polygon class="bridge-glass" :points="bridge" />
        <polygon class="bridge-sheen" :points="bridge" />
        <polygon class="bridge-edge" :points="bridge" />
      </g>

    </svg>
  </div>
</template>
