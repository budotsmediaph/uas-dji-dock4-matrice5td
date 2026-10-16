"""Assemble the Dock 4 compilation: title, DJI's X-ray CG, our Blender X-ray swap (2x), the case-study flight
(cover opens, orbit, LiDAR, RTK, landing), the Dock 2/3/4 comparison and the end card.
Each segment is encoded to 1920x1080 / 30 fps first, then the segments are joined with 0.4 s cross-fades.
Output: results/dock4-compilation_1920x1080.mp4 (H.264, silent AAC track for platforms that expect audio).
Run: python3 scripts/build_compilation.py   (needs ffmpeg; inputs from rec_case_study.mjs and make_cards.mjs)"""
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
# COMP_ROOT holds inputs/ (DJI's clip, not redistributable), work/ (recorded frames, cards) and results/;
# DOCK4_RENDERS is the Dock 4 repo's renders/ folder (swap_frames/ from `blender -b -P blender/build.py -- --video`).
ROOT = os.environ.get("COMP_ROOT", os.path.dirname(HERE))
WORK, RES = os.path.join(ROOT, "work"), os.path.join(ROOT, "results")
SRC = os.environ.get("DOCK4_RENDERS", os.path.join(ROOT, "..", "20261016-claude-opus5.5", "renders"))
DJI = os.path.join(ROOT, "inputs", "dji-dock4-xray-cg_from-x.mp4")
CARDS, CS = os.path.join(WORK, "cards"), os.path.join(WORK, "cs")
SEG = os.path.join(WORK, "seg")
os.makedirs(SEG, exist_ok=True)
os.makedirs(RES, exist_ok=True)
FPS, XF = 30, 0.4
ENC = ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an"]


def run(args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def card(name):
    return os.path.join(CARDS, name + ".png")


def still(out, image, secs, overlay=None, zoom=1.06):
    """A still with a slow push-in (image upscaled first so zoompan does not jitter)."""
    n = int(secs * FPS)
    ins, fc = ["-i", image], f"[0]scale=3840:-2,crop=3840:2160,zoompan=z='1+({zoom}-1)*on/{n}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={n}:s=1920x1080:fps={FPS}[b]"
    last = "[b]"
    if overlay:
        ins += ["-i", overlay]
        fc += f";[b][1]overlay[o]"
        last = "[o]"
    run([*ins, "-filter_complex", fc, "-map", last, "-frames:v", str(n), *ENC, out])


def frames(out, pattern, start, count, overlay, rate=FPS):
    run(["-framerate", str(rate), "-start_number", str(start), "-i", pattern, "-i", overlay, "-filter_complex",
         f"[0]scale=1920:1080:flags=lanczos,fps={FPS}[b];[b][1]overlay[o]", "-map", "[o]", "-frames:v",
         str(int(count * FPS / rate)), *ENC, out])


segs = []

# 1 title over our open-dock render
p = os.path.join(SEG, "01_title.mp4"); still(p, os.path.join(SRC, "02_open_landing.png"), 3.8, card("title")); segs.append(p)

# 2 DJI's launch-film X-ray CG (whole clip, 2:1 letterboxed)
p = os.path.join(SEG, "02_dji.mp4")
run(["-i", DJI, "-i", card("dji"), "-filter_complex", "[0:v:0]scale=1920:960:flags=lanczos,pad=1920:1080:0:60,setsar=1[b];[b][1]overlay[o]",
     "-map", "[o]", *ENC, p]); segs.append(p)

# 3 our rear X-ray swap at 2x: cover closes (frames 120-269), steps 1 (270-464), 2 (465-599), 3 (600-1019)
xr = os.path.join(SRC, "swap_frames", "f_%04d.png")
parts = []
for i, (cap, f0, f1) in enumerate([("x0", 120, 270), ("x1", 270, 465), ("x2", 465, 600), ("x3", 600, 1020)]):
    q = os.path.join(SEG, f"03_xray_{i}.mp4"); frames(q, xr, f0, f1 - f0, card(cap), rate=60); parts.append(q)
lst = os.path.join(SEG, "03_list.txt")
open(lst, "w").write("".join(f"file '{q}'\n" for q in parts))
p = os.path.join(SEG, "03_xray.mp4"); run(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", p]); segs.append(p)

# 4-8 case-study flight (frames recorded at 30 fps with a virtual clock)
for name, a, b in [("lift", 0, 195), ("orbit", 60, 170), ("lidar", 25, 210), ("rtk", 0, 180), ("land", 45, 150)]:
    p = os.path.join(SEG, f"04_{name}.mp4"); frames(p, os.path.join(CS, name, "f%04d.jpg"), a, b - a, card(name)); segs.append(p)

# 9 comparison, 10 end card
p = os.path.join(SEG, "09_compare.mp4"); still(p, card("compare"), 5.5, zoom=1.02); segs.append(p)
p = os.path.join(SEG, "10_end.mp4"); still(p, card("end"), 5.0, zoom=1.02); segs.append(p)


def dur(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).decode())


# join with cross-fades; fade in from black at the start and out at the end
durs = [dur(s) for s in segs]
ins, fc, last, t = [], [], "[0:v]", durs[0]
for s in segs:
    ins += ["-i", s]
for i in range(1, len(segs)):
    off = t - XF
    fc.append(f"{last}[{i}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[x{i}]")
    last, t = f"[x{i}]", t + durs[i] - XF
fc.append(f"{last}fade=t=in:st=0:d=0.5,fade=t=out:st={t - 0.6:.3f}:d=0.6[v]")
out = os.path.join(RES, "dock4-compilation_1920x1080.mp4")
run([*ins, "-f", "lavfi", "-t", f"{t:.3f}", "-i", "anullsrc=r=48000:cl=stereo", "-filter_complex", ";".join(fc), "-map", "[v]",
     "-map", f"{len(segs)}:a", "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS),
     "-profile:v", "high", "-level", "4.1", "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", out])
print(out, f"{dur(out):.2f} s", f"{os.path.getsize(out) / 1e6:.1f} MB")
for s, d in zip(segs, durs):
    print(f"  {os.path.basename(s):18s} {d:6.2f} s")
