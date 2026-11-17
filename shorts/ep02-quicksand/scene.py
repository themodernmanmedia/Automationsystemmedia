"""Ep. 02: "What happens if you step in quicksand" - a 3D animated explainer Short.

Builds the scene procedurally in Blender (bpy) and renders a 9:16 frame sequence
timed to narration.wav (see timing.json).

    python3 scene.py --out frames/ --res 540 --samples 10 [--still N]
"""
import argparse
import math
import random
import sys

import bpy  # noqa: I001  (bpy must load before bmesh)
import bmesh
from mathutils import Vector

FPS = 30
END = 884  # 29.5 s

p = argparse.ArgumentParser()
p.add_argument("--out", default="frames/")
p.add_argument("--res", type=int, default=540)
p.add_argument("--samples", type=int, default=10)
p.add_argument("--start", type=int, default=0)
p.add_argument("--end", type=int, default=END)
p.add_argument("--still", type=int, default=None)
p.add_argument("--blend", default=None)
args = p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])

random.seed(3)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
D = math.radians


# ----------------------------------------------------------------- helpers
def _fcurves(idblock):
    ad = idblock.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    if not out and hasattr(act, "fcurves"):
        out = list(act.fcurves)
    return out


def setk(obj, frame, interp="BEZIER", **props):
    """Set properties on obj and keyframe them at frame with given interpolation."""
    for k, v in props.items():
        setattr(obj, k, v)
        obj.keyframe_insert(data_path=k, frame=frame)
    for fc in _fcurves(obj):
        if fc.data_path in props:
            for kp in fc.keyframe_points:
                if abs(kp.co.x - frame) < 0.01:
                    kp.interpolation = interp


def rot(obj, frame, x=0.0, y=0.0, z=0.0, interp="BEZIER"):
    setk(obj, frame, interp, rotation_euler=(D(x), D(y), D(z)))


def mat(name, color, rough=0.5, metal=0.0, emit=0.0, sss=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*color, 1)
        b.inputs["Emission Strength"].default_value = emit
    if sss:
        b.inputs["Subsurface Weight"].default_value = sss
        b.inputs["Subsurface Radius"].default_value = (0.5, 0.2, 0.1)
        b.inputs["Subsurface Scale"].default_value = 0.05
    return m


def obj_from_bm(name, bm, material, parent=None, loc=(0, 0, 0), scale=(1, 1, 1), smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for poly in me.polygons:
            poly.use_smooth = True
    o = bpy.data.objects.new(name, me)
    scene.collection.objects.link(o)
    me.materials.append(material)
    if parent:
        o.parent = parent
    o.location = loc
    o.scale = scale
    return o


def sphere_bm(r, seg=32, rings=16):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    return bm


def capsule_bm(r, length, seg=24, rings=12):
    """Capsule hanging down from the origin (the joint): top cap centred at 0."""
    bm = sphere_bm(r, seg, rings)
    for v in bm.verts:
        if v.co.z < 0:
            v.co.z -= length
    return bm


def empty(name, parent=None, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    scene.collection.objects.link(e)
    e.empty_display_size = 0.05
    if parent:
        e.parent = parent
    e.location = loc
    return e


def box(name, size, loc, material, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    if bevel:
        bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:], offset=bevel, segments=3, affect="EDGES")
    return obj_from_bm(name, bm, material, loc=loc, smooth=bevel > 0)


def cylinder(name, r, depth, loc, material, verts=64):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r, depth=depth)
    o = obj_from_bm(name, bm, material, loc=loc, smooth=False)
    return o


