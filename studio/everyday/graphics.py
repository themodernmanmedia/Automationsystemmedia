"""Explainer graphics: icons, charts, the brain, stat cards, title slams."""
from __future__ import annotations

import math

from .config import FONT_UI, H, W
from .gfx import (
    TAU, alpha_group, at, burst, circle, clamp, ease_back, ease_out, ellipse, fill, glow, headline,
    hexc, lerp, line, lin_grad, poly, pop, prog, rad_grad, rrect, saved, shade, smooth_path, stroke,
    text, text_size, ui_text, with_alpha,
)


def heart(ctx, x, y, s, c="#ff4d6d", beat_t=None):
    k = 1.0
    if beat_t is not None:
        ph = beat_t % 1.0
        k = 1 + 0.12 * math.exp(-ph * 8) + 0.08 * math.exp(-max(0, ph - 0.22) * 8) * (ph > 0.22)
    with at(ctx, x, y, s * k):
        ctx.move_to(0, 30)
        ctx.curve_to(-70, -20, -40, -80, 0, -45)
        ctx.curve_to(40, -80, 70, -20, 0, 30)
        ctx.close_path()
        ctx.set_source(rad_grad(-15, -40, 5, 80, [(0, shade(c, 0.3)), (1, c)]))
        ctx.fill_preserve()
        stroke(ctx, shade(c, -0.4), 4)


def rain_cloud(ctx, x, y, s, t, c="#8d99ae"):
    with at(ctx, x, y, s):
        for k in range(9):
            ph = (t * 1.6 + k * 0.37) % 1
            dx = -70 + k * 18
            line(ctx, dx, 20 + ph * 140, dx - 6, 40 + ph * 140, (0.5, 0.7, 1, 1 - ph), 5)
        for dx, dy, r in ((-60, 0, 44), (-10, -30, 58), (50, -6, 48), (0, 10, 50)):
            circle(ctx, dx, dy, r)
            fill(ctx, c)


def question_mark(ctx, x, y, s, c="#ffe14d"):
    with at(ctx, x, y, s):
        headline(ctx, "?", 0, 0, 220, color=c, ow=22)


def checkmark(ctx, x, y, s, c="#2ec27e", p=1.0):
    with at(ctx, x, y, s):
        circle(ctx, 0, 0, 40)
        fill(ctx, c)
        pts = [(-18, 2), (-5, 16), (20, -14)]
        ctx.move_to(*pts[0])
        if p < 0.5:
            q = p / 0.5
            ctx.line_to(lerp(pts[0][0], pts[1][0], q), lerp(pts[0][1], pts[1][1], q))
        else:
            q = (p - 0.5) / 0.5
            ctx.line_to(*pts[1])
            ctx.line_to(lerp(pts[1][0], pts[2][0], q), lerp(pts[1][1], pts[2][1], q))
        stroke(ctx, "#ffffff", 9)


def x_mark(ctx, x, y, s, c="#ff3b3b"):
    with at(ctx, x, y, s):
        circle(ctx, 0, 0, 40)
        fill(ctx, c)
        line(ctx, -15, -15, 15, 15, "#ffffff", 9)
        line(ctx, 15, -15, -15, 15, "#ffffff", 9)


def lock_icon(ctx, x, y, s, c="#ffb703"):
    with at(ctx, x, y, s):
        ctx.arc(0, -30, 34, math.pi, 0)
        stroke(ctx, "#adb5bd", 14)
        rrect(ctx, -52, -34, 104, 86, 14)
        fill(ctx, c, preserve=True)
        stroke(ctx, shade(c, -0.35), 4)
        circle(ctx, 0, 0, 10)
        fill(ctx, shade(c, -0.5))


def speech_bubble(ctx, x, y, w, h, msg, size=40, c="#ffffff", tail="left", tc="#111111"):
    rrect(ctx, x - w / 2, y - h / 2, w, h, 30)
    fill(ctx, c, preserve=True)
    stroke(ctx, "#222222", 4)
    tx = x - w * 0.25 if tail == "left" else x + w * 0.25
    ctx.move_to(tx - 20, y + h / 2 - 3)
    ctx.line_to(tx + (-30 if tail == "left" else 30), y + h / 2 + 40)
    ctx.line_to(tx + 20, y + h / 2 - 3)
    fill(ctx, c, preserve=True)
    stroke(ctx, "#222222", 4)
    rrect(ctx, tx - 22, y + h / 2 - 8, 44, 10, 2)
    fill(ctx, c)
    text(ctx, msg, x, y, size, tc, family="Inter", bold=True)


def thought_dots(ctx, x, y, t):
    for k in range(3):
        a = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(t * 6 - k * 0.8))
        circle(ctx, x + k * 26, y, 9)
        fill(ctx, (0.2, 0.2, 0.2, a))


