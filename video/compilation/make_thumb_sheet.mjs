// Labelled 3x3 board of thumbnail candidates (results/thumbs/*.jpg + labels.txt) rendered in headless Chrome.
// Usage: node make_thumb_sheet.mjs <thumbs dir> <out.jpg>
import { spawn } from 'node:child_process';
import { writeFileSync, readFileSync } from 'node:fs';
const [dir, out] = process.argv.slice(2);
const rows = readFileSync(`${dir}/labels.txt`, 'utf8').trim().split('\n').map((l) => l.split('\t'));
const CH = '/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta', port = 9343;
const proc = spawn(CH, ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${dir}/../../work/chrome-sheet`, '--hide-scrollbars', '--allow-file-access-from-files', 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, id = 0; const pending = new Map();
for (let i = 0; i < 60; i++) { try { const j = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); const pg = j.find((t) => t.type === 'page'); if (pg) { ws = new WebSocket(pg.webSocketDebuggerUrl); break; } } catch {} await sleep(250); }
await new Promise((r) => (ws.onopen = r));
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); } };
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const W = 1920, H = 1240;
await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
const tiles = rows.map(([n, t, l]) => `<figure><img src="file://${dir}/${n}_${t}.jpg"><figcaption><b>${n.replace('t', '#')}</b> ${t} · ${l}</figcaption></figure>`).join('');
const html = `<!doctype html><meta charset="utf-8"><style>
body{margin:0;background:#16122a;color:#fff8ef;font:600 22px/1.2 Menlo,monospace;padding:20px;box-sizing:border-box;width:${W}px}
.g{display:grid;grid-template-columns:repeat(3,1fr);gap:16px} figure{margin:0} img{width:100%;display:block}
figcaption{padding:8px 2px 4px} b{color:#ff5c7f}</style><div class="g">${tiles}</div>`;
writeFileSync(`${dir}/sheet.html`, html);
await send('Page.navigate', { url: `file://${dir}/sheet.html` }); await sleep(1500);
const r = await send('Page.captureScreenshot', { format: 'jpeg', quality: 88 });
writeFileSync(out, Buffer.from(r.result.data, 'base64')); ws.close(); proc.kill(); console.log(out);
