"""
build.py - DJI Dock 4 + DJI Matrice 5TD, with the automated battery swap.
Opus 5.5 (claude-opus-5-5), 2026-10-16. Same pipeline as ../../../dock3/20260922-claude-opus5.5/.

Everything DJI publishes is used verbatim and the dock envelope is checked to +/-1 mm on every build.
Everything DJI does not publish (hinge, pad profile, rotor radius, compartment angles, step timing) is
derived from the published envelopes and proportioned from DJI's own animation and real footage.
Sources and confidence levels: ../research/README.md.

  Spec page (enterprise.dji.com/dock-4/specs, read 2026-10-16)
      closed 639 x 640 x 836 mm, open 1750 x 640 x 550 mm, both including the 145 mm wind speed gauge
      and the 69 mm mounting base brackets; swap < 25 s from cover fully closed; landing to take-off
      < 45 s; 4 battery compartments holding at most 3 batteries; 2 charging channels, 27 min 15 -> 95 %
  User Manual v1.0: p10 aircraft parts, p24 dock parts 1-14, p71 battery LEDs, p95 battery
      BPX340 96.02 x 67.7 x 172.9 mm, 925 g, 260 Wh
  Installation and Setup Manual v1.0: p44 footprint 567 x 555 mm, bolt pattern 400 x 400 mm; p53 side view
  DJI's Matrice 5TD STEP (download centre, Creo, 2026-10-12): truncated on DJI's server, no face survives.
      ../official/m5td_vertices.npy holds its 95,153 vertex points in assembly coordinates; the aircraft
      below is fitted to them (fuselage sections, motor centres, battery bay, gimbal, LiDAR).
  Swap mechanism: DJI launch film 62-77 s (rear X-ray, lead screw, hook), Drone DR1's render of the
      compartment cage, KOSECO footage of the cradle rising through the pad.

Frame: +X = tail of the aircraft and the swap module; -X = nose and the wind-gauge half of the cover;
-Y = cabinet face (status light, e-stop); +Z up; origin = bottom of the mounting brackets.

Run:  blender -b -P build.py -- [--render] [--shots=a,b] [--video] [--no-export]
"""

import bpy
import bmesh
import json
import math
import os
import sys

import numpy as np
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
DO_RENDER = "--render" in ARGV
DO_VIDEO = "--video" in ARGV
DO_EXPORT = "--no-export" not in ARGV
SHOTS = next((a.split("=", 1)[1].split(",") for a in ARGV if a.startswith("--shots=")), None)
TOL_MM = 1.0

# ============================================================================ 1. numbers
SPEC = {
    "closed_mm": [639, 640, 836], "open_mm": [1750, 640, 550],
    "gauge_mm": 145, "bracket_mm": 69, "footprint_mm": [567, 555], "mount_holes_mm": [400, 400],
    "weight_kg": 66, "ip": "IP56", "temperature_c": [-40, 50],
    "aircraft_mm": [392.5, 416.2, 230.8], "aircraft_mm_spec_page": [393, 477, 230], "wheelbase_mm": 549,
    "propeller": "1564F (15 in)", "aircraft_g": 2600, "mtow_g": 3050,
    "battery_mm": [172.9, 96.02, 67.7], "battery": {"model": "BPX340-12138-21.42", "g": 925, "wh": 260, "v": 21.42},
    "swap_s": 25, "turnaround_s": 45, "compartments": 4, "max_stored": 3,
    "charging": {"channels": 2, "minutes": 27, "from_pct": 15, "to_pct": 95},
}
MM = 0.001
BRACKET_H = SPEC["bracket_mm"] * MM                                   # 0.069
GAUGE_H = SPEC["gauge_mm"] * MM                                       # 0.145
LID_HX = SPEC["closed_mm"][0] * MM / 2                                # 0.3195
LID_HY = SPEC["closed_mm"][1] * MM / 2                                # 0.320
LID_TOP = (SPEC["closed_mm"][2] - SPEC["gauge_mm"]) * MM              # 0.691 roof
LID_BOT, LID_T, SEAM = 0.130, 0.012, 0.0015                           # LID_BOT: the corner legs on the Y faces
OPEN_REACH = (SPEC["open_mm"][0] - SPEC["gauge_mm"]) * MM / 2         # 0.8025: +X end of the open dock
PIVOT_X = 0.2905                                                      # just outside the body (567 mm)
PIVOT_Z = LID_TOP - (OPEN_REACH - PIVOT_X)                            # 0.179: a 90 deg swing lands the roof on 1750 mm
LID_DX, LID_DZ = 0.0, 0.0                                             # no linkage offset needed
# Below the pivot only the thin corner legs (outside the 544 mm body) continue down to LID_BOT; they swing in
# beside the body. The X end walls stop at the pivot, so the open tubs sit 290-803 mm from the centre (UM p24 plan).
OPEN_H = SPEC["open_mm"][2] * MM                                      # 0.550 = hump tops of the pad

BODY_HX = SPEC["footprint_mm"][0] * MM / 2                            # 0.2835
BODY_HY, BODY_Z1 = 0.272, 0.430                                     # e-stop mushroom stays inside the 640 mm width
DECK_Z = 0.440                                                        # channel floor and rim of the pad
HUMP = OPEN_H - DECK_Z - 0.0008                                       # decals sit 0.8 mm proud
FY, BY = -BODY_HY, BODY_HY

# swap module (estimated from DJI's CG: transfer circle radius 150-200 mm, see research 3e)
R_SWAP = 0.165                                                        # rotor axis -> battery centre
BAT_L, BAT_W, BAT_H = (v * MM for v in SPEC["battery_mm"])            # 0.1729, 0.09602, 0.0677
REAR_IN = 0.040                                                       # battery rear face when seated (aircraft or compartment)
HANDLE = 0.006                                                        # handle stands this far behind the rear face
HATCH = (0.046, 0.262, -0.190, 0.066)                                 # pad opening: x0, x1, y0, y1
CRADLE_X0, CRADLE_X1 = 0.050, 0.252                                   # a carried battery spans 52-225 mm, clear of stored handles (<= 46 mm)
HOOK_GRIP, HOOK_STROKE = REAR_IN + HANDLE, 0.185
HOOK_HOME = HOOK_GRIP + HOOK_STROKE                                   # 0.231: rear of the cradle
COMPARTMENTS = {"A": 45.0, "B": 95.0, "C": 145.0, "D": 215.0}         # degrees from 12 o'clock toward -Y (seen from +X: 10:30, 9, 7, 5 o'clock)
SCREW_PITCH = 0.008

# aircraft: local frame = DJI's Creo frame turned so nose -> -X, up -> +Z (lx = -cz, ly = -cx, lz = cy), mm -> m
AC_REST = Vector((REAR_IN - 0.1745, 0.0, 0.0))                       # battery rear face (cz -174.5) lands on REAR_IN
AC_FOOT = -0.045                                                      # lowest point of the landing feet
AC_REST.z = DECK_Z - AC_FOOT                                          # 0.485 = battery centre height
ZA = AC_REST.z - R_SWAP                                               # 0.320 rotor axis height
BATT_LOCAL = Vector((0.1745 - BAT_L / 2, 0.0, 0.0))                   # battery centre in the aircraft frame
PROP_R = 0.1905                                                       # 15 in
MOTORS = {"FL": (-0.101, 0.2115, 0.100, 0.132, 0.0255, -1), "FR": (-0.101, -0.2115, 0.100, 0.132, 0.0255, +1),
          "RL": (0.244, 0.1955, 0.124, 0.164, 0.0245, +1), "RR": (0.244, -0.1955, 0.124, 0.164, 0.0245, -1)}

# ============================================================================ 2. timeline
FPS = 30
F = {"land0": 0, "land1": 90, "stop0": 90, "stop1": 120, "close0": 120, "close1": 270,
     "swap0": 270, "swap1": 1020, "open0": 1020, "open1": 1140, "spin0": 1140, "spin1": 1185,
     "up0": 1185, "end": 1320}
STEPS = [  # key, f0, f1, label, detail
    ("raise", 270, 315, "Cradle turns up", "The rotor turns the empty cradle 180° to 12 o'clock, through the pad hatch, behind the tail."),
    ("reach", 315, 360, "Hook moves forward", "The lead screw drives the hook 185 mm forward (−X) to the handle on the battery's rear face."),
    ("grip", 360, 375, "Hook engages", "The hook rises 8 mm into the handle and releases the battery latch."),
    ("pull", 375, 465, "Battery pulled out", "The battery slides 185 mm out of the tail into the cradle. The pad's wireless coil keeps the aircraft powered."),
    ("turn_store", 465, 525, "Turn to free compartment", "The rotor carries the battery from 12 o'clock to compartment C (145°)."),
    ("store", 525, 600, "Battery stored", "The hook pushes the battery into compartment C until its contacts mate; charging channel 1 starts."),
    ("release", 600, 615, "Hook releases", "The hook drops out of the handle."),
    ("turn_fetch", 615, 660, "Turn to charged battery", "The empty cradle turns to compartment A (45°), which holds the fullest battery."),
    ("fetch_grip", 660, 675, "Hook engages", "The hook rises into the handle of the charged battery."),
    ("fetch", 675, 750, "Charged battery pulled", "The charged battery slides out of compartment A into the cradle."),
    ("turn_back", 750, 780, "Turn to 12 o'clock", "The rotor brings the charged battery back in line with the aircraft's battery bay."),
    ("insert", 780, 870, "Battery inserted", "The hook pushes the battery forward into the tail until it latches."),
    ("let_go", 870, 885, "Hook releases", "The hook drops out of the handle."),
    ("retract", 885, 945, "Hook returns", "The lead screw returns the hook to the rear of the cradle."),
    ("home", 945, 1020, "Rotor home", "The rotor turns 180° back; its hatch plate closes the pad flush. Swap complete."),
]
PHASES = [("Landing", F["land0"], F["land1"]), ("Props stop", F["stop0"], F["stop1"]), ("Cover closing", F["close0"], F["close1"]),
          ("Battery swap", F["swap0"], F["swap1"]), ("Cover opening", F["open0"], F["open1"]), ("Spin-up", F["spin0"], F["spin1"]),
          ("Take-off", F["up0"], F["end"])]
THETA_KEYS = [(270, 180), (315, 0), (465, 0), (525, 145), (615, 145), (660, 45), (750, 45), (780, 0), (945, 0), (1020, 180)]
HOOK_KEYS = [(315, HOOK_HOME), (360, HOOK_GRIP), (375, HOOK_GRIP), (465, HOOK_GRIP + HOOK_STROKE), (525, HOOK_GRIP + HOOK_STROKE),
             (600, HOOK_GRIP), (675, HOOK_GRIP), (750, HOOK_GRIP + HOOK_STROKE), (780, HOOK_GRIP + HOOK_STROKE), (870, HOOK_GRIP),
             (885, HOOK_GRIP), (945, HOOK_HOME)]
LIFT_KEYS = [(360, 0), (375, 1), (600, 1), (615, 0), (660, 0), (675, 1), (870, 1), (885, 0)]
# battery schedule: (from_frame, place); place = "ac", "cradle" or a compartment letter
BATTERIES = {
    "B1": {"level": 22, "schedule": [(0, "ac"), (375, "cradle"), (600, "C")], "charge_from": 600},
    "B2": {"level": 95, "schedule": [(0, "A"), (675, "cradle"), (870, "ac")], "charge_from": None},
    "B3": {"level": 95, "schedule": [(0, "B")], "charge_from": None},
    "B4": {"level": 68, "schedule": [(0, "D")], "charge_from": 0},
}
OMEGA, FOLD = math.radians(70), math.radians(9)


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (t * 6 - 15) + 10)


