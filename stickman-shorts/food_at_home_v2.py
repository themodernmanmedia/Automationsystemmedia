"""v2: 'When your mom says "We have food at home"' in the big-head stick figure reel style.

Illustrated backgrounds (bg/*.png), ElevenLabs voice lines (voices/*.wav), characters/props/captions
drawn with Pillow, SFX + music synthesized with numpy, muxed with ffmpeg.
Usage: python3 food_at_home_v2.py [out.mp4]   |   python3 food_at_home_v2.py --stills DIR t1 t2 ...
"""
import math, os, random, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, K, FPS, DUR = 1080, 1920, 2, 30, 60.0
F_BLACK = '/usr/share/fonts/opentype/inter/Inter-Black.otf'
F_XB = '/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf'
F_EMOJI = '/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf'
_fc = {}


def font(path, sz):
    key = (path, int(sz))
    if key not in _fc:
        _fc[key] = ImageFont.truetype(path, max(4, int(sz)))
    return _fc[key]


def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(t, a, b): return clamp((t - a) / (b - a))
def ease(p): return p * p * (3 - 2 * p)
def lerp(a, b, p): return a + (b - a) * p
def lerpc(c1, c2, p): return tuple(int(lerp(a, b, p)) for a, b in zip(c1, c2))
def lerpp(p1, p2, p): return (lerp(p1[0], p2[0], p), lerp(p1[1], p2[1], p))


def back(p):
    c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def vec(p, L, ang):
    r = math.radians(ang)
    return (p[0] + L * math.sin(r), p[1] + L * math.cos(r))


def angle_to(a, b): return math.degrees(math.atan2(b[0] - a[0], b[1] - a[1]))


def ik(sh, tgt, L1, L2, bend=1):
    d = math.dist(sh, tgt); d = clamp(d, 1e-3, L1 + L2 - 1e-3)
    a = angle_to(sh, tgt)
    off = math.degrees(math.acos(clamp((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d), -1, 1)))
    el = vec(sh, L1, a + bend * off)
    return el, vec(el, L2, angle_to(el, tgt))


# ------------------------------------------------------------------ drawing context
class Cv:
    """2x supersampled RGBA layer. World coords go through the camera; ui() switches to screen coords."""

    def __init__(s, cam):
        s.img = Image.new('RGBA', (W * K, H * K), (0, 0, 0, 0)); s.d = ImageDraw.Draw(s.img)
        s.cam = cam

    def ui(s): s.cam = (W / 2, H / 2, 1.0)

    def P(s, x, y):
        cx, cy, z = s.cam
        return (((x - cx) * z + W / 2) * K, ((y - cy) * z + H / 2) * K)

    def S(s, v): return v * s.cam[2] * K

    def line(s, pts, col, w):
        q = [s.P(*p) for p in pts]; ww = max(1, int(s.S(w)))
        s.d.line(q, fill=col, width=ww, joint='curve')
        r = ww / 2
        for x, y in (q[0], q[-1]):
            s.d.ellipse([x - r, y - r, x + r, y + r], fill=col)

    def circle(s, x, y, r, fill=None, outline=None, w=0):
        X, Y = s.P(x, y); R = s.S(r)
        s.d.ellipse([X - R, Y - R, X + R, Y + R], fill=fill, outline=outline, width=int(s.S(w)))

    def ell(s, x, y, rx, ry, fill=None, outline=None, w=0):
        X, Y = s.P(x, y); a, b = s.S(rx), s.S(ry)
        s.d.ellipse([X - a, Y - b, X + a, Y + b], fill=fill, outline=outline, width=int(s.S(w)))

    def rect(s, x0, y0, x1, y1, fill=None, outline=None, w=0, r=0):
        a = s.P(x0, y0); b = s.P(x1, y1)
        s.d.rounded_rectangle([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])],
                              radius=s.S(r), fill=fill, outline=outline, width=int(s.S(w)))

    def poly(s, pts, fill=None, outline=None, w=0):
        s.d.polygon([s.P(*p) for p in pts], fill=fill, outline=outline, width=int(s.S(w)))

    def arc(s, x, y, rx, ry, a0, a1, col, w):
        X, Y = s.P(x, y); a, b = s.S(rx), s.S(ry)
        s.d.arc([X - a, Y - b, X + a, Y + b], a0, a1, fill=col, width=max(1, int(s.S(w))))

    def chord(s, x, y, rx, ry, a0, a1, fill, outline=None, w=0):
        X, Y = s.P(x, y); a, b = s.S(rx), s.S(ry)
        s.d.chord([X - a, Y - b, X + a, Y + b], a0, a1, fill=fill, outline=outline, width=int(s.S(w)))

    def out(s): return s.img.reduce(K)


INK = (22, 22, 26)
WHITE = (255, 255, 255)
HEAD = (218, 218, 222)
HEAD_SH = (184, 184, 192)
MOUTH = (80, 18, 28)
TONGUE = (235, 110, 130)


