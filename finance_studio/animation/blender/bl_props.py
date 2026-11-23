"""Reusable financial props and their per-frame animation (runs inside Blender)."""
import math

import bl_lib as L

INK = L.INK


def _apply_tracks(ob, tracks, start, mats=None):
    n = max((len(v) for v in tracks.values() if isinstance(v, list)), default=0)
    prev_vis = None
    for i in range(n):
        f = start + i
        if "x" in tracks:
            L.key_transform(ob, f, loc=(tracks["x"][i], tracks["y"][i]))
        if "rot" in tracks:
            L.key_transform(ob, f, rot_deg=tracks["rot"][i])
        if "s" in tracks:
            s = max(tracks["s"][i], 0.0005)
            L.key_transform(ob, f, scale=(s, s))
        if "alpha" in tracks and mats:
            for m in mats:
                L.set_alpha(m, tracks["alpha"][i], f)
        if "visible" in tracks:
            v = bool(tracks["visible"][i])
            if v != prev_vis:
                L.key_visible(ob, f, v)
                prev_vis = v
    L.linear_interpolation([ob])
    if "visible" in tracks:
        L.constant_interpolation([ob] + list(ob.children_recursive))


def ground_shadow(cid, ch, start, ground_y, z):
    sh = L.shape(f"{cid}.shadow", L.ellipse_pts(0, 0, 0.85, 0.12, 10), "#1B1530", z - 0.35, None, None,
                 alpha=0.28)
    xs = ch["x"]
    for i, x in enumerate(xs):
        lift = ch["y"][i] - ground_y
        sh.location = (x + 0.05 * ch["facing"][i], ground_y + 0.0, z - 0.35)
        sh.keyframe_insert("location", frame=start + i)
        k = max(0.6, 1.0 - max(lift, 0) * 0.5)
        sh.scale = (k, k, 1)
        sh.keyframe_insert("scale", frame=start + i)
    L.linear_interpolation([sh])


def paycheck(name, fonts, parent=None):
    g = L.empty(name, (0, 0, 0), parent)
    L.shape(f"{name}.paper", L.rect_pts(-0.04, -0.2, 0.74, 0.2), "#E6F2DC", 0, g, INK, 0.03, smooth=False)
    L.rect(f"{name}.band", -0.04, 0.1, 0.74, 0.2, "#6DBB75", 0.003, g)
    L.text(f"{name}.label", "PAYCHECK", 0.075, "#FFFFFF", fonts["black"], 0.006, g, (0.35, 0.152), spacing=1.1)
    L.shape(f"{name}.coin", L.ellipse_pts(0.1, -0.04, 0.085, 0.085, 10), "#2E8B57", 0.004, g, INK, 0.022)
    L.text(f"{name}.dollar", "$", 0.13, "#FFFFFF", fonts["black"], 0.008, g, (0.1, -0.045))
    L.rects_mesh(f"{name}.lines", [(0.25, -0.0, 0.66, 0.02), (0.25, -0.07, 0.6, -0.05), (0.25, -0.14, 0.5, -0.12)],
                 "#9DB59A", 0.004, g)
    L.line(f"{name}.sig", [(0.48, -0.15), (0.53, -0.11), (0.57, -0.16), (0.62, -0.12), (0.68, -0.15)],
           "#3B6E8F", 0.014, 0.005, g)
    return g


def badge(name, fonts, label, color="#2FA866", parent=None, width=1.9):
    g = L.empty(name, (0, 0, 0), parent)
    w, h = max(width, 0.25 * len(label) + 0.7), 0.62
    L.shape(f"{name}.body", L.rounded_rect_pts(-w / 2, -h / 2, w / 2, h / 2, h / 2), color, 0, g, INK, 0.04,
            smooth=False)
    L.shape(f"{name}.tail", [(-0.16, -h / 2 + 0.06), (0.14, -h / 2 + 0.06), (-0.12, -h / 2 - 0.26)], color, -0.006,
            g, INK, 0.04, smooth=False)
    L.text(f"{name}.txt", label, 0.34, "#FFFFFF", fonts["black"], 0.004, g, (0, -0.01))
    return g


