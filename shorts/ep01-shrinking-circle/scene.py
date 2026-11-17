"""Episode 01: "Last One In The Circle Wins $1,000,000".

Builds the whole 3D Short procedurally with Blender's Python API (bpy) and
renders a 9:16 frame sequence.

    python3 scene.py --out frames/ --res 720 --samples 12 [--start 0 --end 629]

Timeline (30 fps, 630 frames = 21 s). Captions are added in post (build.sh).
"""
import argparse
import math
import random
import sys

import bpy
from mathutils import Vector

FPS = 30
END = 629

# --------------------------------------------------------------------------- args
p = argparse.ArgumentParser()
p.add_argument("--out", default="frames/")
p.add_argument("--res", type=int, default=720, help="width in px; height = 16:9 of it")
p.add_argument("--samples", type=int, default=12)
p.add_argument("--start", type=int, default=0)
p.add_argument("--end", type=int, default=END)
p.add_argument("--still", type=int, default=None, help="render one frame only")
p.add_argument("--blend", default=None, help="also save the .blend file here")
args = p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])

random.seed(7)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


# ---------------------------------------------------------------------- helpers
def mat(name, color, emit=0.0, rough=0.45, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*color, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


def _fcurves(idblock):
    """F-curves of an ID's action, across the legacy and layered-action APIs."""
    ad = idblock.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "fcurves") and len(getattr(act, "fcurves", [])):
        return list(act.fcurves)
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


def setk(obj, frame, interp="BEZIER", **props):
    for k, v in props.items():
        setattr(obj, k, v)
        obj.keyframe_insert(data_path=k, frame=frame)
    for fc in _fcurves(obj):
        if fc.data_path in props:
            for kp in fc.keyframe_points:
                if abs(kp.co.x - frame) < 0.01:
                    kp.interpolation = interp


def add(prim, **kw):
    getattr(bpy.ops.mesh, f"primitive_{prim}_add")(**kw)
    o = bpy.context.active_object
    return o


def smooth(o):
    for poly in o.data.polygons:
        poly.use_smooth = True


