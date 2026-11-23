"""Blender-side drawing toolkit for the flat 2D illustrated look.

Runs inside Blender. The world is drawn in the XY plane (x right, y up) and
viewed by a perspective camera looking down -Z, so depth (z) gives layering
and genuine parallax. Every shape is an unlit emission fill plus an optional
ink stroke, which reproduces a vector-illustration style with exact colors.
"""
import math

import bpy

_MATS = {}
_FONTS = {}
INK = "#2A2230"


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgba(h, alpha=1.0):
    h = h.lstrip("#")
    return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)) + (alpha,)


def material(color, alpha=1.0, unique=False):
    key = (color, round(alpha, 3))
    if not unique and key in _MATS:
        return _MATS[key]
    m = bpy.data.materials.new(f"m_{color}_{alpha:.2f}")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = hex_rgba(color)
    em.inputs["Strength"].default_value = 1.0
    if alpha < 1.0 or unique:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        mix.name = "alpha_mix"
        mix.inputs[0].default_value = alpha
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs[0])
        m.blend_method = "BLEND"
    else:
        nt.links.new(em.outputs[0], out.inputs[0])
        m.blend_method = "OPAQUE"
    m.shadow_method = "NONE"
    if not unique:
        _MATS[key] = m
    return m


def gradient_material(stops, axis="Y"):
    """stops: [(pos 0..1, hex)] along the object's generated coordinate axis."""
    m = bpy.data.materials.new("m_gradient")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = stops[0][0], hex_rgba(stops[0][1])
    els[1].position, els[1].color = stops[-1][0], hex_rgba(stops[-1][1])
    for pos, col in stops[1:-1]:
        e = els.new(pos)
        e.color = hex_rgba(col)
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs[axis], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], em.inputs[0])
    nt.links.new(em.outputs[0], out.inputs[0])
    m.shadow_method = "NONE"
    return m


def set_alpha(obj_or_mat, value, frame=None):
    m = obj_or_mat if isinstance(obj_or_mat, bpy.types.Material) else obj_or_mat.active_material
    node = m.node_tree.nodes.get("alpha_mix")
    node.inputs[0].default_value = value
    if frame is not None:
        node.inputs[0].keyframe_insert("default_value", frame=frame)


def link(ob, collection=None):
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


def empty(name, loc=(0, 0, 0), parent=None, collection=None):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = 0.15
    ob.location = loc
    ob.parent = parent
    return link(ob, collection)


def _bezier(name, pts, closed, smooth, dims="2D"):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = dims
    cu.resolution_u = 8
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = (p[0], p[1], 0.0)
        bp.handle_left_type = bp.handle_right_type = "AUTO" if smooth else "VECTOR"
    sp.use_cyclic_u = closed
    return cu


def shape(name, pts, color, z=0.0, parent=None, stroke=INK, lw=0.034, smooth=True, alpha=1.0,
          unique_mat=False, collection=None, loc=(0, 0)):
    """Filled closed shape with an optional ink outline."""
    cu = _bezier(name, pts, True, smooth)
    cu.fill_mode = "BOTH"
    ob = bpy.data.objects.new(name, cu)
    ob.data.materials.append(material(color, alpha, unique_mat))
    ob.location = (loc[0], loc[1], z)
    ob.parent = parent
    link(ob, collection)
    if stroke:
        ln = _bezier(name + "_ln", pts, True, smooth, "3D")
        ln.bevel_depth = lw / 2
        ln.bevel_resolution = 1
        lo = bpy.data.objects.new(name + "_ln", ln)
        lo.data.materials.append(material(stroke))
        lo.parent = ob
        lo.location = (0, 0, 0.0015)
        lo.scale = (1, 1, 0.02)
        link(lo, collection)
    return ob


def line(name, pts, color=INK, lw=0.034, z=0.0, parent=None, smooth=True, closed=False, collection=None,
         loc=(0, 0)):
    cu = _bezier(name, pts, closed, smooth, "3D")
    cu.bevel_depth = lw / 2
    cu.bevel_resolution = 2
    cu.use_fill_caps = True
    ob = bpy.data.objects.new(name, cu)
    ob.data.materials.append(material(color))
    ob.location = (loc[0], loc[1], z)
    ob.scale = (1, 1, 0.02)
    ob.parent = parent
    return link(ob, collection)


def ellipse_pts(cx, cy, rx, ry, n=8, rot=0.0):
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x, y = rx * math.cos(a), ry * math.sin(a)
        c, s = math.cos(rot), math.sin(rot)
        out.append((cx + x * c - y * s, cy + x * s + y * c))
    return out