# ------------------------------------------------------------------- world
world = bpy.data.worlds.new("Sky")
scene.world = world
world.use_nodes = True
nt = world.node_tree
bg = nt.nodes["Background"]
tc = nt.nodes.new("ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.5
ramp.color_ramp.elements[0].color = (0.85, 0.82, 0.72, 1)
ramp.color_ramp.elements[1].position = 0.75
ramp.color_ramp.elements[1].color = (0.18, 0.42, 0.85, 1)
mr = nt.nodes.new("ShaderNodeMapRange")
mr.inputs["From Min"].default_value = -1
mr.inputs["From Max"].default_value = 1
nt.links.new(tc.outputs["Generated"], sep.inputs[0])
nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 0.75

bpy.ops.object.light_add(type="SUN")
sun = bpy.context.active_object
sun.data.energy = 3.2
sun.data.color = (1.0, 0.93, 0.82)
sun.data.angle = D(3)
sun.rotation_euler = (D(50), D(10), D(-35))

# ------------------------------------------------------------------ ground
def sand_material(name, color, dark, rough, scale=40.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t = m.node_tree
    b = t.nodes["Principled BSDF"]
    n = t.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = 8
    cr = t.nodes.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].color = (*dark, 1)
    cr.color_ramp.elements[1].color = (*color, 1)
    bump = t.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    t.links.new(n.outputs["Fac"], cr.inputs["Fac"])
    t.links.new(cr.outputs["Color"], b.inputs["Base Color"])
    t.links.new(n.outputs["Fac"], bump.inputs["Height"])
    t.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = rough
    return m, b


SAND, _ = sand_material("Sand", (0.85, 0.62, 0.36), (0.7, 0.48, 0.26), 0.85)
QSAND, qs_bsdf = sand_material("Quicksand", (0.42, 0.29, 0.16), (0.27, 0.18, 0.09), 0.3, 25)
PIT_R = 1.6

ground = box("Ground", (80, 80, 4.0), (0, 0, -2.0), SAND)
pit = cylinder("Pit", PIT_R, 4.0, (0, 0, -1.995), QSAND)

hole = cylinder("HoleCutter", PIT_R, 4.4, (0, 0, -2.0), SAND)
hole.hide_render = True
hole.hide_viewport = True
m = ground.modifiers.new("Hole", "BOOLEAN")
m.operation = "DIFFERENCE"
m.object = hole

cutter = box("Cutaway", (16.0, 20.0, 6.0), (0, -10.0, -0.4), SAND)
cutter.hide_render = True
cutter.hide_viewport = True
CUT_ON, CUT_OFF = 218, 578
for o in (ground, pit):
    cm = o.modifiers.new("Cut", "BOOLEAN")
    cm.operation = "DIFFERENCE"
    cm.object = cutter
    for f, on in ((0, False), (CUT_ON, True), (CUT_OFF, False)):
        cm.show_render = on
        cm.show_viewport = on
        cm.keyframe_insert("show_render", frame=f)
        cm.keyframe_insert("show_viewport", frame=f)

# the pit gets wetter/glossier when he wiggles water into it
rough_in = qs_bsdf.inputs["Roughness"]
for f, v in ((0, 0.3), (600, 0.3), (700, 0.08)):
    rough_in.default_value = v
    rough_in.keyframe_insert("default_value", frame=f)

# ------------------------------------------------------------- set dressing
ROCK = mat("Rock", (0.42, 0.4, 0.37), rough=0.8)
for i in range(14):
    a = random.uniform(0, 2 * math.pi)
    d = random.uniform(3.5, 12)
    x, y = d * math.cos(a), d * math.sin(a) + 3
    if y < 1.2 and abs(x) < 4:
        continue
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=random.uniform(0.25, 0.7))
    for v in bm.verts:
        v.co *= 1 + random.uniform(-0.18, 0.18)
    r = obj_from_bm(f"Rock{i}", bm, ROCK, loc=(x, y, 0.0), smooth=False)
    r.scale = (1, random.uniform(0.7, 1.2), random.uniform(0.5, 0.8))

TRUNK = mat("Trunk", (0.38, 0.26, 0.15), rough=0.9)
LEAF = mat("Leaf", (0.15, 0.45, 0.12), rough=0.6)
for i, (x, y, h) in enumerate([(-5.5, 6, 5.5), (4.5, 7.5, 6.5), (8, 4, 5), (-9, 3, 6), (1.5, 12, 7)]):
    lean = random.uniform(-8, 8)
    t = cylinder(f"Trunk{i}", 0.13, h, (x, y, h / 2), TRUNK, 12)
    t.rotation_euler = (D(lean), D(random.uniform(-6, 6)), 0)
    top = Vector((x, y, h))
    for k in range(7):
        a = 2 * math.pi * k / 7 + random.random()
        bm = sphere_bm(1.0, 16, 8)
        lf = obj_from_bm(f"Leaf{i}_{k}", bm, LEAF, loc=top + Vector((math.cos(a) * 0.9, math.sin(a) * 0.9, -0.15)))
        lf.scale = (1.15, 0.28, 0.05)
        lf.rotation_euler = (0, D(25), a)

