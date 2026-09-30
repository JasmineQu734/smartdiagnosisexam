import { readdirSync, readFileSync } from 'node:fs';
const dir = process.argv[2];
const only = process.argv[3] || '';
const top = process.argv[4] ? parseInt(process.argv[4], 10) : 10;
const EMU_PT = 12700;
const w = (t, sz) => { let s = 0; for (const ch of t) s += /[\u2E80-\u9FFF\uFF00-\uFFEF\u3000-\u303F]/.test(ch) ? sz : sz * 0.53; return s; };
let files = readdirSync(dir).filter((f) => /^slide\d+\.xml$/.test(f));
if (only) files = files.filter((f) => f === only);
files.sort((a, b) => parseInt(a.match(/\d+/)[0], 10) - parseInt(b.match(/\d+/)[0], 10));
const rows = [];
for (const f of files) {
  const xml = readFileSync(dir + '/' + f, 'utf8').replace(/<p:graphicFrame>[\s\S]*?<\/p:graphicFrame>/g, '<p:sp></p:sp>');
  for (const sp of xml.split('<p:sp>').slice(1)) {
    const nm = (sp.match(/name="([^"]*)"/) || [])[1] || '?';
    const off = sp.match(/<a:off x="(-?\d+)" y="(-?\d+)"\/>/);
    const ext = sp.match(/<a:ext cx="(\d+)" cy="(\d+)"\/>/);
    if (!off || !ext) continue;
    const cx = +ext[1], cy = +ext[2];
    const ins = sp.match(/<a:bodyPr[^>]*>/);
    const g = (k, d) => { const m = ins && ins[0].match(new RegExp(k + '="(\\d+)"')); return m ? +m[1] : d; };
    const avW = (cx - g('lIns', 91440) - g('rIns', 91440)) / EMU_PT;
    const avH = (cy - g('tIns', 45720) - g('bIns', 45720)) / EMU_PT;
    let h = 0, chars = 0, det = [];
    for (const para of sp.split('<a:p>').slice(1)) {
      const t = [...para.matchAll(/<a:t>([^<]*)<\/a:t>/g)].map((m) => m[1]).join('');
      if (!t) continue;
      chars += t.length;
      const sz = +((para.match(/sz="(\d+)"/) || [])[1] || 1800) / 100;
      const af = +((para.match(/<a:spcAft><a:spcPts val="(\d+)"\/>/) || [])[1] || 0) / 100;
      const marL = +((para.match(/marL="(\d+)"/) || [])[1] || 0) / EMU_PT;
      const lines = Math.max(1, Math.ceil(w(t, sz) / Math.max(10, avW - marL * 0.9)));
      det.push(lines + 'L');
      h += lines * sz * 1.22 + af;
    }
    if (chars < 2) continue;
    rows.push({ f, nm, fill: avH > 3 ? h / avH : 0, h: Math.round(h), avH: Math.round(avH), chars, det: det.join(',') });
  }
}
rows.sort((a, b) => b.fill - a.fill);
for (const r of rows.slice(0, top)) console.log(r.f.padEnd(14) + r.nm.padEnd(15) + ' fill=' + r.fill.toFixed(2) + '  ' + r.h + 'pt/' + r.avH + 'pt  chars=' + r.chars + '  ' + r.det);
console.log('shapes: ' + rows.length);