# ------------------------------------------------------------------ characters
def face(c, hc, R, expr, dr, look, talk, blink, col):
    lx, ly = look
    ox = dr * 0.13 * R + lx * 0.1 * R
    ey = hc[1] - 0.06 * R + ly * 0.06 * R
    eyes = [(hc[0] - 0.29 * R + ox, ey), (hc[0] + 0.29 * R + ox, ey)]
    big = expr in ('shock', 'scared', 'mad_shock')
    # eyes
    for i, (x, y) in enumerate(eyes):
        if expr == 'dead':
            d = 0.12 * R
            c.line([(x - d, y - d), (x + d, y + d)], col, 0.06 * R); c.line([(x - d, y + d), (x + d, y - d)], col, 0.06 * R)
        elif blink:
            c.arc(x, y, 0.12 * R, 0.06 * R, 10, 170, col, 0.05 * R)
        elif big:
            c.ell(x, y, 0.16 * R, 0.21 * R, fill=WHITE, outline=col, w=0.04 * R)
            c.circle(x + lx * 0.05 * R + dr * 0.03 * R, y + ly * 0.05 * R, 0.065 * R, fill=col)
        else:
            c.ell(x, y, 0.105 * R, 0.19 * R, fill=col)
            c.circle(x - 0.035 * R, y - 0.08 * R, 0.035 * R, fill=WHITE)
            if expr in ('deadpan', 'sly', 'sick', 'unimpressed'):
                c.chord(x, y, 0.15 * R, 0.24 * R, 180, 360, HEAD)
                c.line([(x - 0.15 * R, y), (x + 0.15 * R, y)], col, 0.045 * R)
    # brows
    bw = 0.055 * R
    for i, (x, y) in enumerate(eyes):
        side = -1 if i == 0 else 1  # -1 left eye, +1 right eye
        by = y - 0.32 * R
        if expr in ('angry', 'stern', 'mad_shock'):
            c.line([(x - 0.14 * R, by + side * 0.07 * R), (x + 0.14 * R, by - side * 0.07 * R)], col, bw)
        elif expr in ('sad', 'scared', 'worried'):
            c.line([(x - 0.14 * R, by - side * 0.06 * R), (x + 0.14 * R, by + side * 0.06 * R)], col, bw)
        elif expr in ('shock', 'excited'):
            c.arc(x, by - 0.06 * R, 0.14 * R, 0.07 * R, 200, 340, col, bw)
        elif expr == 'sly':
            lift = 0.08 * R if side == dr else 0
            c.line([(x - 0.14 * R, by - lift), (x + 0.14 * R, by - lift - 0.02 * R)], col, bw)
        elif expr in ('deadpan', 'unimpressed', 'sick'):
            c.line([(x - 0.13 * R, by + 0.05 * R), (x + 0.13 * R, by + 0.05 * R)], col, bw)
        else:
            c.arc(x, by, 0.13 * R, 0.05 * R, 200, 340, col, bw)
    # mouth
    mx, my = hc[0] + ox * 0.9, hc[1] + 0.4 * R
    if talk > 0.08 and expr != 'dead':
        h = R * (0.05 + 0.17 * talk); w = R * (0.17 + 0.05 * talk)
        c.ell(mx, my, w, h, fill=MOUTH, outline=col, w=0.04 * R)
        if h > 0.09 * R:
            c.chord(mx, my + 0.01 * R, w * 0.8, h * 0.85, 25, 155, TONGUE)
            c.chord(mx, my, w * 0.92, h * 0.92, 200, 340, WHITE)
        return
    if expr in ('happy',):
        c.arc(mx, my - 0.1 * R, 0.22 * R, 0.14 * R, 20, 160, col, 0.05 * R)
    elif expr in ('excited', 'grin'):
        c.chord(mx, my - 0.08 * R, 0.24 * R, 0.2 * R, 0, 180, MOUTH, outline=col, w=0.04 * R)
        c.chord(mx, my - 0.08 * R, 0.2 * R, 0.08 * R, 0, 180, WHITE)
    elif expr in ('sad', 'worried'):
        c.arc(mx, my + 0.08 * R, 0.17 * R, 0.1 * R, 200, 340, col, 0.05 * R)
    elif expr in ('scared', 'angry'):
        c.rect(mx - 0.22 * R, my - 0.08 * R, mx + 0.22 * R, my + 0.08 * R, fill=WHITE, outline=col, w=0.04 * R, r=0.07 * R)
        c.line([(mx - 0.2 * R, my), (mx + 0.2 * R, my)], col, 0.025 * R)
        for k in (-0.1, 0, 0.1):
            c.line([(mx + k * R, my - 0.07 * R), (mx + k * R, my + 0.07 * R)], col, 0.02 * R)
    elif expr in ('shock', 'mad_shock'):
        c.ell(mx, my + 0.02 * R, 0.1 * R, 0.14 * R, fill=MOUTH, outline=col, w=0.04 * R)
    elif expr == 'sick':
        pts = [(mx - 0.22 * R + i * 0.073 * R, my + (0.04 * R if i % 2 else -0.04 * R)) for i in range(7)]
        c.line(pts, col, 0.04 * R)
    elif expr == 'sly':
        c.arc(mx + dr * 0.06 * R, my - 0.12 * R, 0.2 * R, 0.13 * R, 15 if dr > 0 else 70, 110 if dr > 0 else 165, col, 0.05 * R)
    elif expr == 'dead':
        c.line([(mx - 0.18 * R, my), (mx + 0.18 * R, my)], col, 0.05 * R)
        c.ell(mx + 0.06 * R, my + 0.1 * R, 0.08 * R, 0.11 * R, fill=TONGUE, outline=col, w=0.03 * R)
    elif expr == 'chew':
        c.ell(mx, my, 0.16 * R, 0.05 * R, fill=col)
    else:
        c.line([(mx - 0.13 * R, my), (mx + 0.13 * R, my)], col, 0.05 * R)


def char(c, kind, hip, R, dr=1, arms=((25, 10), (-25, -10)), legs=None, torso=180, rot=0, expr='neutral',
         look=(0, 0), talk=0.0, blink=False, sit=False, col=INK, head=HEAD, head_sh=HEAD_SH, hold=None):
    """Big-head stick figure. Angles: 0=down, 90=right, 180=up, -90=left.
    arms entries: (upper, fore) angles or ('ik', target, bend)."""
    lw = 0.1 * R
    t = torso + rot
    neck = vec(hip, 1.4 * R, t)
    sh = vec(neck, 0.13 * R, t + 180)
    hc = vec(neck, 0.9 * R, t)
    if legs is None:
        legs = ((dr * 90, 0), (dr * 90, 0)) if sit else ((7, 0), (-7, 0))
    perp = t + 90
    # legs + feet
    for th, sn in legs:
        k = vec(hip, 1.3 * R, th + rot); f = vec(k, 1.25 * R, sn + rot)
        c.line([hip, k, f], col, lw)
        c.line([f, vec(f, 0.26 * R, dr * 90 + rot)], col, lw * 1.25)
    # clothing
    def tp(base, along, side):
        p = vec(base, along, t); return vec(p, side, perp)
    if kind == 'mom':
        dress = [tp(neck, 0.05 * R, 0.3 * R), tp(neck, 0.05 * R, -0.3 * R), tp(hip, -0.9 * R, -0.75 * R), tp(hip, -0.9 * R, 0.75 * R)]
        c.poly(dress, fill=(150, 85, 185), outline=col, w=0.045 * R)
        c.line([tp(hip, 0.25 * R, -0.42 * R), tp(hip, 0.25 * R, 0.42 * R)], (110, 55, 140), 0.06 * R)
    elif kind in ('kid', 'guy'):
        shirt_col = (70, 170, 105) if kind == 'kid' else (245, 190, 45)
        shirt = [tp(neck, 0.02 * R, 0.33 * R), tp(neck, 0.02 * R, -0.33 * R), tp(hip, -0.05 * R, -0.4 * R), tp(hip, -0.05 * R, 0.4 * R)]
        c.poly(shirt, fill=shirt_col, outline=col, w=0.045 * R)
        if kind == 'guy':
            c.circle(*tp(neck, 0.55 * R, dr * 0.12 * R), 0.12 * R, fill=(220, 50, 40))
    c.line([hip, neck], col, lw * 0.8)
    # arms
    hands = []
    for a in arms:
        if a[0] == 'ik':
            el, hd = ik(sh, a[1], 0.85 * R, 0.8 * R, a[2])
        else:
            el = vec(sh, 0.85 * R, a[0] + rot); hd = vec(el, 0.8 * R, a[1] + rot)
        c.line([sh, el, hd], col, lw)
        hands.append(hd)
    if hold:
        hold(hands)
    for hd in hands:
        c.circle(hd[0], hd[1], 0.15 * R, fill=col)
    # hair behind head
    if kind == 'mom':
        c.circle(hc[0] - dr * 0.28 * R, hc[1] - 0.82 * R, 0.62 * R, fill=(45, 34, 34), outline=col, w=0.05 * R)
    # head with shading
    c.circle(hc[0], hc[1], R, fill=head_sh)
    c.circle(hc[0] - 0.09 * R, hc[1] - 0.09 * R, 0.9 * R, fill=head)
    c.circle(hc[0], hc[1], R, outline=col, w=0.075 * R)
    if kind == 'mom':
        c.chord(hc[0], hc[1], R * 0.97, R * 0.97, 198, 342, (45, 34, 34))
        c.arc(hc[0], hc[1], R * 0.86, R * 0.86, 205, 335, (150, 85, 185), 0.13 * R)
        for sx in (-1, 1):
            c.circle(hc[0] + sx * 0.97 * R, hc[1] + 0.32 * R, 0.13 * R, outline=(230, 180, 40), w=0.045 * R)
    elif kind == 'kid':
        cap = (215, 50, 50)
        c.chord(hc[0], hc[1] - 0.08 * R, R * 1.0, R * 0.98, 186, 354, cap, outline=col, w=0.05 * R)
        c.line([(hc[0] - dr * 0.75 * R, hc[1] - 0.5 * R), (hc[0] - dr * 1.25 * R, hc[1] - 0.42 * R)], cap, 0.16 * R)
    elif kind == 'guy':
        cap = (40, 90, 200)
        c.chord(hc[0], hc[1] - 0.1 * R, R * 1.0, R * 0.95, 186, 354, cap, outline=col, w=0.05 * R)
        c.line([(hc[0] + dr * 0.4 * R, hc[1] - 0.48 * R), (hc[0] + dr * 1.3 * R, hc[1] - 0.42 * R)], cap, 0.16 * R)
        c.chord(hc[0] + dr * 0.13 * R, hc[1] + 0.3 * R, 0.25 * R, 0.12 * R, 180, 360, (60, 40, 30))
    face(c, hc, R, expr, dr, look, talk, blink, col)
    return {'hands': hands, 'head': hc, 'R': R, 'neck': neck, 'sh': sh}


