"""Procedural layered environments (runs inside Blender).

Each layer is drawn in *screen units* (16 x 9 at z=0) and placed at a depth z
with scale k = (D - z) / D, so it looks as designed when the camera is centered
but slides at a physically correct rate when the camera moves: real parallax.
Seeds make every environment reproducible, so the same street can return
in later episodes looking identical.
"""
import random

import bl_lib as L

INK = L.INK

PALETTES = {
    "dusk": {
        "sky": [(0.0, "#F6B26B"), (0.28, "#E88A7A"), (0.55, "#9E6E9E"), (1.0, "#2F3366")],
        "sun": "#FFE3A3", "sun_glow": "#FFC98A", "cloud": "#F4B9A8", "cloud_shade": "#D99AA0",
        "far": "#7B6E9E", "far2": "#8C7FAE", "mid": ["#5E5487", "#665C90", "#574D7E"],
        "lit": "#FFD98A", "lit_dim": "#E8B86B", "unlit": "#3F3A63",
        "street_bldg": ["#B65A45", "#3E7C7B", "#E2C9A0", "#3B4A73", "#C9784E"],
        "trim": "#F1E4CC", "sidewalk": "#B9A9A4", "sidewalk_dark": "#9C8C8C", "curb": "#8A7B80",
        "road": "#3D3650", "lamp": "#2E2A45", "lamp_glow": "#FFE6A8", "tree": "#3F7A5A", "tree_dark": "#2F5E47",
        "trunk": "#5A4038",
    }
}


def layer(name, z, D):
    k = (D - z) / D
    g = L.empty(f"layer.{name}", (0, 0, z))
    g.scale = (k, k, 1)
    return g


def build(cfg, fonts, D):
    kind = cfg.get("kind", "solid")
    if kind == "solid":
        bg = L.rect("bg", -60, -40, 60, 40, cfg.get("color", "#EDE6DA"), -80)
        bg.scale = (5, 5, 1)
        if cfg.get("floor"):
            L.rect("floor", -60, -10, 60, cfg["floor"], cfg.get("floor_color", "#D9CFBF"), -1)
        return
    if kind == "city_dusk":
        return city_dusk(cfg, fonts, D)
    raise ValueError(f"unknown background {kind}")


def _windows(rng, x0, x1, y0, y1, cols, rows, pal, lit_ratio, frame=None, prefix="w", parent=None, z=0.0,
             curtains=False):
    lit, unlit, frames, sills, curt = [], [], [], [], []
    cw = (x1 - x0) / cols
    rh = (y1 - y0) / rows
    for c in range(cols):
        for r in range(rows):
            wx0 = x0 + c * cw + cw * 0.22
            wx1 = x0 + (c + 1) * cw - cw * 0.22
            wy0 = y0 + r * rh + rh * 0.2
            wy1 = y0 + (r + 1) * rh - rh * 0.15
            (lit if rng.random() < lit_ratio else unlit).append((wx0, wy0, wx1, wy1))
            if frame:
                frames.append((wx0 - 0.04, wy0 - 0.04, wx1 + 0.04, wy1 + 0.04))
                sills.append((wx0 - 0.08, wy0 - 0.09, wx1 + 0.08, wy0 - 0.03))
            if curtains and rng.random() < 0.45:
                half = (wx1 - wx0) * rng.uniform(0.2, 0.35)
                curt.append((wx0, wy0, wx0 + half, wy1))
                curt.append((wx1 - half, wy0, wx1, wy1))
    if frames:
        L.rects_mesh(f"{prefix}.frames", frames, frame, z, parent)
        L.rects_mesh(f"{prefix}.sills", sills, pal["trim"], z + 0.002, parent)
    if lit:
        L.rects_mesh(f"{prefix}.lit", lit, pal["lit"], z + 0.001, parent)
    if unlit:
        L.rects_mesh(f"{prefix}.unlit", unlit, pal["unlit"], z + 0.001, parent)
    if curt:
        L.rects_mesh(f"{prefix}.curtains", curt, "#C76B5E", z + 0.0015, parent)
    return lit


