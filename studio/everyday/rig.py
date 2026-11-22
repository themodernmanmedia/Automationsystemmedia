"""Procedural 2D character rig drawn with cairo.

A ``Character`` is a set of style choices (skin, hair, outfit). Every frame it
is drawn from a ``Pose`` -- arm angles, expression, mouth openness, gaze, walk
phase -- so scenes animate by changing numbers rather than swapping sprites.

Coordinates: the character's origin is the point on the ground between the
feet. At scale 1 a standing adult is ~560 px tall in the 1920x1080 frame.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Optional

import cairo

from .gfx import (
    TAU, at, circle, clamp, ellipse, fill, hexc, lerp, line, lin_grad, mix,
    rad_grad, rrect, saved, set_color, shade, smooth_path, soft_shadow, stroke,
)

D2R = math.pi / 180

# --------------------------------------------------------------------------
# Expressions
# --------------------------------------------------------------------------

EXPRESSIONS: dict[str, dict[str, float]] = {
    #            brow_y  brow_tilt  m_curve  m_open  m_w   lid   eye_s  happy_eyes  blush
    "neutral":  dict(brow_y=0, brow_tilt=0.0, m_curve=0.25, m_open=0.0, m_w=1.0, lid=0.0, eye_s=1.0, closed=0, blush=0.15),
    "happy":    dict(brow_y=5, brow_tilt=-0.1, m_curve=0.95, m_open=0.12, m_w=1.15, lid=0.0, eye_s=1.0, closed=0, blush=0.35),
    "laugh":    dict(brow_y=8, brow_tilt=-0.2, m_curve=1.0, m_open=0.65, m_w=1.25, lid=0.0, eye_s=1.0, closed=1, blush=0.55),
    "sad":      dict(brow_y=3, brow_tilt=-0.75, m_curve=-0.7, m_open=0.0, m_w=0.85, lid=0.25, eye_s=1.0, closed=0, blush=0.1),
    "cry":      dict(brow_y=5, brow_tilt=-0.9, m_curve=-0.9, m_open=0.25, m_w=0.9, lid=0.3, eye_s=1.0, closed=0, blush=0.3),
    "angry":    dict(brow_y=-6, brow_tilt=0.8, m_curve=-0.45, m_open=0.0, m_w=0.95, lid=0.2, eye_s=0.95, closed=0, blush=0.2),
    "surprised":dict(brow_y=16, brow_tilt=0.0, m_curve=0.0, m_open=0.75, m_w=0.6, lid=0.0, eye_s=1.2, closed=0, blush=0.1),
    "shocked":  dict(brow_y=20, brow_tilt=-0.2, m_curve=-0.2, m_open=1.0, m_w=0.75, lid=0.0, eye_s=1.35, closed=0, blush=0.0),
    "worried":  dict(brow_y=8, brow_tilt=-0.65, m_curve=-0.35, m_open=0.08, m_w=0.8, lid=0.05, eye_s=1.05, closed=0, blush=0.1),
    "smug":     dict(brow_y=2, brow_tilt=0.35, m_curve=0.6, m_open=0.0, m_w=0.95, lid=0.35, eye_s=1.0, closed=0, blush=0.2),
    "blank":    dict(brow_y=-2, brow_tilt=0.0, m_curve=0.0, m_open=0.0, m_w=0.7, lid=0.45, eye_s=1.0, closed=0, blush=0.0),
    "content":  dict(brow_y=3, brow_tilt=-0.15, m_curve=0.7, m_open=0.0, m_w=1.0, lid=0.0, eye_s=1.0, closed=1, blush=0.35),
    "awkward":  dict(brow_y=6, brow_tilt=-0.4, m_curve=0.15, m_open=0.0, m_w=1.2, lid=0.1, eye_s=1.0, closed=0, blush=0.4),
}


def get_expr(e) -> dict[str, float]:
    if isinstance(e, dict):
        return e
    return EXPRESSIONS[e]


def blend_expr(a, b, t: float) -> dict[str, float]:
    a, b = get_expr(a), get_expr(b)
    t = clamp(t)
    return {k: lerp(a[k], b[k], t) for k in a}


# --------------------------------------------------------------------------
# Arm poses: (shoulder_deg, elbow_deg) for (screen-left arm, screen-right arm)
# shoulder: 0 = hanging down, 90 = straight out sideways, 180 = straight up.
# elbow: extra rotation of the forearm; negative folds it across the body.
# --------------------------------------------------------------------------

POSES: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
    "idle":      ((10, -6), (10, -6)),
    "relaxed":   ((6, -14), (6, -14)),
    "wave":      ((10, -6), (150, 20)),
    "hips":      ((42, -118), (42, -118)),
    "shrug":     ((48, 78), (48, 78)),
    "phone":     ((10, -6), (22, -150)),
    "phone2":    ((22, -140), (22, -140)),
    "plate":     ((22, -92), (22, -92)),
    "arms_up":   ((158, 12), (158, 12)),
    "point":     ((10, -6), (95, 0)),
    "point_l":   ((95, 0), (10, -6)),
    "facepalm":  ((10, -6), (24, -162)),
    "crossed":   ((22, -122), (22, -112)),
    "think":     ((30, -112), (20, -158)),
    "hug":       ((72, -58), (72, -58)),
    "type":      ((16, -78), (16, -78)),
    "book":      ((24, -118), (24, -118)),
    "hold_r":    ((10, -6), (30, -90)),
    "phone_ear": ((10, -6), (35, -175)),
    "fist":      ((10, -6), (130, 30)),
    "cover":     ((24, -150), (24, -150)),
}


def get_pose(p):
    if isinstance(p, tuple):
        return p
    return POSES[p]


def blend_pose(a, b, t: float):
    a, b = get_pose(a), get_pose(b)
    t = clamp(t)
    return tuple(tuple(lerp(x, y, t) for x, y in zip(sa, sb)) for sa, sb in zip(a, b))


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------


@dataclass
class Pose:
    t: float = 0.0                 # time (drives idle motion & blinking)
    arms: object = "idle"          # name or ((l_sh, l_el), (r_sh, r_el))
    expr: object = "neutral"       # name or dict
    mouth: float = 0.0             # 0..1 talk openness (lip sync)
    look: tuple = (0.0, 0.0)       # gaze -1..1
    facing: float = 0.0            # -1 (screen left) .. 1 (screen right) head turn
    walk: Optional[float] = None   # walk phase in cycles; None = standing
    sit: bool = False
    lean: float = 0.0              # body tilt degrees
    head_tilt: float = 0.0         # degrees
    bounce: float = 0.0            # extra vertical offset (px, negative = up)
    held: Optional[str] = None     # prop in right hand
    held_l: Optional[str] = None   # prop in left hand
    tears: float = 0.0
    sweat: float = 0.0
    blink: Optional[float] = None  # force eyelid closure 0..1
    wave_speed: float = 2.2
    breath: float = 1.0
    seed: float = 0.0
    shadow: bool = True
    phone_glow: bool = True

    def with_(self, **kw) -> "Pose":
        return replace(self, **kw)


# --------------------------------------------------------------------------
# Character
# --------------------------------------------------------------------------


@dataclass
class Character:
    name: str
    skin: str = "#e9b48a"
    hair: str = "#2b1d16"
    hair_style: str = "short"      # short | curly | bob | bun | long | buzz
    top: str = "#e63946"
    top_style: str = "hoodie"      # hoodie | tee | blazer | cardigan | sweater
    bottom: str = "#2f3e5c"
    shoes: str = "#f2f2f2"
    eye: str = "#3b2416"
    glasses: bool = False
    beard: bool = False
    height: float = 1.0
    width: float = 1.0
    apron: bool = False
    accent: str = "#ffffff"
    lips: str = "#a8464a"
    blink_offset: float = 0.0

    # ---- helpers --------------------------------------------------------
    def _blink(self, p: Pose) -> float:
        if p.blink is not None:
            return p.blink
        period = 3.7 + (hash(self.name) % 7) * 0.23
        ph = (p.t + self.blink_offset + (hash(self.name) % 13) * 0.31) % period
        if ph < 0.14:
            return math.sin(ph / 0.14 * math.pi)
        # occasional double blink
        if period * 0.55 < ph < period * 0.55 + 0.12 and (hash(self.name) % 3 == 0):
            return math.sin((ph - period * 0.55) / 0.12 * math.pi)
        return 0.0

    def outline(self, c) -> tuple:
        return shade(c, -0.45)

    # ---- main entry ------------------------------------------------------
    def draw(self, ctx: cairo.Context, x: float, y: float, s: float, p: Pose, flip: bool = False):
        hscale = self.height
        with at(ctx, x, y, s):
            if p.shadow:
                soft_shadow(ctx, 0, 0, 120 * self.width, 22, 0.32)
            if flip:
                ctx.scale(-1, 1)
            ctx.scale(1, hscale)
            self._draw_body(ctx, p, 1.0 / hscale)

    def _draw_body(self, ctx, p: Pose, inv_h: float):
        t = p.t
        breath = math.sin(t * 2.1 + p.seed) * 2.2 * p.breath
        walk = p.walk
        bob = 0.0
        if walk is not None:
            bob = -abs(math.sin(walk * math.pi)) * 10
        hip_y = -205 + (85 if p.sit else 0)
        lean = (p.lean + (math.sin(walk * TAU) * 1.5 if walk is not None else 0) + math.sin(t * 0.9 + p.seed) * 0.6) * D2R

        # legs (drawn before torso)
        self._legs(ctx, p, hip_y, bob)

        with at(ctx, 0, hip_y + bob + p.bounce, rot=lean):
            # now origin at hip centre
            chest = -168 - breath * 0.3
            self._torso(ctx, chest, breath)
            sh_y = chest + 12
            arms = get_pose(p.arms)
            # wave animation on right arm when pose is wave
            if p.arms == "wave":
                arms = (arms[0], (arms[1][0] + math.sin(t * p.wave_speed * TAU) * 8,
                                   arms[1][1] + math.sin(t * p.wave_speed * TAU) * 28))
            hands = []
            for side, (a1, a2) in zip((-1, 1), arms):
                hands.append(self._arm_geom(side, sh_y, a1, a2))
            # arms that fold across the body go in front; others too (simple)
            neck_top = chest - 10
            self._head(ctx, p, neck_top - 60 - breath * 0.4)
            for side, g in zip((-1, 1), hands):
                self._arm_draw(ctx, g)
            if p.held:
                self._prop(ctx, p.held, hands[1], 1, p)
            if p.held_l:
                self._prop(ctx, p.held_l, hands[0], -1, p)

    # ---- legs ------------------------------------------------------------
    def _legs(self, ctx, p: Pose, hip_y, bob):
        pant = hexc(self.bottom)
        ol = self.outline(pant)
        for side in (-1, 1):
            hx = side * 28 * self.width
            if p.sit:
                kx, ky = side * 46 * self.width, hip_y + 40
                fx, fy = side * 50 * self.width, 0
            elif p.walk is not None:
                ph = p.walk * TAU + (0 if side < 0 else math.pi)
                swing = math.sin(ph)
                lift = max(0.0, math.cos(ph)) * 18
                kx = hx + swing * 10
                ky = hip_y + 102 + bob - lift * 0.4
                fx = hx + swing * 26
                fy = -lift
            else:
                kx, ky = hx + side * 2, hip_y + 102
                fx, fy = hx + side * 4, 0
            hy = hip_y + bob
            ctx.move_to(hx, hy)
            ctx.line_to(kx, ky)
            ctx.line_to(fx, fy - 14)
            stroke(ctx, ol, 46)
            ctx.move_to(hx, hy)
            ctx.line_to(kx, ky)
            ctx.line_to(fx, fy - 14)
            stroke(ctx, pant, 40)
            # shoe
            shoe = hexc(self.shoes)
            rrect(ctx, fx - 26 + side * 6, fy - 26, 52, 26, 12)
            fill(ctx, shoe, preserve=True)
            stroke(ctx, shade(shoe, -0.35), 3)
            rrect(ctx, fx - 26 + side * 6, fy - 8, 52, 8, 4)
            fill(ctx, shade(shoe, -0.25))

    # ---- torso -----------------------------------------------------------
    def _torso(self, ctx, chest, breath):
        wv = self.width
        top = hexc(self.top)
        ol = self.outline(top)
        swx = 66 * wv + breath * 0.25
        hwx = 56 * wv
        y0 = chest
        path_pts = None

        def body_path():
            ctx.move_to(-swx + 26, y0)
            ctx.line_to(swx - 26, y0)
            ctx.curve_to(swx + 2, y0, swx + 4, y0 + 22, swx + 2, y0 + 44)
            ctx.curve_to(hwx + 6, y0 + 110, hwx + 4, y0 + 150, hwx, 10)
            ctx.curve_to(hwx * 0.4, 18, -hwx * 0.4, 18, -hwx, 10)
            ctx.curve_to(-hwx - 4, y0 + 150, -hwx - 6, y0 + 110, -swx - 2, y0 + 44)
            ctx.curve_to(-swx - 4, y0 + 22, -swx - 2, y0, -swx + 26, y0)
            ctx.close_path()

        # neck
        skin = hexc(self.skin)
        rrect(ctx, -17, y0 - 26, 34, 40, 10)
        fill(ctx, shade(skin, -0.12))

        body_path()
        ctx.set_source(lin_grad(-swx, y0, swx, 10, [(0, shade(top, 0.12)), (0.55, top), (1, shade(top, -0.18))]))
        ctx.fill_preserve()
        stroke(ctx, ol, 4)

        with saved(ctx):
            body_path()
            ctx.clip()
            st = self.top_style
            if st == "hoodie":
                # hood collar & strings
                ellipse(ctx, 0, y0 + 2, 44, 18)
                fill(ctx, shade(top, -0.2))
                line(ctx, -12, y0 + 12, -15, y0 + 62, self.accent, 4)
                line(ctx, 12, y0 + 12, 15, y0 + 62, self.accent, 4)
                circle(ctx, -15, y0 + 64, 4); fill(ctx, self.accent)
                circle(ctx, 15, y0 + 64, 4); fill(ctx, self.accent)
                # pocket
                rrect(ctx, -44 * wv, y0 + 104, 88 * wv, 48, 14)
                stroke(ctx, shade(top, -0.22), 4)
                # band
                rrect(ctx, -hwx - 10, -6, hwx * 2 + 20, 22, 6)
                fill(ctx, shade(top, -0.12))
            elif st == "tee":
                ctx.arc(0, y0 - 2, 22, 0, math.pi)
                stroke(ctx, shade(top, -0.25), 5)
                # graphic on tee
                circle(ctx, 0, y0 + 74, 22)
                fill(ctx, with_a(self.accent, 0.9))
            elif st == "blazer":
                # shirt + lapels
                poly_pts = [(-20, y0), (20, y0), (0, y0 + 80)]
                ctx.move_to(*poly_pts[0]); ctx.line_to(*poly_pts[1]); ctx.line_to(*poly_pts[2]); ctx.close_path()
                fill(ctx, self.accent)
                ctx.move_to(-22, y0); ctx.line_to(-6, y0 + 92); ctx.line_to(-36, y0 + 30); ctx.close_path()
                fill(ctx, shade(top, -0.2))
                ctx.move_to(22, y0); ctx.line_to(6, y0 + 92); ctx.line_to(36, y0 + 30); ctx.close_path()
                fill(ctx, shade(top, -0.2))
                circle(ctx, 0, y0 + 118, 5); fill(ctx, shade(top, -0.35))
                circle(ctx, 0, y0 + 142, 5); fill(ctx, shade(top, -0.35))
            elif st == "cardigan":
                ctx.arc(0, y0 - 4, 26, 0, math.pi)
                fill(ctx, self.accent)
                line(ctx, 0, y0 + 22, 0, 14, shade(top, -0.3), 4)
                for k in range(4):
                    circle(ctx, 8, y0 + 40 + k * 32, 4.5); fill(ctx, "#f4e3c1")
            elif st == "sweater":
                ellipse(ctx, 0, y0 + 2, 34, 13)
                fill(ctx, shade(top, -0.2))
                for k in range(3):
                    ctx.move_to(-swx, y0 + 70 + k * 18)
                    ctx.line_to(swx, y0 + 70 + k * 18)
                    stroke(ctx, shade(top, 0.15 if k % 2 else -0.1), 7)
            if self.apron:
                rrect(ctx, -46 * wv, y0 + 40, 92 * wv, 200, 18)
                fill(ctx, "#fff6ea", preserve=True)
                stroke(ctx, "#e7cdb0", 3)
                line(ctx, -40, y0 + 40, -24, y0 - 2, "#fff6ea", 6)
                line(ctx, 40, y0 + 40, 24, y0 - 2, "#fff6ea", 6)
                rrect(ctx, -24, y0 + 104, 48, 34, 8)
                stroke(ctx, "#e7cdb0", 3)
            # soft side shading
            ctx.set_source(lin_grad(-swx, 0, swx, 0, [(0, (0, 0, 0, 0)), (0.75, (0, 0, 0, 0)), (1, (0, 0, 0, 0.14))]))
            ctx.paint()

    # ---- arms ------------------------------------------------------------
    def _arm_geom(self, side, sh_y, a1, a2):
        sx = side * 60 * self.width
        sy = sh_y
        L1, L2 = 92, 86
        t1 = a1 * D2R
        t2 = (a1 + a2) * D2R
        ex = sx + side * math.sin(t1) * L1
        ey = sy + math.cos(t1) * L1
        hx = ex + side * math.sin(t2) * L2
        hy = ey + math.cos(t2) * L2
        return (sx, sy, ex, ey, hx, hy, side, t2)

    def _arm_draw(self, ctx, g):
        sx, sy, ex, ey, hx, hy, side, t2 = g
        top = hexc(self.top)
        skin = hexc(self.skin)
        sleeve_end = 0.78 if self.top_style in ("hoodie", "blazer", "cardigan", "sweater") else 0.0
        # upper + forearm sleeve
        if sleeve_end:
            pts = [(sx, sy), (ex, ey), (lerp(ex, hx, sleeve_end), lerp(ey, hy, sleeve_end))]
            for col, w in ((self.outline(top), 40), (top, 33)):
                ctx.move_to(*pts[0]); ctx.line_to(*pts[1]); ctx.line_to(*pts[2])
                stroke(ctx, col, w)
        else:
            for col, w in ((shade(skin, -0.4), 31), (skin, 25)):
                ctx.move_to(sx, sy); ctx.line_to(ex, ey); ctx.line_to(hx, hy)
                stroke(ctx, col, w)
            mx, my = lerp(sx, ex, 0.5), lerp(sy, ey, 0.5)
            for col, w in ((self.outline(top), 42), (top, 36)):
                ctx.move_to(sx, sy); ctx.line_to(mx, my)
                stroke(ctx, col, w)
        # hand
        circle(ctx, hx, hy, 17)
        fill(ctx, skin, preserve=True)
        stroke(ctx, shade(skin, -0.4), 3)
        # thumb
        tx = hx - side * math.cos(t2) * 10 * 0 + side * 8 * math.cos(t2)
        ty = hy - 8 * math.sin(t2) * side
        circle(ctx, hx + (sx - hx) * 0.0 - side * 4, hy - 9, 7)
        fill(ctx, skin)

    # ---- props -----------------------------------------------------------
    def _prop(self, ctx, name, g, side, p: Pose):
        hx, hy = g[4], g[5]
        if name == "phone":
            with at(ctx, hx - side * 4, hy - 30, rot=-side * 0.12):
                rrect(ctx, -22, -40, 44, 80, 9)
                fill(ctx, "#1d1f24")
                rrect(ctx, -18, -35, 36, 68, 5)
                fill(ctx, "#69c8ff" if p.phone_glow else "#2a2d33")
            circle(ctx, hx, hy, 15)
            fill(ctx, self.skin)
        elif name == "phone_dark":
            with at(ctx, hx, hy - 28, rot=-side * 0.12):
                rrect(ctx, -22, -40, 44, 80, 9)
                fill(ctx, "#1d1f24")
            circle(ctx, hx, hy, 15); fill(ctx, self.skin)
        elif name == "plate":
            # plate held between both hands - drawn centred between hands by caller using right hand only
            with at(ctx, hx - side * 54, hy - 10):
                ellipse(ctx, 0, 0, 78, 22); fill(ctx, "#f8f8f8", preserve=True); stroke(ctx, "#c9ced6", 3)
                for k in range(4):
                    ellipse(ctx, 0, -8 - k * 11, 52 - k * 2, 14); fill(ctx, "#d68a3c", preserve=True); stroke(ctx, "#a65f22", 2.5)
                ellipse(ctx, -6, -52, 18, 6); fill(ctx, "#ffe58a")
                ctx.move_to(-30, -50); ctx.curve_to(-20, -30, 10, -40, 20, -12)
                stroke(ctx, (0.55, 0.27, 0.05, 0.85), 6)
        elif name == "book":
            with at(ctx, hx - side * 46, hy - 26):
                rrect(ctx, -58, -40, 116, 76, 6); fill(ctx, "#2d6a4f")
                rrect(ctx, -52, -36, 104, 68, 4); fill(ctx, "#fbf6e9")
                line(ctx, 0, -36, 0, 32, "#d8cdb5", 3)
                for k in range(5):
                    line(ctx, -44, -24 + k * 11, -8, -24 + k * 11, "#bdb29b", 2)
                    line(ctx, 8, -24 + k * 11, 44, -24 + k * 11, "#bdb29b", 2)
        elif name == "mug":
            with at(ctx, hx, hy - 18):
                rrect(ctx, -20, -26, 40, 48, 6); fill(ctx, "#f1faee", preserve=True); stroke(ctx, "#aab", 2)
                ctx.arc(22, -2, 11, -1.4, 1.4); stroke(ctx, "#f1faee", 6)
            circle(ctx, hx, hy, 15); fill(ctx, self.skin)
        elif name == "snacks":
            with at(ctx, hx, hy - 30, rot=0.1 * side):
                rrect(ctx, -30, -44, 60, 84, 8); fill(ctx, "#ffb703", preserve=True); stroke(ctx, "#b37c00", 3)
                circle(ctx, 0, -4, 16); fill(ctx, "#fb5607")
            circle(ctx, hx, hy, 15); fill(ctx, self.skin)

    # ---- head ------------------------------------------------------------
    def _head(self, ctx, p: Pose, hy):
        skin = hexc(self.skin)
        hair = hexc(self.hair)
        talk_bob = p.mouth * 2.5 * math.sin(p.t * 11)
        tilt = (p.head_tilt + math.sin(p.t * 1.3 + p.seed) * 1.2 + talk_bob * 0.4) * D2R
        fx = p.facing * 10
        with at(ctx, 0, hy - 8, s=1.16, rot=tilt):
            rx, ry = 64, 72
            # back hair
            self._hair_back(ctx, hair, rx, ry)
            # ears
            for side in (-1, 1):
                ex = side * (rx - 4) - fx * 0.5
                ellipse(ctx, ex, 6, 13, 18)
                fill(ctx, shade(skin, -0.06), preserve=True)
                stroke(ctx, shade(skin, -0.38), 3)
            # face
            ellipse(ctx, 0, 0, rx, ry)
            ctx.set_source(rad_grad(-18 + fx, -24, 10, ry * 1.25, [(0, shade(skin, 0.1)), (0.7, skin), (1, shade(skin, -0.12))]))
            ctx.fill_preserve()
            stroke(ctx, shade(skin, -0.4), 3.5)
            self._face(ctx, p, fx)
            self._hair_front(ctx, hair, rx, ry, fx)
            if self.glasses:
                for side in (-1, 1):
                    circle(ctx, side * 25 + fx, -4, 19)
                    stroke(ctx, "#3a3a3a", 4)
                line(ctx, -6 + fx, -6, 6 + fx, -6, "#3a3a3a", 4)

    def _face(self, ctx, p: Pose, fx):
        e = get_expr(p.expr)
        skin = hexc(self.skin)
        blink = clamp(self._blink(p))
        lx, ly = p.look
        # blush
        if e["blush"] > 0.02:
            for side in (-1, 1):
                ctx.set_source(rad_grad(side * 36 + fx, 22, 0, 18, [(0, (0.95, 0.4, 0.45, 0.45 * e["blush"])), (1, (0.95, 0.4, 0.45, 0))]))
                circle(ctx, side * 36 + fx, 22, 18)
                ctx.fill()
        # eyes
        es = e["eye_s"]
        for side in (-1, 1):
            ex, ey = side * 25 + fx, -4
            if e["closed"] > 0.5 and blink < 0.5:
                # happy closed eyes (^ ^)
                ctx.move_to(ex - 12, ey + 3)
                ctx.curve_to(ex - 6, ey - 9, ex + 6, ey - 9, ex + 12, ey + 3)
                stroke(ctx, "#2a1a12", 5)
                continue
            erx, ery = 12.5 * es, 15 * es
            ellipse(ctx, ex, ey, erx, ery)
            fill(ctx, "#ffffff", preserve=True)
            stroke(ctx, shade(skin, -0.45), 2.5)
            with saved(ctx):
                ellipse(ctx, ex, ey, erx, ery)
                ctx.clip()
                px, py = ex + lx * 5.5, ey + ly * 5 + 1
                circle(ctx, px, py, 8.5 * es)
                fill(ctx, self.eye)
                circle(ctx, px, py, 4.5 * es)
                fill(ctx, "#0c0806")
                circle(ctx, px - 3, py - 3.5, 2.6)
                fill(ctx, "#ffffff")
                # lids
                lid = max(blink, e["lid"])
                if lid > 0.01:
                    lid_y = ey - ery + (ery * 2) * lid
                    tilt = e["brow_tilt"] * side * -6 if e["lid"] > 0.01 and blink < 0.3 else 0
                    ctx.move_to(ex - erx - 2, ey - ery - 4)
                    ctx.line_to(ex + erx + 2, ey - ery - 4)
                    ctx.line_to(ex + erx + 2, lid_y - tilt)
                    ctx.line_to(ex - erx - 2, lid_y + tilt)
                    ctx.close_path()
                    fill(ctx, shade(skin, -0.05))
                    ctx.move_to(ex - erx - 2, lid_y + tilt)
                    ctx.line_to(ex + erx + 2, lid_y - tilt)
                    stroke(ctx, shade(skin, -0.45), 3)
        # tears
        if p.tears > 0.01:
            for side in (-1, 1):
                ph = (p.t * 0.9 + (0.5 if side > 0 else 0)) % 1.0
                ty = 10 + ph * 46
                ctx.move_to(side * 30 + fx, ty - 9)
                ctx.curve_to(side * 36 + fx, ty, side * 34 + fx, ty + 7, side * 30 + fx, ty + 7)
                ctx.curve_to(side * 26 + fx, ty + 7, side * 24 + fx, ty, side * 30 + fx, ty - 9)
                fill(ctx, (0.55, 0.8, 1.0, 0.85 * p.tears * (1 - ph * 0.6)))
        if p.sweat > 0.01:
            ctx.move_to(54 + fx, -38)
            ctx.curve_to(62 + fx, -26, 60 + fx, -18, 54 + fx, -18)
            ctx.curve_to(48 + fx, -18, 46 + fx, -26, 54 + fx, -38)
            fill(ctx, (0.6, 0.85, 1.0, 0.9 * p.sweat))
        # brows
        hair_d = shade(self.hair, -0.1) if self.hair_style != "bun" else shade(self.hair, -0.35)
        for side in (-1, 1):
            bx, by = side * 25 + fx, -30 - e["brow_y"]
            tilt = e["brow_tilt"] * 7
            inner = (bx - side * 11, by + tilt)
            outer = (bx + side * 12, by - tilt * 0.4 - 2)
            ctx.move_to(*inner)
            ctx.curve_to(bx - side * 2, by - 6 + tilt * 0.3, bx + side * 6, by - 6, *outer)
            stroke(ctx, hair_d, 6.5)
        # nose
        ctx.move_to(-3 + fx * 1.3, 4)
        ctx.curve_to(-8 + fx * 1.3, 18, 0 + fx * 1.3, 22, 7 + fx * 1.3, 18)
        stroke(ctx, shade(skin, -0.3), 3.5)
        # beard
        if self.beard:
            ctx.move_to(-50, 10)
            ctx.curve_to(-46, 70, 46, 70, 50, 10)
            ctx.curve_to(34, 44, -34, 44, -50, 10)
            fill(ctx, with_a(self.hair, 0.85))
        # mouth
        self._mouth(ctx, e, p.mouth, fx)

    def _mouth(self, ctx, e, talk, fx):
        cx, cy = fx * 1.2, 36
        w = 19 * e["m_w"]
        curve = e["m_curve"]
        op = clamp(e["m_open"] + talk * 0.95)
        h = op * 24
        if h < 2.2:
            ctx.move_to(cx - w, cy - curve * 3)
            ctx.curve_to(cx - w * 0.4, cy + curve * 9, cx + w * 0.4, cy + curve * 9, cx + w, cy - curve * 3)
            stroke(ctx, "#5a2a22", 4.5)
            return
        w2 = w * (0.85 + op * 0.15)
        top_y = cy - h * 0.25 - curve * 2
        bot_y = cy + h * 0.75 + curve * 3
        ctx.move_to(cx - w2, cy - curve * 4)
        ctx.curve_to(cx - w2 * 0.5, top_y - 2, cx + w2 * 0.5, top_y - 2, cx + w2, cy - curve * 4)
        ctx.curve_to(cx + w2 * 0.7, bot_y + 2, cx - w2 * 0.7, bot_y + 2, cx - w2, cy - curve * 4)
        ctx.close_path()
        fill(ctx, "#4a1416", preserve=True)
        with saved(ctx):
            ctx.clip_preserve()
            ctx.new_path()
            # tongue
            ellipse(ctx, cx, bot_y - 2, w2 * 0.6, h * 0.35)
            fill(ctx, "#e26d6d")
            # teeth
            if op > 0.25:
                rrect(ctx, cx - w2, top_y - 6, w2 * 2, 7 + h * 0.12, 3)
                fill(ctx, "#fbfbf6")
        ctx.move_to(cx - w2, cy - curve * 4)
        ctx.curve_to(cx - w2 * 0.5, top_y - 2, cx + w2 * 0.5, top_y - 2, cx + w2, cy - curve * 4)
        ctx.curve_to(cx + w2 * 0.7, bot_y + 2, cx - w2 * 0.7, bot_y + 2, cx - w2, cy - curve * 4)
        ctx.close_path()
        stroke(ctx, "#5a2a22", 3.5)

    # ---- hair ------------------------------------------------------------
    def _hair_back(self, ctx, hair, rx, ry):
        st = self.hair_style
        if st == "bob":
            ctx.move_to(-rx - 12, -10)
            ctx.curve_to(-rx - 22, 60, -rx - 10, 88, -rx + 14, 86)
            ctx.line_to(rx - 14, 86)
            ctx.curve_to(rx + 10, 88, rx + 22, 60, rx + 12, -10)
            ctx.curve_to(rx + 10, -ry - 20, -rx - 10, -ry - 20, -rx - 12, -10)
            fill(ctx, shade(hair, -0.12))
        elif st == "long":
            ctx.move_to(-rx - 10, -20)
            ctx.curve_to(-rx - 30, 90, -rx - 18, 150, -rx + 6, 150)
            ctx.line_to(rx - 6, 150)
            ctx.curve_to(rx + 18, 150, rx + 30, 90, rx + 10, -20)
            ctx.curve_to(rx + 6, -ry - 24, -rx - 6, -ry - 24, -rx - 10, -20)
            fill(ctx, shade(hair, -0.12))
        elif st == "bun":
            circle(ctx, 0, -ry - 16, 30)
            fill(ctx, shade(hair, -0.05), preserve=True)
            stroke(ctx, shade(hair, -0.3), 3)

    def _hair_front(self, ctx, hair, rx, ry, fx):
        st = self.hair_style
        hl = shade(hair, 0.18)
        ol = shade(hair, -0.35)
        if st == "short":
            ctx.move_to(-rx - 5, 6)
            ctx.curve_to(-rx - 10, -ry * 1.38, rx + 10, -ry * 1.38, rx + 5, 6)
            ctx.curve_to(rx + 2, -14, rx - 6, -26, rx - 14, -30)
            pts = [(rx - 14, -30), (34, -40), (14, -30), (-4, -44), (-24, -32), (-42, -40), (-rx + 10, -24)]
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                ctx.curve_to(x1 - 8, y1 - 10, x2 + 8, y2 - 10, x2, y2)
            ctx.curve_to(-rx + 4, -12, -rx - 2, -4, -rx - 5, 6)
            ctx.close_path()
            ctx.set_source(lin_grad(0, -ry - 8, 0, 0, [(0, hl), (1, hair)]))
            ctx.fill_preserve()
            stroke(ctx, ol, 3)
            ctx.move_to(-24, -ry + 14)
            ctx.curve_to(-8, -ry + 6, 14, -ry + 6, 30, -ry + 16)
            stroke(ctx, with_a(hl, 0.6), 5)
        elif st == "buzz":
            ctx.move_to(-rx + 2, -8)
            ctx.curve_to(-rx - 2, -ry * 1.35, rx + 2, -ry * 1.35, rx - 2, -8)
            ctx.curve_to(rx - 12, -38, -rx + 12, -38, -rx + 2, -8)
            fill(ctx, with_a(hair, 0.9))
        elif st == "curly":
            rng_pts = [(-rx + 2, -10), (-rx - 4, -36), (-50, -62), (-28, -78), (0, -84), (28, -78), (50, -62), (rx + 4, -36), (rx - 2, -10)]
            ctx.move_to(-rx, 0)
            ctx.curve_to(-rx - 8, -ry * 1.38, rx + 8, -ry * 1.38, rx, 0)
            ctx.curve_to(rx - 10, -36, -rx + 10, -36, -rx, 0)
            fill(ctx, hair)
            for i, (cx, cy) in enumerate(rng_pts):
                circle(ctx, cx, cy, 20)
                fill(ctx, hair if i % 2 else shade(hair, 0.08), preserve=True)
                stroke(ctx, ol, 2.5)
            for cx in (-36, -12, 12, 36):
                circle(ctx, cx, -50, 14)
                fill(ctx, shade(hair, 0.1))
        elif st == "bob":
            ctx.move_to(-rx - 10, 20)
            ctx.curve_to(-rx - 16, -ry * 1.4, rx + 16, -ry * 1.4, rx + 10, 20)
            ctx.curve_to(rx, -10, rx - 10, -36, 10, -46)
            ctx.curve_to(-20, -36, -40, -30, -rx + 4, -12)
            ctx.curve_to(-rx, 0, -rx - 4, 10, -rx - 10, 20)
            ctx.close_path()
            ctx.set_source(lin_grad(0, -ry, 0, 20, [(0, hl), (1, hair)]))
            ctx.fill_preserve()
            stroke(ctx, ol, 3)
        elif st == "long":
            ctx.move_to(-rx - 8, 40)
            ctx.curve_to(-rx - 14, -ry * 1.42, rx + 14, -ry * 1.42, rx + 8, 40)
            ctx.curve_to(rx - 2, -20, rx - 20, -44, 0, -50)
            ctx.curve_to(-rx + 20, -44, -rx + 2, -20, -rx - 8, 40)
            ctx.close_path()
            ctx.set_source(lin_grad(0, -ry, 0, 20, [(0, hl), (1, hair)]))
            ctx.fill_preserve()
            stroke(ctx, ol, 3)
        elif st == "bun":
            ctx.move_to(-rx - 2, 4)
            ctx.curve_to(-rx - 8, -ry * 1.36, rx + 8, -ry * 1.36, rx + 2, 4)
            ctx.curve_to(rx - 6, -30, 30, -46, 0, -48)
            ctx.curve_to(-30, -46, -rx + 6, -30, -rx - 2, 4)
            ctx.close_path()
            ctx.set_source(lin_grad(0, -ry, 0, 0, [(0, hl), (1, hair)]))
            ctx.fill_preserve()
            stroke(ctx, ol, 3)
            for k in (-30, -10, 10, 30):
                ctx.move_to(k * 0.4, -ry + 2)
                ctx.curve_to(k, -ry + 10, k * 1.4, -40, k * 1.6, -32)
                stroke(ctx, with_a(ol, 0.4), 2)


def with_a(c, a):
    c = hexc(c) if isinstance(c, str) else c
    return (c[0], c[1], c[2], a)


# --------------------------------------------------------------------------
# Dog
# --------------------------------------------------------------------------


@dataclass
class Dog:
    name: str = "Biscuit"
    fur: str = "#d9a05b"

    def draw(self, ctx, x, y, s, t: float, wag: float = 1.0, walk: Optional[float] = None,
             tongue: bool = True, look: float = 0.0, flip=False, happy=True, sleep=False):
        fur = hexc(self.fur)
        dark = shade(fur, -0.3)
        ol = shade(fur, -0.5)
        with at(ctx, x, y, s):
            soft_shadow(ctx, 0, 0, 130, 18, 0.3)
            if flip:
                ctx.scale(-1, 1)
            bob = -abs(math.sin((walk or 0) * math.pi)) * 6 if walk is not None else math.sin(t * 2) * 1.5
            # tail
            ang = math.sin(t * 14) * 0.55 * wag - 0.6
            with at(ctx, -92, -112 + bob, rot=ang):
                ctx.move_to(0, 0)
                ctx.curve_to(-30, -20, -50, -50, -44, -78)
                stroke(ctx, ol, 24)
                ctx.move_to(0, 0)
                ctx.curve_to(-30, -20, -50, -50, -44, -78)
                stroke(ctx, fur, 18)
            # legs
            for i, lx in enumerate((-70, -40, 50, 78)):
                ph = (walk or 0) * TAU + (math.pi if i % 2 else 0)
                sw = math.sin(ph) * 14 if walk is not None else 0
                c = fur if i in (1, 2) else dark
                ctx.move_to(lx, -70 + bob)
                ctx.line_to(lx + sw, -8)
                stroke(ctx, ol, 28)
                ctx.move_to(lx, -70 + bob)
                ctx.line_to(lx + sw, -8)
                stroke(ctx, c, 22)
                ellipse(ctx, lx + sw + 4, -8, 16, 9)
                fill(ctx, shade(fur, 0.15))
            # body
            ellipse(ctx, 0, -100 + bob, 115, 52)
            ctx.set_source(lin_grad(0, -150, 0, -50, [(0, shade(fur, 0.12)), (1, shade(fur, -0.1))]))
            ctx.fill_preserve()
            stroke(ctx, ol, 4)
            ellipse(ctx, 40, -78 + bob, 50, 22)
            fill(ctx, shade(fur, 0.25))
            # collar
            with at(ctx, 92, -132 + bob, rot=0.5):
                rrect(ctx, -10, -36, 20, 72, 8)
                fill(ctx, "#e63946")
            circle(ctx, 100, -104 + bob, 9)
            fill(ctx, "#ffd166")
            # head
            hx, hy = 122 + look * 4, -170 + bob + math.sin(t * 2.5) * 2
            ellipse(ctx, hx, hy, 56, 50)
            ctx.set_source(rad_grad(hx - 10, hy - 18, 6, 70, [(0, shade(fur, 0.15)), (1, fur)]))
            ctx.fill_preserve()
            stroke(ctx, ol, 4)
            # snout
            ellipse(ctx, hx + 44, hy + 16, 36, 26)
            fill(ctx, shade(fur, 0.28), preserve=True)
            stroke(ctx, ol, 3)
            ellipse(ctx, hx + 74, hy + 6, 12, 9)
            fill(ctx, "#2a1a14")
            ctx.move_to(hx + 52, hy + 30)
            ctx.curve_to(hx + 60, hy + 36, hx + 70, hy + 32, hx + 74, hy + 24)
            stroke(ctx, "#2a1a14", 3.5)
            if tongue and not sleep:
                tw = math.sin(t * 9) * 2
                ellipse(ctx, hx + 58, hy + 44 + tw, 10, 16)
                fill(ctx, "#ef6f8a", preserve=True)
                stroke(ctx, "#b8445f", 2.5)
            # eye
            if sleep:
                ctx.move_to(hx + 2, hy - 8)
                ctx.curve_to(hx + 8, hy - 2, hx + 18, hy - 2, hx + 24, hy - 8)
                stroke(ctx, "#2a1a14", 4)
            else:
                blink = (t % 4.1) < 0.12
                if blink:
                    line(ctx, hx + 4, hy - 8, hx + 22, hy - 8, "#2a1a14", 4)
                else:
                    circle(ctx, hx + 14, hy - 10, 9)
                    fill(ctx, "#2a1a14")
                    circle(ctx, hx + 11, hy - 13, 3)
                    fill(ctx, "#ffffff")
                ctx.move_to(hx + 2, hy - 28)
                ctx.line_to(hx + 24, hy - 32)
                stroke(ctx, dark, 4)
            # ear
            ear_sw = math.sin(t * 3) * 0.08
            with at(ctx, hx - 20, hy - 30, rot=0.25 + ear_sw):
                ctx.move_to(0, 0)
                ctx.curve_to(-30, 10, -34, 60, -14, 78)
                ctx.curve_to(4, 82, 14, 40, 14, 6)
                ctx.close_path()
                fill(ctx, dark, preserve=True)
                stroke(ctx, ol, 3)
