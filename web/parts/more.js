(() => {
  const $ = (s) => document.querySelector(s);
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const reducedM = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const NS = 'http://www.w3.org/2000/svg';
  const svgEl = (tag, attrs, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
  const hhmm = (m) => `${String(Math.floor(m / 60) % 24).padStart(2, '0')}:${String(Math.floor(m) % 60).padStart(2, '0')}`;
  const fmt1 = (x) => (Math.round(x * 10) / 10).toFixed(1);

  // ==================================================================== duty model (section 02, also used in 01)
  // Battery use at the hover rate inside each dock's charge window; Dock 2/3 recharge in the aircraft at DJI's
  // published rate plus 20 s for landing and the cover; Dock 4 spends 45 s and recharges used packs on 2 channels.
  const GEN = {
    d2: { name: 'Dock 2', ac: 'Matrice 3D', hover: 40, window: 70, perPct: 32 / 70, swap: false, color: '--g2' },
    d3: { name: 'Dock 3', ac: 'Matrice 4D', hover: 47, window: 80, perPct: 27 / 80, swap: false, color: '--g3' },
    d4: { name: 'Dock 4', ac: 'Matrice 5TD', hover: 55, window: 80, perPct: 27 / 80, swap: true, color: '--g4' },
  };
  const OVER = 20 / 60, TURN = 45 / 60;
  function cycle(g, T) {
    const E = T * 100 / g.hover;
    if (E > g.window + 1e-9) return null;
    const ground = g.swap ? Math.max(TURN, E * g.perPct / 2 - T) : OVER + E * g.perPct;
    return { E, ground, perHour: 60 * T / (T + ground), per8: Math.floor(480 / (T + ground)) };
  }

  // ==================================================================== 01 scenarios
  const SCEN = [
    { tag: 'Public safety', title: 'Drone as first responder', T: 12,
      text: 'Launches on a dispatch call and flies to the scene at up to 21 m/s, inside a 10 km radius. The feed reaches FlightHub 2 with about 160 ms of latency. A second call minutes later gets a full battery instead of a partly recharged one.',
      list: ['17 object classes detected on board', 'Speaker, spotlight or parachute, up to 450 g', 'Laser rangefinder to 3 km with target coordinates'] },
    { tag: 'Energy', title: 'Power line and substation inspection', T: 35,
      text: 'The 11× tele camera (252 mm equivalent) shows pin-level defects from 100 m. Rotating LiDAR and mmWave radar detect thin wires, also at night. The O4 Ground Station can be placed for a clear link past substation walls.',
      list: ['Consecutive spans flown back to back', 'Thermal 1280 × 1024 for hot joints', 'Wire-level obstacle sensing'] },
    { tag: 'Security', title: 'Overnight patrol', T: 22,
      text: 'Scheduled perimeter flights with 4K colour night vision, an NIR auxiliary light and the thermal camera. The aircraft carries a configurable warning light. Patrols follow each other with a 45 s stop instead of a recharge.',
      list: ['Dock and aircraft rated −40 to 50 °C', 'AI alerts by SMS, email or platform notice', 'Visible and thermal feeds fused'] },
    { tag: 'Survey', title: 'Mapping and progress surveys', T: 38,
      text: 'A large site is split into sequential flights. Each landing costs under 45 s, so the whole area is covered in one session, under the same light, without waiting for a recharge between blocks.',
      list: ['59 min max flight, 55 min hover', 'DJI quotes survey accuracy to 10 cm', 'Flights resume from the last block'] },
    { tag: 'Rescue', title: 'Search, rescue and wildfire watch', T: 36,
      text: 'Thermal search at up to 2560 × 2048 in UHR mode, with the laser rangefinder putting coordinates on the target. Watch over a fire line continues with short gaps while the four batteries rotate.',
      list: ['32× zoom on the thermal feed at night', 'PinPoint coordinates on the live view', 'Wind-exceed descend-and-return'] },
    { tag: 'Remote sites', title: 'Cold, hot and off-grid locations', T: 25,
      text: 'The dock preheats batteries in freezing weather and cools the cabin in heat. If the grid fails, a flight battery in a compartment powers the dock. Three stored packs keep flights going between site visits.',
      list: ['−40 °C limit, 10 °C below Dock 3', 'IP56 dock, IP55 aircraft', 'Backup power from the battery pool'] },
  ];
  const scenEl = $('#scen');
  for (const s of SCEN) {
    const a = document.createElement('article');
    const d3 = cycle(GEN.d3, s.T), d4 = cycle(GEN.d4, s.T);
    const bar = (g, c) => `<div class="row2"><span>${g.name}</span><span class="bar2"><i style="width:${c ? (c.perHour / 60) * 100 : 0}%;background:var(${g.color})"></i></span><b>${c ? Math.round(c.perHour) + ' min' : 'n/a'}</b></div>`;
    a.innerHTML = `<span class="tag2"></span><h3></h3><p></p><div><ul></ul>
      <div class="duty" style="margin-top:12px"><div class="cap2"><span>Airborne per hour</span><span>${s.T} min flights</span></div>${bar(GEN.d3, d3)}${bar(GEN.d4, d4)}
      ${d3 ? '' : '<div class="cap2"><span>Dock 3: a ' + s.T + ' min flight exceeds one charge window</span></div>'}</div></div>`;
    a.querySelector('.tag2').textContent = s.tag;
    a.querySelector('h3').textContent = s.title;
    a.querySelector('p').textContent = s.text;
    const ul = a.querySelector('ul');
    for (const li of s.list) { const e = document.createElement('li'); e.textContent = li; ul.appendChild(e); }
    scenEl.appendChild(a);
  }

  // ==================================================================== 02 one hour at the dock
  // Back-to-back flights of T minutes. Each strip is a 60-minute window of that long day, placed so that its flying
  // time equals the day's average (cycle().perHour), so the numbers match section 01 and the notes below.
  const slider = $('#flightLen'), rowsEl = $('#hrows');
  const TOP = { d2: 90, d3: 95, d4: 95 };          // charge at take-off: top of each dock's charge window
  const SPAN = 60;
  function hourPlan(key, g, T) {
    const c = cycle(g, T);
    if (!c) return null;
    const C = T + c.ground, top = TOP[key];
    const airIn = (phi) => {
      let a = 0;
      for (let k = Math.floor(phi / C); k * C < phi + SPAN; k++) a += Math.max(0, Math.min(k * C + T, phi + SPAN) - Math.max(k * C, phi));
      return a;
    };
    let phi0 = 0, best = Infinity;
    for (let i = 0; i < 600; i++) { const phi = (C * i) / 600, d = Math.abs(airIn(phi) - c.perHour); if (d < best - 1e-9) { best = d; phi0 = phi; } }
    const segs = [], pts = [];
    for (let k = Math.floor(phi0 / C); k * C < phi0 + SPAN; k++) {
      const s0 = k * C - phi0, s1 = s0 + T, s2 = s0 + C, low = top - c.E;
      segs.push({ kind: 'fly', a: s0, b: s1, n: g.swap ? (k % 4) + 1 : 1 }, { kind: g.swap ? 'swp' : 'chg', a: s1, b: s2 });
      pts.push({ x: s0, y: top }, { x: s1, y: low });
      if (g.swap) { const m = s1 + c.ground / 2; pts.push({ x: m, y: low }, { x: m, y: top }); }
      else pts.push({ x: s1 + OVER, y: low });
      pts.push({ x: s2, y: top });
    }
    const at = (x) => { for (let i = 0; i < pts.length - 1; i++) { const p = pts[i], q = pts[i + 1]; if (x >= p.x && x <= q.x && q.x > p.x) return p.y + ((q.y - p.y) * (x - p.x)) / (q.x - p.x); } return top; };
    const line = [{ x: 0, y: at(0) }, ...pts.filter((p) => p.x > 0 && p.x < SPAN), { x: SPAN, y: at(SPAN) }];
    const clipped = segs.map((q) => ({ ...q, a: Math.max(0, q.a), b: Math.min(SPAN, q.b) })).filter((q) => q.b - q.a > 1e-6);
    return { c, segs: clipped, line, air: airIn(phi0) };
  }
  function drawHour() {
    const T = parseInt(slider.value, 10);
    $('#flightOut').textContent = `${T} min`;
    rowsEl.textContent = '';
    for (const [key, g] of Object.entries(GEN)) {
      const plan = hourPlan(key, g, T);
      const row = document.createElement('div');
      row.className = 'hrow' + (g.swap ? ' is4' : '');
      row.innerHTML = '<div class="hname"><b></b><small></small></div><div class="hviz"><div class="htrack"></div></div><div class="hstat"></div>';
      row.querySelector('b').textContent = g.name;
      row.querySelector('small').textContent = `${g.ac} · ${g.swap ? '4 batteries' : '1 battery'}`;
      const track = row.querySelector('.htrack'), stat = row.querySelector('.hstat');
      if (!plan) {
        const max = Math.floor((g.window * g.hover) / 100);
        track.classList.add('none');
        track.textContent = `A ${T} min flight needs more than the ${g.window} % this dock charges between flights. Longest flight: ${max} min.`;
        stat.innerHTML = '<b>–</b><span>not possible<br>at this length</span>';
        row.setAttribute('aria-label', `${g.name}: a ${T} minute flight is not possible; longest ${max} minutes.`);
      } else {
        for (const q of plan.segs) {
          const w = q.b - q.a, frac = w / SPAN, el = document.createElement('div');
          el.className = `hseg ${q.kind}`;
          el.style.left = `${(q.a / SPAN) * 100}%`; el.style.width = `${frac * 100}%`;
          let label = '';
          if (q.kind === 'fly') label = frac > 0.24 ? `flying · battery ${q.n}` : frac > 0.08 ? `B${q.n}` : '';
          else if (q.kind === 'chg') label = frac > 0.26 ? `charging ${Math.round(w)} min` : frac > 0.09 ? `${Math.round(w)} min` : '';
          if (label) { const sp = document.createElement('span'); sp.textContent = label; el.appendChild(sp); }
          track.appendChild(el);
        }
        const bat = svgEl('svg', { class: 'hbat', viewBox: '0 0 600 100', preserveAspectRatio: 'none', 'aria-hidden': 'true' });
        const d = plan.line.map((p, i) => `${i ? 'L' : 'M'}${(p.x * 10).toFixed(2)} ${(100 - p.y).toFixed(2)}`).join('');
        svgEl('path', { d: `${d}L600 100L0 100Z`, class: 'fill' }, bat);
        svgEl('path', { d, class: 'line', 'vector-effect': 'non-scaling-stroke' }, bat);
        row.querySelector('.hviz').appendChild(bat);
        const air = Math.round(plan.air), ground = SPAN - air;
        stat.innerHTML = `<b>${air}</b><span>min flying<br>${ground} min ${g.swap ? 'landing and swapping' : 'charging on the pad'}</span>`;
        row.setAttribute('aria-label', `${g.name}: ${air} minutes flying and ${ground} minutes ${g.swap ? 'landing and swapping batteries' : 'charging'} in one hour of ${T} minute flights.`);
      }
      rowsEl.appendChild(row);
    }
  }
  const axis = $('#haxis');
  for (const m of [0, 10, 20, 30, 40, 50, 60]) {
    const sp = document.createElement('span');
    sp.style.left = `${(m / SPAN) * 100}%`;
    sp.textContent = m === 60 ? '60 min' : String(m);
    axis.appendChild(sp);
  }
  slider.addEventListener('input', drawHour);
  drawHour();
  const c3 = cycle(GEN.d3, 20), c4 = cycle(GEN.d4, 20);
  const notes = [
    ['Turnaround.', `A 27 min recharge becomes a 25 s swap. With 20 min flights the model puts the aircraft in the air ${Math.round(c4.perHour)} of every 60 minutes, against ${Math.round(c3.perHour)} with Dock 3.`],
    ['Temperature.', 'Dock and aircraft are rated down to −40 °C: 10 °C colder than Dock 3 and 20 °C colder than the Matrice 4D. DJI preheats the stored batteries in freezing weather.'],
    ['Sensing.', 'Rotating LiDAR and three mmWave radars join the vision cameras, so thin wires and obstacles are detected at night, where vision sensors need light.'],
    ['Thermal.', 'A native 1280 × 1024 thermal sensor has four times the pixels of the 640 × 512 sensors on the Matrice 3TD and 4TD.'],
    ['Size and mass.', 'Dock 4 is 11 kg heavier and 66 mm taller than Dock 3, but 105 mm narrower, because the RTK base moved to the separate O4 Ground Station.'],
    ['Link.', 'DJI quotes 160 ms from aircraft to the FlightHub 2 cloud, 32 % lower than the previous generation.'],
  ];
  const gn = $('#genNotes');
  for (const [b, t] of notes) { const p = document.createElement('p'); p.style.margin = '0'; p.innerHTML = '<b></b> '; p.querySelector('b').textContent = b; p.append(t); gn.appendChild(p); }
  gn.style.gridTemplateColumns = 'repeat(auto-fit, minmax(260px, 1fr))';
  gn.style.columnGap = '28px';

  // ==================================================================== 03 sample day simulation
  function mulberry32(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  const rnd = mulberry32(20261016);
  const N = 1440, LIMIT = 12;
  const wx = { wind: new Float32Array(N), gust: new Float32Array(N), rain: new Float32Array(N), amb: new Float32Array(N), cab: new Float32Array(N) };
  let w = 3.2, nT = 0;
  for (let m = 0; m < N; m++) {
    const target = 3.0 + 1.6 * Math.sin(2 * Math.PI * (m - 600) / 1440) + 10.4 * Math.exp(-(((m - 872) / 42) ** 2));
    w += (target - w) * 0.06 + (rnd() - 0.5) * 0.35;
    wx.wind[m] = Math.max(0.2, w);
    wx.gust[m] = wx.wind[m] * (1.28 + 0.2 * rnd());
    const r = 6.5 * Math.exp(-(((m - 858) / 26) ** 2)) + (m > 300 && m < 365 ? 0.7 + 0.3 * Math.sin(m / 7) : 0);
    wx.rain[m] = r > 0.15 ? r : 0;
    nT += ((rnd() - 0.5) * 0.4 - nT * 0.05);
    wx.amb[m] = 8.5 + 7 * Math.sin(2 * Math.PI * (m - 540) / 1440) - 3.2 * Math.exp(-(((m - 880) / 60) ** 2)) + nT;
    wx.cab[m] = 20 + 0.16 * (wx.amb[m] - 12) + 0.6 * Math.sin(m / 37);
  }
  const TYPES = { patrol: { label: 'Patrol', color: '--t-patrol' }, dispatch: { label: 'Dispatch', color: '--t-dispatch' }, inspect: { label: 'Inspection', color: '--t-inspect' } };
  const REQ = [
    [30, 'patrol', 22, 'Scheduled perimeter patrol'], [150, 'patrol', 22, 'Scheduled perimeter patrol'], [270, 'patrol', 22, 'Scheduled perimeter patrol'],
    [472, 'dispatch', 11, 'Gate alarm, north gate'], [554, 'dispatch', 9, 'Vehicle report, access road'], [600, 'inspect', 38, 'Roof and solar array survey'],
    [727, 'dispatch', 14, 'Smoke report, storage area'], [868, 'dispatch', 12, 'Fence alarm, east side'], [990, 'inspect', 30, 'Perimeter fence inspection'],
    [1125, 'dispatch', 10, 'Person reported in the yard'], [1142, 'dispatch', 13, 'Second report, same area'], [1230, 'patrol', 22, 'Scheduled perimeter patrol'],
    [1270, 'dispatch', 8, 'Alarm test with the control room'], [1350, 'patrol', 22, 'Scheduled perimeter patrol'],
  ].map(([t, type, dur, label]) => ({ t, type, dur, label }));
  const RATE = 100 / 55 * 1.15;          // % per minute in forward flight (hover rate + 15 %)
  const CHG = 80 / 27;                   // % per minute per channel (15 -> 95 % in 27 min)
  const IDS = ['B1', 'B2', 'B3', 'B4'];
  const lvl = { B1: 95, B2: 95, B3: 95, B4: 95 };
  const comp = { A: 'B2', B: 'B3', C: null, D: 'B4' };
  let acBatt = 'B1', acState = 'pad', airUntil = -1, busyUntil = -1, current = null;
  const trace = { level: {}, where: {}, state: new Array(N), charging: new Array(N) };
  IDS.forEach((b) => { trace.level[b] = new Float32Array(N); trace.where[b] = new Array(N); });
  const flights = [], queue = REQ.slice();
  let swaps = 0;
  for (let m = 0; m < N; m++) {
    if (acState === 'air' && m >= airUntil) {                   // landing
      current.land = m; current.lvlOut = lvl[acBatt];
      const best = Object.entries(comp).filter(([, b]) => b && lvl[b] >= 90).sort((a, b) => lvl[b[1]] - lvl[a[1]])[0];
      const free = Object.keys(comp).find((k) => !comp[k]);
      if (lvl[acBatt] < 90 && best && free) {
        const old = acBatt;
        comp[free] = old; acBatt = best[1]; comp[best[0]] = null;
        const st = 23.6 + rnd() * 1.3;
        current.after = `Swap ${fmt1(st)} s: ${old} → ${free}, ${acBatt} in`;
        current.turn = Math.round(st + 15 + rnd() * 4);
        swaps++;
        acState = 'swap'; busyUntil = m + 1;
      } else { current.after = lvl[acBatt] >= 90 ? 'No swap, above 90 %' : 'No swap, no stored pack above 90 %'; acState = 'pad'; busyUntil = m + 1; }
      flights.push(current); current = null;
    }
    if (acState === 'swap' && m >= busyUntil) acState = 'pad';
    if (acState === 'pad' && m >= busyUntil && queue.length && queue[0].t <= m) {
      const q = queue[0];
      const need = q.dur * RATE + 15;
      if (wx.wind[m] > LIMIT) { q.held = q.held || { from: m, peak: 0 }; q.held.peak = Math.max(q.held.peak, wx.wind[m]); acState = 'pad'; }
      else if (lvl[acBatt] < need) {                               // pre-flight swap if a stored pack can cover the task
        const best = Object.entries(comp).filter(([, b]) => b && lvl[b] >= need).sort((a, b) => lvl[b[1]] - lvl[a[1]])[0];
        const free = Object.keys(comp).find((k) => !comp[k]);
        if (best && free) { comp[free] = acBatt; acBatt = best[1]; comp[best[0]] = null; swaps++; acState = 'swap'; busyUntil = m + 1; q.preSwap = true; }
      }
      else {
        queue.shift();
        current = { ...q, launch: m, batt: acBatt, lvlIn: lvl[acBatt] };
        const wait = m - q.t;
        current.note = q.held ? `Held ${m - q.held.from} min: wind up to ${fmt1(q.held.peak)} m/s (limit 12)` : wait > 0 ? `Queued ${wait} min${q.preSwap ? ' for a pre-flight swap' : ' behind the previous flight'}` : '';
        acState = 'air'; airUntil = m + q.dur;
      }
    }
    trace.state[m] = acState === 'pad' && queue.length && queue[0].t <= m && wx.wind[m] > LIMIT ? 'hold' : acState;
    if (acState === 'air') lvl[acBatt] = Math.max(0, lvl[acBatt] - RATE);
    const charging = Object.values(comp).filter((b) => b && lvl[b] < 95).sort((a, b) => lvl[a] - lvl[b]).slice(0, 2);
    charging.forEach((b) => { lvl[b] = Math.min(95, lvl[b] + CHG); });
    trace.charging[m] = charging;
    for (const b of IDS) {
      trace.level[b][m] = lvl[b];
      trace.where[b][m] = b === acBatt ? 'Aircraft' : Object.keys(comp).find((k) => comp[k] === b);
    }
  }

  // ---------------------------------------------------------------- console chrome
  const simTime = $('#simTime');
  const TABS2 = ['Dock', 'Flights', 'Weather', 'Live'];
  function showScreen(n) {
    for (const k of TABS2) { $('#scr' + k).setAttribute('aria-selected', String(k === n)); $('#pane' + k).hidden = k !== n; }
    live.active = n === 'Live';
    if (live.active) live.kick();
  }
  TABS2.forEach((k) => $('#scr' + k).addEventListener('click', () => showScreen(k)));
  const flightAt = (m) => flights.find((f) => m >= f.launch && m < f.land);
  function setSim(m) {
    m = Math.max(0, Math.min(N - 1, Math.round(m)));
    simTime.value = String(m);
    $('#simClock').textContent = hhmm(m);
    const st = trace.state[m], f = flightAt(m), sw = $('#simState');
    sw.className = 'state' + (st === 'air' ? ' air' : st === 'hold' ? ' hold' : st === 'swap' ? ' swap' : '');
    sw.textContent = st === 'air' ? `Airborne · ${TYPES[f.type].label.toLowerCase()}` : st === 'hold' ? 'Take-off held · wind' : st === 'swap' ? 'Swapping battery' : 'On pad · ready';
    renderDock(m); renderDayCursor(m); renderWx(m); live.minute = m;
  }
  simTime.addEventListener('input', () => setSim(+simTime.value));

  // ---------------------------------------------------------------- dock status
  function renderDock(m) {
    const tiles = $('#tiles');
    tiles.textContent = '';
    const st = trace.state[m];
    const acB = IDS.find((b) => trace.where[b][m] === 'Aircraft');
    const mk = (title, b, extra, cls) => {
      const d = document.createElement('div');
      d.className = 'tile' + (b ? '' : ' empty') + (cls ? ' ' + cls : '');
      const level = b ? trace.level[b][m] : 0;
      const charging = b && trace.charging[m].includes(b);
      d.innerHTML = `<div class="hd"><span></span><span></span></div><div class="big"></div><div class="lvl2"><i></i></div><span class="chip2"></span><div class="meta"></div>`;
      d.querySelector('.hd span').textContent = title;
      d.querySelector('.hd span:last-child').textContent = b || 'empty';
      d.querySelector('.big').innerHTML = b ? `${Math.round(level)}<small> %</small>` : '—';
      d.querySelector('.lvl2 i').style.width = `${b ? level : 0}%`;
      const chip = d.querySelector('.chip2');
      chip.textContent = !b ? 'free for a swap' : charging ? `charging · channel ${trace.charging[m].indexOf(b) + 1}` : extra || (level >= 94.9 ? 'ready' : 'waiting for a channel');
      if (charging) chip.classList.add('charge');
      d.querySelector('.meta').textContent = b ? `${({ B1: 118, B2: 96, B3: 131, B4: 74 })[b]} of 400 cycles` : 'four compartments, three batteries at most';
      tiles.appendChild(d);
    };
    mk('Aircraft', acB, st === 'air' ? 'in flight' : st === 'swap' ? 'swapping' : 'on pad, powered by the coil', 'ac');
    for (const k of ['A', 'B', 'C', 'D']) mk(`Compartment ${k}`, IDS.find((b) => trace.where[b][m] === k), null);
    const kv = $('#dockKv');
    const done = flights.filter((f) => f.launch <= m);
    const items = [['Cover', st === 'air' ? 'Open' : 'Closed'], ['Wind', `${fmt1(wx.wind[m])} m/s`, wx.wind[m] > LIMIT], ['Rain', wx.rain[m] ? `${fmt1(wx.rain[m])} mm/h` : 'none'],
      ['Ambient', `${fmt1(wx.amb[m])} °C`], ['Cabin', `${fmt1(wx.cab[m])} °C`], ['Power', 'Mains'], ['Flights so far', `${done.length}`], ['Swaps so far', `${done.filter((f) => f.land <= m && /^Swap/.test(f.after)).length}`]];
    kv.innerHTML = items.map(([k, v, warn]) => `<div><span class="k">${k}</span><span class="v${warn ? ' warn' : ''}">${v}</span></div>`).join('');
    const next = REQ.find((q) => q.t > m) || null;
    const heldNow = flights.find((f) => f.note && f.note.startsWith('Held') && m >= f.t && m < f.launch);
    $('#nextTask').textContent = heldNow ? `${TYPES[heldNow.type].label} requested ${hhmm(heldNow.t)} is waiting for the wind to drop below 12 m/s`
      : next ? `Next task: ${hhmm(next.t)} · ${TYPES[next.type].label} · ${next.label}` : 'No more tasks in the sample day';
  }
  $('#jumpSwap').addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: reducedM ? 'auto' : 'smooth' });
    window.dock4?.jump?.(270, 'xray');
  });

  // ---------------------------------------------------------------- flight log + day chart
  const day = $('#dayChart'), DW = 900, DH = 250, DL = 52, DR = 22;
  const dx = (m) => DL + m / N * (DW - DL - DR);
  const LANE = [14, 44], LV = [70, 222];
  const dyl = (v) => LV[1] - v / 100 * (LV[1] - LV[0]);
  const shown = { patrol: true, dispatch: true, inspect: true };
  let selFlight = null, dayCursor;
  function holdSpans() {
    const spans = []; let s = null;
    for (let m = 0; m < N; m++) { const h = wx.wind[m] > LIMIT; if (h && s == null) s = m; if (!h && s != null) { spans.push([s, m]); s = null; } }
    return spans;
  }
  const HOLDS = holdSpans();
  function drawDay() {
    day.textContent = '';
    for (const [a, b] of HOLDS) svgEl('rect', { x: dx(a), y: LANE[0] - 4, width: dx(b) - dx(a), height: LV[1] - LANE[0] + 4, fill: 'var(--hold-band)' }, day);
    for (let h = 0; h <= 24; h += 3) {
      svgEl('line', { x1: dx(h * 60), x2: dx(h * 60), y1: LANE[0] - 4, y2: LV[1], stroke: 'var(--screen-rule)' }, day);
      svgEl('text', { x: dx(h * 60), y: DH - 8, 'text-anchor': h === 24 ? 'end' : h === 0 ? 'start' : 'middle' }, day).textContent = `${String(h).padStart(2, '0')}:00`;
    }
    for (const v of [15, 50, 95]) {
      svgEl('line', { x1: DL, x2: DW - DR, y1: dyl(v), y2: dyl(v), stroke: 'var(--screen-rule)', 'stroke-dasharray': v === 50 ? '' : '4 4' }, day);
      svgEl('text', { x: DL - 6, y: dyl(v) + 3.5, 'text-anchor': 'end' }, day).textContent = `${v}%`;
    }
    svgEl('text', { x: DL - 6, y: LANE[0] + 18, 'text-anchor': 'end' }, day).textContent = 'flights';
    for (const f of flights) {
      if (!shown[f.type]) continue;
      const r = svgEl('rect', { x: dx(f.launch), y: LANE[0], width: Math.max(2.5, dx(f.land) - dx(f.launch)), height: LANE[1] - LANE[0], rx: 3,
        fill: `var(${TYPES[f.type].color})`, opacity: selFlight && selFlight !== f ? 0.35 : 1, style: 'cursor:pointer' }, day);
      r.addEventListener('click', () => selectFlight(f, true));
      svgEl('title', {}, r).textContent = `${hhmm(f.launch)} ${TYPES[f.type].label}: ${f.label}`;
    }
    const cols = ['--s1', '--s2', '--s3', '--s4'];
    IDS.forEach((b, i) => {
      let d = '';
      for (let m = 0; m < N; m += 4) d += `${m ? 'L' : 'M'}${dx(m).toFixed(1)} ${dyl(trace.level[b][m]).toFixed(1)}`;
      svgEl('path', { d, fill: 'none', stroke: `var(${cols[i]})`, 'stroke-width': 1.8 }, day);
      svgEl('text', { x: DW - DR - 4 - (3 - i) * 34, y: LV[0] - 8, 'text-anchor': 'end', style: `fill:var(${cols[i]})` }, day).textContent = `■ ${b}`;
    });
    dayCursor = svgEl('line', { x1: 0, x2: 0, y1: LANE[0] - 6, y2: LV[1], stroke: '#e8edf0', 'stroke-width': 1.5 }, day);
    renderDayCursor(+simTime.value);
  }
  function renderDayCursor(m) { if (dayCursor) { dayCursor.setAttribute('x1', dx(m)); dayCursor.setAttribute('x2', dx(m)); } }
  day.addEventListener('click', (e) => {
    if (e.target.tagName === 'rect' && e.target.getAttribute('rx')) return;
    const pt = day.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(day.getScreenCTM().inverse());
    setSim((p.x - DL) / (DW - DL - DR) * N);
  });
  const chipsEl = $('#typeChips');
  for (const [k, t] of Object.entries(TYPES)) {
    const b = document.createElement('button');
    b.type = 'button'; b.setAttribute('aria-pressed', 'true');
    b.innerHTML = `<i style="background:var(${t.color})"></i>${t.label} · ${flights.filter((f) => f.type === k).length}`;
    b.addEventListener('click', () => { shown[k] = !shown[k]; b.setAttribute('aria-pressed', String(shown[k])); drawDay(); renderLog(); });
    chipsEl.appendChild(b);
  }
  const logRows = $('#logRows');
  function renderLog() {
    logRows.textContent = '';
    for (const f of flights) {
      if (!shown[f.type]) continue;
      const tr = document.createElement('tr');
      tr.className = f === selFlight ? 'sel' : '';
      tr.innerHTML = `<td>${hhmm(f.launch)}</td><td><span class="ty"><i style="background:var(${TYPES[f.type].color})"></i>${TYPES[f.type].label}</span></td><td>${f.dur} min</td>
        <td>${f.batt} ${Math.round(f.lvlIn)} → ${Math.round(f.lvlOut)} %</td><td></td><td class="note"></td>`;
      tr.children[4].textContent = f.after + (f.turn ? ` · turnaround ${f.turn} s` : '');
      tr.children[5].textContent = `${f.label}${f.note ? '. ' + f.note : ''}`;
      tr.addEventListener('click', () => selectFlight(f, false));
      logRows.appendChild(tr);
      f.row = tr;
    }
  }
  function selectFlight(f, scroll) {
    selFlight = f;
    setSim(f.launch + Math.min(3, f.dur - 1));
    drawDay(); renderLog();
    if (scroll && f.row) f.row.scrollIntoView({ block: 'nearest' });
  }
  $('#flightSum').textContent = `${flights.length} flights · ${flights.filter((f) => /^Swap/.test(f.after)).length} swaps · ${flights.reduce((a, f) => a + f.dur, 0)} min airborne`;

  // ---------------------------------------------------------------- weather
  const wxs = $('#wxChart'), WW = 900, WH = 300, WL = 40, WR = 40;
  const wxx = (m) => WL + m / N * (WW - WL - WR);
  const P1 = [28, 150], P2 = [196, 272];
  const wy = (v) => P1[1] - v / 20 * (P1[1] - P1[0]);
  const ry = (v) => P1[1] - v / 10 * (P1[1] - P1[0]) * 0.45;
  const ty = (v) => P2[1] - (v + 5) / 35 * (P2[1] - P2[0]);
  let wxCursor;
  function drawWx() {
    wxs.textContent = '';
    for (const [a, b] of HOLDS) svgEl('rect', { x: wxx(a), y: P1[0], width: wxx(b) - wxx(a), height: P1[1] - P1[0], fill: 'var(--hold-band)' }, wxs);
    for (let h = 0; h <= 24; h += 3) {
      svgEl('line', { x1: wxx(h * 60), x2: wxx(h * 60), y1: P1[0], y2: P2[1], stroke: 'var(--screen-rule)' }, wxs);
      svgEl('text', { x: wxx(h * 60), y: WH - 6, 'text-anchor': h === 24 ? 'end' : h === 0 ? 'start' : 'middle' }, wxs).textContent = `${String(h).padStart(2, '0')}:00`;
    }
    for (const v of [0, 5, 10, 15, 20]) svgEl('text', { x: WL - 6, y: wy(v) + 3.5, 'text-anchor': 'end' }, wxs).textContent = v;
    svgEl('text', { x: WL - 6, y: P1[0] - 12, 'text-anchor': 'end' }, wxs).textContent = 'm/s';
    for (const v of [0, 5, 10]) svgEl('text', { x: WW - WR + 6, y: ry(v) + 3.5 }, wxs).textContent = v;
    svgEl('text', { x: WW - WR + 4, y: ry(10) - 12 }, wxs).textContent = 'mm/h';
    for (let m = 0; m < N; m += 6) if (wx.rain[m]) svgEl('rect', { x: wxx(m), y: ry(wx.rain[m]), width: Math.max(1.5, wxx(6) - wxx(0) - 0.5), height: P1[1] - ry(wx.rain[m]), fill: '#3b82c4', opacity: 0.55 }, wxs);
    const line = (arr, f, stroke, wdt, dash) => { let d = ''; for (let m = 0; m < N; m += 4) d += `${m ? 'L' : 'M'}${wxx(m).toFixed(1)} ${f(arr[m]).toFixed(1)}`; svgEl('path', { d, fill: 'none', stroke, 'stroke-width': wdt, 'stroke-dasharray': dash || '' }, wxs); };
    line(wx.gust, wy, '#6fe0ee', 1, '2 3');
    line(wx.wind, wy, '#6fe0ee', 2);
    svgEl('line', { x1: WL, x2: WW - WR, y1: wy(LIMIT), y2: wy(LIMIT), stroke: '#f59a90', 'stroke-dasharray': '6 4' }, wxs);
    svgEl('text', { x: WL + 6, y: wy(LIMIT) - 5, style: 'fill:#f59a90' }, wxs).textContent = '12 m/s: no take-off or landing above this';
    for (const v of [0, 10, 20, 30]) svgEl('text', { x: WL - 6, y: ty(v) + 3.5, 'text-anchor': 'end' }, wxs).textContent = v;
    svgEl('text', { x: WL - 6, y: P2[0] - 12, 'text-anchor': 'end' }, wxs).textContent = '°C';
    line(wx.amb, ty, '#e5b45c', 2);
    line(wx.cab, ty, '#c39ae6', 2);
    svgEl('text', { x: WW - WR - 4, y: P2[0] + 2, 'text-anchor': 'end', style: 'fill:#e5b45c' }, wxs).textContent = '— ambient';
    svgEl('text', { x: WW - WR - 4, y: P2[0] + 16, 'text-anchor': 'end', style: 'fill:#c39ae6' }, wxs).textContent = '— cabin (air conditioned)';
    svgEl('text', { x: WW - WR - 4, y: P1[0] + 12, 'text-anchor': 'end', style: 'fill:#6fe0ee' }, wxs).textContent = '— wind, 10-min mean · gusts dotted';
    wxCursor = svgEl('line', { x1: 0, x2: 0, y1: P1[0], y2: P2[1], stroke: '#e8edf0', 'stroke-width': 1.5 }, wxs);
  }
  wxs.addEventListener('click', (e) => {
    const pt = wxs.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(wxs.getScreenCTM().inverse());
    setSim((p.x - WL) / (WW - WL - WR) * N);
  });
  function renderWx(m) {
    if (wxCursor) { wxCursor.setAttribute('x1', wxx(m)); wxCursor.setAttribute('x2', wxx(m)); }
    const peak = Math.max(...wx.gust.slice(Math.max(0, m - 10), m + 1));
    const held = HOLDS.reduce((a, [s, e]) => a + (e - s), 0);
    $('#wxKv').innerHTML = [['Wind, mean', `${fmt1(wx.wind[m])} m/s`, wx.wind[m] > LIMIT], ['Gust, 10 min', `${fmt1(peak)} m/s`], ['Rain', wx.rain[m] ? `${fmt1(wx.rain[m])} mm/h` : 'none'],
      ['Ambient / cabin', `${fmt1(wx.amb[m])} / ${fmt1(wx.cab[m])} °C`], ['Held today', `${held} min`], ['Wind limit', '12 m/s'], ['Dew risk', wx.amb[m] < 3 ? 'watch lens' : 'low'], ['Heater', wx.amb[m] < 0 ? 'on' : 'off']]
      .map(([k, v, warn]) => `<div><span class="k">${k}</span><span class="v${warn ? ' warn' : ''}">${v}</span></div>`).join('');
  }

  // ---------------------------------------------------------------- live view (procedural scene)
  const cv = $('#liveCanvas'), cx = cv.getContext('2d');
  const WD = 1600, HT = 900;
  const live = { active: false, cam: 'ir', zoom: 1.6, ai: true, minute: 862, raf: 0, last: 0, t0: performance.now() };
  const IRON = [[0, [4, 4, 18]], [0.22, [40, 10, 110]], [0.42, [150, 20, 120]], [0.6, [225, 70, 30]], [0.78, [248, 160, 30]], [1, [255, 252, 220]]];
  const iron = (t) => { t = Math.max(0, Math.min(1, t)); for (let i = 1; i < IRON.length; i++) if (t <= IRON[i][0]) { const [a, ca] = IRON[i - 1], [b, cb] = IRON[i], k = (t - a) / (b - a); return ca.map((v, j) => Math.round(v + (cb[j] - v) * k)); } return IRON[IRON.length - 1][1]; };
  const lr = mulberry32(42);
  const ROAD = [[0, 640], [1600, 360]];
  const BUILD = [[160, 110, 420, 270], [960, 80, 1420, 290], [180, 700, 520, 860]];
  const PARK = [[600, 455, 0.35], [690, 440, 0.3], [780, 425, 0.25]];
  const TRANS = [1180, 560, 70, 46];
  function staticScene(mode) {
    const c = document.createElement('canvas'); c.width = WD; c.height = HT;
    const g = c.getContext('2d');
    const img = g.createImageData(WD, HT);
    const heat = new Float32Array(WD * HT);
    for (let y = 0; y < HT; y++) for (let x = 0; x < WD; x++) heat[y * WD + x] = 0.26 + 0.05 * Math.sin(x / 61 + Math.sin(y / 47)) + 0.04 * Math.sin(y / 23 + x / 90);
    const fill = (bx0, by0, bx1, by1, fn, v) => {                 // only scans the shape's bounding box
      for (let y = Math.max(0, by0 | 0); y < Math.min(HT, by1); y++) for (let x = Math.max(0, bx0 | 0); x < Math.min(WD, bx1); x++)
        if (fn(x, y)) heat[y * WD + x] = typeof v === 'function' ? v(x, y) : v;
    };
    const roadY = (x) => ROAD[0][1] + (ROAD[1][1] - ROAD[0][1]) * x / WD;
    fill(0, 300, WD, 700, (x, y) => Math.abs(y - roadY(x)) < 48, (x) => 0.36 + 0.03 * Math.sin(x / 7));
    for (const [x0, y0, x1, y1] of BUILD) fill(x0, y0, x1, y1, () => true, (x, y) => 0.31 + ((Math.floor(x / 40) + Math.floor(y / 40)) % 2) * 0.015);
    fill(980, 120, 1330, 250, (x, y) => (x - 1010) ** 2 + (y - 150) ** 2 < 400 || (x - 1300) ** 2 + (y - 220) ** 2 < 300, 0.72);
    fill(TRANS[0], TRANS[1], TRANS[0] + TRANS[2], TRANS[1] + TRANS[3], () => true, (x) => 0.78 + 0.08 * Math.sin(x / 5));
    for (const [px, py, v] of PARK) fill(px - 38, py - 18, px + 38, py + 18, () => true, (x) => 0.42 + v * 0.3 * Math.exp(-((x - px - 26) ** 2) / 200));
    fill(70, 0, 130, HT, (x, y) => Math.abs(x - 80 - y * 0.05) < 2, 0.4);
    fill(0, 30, WD, 80, (x, y) => Math.abs(y - 40 - x * 0.02) < 2, 0.4);
    for (let i = 0; i < WD * HT; i++) {
      const v = heat[i] + (lr() - 0.5) * 0.02;
      let r, gg, b;
      if (mode === 'ir') [r, gg, b] = iron(v);
      else { const k = 0.35 + 0.65 * v; r = 22 * k + 10; gg = 30 * k + 14; b = 52 * k + 22; }
      img.data[i * 4] = r; img.data[i * 4 + 1] = gg; img.data[i * 4 + 2] = b; img.data[i * 4 + 3] = 255;
    }
    g.putImageData(img, 0, 0);
    if (mode === 'wide') {
      for (const [lx, ly] of [[300, 600], [800, 500], [1300, 420], [1100, 620]]) {
        const rg = g.createRadialGradient(lx, ly, 0, lx, ly, 170);
        rg.addColorStop(0, 'rgba(255,190,90,0.42)'); rg.addColorStop(1, 'rgba(255,190,90,0)');
        g.fillStyle = rg; g.fillRect(lx - 170, ly - 170, 340, 340);
      }
      g.strokeStyle = 'rgba(200,210,220,0.25)'; g.lineWidth = 2;
      for (const [x0, y0, x1, y1] of BUILD) g.strokeRect(x0, y0, x1 - x0, y1 - y0);
    }
    return c;
  }
  let BG = null;
  function ensureBG() { if (!BG) BG = { ir: staticScene('ir'), wide: staticScene('wide') }; }
  function actors(sec) {
    const u = (sec * 0.035) % 1.2 - 0.1;
    const carX = u * WD, carY = ROAD[0][1] + (ROAD[1][1] - ROAD[0][1]) * carX / WD - 14;
    return [
      { kind: 'Car', x: carX, y: carY, w: 84, h: 38, heat: 0.86, conf: 0.91 },
      { kind: 'Person', x: 1040 + 60 * Math.sin(sec * 0.25), y: 360 + 18 * Math.sin(sec * 0.4), w: 18, h: 30, heat: 0.95, conf: 0.94 },
      { kind: 'Person', x: 1080 + 40 * Math.cos(sec * 0.22), y: 395 + 12 * Math.sin(sec * 0.3), w: 18, h: 30, heat: 0.93, conf: 0.89 },
      { kind: 'Car', x: PARK[0][0], y: PARK[0][1], w: 80, h: 36, heat: 0.0, conf: 0.84, parked: true },
    ];
  }
  function drawLive(now) {
    ensureBG();
    const sec = reducedM ? 30 : (now - live.t0) / 1000;
    const z = live.zoom, W = cv.width, H = cv.height;
    const focus = [1040, 390];
    const s = (W / WD) * z;
    const ox = W / 2 - focus[0] * s, oy = H / 2 - focus[1] * s;
    const tx = (x) => ox + x * s, tyy = (y) => oy + y * s;
    cx.setTransform(1, 0, 0, 1, 0, 0);
    cx.fillStyle = '#000'; cx.fillRect(0, 0, W, H);
    cx.imageSmoothingEnabled = true;
    const base = live.cam === 'ir' ? BG.ir : BG.wide;
    cx.drawImage(base, ox, oy, WD * s, HT * s);
    if (live.cam === 'fuse') { cx.globalAlpha = 0.5; cx.globalCompositeOperation = 'screen'; cx.drawImage(BG.ir, ox, oy, WD * s, HT * s); cx.globalAlpha = 1; cx.globalCompositeOperation = 'source-over'; }
    const acts = actors(sec);
    for (const a of acts) {
      if (a.parked) continue;
      const [r, g, b] = iron(a.heat);
      const col = live.cam === 'wide' ? 'rgba(40,46,58,0.95)' : `rgb(${r},${g},${b})`;
      const grd = cx.createRadialGradient(tx(a.x), tyy(a.y), 0, tx(a.x), tyy(a.y), Math.max(a.w, a.h) * s * 0.75);
      grd.addColorStop(0, col); grd.addColorStop(0.55, col); grd.addColorStop(1, 'rgba(0,0,0,0)');
      cx.fillStyle = grd;
      cx.beginPath(); cx.ellipse(tx(a.x), tyy(a.y), a.w * s * 0.6, a.h * s * 0.6, a.kind === 'Car' ? -0.17 : 0, 0, Math.PI * 2); cx.fill();
      if (live.cam === 'wide' && a.kind === 'Car') { cx.fillStyle = 'rgba(255,240,200,0.9)'; cx.beginPath(); cx.arc(tx(a.x + a.w * 0.5), tyy(a.y - 4), 3 * s, 0, 7); cx.fill(); }
    }
    if (live.ai) {
      cx.lineWidth = 2; cx.font = `600 ${Math.round(15)}px ui-monospace, Menlo, monospace`;
      for (const a of acts) {
        const x0 = tx(a.x - a.w * 0.65), y0 = tyy(a.y - a.h * 0.75), w = a.w * 1.3 * s, h = a.h * 1.5 * s;
        if (x0 > W || y0 > H || x0 + w < 0 || y0 + h < 0) continue;
        cx.strokeStyle = a.kind === 'Person' ? '#ffd166' : '#6fe0ee';
        cx.strokeRect(x0, y0, w, h);
        const label = `${a.kind} ${a.conf.toFixed(2)}`;
        const tw = cx.measureText(label).width + 10;
        cx.fillStyle = cx.strokeStyle; cx.fillRect(x0, y0 - 20, tw, 20);
        cx.fillStyle = '#05080a'; cx.fillText(label, x0 + 5, y0 - 5);
      }
    }
    cx.strokeStyle = 'rgba(255,255,255,0.85)'; cx.lineWidth = 1.5;
    cx.beginPath(); cx.moveTo(W / 2 - 22, H / 2); cx.lineTo(W / 2 - 6, H / 2); cx.moveTo(W / 2 + 6, H / 2); cx.lineTo(W / 2 + 22, H / 2);
    cx.moveTo(W / 2, H / 2 - 22); cx.lineTo(W / 2, H / 2 - 6); cx.moveTo(W / 2, H / 2 + 6); cx.lineTo(W / 2, H / 2 + 22); cx.stroke();
    const m = live.minute, secOfMin = Math.floor(sec % 60);
    $('#osdTL').innerHTML = `${hhmm(m)}:${String(secOfMin).padStart(2, '0')} · sample day<br>${live.cam === 'ir' ? 'Thermal 1280 × 1024 · ironbow' : live.cam === 'wide' ? 'Wide 50 MP · night colour' : 'Fusion · thermal over wide'}`;
    $('#osdTR').innerHTML = `${live.zoom.toFixed(1)}×<br>ALT 118 m · GIMBAL −52°`;
    const dist = 404 + Math.round(6 * Math.sin(sec * 0.3));
    $('#osdBL').innerHTML = `LRF ${dist} m · target ${Math.round(dist * 0.78)} m N, ${Math.round(dist * 0.21)} m W of the dock<br>${live.ai ? `AI: ${acts.length} objects (2 person, 2 car)` : 'AI detection off'}`;
  }
  function loop(now) {
    if (!live.active || !live.visible) { live.raf = 0; return; }
    if (now - live.last > 66) { drawLive(now); live.last = now; }
    live.raf = reducedM ? 0 : requestAnimationFrame(loop);
  }
  live.kick = () => { if (!live.raf && live.active) { drawLive(performance.now()); if (!reducedM) live.raf = requestAnimationFrame(loop); } };
  new IntersectionObserver((es) => { live.visible = es[0].isIntersecting; live.kick(); }).observe(cv);
  document.querySelectorAll('[data-cam]').forEach((b) => b.addEventListener('click', () => {
    live.cam = b.dataset.cam;
    document.querySelectorAll('[data-cam]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    drawLive(performance.now());
  }));
  $('#liveZoom').addEventListener('input', (e) => { live.zoom = +e.target.value; $('#liveZoomOut').textContent = `${live.zoom.toFixed(1)}×`; drawLive(performance.now()); });
  $('#liveAI').addEventListener('change', (e) => { live.ai = e.target.checked; drawLive(performance.now()); });

  drawDay(); renderLog(); drawWx();
  setSim(884);
  const deep = { log: 'Flights', weather: 'Weather', live: 'Live', dock: 'Dock' }[location.hash.slice(1)];
  if (deep) { showScreen(deep); $('#screens').scrollIntoView(); }
  const redraw = () => { drawDuty(); drawDay(); drawWx(); setSim(+simTime.value); };
  new MutationObserver(redraw).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
})();