HILL = mat("Hill", (0.35, 0.5, 0.3), rough=0.9)
for i, (x, y, s) in enumerate([(-25, 45, 18), (10, 55, 22), (35, 40, 16)]):
    h = obj_from_bm(f"Hill{i}", sphere_bm(1.0), HILL, loc=(x, y, -2))
    h.scale = (s, s * 0.6, s * 0.35)

# ------------------------------------------------------------------ the man
SKIN = mat("Skin", (0.78, 0.55, 0.42), rough=0.45, sss=0.15)
SHIRT = mat("Shirt", (0.12, 0.42, 0.62), rough=0.7)
PANTS = mat("Pants", (0.62, 0.53, 0.38), rough=0.8)
SHOE = mat("Shoe", (0.25, 0.16, 0.1), rough=0.6)
HAIR = mat("Hair", (0.16, 0.1, 0.06), rough=0.65)
WHITE = mat("EyeWhite", (0.95, 0.95, 0.95), rough=0.15)
DARK = mat("Pupil", (0.03, 0.02, 0.02), rough=0.1)
MOUTH = mat("Mouth", (0.3, 0.07, 0.07), rough=0.4)

root = empty("Root", loc=(0, 0, 0.95))          # pelvis
obj_from_bm("Pelvis", sphere_bm(1.0), PANTS, root, (0, 0, 0.0), (0.18, 0.12, 0.13))
spine = empty("Spine", root, (0, 0, 0.05))
obj_from_bm("Torso", capsule_bm(0.17, 0.32), SHIRT, spine, (0, 0, 0.52), (1.12, 0.72, 1))
neck = empty("Neck", spine, (0, 0, 0.6))
obj_from_bm("NeckMesh", capsule_bm(0.055, 0.06), SKIN, neck, (0, 0, 0.06))
head = empty("Head", neck, (0, 0, 0.08))
obj_from_bm("HeadMesh", sphere_bm(0.125), SKIN, head, (0, 0, 0.13), (1, 1.05, 1.13))
# hair: the head sphere minus the face region
hb = sphere_bm(0.131)
bmesh.ops.delete(hb, geom=[v for v in hb.verts if v.co.z < 0.0 or (v.co.y < -0.05 and v.co.z < 0.075)],
                 context="VERTS")
obj_from_bm("Hair", hb, HAIR, head, (0, 0.006, 0.14), (1, 1.05, 1.1))
for s in (-1, 1):
    obj_from_bm(f"Eye{s}", sphere_bm(0.024, 16, 8), WHITE, head, (s * 0.045, -0.112, 0.15))
    obj_from_bm(f"Pupil{s}", sphere_bm(0.013, 12, 6), DARK, head, (s * 0.045, -0.133, 0.15))
    brow = box(f"Brow{s}", (0.045, 0.012, 0.01), (s * 0.047, -0.125, 0.185), HAIR)
    brow.parent = head
    brow.location = (s * 0.047, -0.125, 0.188)
    brow.rotation_euler = (0, s * D(-14), 0)   # worried brows
    obj_from_bm(f"Ear{s}", sphere_bm(0.03, 12, 6), SKIN, head, (s * 0.125, 0, 0.13), (0.5, 1, 1.3))
obj_from_bm("Nose", sphere_bm(0.022, 12, 6), SKIN, head, (0, -0.135, 0.12), (0.8, 1, 1.2))
obj_from_bm("Mouth", sphere_bm(0.02, 12, 6), MOUTH, head, (0, -0.122, 0.065), (1.2, 0.5, 1.0))

joints = {}
for side, s in (("L", 1), ("R", -1)):
    sh = empty(f"Shoulder{side}", spine, (s * 0.21, 0, 0.47))
    obj_from_bm(f"Sleeve{side}", capsule_bm(0.065, 0.1), SHIRT, sh, (0, 0, 0))
    obj_from_bm(f"UpperArm{side}", capsule_bm(0.05, 0.22), SKIN, sh, (0, 0, 0))
    el = empty(f"Elbow{side}", sh, (0, 0, -0.27))
    obj_from_bm(f"Forearm{side}", capsule_bm(0.043, 0.2), SKIN, el, (0, 0, 0))
    obj_from_bm(f"Hand{side}", sphere_bm(0.05, 16, 8), SKIN, el, (0, 0, -0.27), (0.8, 0.55, 1.1))
    hp = empty(f"Hip{side}", root, (s * 0.095, 0, -0.03))
    obj_from_bm(f"Thigh{side}", capsule_bm(0.08, 0.33), PANTS, hp, (0, 0, 0))
    kn = empty(f"Knee{side}", hp, (0, 0, -0.43))
    obj_from_bm(f"Shin{side}", capsule_bm(0.065, 0.33), PANTS, kn, (0, 0, 0))
    obj_from_bm(f"Shoe{side}", sphere_bm(1.0, 16, 8), SHOE, kn, (0, -0.05, -0.43), (0.065, 0.14, 0.055))
    joints[side] = dict(sh=sh, el=el, hip=hp, knee=kn)
