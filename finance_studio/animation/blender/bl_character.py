"""Cut-out character rig builder (runs inside Blender).

Builds a joint hierarchy of empties that matches animation/motion.py exactly:

  root (x, y, facing) -> hip -> torso -> head
                                     -> shoulder_f -> arm_f_up -> arm_f_lo -> hand_f
                                     -> shoulder_b -> arm_b_up -> arm_b_lo -> hand_b
                             -> leg_f_up -> leg_f_lo -> foot_f
                             -> leg_b_up -> leg_b_lo -> foot_b

Body parts are drawn in each joint's local space, so poses never distort the
design - Maya keeps identical proportions, clothing and colors in every shot.
"""
import math

import bl_lib as L

DZ = 0.006  # depth step between stacked parts


def build(spec, name="maya", collection=None):
    P, sk, lw = spec["palette"], spec["skeleton"], spec["line_width"]
    ink = P["outline"]
    J = {}

    def E(jn, loc, parent, z=0.0):
        J[jn] = L.empty(f"{name}.{jn}", (loc[0], loc[1], z), parent, collection)
        return J[jn]

    def S(n, pts, col, z, parent, stroke=ink, smooth=True, alpha=1.0, w=lw):
        return L.shape(f"{name}.{n}", pts, col, z, parent, stroke, w, smooth, alpha, collection=collection)

    def LN(n, pts, z, parent, col=ink, w=lw, smooth=True, closed=False):
        return L.line(f"{name}.{n}", pts, col, w, z, parent, smooth, closed, collection=collection)

    root = E("root", (0, 0), None)
    hx, hy = sk["hip"]
    hip = E("hip", (hx, hy), root)
    torso = E("torso", (0, 0), hip, 0.0)

    # ---------------- legs (back leg behind everything, front leg behind torso)
    for side, zoff in (("b", -10 * DZ), ("f", -6 * DZ)):
        hp = sk["hip_back" if side == "b" else "hip_front"]
        thigh = E(f"leg_{side}_up", (hp[0] - hx, hp[1] - hy), hip, zoff)
        shin = E(f"leg_{side}_lo", (0, -sk["thigh"]), thigh, -DZ)
        foot = E(f"foot_{side}", (0, -sk["shin"]), shin, -DZ)
        dark = side == "b"
        pc = P["pants_shadow"] if dark else P["pants"]
        S(f"thigh_{side}", L.capsule_pts(sk["thigh"], 0.36, 0.28), pc, 0, thigh)
        S(f"shin_{side}", L.capsule_pts(sk["shin"], 0.28, 0.25), pc, 0, shin)
        S(f"cuff_{side}", L.rect_pts(-0.15, -sk["shin"] + 0.02, 0.15, -sk["shin"] + 0.12), P["pants_shadow"], DZ * 0.5,
          shin, smooth=False)
        a = sk["ankle_height"]
        shoe = [(-0.15, 0.04), (0.06, 0.06), (0.22, -0.02), (0.36, -0.06), (0.38, -a + 0.02),
                (0.3, -a - 0.02), (-0.16, -a - 0.02), (-0.18, -0.03)]
        S(f"shoe_{side}", shoe, P["shoe"] if not dark else "#DCD6CC", DZ, foot)
        S(f"sole_{side}", [(-0.17, -a + 0.025), (0.37, -a + 0.025), (0.3, -a - 0.02), (-0.16, -a - 0.02)],
          P["shoe_sole"], 2 * DZ, foot, smooth=False)
        LN(f"lace_{side}", [(0.04, 0.0), (0.12, -0.03), (0.2, -0.05)], 3 * DZ, foot, w=lw * 0.7)

    # pelvis piece covers the top of the legs
    S("pelvis", [(-0.38, 0.12), (0.37, 0.12), (0.4, -0.1), (0.25, -0.3), (-0.25, -0.3), (-0.41, -0.1)],
      P["pants"], -3 * DZ, hip)
    LN("belt", [(-0.38, 0.06), (0.0, 0.03), (0.38, 0.06)], -2.5 * DZ, hip, col=P["pants_shadow"], w=lw * 0.8)

    # ---------------- back arm (behind torso)
    def arm(side, z):
        sh = sk["shoulder_back" if side == "b" else "shoulder_front"]
        shoulder = E(f"shoulder_{side}", (sh[0] - hx, sh[1] - hy), torso, z)
        up = E(f"arm_{side}_up", (0, 0), shoulder)
        lo = E(f"arm_{side}_lo", (0, -sk["upper_arm"]), up, -DZ)
        hand = E(f"hand_{side}", (0, -sk["forearm"]), lo, -DZ)
        col = P["sweater_shadow"] if side == "b" else P["sweater"]
        S(f"upper_{side}", L.capsule_pts(sk["upper_arm"], 0.22, 0.185, 0.7), col, 0, up)
        S(f"fore_{side}", L.capsule_pts(sk["forearm"] - 0.02, 0.185, 0.16, 0.7), col, 0, lo)
        S(f"wristband_{side}", L.capsule_pts(0.1, 0.175, 0.17, 0.2), P["sweater_shadow"], DZ * 0.5, lo,
          stroke=None)
        skin = P["skin_shadow"] if side == "b" else P["skin"]
        hs = L.empty(f"{name}.handshape_{side}", (0, 0.02, 0), hand, collection)
        hs.scale = (1.3, 1.3, 1)
        J[f"handshape_{side}"] = hs
        S(f"palm_{side}", [(-0.09, 0.02), (0.09, 0.02), (0.11, -0.12), (0.05, -0.21), (-0.05, -0.21), (-0.1, -0.1)],
          skin, -DZ, hs)
        S(f"thumb_{side}", L.ellipse_pts(0.095, -0.07, 0.035, 0.07, 6, 0.5), skin, 2 * DZ, hs)
        LN(f"finger_{side}", [(-0.03, -0.1), (-0.03, -0.18)], DZ * 0.5, hs, w=lw * 0.6)
        return hand

    arm("b", -8 * DZ)

    # ---------------- torso
    tl = sk["torso_len"]
    body = [(-0.38, -0.06), (0.38, -0.06), (0.43, 0.5), (0.46, 1.05), (0.36, 1.38), (0.1, 1.5),
            (-0.24, 1.49), (-0.43, 1.33), (-0.46, 0.85), (-0.42, 0.35)]
    S("sweater", body, P["sweater"], 0, torso)
    S("sweater_shade", [(-0.4, -0.04), (-0.2, -0.04), (-0.24, 0.6), (-0.27, 1.2), (-0.38, 1.36), (-0.45, 0.9),
                        (-0.42, 0.35)], P["sweater_shadow"], DZ, torso, stroke=None)
    S("hem", [(-0.39, -0.07), (0.39, -0.07), (0.4, 0.08), (-0.4, 0.08)], P["sweater_shadow"], 2 * DZ, torso,
      smooth=False)
    LN("rib1", [(-0.25, -0.05), (-0.25, 0.06)], 3 * DZ, torso, w=lw * 0.5)
    LN("rib2", [(0.0, -0.05), (0.0, 0.06)], 3 * DZ, torso, w=lw * 0.5)
    LN("rib3", [(0.25, -0.05), (0.25, 0.06)], 3 * DZ, torso, w=lw * 0.5)
    LN("fold", [(0.22, 0.55), (0.28, 0.8), (0.24, 1.0)], 3 * DZ, torso, col=P["sweater_shadow"], w=lw * 0.9)
    # neck + collar
    nk = sk["neck"]
    S("neck", [(nk[0] - 0.13 - hx, nk[1] - hy - 0.12), (nk[0] + 0.13 - hx, nk[1] - hy - 0.12),
               (nk[0] + 0.12 - hx, nk[1] - hy + 0.25), (nk[0] - 0.12 - hx, nk[1] - hy + 0.25)],
      P["skin_shadow"], -DZ, torso, smooth=False)
    cy = nk[1] - hy
    S("collar_l", [(-0.2, cy + 0.01), (0.04, cy - 0.17), (0.06, cy - 0.04), (-0.12, cy + 0.06)], P["collar"],
      4 * DZ, torso, smooth=False)
    S("collar_r", [(0.32, cy + 0.0), (0.08, cy - 0.17), (0.06, cy - 0.04), (0.24, cy + 0.06)], P["collar"],
      4 * DZ, torso, smooth=False)

    # ---------------- head
    hp = sk["head_pivot"]
    head = E("head", (hp[0] - hx, hp[1] - hy), torso, 5 * DZ)
    head.scale = (1.1, 1.1, 1)  # stylized: slightly larger head keeps expressions readable
    hcx, hcy = sk["head_center"]
    H = lambda x, y: (hcx + x, hcy + y)  # noqa: E731 - head-centre helper
    hair_back = L.bumpy_pts(*H(-0.07, 0.1), 0.6, bumps=11, depth=0.07, phase=0.3, squash=0.95)
    S("hair_back", hair_back, P["hair"], -3 * DZ, head)
    S("bun", L.bumpy_pts(*H(-0.22, 0.66), 0.27, bumps=8, depth=0.1, phase=0.2), P["hair"], -4 * DZ, head)
    S("bun_hi", L.ellipse_pts(*H(-0.27, 0.72), 0.08, 0.05, 6, 0.4), P["hair_light"], -3.5 * DZ, head, stroke=None)
    face = [H(-0.43, 0.2), H(-0.38, 0.45), H(-0.1, 0.58), H(0.26, 0.54), H(0.49, 0.32), H(0.55, 0.02),
            H(0.5, -0.24), H(0.3, -0.44), H(0.1, -0.53), H(-0.14, -0.49), H(-0.34, -0.3)]
    S("face", face, P["skin"], 0, head)
    S("jaw_shade", [H(-0.42, 0.05), H(-0.3, -0.05), H(-0.18, -0.35), H(-0.04, -0.5), H(-0.16, -0.48), H(-0.34, -0.3)],
      P["skin_shadow"], DZ * 0.4, head, stroke=None)
    S("ear", L.ellipse_pts(*H(-0.33, -0.02), 0.085, 0.13, 7), P["skin"], DZ, head)
    LN("ear_in", [H(-0.31, 0.06), H(-0.35, 0.0), H(-0.31, -0.07)], 1.5 * DZ, head, col=P["skin_shadow"], w=lw * 0.8)
    LN("earring", L.ellipse_pts(*H(-0.33, -0.19), 0.05, 0.055, 8), 1.2 * DZ, head, col=P["earring"], w=lw * 0.9,
       closed=True)
    # hair front (hairline with curls) sits over the forehead
    hf = [H(-0.5, 0.2), H(-0.46, 0.52), H(-0.2, 0.7), H(0.18, 0.69), H(0.46, 0.5), H(0.53, 0.32), H(0.38, 0.36),
          H(0.24, 0.3), H(0.1, 0.37), H(-0.06, 0.29), H(-0.24, 0.33), H(-0.36, 0.1)]
    S("hair_front", hf, P["hair"], 3 * DZ, head)
    for k, (cx, cy) in enumerate(((-0.52, 0.3), (-0.45, -0.05), (-0.3, 0.5))):
        LN(f"hair_curl{k}", [H(cx, cy), H(cx - 0.06, cy - 0.06), H(cx, cy - 0.12)], -2.5 * DZ, head,
           col=P["hair_light"], w=lw * 0.8)

    # eyes: group empty scaled in Y for blinks/eye-open; pupil empty slides for gaze
    def eye(tag, cx, cy, rx, ry):
        grp = E(f"eye_{tag}", H(cx, cy), head, 2 * DZ)
        S(f"sclera_{tag}", L.ellipse_pts(0, 0, rx, ry, 8), P["eye_white"], 0, grp, w=lw * 0.55)
        pup = E(f"pupil_{tag}", (0, 0), grp, DZ)
        S(f"iris_{tag}", L.ellipse_pts(0, 0, rx * 0.74, ry * 0.72, 8), P["iris"], 0, pup, stroke=None)
        S(f"glint_{tag}", L.ellipse_pts(rx * 0.2, ry * 0.25, rx * 0.2, ry * 0.18, 6), "#FFFFFF", DZ * 0.5, pup,
          stroke=None)
        LN(f"lash_{tag}", [(-rx * 1.05, ry * 0.1), (-rx * 0.5, ry * 0.95), (rx * 0.4, ry * 1.0), (rx * 1.15, ry * 0.35)],
           2.5 * DZ, grp, w=lw * 1.1)
        J[f"eye_{tag}_r"] = (rx, ry)

    eye("f", 0.04, 0.04, 0.095, 0.115)   # near eye - larger
    eye("b", 0.31, 0.04, 0.065, 0.105)   # far eye - foreshortened
    for tag, bx, by, ln in (("f", 0.04, 0.185, 0.11), ("b", 0.32, 0.185, 0.07)):
        brow = E(f"brow_{tag}", H(bx, by), head, 3.5 * DZ)
        LN(f"brow_{tag}_ln", [(-ln, -0.01), (0, 0.022), (ln, 0.0)], 0, brow, col="#1A0F0B", w=lw * 1.5)
    LN("nose", [H(0.21, -0.0), H(0.27, -0.1), H(0.2, -0.13)], 1.5 * DZ, head, col=P["skin_shadow"], w=lw * 1.1)
    blush = E("blush", H(0.0, -0.15), head, 1.2 * DZ)
    S("blush_f", L.ellipse_pts(0, 0, 0.09, 0.045, 8), P["blush"], 0, blush, stroke=None, alpha=0.55)
    S("blush_b", L.ellipse_pts(0.32, 0.0, 0.05, 0.04, 8), P["blush"], 0, blush, stroke=None, alpha=0.55)

    # mouths: one child per shape, visibility switched per frame
    mouth = E("mouth", H(0.22, -0.27), head, 2 * DZ)
    M = {}

    def mshape(key, pts, fill=None, z=0.0, closed=False, teeth=None, tongue=None):
        grp = L.empty(f"{name}.mouth_{key}", (0, 0, z), mouth, collection)
        if fill:
            S(f"m_{key}", pts, fill, 0, grp, w=lw * 0.9)
            if teeth:
                S(f"m_{key}_teeth", teeth, P["teeth"], DZ * 0.5, grp, stroke=None, smooth=False)
            if tongue:
                S(f"m_{key}_tongue", tongue, P["tongue"], DZ * 0.4, grp, stroke=None)
        else:
            LN(f"m_{key}", pts, 0, grp, w=lw * 1.05)
        M[key] = grp

    mshape("rest", [(-0.08, 0.0), (0.0, -0.01), (0.07, 0.004)])
    mshape("smile", [(-0.1, 0.03), (-0.02, -0.03), (0.06, -0.02), (0.1, 0.035)])
    mshape("smirk", [(-0.08, -0.012), (0.0, -0.006), (0.08, 0.035)])
    mshape("frown", [(-0.08, -0.03), (0.0, 0.012), (0.075, -0.025)])
    mshape("grin", [(-0.11, 0.03), (0.1, 0.035), (0.06, -0.06), (-0.04, -0.07)], P["mouth_inside"],
           teeth=[(-0.09, 0.028), (0.09, 0.032), (0.075, 0.0), (-0.08, -0.002)],
           tongue=L.ellipse_pts(0.0, -0.045, 0.045, 0.02, 6))
    mshape("gasp", L.ellipse_pts(0, -0.01, 0.045, 0.06, 8), P["mouth_inside"],
           tongue=L.ellipse_pts(0.0, -0.045, 0.025, 0.012, 6))
    mshape("small", L.ellipse_pts(0, -0.005, 0.05, 0.022, 8), P["mouth_inside"])
    mshape("open", L.ellipse_pts(0, -0.02, 0.07, 0.055, 8), P["mouth_inside"],
           tongue=L.ellipse_pts(0.0, -0.05, 0.04, 0.018, 6))
    mshape("round", L.ellipse_pts(0, -0.01, 0.04, 0.05, 8), P["mouth_inside"])
    mshape("wide", L.ellipse_pts(0, -0.005, 0.09, 0.035, 8), P["mouth_inside"],
           teeth=[(-0.075, 0.02), (0.075, 0.02), (0.07, 0.0), (-0.07, 0.0)])
    J["mouths"] = M

    # ---------------- front arm (in front of torso and head)
    arm("f", 12 * DZ)
    return J


