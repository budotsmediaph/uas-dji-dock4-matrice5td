// Record the Dock 4 case study (scroll-driven three.js page) frame by frame at an exact 30 fps.
// requestAnimationFrame and performance.now are replaced by a virtual clock, so time-based motion
// (RTK waves, easing) plays at real speed whatever the capture time per frame. Page chrome is hidden;
// only the 3D stage is captured.
// Usage: node rec_case_study.mjs <url> <outdir> <W> <H> "name:ch0:u0:ch1:u1:secs[:preroll],..."
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';

const [url, outdir, W = '1920', H = '1080', plan = 'lift:1:0:2:1:7'] = process.argv.slice(2);
const CH = '/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta', port = 9341;
const prof = `${outdir}/../chrome-profile`;
const proc = spawn(CH, ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, '--use-angle=metal', '--enable-gpu',
  '--hide-scrollbars', '--mute-audio', 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, id = 0; const pending = new Map();
for (let i = 0; i < 60; i++) { try { const j = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); const pg = j.find((t) => t.type === 'page'); if (pg) { ws = new WebSocket(pg.webSocketDebuggerUrl); break; } } catch {} await sleep(250); }
await new Promise((r) => (ws.onopen = r));
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); }
  if (d.method === 'Runtime.exceptionThrown') console.log('EXC', d.params.exceptionDetails.exception?.description?.slice(0, 300)); };
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (e) => (await send('Runtime.evaluate', { expression: e, awaitPromise: true, returnByValue: true })).result?.result?.value;

const SHIM = `(() => {
  let vt = 0, nid = 1; const cbs = new Map();
  performance.now = () => vt;
  window.requestAnimationFrame = (cb) => { const i = nid++; cbs.set(i, cb); return i; };
  window.cancelAnimationFrame = (i) => { cbs.delete(i); };
  window.__step = (ms) => { vt += ms; const list = [...cbs.values()]; cbs.clear(); for (const cb of list) { try { cb(vt); } catch (e) { console.error(e); } } return vt; };
  addEventListener('DOMContentLoaded', () => { const s = document.createElement('style');
    s.textContent = 'body *:not(#gl){visibility:hidden!important} #gl{visibility:visible!important}'; document.head.appendChild(s); });
})();`;
await send('Page.enable'); await send('Runtime.enable');
await send('Page.addScriptToEvaluateOnNewDocument', { source: SHIM });
await send('Emulation.setDeviceMetricsOverride', { width: +W, height: +H, deviceScaleFactor: 1, mobile: false });
await send('Page.navigate', { url });
for (let i = 0; i < 240; i++) { await ev('window.__step && window.__step(16.667)'); if (await ev("document.querySelector('#loading') && document.querySelector('#loading').hidden")) break; await sleep(250); }
for (let i = 0; i < 60; i++) await ev('window.__step(16.667)');
console.log('loaded; docH', await ev('document.documentElement.scrollHeight'));

const yAt = (c, u) => ev(`(() => { const el = document.querySelector('.ch[data-ch="${c}"]'); const vh = innerHeight; const top = el.offsetTop, h = el.offsetHeight;
  const a = top - vh * 0.25, b = Math.max(a + 1, top + h - vh * 0.9); return a + (b - a) * ${+u}; })()`);
const FPS = 30, DT = 1000 / FPS;
for (const seg of plan.split(',')) {
  const [name, c0, u0, c1, u1, secs, pre = '2'] = seg.split(':');
  const y0 = await yAt(c0, u0), y1 = await yAt(c1, u1), n = Math.round(+secs * FPS);
  mkdirSync(`${outdir}/${name}`, { recursive: true });
  await ev(`window.scrollTo(0, ${y0})`);
  for (let i = 0; i < +pre * FPS; i++) await ev(`window.__step(${DT})`);   // let the eased camera settle
  const t0 = Date.now();
  for (let f = 0; f < n; f++) {
    const k = n > 1 ? f / (n - 1) : 0, e = k * k * (3 - 2 * k) * 0.35 + k * 0.65;   // mostly linear, soft start and end
    await ev(`window.scrollTo(0, ${y0 + (y1 - y0) * e}); window.__step(${DT})`);
    const r = await send('Page.captureScreenshot', { format: 'jpeg', quality: 93 });
    writeFileSync(`${outdir}/${name}/f${String(f).padStart(4, '0')}.jpg`, Buffer.from(r.result.data, 'base64'));
  }
  console.log(name, `${n} frames, y ${Math.round(y0)}→${Math.round(y1)}, ${((Date.now() - t0) / n).toFixed(0)} ms/frame`);
}
ws.close(); proc.kill();
