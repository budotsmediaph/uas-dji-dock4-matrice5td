# DJI Dock 4 + Matrice 5TD: battery swap reconstruction

Live: https://budotsmedia.com/uas/dji-dock4-matrice5td/ · repo: https://github.com/budotsmediaph/uas-dji-dock4-matrice5td · local copy `web/index.html` (opens from disk) · Claude artifact https://claude.ai/artifact/87tNcjsAmxhtCHL5FeP7S1

Same pipeline as the Dock 3 rebuild in `../../dock3/20260922-claude-opus5.5/`: a Blender build script, a GLB with one baked animation, and a three.js viewer. This build adds what Dock 4 introduces: the automated battery swap. The 44 s clip runs landing → cover closing → 25.0 s swap → cover opening → take-off. The viewer shows it Solid, X-ray (dock and aircraft translucent, mechanism solid) or Cut-away (a side or rear section plane through the dock, cage and aircraft; batteries and rotor stay whole).

```
20261016-claude-opus5.5/
├── research/               (local only, not in the repo) sources, manuals, videos, key frames, findings
├── official/
│   ├── extract_vertices.py recovers the 95,153 vertex points of DJI's truncated M5TD STEP
│   └── m5td_vertices.npy   (local only) those points (mm, Creo assembly frame)
├── blender/build.py        dock, cover, swap module, batteries, aircraft, animation, validation, export, renders, video
├── dock4.blend             generated scene
├── web/
│   ├── dock4.glb           2.1 MB, one clip "Dock4Swap" 44.0 s
│   ├── dock4_meta.json     spec, validation, timeline (phases, 15 swap steps, battery schedule), callouts, geometry
│   ├── viewer.src.html     three.js 0.186 viewer (first screen)
│   ├── parts/more.*        sections below it: 01 scenarios, 02 Dock 2/3/4 comparison with airborne-time model,
│   │                       03 operator screens with a simulated sample day (dock status, flight log, weather, live view)
│   ├── build_viewer.py     embeds GLB + meta → index.html (standalone), artifact.html, and site/ for budotsmedia.com
├── renders/01–10 *.png     Eevee stills (closed, landing, rear X-ray steps, side cut, cradle detail, plan, bay camera)
├── renders/make_video.py   encodes renders/swap_frames/ with step captions
├── renders/dock4_swap_xray_rear.mp4   rear X-ray of the whole swap, 34 s, 1280 × 720
├── video/compilation/      61 s compilation (budotsmedia.com/uas/#video): case-study recorder, text cards, ffmpeg build
├── site/                   (generated) budotsmedia.com/uas/dji-dock4-matrice5td/: page, dock4.glb, og.jpg, 404
├── wrangler.jsonc          Cloudflare Worker uas-dji-dock4-matrice5td, route budotsmedia.com/uas/dji-dock4-matrice5td*
└── deploy.sh               rebuild site/ and deploy (live at once)
```

## Rebuild

```bash
cd blender && blender -b -P build.py -- --render && python3 ../web/build_viewer.py
blender -b -P build.py -- --video --no-export && python3 ../renders/make_video.py     # ~11 min of Eevee
```

```
[dock4] closed   L x W x H = 639.0 x 640.0 x 836.0 mm  (spec 639 x 640 x 836)  OK (+/-1 mm)
[dock4] open     L x W x H = 1750.0 x 640.0 x 550.0 mm  (spec 1750 x 640 x 550)  OK (+/-1 mm)
[dock4] aircraft L x W x H = 395.0 x 474.0 x 230.9 mm  (user manual 392.5 x 416.2 x 230.8, spec page 393 x 477 x 230; STEP vertices 391.6 x 475.0)
[dock4] wheelbase 533.5 mm (spec 549)
[dock4] aircraft top to cover roof (inside): 8.2 mm; rotor axis z 320 mm, transfer radius 165 mm
```

## How the swap works (as modelled)