def ramp(f, a, b):
    return smooth((f - a) / (b - a))


def piece(f, keys):
    """Hold, then ease between successive (frame, value) keys."""
    if f <= keys[0][0]:
        return keys[0][1]
    for (fa, va), (fb, vb) in zip(keys, keys[1:]):
        if f <= fb:
            return va + (vb - va) * smooth((f - fa) / (fb - fa)) if fb > fa else vb
    return keys[-1][1]


theta = lambda f: math.radians(piece(f, THETA_KEYS))
hook_x = lambda f: piece(f, HOOK_KEYS)
hook_lift = lambda f: piece(f, LIFT_KEYS)


def place(b, f):
    return [p for f0, p in BATTERIES[b]["schedule"] if f >= f0][-1]


def battery_leds(level, f, charging):
    """User manual p.71: four LEDs, eight bands of on / flashing; while charging the next LED flashes."""
    bands = [(92, 4, None), (76, 3, 3), (63, 3, None), (51, 2, 2), (38, 2, None), (26, 1, 1), (13, 1, None), (0, 0, 0)]
    n_on, flash = next((n, fl) for lo, n, fl in bands if level >= lo)
    if charging and n_on < 4:
        flash = n_on
    blink = (f // 15) % 2 == 0
    return [i < n_on or (flash == i and blink) for i in range(4)]


# ============================================================================ 3. scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = "Dock4Swap"
scene.render.fps = FPS
scene.frame_start, scene.frame_end = 0, F["end"]
bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"


def collection(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c


C_DOCK, C_SWAP, C_BATT, C_AC, C_SITE, C_STUDIO = (collection(n) for n in ("Dock4", "SwapModule", "Batteries", "Matrice5TD", "Site", "Studio"))

# ============================================================================ 4. materials
os.makedirs(os.path.join(ROOT, "textures"), exist_ok=True)


def texture(name, rgba):
    h, w = rgba.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.pixels.foreach_set(np.flipud(rgba).astype(np.float32).ravel())
    img.filepath_raw = os.path.join(ROOT, "textures", name + ".png")
    img.file_format = "PNG"
    img.save()
    return img


def slots(px=96):
    """Tileable louvre slots (pad vent grille, cabinet vents, rear dust screen)."""
    yy, xx = np.mgrid[0:px, 0:px] + 0.5
    v = np.full((px, px), 0.2)
    v[((xx % (px / 4)) > px / 16) & ((xx % (px / 4)) < px / 6.5) & (yy > px * 0.08) & (yy < px * 0.92)] = 0.015
    return np.dstack([v, v, v * 1.04, np.ones_like(v)])


TEX_SLOTS = texture("slots", slots())


def hazard(w=192, h=128):
    """Cradle label (KOSECO footage): yellow field, black-and-yellow hazard border, battery-insertion pictogram."""
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    img = np.zeros((h, w, 3))
    img[:] = (0.95, 0.74, 0.05)
    band = (xx < w * 0.08) | (xx > w * 0.92) | (yy < h * 0.12) | (yy > h * 0.88)
    img[band & (((xx + yy) // 10) % 2 == 0)] = (0.03, 0.03, 0.03)
    img[(xx > w * 0.30) & (xx < w * 0.70) & (yy > h * 0.33) & (yy < h * 0.67)] = (0.35, 0.37, 0.45)
    img[(xx > w * 0.74) & (xx < w * 0.84) & (np.abs(yy - h / 2) < (w * 0.84 - xx) * 0.6)] = (0.03, 0.03, 0.03)
    return np.dstack([img, np.ones((h, w))])


TEX_HAZARD = texture("hazard_label", hazard())
TEX_TILE = 0.024


def material(name, rgb, rough=0.5, metal=0.0, coat=0.0, coat_rough=0.12, emit=None, strength=0.0, image=None):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = coat_rough
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    if image:
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = image
        nt.links.new(tn.outputs["Color"], b.inputs["Base Color"])
    m.diffuse_color = (*rgb, 1)
    return m


M = {
    "white": material("Dock_Paint", (0.76, 0.775, 0.79), 0.36, coat=0.45),
    "deck": material("Dock_Deck", (0.085, 0.09, 0.096), 0.66, coat=0.12, coat_rough=0.4),
    "lid_in": material("Dock_CoverInner", (0.11, 0.115, 0.12), 0.72),
    "internal": material("Dock_Internal", (0.22, 0.23, 0.24), 0.55, 0.3),
    "black": material("Dock_Black", (0.016, 0.016, 0.018), 0.45),
    "metal": material("Metal", (0.66, 0.67, 0.69), 0.26, 1.0),
    "marker": material("Dock_MarkerLit", (0.92, 0.94, 0.96), 0.5, emit=(0.9, 0.95, 1.0), strength=1.6),
    "paint_white": material("Dock_MarkingPaint", (0.86, 0.87, 0.87), 0.55),
    "yellow": material("Dock_EStopYellow", (0.95, 0.66, 0.02), 0.35, coat=0.4),
    "red": material("Dock_EStopRed", (0.72, 0.035, 0.02), 0.3, coat=0.6),
    "vent": material("Dock_Vent", (0.2, 0.2, 0.21), 0.55, 0.4, image=TEX_SLOTS),
    "led": material("Dock_StatusLED", (0.55, 0.75, 1.0), 0.3, emit=(0.35, 0.6, 1.0), strength=6.0),
    "glass": material("Glass", (0.008, 0.01, 0.016), 0.04, coat=1.0, coat_rough=0.02),
    "charge": material("Dock_ChargeGlow", (0.5, 0.95, 1.0), 0.3, emit=(0.35, 0.9, 1.0), strength=8.0),
    "cage": material("Swap_CagePlastic", (0.045, 0.047, 0.05), 0.6),
    "rotor": material("Swap_Rotor", (0.20, 0.21, 0.22), 0.42, 0.55),
    "guide": material("Swap_Guide", (0.74, 0.75, 0.76), 0.5),
    "label": material("Swap_HazardLabel", (0.95, 0.74, 0.05), 0.45, image=TEX_HAZARD),
    "steel": material("Swap_Steel", (0.72, 0.73, 0.75), 0.22, 1.0),
    "brass": material("Swap_Contacts", (0.86, 0.66, 0.30), 0.3, 1.0),
    "batt": material("Batt_Shell", (0.60, 0.62, 0.64), 0.5, coat=0.15, coat_rough=0.3),
    "batt_dark": material("Batt_Window", (0.02, 0.022, 0.025), 0.2, coat=0.8, coat_rough=0.05),
    "led_batt": material("Batt_LED", (0.55, 1.0, 0.6), 0.3, emit=(0.4, 1.0, 0.5), strength=8.0),
    "ac": material("M5TD_Shell", (0.79, 0.80, 0.81), 0.42, coat=0.3, coat_rough=0.25),
    "ac_dark": material("M5TD_Dark", (0.10, 0.105, 0.11), 0.45),
    "prop": material("M5TD_Prop", (0.02, 0.02, 0.022), 0.35),
    "prop_tip": material("M5TD_PropTip", (0.95, 0.45, 0.08), 0.4),
    "led_red": material("M5TD_LED_Red", (1, 0.1, 0.05), 0.4, emit=(1, 0.08, 0.03), strength=8.0),
    "led_green": material("M5TD_LED_Green", (0.1, 1, 0.2), 0.4, emit=(0.05, 1, 0.15), strength=8.0),
    "lidar": material("M5TD_LidarWindow", (0.03, 0.035, 0.05), 0.05, coat=1.0, coat_rough=0.02),
    "concrete": material("Site_Concrete", (0.42, 0.42, 0.40), 0.95),
    "ground": material("Studio_Ground", (0.30, 0.31, 0.32), 0.9),
}

# ============================================================================ 5. geometry helpers


def _mat_faces(vs, mat):
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mat


def add_box(bm, mn, mx, bevel=0.0, segs=3, mat=0):
    vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    size = Vector(mx) - Vector(mn)
    bmesh.ops.scale(bm, vec=size, verts=vs)
    bmesh.ops.translate(bm, vec=(Vector(mn) + Vector(mx)) / 2, verts=vs)
    _mat_faces(vs, mat)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list({e for v in vs for e in v.link_edges}), offset=min(bevel, min(size) * 0.49),
                        segments=segs, profile=0.5, affect="EDGES", clamp_overlap=True)
    return vs


def add_cyl(bm, c, r, depth, segs=32, axis="Z", mat=0, r2=None):
    vs = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r,
                               radius2=r if r2 is None else r2, depth=depth)["verts"]
    rot = {"Z": Matrix.Identity(3), "X": Matrix.Rotation(math.pi / 2, 3, "Y"), "Y": Matrix.Rotation(-math.pi / 2, 3, "X")}[axis]
    bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=rot)
    bmesh.ops.translate(bm, vec=c, verts=vs)
    _mat_faces(vs, mat)
    return vs


def add_sphere(bm, c, r, scale=(1, 1, 1), mat=0, segs=24):
    vs = bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=segs // 2, radius=r)["verts"]
    bmesh.ops.scale(bm, vec=scale, verts=vs)
    bmesh.ops.translate(bm, vec=c, verts=vs)
    _mat_faces(vs, mat)
    return vs


def add_prism(bm, pts, plane, d0, d1, mat=0):
    P = {"XZ": lambda u, v, w: (u, w, v), "XY": lambda u, v, w: (u, v, w), "YZ": lambda u, v, w: (w, u, v)}[plane]
    a = [bm.verts.new(P(u, v, d0)) for u, v in pts]
    b = [bm.verts.new(P(u, v, d1)) for u, v in pts]
    n = len(pts)
    fs = [bm.faces.new(a[::-1]), bm.faces.new(b)] + [bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i])) for i in range(n)]
    for f in fs:
        f.material_index = mat
    return a + b


