"""Backgrounds ("sets") and props. All sets paint the full 1920x1080 frame.

The floor line sits around y=840; characters standing at y~=960 read as being
in the room, mid-ground.
"""
from __future__ import annotations

import math

from .gfx import (
    TAU, at, burst, circle, clamp, ellipse, fill, glow, hexc, lerp, line, lin_grad,
    mix, poly, rad_grad, rrect, saved, seeded, set_color, shade, smooth_path,
    soft_shadow, stroke, text, ui_text, with_alpha, headline,
)
from .config import W, H

FLOOR_Y = 820


# --------------------------------------------------------------------------
# Shared pieces
# --------------------------------------------------------------------------


def wall(ctx, top, bottom, y1=FLOOR_Y):
    ctx.rectangle(0, 0, W, y1)
    ctx.set_source(lin_grad(0, 0, 0, y1, [(0, top), (1, bottom)]))
    ctx.fill()


def floor(ctx, c1, c2, y0=FLOOR_Y, boards=True):
    ctx.rectangle(0, y0, W, H - y0)
    ctx.set_source(lin_grad(0, y0, 0, H, [(0, c1), (1, c2)]))
    ctx.fill()
    # skirting
    ctx.rectangle(0, y0 - 14, W, 16)
    fill(ctx, shade(c1, 0.35))
    line(ctx, 0, y0 + 2, W, y0 + 2, shade(c1, -0.25), 3)
    if boards:
        # perspective boards converging to a vanishing point
        vx = W / 2
        for i in range(-14, 15):
            x_bottom = vx + i * 170
            x_top = vx + i * 70
            line(ctx, x_top, y0 + 2, x_bottom, H, with_alpha(shade(c1, -0.2), 0.45), 2)


def window(ctx, x, y, w, h, t, night=False, sky_top=None, sky_bot=None, curtains="#f4a261"):
    rrect(ctx, x - 14, y - 14, w + 28, h + 28, 8)
    fill(ctx, "#ffffff", preserve=True)
    stroke(ctx, "#c8ccd2", 3)
    if night:
        st, sb = sky_top or "#0b1d3a", sky_bot or "#2c3e6b"
    else:
        st, sb = sky_top or "#6cc3ff", sky_bot or "#d6f0ff"
    with saved(ctx):
        ctx.rectangle(x, y, w, h)
        ctx.clip()
        ctx.set_source(lin_grad(0, y, 0, y + h, [(0, st), (1, sb)]))
        ctx.paint()
        if night:
            r = seeded(int(x))
            for _ in range(26):
                sx, sy = x + r.random() * w, y + r.random() * h * 0.7
                a = 0.4 + 0.6 * abs(math.sin(t * (1 + r.random()) + sx))
                circle(ctx, sx, sy, 1.6 + r.random() * 1.5)
                fill(ctx, (1, 1, 0.9, a))
            circle(ctx, x + w * 0.75, y + h * 0.28, 26)
            fill(ctx, "#fff6d5")
            circle(ctx, x + w * 0.75 + 10, y + h * 0.28 - 6, 22)
            fill(ctx, st)
        else:
            glow(ctx, x + w * 0.8, y + h * 0.25, 90, "#fff5c0", 0.8)
            circle(ctx, x + w * 0.8, y + h * 0.25, 30)
            fill(ctx, "#fff1a8")
            for k, (cx, cy) in enumerate(((0.25, 0.35), (0.55, 0.2))):
                ox = ((t * 8 + k * 200) % (w + 200)) - 100
                for dx, dy, rr in ((0, 0, 26), (24, -10, 30), (50, 0, 24)):
                    circle(ctx, x + ox + dx, y + h * cy + dy, rr)
                    fill(ctx, (1, 1, 1, 0.9))
        # distant skyline
        r = seeded(int(y) + 7)
        bx = x
        while bx < x + w:
            bw = 40 + r.random() * 60
            bh = 40 + r.random() * h * 0.45
            ctx.rectangle(bx, y + h - bh, bw, bh)
            fill(ctx, (0.25, 0.3, 0.45, 0.55) if night else (0.55, 0.65, 0.8, 0.6))
            if night:
                for wy in range(int(y + h - bh + 8), int(y + h), 16):
                    for wx in range(int(bx + 6), int(bx + bw - 6), 14):
                        if r.random() < 0.35:
                            ctx.rectangle(wx, wy, 6, 8)
                            fill(ctx, (1, 0.9, 0.5, 0.8))
            bx += bw + 6
    # frame cross
    line(ctx, x + w / 2, y, x + w / 2, y + h, "#ffffff", 10)
    line(ctx, x, y + h / 2, x + w, y + h / 2, "#ffffff", 10)
    # curtains
    if curtains:
        for side in (0, 1):
            cx = x - 40 if side == 0 else x + w - 30
            sway = math.sin(t * 0.8 + side) * 4
            ctx.move_to(cx, y - 40)
            ctx.curve_to(cx + 30 + sway, y + h * 0.3, cx - 10 + sway, y + h * 0.7, cx + 20 + sway, y + h + 40)
            ctx.line_to(cx + 70 + sway, y + h + 40)
            ctx.curve_to(cx + 60 + sway, y + h * 0.6, cx + 80, y + h * 0.3, cx + 70, y - 40)
            ctx.close_path()
            ctx.set_source(lin_grad(cx, 0, cx + 70, 0, [(0, shade(curtains, -0.15)), (0.5, curtains), (1, shade(curtains, -0.2))]))
            ctx.fill()
        rrect(ctx, x - 70, y - 50, w + 140, 14, 7)
        fill(ctx, "#8d6e63")