def skyline(name, g, rng, x0, x1, base, hmin, hmax, colors, pal, win_ratio, wsize, z=0.0, detail=False):
    x = x0
    i = 0
    while x < x1:
        w = rng.uniform(0.8, 2.0) if not detail else rng.uniform(1.3, 2.6)
        h = rng.uniform(hmin, hmax)
        col = rng.choice(colors)
        L.rect(f"{name}.b{i}", x, base, x + w, base + h, col, z + 0.001 * (i % 3), g)
        if detail:
            # rooftop: parapet, water tower or antenna
            L.rect(f"{name}.cap{i}", x - 0.05, base + h, x + w + 0.05, base + h + 0.08, col, z + 0.004, g)
            r = rng.random()
            if r < 0.35:
                tx = x + w * rng.uniform(0.25, 0.6)
                L.rects_mesh(f"{name}.legs{i}", [(tx, base + h, tx + 0.04, base + h + 0.3),
                                                 (tx + 0.36, base + h, tx + 0.4, base + h + 0.3)], col, z + 0.003, g)
                L.shape(f"{name}.tank{i}", [(tx - 0.02, base + h + 0.28), (tx + 0.42, base + h + 0.28),
                                            (tx + 0.42, base + h + 0.72), (tx + 0.2, base + h + 0.86),
                                            (tx - 0.02, base + h + 0.72)], col, z + 0.003, g, None, smooth=False)
            elif r < 0.6:
                ax = x + w * 0.5
                L.rect(f"{name}.ant{i}", ax, base + h, ax + 0.03, base + h + rng.uniform(0.6, 1.2), col, z + 0.003, g)
        cols = max(2, int(w / wsize))
        rows = max(2, int(h / (wsize * 1.3)))
        _windows(rng, x + 0.1, x + w - 0.1, base + 0.2, base + h - 0.2, cols, rows, pal, win_ratio,
                 prefix=f"{name}.w{i}", parent=g, z=z + 0.005)
        x += w + rng.uniform(-0.15, 0.25)
        i += 1