def add_beam(bm, p0, p1, w0, h0, w1, h1, bevel=0.005, segs=3, mat=0):
    p0, p1 = Vector(p0), Vector(p1)
    u = (p1 - p0).normalized()
    side = u.cross(Vector((0, 0, 1)))
    side = side.normalized() if side.length > 1e-6 else Vector((1, 0, 0))
    up = side.cross(u).normalized()
    vs = [bm.verts.new(p + side * sw * w / 2 + up * sh * h / 2)
          for p, w, h in ((p0, w0, h0), (p1, w1, h1)) for sw, sh in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    fs = [bm.faces.new([vs[i] for i in q]) for q in ((0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0))]
    for f in fs:
        f.material_index = mat
    if bevel:
        bmesh.ops.bevel(bm, geom=list({e for f in fs for e in f.edges}), offset=bevel, segments=segs,
                        profile=0.5, affect="EDGES", clamp_overlap=True)


def add_loft(bm, stations, n=28, mat=0):
    """Closed superellipse loft along X: stations = (x, half_width, z_bottom, z_top, exponent)."""
    rings = []
    for x, hw, zb, zt, e in stations:
        zc, hh = (zb + zt) / 2, (zt - zb) / 2
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n
            c, s = math.cos(a), math.sin(a)
            y = hw * math.copysign(abs(c) ** (2 / e), c)
            z = zc + hh * math.copysign(abs(s) ** (2 / e), s)
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((r0[i], r0[j], r1[j], r1[i])).material_index = mat
    for ring, flip in ((rings[0], True), (rings[-1], False)):
        c = bm.verts.new(sum((v.co for v in ring), Vector()) / n)
        for i in range(n):
            tri = (c, ring[(i + 1) % n], ring[i]) if flip else (c, ring[i], ring[(i + 1) % n])
            bm.faces.new(tri).material_index = mat


def planar_uv(bm, axes, tile=TEX_TILE):
    uv = bm.loops.layers.uv.verify()
    a, b = axes
    for f in bm.faces:
        for lp in f.loops:
            lp[uv].uv = (lp.vert.co[a] / tile, lp.vert.co[b] / tile)


def rrect(x0, z0, x1, z1, r, n=6):
    pts = []
    for cx, cz, a0 in ((x1 - r, z0 + r, -90), (x1 - r, z1 - r, 0), (x0 + r, z1 - r, 90), (x0 + r, z0 + r, 180)):
        pts += [(cx + r * math.cos(math.radians(a0 + 90 * i / n)), cz + r * math.sin(math.radians(a0 + 90 * i / n))) for i in range(n + 1)]
    return pts


def to_object(name, bm, mats, coll, parent=None, origin=(0, 0, 0), smooth_deg=38, recalc=True):
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if Vector(origin).length > 0:
        bmesh.ops.translate(bm, vec=-Vector(origin), verts=bm.verts)
    if smooth_deg is not None:
        lim = math.radians(smooth_deg)
        for f in bm.faces:
            f.smooth = True
        for e in bm.edges:
            e.smooth = len(e.link_faces) == 2 and e.calc_face_angle(math.pi) < lim
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(M[m] if isinstance(m, str) else m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.parent = parent
    ob.location = origin
    return ob


def part(name, build, mats, coll, parent=None, origin=(0, 0, 0), local_origin=None, **kw):
    """Build in world (closed-state) coordinates; place the object origin at `origin`.
    local_origin: parent-space origin of `parent`, subtracted so children stay put."""
    bm = bmesh.new()
    build(bm)
    ob = to_object(name, bm, mats, coll, parent, origin, **kw)
    if local_origin is not None:
        ob.location = Vector(origin) - Vector(local_origin)
    return ob


def bake(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)
    me.name = ob.name


def boolean(ob, builders):
    cutters = []
    for i, build in enumerate(builders):
        bm = bmesh.new()
        build(bm)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        me = bpy.data.meshes.new(f"cut{i}")
        bm.to_mesh(me)
        bm.free()
        c = bpy.data.objects.new(f"cut{i}", me)
        C_STUDIO.objects.link(c)
        mod = ob.modifiers.new(f"bool{i}", "BOOLEAN")
        mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", c
        cutters.append(c)
    bake(ob)
    for c in cutters:
        bpy.data.objects.remove(c, do_unlink=True)


def empty(name, coll, parent=None, loc=(0, 0, 0), size=0.05):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = size
    coll.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    return ob


def rotated(bm, ang, build, centre=(0.0, 0.0, ZA)):
    """Build into a scratch bmesh, turn it about the rotor axis (parallel to X) by `ang` radians
    (+ = toward -Y), then append it to bm."""
    tmp = bmesh.new()
    build(tmp)
    m = Matrix.Translation(Vector(centre)) @ Matrix.Rotation(ang, 4, "X") @ Matrix.Translation(-Vector(centre))
    bmesh.ops.transform(tmp, matrix=m, verts=tmp.verts[:])
    me = bpy.data.meshes.new("tmp")
    tmp.to_mesh(me)
    tmp.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


HOTSPOTS = []


def hotspot(num, label, parent, world, coll, group="dock", origin=(0, 0, 0)):
    ob = empty(f"HS_{group}_{num}", coll, parent, Vector(world) - Vector(origin), 0.02)
    ob["hotspot"], ob["label"], ob["group"] = str(num), label, group
    HOTSPOTS.append({"group": group, "id": str(num), "label": label})


# ============================================================================ 6. dock body
print("[dock4] body")
DOCK = empty("Dock4", C_DOCK, size=0.2)


def dpart(name, build, mats, coll=C_DOCK, **kw):
    return part(name, build, mats, coll, DOCK, **kw)


HOLE_X, HOLE_Y = SPEC["mount_holes_mm"][0] * MM / 2, SPEC["mount_holes_mm"][1] * MM / 2
FOOT_HX, FOOT_HY = SPEC["footprint_mm"][0] * MM / 2, SPEC["footprint_mm"][1] * MM / 2


def build_brackets(bm):
    for sx in (-1, 1):
        for sy in (-1, 1):
            add_box(bm, (min(sx * FOOT_HX, sx * (FOOT_HX - 0.12)), min(sy * FOOT_HY, sy * (FOOT_HY - 0.10)), 0),
                    (max(sx * FOOT_HX, sx * (FOOT_HX - 0.12)), max(sy * FOOT_HY, sy * (FOOT_HY - 0.10)), BRACKET_H), 0.004)


brackets = dpart("Dock_Brackets", build_brackets, ["black"])
boolean(brackets, [lambda bm: [add_box(bm, (sx * HOLE_X - 0.006 + dx, sy * HOLE_Y - 0.02, -0.01), (sx * HOLE_X + 0.006 + dx, sy * HOLE_Y + 0.02, 0.02))
                               for sx in (-1, 1) for sy in (-1, 1) for dx in (-0.03, 0.0, 0.03)]])
dpart("Dock_BracketBolts", lambda bm: [add_cyl(bm, (sx * HOLE_X, sy * HOLE_Y, 0.023), 0.0095, 0.007, 6) for sx in (-1, 1) for sy in (-1, 1)],
      ["metal"], smooth_deg=20)


def build_body(bm):
    vs = add_box(bm, (-BODY_HX, -BODY_HY, BRACKET_H), (BODY_HX, BODY_HY, BODY_Z1))
    vert_edges = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 0.1]
    bmesh.ops.bevel(bm, geom=vert_edges, offset=0.024, segments=6, profile=0.5, affect="EDGES", clamp_overlap=True)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if all(v.co.z > BODY_Z1 - 1e-6 for v in f.verts)], context="FACES_ONLY")


dpart("Dock_Body", build_body, ["white"], smooth_deg=40)


def deck_z(x, y):
    """Pad top: a channel along X (aircraft fuselage), two humps beside it, a flat rim with the corner markers."""
    ay = abs(y)
    rise = smooth((ay - 0.062) / 0.050)
    fall = 1 - smooth((ay - 0.215) / 0.050)
    xe = 0.262 - 0.55 * max(0.0, ay - 0.10)
    along = 1 - smooth((abs(x) - (xe - 0.05)) / 0.05)
    return DECK_Z + HUMP * rise * fall * along


def in_hatch(x, y):
    return HATCH[0] < x < HATCH[1] and HATCH[2] < y < HATCH[3]


def build_deck(bm):
    xs = sorted(set(np.round(np.r_[np.linspace(-BODY_HX, BODY_HX, 117), HATCH[:2]], 6)))
    ys = sorted(set(np.round(np.r_[np.linspace(-BODY_HY, BODY_HY, 125), HATCH[2:]], 6)))
    g = [[bm.verts.new((x, y, deck_z(x, y))) for x in xs] for y in ys]
    nx, ny = len(xs), len(ys)
    for j in range(ny - 1):
        for i in range(nx - 1):
            if not in_hatch((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2):
                bm.faces.new((g[j][i], g[j][i + 1], g[j + 1][i + 1], g[j + 1][i]))
    ring = [g[0][i] for i in range(nx)] + [g[j][nx - 1] for j in range(1, ny)] + [g[ny - 1][i] for i in range(nx - 2, -1, -1)] + [g[j][0] for j in range(ny - 2, 0, -1)]
    low = [bm.verts.new((v.co.x, v.co.y, BODY_Z1)) for v in ring]
    for k in range(len(ring)):
        bm.faces.new((ring[k], low[k], low[(k + 1) % len(ring)], ring[(k + 1) % len(ring)]))
    ia, ib, ja, jb = xs.index(round(HATCH[0], 6)), xs.index(round(HATCH[1], 6)), ys.index(round(HATCH[2], 6)), ys.index(round(HATCH[3], 6))
    hole = [g[ja][i] for i in range(ia, ib + 1)] + [g[j][ib] for j in range(ja + 1, jb + 1)] + [g[jb][i] for i in range(ib - 1, ia - 1, -1)] + [g[j][ia] for j in range(jb - 1, ja, -1)]
    hl = [bm.verts.new((v.co.x, v.co.y, DECK_Z - 0.015)) for v in hole]
    for k in range(len(hole)):
        bm.faces.new((hole[k], hole[(k + 1) % len(hole)], hl[(k + 1) % len(hole)], hl[k]))


dpart("Dock_LandingPad", build_deck, ["deck"], smooth_deg=50, recalc=False)


def drape(bm, pts, lift=0.0008):
    """Flat polygon on the pad surface (fan around its centroid)."""
    c = sum((Vector(p) for p in pts), Vector((0, 0))) / len(pts)
    vc = bm.verts.new((c.x, c.y, deck_z(c.x, c.y) + lift))
    vs = [bm.verts.new((x, y, deck_z(x, y) + lift)) for x, y in pts]
    for i in range(len(vs)):
        bm.faces.new((vc, vs[i], vs[(i + 1) % len(vs)]))


def build_corner_markers(bm):
    for sx in (-1, 1):
        for sy in (-1, 1):
            a = (sx * (BODY_HX - 0.012), sy * (BODY_HY - 0.012))
            drape(bm, [a, (a[0] - sx * 0.098, a[1]), (a[0], a[1] - sy * 0.098)][:: sx * sy])


dpart("Dock_PositioningMarkers", build_corner_markers, ["marker"], smooth_deg=None, recalc=False)
CHEVRON = [(-0.215, 0.0), (-0.185, -0.032), (-0.165, -0.032), (-0.192, 0.0), (-0.165, 0.032), (-0.185, 0.032)]


def build_markings(bm):
    pts = CHEVRON
    vs = [bm.verts.new((x, y, DECK_Z + 0.0008)) for x, y in pts]
    for tri in ((0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 5)):
        bm.faces.new([vs[i] for i in tri])
    hx = -0.057                                                       # "H" at 0.40 L from the -X end (UM p24)
    for x0, x1, y0, y1 in ((hx - 0.016, hx - 0.009, -0.018, 0.018), (hx + 0.009, hx + 0.016, -0.018, 0.018), (hx - 0.009, hx + 0.009, -0.0035, 0.0035)):
        bm.faces.new([bm.verts.new((x, y, DECK_Z + 0.0014)) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))])


dpart("Dock_OrientationMarkings", build_markings, ["paint_white"], smooth_deg=None, recalc=False)
dpart("Dock_HPlate", lambda bm: add_box(bm, (-0.087, -0.03, DECK_Z), (-0.027, 0.03, DECK_Z + 0.001), 0.0005), ["black"], smooth_deg=None)


def build_pad_vent(bm):
    x0, x1, y0, y1, n = 0.050, 0.170, 0.128, 0.198, 12
    g = [[bm.verts.new((x, y, deck_z(x, y) + 0.0008)) for x in np.linspace(x0, x1, n)] for y in np.linspace(y0, y1, 4)]
    for j in range(3):
        for i in range(n - 1):
            bm.faces.new((g[j][i], g[j][i + 1], g[j + 1][i + 1], g[j + 1][i]))
    planar_uv(bm, (0, 1))


