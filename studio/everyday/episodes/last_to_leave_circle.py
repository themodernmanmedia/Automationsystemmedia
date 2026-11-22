"""Episode 2 (blocky world) — "Last To Leave The Circle Wins 1,000,000 Gems!"

An original blocky-voxel take on the elimination-challenge format: 100 players,
a shrinking ring, escalating bribes, a mystery chest, a night round, and a
final briefcase standoff. All characters, art, music and voices are original.

Retention structure (from the challenge-video playbook):
  * 0-30s: the promise from the title/thumbnail is shown immediately, then the
    three escalations are previewed (shrink, lava, bribes).
  * A visible PLAYERS LEFT counter that only ever goes down.
  * A new round / twist roughly every 20-40 seconds.
  * Open loops ("round four is where it gets crazy") before the mid-video dip.
  * A planted setup (Zara's snacks) that pays off emotionally at the end.
"""
from __future__ import annotations

import math
import random

from ..config import H, W
from ..gfx import (
    TAU, alpha_group, at, burst, circle, clamp, ease_back, ease_io, ease_out, fill, glow, headline, lerp,
    lin_grad, pop, prog, rad_grad, rrect, saved, stroke, text, ui_text,
)
from .. import blocky as B
from .. import graphics as G
from .. import sets as S
from ..overlays import _word_times
from ..timeline import Episode, Line, Shot
from ..tts import Voice

# --------------------------------------------------------------------------
# Cast
# --------------------------------------------------------------------------

HOST = B.BlockPerson("host", skin="#ffdbac", shirt="#ff006e", pants="#1b1b1b", hair="#5a3825", hair_style="flat",
                     hat="crown", stripe="#ffd60a")
PIP = B.BlockPerson("pip", skin="#c68642", shirt="#06d6a0", pants="#264653", hair="#111111", hair_style="spiky",
                    stripe="#ffffff", size=0.84, head_scale=1.12)
BRICK = B.BlockPerson("brick", skin="#f1c27d", shirt="#d62828", pants="#2b2d42", hair="#1b1b1b", hair_style="flat",
                      hat="cap", hat_color="#111111", size=1.16)
ZARA = B.BlockPerson("zara", skin="#8d5524", shirt="#8338ec", pants="#3d405b", hair="#ff7b00", hair_style="long",
                     hat="band", hat_color="#ffbe0b")
GUS = B.BlockPerson("gus", skin="#ffdbac", shirt="#ffbe0b", pants="#5e548e", hair="#d9a441", hair_style="tall")
DEX = B.BlockPerson("dex", skin="#e0ac69", shirt="#118ab2", pants="#22223b", hair="#2b1d16", hair_style="side",
                    hat="headset")

VOICES = {
    "host": Voice("am_puck", 1.1),
    "pip": Voice("af_sky", 1.06),
    "brick": Voice("am_onyx", 0.98),
    "zara": Voice("af_nova", 1.04),
    "gus": Voice("bm_lewis", 1.15, lang="en-gb"),
    "dex": Voice("am_echo", 1.08),
}
CAPTION_COLORS = {"host": "#ffffff", "pip": "#7cf2c9", "brick": "#ff8a8a", "zara": "#d0a8ff", "gus": "#ffe066",
                  "dex": "#8fd3ff"}
SEED = {"host": 0.0, "pip": 1.7, "brick": 3.1, "zara": 4.6, "gus": 6.2, "dex": 7.4}
CAST = {"host": HOST, "pip": PIP, "brick": BRICK, "zara": ZARA, "gus": GUS, "dex": DEX}


def BP(f, who, **kw) -> B.BPose:
    kw.setdefault("mouth", f.mouth(who))
    return B.BPose(t=f.gt + SEED[who], seed=SEED[who], **kw)


def wt(f, i: int, word: str, nth: int = 0) -> float:
    ln = f.shot.lines[i]
    words = (ln.caption or ln.text).upper().split()
    a, b = f.shot.line_times[i]
    times = _word_times(words, a, b)
    hits = [k for k, w in enumerate(words) if word.upper() in w]
    return times[hits[min(nth, len(hits) - 1)]][0] if hits else a


# --------------------------------------------------------------------------
# Live players-left counter
# --------------------------------------------------------------------------

def alive_at(ep, gt: float) -> int:
    n = 100
    for sh in ep.shots:
        if sh.start > gt:
            break
        el = getattr(sh, "elim", None)
        if not el:
            continue
        n0, n1, a_spec, d = el
        from ..timeline import resolve_time
        a = sh.start + resolve_time(sh, a_spec)
        if gt < a:
            n = n0
        elif gt < a + d:
            n = int(round(lerp(n0, n1, ease_io((gt - a) / d))))
        else:
            n = n1
    return n


def shot_alive(f):
    return alive_at(f.ep, f.gt)


def hud(ctx, ep, gt, value, since):
    n = alive_at(ep, gt)
    # players left (top-left)
    with at(ctx, 200, 92):
        rrect(ctx, -170, -60, 340, 120, 20)
        fill(ctx, (0, 0, 0, 0.6))
        rrect(ctx, -170, -60, 340, 120, 20)
        stroke(ctx, "#ffd60a", 4)
        text(ctx, "PLAYERS LEFT", 0, -30, 28, "#ffffff")
        headline(ctx, str(n), 0, 18, 70, color="#ff4d4d" if n <= 10 else "#ffd60a", ow=8, shadow=3)
    # prize (top-right)
    with at(ctx, W - 230, 92):
        rrect(ctx, -200, -60, 400, 120, 20)
        fill(ctx, (0, 0, 0, 0.6))
        rrect(ctx, -200, -60, 400, 120, 20)
        stroke(ctx, "#29d3ff", 4)
        B.gem(ctx, -150, 4, 0.7, gt)
        text(ctx, "PRIZE", 40, -30, 28, "#ffffff")
        headline(ctx, "1,000,000", 40, 18, 62, color="#29d3ff", ow=8, shadow=3)