def picture_frame(ctx, x, y, w, h, kind="mountain", frame="#6d4c41"):
    rrect(ctx, x, y, w, h, 4)
    fill(ctx, frame)
    ctx.rectangle(x + 10, y + 10, w - 20, h - 20)
    fill(ctx, "#fdf6e3")
    with saved(ctx):
        ctx.rectangle(x + 16, y + 16, w - 32, h - 32)
        ctx.clip()
        if kind == "mountain":
            ctx.set_source(lin_grad(0, y, 0, y + h, [(0, "#a8dadc"), (1, "#f1faee")]))
            ctx.paint()
            poly(ctx, [(x, y + h), (x + w * 0.35, y + h * 0.35), (x + w * 0.6, y + h)])
            fill(ctx, "#457b9d")
            poly(ctx, [(x + w * 0.3, y + h), (x + w * 0.7, y + h * 0.25), (x + w * 1.1, y + h)])
            fill(ctx, "#1d3557")
        elif kind == "family":
            ctx.set_source(lin_grad(0, y, 0, y + h, [(0, "#ffe8d6"), (1, "#ddbea9")]))
            ctx.paint()
            for i, c in enumerate(("#e63946", "#6c9bd2", "#b5838d")):
                cx = x + w * (0.28 + i * 0.22)
                circle(ctx, cx, y + h * 0.45, w * 0.09)
                fill(ctx, "#e0ac7e")
                ellipse(ctx, cx, y + h * 0.85, w * 0.12, h * 0.22)
                fill(ctx, c)


def plant(ctx, x, y, s=1.0, t=0.0, pot="#e76f51"):
    with at(ctx, x, y, s):
        for i in range(7):
            a = -math.pi / 2 + (i - 3) * 0.32 + math.sin(t * 1.2 + i) * 0.03
            L = 110 + (i % 3) * 25
            ex, ey = math.cos(a) * L, math.sin(a) * L - 60
            ctx.move_to(0, -60)
            ctx.curve_to(ex * 0.3, -60 + ey * 0.2, ex * 0.8, ey * 0.9 - 10, ex, ey)
            stroke(ctx, "#2d6a4f" if i % 2 else "#40916c", 16)
        poly(ctx, [(-46, -70), (46, -70), (34, 0), (-34, 0)])
        fill(ctx, pot, preserve=True)
        stroke(ctx, shade(pot, -0.3), 3)
        rrect(ctx, -52, -80, 104, 18, 6)
        fill(ctx, shade(pot, 0.1))


def lamp(ctx, x, y, on=True, s=1.0):
    with at(ctx, x, y, s):
        if on:
            glow(ctx, 0, -150, 260, "#ffd98a", 0.35)
        rrect(ctx, -6, -150, 12, 150, 4)
        fill(ctx, "#5c5c5c")
        ellipse(ctx, 0, 0, 40, 10)
        fill(ctx, "#444")
        poly(ctx, [(-50, -150), (50, -150), (34, -220), (-34, -220)])
        fill(ctx, "#fff3d1" if on else "#d8cfc0", preserve=True)
        stroke(ctx, "#c9b48a", 3)


