"""Low-level cairo drawing helpers, colour utilities and easing curves."""
from __future__ import annotations

import math
import random
from contextlib import contextmanager
from typing import Iterable, Sequence

import cairo

from .config import FONT_HEADLINE, FONT_UI

TAU = math.tau

# --------------------------------------------------------------------------
# Colour
# --------------------------------------------------------------------------


def hexc(h: str, a: float = 1.0) -> tuple[float, float, float, float]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def mix(c1, c2, t: float):
    c1 = hexc(c1) if isinstance(c1, str) else c1
    c2 = hexc(c2) if isinstance(c2, str) else c2
    if len(c1) == 3:
        c1 = (*c1, 1.0)
    if len(c2) == 3:
        c2 = (*c2, 1.0)
    return tuple(a + (b - a) * t for a, b in zip(c1, c2))


def shade(c, amount: float):
    """amount < 0 darkens, > 0 lightens."""
    c = hexc(c) if isinstance(c, str) else c
    target = (0, 0, 0, c[3] if len(c) > 3 else 1) if amount < 0 else (1, 1, 1, c[3] if len(c) > 3 else 1)
    return mix(c, target, abs(amount))


def with_alpha(c, a: float):
    c = hexc(c) if isinstance(c, str) else c
    return (c[0], c[1], c[2], (c[3] if len(c) > 3 else 1) * a)


def set_color(ctx: cairo.Context, c) -> None:
    c = hexc(c) if isinstance(c, str) else c
    if len(c) == 3:
        ctx.set_source_rgb(*c)
    else:
        ctx.set_source_rgba(*c)


# --------------------------------------------------------------------------
# Easing & time helpers
# --------------------------------------------------------------------------


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def prog(t: float, start: float, dur: float) -> float:
    """0..1 progress of t through [start, start+dur]."""
    if dur <= 0:
        return 1.0 if t >= start else 0.0
    return clamp((t - start) / dur)


def ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in(t: float) -> float:
    return t ** 3


def ease_io(t: float) -> float:
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_back(t: float, s: float = 1.70158) -> float:
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


def ease_elastic(t: float) -> float:
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * (TAU / 3)) + 1


def pop(t: float, start: float, dur: float = 0.35) -> float:
    """Overshooting 0->1 'pop in' scale."""
    return ease_back(prog(t, start, dur), 2.4)


def pulse(t: float, period: float = 1.0) -> float:
    return 0.5 + 0.5 * math.sin(t * TAU / period)


def wobble(t: float, seed: float = 0.0, amp: float = 1.0) -> float:
    return amp * (math.sin(t * 1.7 + seed) * 0.6 + math.sin(t * 2.9 + seed * 2.3) * 0.4)


# --------------------------------------------------------------------------
# Shapes
# --------------------------------------------------------------------------


def rrect(ctx, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()


def ellipse(ctx, cx, cy, rx, ry):
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(max(rx, 0.01), max(ry, 0.01))
    ctx.new_sub_path()
    ctx.arc(0, 0, 1, 0, TAU)
    ctx.restore()


def circle(ctx, cx, cy, r):
    ctx.new_sub_path()
    ctx.arc(cx, cy, max(r, 0.01), 0, TAU)


def poly(ctx, pts: Sequence[tuple[float, float]], close=True):
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    if close:
        ctx.close_path()


def smooth_path(ctx, pts: Sequence[tuple[float, float]], close=False, tension=0.5):
    """Catmull-Rom spline through points."""
    n = len(pts)
    if n < 2:
        return
    ctx.move_to(*pts[0])
    rng = range(n if close else n - 1)
    for i in rng:
        p0 = pts[(i - 1) % n] if (close or i > 0) else pts[i]
        p1 = pts[i % n]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (close or i + 2 < n) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 3, p1[1] + (p2[1] - p0[1]) * tension / 3)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 3, p2[1] - (p3[1] - p1[1]) * tension / 3)
        ctx.curve_to(*c1, *c2, *p2)
    if close:
        ctx.close_path()


def fill(ctx, c, preserve=False):
    set_color(ctx, c)
    ctx.fill_preserve() if preserve else ctx.fill()


def stroke(ctx, c, w, preserve=False, cap=cairo.LINE_CAP_ROUND, join=cairo.LINE_JOIN_ROUND):
    set_color(ctx, c)
    ctx.set_line_width(w)
    ctx.set_line_cap(cap)
    ctx.set_line_join(join)
    ctx.stroke_preserve() if preserve else ctx.stroke()


def line(ctx, x1, y1, x2, y2, c, w):
    ctx.move_to(x1, y1)
    ctx.line_to(x2, y2)
    stroke(ctx, c, w)


def lin_grad(x0, y0, x1, y1, stops: Iterable[tuple[float, object]]):
    g = cairo.LinearGradient(x0, y0, x1, y1)
    for off, c in stops:
        c = hexc(c) if isinstance(c, str) else c
        g.add_color_stop_rgba(off, *(c if len(c) == 4 else (*c, 1)))
    return g


def rad_grad(cx, cy, r0, r1, stops, fx=None, fy=None):
    g = cairo.RadialGradient(fx if fx is not None else cx, fy if fy is not None else cy, r0, cx, cy, r1)
    for off, c in stops:
        c = hexc(c) if isinstance(c, str) else c
        g.add_color_stop_rgba(off, *(c if len(c) == 4 else (*c, 1)))
    return g


