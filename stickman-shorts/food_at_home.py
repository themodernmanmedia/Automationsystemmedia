"""Stick man short: "When your mom says 'We have food at home'" (60s, 1080x1920).

Renders every frame with Pillow, synthesizes all audio with numpy and muxes with ffmpeg.
Usage:  python3 food_at_home.py [out.mp4]          full render
        python3 food_at_home.py --stills DIR t1 t2  render stills at given seconds
"""
import math, random, subprocess, sys, wave, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, K, FPS, DUR = 1080, 1920, 2, 30, 60.0
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
_fc = {}


def font(sz):
    sz = max(2, int(sz * K))
    if sz not in _fc:
        _fc[sz] = ImageFont.truetype(FONT, sz)
    return _fc[sz]


def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(t, a, b): return clamp((t - a) / (b - a))
def ease(p): return p * p * (3 - 2 * p)
def lerp(a, b, p): return a + (b - a) * p
def lerpc(c1, c2, p): return tuple(int(lerp(a, b, p)) for a, b in zip(c1, c2))


def back(p):
    c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def vec(p, L, ang):
    r = math.radians(ang)
    return (p[0] + L * math.sin(r), p[1] + L * math.cos(r))


def rot_pt(p, piv, ang):
    r = math.radians(ang); dx, dy = p[0] - piv[0], p[1] - piv[1]
    return (piv[0] + dx * math.cos(r) - dy * math.sin(r), piv[1] + dx * math.sin(r) + dy * math.cos(r))


class Cv:
    def __init__(s):
        s.img = Image.new('RGB', (W * K, H * K)); s.d = ImageDraw.Draw(s.img); s.ox = 0; s.oy = 0

    def P(s, x, y): return ((x + s.ox) * K, (y + s.oy) * K)

    def fill(s, col): s.d.rectangle([0, 0, W * K, H * K], fill=col)

    def line(s, pts, col, w):
        q = [s.P(*p) for p in pts]
        s.d.line(q, fill=col, width=max(1, int(w * K)), joint='curve')
        r = w * K / 2
        for x, y in (q[0], q[-1]):
            s.d.ellipse([x - r, y - r, x + r, y + r], fill=col)

    def circle(s, x, y, r, fill=None, outline=None, w=0):
        X, Y = s.P(x, y); R = r * K
        s.d.ellipse([X - R, Y - R, X + R, Y + R], fill=fill, outline=outline, width=int(w * K))

    def ellipse(s, x0, y0, x1, y1, fill=None, outline=None, w=0):
        a = s.P(x0, y0); b = s.P(x1, y1)
        s.d.ellipse([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])], fill=fill, outline=outline, width=int(w * K))

    def rect(s, x0, y0, x1, y1, fill=None, outline=None, w=0, r=0):
        a = s.P(x0, y0); b = s.P(x1, y1)
        s.d.rounded_rectangle([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])], radius=r * K, fill=fill, outline=outline, width=int(w * K))

    def poly(s, pts, fill=None, outline=None, w=0):
        s.d.polygon([s.P(*p) for p in pts], fill=fill, outline=outline, width=int(w * K))

    def arc(s, cx, cy, rx, ry, a0, a1, col, w):
        a = s.P(cx - rx, cy - ry); b = s.P(cx + rx, cy + ry)
        s.d.arc([a[0], a[1], b[0], b[1]], a0, a1, fill=col, width=max(1, int(w * K)))

    def pie(s, cx, cy, r, a0, a1, fill):
        a = s.P(cx - r, cy - r); b = s.P(cx + r, cy + r)
        s.d.pieslice([a[0], a[1], b[0], b[1]], a0, a1, fill=fill)

    def chord(s, cx, cy, r, a0, a1, fill):
        a = s.P(cx - r, cy - r); b = s.P(cx + r, cy + r)
        s.d.chord([a[0], a[1], b[0], b[1]], a0, a1, fill=fill)

    def text(s, x, y, txt, sz, fill, anchor='mm', stroke=0, sf=(0, 0, 0)):
        s.d.text(s.P(x, y), txt, font=font(sz), fill=fill, anchor=anchor, stroke_width=int(stroke * K), stroke_fill=sf)

    def out(s): return s.img.reduce(K)


# ---------------------------------------------------------------- characters
INK = (25, 25, 32)
WHITE = (255, 255, 255)
SKIN = (255, 255, 255)
GREEN_SICK = (70, 160, 60)


def draw_face(c, hc, r, face, dr, look, col, s, talk):
    ex = look * r * 0.22 + dr * r * 0.14
    ey = hc[1] - 0.05 * r
    L = (hc[0] - 0.32 * r + ex, ey); R = (hc[0] + 0.32 * r + ex, ey)
    lw = max(2.5, 4.5 * s)
    if face in ('shock', 'scared', 'mad_shock'):
        for p in (L, R):
            c.circle(p[0], p[1], r * 0.23, fill=WHITE, outline=col, w=lw * 0.8)
            c.circle(p[0] + dr * 2 * s, p[1], r * 0.08, fill=col)
    elif face == 'dead':
        for p in (L, R):
            d = r * 0.14
            c.line([(p[0] - d, p[1] - d), (p[0] + d, p[1] + d)], col, lw)
            c.line([(p[0] - d, p[1] + d), (p[0] + d, p[1] - d)], col, lw)
    elif face in ('sly', 'deadpan'):
        for p in (L, R):
            c.circle(p[0], p[1] + r * 0.03, r * 0.09, fill=col)
            c.line([(p[0] - r * 0.17, p[1] - r * 0.04), (p[0] + r * 0.17, p[1] - r * 0.04)], col, lw)
    elif face == 'sick':
        for p in (L, R):
            c.arc(p[0], p[1], r * 0.14, r * 0.14, 0, 300, col, lw * 0.8)
    else:
        for p in (L, R):
            c.circle(p[0], p[1], r * 0.1, fill=col)
    # brows
    if face in ('sad', 'scared'):
        c.line([(L[0] - r * 0.15, L[1] - r * 0.2), (L[0] + r * 0.12, L[1] - r * 0.3)], col, lw * 0.8)
        c.line([(R[0] - r * 0.12, R[1] - r * 0.3), (R[0] + r * 0.15, R[1] - r * 0.2)], col, lw * 0.8)
    if face in ('stern', 'angry', 'mad_shock'):
        c.line([(L[0] - r * 0.15, L[1] - r * 0.32), (L[0] + r * 0.15, L[1] - r * 0.2)], col, lw)
        c.line([(R[0] - r * 0.15, R[1] - r * 0.2), (R[0] + r * 0.15, R[1] - r * 0.32)], col, lw)
    if face == 'sly':
        c.line([(L[0] - r * 0.15, L[1] - r * 0.3), (L[0] + r * 0.15, L[1] - r * 0.24)], col, lw * 0.8)
        c.line([(R[0] - r * 0.15, R[1] - r * 0.36), (R[0] + r * 0.15, R[1] - r * 0.28)], col, lw * 0.8)
    # mouth
    mx, my = hc[0] + ex, hc[1] + 0.42 * r
    if talk > 0.15 and face not in ('dead',):
        h = r * (0.08 + 0.2 * talk)
        c.ellipse(mx - r * 0.17, my - h, mx + r * 0.17, my + h, fill=(120, 30, 40), outline=col, w=lw * 0.7)
        return
    if face in ('happy',):
        c.arc(mx, my - r * 0.14, r * 0.3, r * 0.2, 20, 160, col, lw)
    elif face == 'excited':
        c.chord(mx, my - r * 0.12, r * 0.28, 0, 180, (120, 30, 40))
    elif face in ('sad',):
        c.arc(mx, my + r * 0.12, r * 0.24, r * 0.14, 200, 340, col, lw)
    elif face in ('shock', 'scared', 'mad_shock'):
        c.ellipse(mx - r * 0.14, my - r * 0.14, mx + r * 0.14, my + r * 0.18, fill=(120, 30, 40), outline=col, w=lw * 0.7)
    elif face == 'sick':
        pts = [(mx - r * 0.3 + i * r * 0.1, my + (r * 0.05 if i % 2 else -r * 0.05)) for i in range(7)]
        c.line(pts, col, lw * 0.8)
    elif face == 'sly':
        c.arc(mx + r * 0.05, my - r * 0.16, r * 0.26, r * 0.18, 10, 110, col, lw)
    elif face == 'dead':
        c.line([(mx - r * 0.22, my), (mx + r * 0.22, my)], col, lw)
        c.ellipse(mx - r * 0.02, my, mx + r * 0.2, my + r * 0.3, fill=(240, 110, 130), outline=col, w=lw * 0.6)
    else:  # neutral / stern / deadpan / angry
        c.line([(mx - r * 0.18, my), (mx + r * 0.18, my)], col, lw)