def wall_clock(ctx, x, y, r, hours=7.0, t=0.0):
    circle(ctx, x, y, r + 8)
    fill(ctx, "#333")
    circle(ctx, x, y, r)
    fill(ctx, "#fffdf6")
    for i in range(12):
        a = i * TAU / 12
        line(ctx, x + math.cos(a) * r * 0.82, y + math.sin(a) * r * 0.82, x + math.cos(a) * r * 0.92,
             y + math.sin(a) * r * 0.92, "#333", 4)
    ha = (hours % 12) / 12 * TAU - math.pi / 2
    ma = (hours % 1) * TAU - math.pi / 2
    line(ctx, x, y, x + math.cos(ha) * r * 0.5, y + math.sin(ha) * r * 0.5, "#222", 7)
    line(ctx, x, y, x + math.cos(ma) * r * 0.75, y + math.sin(ma) * r * 0.75, "#222", 4)
    sa = t * TAU / 60 * 60 / 60 * 6 - math.pi / 2
    line(ctx, x, y, x + math.cos(sa) * r * 0.8, y + math.sin(sa) * r * 0.8, "#e63946", 2)
    circle(ctx, x, y, 6)
    fill(ctx, "#e63946")


# --------------------------------------------------------------------------
# Rooms
# --------------------------------------------------------------------------