def storefront_building(i, g, rng, x0, w, base, col, pal, fonts, sign=None, awning=None, rent=False,
                        fire_escape=False, floors=2):
    """Facade at storefront scale: ground floor 4.2 units (door ~0.7x a 5-unit character, set back
    in depth), upper floors 2.3 units each."""
    n = f"st{i}"
    gf, fh = 4.2, 2.3
    h = gf + floors * fh + 0.5
    L.rect(f"{n}.wall", x0, base, x0 + w, base + h, col, 0.0, g, INK, 0.035)
    if col in ("#B65A45", "#C9784E"):
        bricks = []
        for r in range(int((h - gf) / 0.3)):
            yy = base + gf + 0.2 + r * 0.3
            off = 0.2 if r % 2 else 0
            for c in range(int(w / 0.8)):
                if rng.random() < 0.14:
                    bx = x0 + off + c * 0.8
                    bricks.append((bx, yy, bx + 0.42, yy + 0.11))
        if bricks:
            L.rects_mesh(f"{n}.bricks", bricks, "#9E4A39" if col == "#B65A45" else "#B0663F", 0.002, g)
    L.rect(f"{n}.cornice", x0 - 0.15, base + h - 0.08, x0 + w + 0.15, base + h + 0.25, pal["trim"], 0.004, g,
           INK, 0.03)
    L.rect(f"{n}.cornice2", x0 - 0.06, base + h - 0.24, x0 + w + 0.06, base + h - 0.08, "#D9C9AE", 0.0035, g)
    if floors:
        cols = max(2, int(w / 1.45))
        _windows(rng, x0 + 0.2, x0 + w - 0.2, base + gf + 0.15, base + gf + 0.15 + floors * fh, cols, floors, pal,
                 0.55, frame="#F3EAD8" if col != "#E2C9A0" else "#8C5E4A", prefix=f"{n}.win", parent=g, z=0.003,
                 curtains=True)
    # ground floor: dark recess, shop window with shelves, door
    L.rect(f"{n}.store", x0 + 0.18, base, x0 + w - 0.18, base + gf - 0.45, "#2C2840", 0.003, g, INK, 0.03)
    gx0, gx1 = x0 + 0.38, x0 + w - 1.85
    L.rect(f"{n}.glass", gx0, base + 0.55, gx1, base + 3.1, "#FFE2A0", 0.004, g, INK, 0.028)
    L.rects_mesh(f"{n}.mull", [(gx0 + (gx1 - gx0) * t - 0.03, base + 0.55, gx0 + (gx1 - gx0) * t + 0.03, base + 3.1)
                               for t in (0.5,)], "#2C2840", 0.0045, g)
    shelf = []
    for sidx in range(3):
        yy = base + 0.9 + sidx * 0.72
        shelf.append((gx0 + 0.06, yy, gx1 - 0.06, yy + 0.06))
        for k in range(int((gx1 - gx0) / 0.3)):
            if rng.random() < 0.7:
                bx = gx0 + 0.1 + k * 0.3
                shelf.append((bx, yy + 0.06, bx + 0.18, yy + 0.06 + rng.uniform(0.15, 0.42)))
    L.rects_mesh(f"{n}.goods", shelf, "#E0A65E", 0.0042, g)
    dx0 = x0 + w - 1.6
    L.rect(f"{n}.door", dx0, base, dx0 + 1.25, base + 3.3, "#5B3B33", 0.004, g, INK, 0.028)
    L.rect(f"{n}.doorglass", dx0 + 0.18, base + 1.5, dx0 + 1.07, base + 3.0, "#FFE2A0", 0.0045, g)
    L.rect(f"{n}.knob", dx0 + 1.0, base + 1.45, dx0 + 1.1, base + 1.55, "#F2C94C", 0.005, g)
    L.rect(f"{n}.step", dx0 - 0.15, base - 0.05, dx0 + 1.4, base + 0.12, "#8E8088", 0.005, g, INK, 0.02)
    if awning:
        a0, a1, top, bot = x0 + 0.08, x0 + w - 0.08, base + 3.95, base + 3.3
        L.shape(f"{n}.awning", [(a0, top), (a1, top), (a1 + 0.15, bot), (a0 + 0.05, bot)], "#F7EDE2", 0.006, g, INK,
                0.03, smooth=False)
        nst = int((a1 - a0) / 0.42)
        stripes = [[(a0 + s * 0.42, top), (a0 + (s + 1) * 0.42, top), (a0 + (s + 1) * 0.42 + 0.06, bot),
                    (a0 + s * 0.42 + 0.06, bot)] for s in range(0, nst, 2)]
        L.polys_mesh(f"{n}.stripes", stripes, awning, 0.0065, g)
        L.polys_mesh(f"{n}.scallop", [L.ellipse_pts(a0 + 0.27 + s * 0.42, bot, 0.21, 0.1, 6) for s in range(nst)],
                     awning, 0.0062, g)
    if sign:
        sw = min(w - 0.5, 0.42 * len(sign) + 0.8)
        sx = x0 + w / 2
        L.rect(f"{n}.sign", sx - sw / 2, base + gf - 0.3, sx + sw / 2, base + gf + 0.45, "#2E2A45", 0.007, g, INK,
               0.03)
        L.text(f"{n}.signtxt", sign, 0.46, "#FFD98A", fonts["black"], 0.008, g, (sx, base + gf + 0.07), spacing=1.15)
    if rent and floors:
        bx, by = x0 + w * 0.5, base + gf + fh * 0.62
        L.rect(f"{n}.rent", bx - 1.15, by - 0.36, bx + 1.15, by + 0.36, "#FFFFFF", 0.008, g, INK, 0.03)
        L.text(f"{n}.renttxt", "FOR RENT", 0.34, "#D2453F", fonts["black"], 0.009, g, (bx, by))
    if fire_escape and floors:
        fx0, fx1 = x0 + w * 0.12, x0 + w * 0.5
        rails = []
        for fl in range(floors):
            yy = base + gf + 0.1 + fl * fh
            rails += [(fx0, yy, fx1, yy + 0.07), (fx0, yy + 0.6, fx1, yy + 0.64)]
            rails += [(fx0 + t * (fx1 - fx0), yy, fx0 + t * (fx1 - fx0) + 0.03, yy + 0.64) for t in
                      (0, 0.25, 0.5, 0.75, 1.0)]
        L.rects_mesh(f"{n}.fire", rails, "#2B2638", 0.006, g)
    return h


