"""
make_video.py - encode the rear X-ray frames from `build.py -- --video` into an MP4 with step captions.

Input : swap_frames/f_0120.png ... f_1140.png (cover closing -> cover open), ../web/dock4_meta.json
Output: dock4_swap_xray_rear.mp4 (1280 x 720, 30 fps, H.264, no audio); captions/ holds the caption PNGs
Needs Pillow (pip install pillow).
"""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
meta = json.load(open(os.path.join(HERE, "..", "web", "dock4_meta.json")))
TL = meta["timeline"]
F, FPS = TL["frames"], TL["fps"]
F0 = F["close0"]
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

def caption_png(path, title, sub):
    """Captions as transparent PNGs (this ffmpeg build has no drawtext filter)."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fb, fr = ImageFont.truetype(BOLD, 30), ImageFont.truetype(FONT, 18)
    w = max(d.textlength(title, font=fb), d.textlength(sub, font=fr)) + 32
    d.rounded_rectangle((24, 24, 24 + w, 110), 10, fill=(0, 0, 0, 140))
    d.text((40, 34), title, font=fb, fill=(255, 255, 255, 255))
    d.text((40, 76), sub, font=fr, fill=(255, 255, 255, 205))
    foot = "DJI Dock 4 + Matrice 5TD · rear X-ray · unofficial reconstruction"
    d.text((1280 - 28 - d.textlength(foot, font=fr), 690), foot, font=fr, fill=(255, 255, 255, 170))
    img.save(path)


cues = [("Cover closes", "The aircraft stays on the pad; push blocks centre it", F["close0"], F["close1"])]
for i, s in enumerate(TL["steps"]):
    a, b = (s["f0"] - F["swap0"]) / FPS, (s["f1"] - F["swap0"]) / FPS
    cues.append((s["label"], f"Step {i + 1} of {len(TL['steps'])} · swap time {a:.1f}–{b:.1f} s of 25.0 s", s["f0"], s["f1"]))
cues.append(("Cover opens", "Swap complete; the aircraft carries the charged battery", F["open0"], F["open1"] + 1))
capdir = os.path.join(HERE, "captions")
os.makedirs(capdir, exist_ok=True)
inputs, chain, last = [], [], "[0:v]"
for k, (title, sub, f0, f1) in enumerate(cues):
    png = os.path.join(capdir, f"cap_{k:02d}.png")
    caption_png(png, title, sub)
    inputs += ["-i", png]
    a, b = (f0 - F0) / FPS, (f1 - F0) / FPS
    out_label = f"[v{k}]"
    chain.append(f"{last}[{k + 1}:v]overlay=0:0:enable='between(t,{a:.3f},{b - 0.001:.3f})'{out_label}")
    last = out_label
out = os.path.join(HERE, "dock4_swap_xray_rear.mp4")
cmd = ["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-start_number", str(F0), "-i", os.path.join(HERE, "swap_frames", "f_%04d.png"),
       *inputs, "-filter_complex", ";".join(chain), "-map", last, "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
       "-movflags", "+faststart", out]
subprocess.run(cmd, check=True)
print(out, f"{os.path.getsize(out) / 1e6:.1f} MB")