dpart("Dock_PadVent", build_pad_vent, ["vent"], smooth_deg=None, recalc=False)

# cabinet face (-Y): electrical cabinet (13), status indicator (12), e-stop, AC-IN, earth wire (14)
CAB = (-0.235, 0.150, 0.085, 0.405)


def build_cabinet(bm):
    add_prism(bm, rrect(CAB[0], CAB[2], CAB[1], CAB[3], 0.025), "XZ", FY - 0.004, FY + 0.002)
    add_box(bm, (-0.060, FY - 0.0055, 0.10), (-0.056, FY - 0.003, 0.37), 0.001)
    for x in np.linspace(CAB[0] + 0.02, CAB[1] - 0.02, 9):
        for z in (CAB[2] + 0.012, CAB[3] - 0.012):
            add_cyl(bm, (x, FY - 0.0045, z), 0.003, 0.002, 8, "Y", mat=1)


dpart("Dock_ElectricalCabinet", build_cabinet, ["white", "metal"], smooth_deg=30)
dpart("Dock_CabinetWindow", lambda bm: add_box(bm, (0.0, FY - 0.009, 0.12), (0.12, FY - 0.004, 0.27), 0.004), ["glass"], smooth_deg=30)


def build_cabinet_vent(bm):
    bm.faces.new([bm.verts.new((x, FY - 0.0046, z)) for x, z in ((CAB[0] + 0.03, 0.375), (CAB[1] - 0.03, 0.375), (CAB[1] - 0.03, 0.392), (CAB[0] + 0.03, 0.392))])
    planar_uv(bm, (0, 2), 0.012)


dpart("Dock_CabinetVent", build_cabinet_vent, ["vent"], smooth_deg=None)
dpart("Dock_EmergencyStop", lambda bm: (add_box(bm, (0.177, FY - 0.026, 0.29), (0.233, FY + 0.002, 0.37), 0.008),
                                        add_cyl(bm, (0.205, FY - 0.031, 0.33), 0.017, 0.010, 32, "Y", mat=1),
                                        add_cyl(bm, (0.205, FY - 0.040, 0.33), 0.023, 0.009, 32, "Y", mat=1, r2=0.020)), ["yellow", "red"])
dpart("Dock_Ports", lambda bm: (add_box(bm, (0.183, FY - 0.012, 0.14), (0.227, FY + 0.002, 0.25), 0.005),
                                add_cyl(bm, (0.205, FY - 0.018, 0.18), 0.012, 0.03, 20, "Y", mat=1),
                                add_cyl(bm, (0.205, FY - 0.022, 0.22), 0.008, 0.024, 16, "Y", mat=1),
                                add_cyl(bm, (0.262, FY - 0.004, 0.090), 0.005, 0.012, 12, "Y", mat=1)), ["black", "metal"])
STATUS_C = Vector((0.0, FY - 0.004, 0.432))
dpart("Dock_StatusIndicator", lambda bm: add_prism(bm, [(-0.026, 0.410), (0.026, 0.410), (0.0, 0.455)], "XZ", FY - 0.010, FY + 0.002), ["led"], smooth_deg=20)


def build_back_screen(bm):
    bm.faces.new([bm.verts.new((x, BY + 0.0006, z)) for x, z in ((0.2, 0.12), (-0.2, 0.12), (-0.2, 0.36), (0.2, 0.36))])
    planar_uv(bm, (0, 2), 0.016)


dpart("Dock_ACDustScreen", build_back_screen, ["vent"], smooth_deg=None)
dpart("Dock_Hinges", lambda bm: [(add_box(bm, (min(sx * (BODY_HX - 0.002), sx * (PIVOT_X + 0.006)), sy * 0.235 - 0.02, PIVOT_Z - 0.03),
                                          (max(sx * (BODY_HX - 0.002), sx * (PIVOT_X + 0.006)), sy * 0.235 + 0.02, PIVOT_Z + 0.02), 0.004),
                                  add_cyl(bm, (sx * PIVOT_X, sy * 0.235, PIVOT_Z), 0.007, 0.05, 16, "Y", mat=1))
                                 for sx in (-1, 1) for sy in (-1, 1)], ["black", "metal"], smooth_deg=30)

# internals (only seen in the X-ray and cut-away modes; positions are free of the rotor sweep)
dpart("Dock_AirConditioner", lambda bm: (add_box(bm, (-0.272, -0.06, 0.08), (-0.168, 0.262, 0.405), 0.01),
                                         [add_box(bm, (-0.170, y - 0.002, 0.10), (-0.164, y + 0.002, 0.39), 0.0) for y in np.linspace(-0.04, 0.245, 16)]),
      ["internal"], smooth_deg=30)
dpart("Dock_PowerUnit", lambda bm: (add_box(bm, (-0.150, 0.236, 0.08), (0.255, 0.264, 0.40), 0.008),
                                    add_box(bm, (-0.120, 0.230, 0.12), (0.040, 0.236, 0.30), 0.003)), ["internal"], smooth_deg=30)
dpart("Dock_CabinetInterior", lambda bm: add_box(bm, (-0.225, -0.266, 0.09), (0.145, -0.240, 0.40), 0.006), ["internal"], smooth_deg=30)

# wireless charging coil under the aircraft (UM p24 note 1); glows while the cover is closed
COIL_C = Vector((-0.075, 0.0, DECK_Z + 0.0009))


def rrect_loop(hx, hy, r, n=5):
    return [Vector((cx + r * math.cos(math.radians(a0 + 90 * i / n)), cy + r * math.sin(math.radians(a0 + 90 * i / n))))
            for cx, cy, a0 in ((hx - r, -hy + r, -90), (hx - r, hy - r, 0), (-hx + r, hy - r, 90), (-hx + r, -hy + r, 180))
            for i in range(n + 1)]


def add_ribbon(bm, pts, w, z):
    n = len(pts)
    outer, inner = [], []
    for i, p in enumerate(pts):
        d = (pts[(i + 1) % n] - pts[i - 1]).normalized()
        nrm = Vector((d.y, -d.x))
        outer.append(bm.verts.new((*(p + nrm * w / 2), z)))
        inner.append(bm.verts.new((*(p - nrm * w / 2), z)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((outer[i], outer[j], inner[j], inner[i]))


def charge_part(name, build):
    ob = dpart(name, build, ["charge"], origin=COIL_C, smooth_deg=None, recalc=False)
    return ob


COIL = charge_part("Dock_ChargeCoil", lambda bm: [add_ribbon(bm, [p + COIL_C.xy for p in rrect_loop(0.070 - k * 0.0085, 0.040 - k * 0.0075, max(0.006, 0.02 - k * 0.004))],
                                                             0.0025, COIL_C.z) for k in range(4)])
FIELD = [charge_part(f"Dock_ChargeField_{k + 1}", lambda bm: add_ribbon(bm, [p + COIL_C.xy for p in rrect_loop(0.070, 0.040, 0.02)], 0.003, COIL_C.z + 0.0004))
         for k in range(3)]

# ============================================================================ 7. cover (item 10)
print("[dock4] cover")


def build_envelope(bm):
    h = LID_TOP - LID_BOT
    vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    bmesh.ops.scale(bm, vec=(2 * LID_HX, 2 * LID_HY, h), verts=vs)
    bmesh.ops.translate(bm, vec=(0, 0, LID_BOT + h / 2), verts=vs)
    low, top = LID_BOT + 1e-6, LID_TOP - 1e-6
    ends = [e for e in bm.edges if all(v.co.z > top for v in e.verts) and abs(e.verts[0].co.x - e.verts[1].co.x) < 1e-6]
    bmesh.ops.bevel(bm, geom=ends, offset=0.055, segments=10, profile=0.5, affect="EDGES", clamp_overlap=True)
    rest = [e for e in bm.edges if not all(v.co.z < low for v in e.verts)
            and len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(50)]
    bmesh.ops.bevel(bm, geom=rest, offset=0.03, segments=6, profile=0.5, affect="EDGES", clamp_overlap=True)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if all(v.co.z < low for v in f.verts)], context="FACES_ONLY")
    for z in (0.44, 0.30):
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=(0, 0, z), plane_no=(0, 0, 1))


cover = part("Dock_Cover", build_envelope, ["white", "lid_in"], C_DOCK, smooth_deg=None)
sol = cover.modifiers.new("shell", "SOLIDIFY")
sol.thickness, sol.offset, sol.use_rim, sol.use_even_offset = LID_T, -1, True, True
sol.material_offset, sol.material_offset_rim = 1, 0
bake(cover)


def notch():
    """The cabinet face shows below the cover; the seam steps up around the status indicator (install manual p53)."""
    r, top = 0.03, 0.425
    pts = [(-0.245, 0.0), (0.245, 0.0)]
    pts += [(0.245 - r + r * math.cos(math.radians(90 * i / 6)), top - r + r * math.sin(math.radians(90 * i / 6))) for i in range(7)]
    pts += [(0.042, top), (0.0, 0.472), (-0.042, top)]
    pts += [(-0.245 + r + r * math.cos(math.radians(90 + 90 * i / 6)), top - r + r * math.sin(math.radians(90 + 90 * i / 6))) for i in range(7)]
    return pts


boolean(cover, [lambda bm: add_prism(bm, notch(), "XZ", -0.36, -0.28),
                lambda bm: add_prism(bm, notch(), "XZ", 0.28, 0.36),
                lambda bm: add_box(bm, (-SEAM, -0.4, 0.05), (SEAM, 0.4, 0.8)),
                lambda bm: [add_box(bm, (min(s * 0.26, s * 0.34), -(LID_HY - LID_T - 0.004), 0.05), (max(s * 0.26, s * 0.34), LID_HY - LID_T - 0.004, PIVOT_Z)) for s in (-1, 1)]])

LIDS, PIV = {}, {}
for side, name in ((1, "Lid_Rear"), (-1, "Lid_Front")):
    bm = bmesh.new()
    bm.from_mesh(cover.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.x * side < 0], context="VERTS")
    PIV[side] = Vector((side * PIVOT_X, 0, PIVOT_Z))
    LIDS[side] = to_object(name, bm, ["white", "lid_in"], C_DOCK, DOCK, PIV[side], smooth_deg=40, recalc=False)
bpy.data.objects.remove(cover, do_unlink=True)


def lpart(side, name, build, mats, **kw):
    return part(name, build, mats, C_DOCK, LIDS[side], origin=PIV[side], local_origin=PIV[side], **kw)


# environment sensors on the -X half (UM p24 items 1-3, 9)
GX, GY = -0.258, 0.0
ROTOR_Z = LID_TOP + GAUGE_H - 0.0125
lpart(-1, "Lid_Front_WindGauge", lambda bm: (add_cyl(bm, (GX, GY, LID_TOP - 0.004), 0.030, 0.012, 32),
                                              add_cyl(bm, (GX, GY, LID_TOP + 0.048), 0.016, 0.092, 24),
                                              add_cyl(bm, (GX, GY, LID_TOP + 0.102), 0.011, 0.018, 20)), ["white"])


def build_wind_rotor(bm):
    for i in range(3):
        a = 2 * math.pi * i / 3
        tip = Vector((GX + 0.030 * math.cos(a), GY + 0.030 * math.sin(a), ROTOR_Z))
        add_beam(bm, (GX, GY, ROTOR_Z), tip, 0.004, 0.004, 0.004, 0.004, bevel=0)
        add_sphere(bm, tip, 0.0125, segs=16)
    add_cyl(bm, (GX, GY, LID_TOP + 0.123), 0.006, 0.014, 12)