def walk(t, dr=1, speed=9, a=24):
    ph = math.sin(t * speed)
    legs = ((dr * a * ph, dr * (a * ph - 18)), (-dr * a * ph, dr * (-a * ph - 18)))
    arms = ((-dr * a * ph + 8, -dr * a * ph + 30), (dr * a * ph - 8, dr * a * ph - 30))
    return legs, arms, abs(ph) * 5


# ------------------------------------------------------------------ props
def burger(c, x, y, s):
    c.chord(x, y, 0.62 * s, 0.5 * s, 180, 360, (235, 160, 60), outline=INK, w=0.05 * s)
    for i in range(4):
        c.ell(x - 0.3 * s + i * 0.2 * s, y - 0.25 * s - (i % 2) * 0.08 * s, 0.04 * s, 0.02 * s, fill=(255, 240, 200))
    c.line([(x - 0.62 * s, y + 0.06 * s), (x + 0.62 * s, y + 0.06 * s)], (90, 190, 60), 0.1 * s)
    c.rect(x - 0.58 * s, y + 0.1 * s, x + 0.58 * s, y + 0.3 * s, fill=(110, 60, 30), outline=INK, w=0.04 * s, r=0.08 * s)
    c.line([(x - 0.55 * s, y + 0.34 * s), (x + 0.55 * s, y + 0.34 * s)], (250, 200, 40), 0.07 * s)
    c.rect(x - 0.6 * s, y + 0.37 * s, x + 0.6 * s, y + 0.55 * s, fill=(235, 160, 60), outline=INK, w=0.04 * s, r=0.08 * s)


def bag(c, x, y, s=60):
    c.poly([(x - 0.5 * s, y - 0.55 * s), (x + 0.5 * s, y - 0.55 * s), (x + 0.58 * s, y + 0.65 * s), (x - 0.58 * s, y + 0.65 * s)],
           fill=(205, 160, 105), outline=INK, w=0.05 * s)
    c.line([(x - 0.5 * s, y - 0.55 * s), (x - 0.42 * s, y - 0.42 * s), (x + 0.42 * s, y - 0.42 * s), (x + 0.5 * s, y - 0.55 * s)], INK, 0.03 * s)
    burger(c, x, y + 0.05 * s, 0.45 * s)


def blob(c, x, y, t, s=1.0, blink=False, look=0, bite=False):
    jig = 1 + 0.07 * math.sin(t * 9)
    pts = []
    for i in range(26):
        a = math.pi + i * math.pi / 25
        rr = 48 * s * (1 + 0.13 * math.sin(i * 2.7 + t * 4))
        pts.append((x + rr * math.cos(a) * 1.3, y + rr * math.sin(a) * jig))
    if bite:
        pts = [p for p in pts if not (p[0] > x + 20 * s and p[1] < y - 25 * s)] + []
    c.poly(pts, fill=(140, 165, 90), outline=INK, w=4)
    for k in range(4):
        c.circle(x - 28 * s + k * 19 * s, y - 16 * s - (k % 2) * 12 * s, 5 * s, fill=(110, 135, 65))
    ey = y - 33 * s * jig
    for dx in (-14, 14):
        ex = x + dx * s
        if blink:
            c.line([(ex - 9 * s, ey), (ex + 9 * s, ey)], INK, 3)
        else:
            c.circle(ex, ey, 10 * s, fill=WHITE, outline=INK, w=2.5)
            c.circle(ex + look * 4 * s, ey, 4.5 * s, fill=INK)


def plate(c, x, y, s=1.0):
    c.ell(x, y, 75 * s, 12 * s, fill=(248, 248, 248), outline=INK, w=3.5)
    c.ell(x, y - 1, 52 * s, 7 * s, outline=(200, 200, 205), w=2)


def sweat(c, x, y, t, s=1.0, n=3):
    for i in range(n):
        ph = (t * 1.3 + i / n) % 1
        px, py = x + i * 22 * s, y + ph * 70 * s
        c.poly([(px, py - 14 * s), (px - 7 * s, py), (px + 7 * s, py)], fill=(110, 185, 255))
        c.circle(px, py, 7 * s, fill=(110, 185, 255))


# ------------------------------------------------------------------ assets: backgrounds + voices
BG = {n: Image.open(os.path.join(HERE, 'bg', n + '.png')).convert('RGB') for n in ('car', 'fridge', 'dining', 'living')}


def couch_overlay():
    """Pixels of the couch in the living-room plate, so the kid can pop up from behind it."""
    a = np.asarray(BG['living']).astype(int)
    m = np.zeros(a.shape[:2], bool)
    x0, y0, x1, y1 = 70, 250, 775, 535
    sub = a[y0:y1, x0:x1]
    blue = (sub[..., 2] > sub[..., 0] + 25) & (sub[..., 2] > sub[..., 1] + 5)
    filled = np.zeros_like(blue)
    for j in range(blue.shape[1]):
        idx = np.where(blue[:, j])[0]
        if len(idx):
            filled[idx[0]:, j] = True
    m[y0:y1, x0:x1] = filled
    rgba = np.dstack([a.astype(np.uint8), (m * 255).astype(np.uint8)])
    return Image.fromarray(rgba, 'RGBA')


COUCH = couch_overlay()

