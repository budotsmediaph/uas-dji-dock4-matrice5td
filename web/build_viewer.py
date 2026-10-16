"""
build_viewer.py - assemble the WebGL viewer for the Dock 4 battery swap.

Inputs:  viewer.src.html, parts/more.{css,html,js} (scenarios, generations, operator screens),
         dock4.glb, dock4_meta.json  (the last two come from ../blender/build.py)
Outputs: index.html     standalone page, GLB embedded; opens straight from disk
         artifact.html  the same page without the document shell, for publishing
         ../site/uas/dji-dock4-matrice5td/  budotsmedia.com page: index.html with site head (canonical, Open Graph,
                        GA4) and a breadcrumb, dock4.glb as its own file, og.jpg (1200 x 630) from renders/03
"""

import base64
import html
import json
import os
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "viewer.src.html"), encoding="utf-8").read()
meta = json.load(open(os.path.join(HERE, "dock4_meta.json"), encoding="utf-8"))
glb = open(os.path.join(HERE, "dock4.glb"), "rb").read()


def order(h):
    i = h["id"]
    return (0, int(i)) if i.isdigit() else (1 if i[0] == "S" else 2, int(i[1:]))


groups = {"dock": ("Dock · user manual p. 24", []), "swap": ("Battery swapping module · reconstructed", []), "aircraft": ("Matrice 5TD · user manual p. 10", [])}
for h in sorted(meta["hotspots"], key=order):
    groups[h["group"]][1].append(h)
parts = []
for title, items in groups.values():
    parts += [f'<div class="group-label">{html.escape(title)}</div>', '<ul class="parts">']
    parts += [f'<li><button type="button" data-id="{h["id"]}" aria-pressed="false"><span class="n">{h["id"]}</span>'
              f'<span>{html.escape(h["label"])}</span></button></li>' for h in items]
    parts.append("</ul>")

v = meta["validation"]
fmt = lambda x: f"{x:.1f}"
subs = {
    "__PARTS__": "\n        ".join(parts),
    "__CL__": fmt(v["closed"]["model_mm"][0]), "__CW__": fmt(v["closed"]["model_mm"][1]), "__CH__": fmt(v["closed"]["model_mm"][2]),
    "__OL__": fmt(v["open"]["model_mm"][0]), "__OW__": fmt(v["open"]["model_mm"][1]), "__OH__": fmt(v["open"]["model_mm"][2]),
    "__AL__": fmt(v["aircraft"]["model_mm"][0]), "__AW__": fmt(v["aircraft"]["model_mm"][1]), "__AH__": fmt(v["aircraft"]["model_mm"][2]),
    "__WB__": fmt(v["wheelbase_mm"]["model"]),
    "__META__": json.dumps({"timeline": meta["timeline"], "geometry": meta["geometry"]}, separators=(",", ":")),
}
for k, f in (("__MORE_CSS__", "more.css"), ("__MORE_HTML__", "more.html"), ("__MORE_JS__", "more.js")):
    subs[k] = open(os.path.join(HERE, "parts", f), encoding="utf-8").read()


def fill(extra):
    page = src
    for k, val in {**subs, **extra}.items():
        assert k in page, k
        page = page.replace(k, val)
    return page


shell = ('<!doctype html>\n<html lang="en">\n<meta charset="utf-8">\n'
         '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
         '<style>html,body{margin:0}[hidden]{display:none!important}</style>\n')
local = {"__GLB_B64__": base64.b64encode(glb).decode("ascii"), "__GLB_URL__": "", "__SITE_NAV__": ""}
page = fill(local)
open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(shell + page + "\n</html>\n")
open(os.path.join(HERE, "artifact.html"), "w", encoding="utf-8").write(page)
print(f"index.html {os.path.getsize(os.path.join(HERE, 'index.html')) / 1e6:.2f} MB")

# budotsmedia.com/uas/dji-dock4-matrice5td/ (Worker uas-dji-dock4-matrice5td, ../wrangler.jsonc)
SLUG = "dji-dock4-matrice5td"
URL = f"https://budotsmedia.com/uas/{SLUG}/"
out = os.path.join(HERE, "..", "site", "uas", SLUG)
os.makedirs(out, exist_ok=True)
desc = ("Unofficial 3D reconstruction of DJI Dock 4 and the Matrice 5TD: the 25-second battery swap in X-ray and "
        "cut-away, Dock 2, 3 and 4 compared, and operator screens with sample data.")
head = (f'<meta name="description" content="{html.escape(desc)}">\n'
        f'<link rel="canonical" href="{URL}">\n'
        '<meta property="og:title" content="DJI Dock 4 + Matrice 5TD: battery swap in 3D">\n'
        f'<meta property="og:description" content="{html.escape(desc)}">\n'
        f'<meta property="og:type" content="website">\n<meta property="og:url" content="{URL}">\n'
        f'<meta property="og:image" content="{URL}og.jpg">\n'
        '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        '<link rel="icon" href="/favicon.ico">\n'
        '<script async src="https://www.googletagmanager.com/gtag/js?id=G-2QYQ7Y2JRK"></script>\n'
        "<script>window.dataLayer = window.dataLayer || []; function gtag(){dataLayer.push(arguments);} "
        "gtag('js', new Date()); gtag('config', 'G-2QYQ7Y2JRK');</script>\n")
nav = ('<nav class="crumbs" aria-label="budotsmedia.com"><a href="/">BUDOTS.MEDIA</a><span aria-hidden="true">/</span>'
       '<a href="/uas/">UAS</a></nav>\n      ')
page = fill({"__GLB_B64__": "", "__GLB_URL__": f"/uas/{SLUG}/dock4.glb", "__SITE_NAV__": nav})
t_old = "<title>UAS · DJI Dock 4 + Matrice 5TD</title>"
assert t_old in page
page = page.replace(t_old, "<title>DJI Dock 4 + Matrice 5TD battery swap — UAS — BUDOTS MEDIA</title>\n" + head.rstrip("\n"), 1)
open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(shell + page + "\n</html>\n")
shutil.copyfile(os.path.join(HERE, "dock4.glb"), os.path.join(out, "dock4.glb"))
og = os.path.join(out, "og.jpg")
src_png = os.path.join(HERE, "..", "renders", "03_rear_xray_pull.png")
if shutil.which("ffmpeg") and (not os.path.exists(og) or os.path.getmtime(og) < os.path.getmtime(src_png)):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src_png, "-vf", "scale=1200:-1,crop=1200:630",
                    "-q:v", "3", og], check=True)
nf = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
      '<title>Not found — BUDOTS MEDIA</title><style>body{margin:0;font:16px/1.5 system-ui,sans-serif;background:#f3efe6;'
      'color:#1a1a1a;display:grid;place-items:center;min-height:100vh;padding:0 16px}a{color:#c8102e}</style>'
      f'<p>Page not found. <a href="/uas/{SLUG}/">DJI Dock 4 + Matrice 5TD</a> · <a href="/uas/">UAS</a> · '
      '<a href="/">budotsmedia.com</a></p></html>\n')
open(os.path.join(HERE, "..", "site", "404.html"), "w", encoding="utf-8").write(nf)
print(f"site {out}: index.html {os.path.getsize(os.path.join(out, 'index.html')) / 1e3:.0f} kB, dock4.glb, og.jpg")