def alley(i, g, rng, x0, w, base, pal):
    """Gap between buildings: brick wall + tree, letting the skyline and sky show through."""
    L.rect(f"al{i}.wall", x0, base, x0 + w, base + 1.5, "#8E5A4C", -0.002, g, INK, 0.03)
    L.rects_mesh(f"al{i}.bricks", [(x0 + 0.1 + c * 0.55 + (0.25 if r % 2 else 0), base + 0.15 + r * 0.28,
                                    x0 + 0.42 + c * 0.55 + (0.25 if r % 2 else 0), base + 0.27 + r * 0.28)
                                   for r in range(5) for c in range(int(w / 0.55) - 1) if rng.random() < 0.5],
                 "#7A4A3F", -0.001, g)
    L.rect(f"al{i}.cap", x0 - 0.05, base + 1.5, x0 + w + 0.05, base + 1.65, "#B9A9A4", -0.0005, g, INK, 0.025)


def street_lamp(name, g, x, base, pal, glow=True):
    base += 2.0  # lamp is 5.6 units tall: geometry below is drawn from a raised origin
    L.rect(f"{name}.pole0", x - 0.07, base - 2.0, x + 0.07, base + 0.1, pal["lamp"], 0.0, g, INK, 0.025)
    L.rect(f"{name}.pole", x - 0.05, base, x + 0.05, base + 3.6, pal["lamp"], 0.0, g, INK, 0.025)
    L.rect(f"{name}.foot", x - 0.17, base - 2.0, x + 0.17, base - 1.7, pal["lamp"], 0.001, g, INK, 0.025)
    L.shape(f"{name}.arm", [(x, base + 3.55), (x + 0.35, base + 3.75), (x + 0.6, base + 3.65)], pal["lamp"], 0.001, g,
            INK, 0.02)
    L.shape(f"{name}.head", [(x + 0.38, base + 3.65), (x + 0.82, base + 3.65), (x + 0.72, base + 3.45),
                             (x + 0.48, base + 3.45)], pal["lamp"], 0.002, g, INK, 0.025, smooth=False)
    L.shape(f"{name}.bulb", L.ellipse_pts(x + 0.6, base + 3.43, 0.12, 0.05, 8), pal["lamp_glow"], 0.003, g, None)
    if glow:
        for j, (r, a) in enumerate(((0.24, 0.55), (0.42, 0.2))):
            L.shape(f"{name}.glow{j}", L.ellipse_pts(x + 0.6, base + 3.38, r, r * 0.8, 12), pal["lamp_glow"],
                    0.004 + j * 0.0005, g, None, alpha=a)


def tree(name, g, x, base, pal, rng):
    L.rect(f"{name}.planter", x - 0.45, base, x + 0.45, base + 0.35, "#6E5A55", 0.0, g, INK, 0.025)
    L.shape(f"{name}.trunk", [(x - 0.08, base + 0.3), (x + 0.08, base + 0.3), (x + 0.05, base + 1.6),
                              (x - 0.05, base + 1.6)], pal["trunk"], -0.001, g, INK, 0.022, smooth=False)
    L.shape(f"{name}.crown_b", L.bumpy_pts(x - 0.05, base + 2.3, 0.9, 13, 0.05, phase=rng.random()), pal["tree_dark"],
            0.001, g, INK, 0.03)
    L.shape(f"{name}.crown", L.bumpy_pts(x + 0.12, base + 2.45, 0.62, 11, 0.05, phase=rng.random()), pal["tree"],
            0.002, g, None)