part("Lid_Front_WindRotor", build_wind_rotor, ["white"], C_DOCK, LIDS[-1], origin=(GX, GY, ROTOR_Z), local_origin=PIV[-1])
lpart(-1, "Lid_Front_RainGauge", lambda bm: (add_cyl(bm, (-0.255, -0.115, LID_TOP - 0.002), 0.038, 0.010, 40),
                                              add_cyl(bm, (-0.255, -0.115, LID_TOP + 0.0035), 0.032, 0.002, 40, mat=1)), ["white", "black"])
lpart(-1, "Lid_Front_DockCamera", lambda bm: (add_box(bm, (-0.29, 0.085, LID_TOP - 0.004), (-0.235, 0.135, LID_TOP + 0.022), 0.006),
                                               add_cyl(bm, (-0.292, 0.110, LID_TOP + 0.010), 0.010, 0.004, 20, "X", mat=1)), ["black", "glass"])
lpart(-1, "Lid_Front_AuxLight", lambda bm: add_box(bm, (-0.292, 0.140, LID_TOP + 0.002), (-0.282, 0.160, LID_TOP + 0.016), 0.002), ["led"])
# push blocks and propeller bumpers on the inside of both halves (maintenance manual p14)
XI = LID_HX - LID_T
lpart(-1, "Lid_Front_PushBlocks", lambda bm: [add_box(bm, (-XI, sy * 0.2115 - 0.02, 0.588), (-0.268, sy * 0.2115 + 0.02, 0.612), 0.004) for sy in (-1, 1)], ["black"])
lpart(1, "Lid_Rear_PushBlocks", lambda bm: [add_box(bm, (0.142, sy * 0.1955 - 0.016, 0.615), (XI, sy * 0.1955 + 0.016, 0.640), 0.004) for sy in (-1, 1)], ["black"])
lpart(-1, "Lid_Front_HMarker", lambda bm: [bm.faces.new([bm.verts.new((x, y, LID_TOP - LID_T - 0.0006)) for x, y in ((x0, y0), (x0, y1), (x1, y1), (x1, y0))])
                                            for x0, x1, y0, y1 in ((-0.16, -0.10, -0.045, -0.03), (-0.16, -0.10, 0.03, 0.045), (-0.137, -0.123, -0.03, 0.03))],
      ["paint_white"], smooth_deg=None, recalc=False)

# ============================================================================ 8. battery swapping module (item 8)
print("[dock4] swap module")
SLEEVE_W, SLEEVE_H, WALL = BAT_W + 0.008, BAT_H + 0.008, 0.004
CAGE_X0, CAGE_X1 = REAR_IN - BAT_L - 0.006, REAR_IN + 0.004


def sleeve(bm):
    """One compartment at 12 o'clock: a rectangular tube around a battery, contact end, ribs to the shell."""
    cz = ZA + R_SWAP
    hw, hh = SLEEVE_W / 2, SLEEVE_H / 2
    for (y0, y1, z0, z1) in ((-hw - WALL, hw + WALL, cz - hh - WALL, cz - hh), (-hw - WALL, hw + WALL, cz + hh, cz + hh + WALL),
                             (-hw - WALL, -hw, cz - hh, cz + hh), (hw, hw + WALL, cz - hh, cz + hh)):
        add_box(bm, (CAGE_X0, y0, z0), (CAGE_X1, y1, z1), 0.0012, 1)
    add_box(bm, (CAGE_X0 - 0.008, -hw - WALL, cz - hh - WALL), (CAGE_X0, hw + WALL, cz + hh + WALL), 0.002, 1)   # contact end
    for dy in (-0.022, 0.022):                                                                                  # ribs to the shell
        add_box(bm, (CAGE_X0, dy - 0.003, cz + hh + WALL), (CAGE_X1, dy + 0.003, ZA + 0.232))


def build_cage(bm):
    for ang in COMPARTMENTS.values():
        rotated(bm, math.radians(ang), sleeve)
    half = 0.232 * math.tan(math.radians(5))
    for k in range(21):                                              # C-shaped polygonal shell, 30..240 deg
        rotated(bm, math.radians(35 + 10 * k), lambda t: add_box(t, (CAGE_X0 - 0.008, -half, ZA + 0.228), (CAGE_X1, half, ZA + 0.234)))
    for x0, x1, rin in ((CAGE_X0 - 0.014, CAGE_X0 - 0.008, 0.045), (CAGE_X1, CAGE_X1 + 0.004, 0.214)):   # end rings
        for k in range(21):
            rotated(bm, math.radians(35 + 10 * k), lambda t, x0=x0, x1=x1, rin=rin: add_box(t, (x0, -0.0215, ZA + rin), (x1, 0.0215, ZA + 0.234)))
    add_cyl(bm, (CAGE_X0 - 0.018, 0, ZA), 0.036, 0.010, 32, "X")    # front bearing boss


dpart("Swap_CompartmentCage", build_cage, ["cage"], coll=C_SWAP, smooth_deg=30)


def build_contacts(bm):
    for ang in COMPARTMENTS.values():
        rotated(bm, math.radians(ang), lambda t: [add_box(t, (CAGE_X0 - 0.0005, dy - 0.003, ZA + R_SWAP - 0.006), (CAGE_X0 + 0.004, dy + 0.003, ZA + R_SWAP + 0.006))
                                                   for dy in (-0.02, -0.007, 0.007, 0.02)])


dpart("Swap_ChargingContacts", build_contacts, ["brass"], coll=C_SWAP, smooth_deg=None)
FLANGE_X = CRADLE_X1 + 0.011                                         # 0.263
dpart("Swap_DriveHousing", lambda bm: (add_cyl(bm, (0.275, 0, ZA), 0.070, 0.013, 40, "X"),
                                       add_box(bm, (0.268, -0.05, ZA - 0.16), (0.2815, 0.05, ZA - 0.07), 0.006),
                                       add_box(bm, (0.262, -0.09, BRACKET_H + 0.005), (0.2815, 0.09, BRACKET_H + 0.02), 0.004)),
      ["rotor"], coll=C_SWAP, smooth_deg=35)

# rotor: built with the cradle at 12 o'clock; its hatch plate sits opposite and closes the pad at home (180 deg)
RC = Vector((0.0, 0.0, ZA))
CZ = ZA + R_SWAP
C_IN_W, C_IN_H = BAT_W + 0.006, BAT_H + 0.006
C_FLOOR = CZ - C_IN_H / 2
C_TOP = CZ + C_IN_H / 2
SCREW_Z = C_FLOOR - 0.014


def build_rotor(bm):
    add_cyl(bm, (FLANGE_X, 0, ZA), 0.065, 0.010, 48, "X")                                      # bolted flange
    for k in range(6):
        a = 2 * math.pi * k / 6
        add_cyl(bm, (FLANGE_X - 0.0055, 0.048 * math.cos(a), ZA + 0.048 * math.sin(a)), 0.0045, 0.003, 12, "X", mat=4)
    add_cyl(bm, ((CAGE_X0 - 0.018 + FLANGE_X) / 2, 0, ZA), 0.028, FLANGE_X - CAGE_X0 + 0.018, 32, "X")  # central tube
    add_box(bm, (CRADLE_X1, -0.03, ZA + 0.02), (CRADLE_X1 + 0.006, 0.03, C_TOP + 0.004), 0.003)  # arm to the cradle
    add_box(bm, (CRADLE_X0, -C_IN_W / 2 - 0.005, C_FLOOR - 0.024), (CRADLE_X1, C_IN_W / 2 + 0.005, C_FLOOR), 0.003)   # floor + screw bay
    for s in (-1, 1):                                                                            # side walls
        add_box(bm, (CRADLE_X0 + 0.012, min(s * C_IN_W / 2, s * (C_IN_W / 2 + 0.005)), C_FLOOR),
                (CRADLE_X1, max(s * C_IN_W / 2, s * (C_IN_W / 2 + 0.005)), C_TOP), 0.002)
    add_box(bm, (CRADLE_X0 + 0.012, -C_IN_W / 2 - 0.005, C_TOP), (CRADLE_X1, C_IN_W / 2 + 0.005, C_TOP + 0.007), 0.003)   # top plate
    add_box(bm, (CRADLE_X1 - 0.006, -C_IN_W / 2 - 0.005, C_FLOOR - 0.024), (CRADLE_X1, C_IN_W / 2 + 0.005, C_TOP + 0.007), 0.002)  # rear wall
    add_box(bm, (CRADLE_X0 + 0.04, -C_IN_W / 2 - 0.004, C_TOP + 0.0068), (CRADLE_X1 - 0.03, C_IN_W / 2 + 0.004, C_TOP + 0.0078), 0.0, mat=1)  # label
    for s in (-1, 1):                                                                            # U-shaped guide fingers at the mouth
        add_box(bm, (CRADLE_X0, min(s * (C_IN_W / 2 - 0.004), s * (C_IN_W / 2 + 0.007)), C_FLOOR - 0.004),
                (CRADLE_X0 + 0.014, max(s * (C_IN_W / 2 - 0.004), s * (C_IN_W / 2 + 0.007)), C_TOP + 0.004), 0.003, mat=2)
    # hatch plate opposite the cradle: flush with the channel floor (z 440 mm) when the rotor is home
    py0, py1 = -HATCH[3] + 0.002, -HATCH[2] - 0.002
    zp = ZA - (DECK_Z - ZA)
    add_box(bm, (HATCH[0] + 0.002, py0, zp), (HATCH[1] - 0.002, py1, zp + 0.006), 0.002, mat=3)
    add_box(bm, (CRADLE_X1, -0.03, zp + 0.006), (CRADLE_X1 + 0.006, 0.03, ZA - 0.02), 0.003)     # arm to the plate
    for x in (0.095, 0.155, 0.215):                                                              # three oval recesses (UM p24 item 8)
        vs = add_cyl(bm, (x, 0.0, zp - 0.0004), 0.016, 0.0012, 24, mat=4)
        for v in vs:
            v.co.x = x + (v.co.x - x) * 1.45
    add_box(bm, (HATCH[0] + 0.002, py0, zp + 0.006), (HATCH[1] - 0.002, py0 + 0.006, zp + 0.03), 0.002)
    add_box(bm, (HATCH[0] + 0.002, py1 - 0.006, zp + 0.006), (HATCH[1] - 0.002, py1, zp + 0.03), 0.002)
    uv = bm.loops.layers.uv.verify()
    lx0, lx1, ly0, ly1 = CRADLE_X0 + 0.04, CRADLE_X1 - 0.03, -C_IN_W / 2 - 0.004, C_IN_W / 2 + 0.004
    for f in bm.faces:
        if f.material_index == 1:
            for lp in f.loops:
                lp[uv].uv = ((lp.vert.co.x - lx0) / (lx1 - lx0), (lp.vert.co.y - ly0) / (ly1 - ly0))


ROTOR = dpart("Swap_Rotor", build_rotor, ["rotor", "label", "guide", "deck", "black"], coll=C_SWAP, origin=RC, smooth_deg=30)