Seen from behind (+X), the aircraft's battery bay and four compartments lie on one circle around a rotor axis parallel to the aircraft: bay at 12 o'clock, compartments A 45°, B 95°, C 145°, D 215° (10:30, 9, 7, 5 o'clock). The fixed C-shaped cage holds the compartments in the same X range as the seated battery; the rotor's cradle sits just behind them and swings through a hatch in the pad. A hook on a lead screw (8 mm pitch, 185 mm stroke) pulls a battery out of the tail by its rear handle and pushes it into a compartment, then fetches a charged one. A hatch plate opposite the cradle closes the pad when the rotor is home.

| s into swap | Step |
|---|---|
| 0.0 | Cradle turns 180° up to 12 o'clock |
| 1.5 | Hook moves forward to the battery handle |
| 3.0 | Hook engages |
| 3.5 | Battery pulled out of the tail (185 mm) |
| 6.5 | Turn to free compartment C |
| 8.5 | Battery stored; charging channel 1 starts |
| 11.5 | Turn to compartment A (charged) |
| 13.5 | Charged battery pulled |
| 16.0 | Turn back to 12 o'clock |
| 17.0 | Battery inserted into the aircraft |
| 20.0 | Hook releases and returns |
| 22.5 | Rotor home, pad flush; 25.0 s swap complete |

DJI publishes the order (launch film, KOSECO and Drone DR1 footage) and the 25 s total; the sub-step split above is an estimate.

## What is DJI's, what is fitted, what is estimated

- **DJI, used verbatim:** both dock envelopes, footprint and bolt pattern, battery size, compartment count and the three-battery limit, charging channels, swap and turnaround times, part numbering (UM p24 dock, p10 aircraft), battery LED bands (p71).
- **Fitted to DJI's own CAD:** DJI's Matrice 5TD STEP (`research/docs/3d-model-stp/`, 266 MB) is cut off on DJI's server at entity #3689064, before Creo wrote any edge or face, so no CAD kernel can rebuild a solid. Its vertex points survive in assembly coordinates and span 391.6 × 475.0 mm, matching the published length. Fuselage sections, motor centres, battery bay, gimbal and LiDAR are fitted to them. The fitted wheelbase is 533.5 mm against DJI's 549 mm. Re-check the download page for a fixed upload.
- **Read from footage and renders:** rotor axis parallel to the aircraft, C-shaped cage, compartment angles, cradle with lead screw and hook, cradle rising behind the H marker through a hatch that reaches into the −Y hump, push blocks inside both cover halves.
- **Estimated:** transfer radius 165 mm, axis height 320 mm, hook stroke and screw pitch, hatch plate opposite the cradle, cover pivot (290.5 mm out, 179 mm up, so a 90° swing lands on 1750 mm), pad hump profile, internal boxes (air conditioner, power unit, cabinet), sub-step timing.
- **Cover geometry note:** a 90° swing with the pivot at the bottom edge of each half would push the open tubs 42 mm into the body. The halves therefore stop at the pivot on their X ends; only the corner legs on the Y faces reach 130 mm and swing in beside the 544 mm body.

## Sections below the viewer

- **01 Scenarios:** DJI's six named uses for Dock 4 (first response, power line inspection, overnight patrol, surveys, rescue, remote sites), each with airborne minutes per hour for Dock 3 and Dock 4 at a typical flight length.
- **02 Generations:** "One hour at the dock": for a chosen flight length (5 to 44 min), one 60-minute strip per dock showing flying, charging on the pad (Dock 2/3) or battery swaps (Dock 4), with the charge of the battery in the aircraft underneath and the minutes flying per hour. Each strip is the hour of a long day of back-to-back flights whose flying time equals the day's average, so the numbers match section 01. Model: battery use at the hover rate, recharge at DJI's published rate plus 20 s on the pad for Dock 2/3, 45 s per landing for Dock 4 with two charging channels. Below it, the spec table of Dock 2 + M3D, Dock 3 + M4D and Dock 4 + M5TD from DJI's spec sheets.
- **Recorder:** the "Record video" widget under the view controls (or the R key) records the 3D view to MP4 (H.264) where the browser can, WebM otherwise, 30 fps. Frame 16:9 1920 × 1080, 9:16 1080 × 1920 for Reels and TikTok (1280 × 720 on phones and slower machines) or the window size; length the whole 44 s clip, the swap (27 s) or until stopped; step captions with the swap clock and a credit line burned in. While it runs, the stage becomes a viewfinder: the recorded output itself (captions included) in its frame, the area outside dimmed, corner marks and a REC timer. It records in real time with MediaRecorder, so a slow GPU gives fewer frames. In the Claude artifact the file is saved through the viewer's downloads capability; on budotsmedia.com and from disk through a normal download.
- **03 Sample data:** a seeded simulation of one day (patrols, dispatches, inspections, a wind front above 12 m/s). It applies DJI's swap rule (aircraft < 90 %, stored pack > 90 %), the 27 min two-channel charging and the three-battery limit. The screens are generic, not DJI software, and are marked as sample data. Deep links: `#dock`, `#log`, `#weather`, `#live`, plus the 3D links `#xray`, `#cut`, `#solid` and step keys such as `#pull`.

## Case study page

`web/case-study.html` → https://budotsmedia.com/uas/dji-dock4-matrice5td/case-study/: one flight driven by scrolling, in the Dot Portal design system (night theme; DotGothic16 and Silkscreen, both OFL, in place of the 04 fonts, whose licence does not cover redistribution on a commercial site). Chapters: cover opens (clip frames 1020–1140), take-off (1140–1320, then a lift to 12 m), camera orbit, a simulated rotating LiDAR scan (analytic ray casts from the dome: 32 beams over −42° to +17°, 1024 steps per turn, six turns, about 113,000 returns from ground, fence, buildings, trees and a power line, coloured by height), RTK (waves from the O4 Ground Station, satellite links, the correction link), then descent (clip 0–90) and the cover closing (120–270). The 3D renders at half resolution with a 4 × 4 ordered dither and is enlarged without smoothing. Lift and yaw go on rig groups around the aircraft and batteries, because the animation mixer only rewrites a value when the clip time changes. Credits are at the bottom only. Share image `web/case-study-og.jpg` (LiDAR chapter, 1200 × 630).

## Compilation video

`video/compilation/` builds the 61 s, 1920 × 1080 compilation shown on https://budotsmedia.com/uas/#video: title, DJI's launch-film X-ray CG of the swap (credited; DJI's clip is not in the repo), our rear X-ray at 2× with three step captions, five chapters of the case study recorded frame by frame at 30 fps (`rec_case_study.mjs` replaces `requestAnimationFrame` and `performance.now` with a virtual clock, so the RTK waves and the easing play at real speed), the Dock 2/3/4 airborne-minutes card and an end card. Text is JetBrains Mono, rendered to PNG in headless Chrome (`make_cards.mjs`); `build_compilation.py` encodes each part and joins them with 0.4 s cross-fades. See `video/compilation/README.md`.

## Publishing

- **Website:** https://budotsmedia.com/uas/dji-dock4-matrice5td/ is served by its own Worker, `uas-dji-dock4-matrice5td` (`wrangler.jsonc`). The `/uas/` index, the UAS link in the top bar and the redirects from `/uas-dji-dock4-matrice5td` and `/uas/dji-dock4-20261015op55` are in the site repo `budotsmediaph/budotsmedia-website`. The web page loads `dock4.glb` as its own file; `web/index.html` keeps it embedded. `./deploy.sh` rebuilds `site/` and deploys; it goes live at once.
- **Repo:** public at `budotsmediaph/uas-dji-dock4-matrice5td`: `web/`, `blender/build.py`, `dock4.blend`, `renders/` (stills, video, `make_video.py`), `textures/` and this README.
- **Not in the repo (`.gitignore`):** `research/`, which holds DJI manuals, DJI's STEP and third-party footage; `official/m5td_vertices.npy` and its preview image, which are derived from DJI's CAD and fall under DJI's download terms; generated frames and captions.

## Notes

- **Licence:** the STEP and manuals are DJI's; use them within DJI's download terms.
- **Unofficial:** not affiliated with or endorsed by DJI.

---

*Signed: Claude (Claude Code) · model `claude-opus-5-5` (Claude Opus 5.5) · 2026-10-16*