def city_dusk(cfg, fonts, D):
    pal = PALETTES[cfg.get("palette", "dusk")]
    rng = random.Random(cfg.get("seed", 7))
    span = cfg.get("span", [-14, 16])  # screen-unit x range the camera may see
    horizon = cfg.get("horizon", -0.6)
    ground = cfg.get("ground_y", -3.2)

    sky = layer("sky", -140, D)
    sk = L.rect("sky.grad", -16, -6, 16, 7, "#000000", 0, sky)
    sk.data.materials[0] = L.gradient_material(pal["sky"])
    stars = [(rng.uniform(-15, 15), rng.uniform(4.0, 6.8)) for _ in range(40)]
    L.rects_mesh("sky.stars", [(x, y, x + 0.04, y + 0.04) for x, y in stars], "#FFF4D6", 0.01, sky, alpha=0.8)

    sun = layer("sun", -130, D)
    sx, sy = cfg.get("sun", [3.4, horizon + 0.6])
    for j, (r, a) in enumerate(((2.6, 0.12), (1.8, 0.2), (1.25, 0.35))):
        L.shape(f"sun.glow{j}", L.ellipse_pts(sx, sy, r, r, 16), pal["sun_glow"], j * 0.01, sun, None, alpha=a)
    L.shape("sun.disc", L.ellipse_pts(sx, sy, 0.95, 0.95, 16), pal["sun"], 0.05, sun, None)

    clouds = layer("clouds", -110, D)
    for i in range(7):
        cx, cy = rng.uniform(-14, 14), rng.uniform(1.8, 5.0)
        w = rng.uniform(1.8, 3.4)
        pts = [(cx - w, cy), (cx - w * 0.6, cy + 0.35), (cx - w * 0.1, cy + 0.6), (cx + w * 0.4, cy + 0.42),
               (cx + w, cy + 0.08), (cx + w * 0.9, cy - 0.1), (cx - w * 0.9, cy - 0.1)]
        L.shape(f"cloud{i}", pts, pal["cloud"], 0.01 * i, clouds, None, alpha=0.85)
        L.shape(f"cloud{i}.sh", [(cx - w * 0.85, cy - 0.02), (cx + w * 0.85, cy - 0.02), (cx + w * 0.6, cy - 0.12),
                                 (cx - w * 0.6, cy - 0.12)], pal["cloud_shade"], 0.01 * i + 0.002, clouds, None,
                alpha=0.7)

    far = layer("far", -70, D)
    skyline("far", far, rng, span[0] - 3, span[1] + 3, ground * D / (D + 70), 1.6, 3.6, [pal["far"], pal["far2"]], pal, 0.25,
            0.22)
    mid = layer("mid", -32, D)
    skyline("mid", mid, rng, span[0] - 3, span[1] + 3, ground * D / (D + 32), 2.6, 5.0, pal["mid"], pal, 0.35, 0.32,
            detail=True)

    # street-facing buildings right behind the sidewalk; bases sit on the perspective ground line
    zst = -7.0
    st = layer("street", zst, D)
    sbase = ground * D / (D - zst)
    x = span[0] - 2
    specs = cfg.get("lots", [
        {"sign": "LAUNDRY", "awning": "#3E7C7B", "floors": 2}, {"alley": 2.6},
        {"sign": "GROCERY", "awning": "#D2453F", "floors": 0},
        {"sign": None, "rent": True, "fire": True, "floors": 2}, {"sign": "BANK", "floors": 2},
        {"alley": 3.0}, {"sign": "COFFEE", "awning": "#E3A72F", "floors": 0},
        {"sign": "PHARMACY", "awning": "#3B4A73", "floors": 2}, {"sign": None, "rent": True, "floors": 2},
        {"alley": 2.4}, {"sign": "DINER", "awning": "#D2453F", "floors": 0},
    ])
    i = 0
    while x < span[1] + 3:
        sp = specs[i % len(specs)]
        if "alley" in sp:
            alley(i, st, rng, x, sp["alley"], sbase, pal)
            x += sp["alley"]
        else:
            w = rng.uniform(4.6, 5.6)
            col = pal["street_bldg"][i % len(pal["street_bldg"])]
            storefront_building(i, st, rng, x, w, sbase, col, pal, fonts, sp.get("sign"), sp.get("awning"),
                                sp.get("rent", False), sp.get("fire", False), sp.get("floors", 2))
            x += w + 0.06
        i += 1

    # sidewalk and furniture
    walk = layer("sidewalk", -2.5, D)
    L.rect("walk.back", span[0] - 4, ground - 0.4, span[1] + 4, sbase + 0.02, pal["sidewalk"], -0.01, walk)
    joints = [(xx, ground - 0.4, xx + 0.03, sbase) for xx in [span[0] - 4 + k * 1.6 for k in range(30)]]
    L.rects_mesh("walk.joints", joints, pal["sidewalk_dark"], -0.008, walk)
    L.rect("walk.edge", span[0] - 4, sbase - 0.04, span[1] + 4, sbase + 0.06, pal["sidewalk_dark"], -0.006, walk)
    furn = layer("furniture", -1.8, D)
    k = 0
    fo = cfg.get("furniture_offset", 0.0)
    for xx in range(int(span[0]) - 7, int(span[1]) + 6, 7):
        street_lamp(f"lamp{k}", furn, xx + 1.2 + fo, sbase - 0.15, pal)
        tree(f"tree{k}", furn, xx + 4.6 + fo, sbase - 0.15, pal, rng)
        k += 1
    for j, xx in enumerate(cfg.get("hydrants", [6.5])):
        hb = sbase - 0.15
        L.rect(f"hydrant{j}.body", xx - 0.17, hb + 0.12, xx + 0.17, hb + 0.85, "#D2453F", 0.0, furn, INK, 0.025)
        L.rect(f"hydrant{j}.base", xx - 0.24, hb, xx + 0.24, hb + 0.14, "#B23A35", 0.001, furn, INK, 0.025)
        L.shape(f"hydrant{j}.cap", L.ellipse_pts(xx, hb + 0.86, 0.2, 0.17, 8), "#D2453F", -0.001, furn, INK, 0.025)
        L.rect(f"hydrant{j}.nozzle", xx - 0.3, hb + 0.45, xx + 0.3, hb + 0.62, "#B23A35", -0.0015, furn, INK, 0.025)

    near = layer("near", 1.2, D)
    L.rect("curb", span[0] - 4, ground - 0.62, span[1] + 4, ground - 0.4, pal["curb"], 0.0, near, INK, 0.03)
    L.rect("road", span[0] - 4, -9, span[1] + 4, ground - 0.62, pal["road"], -0.001, near)
    marks = [(xx, ground - 1.6, xx + 1.2, ground - 1.5) for xx in [span[0] - 4 + k * 2.6 for k in range(16)]]
    L.rects_mesh("road.marks", marks, "#E9D9A6", 0.001, near, alpha=0.8)

    fg = layer("foreground", 6.0, D)
    for j, xx in enumerate(cfg.get("foreground_hedges", [-11.0, -3.5, 6.0, 13.0])):
        L.shape(f"fg.hedge{j}", L.bumpy_pts(xx, -4.95, 1.6, 12, 0.06, squash=0.55), "#24452F", 0.0, fg, INK, 0.04)
        L.shape(f"fg.hedge{j}.hi", L.bumpy_pts(xx + 0.3, -4.7, 0.9, 9, 0.06, squash=0.45), "#2F5A3D", 0.001, fg, None)
