// Render the compilation's text layers (1920x1080 PNG) in headless Chrome: lower thirds and labels with a
// transparent background, the comparison and end cards opaque. Type: JetBrains Mono (Google Fonts), no pixel font.
// Usage: node make_cards.mjs <outdir> <logo.jpg>
import { spawn } from 'node:child_process';
import { writeFileSync, readFileSync, mkdirSync } from 'node:fs';

const [outdir, logo] = process.argv.slice(2);
mkdirSync(outdir, { recursive: true });
const logoURI = 'data:image/jpeg;base64,' + readFileSync(logo).toString('base64');
const CH = '/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta', port = 9342;
const proc = spawn(CH, ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${outdir}/../chrome-cards`, '--hide-scrollbars', 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, id = 0; const pending = new Map();
for (let i = 0; i < 60; i++) { try { const j = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); const pg = j.find((t) => t.type === 'page'); if (pg) { ws = new WebSocket(pg.webSocketDebuggerUrl); break; } } catch {} await sleep(250); }
await new Promise((r) => (ws.onopen = r));
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); } };
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (e) => (await send('Runtime.evaluate', { expression: e, awaitPromise: true, returnByValue: true })).result?.result?.value;
await send('Page.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700;800&display=swap');
:root { --ink: #1d1932; --cream: #fff8ef; --hot: #ff5c7f; --red: #d23a5c; --dim: rgba(255,248,239,.72); }
html, body { margin: 0; width: 1920px; height: 1080px; overflow: hidden; background: transparent; font-family: 'JetBrains Mono', ui-monospace, Menlo, monospace; color: var(--cream); }
.lt { position: absolute; left: 72px; bottom: 84px; max-width: 1240px; padding: 22px 30px 24px; background: rgba(22,18,40,.84);
  border-left: 8px solid var(--red); box-shadow: 0 10px 40px rgba(0,0,0,.35); }
.k { font: 700 22px/1.2 'JetBrains Mono', monospace; letter-spacing: .08em; text-transform: uppercase; color: var(--hot); }
.t { margin-top: 10px; font: 800 44px/1.15 'JetBrains Mono', monospace; letter-spacing: -.02em; text-wrap: balance; }
.s { margin-top: 10px; font: 400 25px/1.35 'JetBrains Mono', monospace; color: var(--dim); }
.url { position: absolute; right: 64px; bottom: 44px; font: 700 22px/1 'JetBrains Mono', monospace; letter-spacing: .04em; color: rgba(255,248,239,.82);
  text-shadow: 0 1px 6px rgba(0,0,0,.7); }
.credit { position: absolute; right: 64px; top: 44px; padding: 10px 16px; background: rgba(22,18,40,.84); font: 700 22px/1 'JetBrains Mono', monospace;
  letter-spacing: .08em; text-transform: uppercase; }
.full { position: absolute; inset: 0; background: var(--ink); }
`;
const lt = (k, t, s = '', extra = '') => `<div class="lt"><div class="k">${k}</div><div class="t">${t}</div>${s ? `<div class="s">${s}</div>` : ''}</div><div class="url">budotsmedia.com/uas</div>${extra}`;

const bars = [['DJI Dock 2', 'Matrice 3D', 28], ['DJI Dock 3', 'Matrice 4D', 35], ['DJI Dock 4', 'Matrice 5TD', 58]];
const compare = `<div class="full" style="padding:110px 140px;box-sizing:border-box">
  <div class="k" style="font-size:26px">Airborne minutes per hour · 20-minute flights</div>
  <div class="t" style="font-size:64px;margin-top:16px;max-width:1500px">Battery swap instead of recharge: Dock 4 keeps the aircraft flying 58 min of every hour</div>
  <div style="margin-top:70px;display:grid;gap:34px">${bars.map(([d, a, v]) => `
    <div style="display:grid;grid-template-columns:420px 1fr;align-items:center;gap:30px">
      <div><div style="font:800 38px/1.1 'JetBrains Mono'">${d}</div><div style="font:400 24px/1.3 'JetBrains Mono';color:var(--dim)">${a}</div></div>
      <div style="display:flex;align-items:center;gap:24px"><div style="height:64px;width:${Math.round(v / 60 * 900)}px;background:${v > 50 ? 'var(--red)' : 'rgba(255,248,239,.38)'}"></div>
        <div style="font:800 46px/1 'JetBrains Mono';white-space:nowrap">${v} min</div></div></div>`).join('')}
  </div>
  <div class="s" style="margin-top:56px;font-size:24px">Our timing model: Dock 2 and Dock 3 recharge the aircraft on the pad between flights; Dock 4 swaps the battery in under 25 s.</div>
</div><div class="url">budotsmedia.com/uas</div>`;

const end = `<div class="full" style="background:var(--cream);color:var(--ink);display:grid;grid-template-columns:520px 1fr;align-items:center;gap:90px;padding:0 150px;box-sizing:border-box">
  <img src="${logoURI}" style="width:520px;height:520px;object-fit:contain;mix-blend-mode:multiply">
  <div>
    <div class="k" style="font-size:26px;color:var(--red)">3D viewer · scroll case study · Dock 3</div>
    <div class="t" style="font-size:92px;margin-top:18px">budotsmedia.com<br>/uas</div>
    <div class="s" style="font-size:30px;margin-top:26px;color:rgba(29,25,50,.72)">Unofficial reconstruction from DJI's published dimensions.<br>DJI launch film footage © DJI.</div>
    <div style="margin-top:44px;font:700 30px/1.3 'JetBrains Mono';letter-spacing:.02em">Aerial Data Ops · Budots Media</div>
  </div></div>`;

const title = `<div style="position:absolute;inset:0;background:linear-gradient(90deg,rgba(22,18,40,.92) 0%,rgba(22,18,40,.75) 48%,rgba(22,18,40,0) 78%)"></div>
  <div style="position:absolute;left:120px;top:50%;transform:translateY(-50%);max-width:1050px">
    <div class="k" style="font-size:26px">Unofficial 3D reconstruction</div>
    <div class="t" style="font-size:96px;line-height:1.02;margin-top:20px">DJI Dock 4<br>+ Matrice 5TD</div>
    <div class="s" style="font-size:32px;margin-top:28px">The 25-second battery swap and one flight, rebuilt in Blender and three.js from DJI's published dimensions</div>
  </div><div class="url">budotsmedia.com/uas</div>`;

const CARDS = {
  title,
  dji: lt('Source: DJI launch film (CG)', "DJI's X-ray view of the Dock 4 battery swap", '', '<div class="credit">Video: DJI</div>'),
  x0: lt('Our reconstruction · rear X-ray · Blender · 2× speed', 'Cover closes; the aircraft stays on the pad', 'Push blocks centre it over the wireless charging coil'),
  x1: lt('Step 1 of 3 · our reconstruction · 2× speed', 'A hook on a lead screw pulls the battery out of the tail', 'The cradle turns up behind the aircraft · swap time 0–6.5 s'),
  x2: lt('Step 2 of 3 · our reconstruction · 2× speed', 'The rotor turns and stores it in a free compartment', 'One of two charging channels starts on it · 6.5–11 s'),
  x3: lt('Step 3 of 3 · our reconstruction · 2× speed', 'The rotor fetches a charged battery and inserts it', 'Rotor back at 12 o\'clock · swap complete at 25 s'),
  lift: lt('Case study · scroll-driven 3D page', 'Cover opens; the Matrice 5TD climbs to 12 m'),
  orbit: lt('Case study · scroll-driven 3D page', 'Camera orbit around the airframe and its sensors'),
  lidar: lt('Case study · simulated data', 'Rotating LiDAR scan: 32 beams, points coloured by height'),
  rtk: lt('Case study · simulated data', 'RTK corrections from the ground station fix the position'),
  land: lt('Case study · scroll-driven 3D page', 'Landing; the cover closes for the battery swap'),
  compare, end,
};
for (const [name, body] of Object.entries(CARDS)) {
  const html = `<!doctype html><html><head><meta charset="utf-8"><style>${CSS}</style></head><body>${body}</body></html>`;
  await send('Page.navigate', { url: 'data:text/html;base64,' + Buffer.from(html).toString('base64') });
  await sleep(300); await ev('document.fonts.ready.then(() => document.fonts.size)'); await sleep(200);
  const transparent = !['compare', 'end'].includes(name);
  await send('Emulation.setDefaultBackgroundColorOverride', transparent ? { color: { r: 0, g: 0, b: 0, a: 0 } } : {});
  const r = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(`${outdir}/${name}.png`, Buffer.from(r.result.data, 'base64'));
  console.log(name, await ev("document.fonts.check('800 40px \"JetBrains Mono\"')"));
}
ws.close(); proc.kill();