# ------------------------------------------------------------------------ world
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
# vertical gradient sky: deep purple top -> magenta horizon
nt = world.node_tree
tc = nt.nodes.new("ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.35
ramp.color_ramp.elements[0].color = (0.55, 0.08, 0.25, 1)
ramp.color_ramp.elements[1].position = 0.75
ramp.color_ramp.elements[1].color = (0.03, 0.01, 0.12, 1)
mapr = nt.nodes.new("ShaderNodeMapRange")
mapr.inputs["From Min"].default_value = -1
mapr.inputs["From Max"].default_value = 1
nt.links.new(tc.outputs["Generated"], sep.inputs[0])
nt.links.new(sep.outputs["Z"], mapr.inputs["Value"])
nt.links.new(mapr.outputs["Result"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 0.9

# ----------------------------------------------------------------------- lights
bpy.ops.object.light_add(type="SUN", location=(6, -6, 12))
sun = bpy.context.active_object
sun.data.energy = 4.0
sun.data.angle = math.radians(6)
sun.rotation_euler = (math.radians(40), math.radians(15), math.radians(35))

bpy.ops.object.light_add(type="AREA", location=(-8, -4, 6))
fill = bpy.context.active_object
fill.data.energy = 900
fill.data.size = 8
fill.data.color = (0.5, 0.7, 1.0)
fill.rotation_euler = (math.radians(60), 0, math.radians(-60))

# ------------------------------------------------------------------- lava below
lava = add("plane", size=200, location=(0, 0, -14))
lm = bpy.data.materials.new("Lava")
lm.use_nodes = True
ln = lm.node_tree
lb = ln.nodes["Principled BSDF"]
noise = ln.nodes.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 22.0
noise.inputs["Distortion"].default_value = 2.5
noise.inputs["Detail"].default_value = 6
lr = ln.nodes.new("ShaderNodeValToRGB")
lr.color_ramp.elements[0].position = 0.54
lr.color_ramp.elements[0].color = (0.06, 0.005, 0.0, 1)
lr.color_ramp.elements[1].position = 0.58
lr.color_ramp.elements[1].color = (1.0, 0.18, 0.0, 1)
ln.links.new(noise.outputs["Fac"], lr.inputs["Fac"])
ln.links.new(lr.outputs["Color"], lb.inputs["Base Color"])
ln.links.new(lr.outputs["Color"], lb.inputs["Emission Color"])
lb.inputs["Emission Strength"].default_value = 2.5
lava.data.materials.append(lm)

# ------------------------------------------------------------------- platform
R0 = 6.0
plat = add("cylinder", vertices=96, radius=1.0, depth=0.6, location=(0, 0, -0.3))
plat.scale = (R0, R0, 1)
smooth(plat)
pm = bpy.data.materials.new("Platform")
pm.use_nodes = True
pn = pm.node_tree
pb = pn.nodes["Principled BSDF"]
# concentric rings so the shrink reads clearly
ptc = pn.nodes.new("ShaderNodeTexCoord")
grad = pn.nodes.new("ShaderNodeTexGradient")
grad.gradient_type = "SPHERICAL"
mapping = pn.nodes.new("ShaderNodeMapping")
mapping.inputs["Scale"].default_value = (1, 1, 1)
math_mul = pn.nodes.new("ShaderNodeMath")
math_mul.operation = "MULTIPLY"
math_mul.inputs[1].default_value = 6
frac = pn.nodes.new("ShaderNodeMath")
frac.operation = "FRACT"
ring = pn.nodes.new("ShaderNodeValToRGB")
ring.color_ramp.interpolation = "CONSTANT"
ring.color_ramp.elements[0].color = (0.95, 0.95, 1.0, 1)
ring.color_ramp.elements[1].position = 0.5
ring.color_ramp.elements[1].color = (0.15, 0.75, 0.95, 1)
pn.links.new(ptc.outputs["Object"], mapping.inputs["Vector"])
pn.links.new(mapping.outputs["Vector"], grad.inputs["Vector"])
pn.links.new(grad.outputs["Fac"], math_mul.inputs[0])
pn.links.new(math_mul.outputs[0], frac.inputs[0])
pn.links.new(frac.outputs[0], ring.inputs["Fac"])
pn.links.new(ring.outputs["Color"], pb.inputs["Base Color"])
pb.inputs["Roughness"].default_value = 0.35
plat.data.materials.append(pm)

# glowing warning rim that flashes before each shrink
rim = add("torus", major_radius=1.0, minor_radius=0.025, major_segments=128,
          location=(0, 0, 0.0))
rim.scale = (R0, R0, R0)
rim_m = mat("Rim", (1.0, 0.1, 0.1), emit=0.0)
rim.data.materials.append(rim_m)
rim_emit = rim_m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]

# shrink schedule: (start_frame, end_frame, new_radius)
SHRINKS = [(75, 88, 4.6), (165, 178, 3.4), (255, 268, 2.25), (345, 358, 1.35)]

r = R0
setk(plat, 0, scale=(R0, R0, 1))
setk(rim, 0, scale=(R0, R0, R0))
for s, e, nr in SHRINKS:
    setk(plat, s, scale=(r, r, 1))
    setk(rim, s, scale=(r, r, r))
    setk(plat, e, scale=(nr, nr, 1))
    setk(rim, e, scale=(nr, nr, nr))
    # rim flash: 3 pulses in the 24 frames before the shrink
    for i in range(3):
        f = s - 24 + i * 8
        rim_emit.default_value = 0
        rim_emit.keyframe_insert("default_value", frame=f)
        rim_emit.default_value = 25
        rim_emit.keyframe_insert("default_value", frame=f + 3)
        rim_emit.default_value = 0
        rim_emit.keyframe_insert("default_value", frame=f + 7)
    r = nr

# ---------------------------------------------------------------------- money
cash_green = mat("Cash", (0.18, 0.55, 0.22), rough=0.6)
band = mat("Band", (0.95, 0.85, 0.35), rough=0.3, metal=0.6)
money_root = bpy.data.objects.new("MoneyRoot", None)
scene.collection.objects.link(money_root)
bricks = []
for z in range(5):
    for ix in range(3):
        for iy in range(2):
            if z == 4 and (ix, iy) not in [(1, 0), (1, 1)]:
                continue
            b = add("cube", size=1, location=((ix - 1) * 0.32, (iy - 0.5) * 0.16, 0.05 + z * 0.1))
            b.scale = (0.3, 0.15, 0.09)
            b.data.materials.append(cash_green)
            bb = add("cube", size=1, location=b.location)
            bb.scale = (0.06, 0.152, 0.092)
            bb.data.materials.append(band)
            b.parent = money_root
            bb.parent = money_root
            bricks += [b, bb]
# pedestal sign "$1M"
bpy.ops.object.text_add(location=(0, -0.2, 0.85))
sign = bpy.context.active_object
sign.data.body = "$1,000,000"
sign.data.align_x = "CENTER"
sign.data.size = 0.32
sign.data.extrude = 0.03
try:
    sign.data.font = bpy.data.fonts.load("/usr/share/fonts/opentype/inter/Inter-Black.otf")
except Exception:
    pass
sign.rotation_euler = (math.radians(80), 0, 0)
sign.data.materials.append(mat("Gold", (1.0, 0.75, 0.1), emit=1.5, rough=0.2, metal=0.8))
sign.parent = money_root
# gentle hover + spin of the sign
for f in range(0, END + 1, 30):
    setk(sign, f, location=(0, -0.2, 0.85 + 0.06 * math.sin(f / 15)))

# ---------------------------------------------------------------- characters
EYE_W = mat("EyeWhite", (1, 1, 1), rough=0.2)
EYE_B = mat("Pupil", (0.02, 0.02, 0.02), rough=0.1)


def make_player(name, color, radius, angle_deg):
    root = bpy.data.objects.new(name, None)
    scene.collection.objects.link(root)
    a = math.radians(angle_deg)
    root.location = (radius * math.cos(a), radius * math.sin(a), 0)
    # face the centre-ish / camera: rotate so local -Y faces the camera side
    root.rotation_euler = (0, 0, a + math.pi / 2)
    body = add("uv_sphere", segments=32, ring_count=16, radius=1, location=(0, 0, 0))
    body.scale = (0.32, 0.32, 0.5)
    body.location = (0, 0, 0.5)
    smooth(body)
    body.data.materials.append(mat(name + "Mat", color, rough=0.35))
    body.parent = root
    for side in (-1, 1):
        e = add("uv_sphere", segments=16, ring_count=8, radius=0.085,
                location=(side * 0.12, 0.27, 0.72))
        smooth(e)
        e.data.materials.append(EYE_W)
        e.parent = root
        pu = add("uv_sphere", segments=12, ring_count=6, radius=0.04,
                 location=(side * 0.12, 0.34, 0.72))
        pu.data.materials.append(EYE_B)
        pu.parent = root
    # little feet
    for side in (-1, 1):
        ft = add("uv_sphere", segments=12, ring_count=6, radius=0.11,
                 location=(side * 0.14, 0.05, 0.06))
        ft.scale = (1, 1.3, 0.6)
        ft.data.materials.append(mat(name + "Foot", tuple(c * 0.6 for c in color)))
        ft.parent = root
    return root


# The "front" of a player is local +Y; we rotate them to face outward-left so
# eyes are visible from the camera at -Y. Simpler: face the camera direction.
PLAYERS = {
    "Red":    ((0.95, 0.12, 0.12), 5.25, 250),
    "Orange": ((1.0, 0.5, 0.05), 4.0, 330),
    "Yellow": ((1.0, 0.85, 0.1), 3.85, 205),
    "Purple": ((0.55, 0.2, 0.9), 2.8, 290),
    "Green":  ((0.15, 0.8, 0.3), 1.0, 20),
    "Blue":   ((0.15, 0.4, 1.0), 1.0, 160),
}
players = {}
for n, (c, rad, ang) in PLAYERS.items():
    pl = make_player(n, c, rad, ang)
    # face camera (camera mostly sits at -Y): local +Y should point to -Y world
    pl.rotation_euler = (0, 0, math.pi)
    players[n] = pl


def idle(pl, f0, f1, phase):
    """Nervous little hops between f0 and f1."""
    base = pl.location.copy()
    for f in range(f0, f1, 6):
        h = 0.08 if (f // 6 + phase) % 2 else 0.0
        setk(pl, f, location=(base.x, base.y, base.z + h))


def fall(pl, f, outward=1.2, dur=26):
    """Lose footing at frame f, flail and drop into the lava."""
    loc = pl.location.copy()
    d = Vector((loc.x, loc.y, 0)).normalized() if loc.length > 0.01 else Vector((0, -1, 0))
    setk(pl, f, location=loc, rotation_euler=pl.rotation_euler.copy())
    up = loc + d * 0.4 + Vector((0, 0, 0.6))
    setk(pl, f + 6, interp="BEZIER", location=up)
    end = loc + d * outward + Vector((0, 0, -16))
    rot = pl.rotation_euler.copy()
    rot.x += math.radians(random.choice([-1, 1]) * 540)
    rot.y += math.radians(200)
    setk(pl, f + dur, interp="LINEAR", location=end, rotation_euler=rot)
    # accelerate like gravity
    for fc in _fcurves(pl):
        if fc.data_path == "location":
            for kp in fc.keyframe_points:
                if abs(kp.co.x - (f + 6)) < 0.01:
                    kp.interpolation = "QUAD"
                    kp.easing = "EASE_IN"


ph = 0
for n, pl in players.items():
    idle(pl, 0, 60, ph)
    ph += 1

# Beat 1 (f75-88): shrink to 4.6 -> Red falls
fall(players["Red"], 84)
for n in ["Orange", "Yellow", "Purple", "Green", "Blue"]:
    idle(players[n], 60, 160, ph); ph += 1
# Orange & Yellow scoot inward but too slow
# Beat 2 (f165-178): shrink to 3.4 -> Orange + Yellow fall
fall(players["Orange"], 172)
fall(players["Yellow"], 176)
for n in ["Purple", "Green", "Blue"]:
    idle(players[n], 160, 250, ph); ph += 1
# Beat 3 (f255-268): shrink to 2.25 -> Purple "thought they were safe" and falls
fall(players["Purple"], 262)
for n in ["Green", "Blue"]:
    idle(players[n], 250, 380, ph); ph += 1

# Beat 4: final 2. Green charges at Blue (f390-412), Blue hops aside, Green slides off.
g = players["Green"]
b = players["Blue"]
gstart = g.location.copy()
bstart = b.location.copy()
setk(g, 390, location=gstart)
# wind up
setk(g, 398, location=gstart + Vector((0.15, 0.0, 0.0)))
setk(b, 400, location=bstart)
# Blue hops up and to the side (toward camera)
setk(b, 406, location=bstart + Vector((0.1, -0.35, 0.7)))
setk(b, 414, location=bstart + Vector((0.15, -0.45, 0.0)))
# Green dashes across where Blue was and overshoots the edge
dash_end = Vector((-1.55, 0.25, 0.0))
setk(g, 410, interp="LINEAR", location=dash_end)
g.location = dash_end
fall(g, 412, outward=1.5)

# Blue wins: big celebration jumps f450 -> 600
bl = bstart + Vector((0.15, -0.45, 0.0))
for i, f in enumerate(range(450, 612, 14)):
    setk(b, f, location=bl)
    setk(b, f + 7, location=bl + Vector((0, 0, 0.6)))
setk(b, 620, location=bl)

# ------------------------------------------------------------------ cash rain
bill_mat = mat("Bill", (0.35, 0.75, 0.35), rough=0.7)
bill_mat.use_backface_culling = False
for i in range(180):
    bill = add("plane", size=1)
    bill.scale = (0.22, 0.1, 1)
    bill.data.materials.append(bill_mat)
    start = random.randint(445, 520)
    x, y = random.uniform(-3.5, 3.5), random.uniform(-3.5, 3.0)
    z0 = random.uniform(6, 10)
    bill.location = (x, y, 40)
    setk(bill, start - 1, interp="CONSTANT", location=(x, y, 40))
    setk(bill, start, location=(x, y, z0),
         rotation_euler=(random.random() * 6, random.random() * 6, random.random() * 6))
    dur = random.randint(70, 120)
    setk(bill, start + dur, interp="LINEAR",
         location=(x + random.uniform(-1, 1), y + random.uniform(-1, 1), -3),
         rotation_euler=(random.random() * 20, random.random() * 20, random.random() * 20))

# ---------------------------------------------------------------------- camera
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 28
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
target = bpy.data.objects.new("CamTarget", None)
scene.collection.objects.link(target)
tt = cam.constraints.new("TRACK_TO")
tt.target = target
tt.track_axis = "TRACK_NEGATIVE_Z"
tt.up_axis = "UP_Y"

CAM_KEYS = [
    # frame, camera location, target location
    (0,   (0.0, -2.8, 1.5), (0, 0, 0.6)),       # tight on the cash (hook)
    (36,  (0.0, -13.5, 10.5), (0, 0.5, 0)),      # snap out to the whole arena
    (84,  (-3.0, -12.0, 8.0), (-1.5, -1.5, 0)),  # follow Red's fall
    (130, (1.5, -11.5, 8.5), (0, 0, 0)),
    (172, (2.5, -10.0, 7.0), (0.5, -0.5, 0)),
    (230, (4.0, -8.5, 6.5), (0, 0, 0.2)),
    (262, (3.0, -7.5, 5.5), (0.5, -1.0, 0.3)),   # Purple falls
    (330, (1.0, -6.0, 3.6), (0, 0, 0.4)),
    (385, (0.4, -4.6, 2.6), (0, 0, 0.5)),        # tension close-up on final 2
    (414, (-1.5, -5.0, 2.8), (-1.2, 0, 0.0)),    # whip to Green falling
    (450, (0.6, -4.2, 1.6), (bl.x, bl.y, 0.7)),  # hero shot: Blue wins
    (560, (-0.8, -4.6, 2.2), (0, 0, 0.6)),
    (629, (0.0, -2.8, 1.5), (0, 0, 0.6)),      # back to the cash = seamless loop
]
for f, cl, tl in CAM_KEYS:
    setk(cam, f, location=cl)
    setk(target, f, location=tl)

# subtle handheld shake
for fc in _fcurves(cam):
    if fc.data_path == "location":
        m = fc.modifiers.new("NOISE")
        m.scale = 6
        m.strength = 0.05

# ---------------------------------------------------------------------- render
scene.frame_start = args.start
scene.frame_end = args.end
scene.render.fps = FPS
scene.render.resolution_x = args.res
scene.render.resolution_y = int(args.res * 16 / 9)
scene.render.resolution_percentage = 100
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 4
scene.cycles.use_adaptive_sampling = True
scene.render.use_motion_blur = True
scene.render.motion_blur_shutter = 0.25
scene.view_settings.view_transform = "Standard"
try:
    scene.view_settings.look = "Medium High Contrast"
except TypeError:
    pass
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = args.out.rstrip("/") + "/f_"

if args.blend:
    bpy.ops.wm.save_as_mainfile(filepath=args.blend)

if args.still is not None:
    scene.frame_set(args.still)
    scene.render.filepath = args.out.rstrip("/") + f"/still_{args.still:04d}.png"
    bpy.ops.render.render(write_still=True)
else:
    bpy.ops.render.render(animation=True)
