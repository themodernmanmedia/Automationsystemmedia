"""Episode 1 — "What Happens If You Ignore Everyone for 30 Days?"

A dramatized, animated story (Max is fictional) built around real research on
ostracism, the spotlight effect, solitude and loneliness. Sources are listed in
META and end up in the YouTube description.
"""
from __future__ import annotations

import math

from ..config import H, W
from ..gfx import (
    TAU, alpha_group, at, burst, circle, clamp, ease_back, ease_io, ease_out, ellipse, fill, glow,
    headline, hexc, lerp, line, lin_grad, mix, pop, prog, rad_grad, rrect, saved, seeded, shade,
    soft_shadow, stroke, text, ui_text, with_alpha,
)
from .. import graphics as G
from .. import sets as S
from ..overlays import _word_times
from ..rig import Character, Dog, Pose, blend_expr, blend_pose
from ..timeline import Episode, Line, Shot
from ..tts import Voice

# --------------------------------------------------------------------------
# Cast
# --------------------------------------------------------------------------

MAX = Character("max", skin="#c68b62", hair="#1f1612", hair_style="short", top="#e63946", top_style="hoodie",
                bottom="#2f3e5c", shoes="#f8f9fa")
MOM = Character("mom", skin="#f1c7a3", hair="#7a4a2a", hair_style="bob", top="#6c9bd2", top_style="sweater",
                bottom="#4a4e69", apron=True, height=0.95, eye="#2d6a4f")
JAY = Character("jay", skin="#8d5a3b", hair="#140d0a", hair_style="curly", top="#ffb703", top_style="tee",
                accent="#219ebc", bottom="#3d405b", shoes="#ff006e")
LINDA = Character("linda", skin="#f3d2b8", hair="#c98b3a", hair_style="long", top="#2b2d42", top_style="blazer",
                  bottom="#2b2d42", glasses=True, eye="#1d3557", shoes="#111111")
GRANDMA = Character("grandma", skin="#efc9a8", hair="#dcdcdc", hair_style="bun", top="#b5838d", top_style="cardigan",
                    accent="#f6e7d8", bottom="#6d597a", glasses=True, height=0.9, shoes="#6d4c41")
BARISTA = Character("barista", skin="#e0ac69", hair="#3d2b1f", hair_style="buzz", top="#2a9d8f", top_style="tee",
                    accent="#ffffff", bottom="#264653", beard=True)
NEIGHBOR = Character("neighbor", skin="#a46b45", hair="#2b2118", hair_style="bob", top="#9d4edd", top_style="sweater",
                     bottom="#3c096c", height=0.97)
BISCUIT = Dog()

VOICES = {
    "narrator": Voice("am_michael", 1.08),
    "max": Voice("am_liam", 0.98),
    "mom": Voice("af_sarah", 1.0),
    "jay": Voice("am_puck", 1.07),
    "linda": Voice("bf_emma", 1.0, lang="en-gb"),
    "grandma": Voice("bf_isabella", 0.86, lang="en-gb"),
}
CAPTION_COLORS = {
    "narrator": "#ffffff", "max": "#ff8787", "mom": "#8fd3ff", "jay": "#ffd166",
    "linda": "#cdb4ff", "grandma": "#ffb5c8",
}

SEEDS = {"max": 0.0, "mom": 1.3, "jay": 2.7, "linda": 4.1, "grandma": 5.5, "barista": 6.2, "neighbor": 7.9}


def P(f, who, **kw) -> Pose:
    kw.setdefault("mouth", f.mouth(who))
    return Pose(t=f.gt + SEEDS.get(who, 0) * 3, seed=SEEDS.get(who, 0), **kw)


def wt(f, i: int, word: str, nth: int = 0) -> float:
    """Local time at which `word` is spoken in line i (caption-timing estimate)."""
    ln = f.shot.lines[i]
    words = (ln.caption or ln.text).upper().split()
    a, b = f.shot.line_times[i]
    times = _word_times(words, a, b)
    hits = [k for k, w in enumerate(words) if word.upper() in w]
    if not hits:
        return a
    return times[hits[min(nth, len(hits) - 1)]][0]


def walk_x(t, t0, t1, x0, x1):
    p = clamp((t - t0) / max(t1 - t0, 1e-6))
    x = lerp(x0, x1, p)
    moving = 0 < p < 1
    return x, (abs(x - x0) / 240 if moving else None)


def ken(f, z0=1.0, z1=1.06, cx=W / 2, cy=H / 2):
    return f.cam(lerp(z0, z1, ease_io(f.p)), cx, cy)


def phone_ui_header(ctx, w, title, t, battery=0.8):
    ui_text(ctx, "9:41", 40, 44, 26, "#ffffff", bold=True)
    rrect(ctx, w - 90, 30, 50, 24, 6)
    stroke(ctx, "#ffffff", 3)
    rrect(ctx, w - 86, 34, 42 * battery, 16, 3)
    fill(ctx, "#ffffff")
    if title:
        ui_text(ctx, title, w / 2, 110, 34, "#ffffff", bold=True, align="center")


def lockscreen_bg(ctx, w, h, c1="#3a0ca3", c2="#f72585"):
    ctx.set_source(lin_grad(0, 0, w, h, [(0, c1), (1, c2)]))
    ctx.paint()


# --------------------------------------------------------------------------
# Shots
# --------------------------------------------------------------------------

NOTIFS = [
    ("#34c759", "Messages", "Mom: pancakes are ready!!", "M"),
    ("#0a84ff", "Jay", "bro?? you alive?", "J"),
    ("#ff9f0a", "Work", "Linda: quick question", "W"),
    ("#34c759", "Messages", "Group chat (14 new)", "G"),
    ("#ff375f", "Missed Call", "Mom", "C"),
    ("#0a84ff", "Jay", "BLINK TWICE", "J"),
    ("#af52de", "Voicemail", "Grandma (0:41)", "V"),
    ("#34c759", "Messages", "Neighbor: is this your package?", "M"),
]