def apply_channels(J, ch, start_frame=1):
    """Keyframe every frame of baked motion channels onto the rig."""
    n = len(ch["x"])
    rot_nodes = {"torso": "torso", "head": "head", "arm_f_up": "arm_f_up", "arm_f_lo": "arm_f_lo",
                 "hand_f": "hand_f", "arm_b_up": "arm_b_up", "arm_b_lo": "arm_b_lo", "hand_b": "hand_b",
                 "leg_f_up": "leg_f_up", "leg_f_lo": "leg_f_lo", "foot_f": "foot_f", "leg_b_up": "leg_b_up",
                 "leg_b_lo": "leg_b_lo", "foot_b": "foot_b"}
    root = J["root"]
    mouths = J["mouths"]
    brow_base = {t: J[f"brow_{t}"].location[1] for t in ("f", "b")}
    for i in range(n):
        f = start_frame + i
        L.key_transform(root, f, loc=(ch["x"][i], ch["y"][i] + ch.get("ground", [0] * n)[i]))
        root.scale[0] = ch["facing"][i]
        root.keyframe_insert("scale", frame=f, index=0)
        for chan, node in rot_nodes.items():
            L.key_transform(J[node], f, rot_deg=ch[chan][i])
        eo = max(ch["eye_open"][i], 0.06)
        for tag in ("f", "b"):
            L.key_transform(J[f"eye_{tag}"], f, scale=(1.0, eo))
            rx, ry = J[f"eye_{tag}_r"]
            L.key_transform(J[f"pupil_{tag}"], f, loc=(ch["pupil_dx"][i] * rx * 0.38, ch["pupil_dy"][i] * ry * 0.3))
        for tag in ("f", "b"):
            brow = J[f"brow_{tag}"]
            brow.location[1] = brow_base[tag] + ch[f"brow_{tag}_dy"][i]
            brow.keyframe_insert("location", frame=f, index=1)
            brow.rotation_euler[2] = math.radians(ch[f"brow_{tag}_rot"][i])
            brow.keyframe_insert("rotation_euler", frame=f, index=2)
        bl = max(ch["blush"][i], 0.001)
        L.key_transform(J["blush"], f, scale=(bl, bl))
        cur = ch["mouth"][i]
        prev = ch["mouth"][i - 1] if i else None
        if cur != prev:
            for k, ob in mouths.items():
                L.key_visible(ob, f, k == cur)
    L.linear_interpolation([J[n] for n in rot_nodes.values()] + [root])
    L.constant_interpolation(list(mouths.values()) + [c for m in mouths.values() for c in m.children_recursive])