def build_screw(bm):
    """Lead screw: a helical thread, so its turning shows."""
    r, n_per = 0.0055, 24
    turns = (CRADLE_X1 - 0.010 - (CRADLE_X0 + 0.006)) / SCREW_PITCH
    rings = []
    for k in range(int(turns * n_per) + 1):
        t = 2 * math.pi * k / n_per
        x = CRADLE_X0 + 0.006 + SCREW_PITCH * t / (2 * math.pi)
        c, s = math.cos(t), math.sin(t)
        rings.append([bm.verts.new((x + dx, (r + dr) * c, SCREW_Z + (r + dr) * s)) for dx, dr in ((-0.0012, 0), (0.0012, 0), (0.0, 0.0018))])
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(3):
            bm.faces.new((r0[i], r0[(i + 1) % 3], r1[(i + 1) % 3], r1[i]))
    add_cyl(bm, ((CRADLE_X0 + CRADLE_X1) / 2, 0, SCREW_Z), 0.0048, CRADLE_X1 - CRADLE_X0 - 0.010, 16, "X")


SCREW = part("Swap_LeadScrew", build_screw, ["steel"], C_SWAP, ROTOR, origin=(0, 0, SCREW_Z), local_origin=RC, smooth_deg=50)


def build_hook(bm):
    hx = HOOK_HOME
    add_box(bm, (hx - 0.002, -0.017, SCREW_Z - 0.011), (hx + 0.012, 0.017, SCREW_Z + 0.011), 0.003)        # ball nut carriage
    for dy in (-0.012, 0.012):                                                                            # two prongs up through the floor slot
        add_box(bm, (hx, dy - 0.003, SCREW_Z), (hx + 0.008, dy + 0.003, CZ - 0.014), 0.0015, mat=1)
        add_box(bm, (hx - 0.005, dy - 0.003, CZ - 0.020), (hx + 0.008, dy + 0.003, CZ - 0.014), 0.0015, mat=1)  # lip over the handle bar


HOOK = part("Swap_Hook", build_hook, ["rotor", "steel"], C_SWAP, ROTOR, origin=(HOOK_HOME, 0, ZA), local_origin=RC, smooth_deg=30)

# ============================================================================ 9. batteries
print("[dock4] batteries")


def build_battery(bm):
    hl, hw, hh = BAT_L / 2, BAT_W / 2, BAT_H / 2
    add_box(bm, (-hl, -hw, -hh), (hl - 0.004, hw, hh), 0.007, 3)
    add_box(bm, (hl - 0.006, -hw + 0.002, -hh + 0.002), (hl, hw - 0.002, hh - 0.002), 0.004, 3)            # rear cap
    for y in (-0.03, -0.01, 0.01, 0.03):                                                                    # grip ribs on the top
        add_box(bm, (-hl + 0.03, y - 0.002, hh - 0.001), (hl - 0.03, y + 0.002, hh + 0.0015), 0.0008, 1)
    add_box(bm, (hl - 0.001, -0.028, 0.004), (hl + 0.0008, 0.028, 0.024), 0.0015, 1, mat=1)                 # LED window
    add_cyl(bm, (hl + 0.0002, 0.036, 0.014), 0.004, 0.002, 16, "X", mat=1)                                  # power button
    for dy in (-0.024, 0.024):                                                                              # U-shaped handle
        add_box(bm, (hl - 0.001, dy - 0.003, -0.026), (hl + HANDLE, dy + 0.003, -0.018), 0.001)
    add_box(bm, (hl + HANDLE - 0.003, -0.027, -0.026), (hl + HANDLE, 0.027, -0.018), 0.001)
    for dy in (-0.02, -0.007, 0.007, 0.02):                                                                 # front contacts
        add_box(bm, (-hl - 0.0015, dy - 0.003, -0.006), (-hl + 0.001, dy + 0.003, 0.006), 0.0, mat=2)


BATT, BATT_LEDS = {}, {}
for b in BATTERIES:
    ob = part(f"Batt_{b}", build_battery, ["batt", "batt_dark", "brass"], C_BATT, smooth_deg=35)
    BATT[b] = ob
    BATT_LEDS[b] = []
    for i, y in enumerate((-0.018, -0.006, 0.006, 0.018)):
        led = part(f"Batt_{b}_LED_{i + 1}", lambda bm: add_box(bm, (-0.0006, -0.004, -0.002), (0.0009, 0.004, 0.002), 0.0005), ["led_batt"], C_BATT, ob, smooth_deg=30)
        led.location = (BAT_L / 2 + 0.0008, y, 0.014)
        BATT_LEDS[b].append(led)

# ============================================================================ 10. Matrice 5TD
print("[dock4] aircraft")
AC = empty("M5TD", C_AC, None, AC_REST, 0.1)


def apart(name, build, mats, parent=None, **kw):
    ob = part(name, build, mats, C_AC, parent or AC, **kw)
    ob.location = (0, 0, 0)
    return ob


# fuselage stations measured from DJI's vertex points (|cx| < 62 mm, 10 mm slices; research/../official)
FUSELAGE = [(0.1735, 0.050, -0.032, 0.078, 2.6), (0.168, 0.055, -0.037, 0.085, 3.0), (0.150, 0.057, -0.039, 0.090, 3.2),
            (0.120, 0.053, -0.040, 0.095, 3.2), (0.080, 0.050, -0.038, 0.099, 3.2), (0.040, 0.051, -0.038, 0.104, 3.2),
            (0.000, 0.055, -0.039, 0.110, 3.2), (-0.028, 0.054, -0.032, 0.111, 3.0), (-0.036, 0.050, 0.040, 0.110, 2.8),
            (-0.060, 0.047, 0.050, 0.106, 2.8), (-0.078, 0.043, 0.056, 0.099, 2.6), (-0.090, 0.035, 0.061, 0.088, 2.4),
            (-0.096, 0.022, 0.066, 0.077, 2.2)]
fus = apart("M5TD_Fuselage", lambda bm: add_loft(bm, FUSELAGE, n=36), ["ac"], smooth_deg=60)
boolean(fus, [lambda bm: add_box(bm, (BATT_LOCAL.x - BAT_L / 2 - 0.003, -BAT_W / 2 - 0.0015, -BAT_H / 2 - 0.0015), (0.20, BAT_W / 2 + 0.0015, BAT_H / 2 + 0.0015))])
apart("M5TD_BayLining", lambda bm: add_box(bm, (BATT_LOCAL.x - BAT_L / 2 - 0.004, -BAT_W / 2 - 0.0015, -BAT_H / 2 - 0.0015),
                                           (BATT_LOCAL.x - BAT_L / 2 - 0.003, BAT_W / 2 + 0.0015, BAT_H / 2 + 0.0015)), ["ac_dark"], smooth_deg=None)


def build_rear_vent(bm):
    bm.faces.new([bm.verts.new((0.1745, y, z)) for y, z in ((-0.036, 0.042), (-0.036, 0.070), (0.036, 0.070), (0.036, 0.042))])
    planar_uv(bm, (1, 2), 0.010)


apart("M5TD_RearVent", build_rear_vent, [material("M5TD_Vent", (0.2, 0.2, 0.21), 0.55, 0.4, image=TEX_SLOTS)], smooth_deg=None)


def build_arms(bm):
    for k, (mx, my, z0, z1, r, _) in MOTORS.items():
        s = 1 if my > 0 else -1
        root = (-0.002, s * 0.048, 0.076) if mx < 0 else (0.150, s * 0.048, 0.058)
        add_beam(bm, root, (mx, my, z0 - 0.004), 0.028, 0.024, 0.022, 0.018, bevel=0.006, segs=3)
        add_cyl(bm, (mx, my, z0 - 0.010), r - 0.003, 0.024, 36)
        add_sphere(bm, (mx, my, z0 - 0.022), r - 0.003, (1, 1, 0.5), segs=24)


apart("M5TD_Arms", build_arms, ["ac"])
apart("M5TD_Motors", lambda bm: [add_cyl(bm, (mx, my, (z0 + z1) / 2), r, z1 - z0, 36) for mx, my, z0, z1, r, _ in MOTORS.values()], ["ac_dark"])
GIM = (-0.100, -0.038, -0.039, 0.039, -0.012, 0.052)                 # lx0, lx1, ly0, ly1, lz0, lz1


def build_gimbal(bm):
    add_box(bm, (GIM[0], GIM[2], GIM[4]), (GIM[1], GIM[3], GIM[5]), 0.012)
    for s in (-1, 1):
        add_box(bm, (GIM[1] - 0.012, s * 0.041 - 0.003, 0.0), (GIM[1] + 0.004, s * 0.041 + 0.003, 0.05), 0.002)
    add_box(bm, (-0.042, -0.044, 0.040), (-0.028, 0.044, 0.050), 0.003)
    add_cyl(bm, (-0.034, 0, 0.046), 0.018, 0.012, 24)


apart("M5TD_Gimbal", build_gimbal, ["ac_dark"])
LENSES = [(0.020, 0.036, 0.011), (-0.017, 0.041, 0.006), (-0.031, 0.041, 0.004), (0.020, 0.008, 0.012), (-0.019, 0.022, 0.010), (-0.019, -0.002, 0.008)]
apart("M5TD_Lenses", lambda bm: [add_cyl(bm, (GIM[0] - 0.001, y, z), r, 0.004, 32, "X") for y, z, r in LENSES], ["glass"])
apart("M5TD_LiDAR", lambda bm: (add_cyl(bm, (-0.062, 0, 0.125), 0.030, 0.050, 40), add_sphere(bm, (-0.062, 0, 0.170), 0.029, (1, 1, 0.55), segs=32)), ["ac_dark"])
apart("M5TD_LiDARWindow", lambda bm: add_cyl(bm, (-0.062, 0, 0.160), 0.0305, 0.018, 40), ["lidar"])
apart("M5TD_RTKBeacon", lambda bm: (add_cyl(bm, (0.122, 0, 0.100), 0.022, 0.030, 32), add_sphere(bm, (0.122, 0, 0.115), 0.021, (1, 1, 0.4), segs=24),
                                    add_box(bm, (0.090, -0.008, 0.096), (0.102, 0.008, 0.112), 0.002, mat=1)), ["ac", "led_red"])
apart("M5TD_Feet", lambda bm: [add_box(bm, (x - 0.012, s * 0.036 - 0.009, AC_FOOT), (x + 0.012, s * 0.036 + 0.009, -0.034), 0.003) for x in (-0.012, 0.150) for s in (-1, 1)], ["ac_dark"])
apart("M5TD_VisionSensors", lambda bm: ([add_cyl(bm, (-0.088, s * 0.022, 0.078), 0.006, 0.004, 20, "X") for s in (-1, 1)]
                                        + [add_cyl(bm, (0.04, s * 0.052, 0.07), 0.006, 0.004, 20, "Y") for s in (-1, 1)]
                                        + [add_cyl(bm, (0.1755, s * 0.044, -0.022), 0.005, 0.004, 20, "X") for s in (-1, 1)]), ["glass"])
apart("M5TD_FrontLEDs", lambda bm: [add_cyl(bm, (mx, my, z0 - 0.034), 0.007, 0.003, 16, mat=0 if my > 0 else 1) for k, (mx, my, z0, z1, r, _) in MOTORS.items() if mx < 0],
      ["led_red", "led_green"])
AC_LOWEST = AC_FOOT