def up_arrow(name, color, parent, loc, size=0.3, z=0.006):
    s = size
    pts = [(0, s), (s * 0.75, 0.05 * s), (s * 0.28, 0.05 * s), (s * 0.28, -s), (-s * 0.28, -s), (-s * 0.28, 0.05 * s),
           (-s * 0.75, 0.05 * s)]
    pts = [(x + loc[0], y + loc[1]) for x, y in pts]
    return L.shape(name, pts, color, z, parent, INK, 0.03, smooth=False)


def price_tag(name, fonts, label, color="#F25C54", parent=None, width=2.3):
    g = L.empty(name, (0, 0, 0), parent)
    w, h = width, 0.78
    pts = [(-w / 2 - 0.32, 0), (-w / 2, h / 2), (w / 2, h / 2), (w / 2, -h / 2), (-w / 2, -h / 2)]
    L.shape(f"{name}.body", pts, color, 0, g, INK, 0.045, smooth=False)
    L.shape(f"{name}.hole", L.ellipse_pts(-w / 2 - 0.06, 0, 0.07, 0.07, 8), "#F7EDE2", 0.004, g, INK, 0.025)
    L.line(f"{name}.string", [(-w / 2 - 0.06, 0.05), (-w / 2 - 0.25, 0.45), (-w / 2 - 0.2, 0.9)], INK, 0.025,
           -0.002, g)
    L.text(f"{name}.txt", label, 0.4, "#FFFFFF", fonts["black"], 0.005, g, (-0.22, -0.01))
    up_arrow(f"{name}.arrow", "#FFFFFF", g, (w / 2 - 0.36, 0.0), 0.26)
    return g


def puff(name, n=7, seed=1):
    """Poof cloud particles, each with its own fading material."""
    import random
    rng = random.Random(seed)
    g = L.empty(name, (0, 0, 0))
    mats, parts = [], []
    for i in range(n):
        a = 2 * math.pi * i / n + rng.uniform(-0.3, 0.3)
        ob = L.shape(f"{name}.p{i}", L.bumpy_pts(0, 0, 0.22 + rng.uniform(0, 0.1), 7, 0.1), "#FFFFFF",
                     0.01 * i, g, None, alpha=1.0, unique_mat=True)
        ob["dir"] = (math.cos(a), math.sin(a))
        mats.append(ob.active_material)
        parts.append(ob)
    return g, parts, mats


def build_prop(p, rigs, fonts, start):
    kind, pid = p["kind"], p["id"]
    parent = None
    if p.get("attach"):
        at = p["attach"]
        parent = rigs[at["character"]][at["joint"]]
    if kind == "paycheck":
        ob = paycheck(pid, fonts, parent)
    elif kind == "badge":
        ob = badge(pid, fonts, p["label"], p.get("color", "#2FA866"), parent, p.get("width", 1.9))
    elif kind == "price_tag":
        ob = price_tag(pid, fonts, p["label"], p.get("color", "#F25C54"), parent, p.get("width", 2.3))
    elif kind == "puff":
        g, parts, mats = puff(pid, p.get("count", 7), p.get("seed", 1))
        tr = p["tracks"]
        _apply_tracks(g, {"x": tr["x"], "y": tr["y"]}, start)
        prog = tr["progress"]
        for ob, m in zip(parts, mats):
            dx, dy = ob["dir"]
            for i, pr in enumerate(prog):
                f = start + i
                r = 0.15 + 1.1 * pr
                L.key_transform(ob, f, loc=(dx * r, dy * r * 0.8 + 0.25 * pr), scale=0.3 + 0.9 * pr if pr > 0 else 0.001)
                L.set_alpha(m, (1 - pr) ** 1.5 if pr > 0 else 0.0, f)
            L.linear_interpolation([ob])
        return g
    else:
        raise ValueError(f"unknown prop kind {kind}")
    if p.get("attach"):
        at = p["attach"]
        ob.location = (at.get("offset", [0, 0])[0], at.get("offset", [0, 0])[1], at.get("z", 0.004))
        ob.rotation_euler[2] = math.radians(at.get("rot", 0))
    else:
        ob.location.z = p.get("z", 0.5)
    if p.get("tracks"):
        _apply_tracks(ob, p["tracks"], start)
    return ob
