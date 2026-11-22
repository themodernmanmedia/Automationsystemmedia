"""Stylised 3D humans + cinematic arena world for engine_hd.

API mirrors world3d (build_world, person, crowd, poof, gem_pile, chest, ...)
so an episode can switch art style by swapping one import.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

import numpy as np

from .engine_hd import (CLOTH, EYE, GEM, GOLD, GRASS, HAIR, LAVA, PLAIN, SKIN, STONE, WOOD, Scene, mesh_annulus,
                        mesh_cylinder, mesh_terrain, mesh_torus)
from .engine3d import RX, RY, RZ, S, T
from .world3d import ARMS, EXPR, Pose, Style, arrow, bed, chest, golden_house, target  # noqa: F401  (re-export)
from .world3d import SHIRTS, SKINS, HAIRS

TAU = math.tau
D2R = math.pi / 180
SHORE = 27.0


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------

def _pt(m, p):
    return (m @ np.array([p[0], p[1], p[2], 1.0], dtype=np.float32))[:3]


def _basis_to(d):
    """Matrix rotating +Y onto direction d."""
    d = d / (np.linalg.norm(d) + 1e-9)
    a = np.array([1, 0, 0], dtype=np.float32) if abs(d[0]) < 0.9 else np.array([0, 0, 1], dtype=np.float32)
    x = np.cross(a, d)
    x /= np.linalg.norm(x) + 1e-9
    z = np.cross(x, d)
    m = np.identity(4, dtype=np.float32)
    m[:3, 0], m[:3, 1], m[:3, 2] = x, d, z
    return m


def capsule(sc: Scene, a, b, r, color, kind=PLAIN, lo=False, rough=0.7):
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    d = b - a
    L = float(np.linalg.norm(d))
    if lo:
        c = (a + b) / 2
        sc.add("sphere_lo", T(*c) @ _basis_to(d) @ S(r, L / 2 + r * 0.6, r), color, kind=kind, rough=rough)
        return
    sc.add("cyl", T(*a) @ _basis_to(d) @ S(r, L, r), color, kind=kind, rough=rough)
    sc.add("sphere", T(*a) @ S(r, r, r), color, kind=kind, rough=rough)
    sc.add("sphere", T(*b) @ S(r, r, r), color, kind=kind, rough=rough)


def ell(sc, m, pos, scale, color, kind=PLAIN, lo=False, rough=0.7, emissive=0.0, rot=None):
    mm = m @ T(*pos)
    if rot is not None:
        mm = mm @ rot
    sc.add("sphere_lo" if lo else "sphere", mm @ S(*scale), color, kind=kind, rough=rough, emissive=emissive)


def _dark(c, k=0.35):
    h = c.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return (r * (1 - k), g * (1 - k), b * (1 - k))


ELBOW = {"hold": 55, "cross": 95, "bow": 15, "think": 110, "hug": 35, "point": 5, "point_l": 5, "cheer": 10,
         "panic": 25, "shrug": 70, "out": 8, "wave": 20, "idle": 12}


# --------------------------------------------------------------------------
# Human
# --------------------------------------------------------------------------

def person(sc: Scene, st: Style, x: float, z: float, yaw: float, p: Pose, y: float = 0.0, scale: float = 1.0,
           detail: bool = True):
    k = st.size * scale * 1.0
    t = p.t
    lo = not detail
    walk = p.walk
    swing = math.sin(walk * TAU) if walk is not None else 0.0
    bob = (abs(math.sin(walk * TAU)) * 0.05 if walk is not None else math.sin(t * 2.1 + p.seed) * 0.006) + p.bounce
    R = T(x, y + bob, z) @ RY(yaw) @ S(k, k, k)
    B = R @ T(0, 0.95, 0) @ RZ(p.roll) @ RX(p.lean + math.sin(t * 1.1 + p.seed) * 0.01) @ T(0, -0.95, 0)
    shirt, pants, skin = st.shirt, st.pants, st.skin

    # ---------------- legs
    for side in (-1, 1):
        hip = _pt(R, (side * 0.095, 0.93, 0))
        sw = swing * side if walk is not None else 0.0
        thigh_p = -sw * 0.55
        knee_b = max(0.0, sw) * 0.9 if walk is not None else 0.04
        Rl = R @ T(side * 0.095, 0.93, 0)
        knee = _pt(Rl @ RX(thigh_p), (0, -0.44, 0))
        ankle = _pt(Rl @ RX(thigh_p) @ T(0, -0.44, 0) @ RX(knee_b), (0, -0.42, 0))
        capsule(sc, hip, knee, 0.075, pants, CLOTH, lo)
        capsule(sc, knee, ankle, 0.06, pants, CLOTH, lo)
        shoe = R @ T(side * 0.095, 0, 0)
        shoe_m = T(*ankle) @ RY(yaw) @ RX(knee_b * 0.3) @ T(0, -0.035, 0.045)
        sc.add("sphere_lo" if lo else "sphere", shoe_m @ S(0.06 * k, 0.05 * k, 0.125 * k), st.shoes, kind=PLAIN, rough=0.5)
        if not lo:
            sc.add("sphere", shoe_m @ T(0, -0.025 * k, 0) @ S(0.062 * k, 0.022 * k, 0.128 * k), "#f2f2f2", rough=0.6)

    # ---------------- torso
    ell(sc, B, (0, 0.97, 0), (0.16, 0.12, 0.105), pants, CLOTH, lo)
    ell(sc, B, (0, 1.08, 0), (0.155, 0.15, 0.105), shirt, CLOTH, lo)
    ell(sc, B, (0, 1.27, 0), (0.19, 0.18, 0.118), shirt, CLOTH, lo)
    if not lo:
        for side in (-1, 1):
            ell(sc, B, (side * 0.17, 1.37, 0), (0.07, 0.06, 0.07), shirt, CLOTH)
        capsule(sc, _pt(B, (0, 1.4, 0)), _pt(B, (0, 1.55, 0.005)), 0.048, skin, SKIN)
        # collar
        ell(sc, B, (0, 1.45, 0.0), (0.075, 0.025, 0.065), _dark(shirt, 0.15), CLOTH)

    # ---------------- arms
    arms = ARMS[p.arms] if isinstance(p.arms, str) else p.arms
    lp, lr, rp, rr = arms
    if p.arms == "wave":
        rr += math.sin(t * 12) * 14
    if p.arms == "panic":
        lr += math.sin(t * 16) * 16
        rr -= math.sin(t * 16 + 1) * 16
    if walk is not None and p.arms == "idle":
        lp, rp = -swing * 30, swing * 30
    bend = ELBOW.get(p.arms if isinstance(p.arms, str) else "idle", 12)
    hands = {}
    for side, (pitch, roll) in ((1, (lp, lr)), (-1, (rp, rr))):
        Ms = B @ T(side * 0.235, 1.38, 0) @ RZ(side * roll * D2R) @ RX(pitch * D2R)
        sh = _pt(Ms, (0, 0, 0))
        el = _pt(Ms, (0, -0.28, 0))
        Mf = Ms @ T(0, -0.28, 0) @ RX(-bend * D2R)
        wr = _pt(Mf, (0, -0.25, 0))
        capsule(sc, sh, el, 0.062, shirt, CLOTH, lo)
        capsule(sc, el, wr, 0.05, skin, SKIN, lo)
        Mh = Mf @ T(0, -0.3, 0.0)
        if not lo:
            sc.add("sphere", Mh @ S(0.04 * k, 0.055 * k, 0.026 * k), skin, kind=SKIN)
            sc.add("sphere", Mh @ T(side * 0.03 * k, 0.02 * k, 0.015 * k) @ RZ(side * 0.6) @ S(0.015 * k, 0.03 * k, 0.015 * k),
                   skin, kind=SKIN)
        hands[side] = Mh

    # ---------------- head
    hk = st.head
    nod = math.sin(t * 1.5 + p.seed) * 0.025 + p.mouth * math.sin(t * 9) * 0.03
    Hm = B @ T(0, 1.53, 0) @ RY(p.look_yaw) @ RX(p.look_pitch + nod) @ S(hk * 1.28, hk * 1.28, hk * 1.28)
    ell(sc, Hm, (0, 0.135, 0), (0.105, 0.125, 0.112), skin, SKIN, lo, rough=0.55)
    ell(sc, Hm, (0, 0.075, 0.018), (0.088, 0.07, 0.092), skin, SKIN, lo, rough=0.55)
    e = EXPR.get(p.expr, EXPR["neutral"])
    mw, mh, corners, btilt, braise, eye_h = e
    blink = p.blink
    if blink is None:
        ph = (t + p.seed * 1.37) % 3.9
        blink = 1.0 if ph < 0.11 else 0.0
    eh = eye_h * (1 - blink)
    if lo:
        for side in (-1, 1):
            ell(sc, Hm, (side * 0.04, 0.145, 0.1), (0.014, 0.016 * max(eh, 0.15), 0.01), "#1a1a1a", lo=True)
    else:
        _face(sc, st, Hm, p, e, eh)
    _hair(sc, st, Hm, lo)
    if p.held and not lo:
        _held(sc, p.held, hands[-1], t, k)
    return hands


def _face(sc, st, Hm, p, e, eh):
    mw, mh, corners, btilt, braise, eye_h = e
    skin = st.skin
    # ears + nose
    for side in (-1, 1):
        ell(sc, Hm, (side * 0.104, 0.125, -0.005), (0.02, 0.032, 0.02), skin, SKIN)
    ell(sc, Hm, (0, 0.112, 0.108), (0.014, 0.022, 0.02), skin, SKIN)
    ell(sc, Hm, (0, 0.098, 0.113), (0.017, 0.01, 0.013), skin, SKIN)
    # eyes
    for side in (-1, 1):
        ex = side * 0.04
        if eh < 0.08:
            ell(sc, Hm, (ex, 0.145, 0.1), (0.024, 0.004, 0.012), _dark(skin, 0.5), SKIN)
            continue
        ell(sc, Hm, (ex, 0.147, 0.09), (0.029, 0.027 * min(eh, 1.3), 0.02), "#fbfbf7", EYE, rough=0.1)
        ix = ex + 0.009 * p.eye_x
        ell(sc, Hm, (ix, 0.146, 0.106), (0.016, 0.016 * min(eh, 1.2), 0.007), st.eye, EYE, rough=0.1)
        ell(sc, Hm, (ix, 0.146, 0.111), (0.0085, 0.0085 * min(eh, 1.2), 0.004), "#050505", EYE, rough=0.05)
        ell(sc, Hm, (ix - 0.005, 0.153, 0.114), (0.0032, 0.0032, 0.002), "#ffffff", PLAIN, emissive=1.5)
        # upper lid (eyelid follows expression)
        lid_y = 0.147 + 0.027 * min(eh, 1.3) * 0.85
        ell(sc, Hm, (ex, lid_y, 0.092), (0.032, 0.009, 0.021), _dark(skin, 0.1), SKIN,
            rot=RZ(-side * btilt * 0.25))
        # brows
        ell(sc, Hm, (ex, 0.192 + braise * 0.6, 0.102), (0.029, 0.007, 0.01), _dark(st.hair or "#3d2b1f", 0.25), HAIR,
            rot=RZ(-side * btilt * 0.35))
    # mouth
    op = mh * 0.6 + p.mouth * 0.75
    w = 0.03 * (mw / 0.16)
    my = 0.06
    if op > 0.04:
        ell(sc, Hm, (0, my, 0.1), (w, 0.006 + 0.028 * op, 0.014), "#3a0d10", PLAIN, rough=0.6)
        ell(sc, Hm, (0, my + 0.004 + 0.018 * op, 0.104), (w * 0.8, 0.005, 0.008), "#f4f1ea", PLAIN, rough=0.3)
        ell(sc, Hm, (0, my - 0.012 * op, 0.102), (w * 0.55, 0.006 * op + 0.002, 0.009), "#c7525c", PLAIN)
    else:
        ell(sc, Hm, (0, my, 0.103), (w, 0.0045, 0.01), "#8a3b3b", PLAIN, rough=0.5)
    if corners > 0.2 and op <= 0.04:
        # smile: a second, wider and lower dark arc reads as a grin
        ell(sc, Hm, (0, my - 0.004, 0.1), (w * 1.05, 0.009, 0.011), "#5a1f22", PLAIN)
    elif corners < -0.2 and op <= 0.04:
        ell(sc, Hm, (0, my + 0.004, 0.1), (w * 0.85, 0.007, 0.011), "#5a1f22", PLAIN)
    if p.sweat > 0.01:
        ell(sc, Hm, (0.07, 0.2, 0.08), (0.008, 0.013, 0.008), "#bfe8ff", PLAIN, rough=0.05, emissive=0.4)
    if p.tears > 0.01:
        for side in (-1, 1):
            ph = (p.t * 1.2 + (0.5 if side > 0 else 0)) % 1
            ell(sc, Hm, (side * 0.045, 0.125 - ph * 0.06, 0.104), (0.005, 0.009, 0.005), "#bfe8ff", PLAIN, rough=0.05,
                emissive=0.6)


def _hair(sc, st, Hm, lo):
    hc = st.hair
    hs = st.hair_style
    if hc and hs != "none":
        ell(sc, Hm, (0, 0.205, -0.018), (0.114, 0.088, 0.122), hc, HAIR, lo)
        ell(sc, Hm, (0, 0.13, -0.05), (0.11, 0.11, 0.085), hc, HAIR, lo)
        if not lo:
            for side in (-1, 1):
                ell(sc, Hm, (side * 0.098, 0.165, -0.01), (0.022, 0.05, 0.07), hc, HAIR)
        if hs == "spiky" and not lo:
            for i in range(6):
                a = (i - 2.5) * 0.32
                ell(sc, Hm, (math.sin(a) * 0.06, 0.27, 0.01 + math.cos(a) * 0.02), (0.022, 0.05, 0.022), hc, HAIR,
                    rot=RZ(-a * 0.8) @ RX(-0.4))
        elif hs == "tall":
            for i in range(10 if not lo else 4):
                a = i * TAU / (10 if not lo else 4)
                ell(sc, Hm, (math.cos(a) * 0.08, 0.25 + 0.02 * math.sin(a * 3), -0.02 + math.sin(a) * 0.08),
                    (0.055, 0.055, 0.055), hc, HAIR, lo)
            ell(sc, Hm, (0, 0.29, -0.02), (0.09, 0.06, 0.09), hc, HAIR, lo)
        elif hs == "side" and not lo:
            ell(sc, Hm, (-0.03, 0.235, 0.085), (0.075, 0.03, 0.04), hc, HAIR, rot=RZ(0.35))
        elif hs == "long":
            ell(sc, Hm, (0, 0.04, -0.07), (0.12, 0.2, 0.07), hc, HAIR, lo)
            if not lo:
                for side in (-1, 1):
                    ell(sc, Hm, (side * 0.105, 0.06, 0.02), (0.03, 0.16, 0.06), hc, HAIR)
                ell(sc, Hm, (0.02, 0.232, 0.08), (0.09, 0.03, 0.045), hc, HAIR, rot=RZ(-0.2))
        elif hs == "flat" and not lo:
            ell(sc, Hm, (0, 0.24, 0.07), (0.095, 0.03, 0.05), hc, HAIR)
    if st.hat == "crown":
        sc.add("cyl", Hm @ T(0, 0.26, -0.01) @ S(0.105, 0.05, 0.11), "#ffd60a", kind=GOLD, emissive=0.35, rough=0.25)
        for i in range(6):
            a = i * TAU / 6
            sc.add("octa", Hm @ T(math.cos(a) * 0.1, 0.33, -0.01 + math.sin(a) * 0.1) @ S(0.018, 0.03, 0.018), "#ffd60a",
                   kind=GOLD, emissive=0.35, rough=0.25)
        sc.add("octa", Hm @ T(0, 0.285, 0.105) @ S(0.016, 0.016, 0.01), "#e63946", kind=GEM, emissive=0.8)
    elif st.hat == "cap":
        ell(sc, Hm, (0, 0.215, -0.015), (0.118, 0.085, 0.126), st.hat_color, CLOTH, lo)
        if not lo:
            sc.add("cyl", Hm @ T(0, 0.205, 0.11) @ S(0.09, 0.008, 0.07), st.hat_color, kind=CLOTH)
    elif st.hat == "headset":
        sc.add("cyl", Hm @ T(0, 0.3, 0) @ RZ(math.pi / 2) @ T(0, -0.12, 0) @ S(0.012, 0.24, 0.02), "#222222", rough=0.4)
        for side in (-1, 1):
            sc.add("cyl", Hm @ T(side * 0.1, 0.13, 0) @ RZ(math.pi / 2) @ T(0, -0.02, 0) @ S(0.04, 0.04, 0.04), "#222222",
                   rough=0.35)
    elif st.hat == "band":
        sc.add("cyl", Hm @ T(0, 0.2, -0.01) @ S(0.118, 0.022, 0.125), st.hat_color, kind=CLOTH)


def _held(sc, kind, Mh, t, k):
    if kind == "mic":
        sc.add("cyl", Mh @ T(0, -0.06, 0.02) @ S(0.016, 0.16, 0.016), "#222222", rough=0.3)
        sc.add("sphere", Mh @ T(0, 0.11, 0.02) @ S(0.035, 0.035, 0.035), "#9a9a9a", rough=0.3)
    elif kind == "briefcase":
        sc.add("box", Mh @ T(0, -0.2, 0.03) @ S(0.42, 0.3, 0.1), "#5c3a1e", kind=PLAIN, rough=0.45)
        sc.add("box", Mh @ T(0, -0.04, 0.03) @ S(0.14, 0.04, 0.03), "#2b1a0d")
        sc.add("box", Mh @ T(0, -0.12, 0.085) @ S(0.06, 0.04, 0.01), "#ffd60a", kind=GOLD, emissive=0.3)
    elif kind == "snack":
        sc.add("box", Mh @ T(0, -0.05, 0.05) @ S(0.13, 0.2, 0.06), "#ff006e", rough=0.4)
        sc.add("box", Mh @ T(0, -0.05, 0.083) @ S(0.08, 0.06, 0.005), "#ffd60a")
    elif kind == "bow":
        for i in range(7):
            a = (i - 3) * 0.25
            sc.add("cyl", Mh @ T(0, math.sin(a) * 0.45, 0.1 + math.cos(a) * 0.1 - 0.1) @ RX(a) @ T(0, -0.04, 0) @ S(0.015, 0.09, 0.015),
                   "#8b5a2b", kind=WOOD)
        sc.add("cyl", Mh @ T(0, -0.45, 0.0) @ S(0.003, 0.9, 0.003), "#eeeeee")
    elif kind == "gem":
        gem(sc, Mh @ T(0, 0.05, 0.08), 0.12, t)


# --------------------------------------------------------------------------
# Props
# --------------------------------------------------------------------------

GEM_COLS = ("#29d3ff", "#ff4fd8", "#7cff6b", "#ffd60a")


def gem(sc, m, s, t, color="#29d3ff"):
    sc.add("octa", m @ RY(t * 1.3) @ S(s * 0.6, s * 0.6, s * 0.6), color, kind=GEM, emissive=0.9, rough=0.05)


def gem_pile(sc, x, y, z, t, n=60, s=1.0):
    r = random.Random(3)
    for k in range(n):
        layer = int(math.sqrt(k) * 0.9)
        a = r.random() * TAU
        rad = (2.2 - layer * 0.42) * math.sqrt(r.random()) * s
        gem(sc, T(x + math.cos(a) * rad, y + 0.15 + layer * 0.26 * s, z + math.sin(a) * rad) @ RY(r.random() * 6)
            @ RZ(r.random() - 0.5), 0.5 * s, t * 0.15 + k, GEM_COLS[k % 4])


def poof(sc, x, y, z, p, t):
    if p >= 1:
        return
    for k in range(14):
        a = k * TAU / 14
        b = (k % 3 - 1) * 0.7
        d = 0.25 + p * 1.3
        s = 0.16 * (1 - p)
        sc.add("sphere_lo", T(x + math.cos(a) * d, y + b * d * 0.5 + p * 0.6, z + math.sin(a) * d) @ S(s, s, s),
               "#fff6d0", kind=PLAIN, emissive=2.0, shadow=False)


# --------------------------------------------------------------------------
# World
# --------------------------------------------------------------------------

def _terrain_h(X, Z):
    D = np.hypot(X, Z)
    n = np.sin(X * 0.11) * np.cos(Z * 0.09) + 0.6 * np.sin((X + Z) * 0.05) + 0.3 * np.sin(X * 0.31 + Z * 0.23)
    h = np.clip(D - SHORE, 0, None) * 0.28 + np.clip(D - SHORE - 4, 0, None) * 0.15 + n * np.clip((D - SHORE) / 10, 0, 1) * 2.2
    return h.astype(np.float32)


@lru_cache(maxsize=1)
def _trees():
    r = random.Random(4)
    out = []
    for k in range(34):
        a = r.random() * TAU
        d = SHORE + 3 + r.random() * 22
        x, z = math.cos(a) * d, math.sin(a) * d
        if abs(x) < 7 and z > 0:
            continue
        h = float(_terrain_h(np.array([[x]]), np.array([[z]]))[0, 0])
        out.append((x, h, z, 0.8 + r.random() * 0.7, r.random()))
    rocks = []
    for k in range(40):
        a = r.random() * TAU
        d = SHORE + 0.5 + r.random() * 2.5
        rocks.append((math.cos(a) * d, math.sin(a) * d, 0.4 + r.random() * 0.9, r.random() * 6))
    return out, rocks


def build_world(sc: Scene, t: float, radius: float, lava: float = 0.0, ring=True, ring_color="gold"):
    sc.mesh("terrain", lambda: mesh_terrain(SHORE - 0.5, 95, _terrain_h, n=170), "#4c9a33", kind=GRASS, static=True)
    sc.mesh("shorewall", lambda: _tube(SHORE, -6.0, 0.02), "#7d7468", kind=STONE, static=True)
    trees, rocks = _trees()
    for x, h, z, s, c in trees:
        sc.add("cyl", T(x, h - 0.2, z) @ S(0.25 * s, 2.6 * s, 0.25 * s), "#6b4426", kind=WOOD)
        g = ("#3f8f3a", "#2f7a35", "#4c9e3c")[int(c * 3)]
        for dx, dy, dz, rr in ((0, 3.1, 0, 1.5), (0.7, 2.6, 0.3, 1.1), (-0.6, 2.7, -0.4, 1.15), (0.1, 3.8, 0.2, 1.0)):
            sc.add("sphere_lo", T(x + dx * s, h + dy * s, z + dz * s) @ S(rr * s, rr * 0.85 * s, rr * s), g, rough=0.9)
    for x, z, s, rot in rocks:
        sc.add("sphere_lo", T(x, 0.0, z) @ RY(rot) @ S(s * 1.2, s * 0.6, s), "#8b857b", kind=STONE)
    sink = ease(lava / 0.45) * 5.5
    rise = ease((lava - 0.3) / 0.7)
    lava_y = -5.0 + rise * 4.65
    rq = round(radius, 2)
    # platform top (always) + outer floor (sinks when lava)
    sc.mesh(("disc", rq), lambda: mesh_annulus(0.02, rq, 0.0, seg=96), "#4c9a33", kind=GRASS)
    if sink < 5.4:
        sq = round(sink, 2)
        sc.mesh(("floor", rq, sq), lambda: mesh_annulus(rq, SHORE, -sq, seg=128), "#4c9a33", kind=GRASS)
    if lava > 0:
        sc.mesh(("pside", rq), lambda: _tube(rq, -6.0, 0.0, inward=False), "#77695a", kind=STONE)
    if rise > 0:
        ly = round(lava_y, 2)
        sc.mesh(("lava", rq, ly), lambda: mesh_annulus(rq, SHORE, ly, seg=128), "#ff5a00", kind=LAVA, emissive=1.0)
    if ring:
        sc.mesh(("ring", rq), lambda: mesh_torus(rq, 0.06, seg=160, tube=8), "#ffd23f", kind=GOLD, emissive=1.6)
        n = max(12, int(rq * 2))
        for k in range(n):
            a = k * TAU / n
            pulse = 0.6 + 0.4 * math.sin(t * 5 + k * 0.5)
            sc.add("sphere_lo", T(math.cos(a) * rq, 0.08, math.sin(a) * rq) @ S(0.09, 0.09, 0.09), "#fff0a0",
                   kind=PLAIN, emissive=2.5 * pulse, shadow=False)
    # host stage (south) and prize podium (north) on stone pillars
    sc.add("box", T(0, -0.2, 19.8) @ S(6.0, 0.4, 4.0), "#a77b4f", kind=WOOD)
    sc.add("cyl", T(0, -6, 19.8) @ S(1.6, 5.8, 1.6), "#77695a", kind=STONE)
    sc.add("box", T(0, -0.35, -21.5) @ S(6.0, 0.7, 5.0), "#e8b923", kind=GOLD, emissive=0.15)
    sc.add("cyl", T(0, -6, -21.5) @ S(1.8, 5.6, 1.8), "#77695a", kind=STONE)


def _tube(r, y0, y1, inward=True, seg=128):
    v = mesh_cylinder(seg, caps=False).reshape(-1, 6).copy()
    v[:, 0] *= r
    v[:, 2] *= r
    v[:, 1] = y0 + v[:, 1] * (y1 - y0)
    if inward:
        v[:, 3:6] *= -1
    return v.reshape(-1).astype(np.float32)


# --------------------------------------------------------------------------
# Crowd
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def crowd_people(n=100):
    r = random.Random(42)
    pts = []
    while len(pts) < n:
        u, v = r.uniform(-1, 1), r.uniform(-1, 1)
        if u * u + v * v > 0.8:
            continue
        if any((u - a) ** 2 + (v - b) ** 2 < 0.0075 for a, b in pts):
            continue
        if v > 0.35 and abs(u) < 0.45:
            continue
        pts.append((u, v))
    out = []
    for i in range(n):
        st = Style(f"p{i}", skin=r.choice(SKINS), shirt=r.choice(SHIRTS),
                   pants=r.choice(["#2b2d42", "#264653", "#3d405b", "#5e548e", "#6c584c", "#1d3557"]),
                   shoes=r.choice(["#f2f2f2", "#222222", "#e63946", "#3a86ff"]),
                   hair=r.choice(HAIRS[:6]), hair_style=r.choice(["flat", "tall", "side", "spiky", "long", "none"]),
                   hat=r.choice([None, None, None, "cap", "band"]), hat_color=r.choice(SHIRTS),
                   size=0.92 + r.random() * 0.16)
        out.append((st, pts[i][0], pts[i][1], r.random() * 10))
    return out


def crowd(sc: Scene, t: float, alive: int, radius: float, leaving=(0, 0, 0.0), expr="neutral", arms="idle",
          panic=0.0, sleep=False, push=0.0, face_yaw=None, teleport=False, cam_pos=None, detail_near=7.0,
          clear=None, clear_r=2.0):
    rr = radius * 0.86
    lo_, hi, lp = leaving
    for i, (st, u, v, ph) in enumerate(crowd_people()):
        if i >= max(alive, hi):
            continue
        x, z = u * rr, v * rr
        yaw = face_yaw if face_yaw is not None else math.atan2(-x, 18 - z) * 0.6
        walk, y = None, 0.0
        e, a = expr, arms
        if lo_ <= i < hi and lp > 0:
            if teleport:
                q = clamp(lp / 0.6)
                if q >= 1:
                    poof(sc, x, 1.1, z, clamp((lp - 0.6) / 0.4), t)
                    continue
                y = q * 1.4
                yaw += q * 6
                e, a = "shocked", "cheer"
            else:
                d = math.hypot(u, v) or 1
                out = lp * radius * 1.6
                x += u / d * out
                z += v / d * out
                yaw = math.atan2(u, v)
                walk = t * 1.8 + ph
                e, a = ("happy", "cheer") if i % 3 else ("laugh", "idle")
        else:
            if panic:
                e, a = ("scared", "panic") if (i + int(t * 2)) % 3 == 0 else ("shocked", "idle")
                x += math.sin(t * 7 + ph) * 0.08 * panic
            if push:
                x += math.sin(t * 5 + ph * 2) * 0.12 * push
                z += math.cos(t * 4 + ph) * 0.07 * push
            if sleep and i % 4 != 0:
                e = "sleep"
        if clear is not None and math.hypot(x - clear[0], z - clear[1]) < clear_r:
            continue
        detail = cam_pos is not None and math.dist((x, 1.5, z), cam_pos) < detail_near
        person(sc, st, x, z, yaw, Pose(t=t + ph, arms=a, expr=e, walk=walk, seed=ph), y=y, detail=detail)