def blade(bm, mirror):
    st, n = 20, 6
    rings = []
    for i in range(st):
        u = i / (st - 1)
        r = 0.012 + u * (PROP_R - 0.012)
        c = 0.017 + 0.015 * min(1, u / 0.3) - 0.02 * max(0, (u - 0.3) / 0.7)
        t = 0.0042 * (1 - 0.6 * u)
        tw = math.radians(20 - 12 * u)
        ring = []
        for cc, tt in ((0.5, 0), (0.18, 0.5), (-0.2, 0.38), (-0.5, 0), (-0.2, -0.22), (0.18, -0.36)):
            y = cc * c * math.cos(tw) - tt * t * math.sin(tw)
            z = cc * c * math.sin(tw) + tt * t * math.cos(tw)
            ring.append(bm.verts.new((r, -y if mirror else y, z)))
        rings.append(ring)
    for i in range(st - 1):
        for k in range(n):
            q = (rings[i][k], rings[i][(k + 1) % n], rings[i + 1][(k + 1) % n], rings[i + 1][k])
            bm.faces.new(q if not mirror else q[::-1]).material_index = 1 if i >= st - 3 else 0
    bm.faces.new(rings[0][::-1] if not mirror else rings[0])
    bm.faces.new(rings[-1] if not mirror else rings[-1][::-1]).material_index = 1


PROPS = {}
for key, (mx, my, z0, z1, r, spin) in MOTORS.items():
    hub = apart(f"M5TD_Prop_{key}", lambda bm: (add_cyl(bm, (0, 0, 0.005), 0.013, 0.01, 24), add_sphere(bm, (0, 0, 0.01), 0.010, (1, 1, 0.5), segs=16)), ["ac_dark"])
    hub.location = (mx, my, z1)
    blades = [apart(f"M5TD_Prop_{key}_{b}", lambda bm: blade(bm, spin < 0), ["prop", "prop_tip"], parent=hub, smooth_deg=50, recalc=False) for b in "AB"]
    for bl in blades:
        bl.location = (0, 0, 0.006)
    PROPS[key] = (hub, blades, math.atan2(-my, BATT_LOCAL.x - mx), spin)       # parked blades point toward the battery centre

# ============================================================================ 11. site
part("Site_ConcreteBase", lambda bm: add_box(bm, (-0.35, -0.35, -0.2), (0.35, 0.35, 0), 0.006), ["concrete"], C_SITE, smooth_deg=30)

# ============================================================================ 12. callouts
LF, LR = LIDS[-1], LIDS[1]
for num, label, parent, pos in [
    (1, "Wind Speed Gauge", LF, (GX, GY, LID_TOP + GAUGE_H)), (2, "Dock Camera", LF, (-0.292, 0.110, LID_TOP + 0.010)),
    (3, "Camera Auxiliary Light", LF, (-0.287, 0.150, LID_TOP + 0.016)), (4, "Illuminated Positioning Markers", DOCK, (0.24, 0.255, DECK_Z + 0.002)),
    (5, "Aircraft Front Orientation Marker", DOCK, (-0.19, 0.0, DECK_Z + 0.002)), (6, "Landing Pad (wireless charging)", DOCK, (-0.06, 0.16, deck_z(-0.06, 0.16) + 0.002)),
    (7, "Drain Pipe Hole (underneath)", DOCK, (0.0, 0.1, BRACKET_H)), (8, "Battery Swapping Module (hatch)", DOCK, (0.145, -0.06, DECK_Z + 0.002)),
    (9, "Rainfall Gauge", LF, (-0.255, -0.115, LID_TOP + 0.005)), (10, "Dock Cover", LR, (LID_HX, 0.0, 0.40)),
    (11, "Mounting Base Brackets", DOCK, (0.24, -FOOT_HY, 0.04)), (12, "Dock Status Indicator", DOCK, (0.0, FY - 0.01, 0.435)),
    (13, "Electrical Cabinet", DOCK, (-0.12, FY - 0.004, 0.24)), (14, "Earth Wire", DOCK, (0.262, FY - 0.01, 0.09)),
]:
    hotspot(num, label, parent, pos, C_DOCK, origin=PIV[1] if parent is LR else PIV[-1] if parent is LF else (0, 0, 0))
for num, label, parent, pos in [
    ("S1", "Battery compartments A–D (C-shaped cage)", DOCK, (CAGE_X1, -0.235 * math.sin(math.radians(95)), ZA + 0.235 * math.cos(math.radians(95)))),
    ("S2", "Rotor drive and flange", ROTOR, (0.26, 0.0, ZA + 0.065)), ("S3", "Lead screw", ROTOR, (0.15, 0.0, SCREW_Z)),
    ("S4", "Hook (grips the battery handle)", HOOK, (HOOK_HOME, 0.0, CZ - 0.017)), ("S5", "Cradle", ROTOR, (0.15, 0.0, C_TOP + 0.008)),
    ("S6", "Charging contacts", DOCK, (CAGE_X0, -R_SWAP * math.sin(math.radians(45)), ZA + R_SWAP * math.cos(math.radians(45)))),
    ("S7", "Hatch plate (flush when home)", ROTOR, (0.145, 0.0, ZA - (DECK_Z - ZA))),
]:
    origin = RC if parent is ROTOR else Vector((HOOK_HOME, 0, ZA)) if parent is HOOK else (0, 0, 0)
    hotspot(num, label, parent, pos, C_SWAP, group="swap", origin=origin)
for num, label, pos in (("A1", "Integrated Gimbal Camera", (GIM[0], 0.0, 0.02)), ("A2", "Motor", (MOTORS["FR"][0], MOTORS["FR"][1], MOTORS["FR"][3])),
                        ("A3", "Front LEDs", (MOTORS["FL"][0], MOTORS["FL"][1], MOTORS["FL"][2] - 0.035)), ("A4", "Propellers (1564F, 15 in)", (MOTORS["RL"][0], MOTORS["RL"][1], MOTORS["RL"][3] + 0.012)),
                        ("A6", "Frame Arm (internal antennas)", (0.2, 0.15, 0.10)), ("A11", "LiDAR", (-0.062, 0.0, 0.186)), ("A13", "Beacon", (0.096, 0.0, 0.112)),
                        ("A14", "Intelligent Flight Battery (tail)", (0.1745, 0.0, 0.0)), ("A15", "Battery Level LEDs", (0.1745, 0.0, 0.014))):
    hotspot(num, label, AC, pos, C_AC, group="aircraft")

# ============================================================================ 13. animation (baked per frame)
print("[dock4] animation")
frames = list(range(F["end"] + 1))


def lid_theta(f):
    return math.pi / 2 * (1 - ramp(f, F["close0"], F["close1"]) + ramp(f, F["open0"], F["open1"]))


for f in frames:
    th = lid_theta(f)
    lag = max(0.0, (th / (math.pi / 2) - 0.5) / 0.5) ** 2
    for side in (1, -1):
        lid = LIDS[side]
        lid.location = Vector((side * (PIVOT_X + LID_DX * lag), 0, PIVOT_Z + LID_DZ * lag))
        lid.rotation_euler = Euler((0, side * th, 0))
        lid.keyframe_insert("location", frame=f)
        lid.keyframe_insert("rotation_euler", frame=f)

REST = AC_REST.copy()


def ac_pose(f):
    if f < F["land1"]:
        u = ramp(f, F["land0"], F["land1"])
        return REST + Vector((0, 0, 1.1 * (1 - u))), 0.35 * (1 - u)
    if f >= F["up0"]:
        u = (f - F["up0"]) / (F["end"] - F["up0"])
        return REST + Vector((0, 0, 1.4 * u * u)), 0.0
    return REST.copy(), 0.0


AC_MW = {}
for f in frames:
    p, yaw = ac_pose(f)
    AC.location, AC.rotation_euler = p, Euler((0, 0, yaw))
    AC.keyframe_insert("location", frame=f)
    AC.keyframe_insert("rotation_euler", frame=f)
    AC_MW[f] = Matrix.Translation(p) @ Euler((0, 0, yaw)).to_matrix().to_4x4()

SPIN_STOP = F["stop0"] + 22
w = np.array([OMEGA if f < F["stop0"] else OMEGA * (1 - ramp(f, F["stop0"], SPIN_STOP)) if f < SPIN_STOP else 0.0 if f < F["spin0"]
              else OMEGA * ramp(f, F["spin0"], F["spin0"] + 30) for f in frames])
acc = np.cumsum(w)
park = int(np.searchsorted(frames, SPIN_STOP))
extra = math.ceil(acc[park] / (2 * math.pi)) * 2 * math.pi - acc[park]   # stop exactly at the parked angle
decel = np.where((np.array(frames) >= F["stop0"]) & (np.array(frames) < SPIN_STOP), w, 0.0)
acc = acc + np.cumsum(decel / decel.sum() * extra)
for hub, blades, h0, spin in PROPS.values():
    for i, f in enumerate(frames):
        hub.rotation_euler = (0, 0, h0 + spin * acc[i])
        hub.keyframe_insert("rotation_euler", frame=f)
        deployed = (1 - ramp(f, SPIN_STOP, F["stop1"])) if f < F["spin0"] else ramp(f, F["spin0"], F["spin0"] + 8)
        a = FOLD + (math.pi / 2 - FOLD) * deployed
        blades[0].rotation_euler, blades[1].rotation_euler = (0, 0, a), (0, 0, -a)
        for bl in blades:
            bl.keyframe_insert("rotation_euler", frame=f)


def slot_matrix(ang, rear):
    """Battery pose on the transfer circle at angle `ang` (rad), rear face at x = rear."""
    return (Matrix.Translation((rear - BAT_L / 2, -R_SWAP * math.sin(ang), ZA + R_SWAP * math.cos(ang)))
            @ Matrix.Rotation(ang, 4, "X"))


for f in frames:
    th = theta(f)
    ROTOR.rotation_euler = (th, 0, 0)
    ROTOR.keyframe_insert("rotation_euler", frame=f)
    hx = hook_x(f)
    HOOK.location = (hx, 0, 0.008 * hook_lift(f))
    HOOK.keyframe_insert("location", frame=f)
    SCREW.rotation_euler = (2 * math.pi * (hx - HOOK_HOME) / SCREW_PITCH, 0, 0)
    SCREW.keyframe_insert("rotation_euler", frame=f)
    for b, ob in BATT.items():
        pl = place(b, f)
        if pl == "ac":
            mw = AC_MW[f] @ Matrix.Translation(BATT_LOCAL)
        elif pl == "cradle":
            mw = slot_matrix(th, hx - HANDLE)
        else:
            mw = slot_matrix(math.radians(COMPARTMENTS[pl]), REAR_IN)
        loc, rot, _ = mw.decompose()
        ob.location, ob.rotation_euler = loc, rot.to_euler("XYZ")
        ob.keyframe_insert("location", frame=f)
        ob.keyframe_insert("rotation_euler", frame=f)
        cfg = BATTERIES[b]
        charging = cfg["charge_from"] is not None and f >= cfg["charge_from"]
        for led, lit in zip(BATT_LEDS[b], battery_leds(cfg["level"], f, charging)):
            led.scale = (1, 1, 1) if lit else (0, 0, 0)
            led.keyframe_insert("scale", frame=f)
    closed = F["close1"] <= f < F["open0"]
    on = ramp(f, F["close1"], F["close1"] + 10) * (1 - ramp(f, F["open0"] - 10, F["open0"]))
    COIL.scale = (on,) * 3 if on > 1e-4 else (0, 0, 0)
    COIL.keyframe_insert("scale", frame=f)
    for k, ring in enumerate(FIELD):
        p = ((f - F["close1"]) / 30.0 + k / 3.0) % 1.0
        ring.scale = (1 + 1.6 * p, 1 + 1.6 * p * 0.57, 1) if closed and on > 1e-4 else (0, 0, 0)
        ring.keyframe_insert("scale", frame=f)