L, R = joints["L"], joints["R"]

# face the +X direction (walking direction)
FACE = 90.0
setk(root, 0, location=(-2.75, 2.3, 0.95))
rot(root, 0, z=50)
# relaxed arms
for j, s in ((L, 1), (R, -1)):
    rot(j["sh"], 0, y=s * 8)
    rot(j["el"], 0, x=-10)


def walk(f0, f1, period=18, amp=1.0):
    for f in range(f0, f1 + 1, 3):
        ph = (f - f0) / period * 2 * math.pi
        a = amp * (1 - 0.0)
        for j, s, sign in ((L, 1, 1), (R, -1, -1)):
            sw = math.sin(ph) * sign
            rot(j["hip"], f, x=-28 * a * sw)
            rot(j["knee"], f, x=35 * a * max(0.0, math.sin(ph * 1 + (0 if sign > 0 else math.pi) + 1.2)))
            rot(j["sh"], f, x=24 * a * sw, y=s * 8)
            rot(j["el"], f, x=-25)


# ---- S1 (0-79): walks in, steps into the pit and sinks to the knees
walk(0, 54)
setk(root, 22, location=(-1.22, 1.02, 0.95))     # edge of the pit
setk(root, 54, location=(-0.08, 0.06, 0.55))
rot(root, 50, z=50)
rot(root, 72, z=12)
setk(root, 66, location=(0.0, 0, 0.38))
for j in (L, R):
    rot(j["hip"], 60, x=-6)
    rot(j["knee"], 60, x=8)
# panic: arms fly up
rot(L["sh"], 58, x=-30, y=40)
rot(R["sh"], 58, x=-30, y=-40)
rot(L["sh"], 66, x=-150, y=20)
rot(R["sh"], 66, x=-150, y=-20)
rot(L["el"], 66, x=-30)
rot(R["el"], 66, x=-30)
rot(spine, 58, x=0)
rot(spine, 66, x=-8)
rot(head, 60, x=0)
rot(head, 70, x=15)   # looks down at his legs
setk(root, 79, location=(0.0, 0, 0.3))

# ---- S2 (80-217): the movie myth - he goes all the way under... then rewind
rot(root, 80, z=12)
for f, z in ((80, 0.3), (105, -0.05), (120, -0.35), (135, -0.75), (145, -1.0), (152, -1.3), (156, -1.6)):
    setk(root, f, location=(0, 0, z))
rot(L["sh"], 80, x=-150, y=20)
rot(L["sh"], 110, x=-60, y=60)
rot(L["sh"], 125, x=-20, y=80)
rot(R["sh"], 92, x=-178, y=-5)                   # one hand reaching up to the end
rot(R["el"], 92, x=0)
rot(head, 100, x=-25)                             # looks up in despair
# "rewind": back up to the waist
setk(root, 156, location=(0, 0, -1.6))
rot(root, 156, z=0)
setk(root, 176, location=(0, 0, -0.1))
rot(L["sh"], 152, x=-20, y=80)
rot(L["sh"], 176, x=-10, y=75)
rot(R["sh"], 152, x=-178, y=-5)
rot(R["sh"], 176, x=-10, y=-75)                   # arms resting on the sand
rot(L["el"], 176, x=-20)
rot(R["el"], 176, x=-20)
rot(head, 176, x=5)
for j in (L, R):
    rot(j["hip"], 176, x=-6)
    rot(j["knee"], 176, x=8)