def stick(c, hip, s=1.0, col=INK, torso=180, arms=((30, 15), (-30, -15)), legs=((12, 4), (-12, -4)),
          face='happy', dr=1, who='kid', rot=0, look=0, talk=0.0, sway=0.0, behind=None):
    """Draw a stick figure. Angles: 0=down, 90=right, 180=up, -90=left. Returns joints."""
    w = 12 * s
    t = torso + rot
    neck = vec(hip, 150 * s, t)
    sh = vec(hip, 132 * s, t)
    r = 48 * s
    hc = vec(neck, r + 4 * s, t)
    hands = []
    for th, sn in legs:
        k = vec(hip, 90 * s, th + rot); f = vec(k, 88 * s, sn + rot)
        c.line([hip, k, f], col, w)
    if behind:
        behind(sh)
    if who == 'mom':  # ponytail behind head
        bx, by = hc[0] - dr * r * 0.8, hc[1] - r * 0.45
        hair = (110, 60, 35)
        c.line([(bx, by), (bx - dr * 38 * s, by + 25 * s + sway), (bx - dr * 40 * s, by + 80 * s + sway * 1.6)], hair, 22 * s)
    c.line([hip, neck], col, w)
    for ua, fa in arms:
        e = vec(sh, 78 * s, ua + rot); h = vec(e, 72 * s, fa + rot)
        c.line([sh, e, h], col, w); hands.append(h)
    c.circle(hc[0], hc[1], r, fill=SKIN, outline=col, w=w * 0.85)
    if who == 'mom':
        hair = (110, 60, 35)
        c.chord(hc[0], hc[1], r + 2 * s, 195, 345, hair)
        bx, by = hc[0] - dr * r * 0.8, hc[1] - r * 0.45
        pk = (240, 90, 150)
        c.poly([(bx, by), (bx - 22 * s, by - 16 * s), (bx - 22 * s, by + 16 * s)], fill=pk)
        c.poly([(bx, by), (bx + 22 * s, by - 16 * s), (bx + 22 * s, by + 16 * s)], fill=pk)
        c.circle(bx, by, 7 * s, fill=(200, 50, 110))
    elif who in ('kid', 'guy'):
        cap = (220, 50, 50) if who == 'kid' else (40, 90, 200)
        c.chord(hc[0], hc[1] - r * 0.12, r * 1.02, 180, 360, cap)
        c.line([(hc[0] + dr * r * 0.1, hc[1] - r * 0.14), (hc[0] + dr * r * 1.35, hc[1] - r * 0.1)], cap, 11 * s)
    draw_face(c, hc, r, face, dr, look, col, s, talk)
    return {'hands': hands, 'head': hc, 'sh': sh, 'neck': neck, 'r': r}


def walk_pose(t, a=26, dr=1, speed=10):
    ph = math.sin(t * speed)
    legs = ((dr * a * ph, dr * (a * ph - 22)), (-dr * a * ph, dr * (-a * ph - 22)))
    arms = ((-dr * a * ph * 0.9 + 18, -dr * a * ph * 0.9 + 40), (dr * a * ph * 0.9 - 18, dr * a * ph * 0.9 - 40))
    return legs, arms, abs(ph) * 6


# ---------------------------------------------------------------- UI pieces
def wrap(txt, sz, maxw):
    f = font(sz); words = txt.split(' '); lines = []; cur = ''
    for wd in words:
        tst = (cur + ' ' + wd).strip()
        if f.getlength(tst) / K <= maxw or not cur:
            cur = tst
        else:
            lines.append(cur); cur = wd
    lines.append(cur)
    return lines


# (start, end, speaker, text, bubble center, tail tip)
LINES = [
    (6.2, 9.3, 'kid', "MOM! Can we get BURGERS?!", (330, 800), (420, 995)),
    (9.6, 12.9, 'mom', "We have food at home.", (740, 800), (690, 990)),
    (19.0, 21.4, 'kid', "...one egg.", (320, 860), (450, 1080)),
    (21.8, 24.1, 'kid', "Uh... why is it MOVING?", (330, 850), (450, 1080)),
    (28.5, 32.4, 'mom', "Tonight I'm making my famous LEFTOVER SURPRISE!", (480, 780), (400, 1085)),
    (36.4, 39.7, 'kid', "...Mom. It BLINKED.", (760, 880), (860, 1100)),
    (40.0, 43.6, 'mom', "Eat it! Kids out there would LOVE this.", (440, 780), (400, 1085)),
    (51.8, 54.2, 'guy', "One LARGE burger combo... for Mom?", (700, 800), (830, 1068)),
    (54.7, 56.0, 'kid', "MOM?!", (270, 950), (250, 1110)),
    (56.1, 58.6, 'mom', "What? This is MY food at home.", (520, 770), (560, 1088)),
]


def type_rate(ln):
    st, en, _, txt, _, _ = ln
    return max(26.0, len(txt) / (0.62 * (en - st)))


def talking(who, t):
    for ln in LINES:
        if ln[2] == who and ln[0] <= t < ln[1]:
            n = (t - ln[0]) * type_rate(ln)
            if n < len(ln[3]):
                return 0.5 + 0.5 * math.sin(t * 32)
    return 0.0