def zzz(ctx, x, y, t):
    for k in range(3):
        ph = (t * 0.5 + k / 3) % 1
        text(ctx, "Z", x + ph * 60 + k * 10, y - ph * 120, 30 + k * 10, (0.2, 0.2, 0.4, 1 - ph))


def stat_card(ctx, x, y, label, value, s=1.0, c="#ffe14d", alpha=1.0, w=520):
    with alpha_group(ctx, alpha), at(ctx, x, y, s):
        rrect(ctx, -w / 2, -80, w, 160, 26)
        fill(ctx, (0.05, 0.05, 0.1, 0.82))
        rrect(ctx, -w / 2, -80, w, 160, 26)
        stroke(ctx, c, 5)
        ui_text(ctx, label.upper(), 0, -38, 30, "#dddddd", bold=True, align="center")
        headline(ctx, value, 0, 28, 74, color=c, ow=8, shadow=4)


def brain(ctx, x, y, s, t, glow_region=0.0, glow_c="#ff3b3b"):
    with at(ctx, x, y, s):
        # side view brain silhouette
        pts = [(-180, 20), (-190, -60), (-140, -130), (-60, -170), (30, -170), (110, -140), (170, -80),
               (185, 0), (160, 60), (90, 90), (20, 80), (-40, 100), (-120, 90), (-170, 60)]
        smooth_path(ctx, pts, close=True)
        ctx.set_source(rad_grad(-30, -60, 20, 260, [(0, "#ffc2d1"), (1, "#f48fb1")]))
        ctx.fill_preserve()
        stroke(ctx, "#c2185b", 6)
        # folds
        with saved(ctx):
            smooth_path(ctx, pts, close=True)
            ctx.clip()
            for k, (sx, sy) in enumerate(((-140, -60), (-80, -120), (0, -130), (80, -110), (130, -40), (-120, 20), (-40, 30), (40, -30), (100, 40), (-20, -70))):
                ctx.move_to(sx - 40, sy)
                ctx.curve_to(sx - 20, sy - 30, sx + 10, sy + 30, sx + 40, sy - 6)
                stroke(ctx, "#d81b60", 5)
        # cerebellum & stem
        ellipse(ctx, 110, 95, 60, 38)
        fill(ctx, "#f06292", preserve=True)
        stroke(ctx, "#c2185b", 5)
        rrect(ctx, 30, 80, 40, 110, 18)
        fill(ctx, "#ec407a")
        if glow_region > 0:
            gx, gy = -20, -70
            pulse = 0.75 + 0.25 * math.sin(t * 8)
            glow(ctx, gx, gy, 140 * glow_region, glow_c, 0.9 * pulse)
            circle(ctx, gx, gy, 26 * glow_region)
            fill(ctx, with_alpha(glow_c, 0.9))


def bar_chart(ctx, x, y, bars, t, start, h=420, bw=200, gap=120, max_v=100):
    """bars = [(label, value, colour, value_text)]; bars grow from `start`."""
    n = len(bars)
    total_w = n * bw + (n - 1) * gap
    x0 = x - total_w / 2
    line(ctx, x0 - 40, y, x0 + total_w + 40, y, "#ffffff", 6)
    for i, (label, v, c, vt) in enumerate(bars):
        p = ease_out(prog(t, start + i * 0.45, 0.9))
        bh = h * v / max_v * p
        bx = x0 + i * (bw + gap)
        rrect(ctx, bx, y - bh, bw, bh, 14)
        ctx.set_source(lin_grad(0, y - h, 0, y, [(0, shade(c, 0.25)), (1, c)]))
        ctx.fill()
        if p > 0.05:
            headline(ctx, vt if p > 0.98 else f"{int(v * p)}%", bx + bw / 2, y - bh - 50, 70, color="#ffffff", ow=9)
        text(ctx, label, bx + bw / 2, y + 50, 36, "#ffffff", family="Inter", bold=True)


def spotlight(ctx, x, y_top, y_floor, width, intensity=1.0):
    with saved(ctx):
        ctx.move_to(x - 40, y_top)
        ctx.line_to(x + 40, y_top)
        ctx.line_to(x + width / 2, y_floor)
        ctx.line_to(x - width / 2, y_floor)
        ctx.close_path()
        ctx.set_source(lin_grad(0, y_top, 0, y_floor, [(0, (1, 0.97, 0.7, 0.55 * intensity)), (1, (1, 0.97, 0.7, 0.12 * intensity))]))
        ctx.fill()
        ellipse(ctx, x, y_floor, width / 2, 40)
        fill(ctx, (1, 0.97, 0.7, 0.35 * intensity))


def film_strip(ctx, x, y, w, h, t, offset=0.0):
    rrect(ctx, x, y, w, h, 10)
    fill(ctx, "#111111")
    hole = 30
    off = (offset * 60) % 60
    for k in range(int(w / 60) + 2):
        hx = x + k * 60 - off
        if x <= hx <= x + w - hole:
            rrect(ctx, hx + 10, y + 10, hole, 22, 4)
            fill(ctx, "#eeeeee")
            rrect(ctx, hx + 10, y + h - 32, hole, 22, 4)
            fill(ctx, "#eeeeee")