VO = [  # file, start, speaker, caption text
    ('01_kid_burgers', 0.35, 'kid', 'Mom! Mom! Can we PLEASE get burgers?!'),
    ('02_mom_food_at_home', 4.55, 'mom', 'No. We have food at home.'),
    ('03_kid_one_egg', 14.9, 'kid', 'One egg. We have ONE egg.'),
    ('04_kid_moving', 19.6, 'kid', 'Uh... why is the container moving?'),
    ('05_kid_nope', 23.6, 'kid', 'Nope. Nope. Nope.'),
    ('06_mom_leftover', 27.0, 'mom', "Tonight I'm making my famous... Leftover Surprise!"),
    ('07_kid_blinked', 34.9, 'kid', 'Mom. It blinked.'),
    ('08_mom_eat_it', 37.75, 'mom', 'Eat it! Kids out there would LOVE this.'),
    ('09_guy_combo', 49.6, 'guy', 'Hi! One large burger combo... for Mom?'),
    ('10_kid_mom', 53.75, 'kid', 'MOM?!'),
    ('11_mom_my_food', 55.35, 'mom', 'What? This is MY food at home.'),
]
SR = 44100
CLIPS = {}
FR = 0.02


def load_wav(path):
    with wave.open(path) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64) / 32768
        if w.getnchannels() == 2:
            x = x.reshape(-1, 2).mean(1)
    return x


for f, st, who, txt in VO:
    wav_path = os.path.join(HERE, 'voices', f + '.wav')
    if not os.path.exists(wav_path):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', wav_path[:-4] + '.mp3', '-ac', '1', '-ar', str(SR), wav_path], check=True)
    x = load_wav(wav_path)
    n = int(FR * SR)
    env = np.array([np.sqrt(np.mean(x[i:i + n] ** 2)) for i in range(0, len(x) - n, n)])
    ref = np.percentile(env, 90) + 1e-6
    voiced = env > env.max() * 0.08
    # word timings: spread words over voiced frames, weighted by letter count
    words = txt.split()
    wts = np.array([len(w.strip('.,!?')) + 1.5 for w in words], float)
    cum = np.concatenate([[0], np.cumsum(wts)]) / wts.sum()
    vidx = np.where(voiced)[0]
    def ft(frac):
        k = int(clamp(frac) * (len(vidx) - 1)); return st + vidx[k] * FR
    wt = [(w, ft(cum[i]), ft(cum[i + 1]) + FR) for i, w in enumerate(words)]
    CLIPS[f] = dict(x=x, env=np.clip(env / ref, 0, 1.3), start=st, who=who, words=wt, dur=len(x) / SR)


def talk(who, t):
    for f, cl in CLIPS.items():
        if cl['who'] == who and cl['start'] <= t < cl['start'] + cl['dur']:
            i = int((t - cl['start']) / FR)
            if i < len(cl['env']):
                v = cl['env'][i]
                return clamp(v * 0.9) if v > 0.12 else 0.0
    return 0.0


def caption_chunks():
    out = []
    for f, st, who, txt in VO:
        ws = CLIPS[f]['words']; chunk = []
        for i, w in enumerate(ws):
            chunk.append(w)
            if len(chunk) == 3 or w[0][-1] in '.!?' or i == len(ws) - 1 or sum(len(x[0]) for x in chunk) > 13:
                out.append(chunk); chunk = []
    res = []
    for i, ch in enumerate(out):
        s = ch[0][1]
        e = ch[-1][2] + 0.25
        if i + 1 < len(out):
            e = min(e, out[i + 1][0][1])
        res.append((s, e, ch))
    return res


CHUNKS = caption_chunks()

# ------------------------------------------------------------------ UI (drawn at 1x onto the frame)
_emoji_cache = {}