# --------------------------------------------------------------------------
# Shot helpers
# --------------------------------------------------------------------------

def arena_view(f, radius=1.0, lava=0.0, night=0.0, sunset=0.0, leaving=None, zoom=(1.0, 1.06), cx=960, cy=640,
               crowd_kw=None, shake=0.0, draw_extra=None, alive=None):
    ctx, t = f.ctx, f.t
    z = lerp(zoom[0], zoom[1], ease_io(f.p))
    with f.cam(z, cx, cy, shake=shake):
        B.world(ctx, t, night=night, sunset=sunset)
        B.arena(ctx, t, radius=radius, lava=lava, night=night)
        n = shot_alive(f) if alive is None else alive
        lv = leaving or (0, 0, 0.0)
        B.crowd(ctx, t, n, radius=radius, leaving=lv, **(crowd_kw or {}))
        if draw_extra:
            draw_extra(ctx, t)
        if night:
            ctx.set_source_rgba(0.02, 0.03, 0.15, 0.25 * night)
            ctx.paint()


def leaving_from_elim(f):
    """(lo, hi, progress) for players leaving during this shot's elim window."""
    el = getattr(f.shot, "elim", None)
    if not el:
        return None
    n0, n1, a_spec, d = el
    a = f.at(a_spec)
    p = clamp((f.t - a) / (d + 1.2))
    if f.t < a:
        return None
    return (n1, n0, p)


def closeup_bg(f, night=0.0, lava=0.0, radius=1.0, sunset=0.0):
    ctx, t = f.ctx, f.t
    with f.cam(1.9, 960, 700):
        B.world(ctx, t, night=night, sunset=sunset)
        B.arena(ctx, t, radius=radius, lava=lava, night=night)
        if shot_alive(f) > 12:
            B.crowd(ctx, t, min(shot_alive(f), 60), radius=radius, sleep=night > 0.5)
    ctx.set_source_rgba(1, 1, 1, 0.08)
    ctx.paint()
    if night:
        ctx.set_source_rgba(0.02, 0.03, 0.15, 0.35 * night)
        ctx.paint()


def name_tag(ctx, x, y, name, sub, color, t, start):
    s = pop(t, start, 0.35)
    if s <= 0.01:
        return
    with at(ctx, x, y, s=s, rot=-0.04):
        rrect(ctx, -230, -70, 460, 140, 22)
        fill(ctx, color)
        rrect(ctx, -230, -70, 460, 140, 22)
        stroke(ctx, "#111111", 6)
        headline(ctx, name, 0, -14, 70, color="#ffffff", ow=8, shadow=0)
        text(ctx, sub, 0, 40, 28, "#111111")


def round_banner(ctx, t, label, sub, start=0.0, color="#ff3b3b"):
    s = pop(t, start, 0.35)
    if s <= 0.01 or t > start + 3.2:
        return
    a = 1 - prog(t, start + 2.8, 0.4)
    with alpha_group(ctx, a), at(ctx, W / 2, 250, s=s, rot=-0.03):
        rrect(ctx, -420, -80, 840, 160, 26)
        fill(ctx, color)
        rrect(ctx, -420, -80, 840, 160, 26)
        stroke(ctx, "#111111", 7)
        headline(ctx, label, 0, -18, 84, color="#ffffff", ow=9)
        text(ctx, sub, 0, 48, 34, "#111111")


def gems_popup(ctx, t, start, amount, x=W / 2, y=430, color="#29d3ff"):
    s = pop(t, start, 0.4)
    if s <= 0.01:
        return
    with at(ctx, x, y, s=s, rot=-0.04):
        burst(ctx, 0, 0, 420, n=20, c1=(1, 1, 1, 0.12), c2=(0, 0, 0, 0), rot=t * 0.4)
        B.gem(ctx, -0.0, -140, 1.3, t, color)
        headline(ctx, amount, 0, 40, 150, color=color, ow=16)
        headline(ctx, "GEMS", 0, 170, 80, color="#ffffff", ow=9)


def confetti(ctx, t, start, n=120):
    if t < start:
        return
    r = random.Random(11)
    for k in range(n):
        x0 = r.random() * W
        sp = 220 + r.random() * 300
        y = -40 + (t - start) * sp - r.random() * 600
        if y < -40 or y > H + 40:
            continue
        x = x0 + math.sin((t - start) * 3 + k) * 40
        with at(ctx, x, y, rot=(t - start) * 4 + k):
            ctx.rectangle(-9, -6, 18, 12)
            fill(ctx, B.SHIRTS[k % len(B.SHIRTS)])


# --------------------------------------------------------------------------
# Shots
# --------------------------------------------------------------------------