def notification_badge(ctx, x, y, n, s=1.0):
    label = str(n) if n < 1000 else "999+"
    w = max(70, text_size(ctx, label, 46, "Anton")[0] + 40)
    with at(ctx, x, y, s):
        rrect(ctx, -w / 2, -36, w, 72, 36)
        fill(ctx, "#ff3b30", preserve=True)
        stroke(ctx, "#ffffff", 5)
        text(ctx, label, 0, 0, 46, "#ffffff")


def title_slam(ctx, lines_, t, start=0.0, y=H / 2, size=150, colors=("#ffffff", "#ffe14d"), gap=1.05, stagger=0.18, rot=-0.035):
    yy = y - (len(lines_) - 1) * size * gap / 2
    for i, ln in enumerate(lines_):
        s = pop(t, start + i * stagger, 0.4)
        if s <= 0.001:
            yy += size * gap
            continue
        with at(ctx, W / 2, yy, s=s, rot=rot):
            headline(ctx, ln, 0, 0, size, color=colors[i % len(colors)], ow=size * 0.13, shadow=size * 0.07)
        yy += size * gap


def rule_card(ctx, x, y, num, msg, p, w=980, c="#ff3b3b"):
    a = clamp(p * 3)
    with alpha_group(ctx, a), at(ctx, x + (1 - ease_out(clamp(p * 2))) * 300, y):
        rrect(ctx, 0, -56, w, 112, 24)
        fill(ctx, (1, 1, 1, 0.96))
        circle(ctx, 60, 0, 38)
        fill(ctx, c)
        text(ctx, str(num), 60, 0, 50, "#ffffff")
        text(ctx, msg, 120, 0, 54, "#111111", align="left")


def arrow(ctx, x1, y1, x2, y2, c="#ffe14d", w=14):
    ang = math.atan2(y2 - y1, x2 - x1)
    ctx.move_to(x1, y1)
    ctx.curve_to(lerp(x1, x2, 0.5) - 40, lerp(y1, y2, 0.5) - 60, x2 - math.cos(ang) * 40, y2 - math.sin(ang) * 40, x2, y2)
    stroke(ctx, c, w)
    for da in (2.6, -2.6):
        ctx.move_to(x2, y2)
        ctx.line_to(x2 + math.cos(ang + da) * 40, y2 + math.sin(ang + da) * 40)
        stroke(ctx, c, w)


def meter(ctx, x, y, label, v, c="#2ec27e", w=520):
    rrect(ctx, x, y, w, 44, 22)
    fill(ctx, (1, 1, 1, 0.25))
    rrect(ctx, x, y, max(44, w * clamp(v)), 44, 22)
    fill(ctx, c)
    ui_text(ctx, label, x, y - 30, 32, "#ffffff", bold=True)


def icon_tile(ctx, x, y, s, kind, t=0.0, c="#ffffff"):
    with at(ctx, x, y, s):
        rrect(ctx, -90, -90, 180, 180, 40)
        fill(ctx, c)
        if kind == "book":
            rrect(ctx, -56, -40, 112, 80, 6)
            fill(ctx, "#2d6a4f")
            rrect(ctx, -50, -36, 100, 70, 4)
            fill(ctx, "#fbf6e9")
            line(ctx, 0, -36, 0, 34, "#bdb29b", 3)
        elif kind == "pan":
            circle(ctx, -10, 6, 50)
            fill(ctx, "#343a40")
            line(ctx, 36, 6, 84, -20, "#343a40", 14)
            circle(ctx, -10, 6, 20)
            fill(ctx, "#ffd166")
            circle(ctx, -10, 6, 10)
            fill(ctx, "#ff9f1c")
        elif kind == "walk":
            circle(ctx, 0, -46, 16)
            fill(ctx, "#264653")
            line(ctx, 0, -28, -4, 14, "#264653", 14)
            line(ctx, -4, 14, -26, 52, "#264653", 12)
            line(ctx, -4, 14, 22, 50, "#264653", 12)
            line(ctx, -2, -16, -30, 6, "#264653", 10)
            line(ctx, -2, -16, 26, -2, "#264653", 10)
        elif kind == "sleep":
            ctx.arc(0, 0, 50, 0.6, TAU - 0.6)
            ctx.arc_negative(22, -14, 40, TAU - 0.9, 1.2)
            fill(ctx, "#ffd166")
        elif kind == "heart":
            heart(ctx, 0, 10, 0.9)
        elif kind == "stress":
            for k in range(5):
                a = k * TAU / 5 + t
                line(ctx, 0, 0, math.cos(a) * 60, math.sin(a) * 60, "#e63946", 8)
            circle(ctx, 0, 0, 30)
            fill(ctx, "#e63946")