def bubble(c, t, ln):
    st, en, who, txt, (bx, by), (tx, ty) = ln
    if not (st <= t < en):
        return
    sz = 54 if len(txt) > 10 else 80
    lines = wrap(txt, sz, 600)
    f = font(sz)
    lw = max(f.getlength(l) for l in lines) / K
    lh = sz * 1.22
    bw = lw + 80; bh = len(lines) * lh + 56
    x0 = clamp(bx - bw / 2, 30, W - 30 - bw); y0 = by - bh / 2
    cx, cy = x0 + bw / 2, y0 + bh / 2
    p = prog(t, st, st + 0.22); sc = back(p) if p < 1 else 1
    sc = max(0.05, sc)
    X0, X1 = cx - bw / 2 * sc, cx + bw / 2 * sc
    Y0, Y1 = cy - bh / 2 * sc, cy + bh / 2 * sc
    c.rect(X0 + 8, Y0 + 10, X1 + 8, Y1 + 10, fill=(0, 0, 0), r=40 * sc)  # drop shadow
    c.rect(X0, Y0, X1, Y1, fill=WHITE, outline=INK, w=6, r=40 * sc)
    down = ty > Y1
    edge = Y1 if down else Y0
    inset = -9 if down else 9
    bxc = clamp(tx, X0 + 70 * sc, X1 - 70 * sc)
    tip = (lerp(bxc, tx, sc), lerp(edge, ty, sc))
    a, b = (bxc - 30 * sc, edge), (bxc + 30 * sc, edge)
    c.poly([(a[0], edge + inset), (b[0], edge + inset), tip], fill=WHITE)
    c.line([a, tip], INK, 6); c.line([b, tip], INK, 6)
    if p < 0.6:
        return
    n = int((t - st) * type_rate(ln))
    for i, l in enumerate(lines):
        y = cy - (len(lines) - 1) * lh / 2 + i * lh
        full = f.getlength(l) / K
        vis = l[:max(0, n)]
        n -= len(l) + 1
        if vis:
            col = (200, 30, 40) if who == 'kid' and txt.isupper() else (30, 30, 36)
            c.text(cx - full / 2, y, vis, sz, col, anchor='lm')


def caption(c, t, t0, txt, y=420, sz=96, col=WHITE, t1=None):
    if t < t0 or (t1 is not None and t >= t1):
        return
    p = prog(t, t0, t0 + 0.25); sc = back(p) if p < 1 else 1
    for i, l in enumerate(txt.split('\n')):
        c.text(540, y + i * sz * 1.15, l, sz * max(0.05, sc), col, stroke=9, sf=INK)


def header(c):
    c.rect(0, 70, 1080, 240, fill=(20, 20, 28))
    c.text(540, 122, 'WHEN YOUR MOM SAYS', 42, (255, 214, 64))
    c.text(540, 190, '"WE HAVE FOOD AT HOME"', 56, WHITE)


def sunburst(c, t, c1, c2, cx=540, cy=1000):
    c.fill(c1)
    for i in range(18):
        a0 = math.radians(i * 20 + t * 12); a1 = math.radians(i * 20 + 10 + t * 12)
        c.poly([(cx, cy), (cx + 2600 * math.cos(a0), cy + 2600 * math.sin(a0)), (cx + 2600 * math.cos(a1), cy + 2600 * math.sin(a1))], fill=c2)


# ---------------------------------------------------------------- props
def burger_icon(c, x, y, s=1.0):
    c.chord(x, y + 10 * s, 62 * s, 180, 360, (235, 160, 60))
    for i in range(5):
        c.circle(x - 34 * s + i * 17 * s, y - 25 * s + (i % 2) * 8 * s, 3 * s, fill=(255, 240, 200))
    c.line([(x - 64 * s, y + 18 * s), (x + 64 * s, y + 18 * s)], (90, 190, 60), 10 * s)
    c.rect(x - 60 * s, y + 22 * s, x + 60 * s, y + 46 * s, fill=(110, 60, 30), r=10 * s)
    c.line([(x - 58 * s, y + 50 * s), (x + 58 * s, y + 50 * s)], (250, 200, 40), 7 * s)
    c.rect(x - 60 * s, y + 52 * s, x + 60 * s, y + 72 * s, fill=(235, 160, 60), r=10 * s)


def blob(c, x, y, t, scale=1.0, blink=False, look=0):
    """The leftover surprise: a lumpy, jiggly, sentient blob sitting at (x, y=plate top)."""
    jig = 1 + 0.06 * math.sin(t * 9)
    pts = []
    for i in range(24):
        a = math.pi + i * math.pi / 23
        rr = 70 * scale * (1 + 0.12 * math.sin(i * 2.7 + t * 4))
        pts.append((x + rr * math.cos(a) * 1.25, y + rr * math.sin(a) * jig))
    c.poly(pts, fill=(140, 160, 95), outline=(70, 90, 50), w=4)
    for k in range(4):
        c.circle(x - 40 * scale + k * 27 * scale, y - 25 * scale - (k % 2) * 18 * scale, 7 * scale, fill=(110, 130, 70))
    ey = y - 48 * scale * jig
    for dx in (-20, 20):
        ex = x + dx * scale
        if blink:
            c.line([(ex - 13 * scale, ey), (ex + 13 * scale, ey)], INK, 4)
        else:
            c.circle(ex, ey, 14 * scale, fill=WHITE, outline=INK, w=3)
            c.circle(ex + look * 6 * scale, ey, 6 * scale, fill=INK)


def plate(c, x, y):
    c.ellipse(x - 100, y - 14, x + 100, y + 14, fill=(245, 245, 245), outline=INK, w=4)


# ---------------------------------------------------------------- scenes
def scene_title(c, t):
    sunburst(c, t, (255, 205, 50), (255, 222, 110), cy=1300)
    caption(c, t, 0.25, 'WHEN YOUR MOM SAYS', y=330, sz=68)
    caption(c, t, 0.85, '"WE HAVE\nFOOD AT\nHOME"', y=560, sz=150, col=(255, 70, 70))
    g = 1780
    bob = math.sin(t * 6) * 4
    stick(c, (620, g - 176 * 1.45 + bob), 1.45, arms=((-25, -10), (150, 175)), face='stern', dr=-1, who='mom',
          sway=math.sin(t * 5) * 6, legs=((10, 4), (-10, -4)))
    stick(c, (300, g - 176 * 0.95), 0.95, arms=((25, 10), (-25, -10)), face='sad', dr=1, who='kid')
    c.text(540, 1850, 'a stick man story', 34, INK)


BUILD = []
_rng = random.Random(7)
_x = -200
while _x < 4000:
    w_ = _rng.randint(170, 260)
    BUILD.append((_x, w_, _rng.randint(280, 620), _rng.choice([(120, 140, 190), (160, 120, 170), (110, 170, 160), (190, 150, 120), (140, 150, 160)])))
    _x += w_ + _rng.randint(10, 40)


