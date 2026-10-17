# Dock 4 compilation video

61 s, 1920 × 1080, 30 fps, H.264, silent AAC track. Shown on https://budotsmedia.com/uas/#video (1280 × 720 web encode)
and posted on 17 Oct 2026 to YouTube (https://youtu.be/-OMzsNUIZkA) and Threads
(https://www.threads.com/@entp83/post/DelZITLkeUS); the Aerial Data Ops LinkedIn page is next.

| Time | Part | Source |
|---|---|---|
| 0–3.8 s | Title over `renders/02_open_landing.png` | our Blender still |
| 3.4–13.2 s | DJI's X-ray view of the swap | DJI launch film (CG), credited "Video: DJI"; not in this repo |
| 12.8–27.8 s | Cover closes, then steps 1–3 of the swap at 2× | `renders/swap_frames/` 120–1019 |
| 27.4–53.5 s | Cover opens and take-off, orbit, LiDAR, RTK, landing | `web/case-study.html`, recorded with `rec_case_study.mjs` |
| 53.1–58.6 s | Airborne minutes per hour at 20-min flights: Dock 2 28, Dock 3 35, Dock 4 58 | timing model of the viewer's section 02 |
| 58.2–61.3 s | End card: budotsmedia.com/uas, Aerial Data Ops logo | |

## Build

```sh
# COMP_ROOT: a folder with inputs/dji-dock4-xray-cg_from-x.mp4; work/ and results/ are created there
export COMP_ROOT=/path/to/compilation-workdir DOCK4_RENDERS=$PWD/renders
node video/compilation/rec_case_study.mjs https://budotsmedia.com/uas/dji-dock4-matrice5td/case-study/ $COMP_ROOT/work/cs 1920 1080 \
  "lift:1:0:2:1:8,orbit:3:0:3:1:6,lidar:4:0:4:1:7,rtk:5:0:5:1:6,land:6:0:6:1:5"
node video/compilation/make_cards.mjs $COMP_ROOT/work/cards "<Aerial Data Ops logo .jpg>"
python3 video/compilation/build_compilation.py
```

`rec_case_study.mjs` hides the page chrome, replaces `requestAnimationFrame` and `performance.now` with a virtual clock
and advances it 1/30 s per captured frame, so time-based motion plays at real speed whatever the capture time
(50–70 ms per frame on an M-series Mac with Metal). Cards are HTML in JetBrains Mono, captured as PNG with a
transparent background. This ffmpeg build has no `drawtext`, so all text is overlaid as images.

## Versions

| Version | Date | Change | Result |
|---|---|---|---|
| v1 | 2026-10-16 | First cut: DJI clip, X-ray swap at 2×, five case-study chapters, comparison and end card | 61.3 s, 63 MB master, 13 MB web encode (CRF 27, 1280 × 720) |