def hook(f):
    ctx, t = f.ctx, f.t
    c1, c2, c3 = f.cue(1), f.cue(2), f.cue(3)
    if t < c1:
        def extra(c, tt):
            B.gem_pile(c, 1720, 1010, 0.95, tt)
        arena_view(f, zoom=(1.18, 1.0), cy=680, draw_extra=extra)
        HOST.draw(ctx, 260, 1180, 2.1, BP(f, "host", arms="point", held="mic", expr="laugh"))
        if t > wt(f, 0, "million") - 0.1:
            gems_popup(ctx, t, wt(f, 0, "million") - 0.1, "1,000,000", x=1250, y=420)
    elif t < c2:
        r = 1.0 - 0.45 * ease_io(prog(t, c1 + 0.2, 1.6))
        arena_view(f, radius=r, zoom=(1.05, 1.15), crowd_kw={"push": 1.0, "expr": "shocked"})
        headline(ctx, "SHRINKING CIRCLE", W / 2, 230, 96, color="#ffd60a")
    elif t < c3:
        arena_view(f, radius=0.55, lava=ease_out(prog(t, c2, 1.0)), zoom=(1.1, 1.2), shake=4,
                   crowd_kw={"panic": 1.0})
        headline(ctx, "LAVA FLOOR", W / 2, 230, 110, color="#ff7b00")
    else:
        closeup_bg(f)
        HOST.draw(ctx, 820, 1300, 2.6, BP(f, "host", arms="hold", held="briefcase", expr="smug"))
        p = pop(t, wt(f, 3, "bribe"))
        if p > 0.01:
            with at(ctx, 1420, 520, s=p, rot=0.05):
                headline(ctx, "BRIBES", 0, 0, 130, color="#7cff6b", ow=14)
    slam = f.dur - 1.5
    if t > slam:
        ctx.set_source_rgba(0, 0, 0, 0.55 * prog(t, slam, 0.2))
        ctx.paint()
        G.title_slam(ctx, ["LAST TO LEAVE", "THE CIRCLE WINS", "1,000,000 GEMS"], t, slam, y=520, size=130,
                     colors=("#ffffff", "#ffffff", "#29d3ff"))


def meet(who, name, sub, color, expr="happy", arms="wave", extra=None):
    def draw(f):
        ctx, t = f.ctx, f.t
        closeup_bg(f)
        ch = CAST[who]
        if who == "host":
            pass
        ch.draw(ctx, 760, 1170, 2.7, BP(f, who, arms=arms if t < 1.6 else "idle", expr=expr,
                                          held="snack" if who == "zara" else None))
        name_tag(ctx, 1420, 520, name, sub, color, t, 0.1)
        if extra:
            extra(f)
    return draw


def host_aside(f):
    ctx, t = f.ctx, f.t
    closeup_bg(f)
    HOST.draw(ctx, 960, 1170, 2.7, BP(f, "host", arms="point_l", held="mic", expr="smug"))
    ZARA.draw(ctx, 380, 1180, 1.5, BP(f, "zara", arms="hold", held="snack", expr="happy", mouth=0))


def rules(f):
    ctx, t = f.ctx, f.t
    go = wt(f, 0, "go")
    arena_view(f, zoom=(1.0, 1.08), crowd_kw={"expr": "determined"})
    if t < wt(f, 0, "three") - 0.1:
        items = [("ONE STEP OUT = OUT", wt(f, 0, "leaves")), ("LAST ONE WINS", wt(f, 0, "last"))]
        for i, (msg, ts) in enumerate(items):
            if t > ts - 0.1:
                G.rule_card(ctx, 470, 300 + i * 150, i + 1, msg, prog(t, ts - 0.1, 0.5))
    else:
        for k, word in enumerate(("THREE", "TWO", "ONE")):
            ts = wt(f, 0, word)
            nxt = wt(f, 0, ("TWO", "ONE", "GO")[k])
            if ts <= t < nxt:
                with at(ctx, W / 2, 420, s=pop(t, ts, 0.3)):
                    headline(ctx, str(3 - k), 0, 0, 340, color="#ffd60a", ow=30)
        if t >= go:
            with at(ctx, W / 2, 420, s=pop(t, go, 0.3), rot=-0.05):
                headline(ctx, "GO!", 0, 0, 300, color="#7cff6b", ow=30)


def round1(f):
    ctx, t = f.ctx, f.t
    lv = leaving_from_elim(f)
    arena_view(f, leaving=lv, zoom=(1.0, 1.1), cy=700)
    round_banner(ctx, t, "ROUND 1", "the bribe", 0.0)
    if t > wt(f, 0, "ten", 1):
        gems_popup(ctx, t, wt(f, 0, "ten", 1), "10,000", x=1500, y=470, color="#7cff6b")


def pip_scoff(f):
    ctx, t = f.ctx, f.t
    closeup_bg(f)
    PIP.draw(ctx, 820, 1170, 2.9, BP(f, "pip", arms="shrug", expr="smug", look=0.4))
    B.gem(ctx, 1450, 420, 1.6, t)


def round2(f):
    ctx, t = f.ctx, f.t
    sh0 = f.cue(0) + 0.6
    r = 1.0 - 0.28 * ease_io(prog(t, sh0, 2.2))
    lv = leaving_from_elim(f)
    arena_view(f, radius=r, leaving=lv, zoom=(1.0, 1.12), crowd_kw={"push": 1.0, "expr": "angry"}, shake=2 if t > sh0 else 0)
    round_banner(ctx, t, "ROUND 2", "the circle shrinks", 0.0, color="#ffbe0b")


def brick_push(f):
    ctx, t = f.ctx, f.t
    closeup_bg(f, radius=0.72)
    shove = f.cue(0) + 0.3 < t < f.cue(1)
    BRICK.draw(ctx, 620 + (40 if shove else 0), 1170, 2.6, BP(f, "brick", arms="out" if shove else "idle", expr="angry", look=1))
    PIP.draw(ctx, 1260 + (80 * ease_out(prog(t, f.cue(0) + 0.3, 0.3)) if t < f.cue(1) else 80), 1170, 2.6,
             BP(f, "pip", arms="panic" if t < f.cue(1) else "point_l", expr="shocked" if t < f.cue(1) else "angry", look=-1,
                tilt=-8 if shove else 0))


def rehook(f):
    ctx, t = f.ctx, f.t
    closeup_bg(f, radius=0.72)
    HOST.draw(ctx, 960, 1170, 2.7, BP(f, "host", arms="hold", held="mic", expr="smug", look=0.3))
    if t > wt(f, 0, "four"):
        with at(ctx, 1500, 420, s=pop(t, wt(f, 0, "four")), rot=0.06):
            rrect(ctx, -200, -70, 400, 140, 24)
            fill(ctx, "#ff3b3b")
            headline(ctx, "ROUND 4 ?!", 0, 0, 80, color="#ffffff", ow=8)