def scene_car(c, t):
    lt = t - 3.5
    c.fill((150, 210, 250))
    c.circle(900, 360, 70, fill=(255, 230, 90))
    for bx, bw, bh, col in BUILD:
        x = bx - 140 * lt
        if x > W or x + bw < 0:
            continue
        c.rect(x, 1160 - bh, x + bw, 1160, fill=col)
        for wy in range(int(1160 - bh + 30), 1130, 70):
            for wx in range(int(x + 25), int(x + bw - 40), 55):
                c.rect(wx, wy, wx + 30, wy + 38, fill=(230, 240, 255))
    # burger sign
    sx = 420 - 260 * (t - 8)
    if -300 < sx < 1400:
        c.line([(sx, 1160), (sx, 640)], (90, 90, 100), 18)
        c.rect(sx - 180, 420, sx + 180, 650, fill=(220, 40, 40), outline=(255, 220, 60), w=10, r=24)
        burger_icon(c, sx, 470, 0.85)
        c.text(sx, 610, 'BURGERS', 52, (255, 220, 60))
    c.rect(0, 1150, W, 1180, fill=(200, 200, 205))
    c.rect(0, 1180, W, 1620, fill=(75, 75, 82))
    off = (lt * 700) % 220
    for i in range(7):
        x = i * 220 - off
        c.rect(x, 1540, x + 120, 1556, fill=(250, 230, 120))
    c.rect(0, 1620, W, H, fill=(110, 185, 90))
    # car
    dy = math.sin(t * 14) * 3
    red = (225, 60, 60)
    c.poly([(250, 1125 + dy), (345, 960 + dy), (740, 960 + dy), (850, 1125 + dy)], fill=red)
    c.poly([(285, 1120 + dy), (365, 985 + dy), (525, 985 + dy), (525, 1120 + dy)], fill=(205, 232, 255))
    c.poly([(550, 1120 + dy), (550, 985 + dy), (725, 985 + dy), (815, 1120 + dy)], fill=(205, 232, 255))
    # kid in back seat
    asking = 6.2 <= t < 9.6
    kid_face = 'excited' if t < 9.6 else ('sad' if t > 11.2 else 'neutral')
    kh = (430, 1188 + dy)
    sh = vec(kh, 132 * 0.72, 180)
    kdr = 1
    karms = ((40, 20), (-30, -10))
    if asking or t < 6.2 and sx < 1000:
        kdr = -1 if sx < kh[0] else 1
        ang = math.degrees(math.atan2(sx - sh[0], 520 - sh[1]))
        karms = ((ang, ang), (-30, -10)) if asking else karms
    stick(c, kh, 0.72, arms=karms, face=kid_face, dr=kdr, who='kid', talk=talking('kid', t), legs=((90, 10), (90, 10)))
    # mom driving
    mtalk = talking('mom', t)
    mdr = -1 if 9.4 < t < 12.4 else 1
    stick(c, (690, 1190 + dy), 0.75, arms=((65, 105), (55, 100)), face='stern' if mdr < 0 else 'neutral', dr=mdr, who='mom',
          talk=mtalk, sway=math.sin(t * 7) * 3, legs=((90, 10), (90, 10)))
    c.line([(790, 1045 + dy), (812, 1125 + dy)], (40, 40, 45), 14)
    c.rect(130, 1118 + dy, 950, 1330 + dy, fill=red, r=50)
    c.line([(525, 985 + dy), (525, 1125 + dy)], red, 22)
    c.line([(400, 1170 + dy), (450, 1170 + dy)], (150, 30, 30), 8)
    c.line([(640, 1170 + dy), (690, 1170 + dy)], (150, 30, 30), 8)
    c.ellipse(905, 1150 + dy, 945, 1190 + dy, fill=(255, 240, 160))
    c.rect(122, 1240 + dy, 160, 1270 + dy, fill=(255, 120, 90), r=8)
    for wx in (300, 780):
        c.circle(wx, 1330, 72, fill=(40, 40, 45))
        c.circle(wx, 1330, 32, fill=(200, 200, 205))
        for k in range(3):
            a = math.radians(k * 120 + t * 720)
            c.line([(wx, 1330), (wx + 30 * math.cos(a), 1330 + 30 * math.sin(a))], (90, 90, 95), 7)
    # speed lines
    for i in range(3):
        y = 1180 + i * 50
        x = 60 - ((t * 900 + i * 90) % 160)
        c.line([(x, y), (x + 60, y)], WHITE, 6)
    header(c)


def scene_dun(c, t):
    c.fill((18, 18, 26))
    if t > 14.2:
        c.circle(540, 980, 380 + (t - 14.2) * 60, fill=(40, 20, 30))
    caption(c, t, 13.15, 'THE', y=700, sz=120)
    caption(c, t, 13.65, 'FOOD AT', y=870, sz=140)
    caption(c, t, 14.15, 'HOME...', y=1060, sz=190, col=(255, 70, 70))


def kitchen_bg(c, wall=(250, 236, 200)):
    c.fill(wall)
    c.rect(0, 1450, W, H, fill=(205, 160, 110))
    for i in range(6):
        c.line([(i * 200 - 40, 1450), (i * 260 - 300, H)], (185, 140, 95), 4)
    c.line([(0, 1600), (W, 1600)], (185, 140, 95), 4)


