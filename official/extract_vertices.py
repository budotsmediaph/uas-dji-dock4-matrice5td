"""
extract_vertices.py - recover what survives of DJI's truncated Matrice 5TD STEP.

Source : ../research/docs/3d-model-stp/ea340_surface_part_packing_asm_20261012.stp
         (DJI download centre, "DJI Dock 4 - Matrice 5TD - 3D Model v1.0", 266 MB, Creo export 2026-10-12)
Output : m5td_vertices.npy  (N x 4: x, y, z in mm in Creo's assembly frame, then file order)

The file stops mid-entity at #3689064. Creo writes the surfaces, points and vertices first and the
EDGE_CURVE / ADVANCED_FACE topology later, so no face or edge survived and no CAD kernel can rebuild a
solid from it. The 95,153 VERTEX_POINTs do survive, already in assembly coordinates (X across, Y up,
Z forward). build.py fits the procedural aircraft to them. Re-download the STEP if DJI fixes the upload.

    python3 -m venv /tmp/cadenv && /tmp/cadenv/bin/pip install numpy
    /tmp/cadenv/bin/python extract_vertices.py
"""
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
STEP = os.path.join(HERE, "..", "research", "docs", "3d-model-stp", "ea340_surface_part_packing_asm_20261012.stp")
if not os.path.exists(STEP):
    sys.exit(f"STEP not found: {STEP}")
data = open(STEP, "rb").read().decode("latin-1").replace("\r\n", "\n")
body = data.split("DATA;", 1)[1]
body = body[:body.rfind(";\n") + 1]                      # drop the cut-off last entity
ent = {}
for e in re.split(r";\n(?=#\d+=)", body.strip()):
    m = re.match(r"#(\d+)=", e)
    if m:
        ent[int(m.group(1))] = e
num = re.compile(r"[-+]?\d*\.?\d+(?:E[-+]?\d+)?")
pts = []
for i, e in enumerate(ent.values()):
    if "=VERTEX_POINT(" in e:
        ref = int(re.findall(r"#(\d+)", e.split("=", 1)[1])[0])
        if ref in ent:
            pts.append([float(v) for v in num.findall(ent[ref].split("(", 2)[2])[:3]] + [i])
pts = np.array(pts)
np.save(os.path.join(HERE, "m5td_vertices.npy"), pts)
print(len(pts), "vertices; extent (mm):", np.round(pts[:, :3].max(0) - pts[:, :3].min(0), 1))