def round3(f):
    ctx, t = f.ctx, f.t
    lv_t = wt(f, 0, "lava")
    lava = ease_out(prog(t, lv_t, 1.6))
    arena_view(f, radius=0.72, lava=lava, leaving=leaving_from_elim(f), zoom=(1.0, 1.1),
               crowd_kw={"panic": lava}, shake=3 * lava)
    round_banner(ctx, t, "ROUND 3", "the floor is lava", 0.0, color="#ff7b00")


def gus_quits(f):
    ctx, t = f.ctx, f.t
    closeup_bg(f, lava=1.0, radius=0.72)
    gone = f.cue_end(0) + 0.2
    if t < gone:
        GUS.draw(ctx, 960, 1170, 2.7, BP(f, "gus", arms="panic", expr="scared", sweat=1.0, look=math.sin(t * 6)))
    else:
        p = prog(t, gone, 0.5)
        for k in range(10):
            a = k * TAU / 10
            ctx.rectangle(960 + math.cos(a) * 300 * p - 20, 700 + math.sin(a) * 200 * p - 20, 40, 40)
            fill(ctx, (1, 1, 1, 1 - p))
        headline(ctx, "GUS: OUT", W / 2, 520, 120, color="#ff4d4d")


def chest_shot(f):
    ctx, t = f.ctx, f.t
    dex_go = f.cue(2)
    open_t = f.cue(3)

    def extra(c, tt):
        B.chest(c, 960, 470, 0.75, tt, open_=ease_out(prog(tt, open_t, 0.6)))
        if tt > dex_go:
            x = lerp(960, 900, ease_io(prog(tt, dex_go, 1.6)))
            y = lerp(780, 500, ease_io(prog(tt, dex_go, 1.6)))
            DEX.draw(c, x, y, 0.75, BP(f, "dex", arms="cheer" if tt > open_t else "idle", expr="laugh" if tt > open_t else "happy",
                                         walk=None if tt > dex_go + 1.6 else tt * 2.5))
    lv = leaving_from_elim(f)
    arena_view(f, radius=0.72, lava=1.0, leaving=lv, zoom=(1.0, 1.05), cy=600, draw_extra=extra,
               crowd_kw={"expr": "shocked" if t > open_t else "neutral"})
    round_banner(ctx, t, "ROUND 4", "the mystery chest", 0.0, color="#8338ec")
    if t > open_t + 0.3:
        gems_popup(ctx, t, open_t + 0.3, "100,000", x=W / 2, y=560)


def copycats(f):
    ctx, t = f.ctx, f.t
    lv = leaving_from_elim(f)
    arena_view(f, radius=0.72, lava=1.0, leaving=lv, zoom=(1.05, 1.0))
    no_t = wt(f, 1, "no")
    if t > no_t:
        with at(ctx, W / 2, 360, s=pop(t, no_t), rot=-0.04):
            rrect(ctx, -460, -80, 920, 160, 26)
            fill(ctx, "#111111")
            headline(ctx, "THERE WAS NO OTHER CHEST", 0, 0, 70, color="#ff4d4d", ow=6)


def night_round(f):
    ctx, t = f.ctx, f.t
    nf = ease_io(prog(t, 0.0, 2.5))
    r = 0.72 - 0.30 * ease_io(prog(t, f.cue(0) + 1.5, 2.5))
    arena_view(f, radius=r, lava=1.0, night=nf, sunset=1 - nf, leaving=leaving_from_elim(f), zoom=(1.0, 1.12),
               crowd_kw={"sleep": t > f.cue(1)})
    round_banner(ctx, t, "ROUND 5", "night falls", 0.2, color="#3a0ca3")
    if t > f.cue(1):
        for k in range(4):
            ph = (t * 0.6 + k / 4) % 1
            text(ctx, "Z", 700 + k * 160 + ph * 40, 500 - ph * 120, 50 + k * 6, (1, 1, 1, 1 - ph))


def snacks(f):
    ctx, t = f.ctx, f.t
    closeup_bg(f, night=1.0, lava=1.0, radius=0.42)
    give = f.cue(0) + 0.4
    PIP.draw(ctx, 1240, 1170, 2.6, BP(f, "pip", arms="hold" if t > give + 0.6 else "hug",
                                        held="snack" if t > give + 0.6 else None,
                                        expr="happy" if t > f.cue(1) else "sad", look=-1,
                                        bounce=math.sin(t * 30) * 2 if t < give else 0))
    ZARA.draw(ctx, 660, 1170, 2.6, BP(f, "zara", arms="point" if give - 0.2 < t < give + 0.6 else "idle",
                                        held="snack" if t < give + 0.6 else None, expr="happy", look=1))
    glow(ctx, 960, 600, 500, "#ffb36b", 0.18)


def sunrise(f):
    ctx, t = f.ctx, f.t
    nf = 1 - ease_io(prog(t, 0.0, 2.0))
    r = 0.42 - 0.2 * ease_io(prog(t, f.cue(1), 2.0))
    arena_view(f, radius=r, lava=1.0, night=nf, sunset=nf * 0.5, leaving=leaving_from_elim(f), zoom=(1.0, 1.3),
               cy=700, crowd_kw={"push": 1.0, "expr": "determined"}, shake=2)
    round_banner(ctx, t, "ROUND 6", "the size of a table", f.cue(1), color="#ff006e")


