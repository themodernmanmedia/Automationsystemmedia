"""3D voxel world + block people built on engine3d (all original designs)."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import numpy as np

from .engine3d import BLOCK_IDS, RX, RY, RZ, S, Scene, T, hex3

TAU = math.tau
D2R = math.pi / 180

SHORE = 27.0       # lava lake radius; beyond this the world stays solid
GRID = 46          # world half-size in blocks


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


# --------------------------------------------------------------------------
# Terrain
# --------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _terrain_static():
    """Shore hills, trees, gem podium — never changes."""
    r = random.Random(4)
    out = []
    G, D, ST, W, LV, GO, GE, PL = (BLOCK_IDS[k] for k in ("grass", "dirt", "stone", "wood", "leaves", "gold", "gem", "plank"))
    def height(x, z):
        d = math.hypot(x + 0.5, z + 0.5)
        if d < SHORE:
            return None
        n = math.sin(x * 0.21) * math.cos(z * 0.17) + math.sin((x + z) * 0.09) * 0.8
        return min(int(max(0, (d - SHORE) * 0.32 + n * 1.6)), 9)

    for x in range(-GRID, GRID):
        for z in range(-GRID, GRID):
            h = height(x, z)
            if h is None:
                continue
            nb = [height(x + dx, z + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            low = min((-3 if v is None else v) for v in nb)
            for y in range(max(-2, low - 1), h - 1):
                out.append((x, y, z, 1, 1, 1, ST if y < h - 3 else D))
            out.append((x, h - 1, z, 1, 1, 1, G))
    # trees on the shore
    for k in range(26):
        a = r.random() * TAU
        d = SHORE + 2 + r.random() * 9
        x, z = int(math.cos(a) * d), int(math.sin(a) * d)
        if abs(x) < 6 and z > 0:
            continue  # keep the host side clear
        dd = math.hypot(x + 0.5, z + 0.5)
        n = math.sin(x * 0.21) * math.cos(z * 0.17) + math.sin((x + z) * 0.09) * 0.8
        base = int(max(0, (dd - SHORE) * 0.32 + n * 1.6))
        base = min(base, 9)
        th = 3 + r.randint(0, 2)
        for y in range(base, base + th):
            out.append((x, y, z, 1, 1, 1, W))
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                for dy in range(0, 2):
                    if abs(dx) == 2 and abs(dz) == 2:
                        continue
                    out.append((x + dx, base + th - 1 + dy, z + dz, 1, 1, 1, LV))
        out.append((x, base + th + 1, z, 1, 1, 1, LV))
    # host stage (south, facing arena) and prize podium (north)
    for x in range(-3, 3):
        for z in range(18, 22):
            out.append((x, -1, z, 1, 1, 1, PL))
    for x in range(-3, 3):
        for z in range(-24, -19):
            for y in range(-1, 1):
                out.append((x, y, z, 1, 1, 1, GO))
    return np.array(out, dtype=np.float32)


@lru_cache(maxsize=64)
def _arena(radius_q: int, lava_q: int):
    radius = radius_q / 100
    lava = lava_q / 100
    G, D, L = BLOCK_IDS["grass"], BLOCK_IDS["dirt"], BLOCK_IDS["lava"]
    out = []
    sink = ease(lava / 0.45) * 7.0                # outside floor falls away
    rise = ease((lava - 0.3) / 0.7)               # lava rises up
    lava_y = -6.0 + rise * 4.0                    # top ends at y=-1
    for x in range(-GRID, GRID):
        for z in range(-GRID, GRID):
            d = math.hypot(x + 0.5, z + 0.5)
            if d >= SHORE:
                continue
            on_stage = (-3 <= x < 3 and 18 <= z < 22)
            if d <= radius + 0.5 or lava <= 0.001:
                out.append((x, -1, z, 1, 1, 1, G))
                if lava > 0 and d > radius - 1.2:
                    for y in (-2, -3, -4):
                        out.append((x, y, z, 1, 1, 1, D))
            else:
                if sink < 6.9 and not on_stage:
                    out.append((x, -1 - sink, z, 1, 1, 1, G))
                if rise > 0:
                    out.append((x, lava_y, z, 1, 1, 1, L))
    return np.array(out, dtype=np.float32)


def build_world(scene: Scene, t: float, radius: float, lava: float = 0.0, ring=True, ring_color="gold"):
    scene.add_blocks(_terrain_static())
    scene.add_blocks(_arena(int(round(radius * 100)), int(round(lava * 100))))
    if ring:
        n = max(24, int(radius * 2 * math.pi / 0.9))
        for k in range(n):
            a = k * TAU / n
            x, z = math.cos(a) * radius, math.sin(a) * radius
            pulse = 0.6 + 0.4 * math.sin(t * 5 + k * 0.4)
            scene.cube(x, 0.08, z, 0.55, 0.16, 0.55, "#ffd60a", emissive=0.5 * pulse, rot_y=-a)
    # clouds
    rr = random.Random(9)
    for k in range(9):
        cx = ((t * 0.8 + rr.random() * 140) % 140) - 70
        cz = -60 + rr.random() * 120
        w = 6 + rr.random() * 8
        scene.cube(cx, 34 + rr.random() * 6, cz, w, 1.2, w * 0.6, "#ffffff", emissive=0.35, shadow=False)


# --------------------------------------------------------------------------
# Block people
# --------------------------------------------------------------------------

ARMS = {
    # (left pitch, left roll, right pitch, right roll) degrees
    # pitch: negative = forward/up in front ; roll: outward
    "idle": (0, 4, 0, 4),
    "cheer": (0, 155, 0, 155),
    "wave": (0, 4, 0, 150),
    "point": (0, 4, -90, 5),
    "point_l": (-90, 5, 0, 4),
    "out": (-80, 10, -80, 10),
    "hold": (0, 4, -40, 6),
    "panic": (-20, 140, -20, 140),
    "shrug": (-30, 45, -30, 45),
    "hug": (-70, -20, -70, -20),
    "bow": (-90, -8, -90, 25),
    "cross": (-75, -40, -65, -40),
    "think": (0, 4, -140, -40),
}

EXPR = {
    # mouth_w, mouth_h, corners(-1..1), brow_tilt, brow_raise, eye_h
    "neutral": (0.16, 0.035, 0.0, 0.0, 0.0, 1.0),
    "happy": (0.2, 0.05, 1.0, 0.0, 0.01, 1.0),
    "laugh": (0.22, 0.1, 1.0, -0.2, 0.03, 0.35),
    "sad": (0.14, 0.035, -1.0, -0.6, 0.0, 0.85),
    "shocked": (0.11, 0.12, 0.0, 0.0, 0.05, 1.25),
    "angry": (0.17, 0.035, -0.6, 0.8, -0.01, 0.75),
    "smug": (0.15, 0.035, 0.7, 0.5, 0.0, 0.65),
    "scared": (0.16, 0.08, -0.6, -0.7, 0.04, 1.25),
    "determined": (0.15, 0.035, 0.0, 0.8, -0.01, 0.8),
    "sleep": (0.1, 0.03, 0.0, 0.0, 0.0, 0.0),
}


@dataclass
class Style:
    name: str
    skin: str = "#e0ac7e"
    shirt: str = "#3a86ff"
    pants: str = "#22223b"
    shoes: str = "#2b2d42"
    hair: Optional[str] = "#3d2b1f"
    hair_style: str = "flat"        # flat | tall | side | long | spiky | none
    hat: Optional[str] = None       # crown | cap | headset | band
    hat_color: str = "#e63946"
    stripe: Optional[str] = None
    eye: str = "#2a2a6a"
    size: float = 1.0
    head: float = 1.0


@dataclass
class Pose:
    t: float = 0.0
    arms: object = "idle"
    expr: str = "neutral"
    mouth: float = 0.0
    walk: Optional[float] = None
    look_yaw: float = 0.0          # head yaw relative to body (rad)
    look_pitch: float = 0.0
    eye_x: float = 0.0             # pupils -1..1
    bounce: float = 0.0
    lean: float = 0.0              # forward lean (rad)
    roll: float = 0.0              # side tilt (rad)
    held: Optional[str] = None
    seed: float = 0.0
    blink: Optional[float] = None
    sweat: float = 0.0
    tears: float = 0.0


def _arm_mat(base, side, pitch, roll):
    # side: -1 left (+x is character's left? we use +x = character's left when facing +z)
    return base @ RZ(side * roll * D2R) @ RX(pitch * D2R)


def person(scene: Scene, st: Style, x: float, z: float, yaw: float, p: Pose, y: float = 0.0, scale: float = 1.0,
           detail: bool = True):
    k = st.size * scale
    t = p.t
    root = T(x, y, z) @ RY(yaw) @ S(k, k, k)
    swing = math.sin(p.walk * TAU) if p.walk is not None else 0.0
    bob = (abs(math.sin(p.walk * TAU)) * 0.08 if p.walk is not None else math.sin(t * 2.2 + p.seed) * 0.012) + p.bounce
    root = root @ T(0, bob, 0)
    body = root @ T(0, 0.75, 0) @ RZ(p.roll) @ RX(p.lean) @ T(0, -0.75, 0)
    # legs
    for side in (-1, 1):
        leg = root @ T(side * 0.125, 0.75, 0) @ RX(swing * 0.6 * side)
        scene.box(leg @ T(0, -0.3, 0) @ S(0.245, 0.6, 0.245), st.pants)
        scene.box(leg @ T(0, -0.68, 0.01) @ S(0.25, 0.15, 0.26), st.shoes)
    # torso
    scene.box(body @ T(0, 1.125, 0) @ S(0.5, 0.75, 0.25), st.shirt)
    if st.stripe:
        scene.box(body @ T(0, 1.2, 0.0) @ S(0.505, 0.12, 0.255), st.stripe)
    # arms
    arms = ARMS[p.arms] if isinstance(p.arms, str) else p.arms
    lp, lr, rp, rr = arms
    if p.arms == "wave":
        rr += math.sin(t * 13) * 16
    if p.arms == "panic":
        lr += math.sin(t * 18) * 18
        rr -= math.sin(t * 18 + 1) * 18
    if p.walk is not None and p.arms == "idle":
        lp, rp = -swing * 35, swing * 35
    hands = {}
    for side, (pitch, roll) in ((1, (lp, lr)), (-1, (rp, rr))):
        sh = body @ T(side * 0.375, 1.44, 0)
        m = sh @ RZ(side * roll * D2R) @ RX(pitch * D2R)
        scene.box(m @ T(0, -0.22, 0) @ S(0.245, 0.46, 0.245), st.shirt)
        scene.box(m @ T(0, -0.58, 0) @ S(0.24, 0.27, 0.24), st.skin)
        hands[side] = m @ T(0, -0.72, 0)
    # head
    hk = st.head
    hm = body @ T(0, 1.5, 0) @ RY(p.look_yaw) @ RX(p.look_pitch + math.sin(t * 1.6 + p.seed) * 0.03) @ S(hk, hk, hk)
    scene.box(hm @ T(0, 0.25, 0) @ S(0.5, 0.5, 0.5), st.skin)
    if detail:
        _face(scene, st, hm, p)
    _hair(scene, st, hm)
    if p.held:
        held(scene, p.held, hands[-1], t)
    return hands


def _face(scene, st, hm, p: Pose):
    e = EXPR.get(p.expr, EXPR["neutral"])
    mw, mh, corners, btilt, braise, eye_h = e
    zf = 0.252
    blink = p.blink
    if blink is None:
        ph = (p.t + p.seed * 1.37) % 3.7
        blink = 1.0 if ph < 0.12 else 0.0
    eh = 0.085 * eye_h * (1 - blink)
    for side in (-1, 1):
        ex = side * 0.115
        if eh < 0.01:
            scene.box(hm @ T(ex, 0.27, zf) @ S(0.1, 0.018, 0.01), "#1b1b1b")
        else:
            scene.box(hm @ T(ex, 0.27, zf) @ S(0.1, eh, 0.01), "#ffffff")
            scene.box(hm @ T(ex + 0.025 * p.eye_x + side * 0.0, 0.265, zf + 0.004) @ S(0.05, eh * 0.8, 0.01), st.eye)
        # brows
        bm = hm @ T(ex, 0.35 + braise, zf + 0.002) @ RZ(-side * btilt * 0.35)
        scene.box(bm @ S(0.11, 0.025, 0.01), _dark(st.hair or "#333333"))
    # mouth
    oh = mh + p.mouth * 0.09
    w = mw * (1 + p.mouth * 0.15)
    scene.box(hm @ T(0, 0.13, zf) @ S(w, max(0.02, oh), 0.01), "#3a1010" if oh > 0.045 else "#5a2a22")
    if abs(corners) > 0.2:
        cy = 0.13 + (oh / 2 + 0.012) * (1 if corners > 0 else -1)
        for side in (-1, 1):
            scene.box(hm @ T(side * (w / 2 + 0.012), cy, zf) @ S(0.028, 0.028, 0.01), "#5a2a22")
    if p.sweat > 0.01:
        scene.box(hm @ T(0.2, 0.42, zf) @ S(0.035, 0.06, 0.02), "#8fd3ff", emissive=0.3)
    if p.tears > 0.01:
        for side in (-1, 1):
            ph = (p.t * 1.3 + (0.5 if side > 0 else 0)) % 1
            scene.box(hm @ T(side * 0.115, 0.2 - ph * 0.15, zf + 0.003) @ S(0.03, 0.05, 0.01), "#8fd3ff", emissive=0.3)


def _dark(c, k=0.35):
    r, g, b = hex3(c)
    return (r * (1 - k), g * (1 - k), b * (1 - k))


def _hair(scene, st, hm):
    hc = st.hair
    if hc and st.hair_style != "none":
        hs = st.hair_style
        if hs in ("flat", "side", "spiky", "long", "tall"):
            scene.box(hm @ T(0, 0.51, 0) @ S(0.53, 0.06 if hs != "tall" else 0.2, 0.53), hc)
            scene.box(hm @ T(0, 0.3, -0.255) @ S(0.53, 0.44, 0.04), hc)
            scene.box(hm @ T(0, 0.47, 0.245) @ S(0.53, 0.07, 0.04), hc)
            for side in (-1, 1):
                scene.box(hm @ T(side * 0.255, 0.4, 0) @ S(0.04, 0.2, 0.53), hc)
        if hs == "side":
            scene.box(hm @ T(-0.1, 0.43, 0.25) @ S(0.3, 0.12, 0.05), hc)
        if hs == "spiky":
            for i in range(4):
                scene.box(hm @ T(-0.19 + i * 0.125, 0.57 + (i % 2) * 0.05, 0.05) @ RZ(0.3 * (i - 1.5)) @ S(0.12, 0.14, 0.4), hc)
        if hs == "long":
            scene.box(hm @ T(0, 0.05, -0.26) @ S(0.55, 0.75, 0.06), hc)
            for side in (-1, 1):
                scene.box(hm @ T(side * 0.27, 0.12, -0.05) @ S(0.05, 0.6, 0.45), hc)
    if st.hat == "crown":
        scene.box(hm @ T(0, 0.58, 0) @ S(0.56, 0.12, 0.56), "#ffd60a", emissive=0.25)
        for cx in (-0.22, 0, 0.22):
            for cz in (-0.22, 0.22):
                scene.box(hm @ T(cx, 0.69, cz) @ S(0.1, 0.12, 0.1), "#ffd60a", emissive=0.25)
        scene.box(hm @ T(0, 0.58, 0.285) @ S(0.1, 0.08, 0.02), "#e63946", emissive=0.4)
    elif st.hat == "cap":
        scene.box(hm @ T(0, 0.55, 0) @ S(0.54, 0.12, 0.54), st.hat_color)
        scene.box(hm @ T(0, 0.5, 0.37) @ S(0.5, 0.04, 0.26), st.hat_color)
    elif st.hat == "headset":
        scene.box(hm @ T(0, 0.56, 0) @ S(0.56, 0.05, 0.1), "#222222")
        for side in (-1, 1):
            scene.box(hm @ T(side * 0.28, 0.28, 0) @ S(0.06, 0.16, 0.16), "#222222")
        scene.box(hm @ T(0.2, 0.15, 0.2) @ S(0.03, 0.03, 0.2), "#222222")
    elif st.hat == "band":
        scene.box(hm @ T(0, 0.44, 0) @ S(0.54, 0.06, 0.54), st.hat_color)


def held(scene, kind, hand, t):
    if kind == "mic":
        scene.box(hand @ T(0, -0.05, 0.05) @ S(0.06, 0.2, 0.06), "#333333")
        scene.box(hand @ T(0, 0.08, 0.05) @ S(0.11, 0.11, 0.11), "#9a9a9a")
    elif kind == "briefcase":
        scene.box(hand @ T(0, -0.2, 0.05) @ S(0.5, 0.36, 0.14), "#5c3a1e")
        scene.box(hand @ T(0, 0.0, 0.05) @ S(0.2, 0.06, 0.06), "#2b1a0d")
        scene.box(hand @ T(0, -0.15, 0.13) @ S(0.08, 0.06, 0.02), "#ffd60a", emissive=0.3)
    elif kind == "snack":
        scene.box(hand @ T(0, -0.05, 0.08) @ S(0.18, 0.26, 0.08), "#ff006e")
        scene.box(hand @ T(0, -0.05, 0.125) @ S(0.1, 0.08, 0.01), "#ffd60a")
    elif kind == "bow":
        for i in range(5):
            a = (i - 2) * 0.35
            scene.box(hand @ T(0, math.sin(a) * 0.45, 0.15 + math.cos(a) * 0.12 - 0.12) @ RX(a) @ S(0.05, 0.22, 0.05), "#8b5a2b")
        scene.box(hand @ T(0, 0, 0.05) @ S(0.01, 0.9, 0.01), "#eeeeee")
    elif kind == "gem":
        gem(scene, hand @ T(0, 0.05, 0.1), 0.25, t)


def gem(scene, m, s, t, color="#29d3ff"):
    m = m @ RY(t * 1.5) @ S(s, s, s)
    scene.box(m @ RZ(math.pi / 4) @ RX(math.pi / 4) @ S(0.7, 0.7, 0.7), color, emissive=0.55)


# --------------------------------------------------------------------------
# Crowd
# --------------------------------------------------------------------------

SHIRTS = ["#e63946", "#3a86ff", "#ffbe0b", "#8338ec", "#06d6a0", "#ff006e", "#fb5607", "#118ab2", "#8ac926",
          "#f15bb5", "#00bbf9", "#9b5de5", "#ef476f", "#2ec4b6"]
SKINS = ["#f1c27d", "#e0ac69", "#c68642", "#8d5524", "#ffdbac", "#a1665e", "#6b4226"]
HAIRS = ["#2b1d16", "#5a3825", "#d9a441", "#111111", "#a14a1a", "#e8e8e8", "#ff5ea8", "#3a86ff"]


@lru_cache(maxsize=1)
def crowd_people(n=100):
    r = random.Random(42)
    out = []
    pts = []
    while len(pts) < n:
        u, v = r.uniform(-1, 1), r.uniform(-1, 1)
        if u * u + v * v > 0.8:
            continue
        if any((u - a) ** 2 + (v - b) ** 2 < 0.0075 for a, b in pts):
            continue
        # keep a clear spot at the front-centre for the named players
        if v > 0.35 and abs(u) < 0.45:
            continue
        pts.append((u, v))
    for i in range(n):
        st = Style(f"p{i}", skin=r.choice(SKINS), shirt=r.choice(SHIRTS),
                   pants=r.choice(["#22223b", "#264653", "#3d405b", "#5e548e", "#6c584c"]),
                   hair=r.choice(HAIRS), hair_style=r.choice(["flat", "tall", "side", "spiky", "long", "none"]),
                   hat=r.choice([None, None, None, "cap", "band"]), hat_color=r.choice(SHIRTS))
        out.append((st, pts[i][0], pts[i][1], r.random() * 10))
    return out


def crowd(scene: Scene, t: float, alive: int, radius: float, leaving=(0, 0, 0.0), expr="neutral", arms="idle",
          panic=0.0, sleep=False, push=0.0, face_yaw=None, teleport=False, cam_pos=None, detail_near=12.0,
          clear=None, clear_r=2.4):
    rr = radius * 0.86
    lo, hi, lp = leaving
    for i, (st, u, v, ph) in enumerate(crowd_people()):
        if i >= max(alive, hi):
            continue
        x, z = u * rr, v * rr
        yaw = face_yaw if face_yaw is not None else math.atan2(-x, 18 - z) * 0.6
        walk = None
        e, a = expr, arms
        y = 0.0
        if lo <= i < hi and lp > 0:
            if teleport:
                # rise, spin, vanish in a burst
                q = clamp(lp / 0.6)
                if q >= 1:
                    poof(scene, x, 1.2 + 0.5, z, clamp((lp - 0.6) / 0.4), t)
                    continue
                y = q * 1.5
                yaw += q * 6
                e, a = "shocked", "cheer"
            else:
                d = math.hypot(u, v) or 1
                out = lp * radius * 1.6
                x += u / d * out
                z += v / d * out
                yaw = math.atan2(u, v)
                walk = t * 2.2 + ph
                e, a = ("happy", "cheer") if i % 3 else ("laugh", "idle")
        else:
            if panic:
                e, a = ("scared", "panic") if (i + int(t * 2)) % 3 == 0 else ("shocked", "idle")
                x += math.sin(t * 7 + ph) * 0.12 * panic
            if push:
                x += math.sin(t * 5 + ph * 2) * 0.18 * push
                z += math.cos(t * 4 + ph) * 0.1 * push
            if sleep and i % 4 != 0:
                e = "sleep"
        if clear is not None and math.hypot(x - clear[0], z - clear[1]) < clear_r:
            continue
        detail = True
        if cam_pos is not None:
            detail = math.dist((x, 1.5, z), cam_pos) < detail_near
        person(scene, st, x, z, yaw, Pose(t=t + ph, arms=a, expr=e, walk=walk, seed=ph, mouth=0.0), y=y, detail=detail)


def poof(scene, x, y, z, p, t):
    if p >= 1:
        return
    for k in range(10):
        a = k * TAU / 10
        b = (k % 3 - 1) * 0.6
        d = 0.3 + p * 1.4
        s = 0.28 * (1 - p)
        scene.cube(x + math.cos(a) * d, y + b * d * 0.6 + p * 0.5, z + math.sin(a) * d, s, s, s, "#ffffff", emissive=0.6)


def gem_pile(scene, x, y, z, t, n=60, s=1.0):
    r = random.Random(3)
    cols = ("#29d3ff", "#ff4fd8", "#7cff6b", "#ffd60a")
    for k in range(n):
        layer = int(math.sqrt(k) * 0.9)
        a = r.random() * TAU
        rad = (2.4 - layer * 0.45) * math.sqrt(r.random()) * s
        gem(scene, T(x + math.cos(a) * rad, y + 0.2 + layer * 0.32 * s, z + math.sin(a) * rad) @ RY(r.random() * 6),
            0.42 * s, t * 0.2 + k, cols[k % 4])


def chest(scene, x, z, t, open_=0.0, yaw=0.0, y=0.0):
    base = T(x, y, z) @ RY(yaw)
    scene.box(base @ T(0, 0.35, 0) @ S(1.0, 0.7, 0.8), "#a0703a")
    scene.box(base @ T(0, 0.35, 0.41) @ S(1.02, 0.08, 0.02), "#5c3a1e")
    lid = base @ T(0, 0.7, -0.4) @ RX(-open_ * 1.9) @ T(0, 0.12, 0.4)
    scene.box(lid @ S(1.0, 0.24, 0.8), "#8b5a2b")
    scene.box(base @ T(0, 0.6, 0.42) @ S(0.16, 0.2, 0.04), "#c0c6cf")
    if open_ > 0.2:
        for k in range(8):
            gem(scene, base @ T(-0.3 + (k % 4) * 0.2, 0.75 + (k // 4) * 0.15 + open_ * 0.1, -0.1 + (k % 2) * 0.15),
                0.16, t + k, ("#29d3ff", "#ffd60a")[k % 2])


def target(scene, x, y, z, yaw=0.0, hit=None):
    base = T(x, y, z) @ RY(yaw)
    for i, c in enumerate(("#ffffff", "#e63946", "#ffffff", "#e63946", "#ffd60a")):
        s = 1.6 - i * 0.32
        scene.box(base @ T(0, 0, 0.02 * i) @ S(s, s, 0.06), c, emissive=0.15 if i == 4 else 0.0)
    scene.box(base @ T(0, -1.6, -0.1) @ S(0.15, 1.8, 0.15), "#7a4f2a")


def arrow(scene, m):
    scene.box(m @ S(0.04, 0.04, 0.9), "#8b5a2b")
    scene.box(m @ T(0, 0, 0.47) @ S(0.08, 0.08, 0.1), "#cccccc")
    scene.box(m @ T(0, 0, -0.42) @ S(0.12, 0.02, 0.12), "#ffffff")


def golden_house(scene, x, z, t, built=1.0, yaw=0.0):
    base = T(x, 0, z) @ RY(yaw)
    cells = []
    for yy in range(4):
        for xx in range(-2, 3):
            for zz in range(-2, 3):
                if yy < 3 and (abs(xx) == 2 or abs(zz) == 2):
                    if zz == 2 and xx == 0 and yy < 2:
                        continue
                    if zz == 2 and abs(xx) == 1 and yy == 1:
                        cells.append((xx, yy, zz, "#29d3ff"))
                        continue
                    cells.append((xx, yy, zz, "#ffd60a"))
                elif yy == 3 and abs(xx) <= 2 and abs(zz) <= 2:
                    cells.append((xx, yy, zz, "#e63946"))
    n = int(len(cells) * clamp(built))
    for xx, yy, zz, c in cells[:n]:
        scene.box(base @ T(xx, yy + 0.5, zz) @ S(1, 1, 1), c, emissive=0.25 if c == "#ffd60a" else 0.4 if c == "#29d3ff" else 0.0)


def bed(scene, x, z, yaw=0.0, color="#e63946"):
    base = T(x, 0, z) @ RY(yaw)
    scene.box(base @ T(0, 0.28, 0) @ S(1.0, 0.56, 2.0), color)
    scene.box(base @ T(0, 0.6, -0.75) @ S(0.98, 0.12, 0.45), "#ffffff")
    scene.box(base @ T(0, 0.14, 0) @ S(1.02, 0.28, 2.02), "#a0703a")