# ---- S3/S4 (218-577): cutaway. Stuck at the waist, one leg strains
for f in range(380, 500, 12):
    up = 1 if (f // 12) % 2 == 0 else 0
    rot(L["hip"], f, x=-6 - 22 * up)
    rot(L["knee"], f, x=8 + 30 * up)
    rot(spine, f, x=-4 - 6 * up)
rot(L["hip"], 505, x=-6)
rot(L["knee"], 505, x=8)
rot(spine, 505, x=-4)
rot(head, 380, x=5)
rot(head, 400, x=20)

# ---- S5 (578-717): wiggles legs, water seeps in
for f in range(590, 712, 4):
    w = 1 if (f // 4) % 2 == 0 else -1
    rot(L["hip"], f, x=-6 + 10 * w, y=6 * w)
    rot(R["hip"], f, x=-6 - 10 * w, y=-6 * w)
    setk(root, f, location=(0, 0, -0.1 + 0.015 * w))
rot(L["hip"], 714, x=-6)
rot(R["hip"], 714, x=-6)
rot(head, 600, x=10)

RIPPLE = mat("Ripple", (0.62, 0.52, 0.36), rough=0.08)
for i, f in enumerate((605, 635, 665, 690)):
    bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.018, major_segments=64,
                                     minor_segments=8, location=(0, 0, -5))
    rp = bpy.context.active_object
    rp.data.materials.append(RIPPLE)
    setk(rp, f - 1, interp="CONSTANT", location=(0, 0, -5), scale=(0.3, 0.3, 0.3))
    setk(rp, f, location=(0, 0, 0.012), scale=(0.35, 0.35, 0.35))
    setk(rp, f + 34, location=(0, 0, -0.03), scale=(1.5, 1.5, 1.5))

# ---- S6 (718-884): leans back, spreads out, floats and slides free
rot(root, 717, z=0, interp="CONSTANT")
rot(root, 718, z=FACE)
setk(root, 718, location=(0, 0, -0.1))
rot(root, 762, x=-78, z=FACE)
setk(root, 762, location=(0, 0, 0.06))
rot(spine, 718, x=-4)
rot(spine, 762, x=6)
rot(head, 762, x=-35)                       # keeps his head up, looking at his feet
for j, s in ((L, 1), (R, -1)):
    rot(j["sh"], 730, x=-10, y=s * 75)
    rot(j["sh"], 775, x=0, y=s * 85)       # arms spread wide on the surface
    rot(j["el"], 775, x=-5)
    rot(j["hip"], 735, x=-6)
    rot(j["knee"], 735, x=8)
    rot(j["hip"], 800, x=-14, y=s * 12)     # legs float up to the surface
    rot(j["knee"], 800, x=12)
setk(root, 790, location=(0, 0, 0.08))
setk(root, 872, location=(-2.75, 0, 0.12))
setk(root, 884, location=(-2.8, 0, 0.12))
rot(head, 860, x=-35)
rot(head, 884, x=-55)                       # head drops back - relief

# ------------------------------------------------------------- arrows & car
def arrow(name, color, length=0.6):
    m_ = mat(name + "M", color, emit=2.5, rough=0.4)
    root_ = empty(name)
    sh_ = cylinder(name + "S", 0.045, length, (0, 0, length / 2), m_, 24)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.11, radius2=0.0, depth=0.2)
    hd = obj_from_bm(name + "H", bm, m_, root_, (0, 0, length + 0.1), smooth=False)
    sh_.parent = root_
    sh_.location = (0, 0, length / 2)
    return root_


ups = []
for i, x in enumerate((-0.32, 0.0, 0.32)):
    a = arrow(f"Up{i}", (1.0, 0.8, 0.05), 0.5)
    a.location = (x, -0.45, -1.75)
    setk(a, 0, scale=(0, 0, 0))
    setk(a, 248 + i * 4, scale=(0, 0, 0))
    setk(a, 258 + i * 4, scale=(1.2, 1.2, 1.2))
    for k, f in enumerate(range(270, 370, 15)):
        setk(a, f, location=(x, -0.45, -1.75 + (0.12 if k % 2 else 0.0)))
    setk(a, 372, scale=(1.2, 1.2, 1.2))
    setk(a, 380, scale=(0, 0, 0))

down = arrow("Down", (0.95, 0.12, 0.1), 0.55)
down.rotation_euler = (D(180), 0, 0)
setk(down, 0, scale=(0, 0, 0))
setk(down, 402, scale=(0, 0, 0))
setk(down, 412, scale=(1.3, 1.3, 1.3), location=(0.25, -0.45, -0.25))
setk(down, 470, location=(0.25, -0.45, -0.35))
setk(down, 575, scale=(1.3, 1.3, 1.3))
setk(down, 577, scale=(0, 0, 0))