def hook(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#ff3d3d", "#7a0010")
    # exploding notifications behind Max
    slam = wt(f, 0, "thirty")
    with ken(f, 1.0, 1.08):
        for k in range(18):
            r = seeded(k)
            a = r.random() * TAU
            st = 0.15 + k * 0.12
            p = ease_out(prog(t, st, 1.2))
            d = 280 + r.random() * 520
            x = W / 2 + math.cos(a) * d * p
            y = 520 + math.sin(a) * d * 0.62 * p
            c, title, body, ic = NOTIFS[k % len(NOTIFS)]
            if p > 0:
                with at(ctx, x, y, s=0.55 + 0.25 * p, rot=(r.random() - 0.5) * 0.4):
                    S.notif_card(ctx, -230, -52, 460, c, title, body, alpha=min(1, p * 2), icon_txt=ic)
        G.notification_badge(ctx, W / 2 + 150, 360, int(412 * ease_out(prog(t, 0.2, 2.6))), s=1.4)
        MAX.draw(ctx, W / 2, 1060, 1.25, P(f, "max", arms="phone", held="phone",
                                            expr=blend_expr("neutral", "shocked", prog(t, 0.4, 0.3)),
                                            look=(0.3, -0.3), sweat=prog(t, 1.0, 0.5)))
    if t > slam - 0.1:
        ctx.set_source_rgba(0, 0, 0, 0.45 * prog(t, slam - 0.1, 0.2))
        ctx.paint()
        G.title_slam(ctx, ["IGNORE EVERYONE", "FOR 30 DAYS?!"], t, slam - 0.05, y=440, size=150)
    text(ctx, "ANIMATED STORY  •  REAL SCIENCE", W - 40, H - 40, 26, (1, 1, 1, 0.65), family="Inter", bold=True, align="right")


def no_contact(f):
    ctx, t = f.ctx, f.t
    lock_t = wt(f, 0, "nothing")
    with ken(f, 1.04, 1.1, cx=900, cy=560):
        S.bedroom(ctx, t, drawer_open=0.0 if t > lock_t else 1.0 - prog(t, lock_t - 0.4, 0.4))
        holding = t < lock_t - 0.35
        MAX.draw(ctx, 980, 990, 1.0, P(f, "max", arms=blend_pose("phone", ((10, -6), (35, -40)), prog(t, lock_t - 1.0, 0.6)),
                                         held="phone" if holding else None, expr="smug" if t < lock_t else "blank",
                                         look=(-0.6, 0.5) if t > lock_t - 1.2 else (0, 0)))
    for i, (word, label) in enumerate((("TEXTS", "TEXTS"), ("CALLS", "CALLS"), ("HEY", "SMALL TALK"))):
        ts = wt(f, 0, word)
        s = pop(t, ts, 0.3)
        if s > 0:
            x = 1340 + i * 0
            y = 250 + i * 170
            with at(ctx, x, y, s=s):
                rrect(ctx, -230, -62, 460, 124, 30)
                fill(ctx, (1, 1, 1, 0.95))
                text(ctx, label, 30, 0, 54, "#111111")
                G.x_mark(ctx, -165, 0, 0.95)
    if t > lock_t:
        s = pop(t, lock_t, 0.35)
        with at(ctx, 720, 560, s=s):
            G.lock_icon(ctx, 0, 0, 1.0)


def meet_max(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#2b7bff", "#0b2a7a")
    insane = wt(f, 0, "insane")
    with ken(f, 1.0, 1.05, cx=W / 2, cy=H / 2):
        expr = "happy"
        if t > insane - 0.1:
            expr = blend_expr("happy", "awkward", prog(t, insane - 0.1, 0.25))
        MAX.draw(ctx, 560, 1130, 1.45, P(f, "max", arms="wave" if t < 2.2 else ("hips" if t < insane else "shrug"),
                                            expr=expr, sweat=prog(t, insane, 0.4)))
        G.title_slam(ctx, ["MEET MAX"], t, 0.0, y=150, size=120, rot=-0.02)
        G.stat_card(ctx, 1380, 400, "Age", "26", s=pop(t, wt(f, 0, "twenty")), c="#ffe14d")
        G.stat_card(ctx, 1380, 610, "Avg. reply time", "3 MIN 52 SEC", s=pop(t, wt(f, 0, "replies")), c="#7cf29c")
        if t > insane:
            G.stat_card(ctx, 1380, 820, "Challenge", "30 DAYS OF SILENCE", s=pop(t, insane), c="#ff6b6b", w=620)


def rules(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#2d2d44", "#0c0c16", ray_c=(1, 1, 1, 0.03))
    G.title_slam(ctx, ["THE RULES"], t, 0.0, y=150, size=120, colors=("#ffe14d",))
    items = (("start", "NO STARTING CONVERSATIONS"), ("answer", "NO ANSWERING ANYONE"), ("nod", "NOT EVEN A NOD BACK"))
    for i, (w, msg) in enumerate(items):
        ts = wt(f, 0, w) - 0.15
        if t > ts:
            G.rule_card(ctx, 470, 360 + i * 170, i + 1, msg, prog(t, ts, 0.5))
    MAX.draw(ctx, 260, 1080, 0.95, P(f, "max", arms="crossed", expr="smug" if t < f.dur * 0.7 else "worried", look=(1, 0)))


def restart(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#3a0ca3", "#10002b")
    reset = wt(f, 0, "day") + 0.1
    tease = wt(f, 2, "nobody")
    # day counter spinning back to 1
    if t < tease - 0.3:
        n = 29 if t < reset else max(1, int(29 - 28 * ease_out(prog(t, reset, 0.8))))
        shake = 8 if reset < t < reset + 0.3 else 0
        with at(ctx, W / 2 + math.sin(t * 80) * shake, 420, s=1.6):
            rrect(ctx, -300, -110, 600, 220, 40)
            fill(ctx, (0, 0, 0, 0.6))
            headline(ctx, f"DAY {n}", 0, 0, 150, color="#ff4d4d" if t > reset else "#ffe14d")
        if t > reset + 0.8:
            headline(ctx, "BACK TO DAY ONE.", W / 2, 760, 90, color="#ffffff")
    else:
        q = prog(t, tease - 0.3, 0.5)
        # mysterious silhouette teaser
        with alpha_group(ctx, q):
            ctx.set_source_rgba(0, 0, 0, 0.6)
            ctx.paint()
            glow(ctx, W / 2, 520, 460, "#ffb3c6", 0.35)
            ctx.push_group()
            GRANDMA.draw(ctx, W / 2, 1000, 1.05, P(f, "grandma", arms="phone_ear", held="phone_dark", shadow=False))
            pat = ctx.pop_group()
            ctx.set_source_rgba(0.05, 0.02, 0.1, 1)
            ctx.mask(pat)
            G.question_mark(ctx, W / 2 + 250, 360 + math.sin(t * 3) * 10, 0.9)
            G.question_mark(ctx, W / 2 - 260, 420 + math.sin(t * 3 + 1) * 10, 0.6, c="#ff6b6b")


def day_card(n, sub="", color="#ffe14d"):
    def draw(f):
        ctx, t = f.ctx, f.t
        S.studio_bg(ctx, t, "#141414", "#000000", ray_c=(1, 0.85, 0.2, 0.05))
        s = ease_back(prog(t, 0.05, 0.4), 2.2)
        with at(ctx, W / 2, 470, s=0.6 + 0.4 * s, rot=-0.03):
            headline(ctx, "DAY", 0, -150, 110, color="#ffffff")
            headline(ctx, str(n), 0, 40, 300, color=color, ow=30)
        if sub:
            with alpha_group(ctx, prog(t, 0.6, 0.3)):
                headline(ctx, sub, W / 2, 790, 64, color="#ffffff", ow=8)
        # 30 dots progress
        for k in range(30):
            x = W / 2 - 29 * 22 + k * 44
            circle(ctx, x, 880, 12)
            fill(ctx, color if k < n else (1, 1, 1, 0.2))
    return draw


def mom_pancakes(f):
    ctx, t = f.ctx, f.t
    walk_start = f.cue(1) - 0.6
    walk_end = f.cue(1) + 3.0
    mx, ph = walk_x(t, walk_start, walk_end, 300, 1750)
    if t < walk_start:
        mx, ph = 300, None
    passing = clamp((t - walk_start) / (walk_end - walk_start))
    mom_expr = "happy"
    if t > f.cue(1) + 1.2:
        mom_expr = blend_expr("happy", "surprised", prog(t, f.cue(1) + 1.2, 0.25))
    if t > f.cue(2) - 0.4:
        mom_expr = blend_expr("surprised", "sad", prog(t, f.cue(2) - 0.4, 0.4))
    look = ((mx - 1150) / 400, 0.0)
    with ken(f, 1.0, 1.07, cx=1000, cy=560):
        S.kitchen(ctx, t)
        MOM.draw(ctx, 1150, 960, 1.0, P(f, "mom", arms="plate", held="plate", expr=mom_expr,
                                          look=(clamp(look[0], -1, 1), 0), facing=clamp(look[0], -1, 1) * 0.5))
        if t < walk_start + 0.01:
            # Max still at doorway looking at phone
            MAX.draw(ctx, 300, 990, 1.0, P(f, "max", arms="relaxed", expr="blank", look=(0.0, 0.4)))
        else:
            MAX.draw(ctx, mx, 990, 1.0, P(f, "max", arms="relaxed", expr="blank", walk=ph, look=(1, 0), facing=0.6))
    if f.cue(1) + 1.0 < t < f.cue(2):
        with at(ctx, 1260, 330, s=pop(t, f.cue(1) + 1.0)):
            G.question_mark(ctx, 0, 0, 0.6)


def cyberball(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#0f4c5c", "#06222b", ray_c=(1, 1, 1, 0.03))
    G.title_slam(ctx, ["THE “CYBERBALL” EXPERIMENT"], t, 0.1, y=110, size=86, colors=("#7cf2ff",))
    stop_t = wt(f, 2, "stopped")
    players = {"A": (560, 340), "B": (1360, 340), "YOU": (960, 660)}
    # avatars
    for name, (x, y) in players.items():
        you = name == "YOU"
        sad = you and t > stop_t + 1.2
        with at(ctx, x, y):
            rrect(ctx, -170, -120, 340, 240, 30)
            fill(ctx, (1, 1, 1, 0.1))
            circle(ctx, 0, -20, 60)
            fill(ctx, "#ffd166" if you else "#a8dadc")
            for side in (-1, 1):
                circle(ctx, side * 20, -32, 7)
                fill(ctx, "#222")
            if sad:
                ctx.arc(0, 18, 20, math.pi + 0.4, TAU - 0.4)
            else:
                ctx.arc(0, -6, 22, 0.4, math.pi - 0.4)
            stroke(ctx, "#222", 5)
            text(ctx, name, 0, 80, 40, "#ffffff", family="Inter", bold=True)
    # ball passes
    seq_in = ["A", "YOU", "B", "YOU", "A", "B", "YOU", "A"]
    seq_out = ["A", "B", "A", "B", "A", "B", "A", "B", "A", "B", "A", "B"]
    hop = 0.75
    if t < stop_t:
        k = int(t / hop)
        a, b = seq_in[k % len(seq_in)], seq_in[(k + 1) % len(seq_in)]
        q = (t % hop) / hop
    else:
        k = int((t - stop_t) / hop)
        a, b = seq_out[k % len(seq_out)], seq_out[(k + 1) % len(seq_out)]
        q = ((t - stop_t) % hop) / hop
    (x1, y1), (x2, y2) = players[a], players[b]
    bx = lerp(x1, x2, ease_io(q))
    by = lerp(y1, y2, ease_io(q)) - math.sin(q * math.pi) * 160 - 40
    glow(ctx, bx, by, 60, "#ffffff", 0.4)
    circle(ctx, bx, by, 26)
    fill(ctx, "#ff6b6b", preserve=True)
    stroke(ctx, "#ffffff", 4)
    if t > stop_t + 0.8:
        with at(ctx, 960, 610, s=pop(t, stop_t + 0.8)):
            rrect(ctx, -250, -40, 500, 80, 20)
            fill(ctx, "#ff3b3b")
            text(ctx, "LEFT OUT ON PURPOSE", 0, 0, 44, "#ffffff")


def brain_scan(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#1b263b", "#0d1b2a", ray_c=(1, 1, 1, 0.03))
    g = prog(t, wt(f, 0, "brain"), 0.8)
    with ken(f, 1.0, 1.08, cx=W / 2, cy=500):
        G.brain(ctx, 700, 520, 1.6, t, glow_region=g)
    if t > wt(f, 0, "worse"):
        G.stat_card(ctx, 1450, 300, "Mood after being ignored", "WORSE", s=pop(t, wt(f, 0, "worse")), c="#ff6b6b")
    if t > wt(f, 0, "physical"):
        with at(ctx, 1450, 640, s=pop(t, wt(f, 0, "physical"))):
            rrect(ctx, -330, -120, 660, 240, 30)
            fill(ctx, (1, 1, 1, 0.95))
            text(ctx, "SOCIAL PAIN", 0, -55, 58, "#e63946")
            text(ctx, "≈", 0, 0, 58, "#111111", family="DejaVu Sans")
            text(ctx, "PHYSICAL PAIN", 0, 58, 58, "#111111")


def mom_alone(f):
    ctx, t = f.ctx, f.t
    with ken(f, 1.05, 1.15, cx=960, cy=600):
        S.kitchen(ctx, t)
        MOM.draw(ctx, 960, 960, 1.0, P(f, "mom", sit=True, arms="type", expr="sad", look=(0, 0.6)))
        S.dining_table(ctx, 960, 790, 640)
        S.plate_of_pancakes(ctx, 960, 770, 1.0, t=t)
        G.rain_cloud(ctx, 960, 250, 0.9, t)
    if t > wt(f, 0, "hurt") and t < f.dur:
        with at(ctx, 1500, 330, s=pop(t, wt(f, 0, "hurt"))):
            G.heart(ctx, 0, 0, 1.6, c="#ff4d6d")
            line(ctx, -30, -60, 10, -10, "#ffffff", 8)
            line(ctx, 10, -10, -20, 30, "#ffffff", 8)


def phone_flood(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#00b4d8", "#03045e")
    stat_t = [wt(f, 1, "forty"), wt(f, 1, "twelve"), wt(f, 1, "voicemail")] if len(f.shot.lines) > 1 else [99, 99, 99]

    def screen(c, w, h):
        lockscreen_bg(c, w, h)
        phone_ui_header(c, w, "", t)
        text(c, "9:41", w / 2, 190, 120, "#ffffff", family="Inter", bold=False)
        n = int(ease_out(prog(t, 0.2, 2.8)) * 8)
        for k in range(n):
            col, title, body, ic = NOTIFS[k]
            y = 300 + k * 116 - max(0, n - 5) * 116 * 0
            hl = 1.0
            if title == "Voicemail" and t > stat_t[2]:
                rrect(c, 8, y - 8, w - 16, 120, 26)
                fill(c, (1, 0.88, 0.3, 0.6 + 0.4 * math.sin(t * 8)))
            S.notif_card(c, 20, y, w - 40, col, title, body, alpha=min(1, prog(t, 0.2 + k * 0.33, 0.25) * 2), icon_txt=ic,
                         time_s=f"{k + 1}d ago")
    with ken(f, 1.0, 1.05):
        S.phone_frame(ctx, 760, 560, 1.0, screen, t, tilt=-0.04)
    G.notification_badge(ctx, 1010, 120, int(59 * ease_out(prog(t, 0.2, 3.0))), s=1.2)
    labels = (("47", "UNREAD TEXTS", "#7cf29c"), ("12", "MISSED CALLS", "#ff6b6b"), ("1", "VOICEMAIL FROM GRANDMA", "#ffb5c8"))
    for i, (num, lab, c) in enumerate(labels):
        if t > stat_t[i]:
            with at(ctx, 1480, 320 + i * 210, s=pop(t, stat_t[i])):
                rrect(ctx, -330, -85, 660, 170, 28)
                fill(ctx, (0, 0, 0, 0.6))
                headline(ctx, num, -230, 0, 110, color=c)
                text(ctx, lab, 60, 0, 42 if len(lab) < 16 else 34, "#ffffff")


def jay_door(f):
    ctx, t = f.ctx, f.t
    knock = 1.0 if (f.cue(0) - 0.8 < t < f.cue(0) - 0.1) else 0.0
    with ken(f, 1.0, 1.06, cx=W / 2, cy=560):
        S.hallway_door(ctx, t, knock=knock)
        jx = 1320 + math.sin(t * 2.2) * 30 * (t > f.cue(1))
        arms = "fist" if t < f.cue(0) else ("cover" if t < f.cue(0) + 1.2 else "point_l")
        if t > f.cue(1):
            arms = "hips"
        JAY.draw(ctx, jx, 990, 1.05, P(f, "jay", arms=arms, expr="worried" if t < f.cue(1) else "awkward", look=(-0.8, 0),
                                         sweat=1.0 if t > f.cue(1) else 0.0))
    if t > f.cue(1):
        with at(ctx, 1500, 260, s=pop(t, f.cue(1))):
            rrect(ctx, -250, -60, 500, 120, 26)
            fill(ctx, "#ffd166")
            text(ctx, "JAY (BEST FRIEND)", 0, -8, 46, "#111111")
            ui_text(ctx, "silence tolerance: 0%", 0, 36, 26, "#333333", bold=True, align="center")


def office_ask(f):
    ctx, t = f.ctx, f.t
    with ken(f, 1.0, 1.08, cx=900, cy=560):
        S.office(ctx, t)
        MAX.draw(ctx, 560, 1000, 1.0, P(f, "max", sit=True, arms="type", expr="neutral" if t < f.cue(1) else "worried",
                                         look=(0.8, -0.2) if t > f.cue(1) else (0, 0.6),
                                         sweat=prog(t, f.cue(1) + 1.5, 0.5)))
        S.monitor(ctx, 330, 700, 0.9, t=t)
        # desk front panel hides legs
        rrect(ctx, 230, 760, 500, 80, 8)
        fill(ctx, "#adb5bd")
        lx, ph = walk_x(t, 0.0, f.cue(1) - 0.2, 1900, 1150)
        LINDA.draw(ctx, lx, 990, 1.02, P(f, "linda", arms="wave" if f.cue(1) <= t < f.cue(1) + 0.9 else ("hold_r" if t > f.cue(1) else "relaxed"),
                                          held="mug", expr="happy", walk=ph, look=(-1, 0), facing=-0.6))


def office_statue(f):
    ctx, t = f.ctx, f.t
    statue_t = wt(f, 0, "statue")
    z = lerp(1.0, 1.45, ease_io(prog(t, statue_t - 0.3, 1.2)))
    with f.cam(z, 760, 560, shake=0):
        S.office(ctx, t, tension=prog(t, statue_t, 0.5))
        frozen = t > statue_t - 0.2
        MAX.draw(ctx, 560, 1000, 1.0, P(f, "max", sit=True, arms="type", expr="blank" if frozen else "worried",
                                         blink=0.0 if frozen else None, breath=0.0 if frozen else 1.0,
                                         sweat=1.0, look=(0, 0)))
        S.monitor(ctx, 330, 700, 0.9, t=t, content="email" if t > f.cue(2) else "code")
        rrect(ctx, 230, 760, 500, 80, 8)
        fill(ctx, "#adb5bd")
        linda_expr = "happy" if t < statue_t else "awkward"
        LINDA.draw(ctx, 1150 + (60 * ease_io(prog(t, f.cue(1), 1.5))), 990, 1.02,
                   P(f, "linda", arms="hold_r", held="mug", expr=linda_expr, look=(-1, 0), facing=-0.6,
                     sweat=prog(t, statue_t + 1.0, 0.4)))
    if frozen and t < f.cue(1):
        G.thought_dots(ctx, 1000, 330, t)
    if t > f.cue(2):
        for k in range(3):
            ts = f.cue(2) + 0.8 + k * 0.5
            if t > ts:
                with at(ctx, 1400 + k * 60, 300 + k * 60, s=pop(t, ts)):
                    rrect(ctx, -140, -60, 280, 120, 18)
                    fill(ctx, "#ffffff", preserve=True)
                    stroke(ctx, "#333", 4)
                    ctx.move_to(-140, -60)
                    ctx.line_to(0, 10)
                    ctx.line_to(140, -60)
                    stroke(ctx, "#333", 4)
                    G.notification_badge(ctx, 130, -60, k + 1, s=0.6)


def street_walk(f):
    ctx, t = f.ctx, f.t
    scroll = t * 260
    with ken(f, 1.0, 1.04):
        S.street(ctx, t, scroll=scroll)
        # pedestrians walking the other way, all on phones
        for k, (ch, off) in enumerate(((NEIGHBOR, 0), (BARISTA, 900), (JAY, 1700))):
            if ch is JAY:
                continue
            x = W + 300 - ((t * 420 + off) % (W + 700))
            ch.draw(ctx, x, 1000, 0.95, P(f, ch.name, arms="phone", held="phone", walk=t * 1.6 + k, expr="neutral",
                                             look=(0, 0.6)), flip=True)
        MAX.draw(ctx, 760, 1010, 1.0, P(f, "max", arms="relaxed", walk=t * 1.1, expr="worried" if t > f.cue(0) + 2 else "neutral",
                                           look=(1, 0), facing=0.4))


def montage_unnoticed(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#ff9f1c", "#b65c00")
    panels = [("barista", wt(f, 0, "barista")), ("neighbors", wt(f, 0, "neighbors")), ("chat", wt(f, 0, "group"))]
    for i, (kind, ts) in enumerate(panels):
        if t < ts - 0.1:
            continue
        s = pop(t, ts - 0.1, 0.35)
        x = 340 + i * 620
        with at(ctx, x, 520, s=s, rot=(-0.04, 0.02, -0.02)[i]):
            rrect(ctx, -280, -330, 560, 660, 30)
            fill(ctx, "#ffffff")
            with saved(ctx):
                rrect(ctx, -262, -312, 524, 560, 22)
                ctx.clip()
                ctx.translate(-262, -312)
                if kind == "barista":
                    ctx.set_source(lin_grad(0, 0, 0, 560, [(0, "#ffe8d6"), (1, "#ddbea9")]))
                    ctx.paint()
                    rrect(ctx, 0, 380, 524, 200, 0)
                    fill(ctx, "#6f4518")
                    BARISTA.draw(ctx, 262, 640, 0.8, P(f, "barista", arms="hold_r", held="mug", expr="happy", look=(1, 0), shadow=False))
                    rrect(ctx, 0, 440, 524, 140, 0)
                    fill(ctx, "#8d5524")
                elif kind == "neighbors":
                    ctx.set_source(lin_grad(0, 0, 0, 560, [(0, "#bde0fe"), (1, "#e9f5db")]))
                    ctx.paint()
                    ctx.rectangle(0, 430, 524, 140)
                    fill(ctx, "#95d5b2")
                    S.plant(ctx, 120, 470, 0.9, t)
                    NEIGHBOR.draw(ctx, 320, 620, 0.8, P(f, "neighbor", arms="phone", held="phone", expr="content", shadow=False))
                else:
                    ctx.set_source_rgb(0.97, 0.97, 0.98)
                    ctx.paint()
                    rrect(ctx, 0, 0, 524, 70, 0)
                    fill(ctx, "#ececf0")
                    ui_text(ctx, "THE BOYS (6)", 262, 36, 26, "#111", bold=True, align="center")
                    msgs = ["who's down for saturday", "lol", "me", "bring snacks", "LOL", "wait where's max", "idk anyway"]
                    n = int(prog(t, ts, 2.4) * len(msgs)) + 1
                    y = 90
                    for k, m in enumerate(msgs[:n]):
                        me = k % 3 == 1
                        bh = S.chat_bubble(ctx, 500 if me else 24, y, m, me=me, size=24, max_w=330)
                        y += bh + 12
            label = {"barista": "BARISTA", "neighbors": "NEIGHBORS", "chat": "GROUP CHAT"}[kind]
            text(ctx, label, 0, 290, 48, "#111111")
        nt = ts + 0.7
        if t > nt:
            with at(ctx, x + 180, 160, s=pop(t, nt), rot=0.2):
                rrect(ctx, -150, -44, 300, 88, 16)
                fill(ctx, "#ff3b3b")
                text(ctx, "DIDN'T NOTICE", 0, 0, 40, "#ffffff")


def spotlight_effect(f):
    ctx, t = f.ctx, f.t
    ctx.set_source(lin_grad(0, 0, 0, H, [(0, "#0b0b14"), (1, "#1a1a2e")]))
    ctx.paint()
    # stage
    ctx.rectangle(0, 760, W, 320)
    ctx.set_source(lin_grad(0, 760, 0, H, [(0, "#5c3d2e"), (1, "#2d1b12")]))
    ctx.fill()
    on = prog(t, 0.2, 0.4)
    G.spotlight(ctx, 960, 0, 900, 560, intensity=on)
    MAX.draw(ctx, 960, 900, 1.0, P(f, "max", arms="shrug" if t > wt(f, 1, "overestimate") else "relaxed",
                                      expr="awkward", sweat=1.0, look=(0, 0.2)))
    # audience: back of heads, all looking at phones
    r = seeded(4)
    for row in range(2):
        for k in range(11):
            x = 60 + k * 180 + (90 if row else 0) + r.random() * 20
            y = 1000 + row * 90
            ctx.save()
            ctx.translate(x, y)
            circle(ctx, 0, 0, 58)
            fill(ctx, "#111118")
            ellipse(ctx, 0, 90, 80, 60)
            fill(ctx, "#111118")
            if t > wt(f, 1, "notice") - 0.5:
                glow(ctx, 30, -20, 70, "#69c8ff", 0.35)
            ctx.restore()
    G.title_slam(ctx, ["THE SPOTLIGHT EFFECT"], t, 0.2, y=110, size=96, colors=("#ffe14d",))


def tshirt_study(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#7209b7", "#2b0547")
    g_t = wt(f, 1, "half")
    a_t = wt(f, 2, "quarter")
    # embarrassing tee icon
    with at(ctx, 330, 470, s=pop(t, 0.2)):
        ctx.move_to(-150, -170)
        ctx.line_to(-60, -200)
        ctx.curve_to(-30, -160, 30, -160, 60, -200)
        ctx.line_to(150, -170)
        ctx.line_to(210, -60)
        ctx.line_to(130, -30)
        ctx.line_to(130, 200)
        ctx.line_to(-130, 200)
        ctx.line_to(-130, -30)
        ctx.line_to(-210, -60)
        ctx.close_path()
        fill(ctx, "#fef9ef", preserve=True)
        stroke(ctx, "#333", 5)
        circle(ctx, 0, 30, 70)
        fill(ctx, "#ffbe0b")
        text(ctx, "CRINGE", 0, 30, 34, "#111")
        text(ctx, "♥ 80s POP ♥", 0, 150, 30, "#ff006e", family="DejaVu Sans", bold=True)
    bars = [("GUESSED", 50, "#ffbe0b", "~50%"), ("ACTUALLY", 25, "#3a86ff", "~25%")]
    if t > g_t - 0.4:
        G.bar_chart(ctx, 1200, 860, bars[:1] if t < a_t - 0.3 else bars, t, g_t - 0.4, h=900, bw=230, gap=140)
    text(ctx, "WHO NOTICED THE SHIRT?", 1200, 120, 64, "#ffffff")


def extras(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#14213d", "#000000", ray_c=(1, 1, 1, 0.03))
    extra_t = wt(f, 1, "extra")
    with ken(f, 1.0, 1.06):
        G.film_strip(ctx, 140, 110, 1640, 860, t, offset=t * 0.5)
        with saved(ctx):
            ctx.rectangle(190, 170, 1540, 740)
            ctx.clip()
            S.park(ctx, t)
            MAX.draw(ctx, 1500, 760, 0.38, P(f, "max", arms="idle", expr="neutral", walk=t * 1.2))
            JAY.draw(ctx, 800, 1260, 1.6, P(f, "jay", arms="arms_up", expr="laugh"))
            G.title_slam(ctx, ["STARRING: JAY"], t, 0.3, y=260, size=90, colors=("#ffe14d",))
    if t > extra_t - 0.2:
        s = pop(t, extra_t - 0.2)
        with at(ctx, 1430, 450, s=s):
            rrect(ctx, -150, -50, 300, 100, 18)
            fill(ctx, "#ff3b3b")
            text(ctx, "EXTRA #4", 0, 0, 50, "#ffffff")
        G.arrow(ctx, 1450, 510, 1505, 650, c="#ff3b3b")


def park_reading(f):
    ctx, t = f.ctx, f.t
    like_t = wt(f, 0, "like")
    with ken(f, 1.0, 1.08, cx=960, cy=640):
        S.park(ctx, t, golden=0.2)
        S.bench(ctx, 960, 980, 1.2)
        MAX.draw(ctx, 960, 980, 1.0, P(f, "max", sit=True, arms="book", held="book",
                                          expr="neutral" if t < like_t else blend_expr("neutral", "content", prog(t, like_t, 0.4)),
                                          look=(0, 0.7)))
    if t > like_t:
        with at(ctx, 1260, 330, s=pop(t, like_t)):
            G.heart(ctx, 0, 0, 1.0, beat_t=t)


def upside_montage(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#52b788", "#1b4332")
    tiles = [("book", "READ A WHOLE BOOK", wt(f, 1, "book")), ("pan", "COOKED REAL FOOD", wt(f, 1, "cooked")),
             ("walk", "LONG WALKS. NO SCREENS.", wt(f, 1, "walks"))]
    top = [("NO NOTIFICATIONS", wt(f, 0, "notifications")), ("NO PRESSURE TO REPLY", wt(f, 0, "pressure"))]
    for i, (msg, ts) in enumerate(top):
        if t > ts:
            with at(ctx, 560 + i * 800, 140, s=pop(t, ts)):
                rrect(ctx, -330, -52, 660, 104, 52)
                fill(ctx, (0, 0, 0, 0.35))
                text(ctx, msg, 0, 0, 52, "#ffffff")
    for i, (kind, label, ts) in enumerate(tiles):
        if t > ts - 0.1:
            s = pop(t, ts - 0.1)
            x = 420 + i * 540
            with at(ctx, x, 520, s=s):
                G.icon_tile(ctx, 0, 0, 1.4, kind, t)
                headline(ctx, label, 0, 220, 46 if len(label) < 18 else 40, color="#ffffff", ow=6)
                G.checkmark(ctx, 110, -110, 0.9, p=prog(t, ts + 0.2, 0.4))


def solitude_science(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#2a9d8f", "#0b3d38")
    p = ease_io(prog(t, wt(f, 0, "solitude"), 2.0))
    G.meter(ctx, 980, 420, "STRESS", 0.85 - 0.55 * p, c="#e63946", w=760)
    G.meter(ctx, 980, 620, "CALM", 0.25 + 0.6 * p, c="#7cf29c", w=760)
    MAX.draw(ctx, 470, 1040, 1.15, P(f, "max", arms="relaxed", expr="content", look=(0, 0)))
    if p > 0.2:
        G.zzz(ctx, 620, 380, t)
    text(ctx, "CHOSEN ALONE TIME", 1360, 180, 72, "#ffffff")


def split_solitude(f):
    ctx, t = f.ctx, f.t
    reveal = wt(f, 0, "lonely")
    with saved(ctx):
        ctx.rectangle(0, 0, W / 2, H)
        ctx.clip()
        with at(ctx, -W / 4, 0):
            S.park(ctx, t, golden=0.3)
        MAX.draw(ctx, W / 4, 980, 1.0, P(f, "max", arms="book", held="book", expr="content", look=(0, 0.7), mouth=0))
        headline(ctx, "SOLITUDE", W / 4, 160, 100, color="#ffe14d")
    with saved(ctx):
        ctx.rectangle(W / 2, 0, W / 2, H)
        ctx.clip()
        with at(ctx, W / 2 - W / 4, 0):
            S.gray_room(ctx, t)
        a = prog(t, reveal - 0.3, 0.4)
        MAX.draw(ctx, W * 3 / 4, 980, 1.0, P(f, "max", arms="relaxed", expr="sad", look=(-0.3, 0.6), mouth=0))
        G.rain_cloud(ctx, W * 3 / 4, 300, 0.6, t)
        with alpha_group(ctx, a):
            headline(ctx, "LONELINESS", W * 3 / 4, 160, 100, color="#8ecae6")
    line(ctx, W / 2, 0, W / 2, H, "#ffffff", 10)


def night_silence(f):
    ctx, t = f.ctx, f.t
    with ken(f, 1.0, 1.12, cx=760, cy=560):
        S.bedroom(ctx, t, night=True, lamp_on=True)
        MAX.draw(ctx, 760, 990, 1.0, P(f, "max", arms="relaxed", expr="sad", look=(0.6, -0.4), sit=False))
    # ticking clock emphasis
    with at(ctx, 1500, 280, s=1.0 + 0.04 * math.sin(t * TAU)):
        S.wall_clock(ctx, 0, 0, 120, 11.5 + t / 3600, t * 60)


def couch_laugh(f):
    ctx, t = f.ctx, f.t
    turn_t = wt(f, 2, "turn")
    gone_t = wt(f, 2, "wasn't")
    with ken(f, 1.0, 1.1, cx=900, cy=600):
        S.gray_room(ctx, t)
        S.couch(ctx, 960, 960, 1.2, c="#577590")
        laughing = wt(f, 2, "laugh") - 0.2 < t < turn_t + 0.4
        expr = "laugh" if laughing else ("neutral" if t < turn_t else blend_expr("laugh", "sad", prog(t, turn_t + 0.3, 0.6)))
        turned = ease_io(prog(t, turn_t, 0.4))
        MAX.draw(ctx, 760, 950, 1.0, P(f, "max", sit=True, arms="phone", held="phone", expr=expr,
                                          facing=turned, look=(turned, 0.0 if turned > 0.5 else 0.6),
                                          bounce=-6 * abs(math.sin(t * 14)) if laughing else 0))
        if t > gone_t:
            with alpha_group(ctx, 0.25 * prog(t, gone_t, 0.6)):
                ctx.push_group()
                JAY.draw(ctx, 1180, 950, 1.0, P(f, "jay", sit=True, arms="relaxed", expr="laugh", mouth=0, shadow=False))
                pat = ctx.pop_group()
                ctx.set_source_rgba(1, 1, 1, 1)
                ctx.mask(pat)
    if t > wt(f, 1, "joke"):
        with at(ctx, 1400, 260, s=pop(t, wt(f, 1, "joke"))):
            G.speech_bubble(ctx, 0, 0, 420, 140, "...to nobody.", size=44)


def loneliness_science(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#3d405b", "#14141f", ray_c=(1, 1, 1, 0.02))
    items = [("sleep", "WORSE SLEEP", wt(f, 0, "sleep")), ("stress", "HIGHER STRESS", wt(f, 0, "stress")),
             ("heart", "HEALTH RISKS", wt(f, 0, "health"))]
    for i, (kind, label, ts) in enumerate(items):
        if t > ts - 0.1:
            with at(ctx, 420 + i * 540, 430, s=pop(t, ts - 0.1)):
                G.icon_tile(ctx, 0, 0, 1.3, kind, t)
                headline(ctx, label, 0, 200, 50, color="#ffffff", ow=6)
    need_t = wt(f, 1, "need") if len(f.shot.lines) > 1 else 999
    if t > wt(f, 1, "wired") - 0.2:
        a = prog(t, wt(f, 1, "wired") - 0.2, 0.3)
        with alpha_group(ctx, a):
            ctx.set_source_rgba(0, 0, 0, 0.6)
            ctx.paint()
            G.heart(ctx, W / 2, 470, 3.0, beat_t=t * 1.1)
            headline(ctx, "CONNECTION IS A", W / 2, 760, 90, color="#ffffff")
            if t > need_t - 0.1:
                with at(ctx, W / 2, 880, s=pop(t, need_t - 0.1)):
                    headline(ctx, "NEED.", 0, 0, 130, color="#ff4d6d")


def jay_snacks(f):
    ctx, t = f.ctx, f.t
    with ken(f, 1.0, 1.06, cx=W / 2, cy=560):
        S.hallway_door(ctx, t)
        drop_t = f.cue_end(0) - 1.0
        jx = 1260
        arms = "point" if t < drop_t else "wave"
        held = "snacks" if t < drop_t else None
        JAY.draw(ctx, jx, 990, 1.05, P(f, "jay", arms=arms if t > 0.6 else "hold_r", held=held, expr="smug" if t < drop_t else "happy",
                                         look=(-0.8, 0)))
        if t > drop_t:
            with at(ctx, 1120, 930):
                rrect(ctx, -30, -84, 60, 84, 8)
                fill(ctx, "#ffb703", preserve=True)
                stroke(ctx, "#b37c00", 3)
                circle(ctx, 0, -44, 16)
                fill(ctx, "#fb5607")


def jay_feed(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#ffb703", "#a05a00")
    msgs = ["day 15: saw a dog that looks exactly like biscuit", "day 16: i made pasta. it's bad.",
            "day 17: still here btw", "day 18: [blurry photo of a sandwich]", "day 19: knock knock",
            "day 19: ...you're supposed to say who's there", "day 20: miss you man"]

    def screen(c, w, h):
        c.set_source_rgb(1, 1, 1)
        c.paint()
        rrect(c, 0, 0, w, 150, 0)
        fill(c, "#f2f2f7")
        circle(c, w / 2, 70, 34)
        fill(c, "#ffb703")
        text(c, "J", w / 2, 70, 36, "#ffffff", family="Inter", bold=True)
        ui_text(c, "Jay", w / 2, 128, 24, "#111", bold=True, align="center")
        n = 1 + int(prog(t, 0.3, f.dur * 0.75) * len(msgs))
        y = 180
        heights = []
        for m in msgs[:n]:
            heights.append(1)
        total_h = 0
        bubbles = []
        for m in msgs[:n]:
            bubbles.append(m)
        # draw from bottom so the newest is visible
        y = 180
        ys = []
        for m in bubbles:
            ys.append(y)
            y += 120
        shift = max(0, y - (h - 40))
        for m, yy in zip(bubbles, ys):
            S.chat_bubble(c, 18, yy - shift, m, size=24, max_w=360)
    with ken(f, 1.0, 1.04):
        S.phone_frame(ctx, 680, 560, 1.0, screen, t, tilt=0.03)
        JAY.draw(ctx, 1450, 1080, 1.2, P(f, "jay", arms="phone2", held="phone", expr="happy", look=(0, 0.5)))
    if t > wt(f, 0, "every"):
        with at(ctx, 1450, 230, s=pop(t, wt(f, 0, "every"))):
            headline(ctx, "EVERY. SINGLE. DAY.", 0, 0, 70, color="#ffffff")


def pancake_door(f):
    ctx, t = f.ctx, f.t
    plates = 1 + int(prog(t, 0.5, f.dur - 1.0) * 9)
    cyc = (t % 2.2) / 2.2
    with ken(f, 1.0, 1.05, cx=W / 2, cy=560):
        S.hallway_door(ctx, t, plates=plates)
        # mom tiptoes in and out each 'morning'
        mx = 300 + math.sin(cyc * math.pi) * 380
        MOM.draw(ctx, mx, 990, 0.98, P(f, "mom", arms="plate", held="plate" if cyc < 0.5 else None,
                                         expr="content" if cyc > 0.5 else "happy", walk=t * 1.5, look=(1, 0)))
    with at(ctx, 1480, 200, s=1.0):
        rrect(ctx, -200, -70, 400, 140, 26)
        fill(ctx, (0, 0, 0, 0.55))
        headline(ctx, f"PLATES: {plates}", 0, 0, 70, color="#ffd166")


def fading_notifs(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#495057", "#212529", ray_c=(1, 1, 1, 0.02))
    names = ["Group chat", "Coworkers", "Gym buddy", "Old roommate", "Group chat 2", "Cousin Dave", "Neighbor", "Fantasy league"]
    for k, nm in enumerate(names):
        fade = prog(t, 0.6 + k * 0.32, 0.6)
        col = k % 4
        x = 300 + col * 440
        y = 300 + (k // 4) * 300
        with alpha_group(ctx, 1 - fade * 0.85), at(ctx, x, y + fade * 40):
            rrect(ctx, -190, -100, 380, 200, 28)
            fill(ctx, (1, 1, 1, 0.92))
            circle(ctx, -110, 0, 46)
            fill(ctx, ("#0a84ff", "#34c759", "#ff9f0a", "#af52de")[col])
            text(ctx, nm, 40, -20, 30, "#111", family="Inter", bold=True)
            text(ctx, "silent" if fade > 0.5 else "typing…", 40, 26, 26, "#777", family="Inter")
            if fade > 0.5:
                G.x_mark(ctx, 150, -80, 0.6, c="#868e96")
    text(ctx, "MESSAGES PER DAY", W / 2, 940, 50, "#ffffff")
    n = int(lerp(87, 3, ease_out(prog(t, 0.6, f.dur - 1))))
    with at(ctx, W / 2 + 330, 940):
        headline(ctx, str(n), 0, 0, 70, color="#ff6b6b")


def biscuit(f):
    ctx, t = f.ctx, f.t
    reveal = f.cue(1)
    talk = f.cue(2) if len(f.shot.lines) > 2 else 999
    with ken(f, 1.0, 1.1, cx=960, cy=640):
        S.bedroom(ctx, t)
        BISCUIT.draw(ctx, 1180, 980, 1.2, t, wag=1.0 + (t > reveal) * 0.5, look=-1, flip=True)
        hug = t > talk - 0.3
        MAX.draw(ctx, 760 if not hug else lerp(760, 860, prog(t, talk - 0.3, 0.4)), 990, 1.0,
                 P(f, "max", arms="hug" if hug else "relaxed", expr="happy" if t > reveal else "neutral",
                   look=(1, 0.3), facing=0.4))
    if t > reveal and t < talk:
        with at(ctx, 1420, 380, s=pop(t, reveal)):
            rrect(ctx, -230, -110, 460, 220, 30)
            fill(ctx, (1, 1, 1, 0.95))
            text(ctx, "BISCUIT", 0, -40, 64, "#c06c00")
            ui_text(ctx, "knows about the challenge: NO", 0, 30, 26, "#333", bold=True, align="center")
            ui_text(ctx, "cares: ALSO NO", 0, 66, 26, "#333", bold=True, align="center")


def biscuit_report(f):
    ctx, t = f.ctx, f.t
    with ken(f, 1.1, 1.2, cx=1000, cy=660):
        S.bedroom(ctx, t)
        BISCUIT.draw(ctx, 1080, 990, 1.2, t, wag=1.6, look=-1, flip=True)
        MAX.draw(ctx, 860, 990, 1.0, P(f, "max", arms="hug", expr="content", look=(1, 0.3), facing=0.4))
    with at(ctx, 1450, 330, s=pop(t, wt(f, 0, "report"))):
        rrect(ctx, -260, -90, 520, 180, 20)
        fill(ctx, "#fff3bf", preserve=True)
        stroke(ctx, "#333", 4)
        text(ctx, "INCIDENT REPORT", 0, -40, 44, "#111")
        ui_text(ctx, "filed by Biscuit: 0", 0, 20, 30, "#333", bold=True, align="center")
        with at(ctx, 140, 50, rot=-0.3):
            rrect(ctx, -90, -26, 180, 52, 8)
            stroke(ctx, "#e63946", 5)
            text(ctx, "DENIED", 0, 0, 36, "#e63946")


def drawer_open(f):
    ctx, t = f.ctx, f.t
    open_p = prog(t, wt(f, 0, "unlocks"), 0.6)
    on_t = wt(f, 0, "back")
    with ken(f, 1.0, 1.3, cx=760, cy=640):
        S.bedroom(ctx, t, night=True, drawer_open=open_p, phone_glow=t > on_t, lamp_on=False)
        MAX.draw(ctx, 980, 990, 1.0, P(f, "max", arms="phone" if t > on_t - 0.4 else "relaxed",
                                          held="phone" if t > on_t - 0.4 else None, expr="worried", look=(-0.6, 0.4)))
    if t > on_t:
        glow(ctx, 1000, 560, 300, "#7fd3ff", 0.35 * prog(t, on_t, 0.3))


def notif_412(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#d00000", "#370617")
    stop_t = wt(f, 1, "stop")
    n = int(412 * ease_out(prog(t, 0.2, wt(f, 0, "notifications") - 0.2)))
    shake = 6 if t < stop_t else 0
    with f.cam(1.0, W / 2, H / 2, shake=shake):
        def screen(c, w, h):
            lockscreen_bg(c, w, h, "#240046", "#3c096c")
            phone_ui_header(c, w, "", t)
            scroll = 0 if t > stop_t else t * 900
            for k in range(14):
                y = 200 + ((k * 116 - scroll) % (14 * 116)) - 116
                col, title, body, ic = NOTIFS[k % len(NOTIFS)]
                S.notif_card(c, 20, y, w - 40, col, title, body, icon_txt=ic)
            if t > stop_t:
                c.set_source_rgba(0, 0, 0, 0.5 * prog(t, stop_t, 0.3))
                c.paint()
                with at(c, w / 2, h / 2, s=pop(t, stop_t)):
                    rrect(c, -210, -60, 420, 120, 26)
                    fill(c, "#ffffff")
                    rrect(c, -190, -38, 76, 76, 18)
                    fill(c, "#af52de")
                    text(c, "V", -152, 0, 40, "#ffffff", family="Inter", bold=True)
                    ui_text(c, "Voicemail", -95, -14, 26, "#111", bold=True)
                    ui_text(c, "Grandma", -95, 20, 26, "#555")
        S.phone_frame(ctx, W / 2, 560, 1.0, screen, t)
        G.notification_badge(ctx, W / 2 + 240, 110, n, s=1.6)


def voicemails(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#1a1a2e", "#000000", ray_c=(1, 1, 1, 0.02))
    many_t = f.cue(1) if len(f.shot.lines) > 1 else 0

    def screen(c, w, h):
        c.set_source_rgb(1, 1, 1)
        c.paint()
        rrect(c, 0, 0, w, 140, 0)
        fill(c, "#f2f2f7")
        ui_text(c, "Voicemail", w / 2, 90, 36, "#111", bold=True, align="center")
        n = 1 if t < many_t else 1 + int(29 * ease_io(prog(t, many_t, 3.2)))
        row_h = 92
        visible = int((h - 160) / row_h)
        first = max(0, n - visible)
        for i, k in enumerate(range(first, n)):
            y = 160 + i * row_h
            circle(c, 46, y + 40, 10)
            fill(c, "#0a84ff")
            ui_text(c, "Grandma", 72, y + 30, 28, "#111", bold=True)
            ui_text(c, f"Day {k + 1}  •  0:{30 + (k * 7) % 29:02d}", 72, y + 64, 22, "#888")
            line(c, 72, y + row_h - 4, w, y + row_h - 4, "#e5e5ea", 2)
    with ken(f, 1.0, 1.06):
        S.phone_frame(ctx, 700, 560, 1.0, screen, t)
    if t > many_t:
        n = 1 + int(29 * ease_io(prog(t, many_t, 3.2)))
        with at(ctx, 1420, 520, s=pop(t, many_t)):
            headline(ctx, str(n), 0, -40, 260, color="#ffb5c8", ow=24)
            headline(ctx, "VOICEMAILS", 0, 130, 70, color="#ffffff")


def grandma_call(f):
    ctx, t = f.ctx, f.t
    with ken(f, 1.0, 1.12, cx=1000, cy=520):
        S.grandma_kitchen(ctx, t)
        GRANDMA.draw(ctx, 980, 980, 1.08, P(f, "grandma", arms="phone_ear", held="phone_dark", expr="content" if not f.talking("grandma") else "happy",
                                               look=(0.3, -0.1), head_tilt=6))
    # sunlight particles
    r = seeded(9)
    for k in range(30):
        x = (r.random() * W + t * 12 * (r.random() + 0.3)) % W
        y = (r.random() * H - t * 8) % H
        circle(ctx, x, y, 2 + r.random() * 3)
        fill(ctx, (1, 0.95, 0.7, 0.25 + 0.2 * math.sin(t + k)))


def max_listening(f):
    ctx, t = f.ctx, f.t
    with f.cam(lerp(1.6, 1.8, ease_io(f.p)), 900, 520):
        S.bedroom(ctx, t, night=True, lamp_on=False, phone_glow=True)
        MAX.draw(ctx, 900, 990, 1.0, P(f, "max", arms="phone_ear", held="phone_dark", expr="cry" if t > 1.2 else "sad",
                                          tears=prog(t, 1.0, 1.0), look=(0, 0.4)))
    glow(ctx, 1100, 360, 260, "#7fd3ff", 0.2)


def lineup(f):
    ctx, t = f.ctx, f.t
    ctx.set_source(rad_grad(W / 2, H * 0.55, 50, W * 0.8, [(0, "#ffd6a5"), (1, "#bc6c25")]))
    ctx.paint()
    few_t = wt(f, 1, "few")
    people = [(MOM, "mom", 520), (GRANDMA, "grandma", 900), (JAY, "jay", 1280)]
    for i, (ch, who, x) in enumerate(people):
        ts = few_t + i * 0.45
        if t > ts:
            s = ease_back(prog(t, ts, 0.4), 2)
            ch.draw(ctx, x, 1000, 1.0 * s, P(f, who, arms="wave" if i == 1 else "relaxed", expr="happy", mouth=0))
    if t > few_t + 1.4:
        BISCUIT.draw(ctx, 1650, 1000, 1.0 * ease_back(prog(t, few_t + 1.4, 0.4), 2), t, wag=1.5, flip=False, look=-1)
    if t < few_t:
        # the crowd fades away
        a = 1 - prog(t, few_t - 0.7, 0.7)
        with alpha_group(ctx, a):
            r = seeded(2)
            for k in range(26):
                x = 80 + (k % 13) * 145
                y = 840 + (k // 13) * 120
                circle(ctx, x, y - 120, 46)
                fill(ctx, (0.3, 0.2, 0.15, 0.6))
                ellipse(ctx, x, y, 70, 70)
                fill(ctx, (0.3, 0.2, 0.15, 0.6))
    if t > wt(f, 1, "knocking") - 0.2:
        G.title_slam(ctx, ["THE ONES WHO KEPT KNOCKING"], t, wt(f, 1, "knocking") - 0.2, y=150, size=80, colors=("#ffffff",))


def call_split(f):
    ctx, t = f.ctx, f.t
    ring_t = wt(f, 0, "call")
    pick = ring_t + 1.6
    with saved(ctx):
        ctx.rectangle(0, 0, W / 2, H)
        ctx.clip()
        with at(ctx, -300, 0):
            S.bedroom(ctx, t)
        MAX.draw(ctx, W / 4, 1100, 1.3, P(f, "max", arms="phone_ear", held="phone_dark",
                                             expr="happy" if f.talking("max") else ("worried" if t < pick else "content"),
                                             tears=0.4 if t > pick else 0, look=(0.6, 0)))
    with saved(ctx):
        ctx.rectangle(W / 2, 0, W / 2, H)
        ctx.clip()
        with at(ctx, W / 2 - 900, 0):
            S.grandma_kitchen(ctx, t)
        if t < pick:
            GRANDMA.draw(ctx, W * 3 / 4, 1100, 1.3, P(f, "grandma", arms="relaxed", expr="neutral", look=(-0.8, -0.2)))
            if t > ring_t:
                for k in range(3):
                    ph = ((t - ring_t) * 1.5 + k / 3) % 1
                    ctx.arc(W * 3 / 4 - 240, 360, 30 + ph * 90, -0.8, 0.8)
                    stroke(ctx, (1, 0.3, 0.3, 1 - ph), 6)
        else:
            GRANDMA.draw(ctx, W * 3 / 4, 1100, 1.3, P(f, "grandma", arms="phone_ear", held="phone_dark",
                                                       expr="laugh" if f.talking("grandma") else "happy", tears=0.6, look=(-0.6, 0)))
    line(ctx, W / 2, 0, W / 2, H, "#ffffff", 10)


def reunion(f):
    ctx, t = f.ctx, f.t
    jay_t = f.cue(1)
    with ken(f, 1.0, 1.05, cx=W / 2, cy=600):
        S.kitchen(ctx, t, warm=1.0)
        S.dining_table(ctx, 1500, 800, 520)
        for k in range(6):
            S.plate_of_pancakes(ctx, 1340 + (k % 3) * 160, 780 - (k // 3) * 40, 0.55, steam=k == 0, t=t)
        MOM.draw(ctx, 560, 990, 1.0, P(f, "mom", arms="hug", expr="content", tears=0.5, look=(1, 0)))
        MAX.draw(ctx, 780, 1000, 1.0, P(f, "max", arms="hug", expr="laugh" if t > jay_t else "happy", look=(-1, 0),
                                          held_l=None, bounce=-4 * abs(math.sin(t * 12)) if t > jay_t else 0))
        jx, ph = walk_x(t, jay_t - 1.0, jay_t + 0.2, 2100, 1080)
        if t > jay_t - 1.0:
            JAY.draw(ctx, jx, 1000, 1.05, P(f, "jay", arms="point_l" if t > jay_t else "relaxed", expr="smug" if not f.talking("jay") else "laugh",
                                             walk=ph, look=(-1, 0), facing=-0.5))


def conclusion(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#ff006e", "#3a0ca3")
    l1 = wt(f, 1, "world")
    l2 = wt(f, 2, "few")
    if t < l1 - 0.3:
        G.title_slam(ctx, ["30 DAYS.", "ZERO REPLIES."], t, 0.1, y=430, size=150)
    elif t < l2 - 0.3:
        G.title_slam(ctx, ["THE WORLD NEEDS YOUR", "ATTENTION LESS", "THAN YOU THINK."], t, l1 - 0.3, y=440, size=110)
    else:
        G.title_slam(ctx, ["BUT A FEW PEOPLE", "REALLY, REALLY DO."], t, l2 - 0.3, y=360, size=130, colors=("#ffffff", "#ffe14d"))
        for i, (ch, who, x) in enumerate(((MOM, "mom", 600), (GRANDMA, "grandma", 960), (JAY, "jay", 1320))):
            ts = l2 + 0.6 + i * 0.25
            if t > ts:
                ch.draw(ctx, x, 1280, 0.9 * ease_back(prog(t, ts, 0.4)), P(f, who, arms="wave", expr="happy", mouth=0, shadow=False))


def cta_text(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#06d6a0", "#035e46")
    msg = "hey :) been thinking about you"
    type_t = wt(f, 0, "text")
    sent_t = wt(f, 2, "wait") if len(f.shot.lines) > 2 else f.dur - 1
    typed = int(len(msg) * prog(t, type_t, 2.2))

    def screen(c, w, h):
        c.set_source_rgb(1, 1, 1)
        c.paint()
        rrect(c, 0, 0, w, 140, 0)
        fill(c, "#f2f2f7")
        ui_text(c, "Someone you miss", w / 2, 90, 30, "#111", bold=True, align="center")
        if t > sent_t - 1.0:
            S.chat_bubble(c, w - 18, 220, msg, me=True, size=30, max_w=360)
            if t > sent_t + 0.3:
                ui_text(c, "Delivered", w - 24, 360, 20, "#888", align="right")
        rrect(c, 16, h - 110, w - 32, 70, 35)
        stroke(c, "#d1d1d6", 3)
        cur = msg[:typed] if t < sent_t - 1.0 else ""
        ui_text(c, cur + ("|" if int(t * 2) % 2 == 0 else ""), 40, h - 75, 26, "#111")
    with ken(f, 1.0, 1.04):
        S.phone_frame(ctx, 620, 560, 1.0, screen, t, tilt=-0.03)
        MAX.draw(ctx, 1420, 1060, 1.15, P(f, "max", arms="crossed" if t > sent_t else "point_l",
                                            expr="smug" if t < sent_t else "happy", look=(-0.6, 0)))
    if t > sent_t:
        tap = math.sin(t * 10)
        with at(ctx, 1500, 260, s=pop(t, sent_t)):
            S.wall_clock(ctx, 0, 0, 90, 3 + t / 60, t * 30)
            headline(ctx, "I'LL WAIT.", 0, 160, 70, color="#ffffff")


def end_card(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#111111", "#000000", ray_c=(1, 0.85, 0.2, 0.04))
    sub_t = wt(f, 0, "subscribe") if f.shot.lines else 1
    # next video tile
    with at(ctx, 1260, 430, s=pop(t, 0.2)):
        rrect(ctx, -380, -220, 760, 440, 24)
        fill(ctx, "#ffbe0b")
        with saved(ctx):
            rrect(ctx, -366, -206, 732, 412, 18)
            ctx.clip()
            S.studio_bg(ctx, t, "#2ec27e", "#0b5d36")
            MAX.draw(ctx, -160, 330, 0.9, P(f, "max", arms="arms_up", expr="laugh", mouth=0, shadow=False))
            headline(ctx, "SAYING YES TO", 150, -60, 64, color="#ffffff")
            headline(ctx, "EVERYTHING", 150, 20, 78, color="#ffe14d")
            headline(ctx, "FOR 30 DAYS", 150, 100, 64, color="#ffffff")
        text(ctx, "NEXT VIDEO", 0, 270, 44, "#ffffff")
    MAX.draw(ctx, 420, 1060, 1.1, P(f, "max", arms="point", expr="happy", look=(1, -0.2)))
    if t > sub_t:
        s = pop(t, sub_t)
        with at(ctx, 1260, 860, s=s * (1 + 0.04 * math.sin(t * 6))):
            rrect(ctx, -240, -60, 480, 120, 22)
            fill(ctx, "#ff0000")
            headline(ctx, "SUBSCRIBE", 0, 0, 70, color="#ffffff", ow=0, shadow=0)
    text(ctx, "Max is fictional. The research is real — sources in the description.", W / 2, H - 40, 26,
         (1, 1, 1, 0.6), family="Inter")


# --------------------------------------------------------------------------
# The script
# --------------------------------------------------------------------------

L = Line
SHOTS = [
    Shot("hook", hook, [L("narrator", "What happens if you ignore everyone... for thirty days?", 0.4)],
         music="upbeat", sfx=[(0.0, "riser", 0.6), ("L0+2.4", "boom", 0.9)], pre=0.3, post=0.6),
    Shot("no_contact", no_contact, [L("narrator", "No texts. No calls. No, hey, how's it going. Nothing.",
                                      caption="No texts. No calls. No “hey, how's it going.” Nothing.")],
         transition="whip", sfx=[("L0+0.2", "pop"), ("L0+0.9", "pop"), ("L0+1.6", "pop"), ("L0e-0.2", "knock", 0.5)]),
    Shot("meet_max", meet_max, [L("narrator", "Meet Max. Max is twenty-six, he replies to every message in under four minutes, and he just agreed to do something insane.")],
         transition="whip", chapter="Meet Max", sfx=[("L0+2.4", "pop"), ("L0+4.0", "pop"), ("L0e-0.6", "boom", 0.6)]),
    Shot("rules", rules, [L("narrator", "The rules are simple. For thirty days, Max can't start a conversation, can't answer one, and can't even nod back.")],
         transition="whip", chapter="The Rules", sfx=[("L0+2.2", "pop"), ("L0+3.6", "pop"), ("L0+5.0", "pop")]),
    Shot("restart", restart, [L("narrator", "If he breaks a single rule, it's back to day one."),
                              L("narrator", "And trust me...", 0.35),
                              L("narrator", "by the end, something happens that nobody saw coming.")],
         transition="pop", sfx=[("L0+1.6", "sad_trombone", 0.5), ("L2", "riser", 0.5), ("L2+1.4", "boom", 0.7)]),
    Shot("day_card_1", day_card(1, "7:00 AM"), [L("narrator", "Day one. Seven A.M.")], transition="flash", day=1,
         chapter="Day 1: The Pancake Incident", sfx=[(0.05, "boom", 0.8)], post=0.4),
    Shot("mom_pancakes", mom_pancakes, [L("mom", "Morning, sweetheart! I made your favorite. Pancakes!", 0.3),
                                        L("narrator", "And Max just... walks right past her.", 0.6),
                                        L("mom", "...Okay then.", 0.2)],
         transition="cut", post=0.6, sfx=[("L2-0.2", "sad_trombone", 0.35)]),
    Shot("cyberball", cyberball, [L("narrator", "Here's the crazy part."),
                                  L("narrator", "Scientists have actually studied what being ignored does to us."),
                                  L("narrator", "In one famous experiment, people played a simple online ball-tossing game, and the other two players secretly stopped throwing them the ball.")],
         transition="whip", music="science", chapter="The Science of Being Ignored"),
    Shot("brain", brain_scan, [L("narrator", "After just a few minutes of being left out, people felt worse, and brain scans showed activity in some of the same areas that respond to physical pain.")],
         transition="whip", sfx=[("L0+3.0", "pop"), ("L0e-1.6", "heartbeat", 0.8)]),
    Shot("mom_alone", mom_alone, [L("narrator", "So when Max walked past those pancakes... it actually hurt. Like, for real.")],
         transition="cut", post=0.6, sfx=[("L0+2.8", "pop", 0.6)]),
    Shot("phone_flood", phone_flood, [L("narrator", "By day three, Max's phone looked like this."),
                                      L("narrator", "Forty-seven unread texts. Twelve missed calls. And one voicemail from his grandma, that he swore he'd listen to later.")],
         transition="whip", day=3, music="curious", chapter="Day 3: The Phone Explodes",
         sfx=[(0.3, "buzz", 0.5), (0.9, "buzz", 0.5), (1.5, "buzz", 0.5), ("L1", "pop"), ("L1+1.6", "pop"), ("L1+3.0", "ding", 0.7)]),
    Shot("jay_door", jay_door, [L("jay", "Bro. Did you die? Blink twice if you've been kidnapped."),
                                L("narrator", "This is Max's best friend, Jay. Jay does not handle silence well.")],
         transition="whip", pre=0.9, sfx=[(0.05, "knock", 0.9)]),
    Shot("office_ask", office_ask, [L("narrator", "Day five. Work. This is where it got... awkward.", 0.3),
                                    L("linda", "Max! Great presentation yesterday. Quick question, can you send me those numbers?")],
         transition="whip", day=5, chapter="Day 5: Work Gets Awkward"),
    Shot("office_statue", office_statue, [L("narrator", "Max can't answer. So he does the only thing he can think of. He becomes... a statue.", 0.9),
                                          L("linda", "...I'll just... email you.", 0.4),
                                          L("narrator", "She emailed him. He didn't answer that either.")],
         sfx=[("L0e-0.3", "tick", 0.8), ("L0e+0.2", "tick", 0.8), ("L0e+0.6", "tick", 0.8), ("L2+0.8", "ding", 0.5),
              ("L2+1.3", "ding", 0.5), ("L2+1.8", "ding", 0.5)]),
    Shot("day_card_7", day_card(7, "NOBODY NOTICED?!"), [L("narrator", "Day seven.")], transition="flash", day=7,
         chapter="Day 7: Did Anyone Even Notice?", sfx=[(0.05, "boom", 0.8)], post=0.5),
    Shot("street", street_walk, [L("narrator", "On day seven, Max noticed something weird. The world... just kept going.")],
         transition="cut", music="curious"),
    Shot("unnoticed", montage_unnoticed, [L("narrator", "The barista didn't notice. His neighbors didn't notice. And his group chat didn't even realize he was gone.")],
         transition="whip", sfx=[("L0", "pop"), ("L0+1.5", "pop"), ("L0+3.0", "pop")]),
    Shot("spotlight", spotlight_effect, [L("narrator", "Psychologists call this the spotlight effect."),
                                         L("narrator", "We massively overestimate how much other people notice us.")],
         transition="fade", chapter="The Spotlight Effect", sfx=[(0.2, "boom", 0.5)]),
    Shot("tshirt", tshirt_study, [L("narrator", "In one study, students had to walk into a room wearing a really embarrassing T-shirt."),
                                  L("narrator", "They guessed about half the room would notice."),
                                  L("narrator", "In reality? It was closer to a quarter.")],
         transition="whip", sfx=[("L1", "riser", 0.4), ("L2+0.8", "boom", 0.5)]),
    Shot("extras", extras, [L("narrator", "Everyone is the main character of their own movie."),
                            L("narrator", "And in most people's movies... Max was just an extra.")],
         transition="whip", post=0.6, sfx=[("L1e-0.4", "laugh_track", 0.6)]),
    Shot("day_card_10", day_card(10, "THE UNEXPECTED UPSIDE"), [L("narrator", "Day ten.")], transition="flash", day=10,
         chapter="Day 10: The Unexpected Upside", sfx=[(0.05, "boom", 0.8)], post=0.5, music="chill"),
    Shot("park", park_reading, [L("narrator", "And then, something unexpected happened. Max started... to like it.")],
         transition="cut", sfx=[("L0e-0.4", "sparkle", 0.6)]),
    Shot("upside", upside_montage, [L("narrator", "No notifications. No pressure to reply."),
                                    L("narrator", "For the first time in years, he read an entire book. He cooked real food. He took long walks without checking a single screen.")],
         transition="whip", sfx=[("L1+1.6", "pop"), ("L1+3.4", "pop"), ("L1+4.8", "pop")]),
    Shot("solitude", solitude_science, [L("narrator", "And research backs this up. Short periods of solitude that you choose can actually help people calm down.")],
         transition="whip"),
    Shot("split", split_solitude, [L("narrator", "But here's the catch. Choosing to be alone... and feeling lonely... are two very different things.")],
         transition="whip", post=0.6, sfx=[("L0+3.4", "boom", 0.5)]),
    Shot("day_card_14", day_card(14, "THE SILENCE GETS LOUD", color="#8ecae6"), [L("narrator", "Day fourteen.")],
         transition="fade", day=14, chapter="Day 14: The Silence Gets Loud", music="lonely", post=0.5),
    Shot("night", night_silence, [L("narrator", "The silence started getting louder.", 0.5)],
         transition="cut", post=0.8, sfx=[(0.3, "tick", 0.6), (1.3, "tick", 0.6), (2.3, "tick", 0.6), (3.3, "tick", 0.6)]),
    Shot("couch", couch_laugh, [L("narrator", "Weekends felt longer."),
                                L("narrator", "When he thought of a joke, it had nowhere to go."),
                                L("narrator", "He'd laugh at a video... and turn to share it with someone who wasn't there.")],
         transition="cut", post=0.8),
    Shot("lonely_science", loneliness_science, [L("narrator", "Scientists who study loneliness have linked it to worse sleep, higher stress, and real long-term health risks."),
                                                L("narrator", "Humans are wired for connection. Not as a bonus... as a need.")],
         transition="whip", chapter="Why Loneliness Hurts", sfx=[("L1+1.4", "heartbeat", 0.9), ("L1+2.4", "heartbeat", 0.9)]),
    Shot("jay_snacks", jay_snacks, [L("jay", "Okay. I get it. You're doing a thing. But I'm still gonna text you every single day. You can't stop me!")],
         transition="whip", day=18, music="curious", chapter="Day 18: The Ones Who Didn't Quit"),
    Shot("jay_feed", jay_feed, [L("narrator", "And he did. Every single day. Memes, terrible jokes, blurry photos of his lunch.")],
         transition="whip", sfx=[(0.6, "pop", 0.5), (1.6, "pop", 0.5), (2.6, "pop", 0.5), (3.6, "pop", 0.5), (4.6, "pop", 0.5)]),
    Shot("pancake_door", pancake_door, [L("narrator", "And every morning, there was a plate of pancakes waiting outside his door. Every. Single. Morning.")],
         transition="whip", post=0.5),
    Shot("fading", fading_notifs, [L("narrator", "Meanwhile, almost everyone else... quietly stopped messaging.")],
         transition="whip", post=0.6),
    Shot("biscuit", biscuit, [L("narrator", "Day twenty-five. Only one living thing in the house had no idea Max was doing a challenge.", 0.3),
                              L("narrator", "Biscuit. Because Biscuit... is a dog.", 0.4),
                              L("max", "Don't tell anyone, buddy.", 0.3)],
         transition="whip", day=25, music="upbeat", chapter="Day 25: Biscuit", sfx=[("L1+1.6", "laugh_track", 0.5)]),
    Shot("biscuit_report", biscuit_report, [L("narrator", "Technically, that's against the rules. Biscuit has chosen not to report it.")],
         transition="cut", sfx=[("L0e-0.3", "pop")]),
    Shot("day_card_30", day_card(30, "THE FINAL DAY", color="#ff6b6b"), [L("narrator", "Day thirty.")], transition="flash",
         day=30, chapter="Day 30: The Twist", music="tension", sfx=[(0.05, "boom", 0.9)], post=0.5),
    Shot("drawer", drawer_open, [L("narrator", "Max unlocks the drawer... and turns his phone back on.", 0.5)],
         transition="fade", sfx=[("L0+1.4", "pop", 0.6), ("L0e", "sparkle", 0.6)]),
    Shot("notif_412", notif_412, [L("narrator", "Four hundred and twelve notifications."),
                                  L("narrator", "But one of them made him stop scrolling.", 0.4)],
         transition="pop", sfx=[(0.1, "buzz", 0.6), (0.6, "buzz", 0.6), (1.1, "buzz", 0.6), (1.6, "buzz", 0.6), ("L1+1.7", "boom", 0.7)]),
    Shot("voicemails", voicemails, [L("narrator", "Remember that voicemail from his grandma? It wasn't one voicemail.", 0.6),
                                    L("narrator", "It was thirty. One for every single day.", 0.6)],
         transition="cut", music="off", post=0.8, sfx=[("L1", "riser", 0.4)]),
    Shot("grandma", grandma_call, [L("grandma", "Hi Maxie, it's Grandma. I know you're busy, honey. You don't have to call me back.", 0.5),
                                   L("grandma", "I just like saying good morning to you.", 0.5)],
         transition="fade", music="emotional", chapter="The Voicemails", post=1.0),
    Shot("max_listening", max_listening, [L("narrator", "She never asked why he wasn't answering. She never got mad. She just... kept showing up.", 0.5)],
         transition="fade", post=1.0),
    Shot("lineup", lineup, [L("narrator", "Max spent thirty days finding out who would notice if he disappeared.", 0.4),
                            L("narrator", "And the answer was never the crowd. It was a few people. Just a few... who never stopped knocking.", 0.5)],
         transition="fade", post=0.8, sfx=[("L1+3.2", "sparkle", 0.5)]),
    Shot("call", call_split, [L("narrator", "So on day thirty-one, the very first thing Max did... was call her.", 1.9),
                              L("grandma", "Maxie?! Oh, there's my favorite voice!", 0.4),
                              L("max", "Hi, Grandma. ...I missed you.", 0.3)],
         transition="fade", day=31, chapter="Day 31", post=1.2, sfx=[("L0e+0.1", "ring", 0.6), ("L0e+1.1", "ring", 0.6)]),
    Shot("reunion", reunion, [L("narrator", "Then he ate the pancakes. All of them. And Jay absolutely roasted him."),
                              L("jay", "Thirty days, man. THIRTY. You owe me, like, four hundred replies!")],
         transition="whip", music="triumph", sfx=[("L1e-0.4", "laugh_track", 0.6)]),
    Shot("conclusion", conclusion, [L("narrator", "So, what happens if you ignore everyone for thirty days?", 0.3),
                                    L("narrator", "You find out the world doesn't need your attention nearly as much as you think."),
                                    L("narrator", "But a few people do. They really, really do.", 0.4)],
         transition="flash", day=0, chapter="What It All Means", sfx=[("L1", "pop"), ("L2", "boom", 0.6)]),
    Shot("cta", cta_text, [L("narrator", "So before you watch another video, text someone you've been leaving on read."),
                           L("narrator", "Seriously. Do it right now."),
                           L("narrator", "I'll wait.", 0.8)],
         transition="whip", post=1.4, sfx=[("L2-0.9", "whoosh", 0.5), ("L2+0.6", "tick"), ("L2+1.1", "tick"), ("L2+1.6", "tick")]),
    Shot("end_card", end_card, [L("narrator", "And if you want to see what happens when Max says YES to everything for thirty days, subscribe. Because that's next.")],
         transition="whip", day=0, post=3.0, sfx=[("L0+4.6", "pop")]),
]

META = {
    "title": "What Happens If You Ignore Everyone for 30 Days?",
    "alt_titles": [
        "I Ignored Everyone for 30 Days (The Ending Got Me)",
        "Ignoring Everyone for 30 Days Taught Me This",
        "30 Days of Ignoring Everyone — Here's What Happened",
    ],
    "description": """Max replies to every text in under 4 minutes. So we made him ignore EVERYONE for 30 days. No texts, no calls, not even a nod. What happened to his mom, his best friend, his boss... and his grandma will surprise you.

This is an animated story — Max is fictional — but the psychology is real: the Cyberball ostracism experiments, the spotlight effect, the benefits of chosen solitude, and what science says about loneliness.

👉 Your challenge: text someone you've been leaving on read. Right now.""",
    "sources": [
        "Williams, K. D., Cheung, C. K. T., & Choi, W. (2000). Cyberostracism: Effects of being ignored over the Internet. Journal of Personality and Social Psychology, 79(5), 748–762.",
        "Eisenberger, N. I., Lieberman, M. D., & Williams, K. D. (2003). Does rejection hurt? An fMRI study of social exclusion. Science, 302(5643), 290–292.",
        "Gilovich, T., Medvec, V. H., & Savitsky, K. (2000). The spotlight effect in social judgment. Journal of Personality and Social Psychology, 78(2), 211–222.",
        "Nguyen, T. T., Ryan, R. M., & Deci, E. L. (2018). Solitude as an approach to affective self-regulation. Personality and Social Psychology Bulletin, 44(1), 92–106.",
        "Holt-Lunstad, J., Smith, T. B., Baker, M., Harris, T., & Stephenson, D. (2015). Loneliness and social isolation as risk factors for mortality. Perspectives on Psychological Science, 10(2), 227–237.",
        "U.S. Surgeon General (2023). Our Epidemic of Loneliness and Isolation: Advisory on the Healing Effects of Social Connection and Community.",
    ],
    "footer": "#psychology #animation #30daychallenge #storytime #humanbehavior",
    "tags": ["ignore everyone for 30 days", "30 day challenge", "psychology", "animated story", "spotlight effect",
             "loneliness", "social experiment animation", "human behavior", "everyday psychology", "storytime animation"],
}


def thumbnail(ctx):
    """1280x720 thumbnail drawn in 1920x1080 units (caller scales)."""
    from types import SimpleNamespace

    S.studio_bg(ctx, 0.3, "#ff2e2e", "#5c0000")
    burst(ctx, 1450, 520, 900, n=22, c1=(1, 1, 1, 0.07), c2=(0, 0, 0, 0), rot=0.1)
    # phone with 412 badge
    def screen(c, w, h):
        lockscreen_bg(c, w, h, "#240046", "#3c096c")
        for k in range(7):
            col, title, body, ic = NOTIFS[k]
            S.notif_card(c, 20, 120 + k * 116, w - 40, col, title, body, icon_txt=ic)
    S.phone_frame(ctx, 1480, 600, 0.95, screen, 0, tilt=0.12)
    G.notification_badge(ctx, 1700, 150, 412, s=2.4)
    pose = Pose(t=0.0, arms="facepalm", expr="shocked", look=(0.8, -0.2), sweat=1.0, blink=0.0)
    MAX.draw(ctx, 700, 1500, 2.15, pose)
    with at(ctx, 560, 170, rot=-0.06):
        headline(ctx, "IGNORED", 0, 0, 190, color="#ffffff", ow=24)
    with at(ctx, 520, 360, rot=-0.06):
        headline(ctx, "EVERYONE", 0, 0, 150, color="#ffe14d", ow=22)
    with at(ctx, 1100, 930, rot=-0.04):
        rrect(ctx, -250, -95, 500, 190, 30)
        fill(ctx, "#ffe14d")
        headline(ctx, "30 DAYS", 0, 0, 150, color="#111111", outline="#ffffff", ow=0, shadow=0)


EPISODE = Episode(
    slug="ignore-everyone-30-days",
    title=META["title"],
    cast={"max": MAX, "mom": MOM, "jay": JAY, "linda": LINDA, "grandma": GRANDMA, "dog": BISCUIT},
    voices=VOICES,
    caption_colors=CAPTION_COLORS,
    shots=SHOTS,
    meta=META,
    thumbnail=thumbnail,
)