def scene_fridge(c, t):
    kitchen_bg(c)
    # wall decor
    c.rect(90, 520, 430, 800, fill=(170, 215, 250), outline=(140, 100, 70), w=12)
    c.line([(260, 520), (260, 800)], (140, 100, 70), 8)
    c.circle(250, 400, 55, fill=WHITE, outline=INK, w=6)
    c.line([(250, 400), (250, 365)], INK, 5); c.line([(250, 400), (275, 410)], INK, 5)
    p = ease(prog(t, 18.0, 18.5)) * (1 - prog(t, 25.15, 25.35))
    # floor glow
    if p > 0:
        c.ellipse(330, 1430, 880, 1520, fill=lerpc((205, 160, 110), (245, 215, 150), p))
    # fridge body
    c.rect(600, 760, 900, 1450, fill=(240, 242, 246), outline=(60, 60, 72), w=7, r=18)
    c.line([(600, 965), (900, 965)], (60, 60, 72), 6)
    c.line([(625, 820), (625, 920)], (150, 150, 160), 10)
    c.rect(680, 790, 820, 930, fill=(255, 250, 230), outline=(200, 190, 150), w=3)
    c.text(750, 860, 'NO\nSNACKS\n-MOM', 24, (200, 40, 40))
    shake = 0
    if 21.8 < t < 24.3:
        shake = math.sin(t * 70) * 8 * prog(t, 21.8, 24.2)
    lid = ease(prog(t, 24.3, 24.45)) * (1 - prog(t, 25.0, 25.15))
    if p > 0.02:
        c.rect(614, 975, 886, 1438, fill=(255, 250, 215))
        c.line([(614, 1130), (886, 1130)], (200, 200, 190), 6)
        c.line([(614, 1290), (886, 1290)], (200, 200, 190), 6)
        c.ellipse(718, 1060, 772, 1128, fill=WHITE, outline=INK, w=4)  # the egg
        c.rect(650, 1185, 690, 1288, fill=(240, 240, 240), outline=INK, w=4, r=10)  # ketchup
        c.rect(653, 1255, 687, 1286, fill=(210, 30, 30), r=8)
        c.rect(660, 1170, 680, 1188, fill=(210, 30, 30))
        c.text(810, 1250, '?', 40, (180, 180, 170))
        # mystery container
        bx = 760 + shake
        c.rect(bx - 85, 1345, bx + 85, 1430, fill=(90, 140, 220), outline=INK, w=4, r=8)
        if lid > 0:
            c.rect(bx - 80, 1340 - 40 * lid, bx + 80, 1348, fill=(10, 10, 12))
            for ex in (-24, 24):
                c.circle(bx + ex, 1325 - 14 * lid, 9 * lid, fill=(255, 230, 40))
                c.circle(bx + ex, 1325 - 14 * lid, 3 * lid, fill=(200, 20, 20))
        c.rect(bx - 92, 1330 - 46 * lid, bx + 92, 1350 - 46 * lid, fill=(60, 100, 180), outline=INK, w=4, r=6)
        c.rect(bx - 55, 1365, bx + 55, 1415, fill=(255, 250, 200))
        c.text(bx, 1390, 'DO NOT\nOPEN', 16, (200, 30, 30))
    # door
    sk = 45 * math.sin(math.pi * p)
    if p < 0.5:
        xl = 600 + 600 * p
        c.poly([(xl, 965 - sk), (900, 965), (900, 1450), (xl, 1450 + sk)], fill=(240, 242, 246), outline=(60, 60, 72), w=6)
        if xl < 860:
            c.line([(xl + 25, 1000), (xl + 25, 1150)], (150, 150, 160), 10)
    else:
        xr = 900 + 260 * (p - 0.5) * 2
        c.poly([(900, 965), (xr, 965 - sk), (xr, 1450 + sk), (900, 1450)], fill=(220, 222, 228), outline=(60, 60, 72), w=6)
    # kid
    g = 1450; s = 0.85
    if t < 18.0:
        x = lerp(140, 470, prog(t, 15.5, 18.0))
        legs, arms, b = walk_pose(t)
        stick(c, (x, g - 176 * s - b), s, legs=legs, arms=arms, face='happy', dr=1, who='kid')
    elif t < 25.6:
        face = 'sad' if t < 21.7 else ('scared' if t < 24.3 else 'shock')
        jump = 130 * math.sin(math.pi * prog(t, 24.3, 24.85))
        arms = ((30, 15), (-30, -15))
        if 24.3 <= t < 25.1:
            arms = ((160, 175), (-160, -175))
        elif 25.1 <= t < 25.6:
            arms = ((95, 90), (75, 90))
        x = 470 if t < 25.1 else lerp(470, 520, prog(t, 25.1, 25.3))
        stick(c, (x, g - 176 * s - jump), s, arms=arms, face=face, dr=1, who='kid', talk=talking('kid', t),
              look=-0.6 if 24.5 < t < 25.1 else 0)
    else:
        bump = 40 * math.sin(math.pi * prog(t, 26.8, 27.1))
        x = 560
        stick(c, (x, g - 176 * s - bump), s, arms=((-150, -160), (-40, -20)), face='shock', dr=-1, who='kid',
              legs=((14, 4), (-14, -4)))
        for i in range(3):
            ph = ((t * 1.4 + i * 0.33) % 1)
            sx_, sy_ = 470 + i * 30, 1060 + ph * 90
            c.poly([(sx_, sy_ - 18), (sx_ - 9, sy_), (sx_ + 9, sy_)], fill=(90, 170, 255))
            c.circle(sx_, sy_, 9, fill=(90, 170, 255))
        caption(c, t, 26.0, 'NOPE.', y=520, sz=150, col=(255, 230, 60))
    header(c)


def chair_pts(rotang, piv):
    segs = [[(840, 1330), (935, 1330)], [(935, 1330), (935, 1170)], [(845, 1330), (845, 1450)], [(930, 1330), (930, 1450)]]
    return [[rot_pt(p, piv, rotang) for p in sg] for sg in segs]