CAR = mat("Car", (0.8, 0.06, 0.05), rough=0.25, metal=0.3)
GLASS = mat("Glass", (0.1, 0.15, 0.2), rough=0.05)
TYRE = mat("Tyre", (0.05, 0.05, 0.05), rough=0.7)
car = empty("Car", loc=(2.25, 0.9, 0.0))
cb = box("CarBody", (1.0, 1.9, 0.45), (0, 0, 0.42), CAR, bevel=0.08)
cb.parent = car
cb.location = (0, 0, 0.42)
cc = box("CarCabin", (0.85, 1.0, 0.38), (0, 0.1, 0.8), GLASS, bevel=0.08)
cc.parent = car
cc.location = (0, 0.1, 0.8)
for i, (x, y) in enumerate(((-0.5, -0.6), (0.5, -0.6), (-0.5, 0.6), (0.5, 0.6))):
    w = cylinder(f"Wheel{i}", 0.2, 0.18, (0, 0, 0), TYRE, 32)
    w.parent = car
    w.location = (x, y, 0.2)
    w.rotation_euler = (0, D(90), 0)
car.rotation_euler = (0, 0, D(-25))
setk(car, 0, scale=(0, 0, 0))
setk(car, 492, scale=(0, 0, 0))
setk(car, 502, scale=(1.15, 1.15, 1.15))
setk(car, 508, scale=(1, 1, 1))
setk(car, 576, scale=(1, 1, 1))
setk(car, 577, interp="CONSTANT", scale=(0, 0, 0))

# ------------------------------------------------------------------ camera
cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
target = empty("Target")
tt = cam.constraints.new("TRACK_TO")
tt.target = target
tt.track_axis = "TRACK_NEGATIVE_Z"
tt.up_axis = "UP_Y"

# (start, end, cam_from, cam_to, target_from, target_to, lens_from, lens_to)
SHOTS = [
    (0, 50, (-1.2, -3.6, 1.6), (0.3, -3.4, 1.4), (-2.5, 2.1, 1.2), (-0.3, 0.3, 0.95), 32, 32),
    (50, 79, (0.25, -2.3, 1.3), (0.15, -1.75, 1.15), (0, 0, 1.15), (0, 0, 1.0), 40, 45),
    (80, 217, (2.4, -5.5, 2.4), (1.4, -4.4, 1.4), (0, 0, 0.6), (0, 0, 0.3), 32, 32),
    (218, 377, (0, -4.6, 0.1), (0, -3.9, -0.1), (0, 0, -0.4), (0, 0, -0.45), 32, 32),
    (378, 485, (0.5, -3.4, -0.45), (0.3, -3.0, -0.5), (0, 0, -0.5), (0, 0, -0.55), 32, 32),
    (486, 577, (0.5, -3.4, -0.45), (1.3, -6.6, 0.7), (0, 0, -0.55), (1.1, 0, 0.15), 32, 32),
    (578, 717, (2.6, -3.0, 1.4), (1.9, -2.3, 1.05), (0, 0, 0.35), (0, 0, 0.25), 32, 35),
    (718, 884, (-0.4, -4.4, 3.8), (-1.6, -4.6, 3.6), (-0.4, 0, 0.0), (-1.9, 0, 0.0), 32, 32),
]
for s, e, c0, c1, t0, t1, l0, l1 in SHOTS:
    setk(cam, s, location=c0)
    setk(target, s, location=t0)
    cam_data.lens = l0
    cam_data.keyframe_insert("lens", frame=s)
    setk(cam, e, interp="CONSTANT", location=c1)
    setk(target, e, interp="CONSTANT", location=t1)
    cam_data.lens = l1
    cam_data.keyframe_insert("lens", frame=e)
for fc in _fcurves(cam_data):
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"
for fc in _fcurves(cam):
    if fc.data_path == "location":
        n = fc.modifiers.new("NOISE")
        n.scale = 30
        n.strength = 0.03

# ------------------------------------------------------------------ render
scene.frame_start = args.start
scene.frame_end = args.end
scene.render.fps = FPS
scene.render.resolution_x = args.res
scene.render.resolution_y = int(args.res * 16 / 9)
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 4
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
