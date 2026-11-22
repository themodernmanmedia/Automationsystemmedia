"""Original blocky-voxel art style: block people, pixel textures, block worlds.

Everything here is drawn procedurally (no assets from any existing game).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

import cairo

from .config import H, W
from .gfx import (
    TAU, at, circle, clamp, ellipse, fill, glow, hexc, lerp, lin_grad, rad_grad, rrect, saved,
    set_color, shade, soft_shadow, stroke, text,
)

D2R = math.pi / 180

# --------------------------------------------------------------------------
# Pixel textures
# --------------------------------------------------------------------------


def _surface_from_pixels(pixels: list[list[tuple]]) -> cairo.ImageSurface:
    h, w = len(pixels), len(pixels[0])
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surf)
    for y, row in enumerate(pixels):
        for x, c in enumerate(row):
            ctx.rectangle(x, y, 1, 1)
            ctx.set_source_rgba(*c)
            ctx.fill()
    return surf


@lru_cache(maxsize=64)
def texture(kind: str, frame: int = 0) -> cairo.ImageSurface:
    r = random.Random(hash((kind, frame)) & 0xFFFF)
    px = []
    for y in range(16):
        row = []
        for x in range(16):
            n = r.random()
            if kind == "grass_top":
                c = shade("#5fbf3f", (n - 0.5) * 0.35)
            elif kind == "grass_side":
                edge = 3 + (1 if r.random() < 0.4 else 0)
                c = shade("#5fbf3f", (n - 0.5) * 0.3) if y < edge else shade("#8b5a2b", (n - 0.5) * 0.35)
            elif kind == "dirt":
                c = shade("#8b5a2b", (n - 0.5) * 0.4)
            elif kind == "stone":
                c = shade("#8a8f98", (n - 0.5) * 0.35)
            elif kind == "lava":
                v = 0.5 + 0.5 * math.sin((x * 0.7 + y * 0.5) + frame * 0.6 + n * 1.5)
                c = (1.0, 0.35 + 0.45 * v, 0.05 + 0.1 * v, 1)
            elif kind == "gold":
                c = shade("#f5c518", (n - 0.5) * 0.3 + (0.25 if (x + y) % 7 == 0 else 0))
            elif kind == "gem":
                c = shade("#29d3ff", (n - 0.5) * 0.25 + (0.35 if (x - y) % 5 == 0 else 0))
            elif kind == "wood":
                c = shade("#a0703a", (0.1 if x % 4 == 0 else 0) + (n - 0.5) * 0.2)
            elif kind == "leaves":
                c = shade("#2f8f3a", (n - 0.5) * 0.5)
            elif kind == "sand":
                c = shade("#e8d39a", (n - 0.5) * 0.2)
            elif kind == "water":
                v = 0.5 + 0.5 * math.sin(x * 0.6 + frame * 0.5)
                c = (0.15, 0.45 + 0.1 * v, 0.9, 1)
            elif kind == "plank":
                c = shade("#c49a5a", (-0.2 if y % 4 == 3 else 0) + (n - 0.5) * 0.15)
            else:
                c = (1, 0, 1, 1)
            if len(c) == 3:
                c = (*c, 1)
            row.append(c)
        px.append(row)
    return _surface_from_pixels(px)


def block_face(ctx, kind, x, y, size, frame=0, shade_amt=0.0):
    """Draw one 16x16 texture scaled into a square (nearest-neighbour)."""
    surf = texture(kind, frame % 8 if kind in ("lava", "water") else 0)
    with saved(ctx):
        ctx.translate(x, y)
        ctx.scale(size / 16, size / 16)
        pat = cairo.SurfacePattern(surf)
        pat.set_filter(cairo.FILTER_NEAREST)
        ctx.set_source(pat)
        ctx.rectangle(0, 0, 16, 16)
        ctx.fill()
        if shade_amt:
            ctx.set_source_rgba(0, 0, 0, shade_amt)
            ctx.rectangle(0, 0, 16, 16)
            ctx.fill()


# --------------------------------------------------------------------------
# Block person
# --------------------------------------------------------------------------

ARMS = {
    "idle": (4, 4),
    "up": (165, 165),
    "cheer": (150, 150),
    "wave": (4, 150),
    "point": (4, 92),
    "point_l": (92, 4),
    "out": (70, 70),
    "hold": (4, 40),
    "panic": (130, 130),
    "shrug": (55, 55),
    "hug": (40, 40),
}

EXPR = {
    #          mouth_w mouth_h curve brow   eye_h
    "neutral": (0.40, 0.08, 0.0, 0.0, 1.0),
    "happy": (0.50, 0.14, 1.0, 0.0, 1.0),
    "laugh": (0.55, 0.30, 1.0, 0.1, 0.4),
    "sad": (0.38, 0.08, -1.0, -0.6, 0.9),
    "shocked": (0.26, 0.34, 0.0, 0.6, 1.3),
    "angry": (0.42, 0.08, -0.6, 1.0, 0.8),
    "smug": (0.36, 0.08, 0.6, 0.6, 0.7),
    "scared": (0.40, 0.22, -0.5, -0.8, 1.3),
    "determined": (0.36, 0.08, 0.0, 1.0, 0.85),
    "sleep": (0.25, 0.06, 0.0, 0.0, 0.0),
}


@dataclass
class BPose:
    t: float = 0.0
    arms: object = "idle"
    expr: str = "neutral"
    mouth: float = 0.0
    walk: Optional[float] = None
    look: float = 0.0          # -1..1 horizontal gaze
    bounce: float = 0.0
    held: Optional[str] = None
    tilt: float = 0.0          # body tilt (deg)
    shadow: bool = True
    blink: Optional[float] = None
    seed: float = 0.0
    sweat: float = 0.0
    tears: float = 0.0


@dataclass
class BlockPerson:
    name: str
    skin: str = "#e0ac7e"
    shirt: str = "#3a86ff"
    pants: str = "#22223b"
    shoes: str = "#2b2d42"
    hair: Optional[str] = "#3d2b1f"
    hair_style: str = "flat"     # flat | tall | side | none | long | spiky
    hat: Optional[str] = None    # crown | cap | headset | band | None
    hat_color: str = "#e63946"
    eye: str = "#2a2a6a"
    stripe: Optional[str] = None
    size: float = 1.0            # overall scale multiplier (kids smaller)
    head_scale: float = 1.0

    def draw(self, ctx, x, y, s, p: BPose, detail=True):
        s = s * self.size
        with at(ctx, x, y, s):
            if p.shadow:
                ctx.save()
                ctx.scale(1, 0.25)
                circle(ctx, 0, 0, 70)
                ctx.restore()
                fill(ctx, (0, 0, 0, 0.25))
            self._body(ctx, p, detail)

    def _limb(self, ctx, px, py, w, h, ang, top_c, bot_c=None, split=0.0, outline=True):
        with at(ctx, px, py, rot=ang):
            ctx.rectangle(-w / 2, 0, w, h)
            fill(ctx, top_c)
            if bot_c is not None:
                ctx.rectangle(-w / 2, h * split, w, h * (1 - split))
                fill(ctx, bot_c)
            # shading stripe
            ctx.rectangle(w / 2 - w * 0.22, 0, w * 0.22, h)
            fill(ctx, (0, 0, 0, 0.12))
            if outline:
                ctx.rectangle(-w / 2, 0, w, h)
                stroke(ctx, (0, 0, 0, 0.35), 3, join=cairo.LINE_JOIN_MITER)

    def _body(self, ctx, p: BPose, detail):
        t = p.t
        swing = math.sin(p.walk * TAU) if p.walk is not None else 0.0
        bob = -abs(math.sin(p.walk * TAU)) * 8 if p.walk is not None else math.sin(t * 2.2 + p.seed) * 1.5
        bob += p.bounce
        # legs
        hip_y = -96
        for side, k in ((-1, 1), (1, -1)):
            self._limb(ctx, side * 16, hip_y + bob * 0.3, 32, 96, swing * 0.45 * k, self.pants, self.shoes, 0.82)
        with at(ctx, 0, bob, rot=p.tilt * D2R):
            # torso
            ctx.rectangle(-32, -192, 64, 96)
            fill(ctx, self.shirt)
            if self.stripe:
                ctx.rectangle(-32, -160, 64, 16)
                fill(ctx, self.stripe)
            ctx.rectangle(14, -192, 18, 96)
            fill(ctx, (0, 0, 0, 0.12))
            ctx.rectangle(-32, -192, 64, 96)
            stroke(ctx, (0, 0, 0, 0.35), 3, join=cairo.LINE_JOIN_MITER)
            # arms
            arms = ARMS[p.arms] if isinstance(p.arms, str) else p.arms
            la, ra = arms
            if p.arms == "wave":
                ra += math.sin(t * 14) * 18
            if p.arms in ("panic",):
                la += math.sin(t * 20) * 20
                ra -= math.sin(t * 20 + 1) * 20
            if p.walk is not None and p.arms == "idle":
                la, ra = 4 + swing * 25, 4 - swing * 25
            for side, a in ((-1, la), (1, ra)):
                self._limb(ctx, side * 46, -188, 28, 92, -side * a * D2R, self.shirt, self.skin, 0.62)
            if p.held:
                ang = ra * D2R
                hx = 46 + math.sin(ang) * 80
                hy = -188 + math.cos(ang) * 80
                held_item(ctx, p.held, hx, hy, t)
            # head
            hs = 1.0 * self.head_scale
            with at(ctx, 0, -192, s=hs, rot=math.sin(t * 1.7 + p.seed) * 0.03):
                self._head(ctx, p, detail)

    def _head(self, ctx, p: BPose, detail):
        S = 72
        x0, y0 = -S / 2, -S
        ctx.rectangle(x0, y0, S, S)
        fill(ctx, self.skin)
        ctx.rectangle(x0 + S * 0.78, y0, S * 0.22, S)
        fill(ctx, (0, 0, 0, 0.1))
        # hair
        hc = self.hair
        if hc and self.hair_style != "none":
            if self.hair_style == "flat":
                ctx.rectangle(x0, y0, S, S * 0.22)
                fill(ctx, hc)
                ctx.rectangle(x0, y0, S * 0.12, S * 0.45)
                fill(ctx, hc)
                ctx.rectangle(x0 + S * 0.88, y0, S * 0.12, S * 0.45)
                fill(ctx, hc)
            elif self.hair_style == "tall":
                ctx.rectangle(x0 - 2, y0 - S * 0.2, S + 4, S * 0.36)
                fill(ctx, hc)
            elif self.hair_style == "side":
                ctx.rectangle(x0, y0, S, S * 0.2)
                fill(ctx, hc)
                ctx.rectangle(x0, y0, S * 0.45, S * 0.32)
                fill(ctx, hc)
            elif self.hair_style == "long":
                ctx.rectangle(x0 - 6, y0 - 4, S + 12, S * 0.24)
                fill(ctx, hc)
                ctx.rectangle(x0 - 6, y0, S * 0.18, S * 1.25)
                fill(ctx, hc)
                ctx.rectangle(x0 + S * 0.9, y0, S * 0.18, S * 1.25)
                fill(ctx, hc)
            elif self.hair_style == "spiky":
                for k in range(4):
                    ctx.rectangle(x0 + k * S / 4, y0 - S * (0.18 if k % 2 else 0.1), S / 4, S * 0.3)
                    fill(ctx, hc)
        e = EXPR.get(p.expr, EXPR["neutral"])
        mw, mh, curve, brow, eye_h = e
        lk = p.look * S * 0.06
        # blink
        blink = p.blink
        if blink is None:
            ph = (p.t + p.seed * 1.3) % 3.9
            blink = 1.0 if ph < 0.12 else 0.0
        eh = S * 0.18 * eye_h * (1 - blink)
        for side in (-1, 1):
            ex = side * S * 0.2 - S * 0.09
            ey = y0 + S * 0.42
            if p.expr == "sleep" or eh < 2:
                ctx.rectangle(ex, ey + S * 0.07, S * 0.18, 3.5)
                fill(ctx, "#1d1d1d")
                continue
            ctx.rectangle(ex, ey + (S * 0.18 - eh) / 2, S * 0.18, eh)
            fill(ctx, "#ffffff")
            ctx.rectangle(ex + S * 0.045 + lk + (S * 0.045 if side < 0 else 0) * 0, ey + (S * 0.18 - eh) / 2 + eh * 0.25,
                          S * 0.09, eh * 0.75)
            fill(ctx, self.eye)
            # brows
            if abs(brow) > 0.05:
                by = ey - S * 0.08
                with at(ctx, ex + S * 0.09, by, rot=side * brow * 0.35):
                    ctx.rectangle(-S * 0.11, -3, S * 0.22, 6)
                    fill(ctx, shade(self.hair or "#333333", -0.3))
        # mouth (pixel style)
        open_h = S * (mh + p.mouth * 0.22)
        w = S * mw * (1 + p.mouth * 0.1)
        my = y0 + S * 0.74
        ctx.rectangle(-w / 2, my - open_h / 2, w, max(4, open_h))
        fill(ctx, "#3a1010" if open_h > 7 else "#5a2a22")
        if curve > 0.2:
            ctx.rectangle(-w / 2 - 5, my - open_h / 2 - 6, 6, 6)
            fill(ctx, "#5a2a22")
            ctx.rectangle(w / 2 - 1, my - open_h / 2 - 6, 6, 6)
            fill(ctx, "#5a2a22")
        elif curve < -0.2:
            ctx.rectangle(-w / 2 - 5, my + open_h / 2, 6, 6)
            fill(ctx, "#5a2a22")
            ctx.rectangle(w / 2 - 1, my + open_h / 2, 6, 6)
            fill(ctx, "#5a2a22")
        if p.sweat > 0.01:
            ctx.rectangle(S * 0.42, y0 + S * 0.15, 8, 14)
            fill(ctx, (0.55, 0.8, 1, p.sweat))
        if p.tears > 0.01:
            for side in (-1, 1):
                ph = (p.t * 1.2 + (0.5 if side > 0 else 0)) % 1
                ctx.rectangle(side * S * 0.2 - S * 0.03, y0 + S * 0.6 + ph * S * 0.4, 7, 10)
                fill(ctx, (0.55, 0.8, 1, 0.9 * p.tears))
        ctx.rectangle(x0, y0, S, S)
        stroke(ctx, (0, 0, 0, 0.4), 3, join=cairo.LINE_JOIN_MITER)
        # hats
        if self.hat == "crown":
            pts = [(x0 - 4, y0), (x0 - 4, y0 - 30), (x0 + 14, y0 - 16), (0, y0 - 38), (S / 2 - 14, y0 - 16),
                   (S / 2 + 4, y0 - 30), (S / 2 + 4, y0)]
            ctx.move_to(*pts[0])
            for q in pts[1:]:
                ctx.line_to(*q)
            ctx.close_path()
            fill(ctx, "#ffd60a", preserve=True)
            stroke(ctx, "#b08900", 3)
            ctx.rectangle(-6, y0 - 16, 12, 12)
            fill(ctx, "#e63946")
        elif self.hat == "cap":
            ctx.rectangle(x0 - 2, y0 - 12, S + 4, 24)
            fill(ctx, self.hat_color)
            ctx.rectangle(x0 + S * 0.4, y0 + 4, S * 0.75, 10)
            fill(ctx, shade(self.hat_color, -0.2))
        elif self.hat == "headset":
            ctx.rectangle(x0 - 10, y0 + S * 0.3, 12, 26)
            fill(ctx, "#222")
            ctx.rectangle(x0 + S - 2, y0 + S * 0.3, 12, 26)
            fill(ctx, "#222")
            ctx.rectangle(x0 - 6, y0 - 10, S + 12, 10)
            fill(ctx, "#222")
            ctx.move_to(x0 - 4, y0 + S * 0.55)
            ctx.line_to(x0 + S * 0.25, y0 + S * 0.8)
            stroke(ctx, "#222", 4)
        elif self.hat == "band":
            ctx.rectangle(x0 - 2, y0 + S * 0.18, S + 4, 10)
            fill(ctx, self.hat_color)


def held_item(ctx, kind, x, y, t):
    if kind == "mic":
        with at(ctx, x, y, rot=-0.4):
            ctx.rectangle(-6, -10, 12, 46)
            fill(ctx, "#333")
            ctx.rectangle(-12, -34, 24, 26)
            fill(ctx, "#888", )
    elif kind == "briefcase":
        with at(ctx, x, y + 30):
            ctx.rectangle(-48, -32, 96, 64)
            fill(ctx, "#5c3a1e", preserve=True)
            stroke(ctx, "#2b1a0d", 4)
            ctx.rectangle(-16, -44, 32, 14)
            stroke(ctx, "#2b1a0d", 6)
            ctx.rectangle(-8, -6, 16, 12)
            fill(ctx, "#ffd60a")
    elif kind == "snack":
        with at(ctx, x, y):
            ctx.rectangle(-18, -30, 36, 44)
            fill(ctx, "#ff006e", preserve=True)
            stroke(ctx, "#8a0039", 3)
            ctx.rectangle(-10, -18, 20, 14)
            fill(ctx, "#ffd60a")
    elif kind == "gem":
        gem(ctx, x, y - 10, 0.5, t)


def gem(ctx, x, y, s=1.0, t=0.0, c="#29d3ff"):
    with at(ctx, x, y, s):
        glow(ctx, 0, 0, 80, c, 0.35 + 0.15 * math.sin(t * 4))
        pts = [(-40, -14), (-22, -38), (22, -38), (40, -14), (0, 40)]
        ctx.move_to(*pts[0])
        for q in pts[1:]:
            ctx.line_to(*q)
        ctx.close_path()
        ctx.set_source(lin_grad(-40, -40, 40, 40, [(0, shade(c, 0.5)), (0.5, c), (1, shade(c, -0.35))]))
        ctx.fill_preserve()
        stroke(ctx, shade(c, -0.5), 3)
        ctx.move_to(-40, -14)
        ctx.line_to(40, -14)
        stroke(ctx, (1, 1, 1, 0.6), 3)
        ctx.move_to(-22, -38)
        ctx.line_to(-8, -14)
        ctx.line_to(0, 40)
        ctx.line_to(8, -14)
        ctx.line_to(22, -38)
        stroke(ctx, (1, 1, 1, 0.35), 2.5)


def gem_pile(ctx, x, y, s, t, n=40):
    r = random.Random(3)
    items = []
    for k in range(n):
        layer = int(math.sqrt(k))
        gx = (r.random() - 0.5) * (220 - layer * 30)
        gy = -layer * 26 - r.random() * 10
        items.append((gy, gx, ("#29d3ff", "#ff4fd8", "#7cff6b", "#ffd60a")[k % 4]))
    with at(ctx, x, y, s):
        glow(ctx, 0, -80, 260, "#29d3ff", 0.35)
        for gy, gx, c in sorted(items, reverse=True):
            gem(ctx, gx, gy, 0.55, t + gx, c)


# --------------------------------------------------------------------------
# World
# --------------------------------------------------------------------------

HORIZON = 470


def sky(ctx, t, night=0.0, sunset=0.0):
    top = mix_c("#4aa8ff", "#0b1030", night)
    bot = mix_c("#bfe6ff", "#24305e", night)
    if sunset:
        bot = mix_c(bot, "#ff9e5e", sunset)
    ctx.set_source(lin_grad(0, 0, 0, HORIZON + 50, [(0, top), (1, bot)]))
    ctx.rectangle(0, 0, W, HORIZON + 60)
    ctx.fill()
    if night > 0.3:
        r = random.Random(5)
        for _ in range(80):
            x, y = r.random() * W, r.random() * HORIZON
            a = night * (0.5 + 0.5 * math.sin(t * 2 + x))
            ctx.rectangle(x, y, 4, 4)
            fill(ctx, (1, 1, 1, a))
        ctx.rectangle(1500, 90, 80, 80)
        fill(ctx, (0.95, 0.95, 1, night))
    else:
        # square sun
        glow(ctx, 1560, 130, 200, "#fff6b0", 0.6)
        ctx.rectangle(1510, 80, 100, 100)
        fill(ctx, "#fff7a0")
    # block clouds
    for k in range(5):
        cx = ((t * 14 + k * 430) % (W + 400)) - 200
        cy = 80 + (k % 3) * 70
        for dx, dy, w_, h_ in ((0, 0, 200, 40), (40, -30, 110, 40), (120, -20, 90, 30)):
            ctx.rectangle(cx + dx, cy + dy, w_, h_)
            fill(ctx, (1, 1, 1, 0.85 - 0.5 * night))


def mix_c(a, b, t):
    a = hexc(a) if isinstance(a, str) else a
    b = hexc(b) if isinstance(b, str) else b
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def hills(ctx, t, night=0.0):
    r = random.Random(8)
    for layer, (col, base, amp, bw) in enumerate((("#7fb8a0", HORIZON - 40, 120, 60), ("#4f9e5a", HORIZON, 70, 48))):
        x = -20
        c = mix_c(col, "#1a2440", night * 0.7)
        while x < W + 40:
            h = amp * (0.4 + 0.6 * abs(math.sin(x * 0.004 + layer))) + r.random() * 20
            h = int(h / 16) * 16
            ctx.rectangle(x, base - h, bw, h + 80)
            fill(ctx, c)
            x += bw
    # trees
    for k, tx in enumerate((120, 330, 1680, 1830)):
        ty = HORIZON + 10
        ctx.rectangle(tx - 10, ty - 90, 20, 90)
        fill(ctx, mix_c("#7a4f2a", "#20182a", night * 0.6))
        ctx.rectangle(tx - 50, ty - 170, 100, 90)
        fill(ctx, mix_c("#2f8f3a", "#13301f", night * 0.6))
        ctx.rectangle(tx - 30, ty - 200, 60, 40)
        fill(ctx, mix_c("#3aa548", "#13301f", night * 0.6))


def ground(ctx, t, kind="grass_top", night=0.0, frame=None):
    """Perspective block floor from HORIZON to bottom."""
    frame = int(t * 6) if frame is None else frame
    rows = 14
    y = HORIZON
    vx = W / 2
    for i in range(rows):
        f0 = i / rows
        f1 = (i + 1) / rows
        y0 = HORIZON + (H + 120 - HORIZON) * (f0 ** 1.6)
        y1 = HORIZON + (H + 120 - HORIZON) * (f1 ** 1.6)
        tile = 30 + 230 * ((f0 + f1) / 2) ** 1.2
        off = (W / 2) % tile
        x = -tile + (vx % tile)
        while x < W + tile:
            ctx.save()
            ctx.rectangle(x, y0, tile, y1 - y0)
            ctx.clip()
            block_face(ctx, kind, x, y0, max(tile, y1 - y0), frame)
            ctx.restore()
            x += tile
        ctx.move_to(0, y0)
        ctx.line_to(W, y0)
        stroke(ctx, (0, 0, 0, 0.08), 2)
    if night:
        ctx.set_source_rgba(0.03, 0.05, 0.18, 0.55 * night)
        ctx.rectangle(0, HORIZON, W, H)
        ctx.fill()


ARENA_C = (960, 800)
ARENA_R = (760, 230)


def arena(ctx, t, radius=1.0, lava=0.0, night=0.0, glow_c="#ffd60a"):
    """Arena floor: ring of radius (fraction) at ARENA_C. Lava outside if lava>0."""
    cx, cy = ARENA_C
    rx, ry = ARENA_R[0] * radius, ARENA_R[1] * radius
    if lava > 0:
        with saved(ctx):
            ctx.rectangle(0, HORIZON + 40 + (1 - lava) * 500, W, H)
            ctx.clip()
            ground(ctx, t, "lava", 0)
            glow(ctx, W / 2, H, 900, "#ff6a00", 0.3 * lava)
        # safe platform inside ring
        with saved(ctx):
            ellipse(ctx, cx, cy, rx, ry)
            ctx.clip()
            ground(ctx, t, "grass_top", night)
        # platform edge (dirt side)
        with saved(ctx):
            ellipse(ctx, cx, cy + 26, rx, ry)
            ellipse(ctx, cx, cy, rx, ry)
            ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            ctx.clip()
            ctx.rectangle(cx - rx, cy - ry, rx * 2, ry * 2 + 40)
            fill(ctx, "#6b4423")
    # ring
    pulse = 0.6 + 0.4 * math.sin(t * 5)
    ellipse(ctx, cx, cy, rx, ry)
    stroke(ctx, (*hexc(glow_c)[:3], 0.35 * pulse), 28)
    ellipse(ctx, cx, cy, rx, ry)
    stroke(ctx, glow_c, 9)
    # block markers on ring
    for k in range(24):
        a = k * TAU / 24 + t * 0.15
        bx = cx + math.cos(a) * rx
        by = cy + math.sin(a) * ry
        sz = 14 + 10 * (by - (cy - ry)) / (2 * ry)
        ctx.rectangle(bx - sz / 2, by - sz / 2, sz, sz)
        fill(ctx, glow_c)


def world(ctx, t, night=0.0, sunset=0.0):
    sky(ctx, t, night, sunset)
    hills(ctx, t, night)
    ground(ctx, t, "grass_top", night)


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
    for i in range(n):
        p = BlockPerson(
            f"p{i}", skin=r.choice(SKINS), shirt=r.choice(SHIRTS), pants=r.choice(["#22223b", "#264653", "#3d405b", "#5e548e", "#6c584c"]),
            hair=r.choice(HAIRS), hair_style=r.choice(["flat", "tall", "side", "spiky", "long", "none"]),
            hat=r.choice([None, None, None, "cap", "band"]), hat_color=r.choice(SHIRTS),
        )
        # position in unit disk (rejection)
        while True:
            u, v = r.uniform(-1, 1), r.uniform(-1, 1)
            if u * u + v * v < 0.82:
                break
        out.append((p, u, v, r.random() * 10))
    return out


def crowd(ctx, t, alive: int, radius=1.0, leaving=(0, 0, 0.0), expr="neutral", arms="idle", skip=(), scale=1.0,
          panic=0.0, sleep=False, push=0.0):
    """Draw players 0..alive-1 inside the ring.

    leaving = (lo, hi, p): players lo..hi-1 are running out of the ring with progress p (0..1).
    """
    cx, cy = ARENA_C
    rx, ry = ARENA_R[0] * radius * 0.92, ARENA_R[1] * radius * 0.92
    people = crowd_people()
    lo, hi, lp = leaving
    items = []
    for i, (person, u, v, ph) in enumerate(people):
        if i in skip:
            continue
        if i >= max(alive, hi):
            continue
        x = cx + u * rx
        y = cy + v * ry
        walk = None
        e, a = expr, arms
        alpha = 1.0
        if lo <= i < hi and lp > 0:
            d = math.hypot(u, v) or 1
            out = lp * 1.4
            x = cx + (u / d) * (abs(u) * rx + out * ARENA_R[0] * 0.8)
            y = cy + (v / d) * (abs(v) * ry + out * ARENA_R[1] * 0.8)
            walk = t * 2.4 + ph
            e, a = ("happy", "cheer") if i % 3 else ("scared", "panic")
            alpha = 1.0 - clamp((lp - 0.7) / 0.3)
        elif panic:
            e, a = ("scared", "panic") if (i + int(t * 2)) % 3 == 0 else ("shocked", "idle")
            x += math.sin(t * 9 + ph) * 6 * panic
        if push:
            x += math.sin(t * 6 + ph * 2) * 10 * push
        if sleep and i % 4 != 0:
            e = "sleep"
        depth = (y - (cy - ry)) / (2 * ry + 1)
        s = (0.34 + 0.22 * depth) * scale
        items.append((y, x, s, person, BPose(t=t + ph, arms=a, expr=e, walk=walk, seed=ph), alpha))
    items.sort(key=lambda it: it[0])
    for y, x, s, person, pose, alpha in items:
        if alpha <= 0.01:
            continue
        if alpha < 1:
            ctx.push_group()
            person.draw(ctx, x, y, s, pose, detail=False)
            ctx.pop_group_to_source()
            ctx.paint_with_alpha(alpha)
            # poof
            pp = clamp((1 - alpha))
            for k in range(6):
                a_ = k * TAU / 6
                ctx.rectangle(x + math.cos(a_) * 60 * pp - 8, y - 60 + math.sin(a_) * 40 * pp - 8, 16, 16)
                fill(ctx, (1, 1, 1, 0.8 * (1 - pp)))
        else:
            person.draw(ctx, x, y, s, pose, detail=False)


def chest(ctx, x, y, s, t, open_=0.0, glow_c="#ffd60a"):
    with at(ctx, x, y, s):
        soft_shadow(ctx, 0, 0, 120, 20, 0.3)
        if open_ > 0:
            glow(ctx, 0, -120, 260 * open_, glow_c, 0.7 * open_)
            for k in range(8):
                a = -math.pi / 2 + (k - 3.5) * 0.18
                ctx.move_to(0, -90)
                ctx.line_to(math.cos(a) * 420 * open_, -90 + math.sin(a) * 420 * open_)
                stroke(ctx, (1, 0.95, 0.5, 0.35 * open_), 18)
        block_face(ctx, "plank", -100, -140, 200)
        ctx.rectangle(-100, -140, 200, 140)
        stroke(ctx, "#5c3a1e", 6, join=cairo.LINE_JOIN_MITER)
        with at(ctx, 0, -140 - open_ * 70, sx=1.0, sy=1.0 - 0.55 * open_):
            with saved(ctx):
                ctx.rectangle(-100, -70, 200, 70)
                ctx.clip()
                block_face(ctx, "plank", -100, -170, 200)
            ctx.rectangle(-100, -70, 200, 70)
            stroke(ctx, "#5c3a1e", 6, join=cairo.LINE_JOIN_MITER)
        ctx.rectangle(-18, -160, 36, 40)
        fill(ctx, "#c0c6cf", preserve=True)
        stroke(ctx, "#5c6270", 4)