def scene_dinner(c, t):
    kitchen_bg(c, wall=(205, 232, 212))
    c.rect(560, 520, 900, 720, fill=(255, 255, 255), outline=(150, 110, 80), w=10)
    c.text(730, 620, 'HOME\nSWEET\nHOME', 34, (200, 80, 100))
    # stove + counter
    c.rect(50, 1150, 470, 1450, fill=(235, 235, 238), outline=INK, w=6)
    c.rect(90, 1220, 430, 1400, fill=(60, 60, 66), r=12)
    c.line([(130, 1240), (390, 1240)], (180, 180, 185), 10)
    for k in range(3):
        c.circle(150 + k * 50, 1180, 14, fill=(60, 60, 66))
    # pot
    c.rect(140, 1040, 340, 1150, fill=(75, 75, 85), outline=INK, w=6, r=10)
    c.line([(110, 1065), (140, 1065)], INK, 12); c.line([(340, 1065), (370, 1065)], INK, 12)
    c.ellipse(150, 1028, 330, 1056, fill=(130, 200, 60), outline=INK, w=4)
    rng = random.Random(int(t * 10) // 3)
    for i in range(9):
        ph = (t * 0.6 + i * 0.113) % 1
        bx = 170 + (i * 47) % 150 + math.sin(t * 2 + i) * 15
        by = 1030 - ph * 420
        rr = 18 + ph * 45
        c.circle(bx, by, rr, fill=lerpc((140, 210, 80), (205, 232, 212), ph))
    for i in range(4):
        ph = (t * 1.3 + i * 0.25) % 1
        c.circle(185 + i * 40, 1040 - ph * 20, 8 + ph * 6, fill=(150, 220, 70), outline=(90, 140, 40), w=2)
    # table + chair
    c.rect(600, 1250, 1040, 1276, fill=(150, 95, 55), r=6)
    c.line([(630, 1276), (630, 1450)], (120, 75, 45), 14)
    c.line([(1010, 1276), (1010, 1450)], (120, 75, 45), 14)
    fall = ease(prog(t, 46.3, 46.85))
    piv = (935, 1450)
    for sg in chair_pts(-80 * fall, piv):
        c.line(sg, (150, 95, 55), 12)
    # plate + blob
    px = lerp(560, 760, ease(prog(t, 32.8, 33.4)))
    if t >= 32.8:
        plate(c, px, 1240)
        bite = 0.8 if t > 44.4 else 1.0
        blink = 35.9 < t < 36.15 or 38.4 < t < 38.55
        look = 1 if t < 46.3 else -1
        blob(c, px, 1236, t, scale=0.9 * bite, blink=blink, look=look)
    # mom
    g = 1520; ms = 1.0
    mtalk = talking('mom', t)
    sway = math.sin(t * 5) * 5
    if t < 32.6:
        st_ = math.sin(t * 8)
        stick(c, (420, g - 176 * ms), ms, arms=((-110 + st_ * 12, -150 + st_ * 15), (-30, -15)), face='happy', dr=-1,
              who='mom', talk=mtalk, sway=sway)
        hd = vec(vec(vec((420, g - 176 * ms), 132 * ms, 180), 78 * ms, -110 + st_ * 12), 72 * ms, -150 + st_ * 15)
        c.line([hd, (240 + 30 * math.cos(t * 8), 1040 + 6 * math.sin(t * 8))], (150, 100, 60), 9)
    elif t < 33.8:
        stick(c, (420, g - 176 * ms), ms, arms=((80, 95), (-30, -15)), face='happy', dr=1, who='mom', sway=sway)
    elif 40.0 <= t < 43.8:
        stick(c, (420, g - 176 * ms), ms, arms=((100, 95), (-60, 60)), face='stern', dr=1, who='mom', talk=mtalk, sway=sway)
    else:
        face = 'happy' if t < 40 else ('neutral' if t < 46.9 else 'deadpan')
        stick(c, (420, g - 176 * ms), ms, arms=((60, -60), (-60, 60)), face=face, dr=1, who='mom', talk=mtalk, sway=sway)
    # kid
    ks = 0.85
    col = lerpc(INK, GREEN_SICK, prog(t, 45.3, 46.0))
    ktalk = talking('kid', t)
    if t < 46.3:
        hip = (880, 1320)
        face = 'neutral'
        arms = ((-60, -100), (-40, -80))
        if 33.4 < t < 36.0: face = 'deadpan'
        if 35.9 < t < 36.4: face = 'shock'
        if 36.4 <= t < 40: face = 'deadpan'
        if 40 <= t < 43.8: face = 'sad'
        spoon_end = None
        if 43.8 <= t < 46.3:
            face = 'scared' if t < 45.0 else ('shock' if t < 45.3 else 'sick')
            p1 = ease(prog(t, 43.8, 44.2)); p2 = ease(prog(t, 44.2, 44.8))
            if t < 44.2:
                ua, fa = lerp(-60, -70, p1), lerp(-100, -90, p1)
            else:
                ua, fa = lerp(-70, -20, p2), lerp(-90, -178, p2)
            arms = ((ua, fa), (-40, -80))
            spoon_end = 'mouth' if t >= 44.6 else 'plate'
        dx = math.sin(t * 50) * 4 if 45.3 < t < 46.3 else 0
        j = stick(c, (hip[0] + dx, hip[1]), ks, col=col, arms=arms, face=face, dr=-1, who='kid', talk=ktalk,
                  legs=((-90, 0), (-90, 0)), look=0.5 if face == 'deadpan' else 0)
        if spoon_end:
            hnd = j['hands'][0]
            end = (hnd[0] - 45, hnd[1] - 25) if spoon_end == 'mouth' else (hnd[0] - 40, hnd[1] + 5)
            c.line([hnd, end], (170, 170, 180), 7)
            c.ellipse(end[0] - 14, end[1] - 9, end[0] + 10, end[1] + 9, fill=(170, 170, 180))
    else:
        f2 = fall
        hip = rot_pt((880, 1320), piv, -80 * f2)
        twitch = math.sin(t * 20) * 8 if t > 47 else 0
        stick(c, hip, ks, col=col, rot=-85 * f2, arms=((-60, -100), (-40, -80)), face='dead' if t > 46.85 else 'sick',
              dr=-1, who='kid', legs=((-90 + twitch, 0), (-90, 0 - twitch)))
    if 46.85 < t < 47.4:
        c.ox = math.sin(t * 90) * 14
    # error box
    if t >= 47.3:
        sc = back(prog(t, 47.3, 47.5)) if t < 47.5 else 1
        cx, cy = 540, 700
        bw, bh = 820 * sc, 330 * sc
        c.rect(cx - bw / 2 + 10, cy - bh / 2 + 12, cx + bw / 2 + 10, cy + bh / 2 + 12, fill=(0, 0, 0), r=14)
        c.rect(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2, fill=(236, 236, 240), outline=(40, 40, 60), w=5, r=14)
        if sc > 0.9:
            c.rect(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy - bh / 2 + 64, fill=(30, 100, 210), r=14)
            c.text(cx - bw / 2 + 30, cy - bh / 2 + 32, 'Kid.exe', 36, WHITE, anchor='lm')
            c.circle(cx - 300, cy + 20, 50, fill=(220, 40, 40))
            c.text(cx - 300, cy + 20, 'X', 60, WHITE)
            c.text(cx - 220, cy + 0, 'Kid.exe has stopped', 46, INK, anchor='lm')
            c.text(cx - 220, cy + 56, 'working.', 46, INK, anchor='lm')
            c.rect(cx + 190, cy + 100, cx + 370, cy + 150, fill=WHITE, outline=(30, 100, 210), w=4, r=8)
            c.text(cx + 280, cy + 125, 'OK', 34, INK)
    header(c)


def scene_door(c, t):
    c.fill((215, 205, 240))
    c.rect(0, 1500, W, H, fill=(170, 125, 95))
    c.line([(0, 1505), (W, 1505)], (140, 100, 75), 6)
    c.rect(130, 520, 400, 760, fill=(255, 250, 240), outline=(130, 90, 70), w=10)
    c.circle(265, 640, 60, fill=(255, 200, 80))
    c.text(265, 640, 'MOM', 28, (120, 60, 30))
    # doorway
    op = ease(prog(t, 51.2, 51.6))
    c.rect(720, 900, 980, 1500, fill=(160, 215, 255))
    c.rect(720, 1380, 980, 1500, fill=(110, 190, 90))
    if t >= 51.2:
        bag_pos = (775, 1300)
        if t >= 54.2:
            bag_pos = (lerp(775, 470, ease(prog(t, 54.2, 54.5))), lerp(1300, 1340, ease(prog(t, 54.2, 54.5))))
        gd = 1500; gs = 1.0
        stick(c, (840, gd - 176 * gs), gs, arms=((-55, -80), (-30, -10)), face='happy', dr=-1, who='guy',
              talk=talking('guy', t))
        if t < 54.2:
            draw_bag(c, *bag_pos)
    if op < 1:
        xl = lerp(720, 950, op)
        c.poly([(xl, 900), (980, 900), (980, 1500), (xl, 1500)], fill=(150, 90, 50), outline=INK, w=5)
        if xl < 900:
            c.circle(xl + 30, 1220, 12, fill=(240, 200, 70))
    else:
        c.poly([(950, 900), (980, 900), (980, 1500), (950, 1500)], fill=(150, 90, 50), outline=INK, w=5)
    c.rect(700, 880, 1000, 1500, outline=(110, 70, 40), w=22)
    # couch (kid hides behind it)
    if t >= 54.6:
        kh = lerp(1640, 1330, ease(prog(t, 54.6, 54.85)))
        stick(c, (250, kh), 0.85, arms=((150, 170), (-150, -170)) if t < 56.1 else ((60, 160), (-60, -160)),
              face='mad_shock' if t < 56.1 else 'angry', dr=1, who='kid', talk=talking('kid', t))
    c.rect(40, 1240, 440, 1420, fill=(70, 110, 200), outline=INK, w=6, r=30)
    c.rect(40, 1360, 440, 1470, fill=(90, 135, 225), outline=INK, w=6, r=20)
    c.line([(80, 1470), (80, 1500)], INK, 12); c.line([(400, 1470), (400, 1500)], INK, 12)
    # mom
    g = 1520
    sway = math.sin(t * 5) * 5
    if t < 51.3:
        x = lerp(-120, 560, prog(t, 50.0, 51.3))
        legs, arms, b = walk_pose(t, speed=13)
        stick(c, (x, g - 176 - b), 1.0, legs=legs, arms=arms, face='happy', dr=1, who='mom', sway=sway)
    else:
        def bag_behind(sh):
            if t >= 54.2:
                bx, by = lerp(775, 470, ease(prog(t, 54.2, 54.5))), lerp(1300, 1340, ease(prog(t, 54.2, 54.5)))
                draw_bag(c, bx, by)
        face = 'happy' if t < 54.2 else 'sly'
        if t >= 56.1:
            arms = ((140, 200), (-30, -10))
        elif t >= 54.2:
            arms = ((40, 20), (-40, -15))
        else:
            arms = ((40, 20), (-30, -15))
        stick(c, (560, g - 176), 1.0, arms=arms, face=face, dr=1, who='mom', talk=talking('mom', t), sway=sway,
              behind=bag_behind)
    if 54.6 < t < 54.9:
        c.ox = math.sin(t * 120) * 12
    header(c)


def draw_bag(c, x, y):
    c.poly([(x - 55, y - 60), (x + 55, y - 60), (x + 62, y + 70), (x - 62, y + 70)], fill=(205, 160, 105), outline=INK, w=4)
    burger_icon(c, x, y - 8, 0.38)
    c.text(x, y + 48, 'YUM', 20, (200, 40, 40))


def scene_end(c, t):
    sunburst(c, t, (255, 205, 50), (255, 222, 110))
    caption(c, t, 58.65, 'TAG YOUR MOM', y=650, sz=120, col=(255, 70, 70))
    caption(c, t, 58.95, 'who says this', y=820, sz=64)
    caption(c, t, 59.2, 'FOLLOW FOR PART 2', y=1550, sz=70)
    stick(c, (540, 1400 - 176 * 1.2), 1.2, arms=((140, 170), (-140, -170)), face='sly', dr=1, who='mom',
          sway=math.sin(t * 6) * 6)
    draw_bag(c, 690, 1080)


SCENES = [(0, 3.5, scene_title), (3.5, 13.0, scene_car), (13.0, 15.5, scene_dun), (15.5, 28.0, scene_fridge),
          (28.0, 50.0, scene_dinner), (50.0, 58.6, scene_door), (58.6, 60.01, scene_end)]


def render(t):
    c = Cv()
    for a, b, fn in SCENES:
        if a <= t < b:
            # global camera shake on the fridge slam
            if 25.3 < t < 25.6:
                c.ox = math.sin(t * 110) * 16; c.oy = math.cos(t * 90) * 10
            fn(c, t)
            break
    c.ox = c.oy = 0
    for ln in LINES:
        bubble(c, t, ln)
    # fade in/out of black at scene edges
    img = c.out()
    for a, b, _ in SCENES:
        if 0 < a and abs(t - a) < 0.1:
            k = abs(t - a) / 0.1
            img = Image.blend(Image.new('RGB', img.size), img, k)
    return img


# ---------------------------------------------------------------- audio
SR = 44100
NS = int(SR * DUR)


def tt(d): return np.arange(int(d * SR)) / SR
def sine(f, d): return np.sin(2 * np.pi * f * tt(d))


def sweep(f0, f1, d, vib=0.0, vibf=0.0, sq=False):
    t = tt(d); f = np.linspace(f0, f1, len(t)) + vib * np.sin(2 * np.pi * vibf * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.tanh(3 * np.sin(ph)) if sq else np.sin(ph)


def noise(d, seed=None):
    r = np.random.default_rng(seed)
    return r.uniform(-1, 1, int(d * SR))


def lp(x, n): return np.convolve(x, np.ones(n) / n, mode='same')


def env(d, a=0.005, k=6.0):
    t = tt(d); e = np.exp(-t * k)
    na = max(1, int(a * SR)); e[:na] *= np.linspace(0, 1, na)
    return e


def mtof(m): return 440 * 2 ** ((m - 69) / 12)


def build_audio(path):
    A = np.zeros(NS)

    def add(t, sig, vol=1.0):
        i = int(t * SR)
        if i >= NS or i < 0:
            return
        j = min(NS, i + len(sig)); A[i:j] += sig[:j - i] * vol

    def pluck(f, d=0.45, k=7):
        t = tt(d)
        return (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(4 * np.pi * f * t) + 0.2 * np.sin(6 * np.pi * f * t)) * env(d, 0.003, k)

    def bell(f, d=1.2):
        t = tt(d)
        return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * 2.01 * f * t) + 0.2 * np.sin(2 * np.pi * 3.02 * f * t)) * env(d, 0.002, 3.5)

    def thump(d=0.35, f=55, nz=0.6):
        return (np.sin(2 * np.pi * f * tt(d)) * env(d, 0.002, 9) + lp(noise(d, 1), 6) * env(d, 0.001, 28) * nz)

    # music: bouncy C - Am - F - G loop, 120 bpm
    M = np.zeros(NS)
    chords = [(48, [0, 4, 7, 12]), (45, [0, 3, 7, 12]), (41, [0, 4, 7, 12]), (43, [0, 4, 7, 12])]
    patt = [0, 1, 2, 3, 2, 1, 2, 1]
    bar = 0; tb = 0.0
    while tb < DUR:
        root, iv = chords[bar % 4]
        for i, pi in enumerate(patt):
            s = pluck(mtof(root + 12 + iv[pi]), 0.4)
            i0 = int((tb + i * 0.25) * SR); j0 = min(NS, i0 + len(s))
            if i0 < NS: M[i0:j0] += s[:j0 - i0] * 0.55
        for bt in (0, 1.0):
            s = (np.sin(2 * np.pi * mtof(root - 12) * tt(0.5)) + 0.3 * np.sin(4 * np.pi * mtof(root - 12) * tt(0.5))) * env(0.5, 0.005, 4)
            i0 = int((tb + bt) * SR); j0 = min(NS, i0 + len(s))
            if i0 < NS: M[i0:j0] += s[:j0 - i0] * 0.9
        for bt in (0.5, 1.5):
            s = np.diff(noise(0.08, bar), prepend=0) * env(0.08, 0.001, 40)
            i0 = int((tb + bt) * SR); j0 = min(NS, i0 + len(s))
            if i0 < NS: M[i0:j0] += s[:j0 - i0] * 0.35
        bar += 1; tb += 2.0
    tl = np.arange(NS) / SR
    mv = np.ones(NS)
    mv[(tl >= 13.0) & (tl < 15.6)] = 0.0
    mv[(tl >= 22.0) & (tl < 26.0)] = 0.35
    mv[(tl >= 45.0) & (tl < 50.0)] = 0.0
    mv[(tl >= 54.6) & (tl < 56.0)] = 0.0
    mv[tl >= 58.6] = 0.0
    mv = lp(mv, int(0.05 * SR))
    A += M * mv * 0.16

    # dialogue gibberish blips
    base = {'kid': 640, 'mom': 400, 'guy': 230}
    rng = random.Random(3)
    for ln in LINES:
        st, en, who, txt, _, _ = ln
        dur = len(txt) / type_rate(ln)
        n = int(dur / 0.075)
        for k in range(n):
            ch = txt[min(len(txt) - 1, int(k * 0.075 * type_rate(ln)))]
            if ch in ' .!?,':
                continue
            f = base[who] * 2 ** (rng.choice([-2, 0, 2, 3, 5, 7]) / 12)
            if txt.isupper() or ch.isupper():
                f *= 1.12
            add(st + k * 0.075, sweep(f, f * 0.92, 0.065, sq=True) * env(0.065, 0.004, 25), 0.16)

    # SFX
    pop = sweep(380, 1100, 0.07) * env(0.07, 0.002, 30)
    for tp in (0.25, 0.85, 26.0, 58.65, 58.95, 59.2):
        add(tp, pop, 0.35)
    # engine
    d = 9.5
    eng = lp(noise(d, 2), 60) * 6 + 0.5 * np.sin(2 * np.pi * 52 * tt(d)) * (1 + 0.3 * np.sin(2 * np.pi * 9 * tt(d)))
    fade = np.minimum(1, np.minimum(tt(d) / 0.3, (d - tt(d)) / 0.3))
    add(3.5, eng * fade, 0.12)
    add(3.5, sweep(80, 160, 0.8, sq=True) * env(0.8, 0.05, 2), 0.08)
    # dun dun DUUN
    for tp, f, dd in ((13.15, 110, 0.45), (13.65, 104, 0.45), (14.15, 92.5, 1.3)):
        t = tt(dd); saw = 2 * ((f * t) % 1) - 1; saw2 = 2 * ((f * 1.5 * t) % 1) - 1
        add(tp, lp(saw + 0.6 * saw2 + 0.8 * np.sin(np.pi * f * t), 8) * env(dd, 0.01, 1.6), 0.4)
    # fridge creak + hum
    add(18.0, lp(np.sign(np.sin(2 * np.pi * np.cumsum(240 + 70 * np.sin(2 * np.pi * 9 * tt(0.55)) + 40 * noise(0.55, 4)) / SR)), 6) * env(0.55, 0.02, 2), 0.1)
    add(18.5, np.sin(2 * np.pi * 60 * tt(6.6)) * 0.5, 0.06)
    # growl
    d = 3.2; t = tt(d)
    gr = lp(noise(d, 5), 30) * 5 * (0.55 + 0.45 * np.sin(2 * np.pi * 23 * t))
    gr += 0.4 * lp(2 * ((68 * t) % 1) - 1, 10)
    gr *= np.clip(t / 2.3, 0, 1) ** 2 * (t < 2.4) + (t >= 2.4) * 1.6 * np.exp(-(t - 2.4) * 3)
    add(21.9, gr, 0.35)
    # boing jump
    add(24.3, sweep(140, 700, 0.45, vib=60, vibf=28) * env(0.45, 0.005, 5), 0.25)
    # slam + thump
    add(25.28, thump(0.45, 50, 0.9), 0.75)
    add(26.8, thump(0.3, 70, 0.4), 0.45)
    # bubbling pot
    r2 = random.Random(9)
    tp = 28.0
    while tp < 50:
        f0 = r2.uniform(180, 380)
        add(tp, sweep(f0, f0 * 2.6, 0.045) * env(0.045, 0.002, 40), 0.07)
        tp += r2.uniform(0.08, 0.3)
    # whoosh plate slide
    d = 0.6; wn = np.diff(noise(d, 11), prepend=0)
    add(32.75, wn * np.hanning(len(wn)), 0.25)
    add(33.4, sweep(1200, 1000, 0.08) * env(0.08, 0.001, 30), 0.15)
    # blink bloops
    for tp in (35.9, 38.4):
        add(tp, sweep(300, 950, 0.09) * env(0.09, 0.002, 18), 0.3)
    # gulp
    for tp in (45.0, 45.18):
        add(tp, sweep(520, 160, 0.16) * env(0.16, 0.002, 10), 0.35)
    # sick wobble
    d = 1.0; t = tt(d)
    f = 320 - 140 * t + 30 * np.sin(2 * np.pi * 7 * t)
    add(45.3, np.tanh(2 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.minimum(1, (d - t) * 5), 0.12)
    # slide whistle down + thud
    add(46.3, sweep(1500, 260, 0.55) * np.minimum(1, (0.55 - tt(0.55)) * 20), 0.15)
    add(46.85, thump(0.5, 45, 1.0), 0.8)
    # error tones
    add(47.3, (sine(523, 0.45) + sine(659, 0.45) * 0.7 + sine(784, 0.45) * 0.4) * env(0.45, 0.004, 5), 0.18)
    # doorbell
    add(50.0, bell(659, 1.0), 0.3)
    add(50.45, bell(523, 1.4), 0.3)
    # footsteps
    for k in range(5):
        add(50.1 + k * 0.24, thump(0.08, 120, 0.3), 0.12)
    # door creak
    add(51.2, lp(np.sign(np.sin(2 * np.pi * np.cumsum(300 + 90 * np.sin(2 * np.pi * 7 * tt(0.4))) / SR)), 6) * env(0.4, 0.01, 4), 0.08)
    # bag rustle
    add(54.2, lp(noise(0.3, 13), 3) * env(0.3, 0.01, 8), 0.2)
    # record scratch
    d = 0.5; t = tt(d)
    f = 700 + 600 * np.sin(2 * np.pi * 5 * t)
    sc = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.4 + lp(noise(d, 15), 2) * 0.6
    add(54.6, lp(sc, 4) * env(d, 0.002, 4), 0.35)
    # end stinger
    for i, m in enumerate((60, 64, 67, 72)):
        add(58.65 + i * 0.09, pluck(mtof(m), 1.0, 3), 0.25)
    for m in (60, 64, 67, 72, 76):
        add(59.05, pluck(mtof(m), 1.0, 2.5), 0.15)

    A = A / (np.max(np.abs(A)) + 1e-9) * 0.9
    fo = int(0.4 * SR); A[-fo:] *= np.linspace(1, 0, fo)
    data = (A * 32767).astype(np.int16)
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR); wf.writeframes(data.tobytes())


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--stills':
        out = sys.argv[2]; os.makedirs(out, exist_ok=True)
        for ts in sys.argv[3:]:
            render(float(ts)).save(os.path.join(out, f't{float(ts):05.1f}.png'))
        return
    out = sys.argv[1] if len(sys.argv) > 1 else 'food_at_home.mp4'
    wav = out.rsplit('.', 1)[0] + '.wav'
    build_audio(wav)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-i', wav, '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', out]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nf = int(DUR * FPS)
    for i in range(nf):
        pr.stdin.write(render(i / FPS).tobytes())
        if i % 150 == 0:
            print(f'frame {i}/{nf}', flush=True)
    pr.stdin.close(); pr.wait()
    os.remove(wav)
    print('done', out)


if __name__ == '__main__':
    main()