def kitchen(ctx, t, warm=0.0):
    wall(ctx, "#fef3e2", "#fbe3c4")
    # tiles backsplash
    with saved(ctx):
        ctx.rectangle(0, 430, W, 230)
        ctx.clip()
        for yy in range(430, 660, 46):
            for xx in range(-40, W, 70):
                off = 35 if ((yy - 430) // 46) % 2 else 0
                rrect(ctx, xx + off + 2, yy + 2, 66, 42, 4)
                fill(ctx, "#e9f5f2")
    window(ctx, 760, 170, 400, 260, t, curtains="#e76f51")
    # upper cabinets
    for x0 in (60, 330, 1300, 1570):
        rrect(ctx, x0, 90, 250, 300, 10)
        ctx.set_source(lin_grad(x0, 90, x0 + 250, 390, [(0, "#8ecae6"), (1, "#5fa8d3")]))
        ctx.fill_preserve()
        stroke(ctx, "#3d7ea6", 4)
        rrect(ctx, x0 + 20, 110, 210, 260, 8)
        stroke(ctx, "#a9d6ee", 4)
        rrect(ctx, x0 + 112, 320, 26, 8, 4)
        fill(ctx, "#f1faee")
    # counter
    rrect(ctx, 0, 640, W, 40, 6)
    fill(ctx, "#f1e4d0")
    ctx.rectangle(0, 676, W, FLOOR_Y - 676)
    ctx.set_source(lin_grad(0, 676, 0, FLOOR_Y, [(0, "#219ebc"), (1, "#1b7f99")]))
    ctx.fill()
    for x0 in range(30, W, 260):
        rrect(ctx, x0, 700, 230, 110, 8)
        stroke(ctx, "#5fb7d0", 4)
        rrect(ctx, x0 + 95, 716, 40, 8, 4)
        fill(ctx, "#f1faee")
    # stove & pan
    rrect(ctx, 1380, 616, 220, 26, 6)
    fill(ctx, "#333")
    ellipse(ctx, 1490, 612, 80, 14)
    fill(ctx, "#2b2b2b")
    line(ctx, 1570, 610, 1660, 590, "#2b2b2b", 12)
    # steam
    for k in range(3):
        ph = (t * 0.6 + k / 3) % 1
        x0 = 1470 + k * 20 + math.sin(t * 2 + k) * 8
        ctx.move_to(x0, 600 - ph * 140)
        ctx.curve_to(x0 + 14, 580 - ph * 140, x0 - 14, 560 - ph * 140, x0, 540 - ph * 140)
        stroke(ctx, (1, 1, 1, 0.6 * (1 - ph)), 8)
    # fridge
    rrect(ctx, 1700, 300, 220, 520, 18)
    ctx.set_source(lin_grad(1700, 0, 1920, 0, [(0, "#f8f9fa"), (1, "#ced4da")]))
    ctx.fill_preserve()
    stroke(ctx, "#adb5bd", 4)
    line(ctx, 1700, 480, 1920, 480, "#adb5bd", 4)
    rrect(ctx, 1724, 380, 12, 70, 6)
    fill(ctx, "#868e96")
    # magnets / drawing
    rrect(ctx, 1760, 520, 90, 110, 4)
    fill(ctx, "#ffffff")
    circle(ctx, 1805, 560, 18)
    fill(ctx, "#ffd166")
    floor(ctx, "#e9c46a", "#d4a373")
    if warm:
        ctx.set_source_rgba(1, 0.7, 0.3, 0.12 * warm)
        ctx.paint()


def dining_table(ctx, x, y, w=520, items=True, t=0.0):
    soft_shadow(ctx, x, y + 150, w * 0.6, 26, 0.25)
    for lx in (x - w / 2 + 40, x + w / 2 - 40):
        rrect(ctx, lx - 12, y, 24, 160, 6)
        fill(ctx, "#8d5524")
    rrect(ctx, x - w / 2, y - 20, w, 36, 10)
    ctx.set_source(lin_grad(0, y - 20, 0, y + 16, [(0, "#c68642"), (1, "#8d5524")]))
    ctx.fill()


def plate_of_pancakes(ctx, x, y, s=1.0, steam=True, t=0.0, eaten=0.0):
    with at(ctx, x, y, s):
        ellipse(ctx, 0, 0, 90, 24)
        fill(ctx, "#ffffff", preserve=True)
        stroke(ctx, "#c9ced6", 3)
        n = max(0, int(round(4 * (1 - eaten))))
        for k in range(n):
            ellipse(ctx, 0, -8 - k * 12, 60, 16)
            fill(ctx, "#e09f3e", preserve=True)
            stroke(ctx, "#a0612b", 2.5)
        if n:
            top = -8 - (n - 1) * 12
            ellipse(ctx, -6, top - 4, 20, 7)
            fill(ctx, "#ffe08a")
            ctx.move_to(-36, top)
            ctx.curve_to(-20, top + 20, 18, top + 8, 34, top + 30)
            stroke(ctx, (0.55, 0.27, 0.05, 0.85), 7)
        if steam and n:
            for k in range(3):
                ph = (t * 0.5 + k / 3) % 1
                x0 = -24 + k * 24 + math.sin(t * 2 + k) * 6
                y0 = -60 - ph * 100
                ctx.move_to(x0, y0)
                ctx.curve_to(x0 + 12, y0 - 16, x0 - 12, y0 - 32, x0, y0 - 48)
                stroke(ctx, (1, 1, 1, 0.65 * (1 - ph)), 7)


def bedroom(ctx, t, night=False, drawer_open=0.0, phone_glow=False, lamp_on=None):
    if night:
        wall(ctx, "#2e3a59", "#3e4c70")
    else:
        wall(ctx, "#cde7d8", "#b7dcc8")
    # wallpaper stripes
    for xx in range(0, W, 90):
        ctx.rectangle(xx, 0, 40, FLOOR_Y)
        fill(ctx, (1, 1, 1, 0.05 if night else 0.18))
    window(ctx, 180, 160, 360, 300, t, night=night, curtains="#6d597a")
    picture_frame(ctx, 760, 170, 220, 160, "mountain")
    picture_frame(ctx, 1010, 200, 150, 120, "family", frame="#c68642")
    # bed (right side)
    rrect(ctx, 1260, 540, 600, 290, 24)
    fill(ctx, "#6d4c41")
    rrect(ctx, 1240, 430, 60, 400, 20)
    fill(ctx, "#5d4037")
    rrect(ctx, 1290, 600, 560, 150, 30)
    fill(ctx, "#e5e5e5")
    rrect(ctx, 1450, 580, 420, 190, 36)
    ctx.set_source(lin_grad(0, 580, 0, 770, [(0, "#4d908e"), (1, "#277da1")]))
    ctx.fill()
    rrect(ctx, 1300, 560, 150, 80, 30)
    fill(ctx, "#ffffff", preserve=True)
    stroke(ctx, "#d0d0d0", 3)
    # desk with drawer (left-centre)
    rrect(ctx, 600, 600, 420, 30, 6)
    fill(ctx, "#a47148")
    rrect(ctx, 620, 630, 380, 190, 6)
    fill(ctx, "#8d5524")
    # drawer
    dx = 640
    dy = 660 + drawer_open * 40
    rrect(ctx, dx, dy, 160, 70 + drawer_open * 10, 6)
    fill(ctx, "#b5835a", preserve=True)
    stroke(ctx, "#6f4518", 3)
    rrect(ctx, dx + 60, dy + 28 + drawer_open * 6, 40, 10, 5)
    fill(ctx, "#ffd166")
    if drawer_open < 0.05:
        # padlock
        with at(ctx, dx + 80, dy + 60):
            ctx.arc(0, -10, 12, math.pi, 0)
            stroke(ctx, "#adb5bd", 5)
            rrect(ctx, -16, -10, 32, 26, 5)
            fill(ctx, "#f4a261")
    if phone_glow:
        glow(ctx, dx + 80, dy - 10, 180, "#7fd3ff", 0.7)
    lamp(ctx, 940, 600, on=night if lamp_on is None else lamp_on, s=0.9)
    wall_clock(ctx, 1110, 380, 46, 7.0 if not night else 11.5, t)
    floor(ctx, "#a98467", "#7f5539")
    # rug
    ellipse(ctx, 960, 960, 520, 70)
    fill(ctx, (0.85, 0.45, 0.4, 0.55))
    if night:
        ctx.set_source_rgba(0.05, 0.08, 0.2, 0.28)
        ctx.paint()


def office(ctx, t, tension=0.0):
    wall(ctx, "#eef2f6", "#dde4ec")
    # big windows with city
    for i in range(3):
        window(ctx, 120 + i * 600, 120, 480, 330, t + i, curtains=None)
    # desks
    for x0 in (240, 1240):
        rrect(ctx, x0, 640, 480, 26, 6)
        fill(ctx, "#ced4da")
        rrect(ctx, x0 + 20, 666, 18, 160, 4)
        fill(ctx, "#868e96")
        rrect(ctx, x0 + 442, 666, 18, 160, 4)
        fill(ctx, "#868e96")
    plant(ctx, 1080, 820, 1.0, t, pot="#ffffff")
    plant(ctx, 1840, 820, 0.8, t + 2, pot="#2a9d8f")
    rrect(ctx, 80, 500, 260, 130, 10)
    fill(ctx, "#ffffff", preserve=True)
    stroke(ctx, "#ced4da", 3)
    # chart on whiteboard
    for k, h in enumerate((40, 70, 55, 95)):
        ctx.rectangle(110 + k * 52, 610 - h, 34, h)
        fill(ctx, ("#e63946", "#f4a261", "#2a9d8f", "#264653")[k])
    floor(ctx, "#adb5bd", "#868e96", boards=False)
    if tension:
        ctx.set_source_rgba(0.4, 0.4, 0.6, 0.15 * tension)
        ctx.paint()


def monitor(ctx, x, y, s=1.0, screen="#1d3557", t=0.0, content="code"):
    with at(ctx, x, y, s):
        rrect(ctx, -10, -20, 20, 60, 4)
        fill(ctx, "#495057")
        ellipse(ctx, 0, 40, 60, 10)
        fill(ctx, "#495057")
        rrect(ctx, -150, -200, 300, 190, 12)
        fill(ctx, "#212529")
        rrect(ctx, -140, -190, 280, 170, 6)
        fill(ctx, screen)
        if content == "code":
            r = seeded(5)
            for k in range(8):
                ww = 40 + r.random() * 160
                rrect(ctx, -120 + (k % 3) * 14, -175 + k * 19, ww, 9, 4)
                fill(ctx, ("#a8dadc", "#ffd166", "#f4a261", "#e9c46a")[k % 4])
        elif content == "email":
            for k in range(6):
                rrect(ctx, -126, -178 + k * 26, 252, 20, 4)
                fill(ctx, "#ffffff" if k else "#ffd166")


def street(ctx, t, scroll=0.0, evening=0.0):
    sky_top = mix("#4facfe", "#f77f00", evening)
    sky_bot = mix("#c2e9fb", "#fcbf49", evening)
    ctx.set_source(lin_grad(0, 0, 0, 700, [(0, sky_top), (1, sky_bot)]))
    ctx.paint()
    glow(ctx, 1560, 180 + evening * 300, 220, "#fff3b0", 0.8)
    circle(ctx, 1560, 180 + evening * 300, 70)
    fill(ctx, "#fff1a8" if not evening else "#ffb703")
    # far buildings (parallax)
    r = seeded(3)
    off = -(scroll * 0.3) % 2400
    bx = -off
    while bx < W + 200:
        bw = 120 + r.random() * 140
        bh = 220 + r.random() * 320
        c = ("#8ecae6", "#a2d2ff", "#bde0fe", "#90a8c3")[int(r.random() * 4)]
        ctx.rectangle(bx, 700 - bh, bw, bh)
        fill(ctx, c)
        for wy in range(int(700 - bh + 20), 690, 40):
            for wx in range(int(bx + 14), int(bx + bw - 20), 34):
                ctx.rectangle(wx, wy, 18, 22)
                fill(ctx, (1, 1, 1, 0.5))
        bx += bw + 18
        if bx > 2400:
            break
    # near shops
    off2 = -(scroll * 0.7) % 1400
    for i in range(-1, 4):
        sx = i * 700 - off2
        rrect(ctx, sx + 40, 330, 620, 400, 10)
        fill(ctx, ("#f28482", "#84a59d", "#f6bd60")[i % 3])
        rrect(ctx, sx + 80, 450, 260, 250, 8)
        fill(ctx, "#cfe8ff", preserve=True)
        stroke(ctx, "#ffffff", 8)
        rrect(ctx, sx + 400, 480, 120, 220, 6)
        fill(ctx, shade(("#f28482", "#84a59d", "#f6bd60")[i % 3], -0.3))
        # awning
        for k in range(8):
            ctx.rectangle(sx + 60 + k * 72, 380, 72, 50)
            fill(ctx, "#ffffff" if k % 2 else "#e63946")
        rrect(ctx, sx + 200, 340, 260, 34, 6)
        fill(ctx, "#ffffff")
        text(ctx, ("CAFE", "BOOKS", "BAKERY")[i % 3], sx + 330, 357, 26, "#333333")
    # sidewalk
    ctx.rectangle(0, 730, W, 350)
    ctx.set_source(lin_grad(0, 730, 0, H, [(0, "#d6d6d6"), (1, "#b0b0b0")]))
    ctx.fill()
    off3 = -(scroll) % 220
    x = -off3
    while x < W:
        line(ctx, x, 730, x - 120, H, "#a5a5a5", 3)
        x += 220
    ctx.rectangle(0, 1010, W, 70)
    fill(ctx, "#5c5c5c")
    if evening:
        ctx.set_source_rgba(1, 0.5, 0.2, 0.12 * evening)
        ctx.paint()


def park(ctx, t, golden=0.0):
    ctx.set_source(lin_grad(0, 0, 0, 760, [(0, mix("#74c0fc", "#ffb347", golden)), (1, mix("#e7f5ff", "#ffe5b4", golden))]))
    ctx.paint()
    glow(ctx, 1500, 200, 260, "#fff3b0", 0.9)
    circle(ctx, 1500, 200, 72)
    fill(ctx, "#fff3a0")
    # hills
    ctx.move_to(0, 640)
    ctx.curve_to(400, 520, 800, 600, 1100, 560)
    ctx.curve_to(1400, 520, 1700, 560, W, 600)
    ctx.line_to(W, H)
    ctx.line_to(0, H)
    ctx.close_path()
    fill(ctx, "#95d5b2")
    ctx.move_to(0, 760)
    ctx.curve_to(500, 700, 1200, 760, W, 720)
    ctx.line_to(W, H)
    ctx.line_to(0, H)
    ctx.close_path()
    ctx.set_source(lin_grad(0, 700, 0, H, [(0, "#74c69d"), (1, "#40916c")]))
    ctx.fill()
    # trees
    for tx, ts in ((180, 1.1), (520, 0.8), (1350, 0.9), (1750, 1.2)):
        with at(ctx, tx, 760, ts):
            rrect(ctx, -18, -200, 36, 210, 10)
            fill(ctx, "#7f5539")
            sway = math.sin(t * 0.9 + tx) * 6
            for dx, dy, rr in ((0, -260, 110), (-70, -210, 80), (70, -210, 80), (0, -340, 80)):
                circle(ctx, dx + sway, dy, rr)
                fill(ctx, "#2d6a4f" if dy < -250 else "#40916c")
    # path
    ctx.move_to(760, H)
    ctx.curve_to(840, 900, 980, 800, 1060, 740)
    ctx.line_to(1110, 740)
    ctx.curve_to(1060, 820, 1040, 920, 1160, H)
    ctx.close_path()
    fill(ctx, "#e9d8a6")
    # birds
    for k in range(3):
        bx = (t * 60 + k * 300) % (W + 200) - 100
        by = 260 + k * 40 + math.sin(t * 2 + k) * 10
        flap = math.sin(t * 10 + k) * 8
        ctx.move_to(bx - 16, by - flap)
        ctx.curve_to(bx - 8, by - 10, bx - 4, by - 4, bx, by)
        ctx.curve_to(bx + 4, by - 4, bx + 8, by - 10, bx + 16, by - flap)
        stroke(ctx, "#333", 3)
    if golden:
        ctx.set_source_rgba(1, 0.6, 0.2, 0.1 * golden)
        ctx.paint()


def bench(ctx, x, y, s=1.0):
    with at(ctx, x, y, s):
        for lx in (-170, 170):
            rrect(ctx, lx - 10, -90, 20, 90, 4)
            fill(ctx, "#343a40")
        for k in range(3):
            rrect(ctx, -210, -210 + k * 30, 420, 20, 6)
            fill(ctx, "#bc6c25")
        rrect(ctx, -220, -100, 440, 26, 6)
        fill(ctx, "#dda15e")


def couch(ctx, x, y, s=1.0, c="#457b9d"):
    with at(ctx, x, y, s):
        soft_shadow(ctx, 0, 10, 340, 26, 0.3)
        rrect(ctx, -320, -300, 640, 200, 40)
        fill(ctx, shade(c, -0.1))
        rrect(ctx, -300, -150, 600, 110, 30)
        fill(ctx, c)
        for side in (-1, 1):
            rrect(ctx, side * 320 - 50, -230, 100, 210, 40)
            fill(ctx, shade(c, -0.18))
        for k in (-1, 1):
            rrect(ctx, k * 140 - 130, -170, 260, 50, 22)
            fill(ctx, shade(c, 0.1))


def grandma_kitchen(ctx, t):
    wall(ctx, "#fff1d6", "#f6d7a7")
    # floral wallpaper
    r = seeded(11)
    for yy in range(40, 760, 110):
        for xx in range(30, W, 120):
            ox = 60 if (yy // 110) % 2 else 0
            cx, cy = xx + ox, yy
            for k in range(5):
                a = k * TAU / 5
                circle(ctx, cx + math.cos(a) * 9, cy + math.sin(a) * 9, 7)
                fill(ctx, (0.9, 0.55, 0.55, 0.35))
            circle(ctx, cx, cy, 5)
            fill(ctx, (0.95, 0.8, 0.4, 0.5))
    window(ctx, 1180, 170, 380, 280, t, curtains="#e5989b")
    # old wall phone
    with at(ctx, 420, 360):
        rrect(ctx, -60, -110, 120, 220, 16)
        fill(ctx, "#f2cc8f", preserve=True)
        stroke(ctx, "#bc8a4f", 4)
        for i in range(12):
            circle(ctx, -28 + (i % 3) * 28, -30 + (i // 3) * 28, 10)
            fill(ctx, "#fff7e6")
        rrect(ctx, -76, -150, 40, 140, 18)
        fill(ctx, "#e07a5f")
        ctx.move_to(-56, 0)
        for k in range(10):
            ctx.curve_to(-70, 20 + k * 22, -40, 30 + k * 22, -56, 42 + k * 22)
        stroke(ctx, "#e07a5f", 4)
    picture_frame(ctx, 700, 200, 240, 180, "family", frame="#9c6644")
    # shelf with jars
    rrect(ctx, 640, 470, 420, 16, 4)
    fill(ctx, "#9c6644")
    for k, c in enumerate(("#f4a261", "#e76f51", "#2a9d8f", "#e9c46a")):
        rrect(ctx, 670 + k * 98, 400, 70, 72, 12)
        fill(ctx, with_alpha(c, 0.85), preserve=True)
        stroke(ctx, shade(c, -0.3), 3)
        rrect(ctx, 676 + k * 98, 392, 58, 14, 4)
        fill(ctx, "#ffffff")
    # counter
    rrect(ctx, 0, 650, W, 36, 6)
    fill(ctx, "#fefae0")
    ctx.rectangle(0, 684, W, FLOOR_Y - 684)
    fill(ctx, "#ccd5ae")
    for x0 in range(30, W, 250):
        rrect(ctx, x0, 704, 220, 104, 8)
        stroke(ctx, "#a3b18a", 4)
    # kettle
    with at(ctx, 1500, 650):
        ellipse(ctx, 0, -50, 70, 56)
        fill(ctx, "#e63946", preserve=True)
        stroke(ctx, "#9d0208", 3)
        ctx.arc(0, -96, 34, math.pi, 0)
        stroke(ctx, "#333", 6)
    floor(ctx, "#ddb892", "#b08968")
    # warm light
    ctx.set_source(rad_grad(1370, 300, 50, 1300, [(0, (1, 0.85, 0.5, 0.25)), (1, (1, 0.85, 0.5, 0))]))
    ctx.paint()


def hallway_door(ctx, t, plates=0, light="day", knock=0.0):
    wall(ctx, "#e9edc9", "#ccd5ae") if light == "day" else wall(ctx, "#b8c0a0", "#9aa284")
    # door
    shake = math.sin(t * 60) * 4 * knock
    with at(ctx, W / 2 + shake, 0):
        rrect(ctx, -230, 120, 460, 710, 10)
        fill(ctx, "#6f4518")
        rrect(ctx, -210, 140, 420, 690, 8)
        ctx.set_source(lin_grad(-210, 0, 210, 0, [(0, "#bc6c25"), (1, "#99582a")]))
        ctx.fill()
        for (x0, y0, w0, h0) in ((-170, 180, 150, 260), (20, 180, 150, 260), (-170, 490, 150, 280), (20, 490, 150, 280)):
            rrect(ctx, x0, y0, w0, h0, 8)
            stroke(ctx, "#7f4f24", 6)
        circle(ctx, 160, 500, 18)
        fill(ctx, "#ffd166", preserve=True)
        stroke(ctx, "#b5838d", 3)
        # name sign
        rrect(ctx, -80, 80, 160, 50, 10)
        fill(ctx, "#ffffff", preserve=True)
        stroke(ctx, "#6f4518", 3)
        text(ctx, "MAX'S ROOM", 0, 105, 26, "#6f4518")
        rrect(ctx, -60, 300, 120, 70, 8)
        fill(ctx, "#fefae0")
        text(ctx, "DO NOT", 0, 322, 22, "#e63946")
        text(ctx, "DISTURB", 0, 350, 22, "#e63946")
    plant(ctx, 360, 840, 1.1, t, pot="#e9c46a")
    picture_frame(ctx, 1460, 260, 240, 180, "mountain")
    floor(ctx, "#cdb4db", "#a08ab8", boards=False)
    # stack of plates (accumulating)
    for k in range(min(plates, 12)):
        ellipse(ctx, W / 2 - 300 + (k % 2) * 4, 900 - k * 10, 90, 22)
        fill(ctx, "#ffffff", preserve=True)
        stroke(ctx, "#c9ced6", 3)


def studio_bg(ctx, t, c1="#1e6fff", c2="#0a2a8a", rays=True, ray_c=(1, 1, 1, 0.06)):
    ctx.set_source(rad_grad(W / 2, H / 2, 50, W * 0.75, [(0, c1), (1, c2)]))
    ctx.paint()
    if rays:
        with at(ctx, W / 2, H / 2, rot=t * 0.08):
            for i in range(18):
                a0 = i * TAU / 18
                ctx.move_to(0, 0)
                ctx.line_to(math.cos(a0) * 2200, math.sin(a0) * 2200)
                ctx.line_to(math.cos(a0 + TAU / 36) * 2200, math.sin(a0 + TAU / 36) * 2200)
                ctx.close_path()
                set_color(ctx, ray_c)
                ctx.fill()


def gray_room(ctx, t):
    wall(ctx, "#5c677d", "#4a5468")
    window(ctx, 200, 160, 360, 300, t, night=True, curtains="#33415c")
    floor(ctx, "#5c5470", "#3f3a50", boards=False)


# --------------------------------------------------------------------------
# Phone UI
# --------------------------------------------------------------------------


def phone_frame(ctx, x, y, s, draw_screen, t=0.0, tilt=0.0):
    """Big phone with a screen callback draw_screen(ctx, w, h)."""
    w, h = 470, 940
    with at(ctx, x, y, s, rot=tilt):
        soft_shadow(ctx, 20, h / 2 + 20, 260, 40, 0.35)
        rrect(ctx, -w / 2 - 16, -h / 2 - 16, w + 32, h + 32, 70)
        ctx.set_source(lin_grad(-w / 2, 0, w / 2, 0, [(0, "#2b2d31"), (0.5, "#4a4d55"), (1, "#1d1f23")]))
        ctx.fill()
        rrect(ctx, -w / 2, -h / 2, w, h, 56)
        fill(ctx, "#000000")
        with saved(ctx):
            rrect(ctx, -w / 2 + 6, -h / 2 + 6, w - 12, h - 12, 50)
            ctx.clip()
            ctx.translate(-w / 2 + 6, -h / 2 + 6)
            draw_screen(ctx, w - 12, h - 12)
        rrect(ctx, -60, -h / 2 + 18, 120, 30, 15)
        fill(ctx, "#000000")


def notif_card(ctx, x, y, w, icon_c, title, body, alpha=1.0, time_s="now", icon_txt=""):
    with saved(ctx):
        ctx.push_group()
        rrect(ctx, x, y, w, 104, 22)
        fill(ctx, (1, 1, 1, 0.94))
        rrect(ctx, x + 16, y + 18, 52, 52, 13)
        fill(ctx, icon_c)
        if icon_txt:
            text(ctx, icon_txt, x + 42, y + 44, 28, "#ffffff", family="Inter", bold=True)
        ui_text(ctx, title, x + 84, y + 34, 22, "#111111", bold=True)
        ui_text(ctx, time_s, x + w - 18, y + 34, 18, "#888888", align="right")
        ui_text(ctx, body[:34] + ("…" if len(body) > 34 else ""), x + 84, y + 70, 20, "#333333")
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(alpha)


def chat_bubble(ctx, x, y, msg, me=False, size=30, max_w=560, color=None, scale=1.0):
    from .gfx import wrap
    lines_ = wrap(ctx, msg, size, max_w, family="Inter")
    from .gfx import text_size
    tw = max(text_size(ctx, l, size, "Inter")[0] for l in lines_)
    bw = tw + 48
    bh = len(lines_) * size * 1.3 + 30
    bx = x - bw if me else x
    col = color or ("#1e88ff" if me else "#e9e9eb")
    with at(ctx, bx + (bw if me else 0), y + bh / 2, scale):
        ox = -bw if me else 0
        rrect(ctx, ox, -bh / 2, bw, bh, 26)
        fill(ctx, col)
        for i, l in enumerate(lines_):
            ui_text(ctx, l, ox + 24, -bh / 2 + 15 + size * 0.65 + i * size * 1.3, size,
                    "#ffffff" if me else "#111111")
    return bh