def bumpy_pts(cx, cy, r, bumps=9, depth=0.12, n_per=3, phase=0.0, squash=1.0):
    out = []
    n = bumps * n_per
    for i in range(n):
        a = 2 * math.pi * i / n + phase
        rr = r * (1 + depth * math.cos(bumps * (a - phase)))
        out.append((cx + rr * math.cos(a), cy + rr * math.sin(a) * squash))
    return out


def capsule_pts(length, w0, w1, top_cap=0.9):
    """Tapered limb hanging from (0,0) down to (0,-length)."""
    return [(0, w0 * 0.5 * top_cap), (w0 * 0.5, 0), (w1 * 0.5, -length), (0, -length - w1 * 0.5 * top_cap),
            (-w1 * 0.5, -length), (-w0 * 0.5, 0)]


def rounded_rect_pts(x0, y0, x1, y1, r, seg=4):
    import math as _m
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    pts = []
    for cx, cy, a0 in ((x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180), (x1 - r, y0 + r, 270)):
        for k in range(seg + 1):
            a = _m.radians(a0 + 90 * k / seg)
            pts.append((cx + r * _m.cos(a), cy + r * _m.sin(a)))
    return pts


def rect_pts(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def rect(name, x0, y0, x1, y1, color, z=0.0, parent=None, stroke=None, lw=0.03, alpha=1.0, collection=None):
    return shape(name, rect_pts(x0, y0, x1, y1), color, z, parent, stroke, lw, smooth=False, alpha=alpha,
                 collection=collection)


def rects_mesh(name, rects, color, z=0.0, parent=None, alpha=1.0, collection=None):
    """Many axis-aligned rectangles as ONE mesh (fast for windows, bricks, stripes)."""
    verts, faces = [], []
    for (x0, y0, x1, y1) in rects:
        i = len(verts)
        verts += [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)]
        faces.append((i, i + 1, i + 2, i + 3))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(material(color, alpha))
    ob.location.z = z
    ob.parent = parent
    return link(ob, collection)


def polys_mesh(name, polys, color, z=0.0, parent=None, alpha=1.0, collection=None):
    verts, faces = [], []
    for poly in polys:
        i = len(verts)
        verts += [(x, y, 0) for x, y in poly]
        faces.append(tuple(range(i, i + len(poly))))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(material(color, alpha))
    ob.location.z = z
    ob.parent = parent
    return link(ob, collection)


def font(path):
    if path not in _FONTS:
        _FONTS[path] = bpy.data.fonts.load(path)
    return _FONTS[path]


def text(name, body, size, color, font_path, z=0.0, parent=None, loc=(0, 0), align="CENTER",
         collection=None, spacing=1.0, alpha=1.0):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.font = font(font_path)
    cu.align_x = align
    cu.align_y = "CENTER"
    cu.space_character = spacing
    ob = bpy.data.objects.new(name, cu)
    ob.data.materials.append(material(color, alpha))
    ob.location = (loc[0], loc[1], z)
    ob.parent = parent
    return link(ob, collection)


def key_transform(ob, frame, loc=None, rot_deg=None, scale=None):
    if loc is not None:
        ob.location[0], ob.location[1] = loc[0], loc[1]
        ob.keyframe_insert("location", frame=frame, index=0)
        ob.keyframe_insert("location", frame=frame, index=1)
    if rot_deg is not None:
        ob.rotation_euler[2] = math.radians(rot_deg)
        ob.keyframe_insert("rotation_euler", frame=frame, index=2)
    if scale is not None:
        sx, sy = scale if isinstance(scale, (tuple, list)) else (scale, scale)
        ob.scale[0], ob.scale[1] = sx, sy
        ob.keyframe_insert("scale", frame=frame, index=0)
        ob.keyframe_insert("scale", frame=frame, index=1)


def key_visible(ob, frame, visible):
    ob.hide_render = not visible
    ob.keyframe_insert("hide_render", frame=frame)
    for child in ob.children_recursive:
        child.hide_render = not visible
        child.keyframe_insert("hide_render", frame=frame)


def constant_interpolation(obs):
    for ob in obs:
        ad = ob.animation_data
        if ad and ad.action:
            for fc in ad.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"


def linear_interpolation(obs):
    for ob in obs:
        ad = ob.animation_data
        if ad and ad.action:
            for fc in ad.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