def zara_out(f):
    ctx, t = f.ctx, f.t
    closeup_bg(f, lava=1.0, radius=0.22)
    shove = f.cue(0) + 0.8
    zx = 1300 + 260 * ease_out(prog(t, shove, 0.6))
    BRICK.draw(ctx, 560, 1170, 2.4, BP(f, "brick", arms="out" if shove < t < shove + 0.8 else "idle", expr="smug", look=1))
    PIP.draw(ctx, 900, 1170, 2.3, BP(f, "pip", arms="panic" if t > shove else "idle", expr="shocked" if t > shove else "determined", look=1))
    ZARA.draw(ctx, zx, 1170, 2.4, BP(f, "zara", arms="panic" if t > shove else "idle", expr="sad" if t > shove + 0.6 else "shocked",
                                       tilt=18 * prog(t, shove, 0.4), tears=prog(t, shove + 1.0, 0.5)))
    if t > f.cue(1):
        with at(ctx, W / 2, 330, s=pop(t, f.cue(1))):
            headline(ctx, "ZARA IS OUT!", 0, 0, 110, color="#ff4d4d")


def final_offer(amount_idx):
    amounts = ["50,000", "100,000", "250,000", "500,000"]

    def draw(f):
        ctx, t = f.ctx, f.t
        closeup_bg(f, lava=1.0, radius=0.22)
        brick_t = f.cue(-1)
        brick_out = amount_idx == 3 and t > f.cue_end(-1) - 0.3
        HOST.draw(ctx, 960, 1190, 2.2, BP(f, "host", arms="hold", held="briefcase", expr="smug" if amount_idx < 3 else "laugh"))
        bx = 420 - (300 * ease_out(prog(t, f.cue_end(-1) - 0.3, 0.8)) if brick_out else 0)
        BRICK.draw(ctx, bx, 1170, 2.3, BP(f, "brick", arms="cheer" if brick_out else ("shrug" if amount_idx >= 2 else "idle"),
                                           expr=("laugh" if brick_out else ("determined", "smug", "scared", "shocked")[amount_idx]),
                                           sweat=1.0 if amount_idx >= 2 else 0, look=0.5,
                                           walk=t * 2.5 if brick_out else None))
        PIP.draw(ctx, 1520, 1170, 2.2, BP(f, "pip", arms="idle", expr="determined", look=-0.6))
        with at(ctx, W / 2, 330, s=pop(t, f.cue(0) + 0.6), rot=-0.04):
            burst(ctx, 0, 0, 320, n=18, c1=(1, 1, 1, 0.1), c2=(0, 0, 0, 0), rot=t * 0.5)
            B.gem(ctx, -0, -90, 1.0, t, "#7cff6b")
            headline(ctx, amounts[amount_idx], 0, 40, 130, color="#7cff6b", ow=14)
        if brick_out:
            with at(ctx, W / 2, 620, s=pop(t, f.cue_end(-1) - 0.3), rot=0.05):
                headline(ctx, "DEAL!", 0, 0, 170, color="#ffd60a", ow=18)
    return draw


def winner(f):
    ctx, t = f.ctx, f.t
    closeup_bg(f, lava=0.0, radius=0.22)
    glow(ctx, 960, 700, 700, "#ffd60a", 0.35)
    jump = -abs(math.sin(t * 7)) * 60 if t < f.cue(1) else 0
    PIP.draw(ctx, 960, 1170, 2.9, BP(f, "pip", arms="cheer" if t < f.cue(1) else "idle",
                                       expr="laugh" if t < f.cue(1) else "happy", bounce=jump, tears=0.6))
    confetti(ctx, t, 0.0)
    if t < f.cue(1):
        G.title_slam(ctx, ["PIP WINS!"], t, wt(f, 0, "won"), y=260, size=150, colors=("#ffd60a",))


def match(f):
    ctx, t = f.ctx, f.t
    closeup_bg(f, radius=0.22)
    zara_t = f.cue(1)
    HOST.draw(ctx, 520, 1170, 2.4, BP(f, "host", arms="point" if t > wt(f, 0, "match") else "idle", held=None,
                                        expr="happy", look=1))
    PIP.draw(ctx, 980, 1170, 2.2, BP(f, "pip", arms="cheer" if t > zara_t else "idle", expr="happy", look=1))
    ZARA.draw(ctx, 1450, 1170, 2.4, BP(f, "zara", arms="cheer" if t > zara_t else "idle", expr="laugh" if t > zara_t else "shocked",
                                         tears=0.7 if t > zara_t else 0, look=-1))
    if t > wt(f, 0, "two"):
        gems_popup(ctx, t, wt(f, 0, "two"), "200,000", x=1450, y=360, color="#d0a8ff")
    confetti(ctx, t, zara_t)


def pip_dream(f):
    ctx, t = f.ctx, f.t
    sunset = 0.6
    with f.cam(lerp(1.0, 1.06, f.p), 960, 600):
        B.sky(ctx, t, sunset=sunset)
        B.hills(ctx, t)
        B.ground(ctx, t)
        # dream house of blocks, built up over time
        built = prog(t, f.cue(1), 3.0)
        cols, rows = 9, 6
        k = 0
        for r_ in range(rows):
            for c_ in range(cols):
                k += 1
                if k / (cols * rows) > built:
                    continue
                x = 1100 + c_ * 70
                y = 760 - r_ * 70
                kind = "plank" if r_ < 5 else "gold"
                if r_ in (1, 2) and c_ in (2, 6):
                    kind = "water"
                B.block_face(ctx, kind, x, y, 70, int(t * 4))
                ctx.rectangle(x, y, 70, 70)
                stroke(ctx, (0, 0, 0, 0.25), 2)
        if built > 0.98:
            B.gem(ctx, 1415, 300, 1.2, t)
    PIP.draw(ctx, 520, 1250, 2.4, BP(f, "pip", arms="point" if t > f.cue(1) else "idle", expr="happy", look=1))