def soft_shadow(ctx, cx, cy, rx, ry, alpha=0.28):
    ctx.save()
    ctx.set_source(rad_grad(cx, cy, 0, 1, [(0, (0, 0, 0, alpha)), (1, (0, 0, 0, 0))]))
    ctx.translate(cx, cy)
    ctx.scale(rx, ry)
    ctx.translate(-cx, -cy)
    ctx.arc(cx, cy, 1, 0, TAU)
    ctx.fill()
    ctx.restore()


def vignette(ctx, w, h, strength=0.45):
    g = rad_grad(w / 2, h / 2, h * 0.35, h * 1.05, [(0, (0, 0, 0, 0)), (1, (0, 0, 0, strength))])
    ctx.set_source(g)
    ctx.paint()


def glow(ctx, cx, cy, r, c, alpha=0.6):
    c = hexc(c) if isinstance(c, str) else c
    ctx.set_source(rad_grad(cx, cy, 0, r, [(0, (*c[:3], alpha)), (1, (*c[:3], 0))]))
    circle(ctx, cx, cy, r)
    ctx.fill()


@contextmanager
def saved(ctx):
    ctx.save()
    try:
        yield ctx
    finally:
        ctx.restore()


@contextmanager
def at(ctx, x, y, s=1.0, rot=0.0, sx=None, sy=None):
    ctx.save()
    ctx.translate(x, y)
    if rot:
        ctx.rotate(rot)
    kx = sx if sx is not None else s
    ky = sy if sy is not None else s
    kx = kx if abs(kx) > 1e-4 else 1e-4
    ky = ky if abs(ky) > 1e-4 else 1e-4
    ctx.scale(kx, ky)
    try:
        yield ctx
    finally:
        ctx.restore()


@contextmanager
def alpha_group(ctx, a: float):
    if a >= 0.999:
        yield ctx
        return
    ctx.push_group()
    try:
        yield ctx
    finally:
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(max(0.0, a))


# --------------------------------------------------------------------------
# Text
# --------------------------------------------------------------------------


def _face(ctx, family: str, bold: bool):
    fam = family.split(",")[0].strip()
    ctx.select_font_face(fam, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)


def text_size(ctx, s: str, size: float, family=FONT_HEADLINE, bold=False):
    _face(ctx, family, bold)
    ctx.set_font_size(size)
    ext = ctx.text_extents(s)
    return ext.x_advance, ext.height, ext


def text(
    ctx,
    s: str,
    x: float,
    y: float,
    size: float,
    color="#ffffff",
    family=FONT_HEADLINE,
    bold=False,
    align="center",
    outline=None,
    outline_w=0.0,
    shadow: float = 0.0,
    baseline="middle",
):
    """Draw text. y is the vertical centre (baseline='middle') or baseline."""
    _face(ctx, family, bold)
    ctx.set_font_size(size)
    ext = ctx.text_extents(s)
    fe = ctx.font_extents()
    w = ext.x_advance
    if align == "center":
        tx = x - w / 2
    elif align == "right":
        tx = x - w
    else:
        tx = x
    if baseline == "middle":
        ty = y + (fe[0] - fe[1]) / 2 * 0.92
    else:
        ty = y
    if shadow:
        ctx.move_to(tx + shadow * 0.6, ty + shadow)
        ctx.text_path(s)
        set_color(ctx, (0, 0, 0, 0.45))
        if outline_w:
            ctx.set_line_width(outline_w)
            ctx.set_line_join(cairo.LINE_JOIN_ROUND)
            ctx.stroke_preserve()
        ctx.fill()
    ctx.move_to(tx, ty)
    ctx.text_path(s)
    if outline and outline_w:
        set_color(ctx, outline)
        ctx.set_line_width(outline_w)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.stroke_preserve()
    set_color(ctx, color)
    ctx.fill()
    return w


def headline(ctx, s, x, y, size, color="#ffffff", outline="#111111", ow=None, shadow=None, family=FONT_HEADLINE):
    ow = size * 0.16 if ow is None else ow
    shadow = size * 0.08 if shadow is None else shadow
    return text(ctx, s, x, y, size, color, family=family, outline=outline, outline_w=ow, shadow=shadow)


def ui_text(ctx, s, x, y, size, color="#222222", bold=False, align="left"):
    return text(ctx, s, x, y, size, color, family=FONT_UI, bold=bold, align=align)


def wrap(ctx, s: str, size: float, max_w: float, family=FONT_UI, bold=False) -> list[str]:
    words = s.split()
    lines, cur = [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if text_size(ctx, trial, size, family, bold)[0] > max_w and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


# --------------------------------------------------------------------------
# Misc
# --------------------------------------------------------------------------


def seeded(seed: int) -> random.Random:
    return random.Random(seed)


def star(ctx, cx, cy, r_out, r_in, n=5, rot=-math.pi / 2):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot + i * math.pi / n
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    poly(ctx, pts)


def burst(ctx, cx, cy, r, n=16, c1="#ffd21f", c2="#ffb000", rot=0.0):
    for i in range(n):
        a0 = rot + i * TAU / n
        a1 = a0 + TAU / n / 2
        ctx.move_to(cx, cy)
        ctx.line_to(cx + math.cos(a0) * r, cy + math.sin(a0) * r)
        ctx.line_to(cx + math.cos(a1) * r, cy + math.sin(a1) * r)
        ctx.close_path()
        fill(ctx, c1 if i % 2 == 0 else c2)