def emoji(ch, size):
    key = (ch, size)
    if key not in _emoji_cache:
        f = ImageFont.truetype(F_EMOJI, 109)
        im = Image.new('RGBA', (140, 140), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((70, 70), ch, font=f, embedded_color=True, anchor='mm')
        im = im.crop(im.getbbox())
        _emoji_cache[key] = im.resize((size, int(size * im.height / im.width)), Image.LANCZOS)
    return _emoji_cache[key]


def title_box(img, d):
    lines = [('When your mom says', None), ('"We have food at home"', '😭')]
    y = 250
    for txt, em in lines:
        f = font(F_BLACK, 58)
        tw = f.getlength(txt) + (70 if em else 0)
        x0 = W / 2 - tw / 2 - 28; x1 = W / 2 + tw / 2 + 28
        d.rounded_rectangle([x0, y - 44, x1, y + 44], radius=16, fill=(12, 12, 14))
        d.text((W / 2 - (35 if em else 0), y), txt, font=f, fill=WHITE, anchor='mm')
        if em:
            e = emoji(em, 60); img.alpha_composite(e, (int(W / 2 + tw / 2 - 62), int(y - e.height / 2)))
        y += 80


def captions(img, d, t):
    for s, e, ch in CHUNKS:
        if s <= t < e:
            f = font(F_BLACK, 84)
            words = [w for w, _, _ in ch]
            gap = 22
            total = sum(f.getlength(w) for w in words) + gap * (len(words) - 1)
            pop = back(prog(t, s, s + 0.12)) if t < s + 0.12 else 1
            fs = font(F_BLACK, max(8, int(84 * pop)))
            x = W / 2 - total / 2 * pop; y = 1150 if 14.6 <= t < 23.2 else 1360
            for w, ws, we in ch:
                cur = ws <= t < we + 0.05
                col = (255, 226, 40) if cur else WHITE
                d.text((x, y), w, font=fs, fill=col, anchor='lm', stroke_width=9, stroke_fill=(10, 10, 10))
                x += (f.getlength(w) + gap) * pop
            return


def big_text(d, txt, y, sz, col, t, t0, stroke=10):
    if t < t0:
        return
    p = prog(t, t0, t0 + 0.22); s = back(p) if p < 1 else 1
    d.text((W / 2, y), txt, font=font(F_BLACK, max(6, int(sz * s))), fill=col, anchor='mm', stroke_width=stroke, stroke_fill=(10, 10, 10))


def error_box(img, d, t, t0):
    sc = back(prog(t, t0, t0 + 0.2)) if t < t0 + 0.2 else 1
    cx, cy = W / 2, 820
    bw, bh = 860 * sc, 330 * sc
    d.rounded_rectangle([cx - bw / 2 + 10, cy - bh / 2 + 12, cx + bw / 2 + 10, cy + bh / 2 + 12], 16, fill=(0, 0, 0))
    d.rounded_rectangle([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], 16, fill=(238, 238, 242), outline=(40, 40, 60), width=4)
    if sc < 0.9:
        return
    d.rounded_rectangle([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy - bh / 2 + 64], 16, fill=(30, 100, 210))
    d.text((cx - bw / 2 + 30, cy - bh / 2 + 32), 'Kid.exe', font=font(F_XB, 36), fill=WHITE, anchor='lm')
    d.ellipse([cx - 360, cy - 30, cx - 260, cy + 70], fill=(220, 40, 40))
    d.text((cx - 310, cy + 20), 'X', font=font(F_BLACK, 60), fill=WHITE, anchor='mm')
    d.text((cx - 225, cy - 5), 'Kid.exe has stopped', font=font(F_XB, 48), fill=INK, anchor='lm')
    d.text((cx - 225, cy + 52), 'working.', font=font(F_XB, 48), fill=INK, anchor='lm')
    d.rounded_rectangle([cx + 200, cy + 100, cx + 380, cy + 150], 8, fill=WHITE, outline=(30, 100, 210), width=4)
    d.text((cx + 290, cy + 125), 'OK', font=font(F_XB, 34), fill=INK, anchor='mm')


# ------------------------------------------------------------------ shots
Z0 = H / 720.0  # zoom that fills the frame height


def cam_ok(bg, cx, cy, z):
    im = BG[bg]; w, h = W / z, H / z
    cx = clamp(cx, w / 2, im.width - w / 2); cy = clamp(cy, h / 2, im.height - h / 2)
    return (cx, cy, z)


def kid_car(c, t, expr, sad=False):
    hip = (330, 440)
    if sad:
        return char(c, 'kid', hip, 72, dr=1, sit=True, arms=((15, 5), (-10, -5)), expr='sad', look=(0, 1),
                    blink=(9.2 < t < 9.32))
    point = 0.6 < t < 3.9
    arms = (('ik', (470, 230 + 10 * math.sin(t * 9)), -1), (-20, -5)) if point else ((20, 5), (-20, -5))
    bounce = abs(math.sin(t * 10)) * 6 if t < 3.9 else 0
    return char(c, 'kid', (hip[0], hip[1] - bounce), 72, dr=1, sit=True, arms=arms, expr=expr, talk=talk('kid', t),
                look=(1, -0.5))


def mom_car(c, t):
    hip = (905, 552)
    wob = math.sin(t * 2) * 6
    return char(c, 'mom', hip, 85, dr=1, sit=True, arms=(('ik', (1000, 350 + wob), -1), ('ik', (1012, 330 - wob), -1)),
                expr='unimpressed' if t > 5.2 else 'neutral', talk=talk('mom', t), look=(1, 0),
                blink=(6.6 < t < 6.72))


def fridge_open_overlay(c, p):
    if p <= 0:
        return
    c.rect(966, 80, 1192, 522, fill=lerpc((230, 230, 225), (255, 250, 210), p), outline=INK, w=3)
    for y in (230, 330, 430):
        c.line([(970, y), (1188, y)], (205, 205, 195), 5)
    c.ell(1080, 205, 12, 16, fill=WHITE, outline=INK, w=2.5)
    sk = 40 * p
    c.poly([(1197, 75), (1197 + 85 * p, 75 - sk), (1197 + 85 * p, 530 + sk), (1197, 525)], fill=(235, 236, 240), outline=INK, w=3)


def fridge_pov(c, t):
    """Full-screen view into the fridge (screen coords)."""
    c.ui()
    c.rect(0, 0, W, H, fill=(250, 246, 214))
    c.rect(0, 0, 70, H, fill=(225, 225, 228)); c.rect(W - 70, 0, W, H, fill=(225, 225, 228))
    c.rect(0, 0, W, 60, fill=(210, 210, 214))
    for y in (620, 1050, 1480):
        c.rect(70, y, W - 70, y + 22, fill=(225, 232, 236), outline=(170, 180, 186), w=3)
    c.ell(540, 545, 58, 76, fill=WHITE, outline=INK, w=6)  # the egg
    c.circle(512, 510, 12, fill=(240, 240, 240))
    # ketchup nearly empty
    c.rect(230, 840, 330, 1050, fill=(245, 245, 245), outline=INK, w=6, r=24)
    c.rect(236, 1000, 324, 1046, fill=(210, 30, 30), r=18)
    c.rect(255, 800, 305, 845, fill=(210, 30, 30), outline=INK, w=5, r=6)
    # sad pickle jar (just juice)
    c.rect(720, 880, 860, 1050, fill=(200, 225, 160), outline=INK, w=6, r=16)
    c.rect(712, 850, 868, 890, fill=(90, 140, 80), outline=INK, w=5, r=6)
    # mystery container
    shake = 0
    if t > 19.4:
        shake = math.sin(t * 75) * 14 * prog(t, 19.4, 22.4)
    lid = ease(prog(t, 22.55, 22.75))
    bx = 560 + shake
    c.rect(bx - 220, 1250, bx + 220, 1478, fill=(95, 145, 225), outline=INK, w=7, r=20)
    if lid > 0:
        c.rect(bx - 210, 1235 - 110 * lid, bx + 210, 1262, fill=(10, 10, 12))
        for ex in (-60, 60):
            c.ell(bx + ex, 1215 - 50 * lid, 26 * lid + 1, 16 * lid + 1, fill=(255, 230, 40))
            c.circle(bx + ex, 1215 - 50 * lid, 8 * lid + 1, fill=(200, 20, 20))
    c.rect(bx - 235, 1205 - 130 * lid, bx + 235, 1255 - 130 * lid, fill=(60, 100, 185), outline=INK, w=7, r=12)
    c.rect(bx - 130, 1300, bx + 130, 1420, fill=(255, 250, 200), outline=(150, 140, 90), w=3)
    # kid peeking in from bottom-left
    kt = talk('kid', t)
    expr = 'sad' if t < 19.4 else ('scared' if t < 22.55 else 'shock')
    char(c, 'kid', (250, 2150), 300, dr=1, arms=((10, 0), (-10, 0)), expr=expr, talk=kt, look=(0.6, -0.6),
         blink=(17.5 < t < 17.62))


def shot(t):
    """Returns (bg, cam, draw_fn(c), overlay_fn(img, d))."""
    if t < 4.4:
        z = lerp(Z0, Z0 * 1.08, prog(t, 0, 4.4))
        return 'car', cam_ok('car', 330, 340, z), lambda c: kid_car(c, t, 'excited'), None
    if t < 8.1:
        z = lerp(Z0, Z0 * 1.06, prog(t, 4.4, 8.1))
        return 'car', cam_ok('car', 985, 360, z), lambda c: mom_car(c, t), None
    if t < 9.8:
        return 'car', cam_ok('car', 330, 300, Z0 * 1.35), lambda c: kid_car(c, t, 'sad', sad=True), None
    if t < 12.2:
        def card(img, d):
            d.rectangle([0, 0, W, H], fill=(14, 14, 20))
            big_text(d, 'THE', 760, 120, WHITE, t, 9.95)
            big_text(d, 'FOOD AT', 920, 140, WHITE, t, 10.45)
            big_text(d, 'HOME...', 1110, 190, (255, 70, 70), t, 10.95)
        return None, None, None, card
    if t < 14.6:
        def d_(c):
            fridge_open_overlay(c, ease(prog(t, 14.05, 14.45)))
            if t < 13.8:
                x = lerp(800, 925, prog(t, 12.2, 13.8))
                legs, arms, b = walk(t)
                char(c, 'kid', (x, 458 - b), 72, legs=legs, arms=arms, expr='happy', look=(1, 0))
            else:
                char(c, 'kid', (925, 458), 72, arms=(('ik', (1012, 300), 1), (-20, -5)), expr='excited', look=(1, -0.3))
        return 'fridge', cam_ok('fridge', 1000, 360, Z0), d_, None
    if t < 23.2:
        return None, None, lambda c: fridge_pov(c, t), None
    if t < 26.8:
        def d_(c):
            hop = 30 * math.sin(math.pi * prog(t, 25.5, 25.8))
            sk = (math.sin(t * 90) * 8 if t < 23.6 else 0)
            char(c, 'kid', (935 + sk, 458 - hop), 72, dr=-1, arms=((-150, -170), (150, 170)), legs=((10, 3), (-10, -3)),
                 expr='scared', talk=talk('kid', t), look=(-1, 0))
            sweat(c, 880, 260, t)
        def ov(img, d):
            if 26.0 < t < 26.8:
                pass
        z = Z0 * (1.0 + 0.04 * prog(t, 23.2, 26.8))
        return 'fridge', cam_ok('fridge', 980, 360, z), d_, None
    if t < 31.8:
        def d_(c):
            stir = math.sin(t * 7)
            pot_fx(c, t)
            jazz = t > 30.8
            if jazz:
                arms = ((-140, -160), (140, 160))
                char(c, 'mom', (360, 433), 85, dr=-1, arms=arms, expr='grin', talk=talk('mom', t), look=(-0.5, 0))
            else:
                tgt = (245 + 18 * stir, 286 + 5 * math.cos(t * 7))
                def spoon(hands):
                    h = hands[0]
                    c.line([h, (tgt[0] - 45, tgt[1] + 18)], (150, 100, 60), 7)
                char(c, 'mom', (360, 433), 85, dr=-1, arms=(('ik', tgt, -1), (-30, -15)), expr='happy',
                     talk=talk('mom', t), look=(-1, 0.3), hold=spoon)
        return 'dining', cam_ok('dining', 300, 360, Z0), d_, None
    if t < 37.6:
        def d_(c):
            drop = ease(prog(t, 31.85, 32.2))
            py = lerp(150, 372, drop)
            if t >= 31.85:
                plate(c, 985, py)
                blob(c, 985, py - 4, t, 1.0, blink=(34.15 < t < 34.35 or 36.85 < t < 37.0), look=1)
            if t < 32.7:  # mom's arm slamming the plate down from the left
                hx = 985 - 60
                c.line([(860, py - 60), (hx, py - 10)], INK, 8.5); c.circle(hx, py - 10, 12.5, fill=INK)
            expr = 'neutral' if t < 33.2 else ('shock' if 34.15 < t < 34.6 else 'deadpan')
            char(c, 'kid', (1150, 468), 70, dr=-1, sit=True, arms=(('ik', (1060, 372), 1), ('ik', (1075, 378), 1)),
                 expr=expr, talk=talk('kid', t), look=(-1, 0.6), blink=(33.6 < t < 33.72))
        z = lerp(Z0, Z0 * 1.22, ease(prog(t, 32.6, 37.6)))
        return 'dining', cam_ok('dining', lerp(1075, 1060, prog(t, 32.6, 37.6)), lerp(360, 340, prog(t, 32.6, 37.6)), z), d_, None
    if t < 41.5:
        def d_(c):
            pot_fx(c, t)
            jab = math.sin(t * 14) * 6 if talk('mom', t) > 0.1 else 0
            char(c, 'mom', (360, 433), 85, dr=1, arms=((95 + jab, 92 + jab), (-40, 30)), expr='stern', talk=talk('mom', t),
                 look=(1, 0))
        return 'dining', cam_ok('dining', 330, 360, Z0 * 1.05), d_, None
    if t < 47.8:
        def d_(c):
            bite = t > 42.3
            plate(c, 985, 372)
            blob(c, 985, 368, t, 1.0, look=1 if t < 44 else -1, bite=bite)
            green = prog(t, 43.0, 43.8)
            col = lerpc(INK, (40, 120, 40), green)
            headc = lerpc(HEAD, (160, 205, 130), green); headsh = lerpc(HEAD_SH, (120, 170, 95), green)
            if t < 44.0:
                p1 = ease(prog(t, 41.6, 41.95)); p2 = ease(prog(t, 41.95, 42.35))
                mouth = (1120, 338)
                if t < 41.95:
                    tgt = lerpp((1075, 378), (1000, 360), p1)
                else:
                    tgt = lerpp((1000, 360), (mouth[0] - 8, mouth[1] + 30), p2)
                if t > 42.9: tgt = (1075, 378)
                def spoon(hands):
                    if t < 42.9:
                        h = hands[0]; tip = (h[0] - 28, h[1] - (22 if t > 41.95 else -6))
                        c.line([h, tip], (170, 170, 180), 6); c.ell(tip[0], tip[1], 9, 6, fill=(170, 170, 180))
                expr = 'scared' if t < 42.35 else ('chew' if t < 42.7 else ('shock' if t < 43.0 else 'sick'))
                wob = math.sin(t * 40) * 4 if t > 43.0 else 0
                char(c, 'kid', (1150 + wob, 468), 70, dr=-1, sit=True, arms=(('ik', tgt, 1), ('ik', (1075, 378), 1)),
                     expr=expr, col=col, head=headc, head_sh=headsh, look=(-1, 0.4), hold=spoon)
            else:
                f = ease(prog(t, 44.0, 44.55))
                hip = lerpp((1150, 468), (1125, 600), f)
                tw = math.sin(t * 22) * 10 if t > 45 else 0
                char(c, 'kid', hip, 70, dr=-1, rot=85 * f, legs=((-90 + tw, 0), (-80, -10 - tw)), arms=((-60, -100), (60, 100)),
                     expr='dead' if t > 44.55 else 'sick', col=col, head=headc, head_sh=headsh)
        shake = math.sin(t * 100) * 6 if 44.55 < t < 44.9 else 0
        return 'dining', cam_ok('dining', 1075 + shake, 360, Z0), d_, (lambda img, d: error_box(img, d, t, 45.0)) if t >= 45.0 else None
    if t < 53.6:
        def d_(c):
            op = ease(prog(t, 49.1, 49.5))
            doorway(c, op)
            if op > 0:
                def hold_bag(hands):
                    if t < 53.25:
                        bag(c, hands[0][0] - 10, hands[0][1] + 25, 52)
                char(c, 'guy', (978, 297), 58, dr=-1, arms=(('ik', (935, 330), 1), (-20, -8)), expr='happy',
                     talk=talk('guy', t), look=(-1, 0.3), hold=hold_bag)
            if t < 49.0:
                x = lerp(620, 790, prog(t, 48.0, 49.0)); legs, arms, b = walk(t, speed=11)
                char(c, 'mom', (x, 443 - b), 85, dr=1, legs=legs, arms=arms, expr='happy', look=(1, 0))
            else:
                grab = ease(prog(t, 53.2, 53.45))
                def hold(hands):
                    if t >= 53.25:
                        bag(c, 735, 470, 52)
                if t < 53.2:
                    arms = ((25, 10), (-25, -10)); expr = 'happy' if t < 52.4 else 'sly'
                else:
                    arms = (('ik', lerpp((900, 360), (760, 470), grab), 1), (-25, -10)); expr = 'sly'
                char(c, 'mom', (790, 443), 85, dr=1, arms=arms, expr=expr, look=(1, -0.3), hold=hold)
        return 'living', cam_ok('living', 900, 360, Z0), d_, None
    if t < 55.2:
        def d_(c):
            rise = ease(prog(t, 53.6, 53.85))
            char(c, 'kid', (420, lerp(720, 400, rise)), 72, dr=1, arms=((150, 175), (-150, -175)), expr='mad_shock',
                 talk=talk('kid', t), look=(1, 0))
        sh = math.sin(t * 120) * 8 if 53.6 < t < 53.9 else 0
        return 'living', cam_ok('living', 420 + sh, 360, Z0 * 1.05), d_, 'couch'
    # final: mom close-up with the burger, then end card
    def d_(c):
        chomp = t > 57.95
        def hold(hands):
            h = hands[0]
            burger(c, h[0] - 12, h[1] - 30, 46)
            if chomp:
                c.circle(h[0] + 6, h[1] - 52, 14, fill=(184, 205, 230))
        lift = ease(prog(t, 56.9, 57.6))
        tgt = lerpp((735, 470), (742, 400), lift)
        expr = 'sly' if t < 57.95 else 'chew'
        char(c, 'mom', (790, 443), 85, dr=-1, arms=(('ik', tgt, -1), (40, 15)), expr=expr, talk=talk('mom', t),
             look=(-1, 0))
    z = lerp(Z0 * 1.5, Z0 * 1.62, prog(t, 55.2, 60))
    def ov(img, d):
        if t >= 58.3:
            veil = Image.new('RGBA', (W, H), (0, 0, 0, int(140 * prog(t, 58.3, 58.5))))
            img.alpha_composite(veil)
            big_text(d, 'TAG YOUR MOM', 800, 120, (255, 226, 40), t, 58.35)
            big_text(d, 'who does this', 940, 64, WHITE, t, 58.6, stroke=7)
            big_text(d, 'FOLLOW FOR PART 2', 1560, 70, WHITE, t, 58.9, stroke=8)
            if t > 58.4:
                e = emoji('😂', 150); img.alpha_composite(e, (W // 2 - 75, 560))
    return 'living', cam_ok('living', 770, 300, z), d_, ov


def pot_fx(c, t):
    for i in range(10):
        ph = (t * 0.55 + i * 0.1) % 1
        bx = 160 + (i * 37) % 70 + math.sin(t * 2 + i) * 10
        c.circle(bx, 268 - ph * 230, 9 + ph * 30, fill=lerpc((150, 215, 90), (170, 195, 160), ph))
    for i in range(4):
        ph = (t * 1.4 + i * 0.25) % 1
        c.circle(150 + i * 15, 277 - ph * 8, 4 + ph * 4, fill=(150, 220, 70), outline=(80, 130, 40), w=1.5)


def doorway(c, op):
    if op <= 0:
        return
    x0, y0, x1, y1 = 888, 92, 1064, 450
    c.rect(x0, y0, x1, y1, fill=(165, 215, 250))
    c.rect(x0, 330, x1, y1, fill=(120, 185, 95))
    c.poly([(950, y1), (1000, y1), (1030, 330), (990, 330)], fill=(200, 190, 170))
    xr = lerp(x0, 1064, op)
    c.poly([(xr, y0), (1066, y0), (1066, y1), (xr, y1)], fill=(140, 85, 45), outline=INK, w=3)
    c.poly([(1066, 80), (1066 + 70 * op, 60), (1066 + 70 * op, 470), (1066, 458)], fill=(150, 92, 50), outline=INK, w=3)


def render(t):
    bg, cam, draw_fn, ov = shot(t)
    if bg:
        cx, cy, z = cam
        w, h = W / z, H / z
        frame = BG[bg].resize((W, H), Image.BICUBIC, box=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)).convert('RGBA')
    else:
        frame = Image.new('RGBA', (W, H), (14, 14, 20, 255))
        cam = (W / 2, H / 2, 1.0)
    if draw_fn:
        c = Cv(cam)
        draw_fn(c)
        frame.alpha_composite(c.out())
    if ov == 'couch':
        cx, cy, z = cam; w, h = W / z, H / z
        frame.alpha_composite(COUCH.resize((W, H), Image.BICUBIC, box=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)))
        ov = None
    d = ImageDraw.Draw(frame)
    if ov:
        ov(frame, d)
    title_box(frame, d)
    if not (9.8 <= t < 12.2):
        captions(frame, d, t)
    return frame.convert('RGB')


# ------------------------------------------------------------------ audio
NS = int(SR * DUR)


def tt(dur): return np.arange(int(dur * SR)) / SR
def sine(f, dur): return np.sin(2 * np.pi * f * tt(dur))


def sweep(f0, f1, dur, vib=0.0, vibf=0.0, sq=False):
    t = tt(dur); f = np.linspace(f0, f1, len(t)) + vib * np.sin(2 * np.pi * vibf * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.tanh(3 * np.sin(ph)) if sq else np.sin(ph)


def noise(dur, seed=0): return np.random.default_rng(seed).uniform(-1, 1, int(dur * SR))
def lp(x, n): return np.convolve(x, np.ones(n) / n, mode='same')


def env(dur, a=0.005, k=6.0):
    t = tt(dur); e = np.exp(-t * k); na = max(1, int(a * SR)); e[:na] *= np.linspace(0, 1, na); return e


def mtof(m): return 440 * 2 ** ((m - 69) / 12)


def build_audio(path):
    A = np.zeros(NS); V = np.zeros(NS)

    def add(t, sig, vol=1.0, buf=None):
        b = A if buf is None else buf
        i = int(t * SR)
        if i >= NS or i < 0: return
        j = min(NS, i + len(sig)); b[i:j] += sig[:j - i] * vol

    def pluck(f, d=0.45, k=7):
        t = tt(d)
        return (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(4 * np.pi * f * t) + 0.2 * np.sin(6 * np.pi * f * t)) * env(d, 0.003, k)

    def bell(f, d=1.2):
        t = tt(d)
        return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * 2.01 * f * t) + 0.2 * np.sin(2 * np.pi * 3.02 * f * t)) * env(d, 0.002, 3.5)

    def thump(d=0.35, f=55, nz=0.6, seed=1):
        return np.sin(2 * np.pi * f * tt(d)) * env(d, 0.002, 9) + lp(noise(d, seed), 6) * env(d, 0.001, 28) * nz

    # voices
    for f, cl in CLIPS.items():
        add(cl['start'], cl['x'], 1.0, V)

    # music bed: light plucky loop
    M = np.zeros(NS)
    chords = [(48, [0, 4, 7, 12]), (45, [0, 3, 7, 12]), (41, [0, 4, 7, 12]), (43, [0, 4, 7, 12])]
    patt = [0, 1, 2, 3, 2, 1, 2, 1]
    tb, bar = 0.0, 0
    while tb < DUR:
        root, iv = chords[bar % 4]
        for i, pi in enumerate(patt):
            s = pluck(mtof(root + 12 + iv[pi]), 0.35)
            i0 = int((tb + i * 0.25) * SR); j0 = min(NS, i0 + len(s))
            if i0 < NS: M[i0:j0] += s[:j0 - i0] * 0.5
        for bt in (0, 1.0):
            s = np.sin(2 * np.pi * mtof(root - 12) * tt(0.5)) * env(0.5, 0.005, 4)
            i0 = int((tb + bt) * SR); j0 = min(NS, i0 + len(s))
            if i0 < NS: M[i0:j0] += s[:j0 - i0] * 0.8
        tb += 2.0; bar += 1
    tl = np.arange(NS) / SR
    mv = np.ones(NS)
    for a, b in ((8.1, 12.3), (19.4, 23.6), (42.7, 47.8), (53.6, 55.2), (58.3, 60)):
        mv[(tl >= a) & (tl < b)] = 0.0
    mv = lp(mv, int(0.08 * SR))

    # SFX
    d = 8.1; eng = lp(noise(d, 2), 60) * 6 + 0.4 * np.sin(2 * np.pi * 50 * tt(d)) * (1 + 0.3 * np.sin(2 * np.pi * 7 * tt(d)))
    add(0, eng * np.minimum(1, (d - tt(d)) / 0.3), 0.06)
    for i, (m, dd) in enumerate(((58, 0.35), (57, 0.35), (56, 0.35), (55, 0.9))):  # sad trombone
        t0 = 8.25 + i * 0.36; tq = tt(dd); f = mtof(m) * (1 + (0.02 * np.sin(2 * np.pi * 6 * tq) if i == 3 else 0))
        ph = 2 * np.pi * np.cumsum(np.ones_like(tq) * f) / SR
        saw = lp(2 * ((ph / (2 * np.pi)) % 1) - 1, 6)
        add(t0, saw * np.minimum(1, tq / 0.03) * np.minimum(1, (dd - tq) / 0.08), 0.22)
    for tp, f, dd in ((9.95, 110, 0.45), (10.45, 104, 0.45), (10.95, 92.5, 1.3)):
        tq = tt(dd); s = 2 * ((f * tq) % 1) - 1; s2 = 2 * ((f * 1.5 * tq) % 1) - 1
        add(tp, lp(s + 0.6 * s2 + 0.8 * np.sin(np.pi * f * tq), 8) * env(dd, 0.01, 1.6), 0.42)
    for k in range(6):
        add(12.3 + k * 0.26, thump(0.08, 130, 0.3, k), 0.1)
    add(14.05, lp(np.sign(np.sin(2 * np.pi * np.cumsum(240 + 70 * np.sin(2 * np.pi * 9 * tt(0.5))) / SR)), 6) * env(0.5, 0.02, 3), 0.07)
    add(14.6, np.sin(2 * np.pi * 60 * tt(8.6)), 0.03)
    dd = 3.4; tq = tt(dd)
    gr = lp(noise(dd, 5), 30) * 5 * (0.55 + 0.45 * np.sin(2 * np.pi * 23 * tq)) + 0.4 * lp(2 * ((68 * tq) % 1) - 1, 10)
    gr *= np.clip(tq / 3.1, 0, 1) ** 2 * (tq < 3.15) + (tq >= 3.15) * 1.8 * np.exp(-(tq - 3.15) * 3)
    add(19.4, gr, 0.3)
    add(23.25, thump(0.45, 50, 0.9), 0.75)
    add(25.5, thump(0.3, 70, 0.4), 0.4)
    add(25.5, sweep(160, 600, 0.3, vib=50, vibf=28) * env(0.3, 0.005, 6), 0.12)
    r2 = random.Random(9)
    for a, b in ((26.8, 31.8), (37.6, 41.5)):
        tp = a
        while tp < b:
            f0 = r2.uniform(180, 380); add(tp, sweep(f0, f0 * 2.6, 0.045) * env(0.045, 0.002, 40), 0.06); tp += r2.uniform(0.08, 0.3)
    add(31.85, np.diff(noise(0.3, 11), prepend=0) * np.hanning(int(0.3 * SR)), 0.2)
    add(32.2, thump(0.3, 90, 0.8, 3), 0.45)
    add(32.2, bell(1400, 0.4), 0.18)
    add(32.25, lp(noise(0.25, 7), 12) * 3 * env(0.25, 0.01, 10) * np.sin(2 * np.pi * 9 * tt(0.25)), 0.25)
    for tp in (34.15, 36.85):
        add(tp, sweep(300, 950, 0.09) * env(0.09, 0.002, 18), 0.3)
    add(41.6, np.diff(noise(0.2, 12), prepend=0) * np.hanning(int(0.2 * SR)), 0.1)
    for k in range(4):
        add(42.35 + k * 0.09, lp(noise(0.07, 20 + k), 10) * 4 * env(0.07, 0.005, 20), 0.2)
    for tp in (42.72, 42.88):
        add(tp, sweep(520, 160, 0.15) * env(0.15, 0.002, 10), 0.35)
    dd = 1.0; tq = tt(dd); f = 320 - 140 * tq + 30 * np.sin(2 * np.pi * 7 * tq)
    add(43.0, np.tanh(2 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.minimum(1, (dd - tq) * 5), 0.1)
    add(44.0, sweep(1500, 260, 0.55) * np.minimum(1, (0.55 - tt(0.55)) * 20), 0.14)
    add(44.55, thump(0.5, 45, 1.0), 0.8)
    add(45.0, (sine(523, 0.45) + sine(659, 0.45) * 0.7 + sine(784, 0.45) * 0.4) * env(0.45, 0.004, 5), 0.18)
    add(47.8, bell(659, 1.0), 0.3); add(48.25, bell(523, 1.4), 0.3)
    for k in range(4):
        add(48.05 + k * 0.27, thump(0.08, 120, 0.3, k), 0.12)
    add(49.1, lp(np.sign(np.sin(2 * np.pi * np.cumsum(300 + 90 * np.sin(2 * np.pi * 7 * tt(0.4))) / SR)), 6) * env(0.4, 0.01, 4), 0.06)
    add(53.2, lp(noise(0.3, 13), 3) * env(0.3, 0.01, 8), 0.2)
    dd = 0.5; tq = tt(dd); f = 700 + 600 * np.sin(2 * np.pi * 5 * tq)
    sc = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.4 + lp(noise(dd, 15), 2) * 0.6
    add(53.55, lp(sc, 4) * env(dd, 0.002, 4), 0.3)
    add(57.95, thump(0.12, 150, 0.9, 30), 0.4)
    add(57.95, lp(noise(0.15, 31), 4) * env(0.15, 0.002, 18), 0.4)
    for k in range(3):
        add(58.2 + k * 0.22, lp(noise(0.06, 40 + k), 8) * 4 * env(0.06, 0.005, 25), 0.12)
    for i, m in enumerate((60, 64, 67, 72)):
        add(58.35 + i * 0.09, pluck(mtof(m), 1.0, 3), 0.22)

    # duck music under dialogue
    venv = lp(np.abs(V), int(0.3 * SR)); duck = 1 - 0.55 * np.clip(venv / (venv.max() * 0.25 + 1e-9), 0, 1)
    mix = V * 1.0 + A + M * mv * duck * 0.07
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.92
    fo = int(0.4 * SR); mix[-fo:] *= np.linspace(1, 0, fo)
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR); wf.writeframes((mix * 32767).astype(np.int16).tobytes())


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--stills':
        out = sys.argv[2]; os.makedirs(out, exist_ok=True)
        for ts in sys.argv[3:]:
            render(float(ts)).save(os.path.join(out, f't{float(ts):05.1f}.png'))
        return
    out = sys.argv[1] if len(sys.argv) > 1 else 'food_at_home_v2.mp4'
    wav = out.rsplit('.', 1)[0] + '.wav'
    build_audio(wav)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-i', wav, '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', out]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nf = int(DUR * FPS)
    for i in range(nf):
        pr.stdin.write(render(i / FPS).tobytes())
        if i % 300 == 0:
            print(f'frame {i}/{nf}', flush=True)
    pr.stdin.close(); pr.wait(); os.remove(wav)
    print('done', out)


if __name__ == '__main__':
    main()