def end_card(f):
    ctx, t = f.ctx, f.t
    S.studio_bg(ctx, t, "#0b3d91", "#020b24", ray_c=(1, 1, 1, 0.05))
    with at(ctx, 1260, 430, s=pop(t, 0.2)):
        rrect(ctx, -400, -230, 800, 460, 24)
        fill(ctx, "#29d3ff")
        with saved(ctx):
            rrect(ctx, -386, -216, 772, 432, 18)
            ctx.clip()
            ctx.translate(-386, -216)
            ctx.scale(772 / W, 432 / H)
            B.sky(ctx, t)
            # floating island
            for c_ in range(-4, 5):
                for r_ in range(0, 4 - abs(c_) // 2):
                    B.block_face(ctx, "grass_side" if r_ == 0 else "dirt", 960 + c_ * 100 - 50, 560 + r_ * 100, 100)
            BRICK.draw(ctx, 860, 560, 1.4, B.BPose(t=t, arms="panic", expr="scared"))
            PIP.draw(ctx, 1080, 560, 1.4, B.BPose(t=t + 1, arms="cheer", expr="laugh"))
        headline(ctx, "LAST TO LEAVE THE", 0, 270, 48, color="#ffffff", ow=6)
        headline(ctx, "FLOATING ISLAND", 0, 330, 60, color="#ffd60a", ow=7)
    HOST.draw(ctx, 420, 1080, 2.0, BP(f, "host", arms="point", held="mic", expr="happy"))
    sub_t = wt(f, 0, "subscribe")
    if t > sub_t:
        with at(ctx, 1260, 900, s=pop(t, sub_t) * (1 + 0.04 * math.sin(t * 6))):
            rrect(ctx, -240, -60, 480, 120, 22)
            fill(ctx, "#ff0000")
            headline(ctx, "SUBSCRIBE", 0, 0, 70, color="#ffffff", ow=0, shadow=0)


# --------------------------------------------------------------------------
# Script
# --------------------------------------------------------------------------

L = Line


def E(shot, n0, n1, start, d):
    shot.elim = (n0, n1, start, d)
    return shot


SHOTS = [
    Shot("hook", hook, [
        L("host", "One hundred players. One circle. And the last one to leave it wins one million gems!", 0.25),
        L("host", "But every round, the circle gets smaller...", 0.1),
        L("host", "the floor turns into lava...", 0.1),
        L("host", "and I'm going to try to bribe every single one of them to quit.", 0.2)],
        music="upbeat", pre=0.2, post=2.0, day=1,
        sfx=[("L0+3.2", "boom", 0.8), ("L1", "whoosh", 0.6), ("L2", "boom", 0.6), ("L3", "whoosh", 0.6),
             ("end-1.5", "boom", 0.9)]),
    Shot("meet_pip", meet("pip", "PIP", "smallest player", "#06d6a0", arms="wave"),
         [L("host", "Before we start, meet a few of the players."), L("pip", "I'm Pip, and I'm not leaving. Ever.")],
         transition="whip", chapter="Meet The Players", day=1, sfx=[("L1", "pop")]),
    Shot("meet_brick", meet("brick", "BRICK", "never lost a game", "#d62828", expr="smug", arms="cheer"),
         [L("brick", "I'm Brick. I've never lost a game in my life.")], transition="whip", day=1, sfx=[(0.1, "pop")]),
    Shot("meet_zara", meet("zara", "ZARA", "brought snacks", "#8338ec", arms="hold"),
         [L("zara", "I'm Zara. And I brought snacks.")], transition="whip", day=1, sfx=[(0.1, "pop")]),
    Shot("aside", host_aside, [L("host", "Zara might be the smartest player here.")], transition="cut", day=1,
         sfx=[("L0e-0.3", "laugh_track", 0.5)]),
    Shot("rules", rules, [L("host", "The rules are simple. If any part of you leaves the circle, you're out. The last player standing wins the million. Three... two... one... go!")],
         transition="whip", chapter="The Rules", day=1,
         sfx=[("L0+2.0", "pop"), ("L0+4.0", "pop"), ("L0e-2.6", "tick"), ("L0e-1.7", "tick"), ("L0e-0.9", "tick"),
              ("L0e-0.2", "boom", 0.9)]),
    E(Shot("round1", round1, [L("host", "Round one! The first ten players to leave right now get ten thousand gems each.", 0.4),
                              L("host", "Okay, that was fast. Like, really fast.")],
           transition="whip", chapter="Round 1: The Bribe", day=1,
           sfx=[(0.1, "boom", 0.6), ("L0e-0.6", "pop"), ("L0e", "whoosh", 0.7), ("L1-0.3", "laugh_track", 0.4)]),
      100, 90, "L0e-0.1", 1.2),
    Shot("pip_scoff", pip_scoff, [L("pip", "Ten thousand? I'm here for a million.")], transition="cut", day=1),
    E(Shot("round2", round2, [L("host", "Round two! The circle is shrinking!", 0.3),
                              L("host", "One toe over the line, and you're out.")],
           transition="whip", chapter="Round 2: The Circle Shrinks", day=1,
           sfx=[(0.1, "boom", 0.6), ("L0+0.6", "riser", 0.6), ("L1", "pop"), ("L1+0.6", "pop"), ("L1+1.2", "pop")]),
      90, 72, "L0+1.2", 2.6),
    Shot("brick_push", brick_push, [L("brick", "Move it, little guy!", 0.2), L("pip", "Hey! I was here first!")],
         transition="cut", day=1, sfx=[("L0+0.3", "whoosh", 0.6)]),
    Shot("rehook", rehook, [L("host", "Seventy-two players left. And trust me... round four is where things get crazy.")],
         transition="whip", day=1, sfx=[("L0e-0.8", "riser", 0.5)]),
    E(Shot("round3", round3, [L("host", "Round three. I hope nobody's scared of lava.", 0.3),
                              L("host", "Tap out, and you're teleported to safety. But you lose the million.")],
           transition="whip", chapter="Round 3: The Floor Is Lava", music="tension", day=1,
           sfx=[(0.1, "boom", 0.6), ("L0e-0.4", "boom", 0.8), ("L1+1.0", "pop"), ("L1+1.6", "pop"), ("L1+2.2", "pop")]),
      72, 51, "L1", 3.0),
    Shot("gus", gus_quits, [L("gus", "Nope. Nope! I'm out! I am so out!", 0.4)], transition="cut", day=1,
         sfx=[("L0e+0.2", "pop", 0.9), ("L0e+0.25", "laugh_track", 0.5)], post=0.8),
    E(Shot("chest", chest_shot, [L("host", "Round four. Out there is a mystery chest. One player can leave the circle and take whatever's inside.", 0.2),
                                 L("host", "It could be one gem... or it could be a lot more.", 0.2),
                                 L("dex", "I'm taking it!", 1.6),
                                 L("host", "One hundred thousand gems!")],
           transition="whip", chapter="Round 4: The Mystery Chest", music="curious", day=1,
           sfx=[(0.1, "boom", 0.6), ("L2", "whoosh", 0.6), ("L3-0.6", "riser", 0.5), ("L3", "sparkle", 0.9), ("L3+0.1", "boom", 0.7)]),
      51, 50, "L2+0.3", 0.4),
    E(Shot("copycats", copycats, [L("host", "And now twelve more players quit, hoping there's another chest.", 0.3),
                                  L("host", "There was no other chest.")],
           transition="cut", day=1, sfx=[("L0+1.0", "whoosh", 0.5), ("L1", "sad_trombone", 0.6)]),
      50, 38, "L0+0.6", 1.8),
    E(Shot("night", night_round, [L("host", "Night falls. It's cold, it's dark, and the circle shrinks again.", 0.3),
                                  L("host", "Some players fell asleep... and literally sleepwalked out of the circle.")],
           transition="fade", chapter="Round 5: Night", music="lonely", day=1,
           sfx=[("L0+1.5", "riser", 0.4), ("L1+2.0", "pop", 0.5), ("L1+2.6", "pop", 0.5), ("L1+3.2", "pop", 0.5)]),
      38, 12, "L1+1.0", 3.5),
    Shot("snacks", snacks, [L("zara", "Here. You look hungry.", 0.4), L("pip", "Thanks, Zara. I owe you one.", 0.4)],
         transition="cut", day=1, post=0.8),
    E(Shot("sunrise", sunrise, [L("host", "By sunrise, only twelve players are left.", 0.2),
                                L("host", "And the circle is now the size of a kitchen table!")],
           transition="fade", chapter="Round 6: Tiny Circle", music="tension", day=1,
           sfx=[("L1", "boom", 0.6), ("L1+1.2", "pop"), ("L1+1.8", "pop"), ("L1+2.4", "pop")]),
      12, 3, "L1+0.8", 2.6),
    E(Shot("zara_out", zara_out, [L("brick", "Sorry, Zara. Nothing personal.", 0.9), L("host", "Zara is out! And then there were two.")],
           transition="whip", day=1, sfx=[("L0e+0.3", "whoosh", 0.7), ("L1", "boom", 0.6)]),
      3, 2, "L0e+0.4", 0.4),
    Shot("offer1", final_offer(0), [L("host", "Brick. Pip. This briefcase has fifty thousand gems. Leave right now, and it's yours.", 0.2),
                                    L("brick", "Not a chance.")],
         transition="whip", chapter="The Final Offer", music="upbeat", day=1, sfx=[("L0+1.2", "pop")]),
    Shot("offer2", final_offer(1), [L("host", "One hundred thousand.", 0.2), L("pip", "Nope.")], transition="cut", day=1,
         sfx=[(0.6, "pop")]),
    Shot("offer3", final_offer(2), [L("host", "Two hundred and fifty thousand!", 0.3), L("brick", "Hmm...", 0.3)],
         transition="cut", day=1, sfx=[(0.6, "pop"), ("L1", "heartbeat", 0.8)]),
    E(Shot("offer4", final_offer(3), [L("host", "Final offer. Five hundred thousand gems.", 0.6), L("brick", "...Deal. I'm out!")],
           transition="pop", day=1, post=1.0, sfx=[("L0", "riser", 0.6), ("L1e-0.3", "boom", 0.9)]),
      2, 1, "L1e", 0.3),
    Shot("winner", winner, [L("host", "Pip! You just won one million gems!", 0.4),
                            L("pip", "Wait. Can I give some to Zara? She gave me her snacks last night.")],
         transition="flash", chapter="The Winner", music="triumph", day=1, sfx=[(0.1, "boom", 0.9), ("L0+1.0", "sparkle", 0.8)]),
    Shot("match", match, [L("host", "You know what? I'll match it. Zara gets two hundred thousand too!", 0.3),
                          L("zara", "No way! No way!")],
         transition="whip", music="emotional", day=1, sfx=[("L0+2.4", "sparkle", 0.8)]),
    Shot("dream", pip_dream, [L("host", "Pip, what are you going to do with a million gems?", 0.3),
                              L("pip", "Build the biggest house in the world. With a room for everybody.", 0.6)],
         transition="fade", day=1, post=1.2),
    Shot("end_card", end_card, [L("host", "And subscribe, because next time, it's last to leave the floating island!")],
         transition="whip", music="upbeat", day=0, post=3.0, sfx=[("L0+0.8", "pop")]),
]

META = {
    "title": "Last To Leave The Circle Wins 1,000,000 Gems!",
    "alt_titles": [
        "100 Players vs 1 Shrinking Circle For 1,000,000 Gems!",
        "I Bribed 100 Players To Quit... Last One Wins 1,000,000!",
        "Last To Leave The Lava Circle Wins 1,000,000 Gems!",
    ],
    "description": """100 players. 1 shrinking circle. The last one to leave wins 1,000,000 gems! But every round the circle gets smaller, the floor turns to lava, and I try to bribe every player to quit. Who would YOU bet on: Pip, Brick or Zara?

In this Last To Leave The Circle challenge, 100 blocky players battle through 6 rounds: a 10,000-gem bribe, a shrinking circle, the floor is lava, a mystery chest, a night round, and a final briefcase standoff worth 500,000 gems. Stay to the end for the twist.

Comment who you think wins BEFORE the end. Subscribe for the next one: Last To Leave The Floating Island!""",
    "sources": [],
    "footer": "#LastToLeave #Challenge #Animation",
    "tags": [
        "last to leave", "last to leave circle", "last to leave the circle wins", "last to leave wins",
        "100 players", "100 players challenge", "1000000 challenge", "challenge video", "elimination challenge",
        "floor is lava", "lava challenge", "shrinking circle", "mystery chest", "bribe challenge",
        "block world animation", "blocky animation", "animated challenge", "challenge animation",
        "who will win", "last one standing",
    ],
}


def thumbnail(ctx):
    from ..gfx import burst as _burst
    t = 0.5
    B.sky(ctx, t)
    B.hills(ctx, t)
    B.ground(ctx, t, "lava", frame=3)
    glow(ctx, W / 2, H, 1100, "#ff6a00", 0.45)
    # tiny safe circle
    with at(ctx, 0, 300):
        B.arena(ctx, t, radius=0.42, lava=1.0)
    PIP.draw(ctx, 900, 1260, 3.3, B.BPose(t=t, arms="panic", expr="shocked", blink=0.0, sweat=1.0, look=0.6))
    B.gem_pile(ctx, 1560, 1060, 2.6, t)
    with at(ctx, 1450, 170, rot=0.05):
        headline(ctx, "1,000,000", 0, 0, 180, color="#29d3ff", ow=24)
    with at(ctx, 1450, 345, rot=0.05):
        headline(ctx, "GEMS", 0, 0, 150, color="#ffffff", ow=20)


EPISODE = Episode(
    slug="last-to-leave-circle",
    title=META["title"],
    cast=CAST,
    voices=VOICES,
    caption_colors=CAPTION_COLORS,
    shots=SHOTS,
    meta=META,
    thumbnail=thumbnail,
    hud=hud,
)


# --------------------------------------------------------------------------
# Thumbnail variants for YouTube "Test & Compare" (A/B/C)
#   A  "the prize"     : one shocked kid on a tiny circle in lava + giant number
#   B  "100 vs 1"      : before/after contrast, no words beyond two numbers
#   C  "the bribe"     : temptation — sweating player vs open case of gems
# Rules applied: one focal subject, readable at 160px wide, max 3 words,
# saturated complementary colours (lava orange vs gem cyan), clear emotion,
# a question the title doesn't answer.
# --------------------------------------------------------------------------


def thumbnail_b(ctx):
    t = 0.5
    # left: full circle of 100
    with saved(ctx):
        ctx.rectangle(0, 0, W / 2, H)
        ctx.clip()
        with at(ctx, -480, 0, s=1.0):
            B.world(ctx, t)
            B.arena(ctx, t, radius=1.0)
            B.crowd(ctx, t, 100, radius=1.0, expr="happy")
    # right: one player, tiny circle, lava everywhere
    with saved(ctx):
        ctx.rectangle(W / 2, 0, W / 2, H)
        ctx.clip()
        with at(ctx, W / 2 - 480, 0):
            B.sky(ctx, t)
            B.hills(ctx, t)
            B.ground(ctx, t, "lava", frame=3)
            glow(ctx, 960, 900, 900, "#ff6a00", 0.5)
            B.arena(ctx, t, radius=0.26, lava=1.0)
            PIP.draw(ctx, 960, 1000, 2.6, B.BPose(t=t, arms="cheer", expr="laugh", blink=0.0))
    ctx.rectangle(W / 2 - 8, 0, 16, H)
    fill(ctx, "#ffffff")
    with at(ctx, 480, 190, rot=-0.04):
        headline(ctx, "100", 0, 0, 230, color="#ffffff", ow=26)
    with at(ctx, 1440, 190, rot=0.04):
        headline(ctx, "1", 0, 0, 260, color="#ffd60a", ow=28)
    G.arrow(ctx, 760, 820, 1180, 820, c="#ffd60a", w=26)


def thumbnail_c(ctx):
    t = 0.5
    B.sky(ctx, t)
    B.hills(ctx, t)
    B.ground(ctx, t, "lava", frame=5)
    glow(ctx, 1300, 700, 900, "#29d3ff", 0.35)
    # open case overflowing with gems
    with at(ctx, 1320, 930):
        ctx.rectangle(-330, -230, 660, 230)
        fill(ctx, "#5c3a1e", preserve=True)
        stroke(ctx, "#2b1a0d", 10)
        ctx.rectangle(-330, -560, 660, 300)
        fill(ctx, "#3e2612", preserve=True)
        stroke(ctx, "#2b1a0d", 10)
    B.gem_pile(ctx, 1320, 800, 3.0, t)
    BRICK.draw(ctx, 520, 1500, 3.4, B.BPose(t=t, arms="shrug", expr="shocked", look=1, sweat=1.0, blink=0.0))
    with at(ctx, 1330, 170, rot=0.04):
        headline(ctx, "TAKE IT", 0, 0, 170, color="#ffffff", ow=22)
    with at(ctx, 1330, 340, rot=0.04):
        headline(ctx, "OR STAY?", 0, 0, 150, color="#7cff6b", ow=20)


THUMBNAILS = {"A_prize": thumbnail, "B_100_vs_1": thumbnail_b, "C_bribe": thumbnail_c}