markers = {"Landing": F["land0"], "Cover closing": F["close0"], "Swap": F["swap0"], "Cover opening": F["open0"], "Take-off": F["up0"], "End": F["end"]}
for name, f in markers.items():
    scene.timeline_markers.new(name, frame=f)
TIMELINE = {"fps": FPS, "frames": F, "markers": markers, "phases": [{"label": l, "f0": a, "f1": b} for l, a, b in PHASES],
            "steps": [{"key": k, "f0": a, "f1": b, "label": l, "detail": d} for k, a, b, l, d in STEPS],
            "batteries": BATTERIES, "compartments": COMPARTMENTS, "theta_keys": THETA_KEYS}

# ============================================================================ 14. validation (+/-1 mm)


def envelope(objs, frame):
    scene.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = np.full(3, 1e9), np.full(3, -1e9)
    for ob in objs:
        if ob.type != "MESH":
            continue
        ev = ob.evaluated_get(dg)
        if not len(ev.data.vertices) or min(ev.matrix_world.to_scale()) < 1e-6:
            continue
        co = np.empty(len(ev.data.vertices) * 3)
        ev.data.vertices.foreach_get("co", co)
        mw = np.array(ev.matrix_world)
        pts = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
        lo, hi = np.minimum(lo, pts.min(0)), np.maximum(hi, pts.max(0))
    return (hi - lo) * 1000, lo, hi


dock_objs = list(C_DOCK.all_objects) + list(C_SWAP.all_objects)
ac_objs = [o for o in C_AC.all_objects if not o.name.startswith("M5TD_Prop")]
report, failed = {}, []
for label, objs, frame, spec in (("closed", dock_objs, 600, SPEC["closed_mm"]), ("open", dock_objs, 0, SPEC["open_mm"])):
    size, lo, hi = envelope(objs, frame)
    ok = all(abs(a - b) <= TOL_MM for a, b in zip(size, spec))
    report[label] = {"model_mm": [round(float(v), 1) for v in size], "spec_mm": spec, "ok": bool(ok)}
    print(f"[dock4]   {label} bounds x {lo[0] * 1000:.1f}..{hi[0] * 1000:.1f}  y {lo[1] * 1000:.1f}..{hi[1] * 1000:.1f}  z {lo[2] * 1000:.1f}..{hi[2] * 1000:.1f}")
    failed += [] if ok else [label]
    print(f"[dock4] {label:8s} L x W x H = {size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm  (spec {spec[0]} x {spec[1]} x {spec[2]})  "
          f"{'OK' if ok else 'OUT OF TOLERANCE'} (+/-{TOL_MM:g} mm)")
size, lo, hi = envelope(ac_objs, 600)
report["aircraft"] = {"model_mm": [round(float(v), 1) for v in size], "spec_mm": SPEC["aircraft_mm"], "spec_page_mm": SPEC["aircraft_mm_spec_page"],
                      "source": "fitted to DJI's STEP vertex points", "ok": bool(abs(size[0] - SPEC["aircraft_mm"][0]) <= 5 and abs(size[2] - SPEC["aircraft_mm"][2]) <= 2)}
print(f"[dock4] aircraft L x W x H = {size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm  (user manual {SPEC['aircraft_mm']}, spec page {SPEC['aircraft_mm_spec_page']}; "
      f"DJI's STEP vertices span 391.6 x 475.0 mm)")
fl, fr = Vector(MOTORS["FL"][:2]), Vector(MOTORS["RR"][:2])
report["wheelbase_mm"] = {"model": round(float((fl - fr).length) * 1000, 1), "spec": SPEC["wheelbase_mm"]}
print(f"[dock4] wheelbase {report['wheelbase_mm']['model']} mm (spec {SPEC['wheelbase_mm']})")
roof_gap = (LID_TOP - LID_T) - (AC_REST.z + 0.1858)
print(f"[dock4] aircraft top to cover roof (inside): {roof_gap * 1000:.1f} mm; rotor axis z {ZA * 1000:.0f} mm, transfer radius {R_SWAP * 1000:.0f} mm")
report["clearances_mm"] = {"aircraft_to_roof": round(roof_gap * 1000, 1)}
scene["dock4_validation"] = json.dumps(report)
scene.frame_set(0)

# ============================================================================ 15. studio (Blender only)
world = bpy.data.worlds.new("Studio")
scene.world = world
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value, bg.inputs[1].default_value = (0.58, 0.62, 0.67, 1), 0.7


def light(name, kind, energy, loc, rot, size):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    if kind == "SUN":
        ld.angle = size
    else:
        ld.size = size
    ob = bpy.data.objects.new(name, ld)
    C_STUDIO.objects.link(ob)
    ob.location, ob.rotation_euler = loc, rot
    return ob


light("Key", "SUN", 3.2, (3, -4, 6), (math.radians(48), 0, math.radians(38)), math.radians(4))
light("Fill", "AREA", 250, (-3.5, -2.5, 2.5), (math.radians(60), 0, math.radians(-55)), 3.0)
light("Rim", "AREA", 180, (1.0, 4.0, 2.2), (math.radians(-65), 0, math.radians(190)), 2.0)
part("Studio_Ground", lambda bm: add_box(bm, (-150, -150, -0.201), (150, 150, -0.2)), ["ground"], C_STUDIO, smooth_deg=None)


def camera(name, loc, target, lens=50, ortho=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    if ortho:
        cd.type, cd.ortho_scale = "ORTHO", ortho
    ob = bpy.data.objects.new(name, cd)
    C_STUDIO.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return ob


CAMS = {
    "hero": camera("Cam_Hero", (-1.55, -1.85, 1.25), (0.0, -0.02, 0.40)),
    "open": camera("Cam_Open", (-1.35, -2.9, 1.35), (-0.05, 0.0, 0.62), 40),
    "rear": camera("Cam_RearSection", (1.95, -0.32, 0.62), (0.0, -0.06, 0.40), 55),
    "side": camera("Cam_SideSection", (0.12, -1.85, 0.62), (0.02, 0.0, 0.42), 55),
    "detail": camera("Cam_SwapDetail", (0.75, -0.85, 0.95), (0.08, -0.04, 0.44), 50),
    "top": camera("Cam_TopOrtho", (0, 0, 6), (0, 0, 0), ortho=2.0),
    "front": camera("Cam_FrontOrtho", (0, -6, 0.35), (0, 0, 0.35), ortho=2.0),
    "bay": camera("Cam_BatteryBay", (-0.128, 0.0, AC_REST.z + 0.006), (0.3, 0.0, AC_REST.z - 0.012), 16),
}
scene.camera = CAMS["hero"]
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
try:
    scene.eevee.taa_render_samples = 64
except AttributeError:
    pass

# X-ray materials for the cut-away renders: the dock shell and aircraft turn translucent, the mechanism stays solid
XRAY = {}


def xray_copy(m, alpha):
    if m.name in XRAY:
        return XRAY[m.name]
    c = m.copy()
    c.name = m.name + "_XRay"
    b = next(n for n in c.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    b.inputs["Alpha"].default_value = alpha
    try:
        c.surface_render_method = "BLENDED"
    except AttributeError:
        c.blend_method = "BLEND"
    c.use_backface_culling = False
    XRAY[m.name] = c
    return c


SHELL = [o for o in list(C_DOCK.all_objects) if o.type == "MESH" and not any(k in o.name for k in ("Marker", "Charge", "StatusIndicator", "Internal"))]
AIRFRAME = [o for o in C_AC.all_objects if o.type == "MESH" and o.name in ("M5TD_Fuselage", "M5TD_Arms", "M5TD_Gimbal", "M5TD_LiDAR", "M5TD_RTKBeacon", "M5TD_BayLining")]
ORIG = {o.name: [s.material for s in o.material_slots] for o in SHELL + AIRFRAME}


def set_xray(on):
    for o in SHELL + AIRFRAME:
        a = 0.10 if o in SHELL else 0.35
        if o.name.startswith("Dock_Internal") or o.name in ("Dock_AirConditioner", "Dock_PowerUnit", "Dock_CabinetInterior"):
            a = 0.22
        for s, m in zip(o.material_slots, ORIG[o.name]):
            if m is not None:
                s.material = xray_copy(m, a) if on else m


# ============================================================================ 16. save / export / render
scene.frame_set(0)
blend = os.path.join(ROOT, "dock4.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend)
print("[dock4] saved", blend)

if DO_EXPORT:
    bpy.ops.object.select_all(action="DESELECT")
    for c in (C_DOCK, C_SWAP, C_BATT, C_AC):
        for ob in c.all_objects:
            ob.select_set(True)
    glb = os.path.join(ROOT, "web", "dock4.glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True, export_extras=True, export_apply=True,
                              export_yup=True, export_animations=True, export_animation_mode="SCENE",
                              export_anim_scene_split_object=False, export_frame_range=True, export_force_sampling=True,
                              export_optimize_animation_size=True)
    print(f"[dock4] exported {glb} {os.path.getsize(glb) / 1e6:.2f} MB")
    with open(os.path.join(ROOT, "web", "dock4_meta.json"), "w") as fh:
        json.dump({"spec": SPEC, "validation": report, "timeline": TIMELINE, "hotspots": HOTSPOTS,
                   "geometry": {"rotor_axis_z_mm": round(ZA * 1000, 1), "transfer_radius_mm": R_SWAP * 1000, "deck_z_mm": DECK_Z * 1000,
                                "hatch_mm": [round(v * 1000, 1) for v in HATCH], "rear_face_x_mm": REAR_IN * 1000,
                                "hook_stroke_mm": HOOK_STROKE * 1000, "screw_pitch_mm": SCREW_PITCH * 1000}}, fh, indent=2)

if DO_RENDER:
    out = os.path.join(ROOT, "renders")
    os.makedirs(out, exist_ok=True)
    shots = [("01_closed", "hero", 600, None), ("02_open_landing", "open", 62, None), ("03_rear_xray_pull", "rear", 430, "xray"),
             ("04_side_cutaway_turn", "side", 500, "xray"), ("05_rear_xray_store", "rear", 570, "xray"), ("06_rear_xray_fetch", "rear", 700, "xray"),
             ("07_detail_cradle_up", "detail", 330, "nocover"), ("08_top_open_ortho", "top", 0, None), ("09_front_closed_ortho", "front", 600, None),
             ("10_bay_camera", "bay", 765, None)]
    cover_parts = [o for lid in LIDS.values() for o in [lid] + list(lid.children_recursive)]
    for name, cam, frame, mode in shots:
        if SHOTS and name not in SHOTS:
            continue
        set_xray(mode == "xray")
        for o in cover_parts:
            o.hide_render = mode == "nocover"
        scene.camera, scene.render.filepath = CAMS[cam], os.path.join(out, name + ".png")
        scene.frame_set(frame)
        bpy.ops.render.render(write_still=True)
        print("[dock4] rendered", scene.render.filepath)
    set_xray(False)
    for o in cover_parts:
        o.hide_render = False
    scene.frame_set(0)
    scene.camera = CAMS["hero"]

if DO_VIDEO:
    set_xray(True)
    vid = os.path.join(ROOT, "renders", "swap_frames")
    os.makedirs(vid, exist_ok=True)
    scene.camera = CAMS["rear"]
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.eevee.taa_render_samples = 24
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = os.path.join(vid, "f_")
    scene.frame_start, scene.frame_end = F["close0"], F["open1"]
    bpy.ops.render.render(animation=True)
    scene.frame_start, scene.frame_end = 0, F["end"]
    set_xray(False)

if failed:
    print("[dock4] VALIDATION FAILED:", ", ".join(failed))
