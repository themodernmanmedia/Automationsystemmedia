"""Episode 4 — "Last To Leave The Circle Wins 1,000,000 Gems!" with 3D humans (cinematic renderer).

Same script and shot list as the voxel 3D episode; art style switched to engine_hd + humans3d.


Same challenge as the 2D blocky version, rebuilt in 3D (OpenGL) and extended to
~3.5 minutes with extra beats modelled on the real-world challenge format:
a consolation prize for the very first quitter, a skill side-challenge whose
failure shrinks the circle, a comfort temptation at night (beds outside the
ring), escalating final offers, and a planted payoff.
"""
from __future__ import annotations

import math

from ..config import H, W
from ..gfx import alpha_group, at, burst, clamp, ease_io, ease_out, fill, glow, headline, lerp, pop, prog, rrect, stroke, text
from .. import blocky as B2
from .. import graphics as G
from .. import humans3d as W3
from ..engine_hd import DAY, NIGHT, SUNSET, Env, Scene, blit, renderer
from ..engine3d import RY, T
from ..world3d import Style as _Style, Pose as _Pose
from ..timeline import Episode, Line, Shot
from ..tts import Voice
from .last_to_leave_circle import (CAPTION_COLORS, E, VOICES, alive_at, confetti, gems_popup, hud, name_tag,
                                   round_banner, wt)

# --------------------------------------------------------------------------
# Cast (3D styles)
# --------------------------------------------------------------------------

HOST = _Style("host", skin="#ffdbac", shirt="#ff006e", pants="#1b1b1b", hair="#5a3825", hat="crown", stripe="#ffd60a")
PIP = _Style("pip", skin="#c68642", shirt="#06d6a0", pants="#264653", hair="#111111", hair_style="spiky",
               stripe="#ffffff", size=0.84, head=1.12)
BRICK = _Style("brick", skin="#f1c27d", shirt="#d62828", pants="#2b2d42", hair="#1b1b1b", hat="cap",
                 hat_color="#111111", size=1.14)
ZARA = _Style("zara", skin="#8d5524", shirt="#8338ec", pants="#3d405b", hair="#ff7b00", hair_style="long",
                hat="band", hat_color="#ffbe0b")
GUS = _Style("gus", skin="#ffdbac", shirt="#ffbe0b", pants="#5e548e", hair="#d9a441", hair_style="tall")
DEX = _Style("dex", skin="#e0ac69", shirt="#118ab2", pants="#22223b", hair="#2b1d16", hair_style="side", hat="headset")
STYLES = {"host": HOST, "pip": PIP, "brick": BRICK, "zara": ZARA, "gus": GUS, "dex": DEX}
SEED = {"host": 0.0, "pip": 1.7, "brick": 3.1, "zara": 4.6, "gus": 6.2, "dex": 7.4}

# named players stand in the clear front pocket of the crowd (unit-disk coords)
SPOT = {"pip": (-0.12, 0.62), "brick": (0.16, 0.66), "zara": (-0.38, 0.5), "gus": (0.4, 0.5), "dex": (0.02, 0.42)}
HOST_POS = (0.0, 19.6)

R0 = 12.0


def ring_at(gt: float) -> float:
    """Ring radius over the whole video (driven by shot attributes)."""
    r = R0
    for sh in EPISODE.shots:
        if sh.start > gt:
            break
        rs = getattr(sh, "ring", None)
        if rs:
            r0, r1, a_spec, d = rs
            from ..timeline import resolve_time
            a = sh.start + resolve_time(sh, a_spec)
            r = r0 if gt < a else lerp(r0, r1, ease_io((gt - a) / d)) if gt < a + d else r1
    return r


def P(f, who, **kw) -> W3.Pose:
    kw.setdefault("mouth", f.mouth(who))
    return _Pose(t=f.gt + SEED[who], seed=SEED[who], **kw)


def spot(who, radius):
    u, v = SPOT[who]
    return u * radius * 0.86, v * radius * 0.86


# --------------------------------------------------------------------------
# Scene assembly
# --------------------------------------------------------------------------


def base_scene(f, radius=None, lava=0.0, crowd=True, crowd_kw=None, named=("pip", "brick", "zara", "gus", "dex"),
               named_pose=None, host=True, host_pose=None, cam_pos=None, leaving=True, gems=True, clear=None):
    sc = Scene()
    t = f.gt
    radius = ring_at(f.gt) if radius is None else radius
    W3.build_world(sc, t, radius, lava)
    alive = alive_at(f.ep, f.gt)
    if crowd:
        lv = (0, 0, 0.0)
        el = getattr(f.shot, "elim", None)
        if el and leaving:
            n0, n1, a_spec, d = el
            a = f.at(a_spec)
            if f.t >= a:
                lv = (n1, n0, clamp((f.t - a) / (d + 1.4)))
        kw = dict(crowd_kw or {})
        n_generic = alive if alive > 12 else max(0, alive - 3)
        if alive <= 12 and lv[2] > 0:
            lv = (max(0, lv[0] - 3), max(0, lv[1] - 3), lv[2])
        W3.crowd(sc, t, n_generic, radius, leaving=lv, cam_pos=cam_pos, clear=clear, **kw)
    named_pose = named_pose or {}
    survivors = {"pip", "brick", "zara"} if alive >= 3 else {"pip", "brick"}
    for who in named:
        if who not in named_pose and alive <= 12 and who not in survivors:
            continue
        x, z = spot(who, radius)
        yaw, pose = named_pose.get(who, (0.0, None))
        pose = pose or P(f, who, mouth=0.0)
        W3.person(sc, STYLES[who], x, z, yaw, pose)
    if host:
        hp = host_pose or P(f, "host", arms="hold", held="mic", expr="happy")
        W3.person(sc, HOST, HOST_POS[0], HOST_POS[1], math.pi, hp)
    if gems:
        W3.gem_pile(sc, 0, 0, -21.5, t)
    return sc


def env_for(f, kind="day", k=1.0):
    if kind == "day":
        return DAY
    if kind == "sunset":
        return Env.blend(DAY, SUNSET, k)
    if kind == "night":
        return Env.blend(SUNSET, NIGHT, k)
    if kind == "dawn":
        return Env.blend(NIGHT, DAY, k)
    return DAY


def shoot(f, sc, eye0, tgt0, eye1=None, tgt1=None, env=DAY, fov=55.0, shake=0.0, ease=True, dof=None):
    p = ease_io(f.p) if ease else f.p
    eye1 = eye1 or eye0
    tgt1 = tgt1 or tgt0
    eye = [lerp(a, b, p) for a, b in zip(eye0, eye1)]
    tgt = [lerp(a, b, p) for a, b in zip(tgt0, tgt1)]
    # subtle handheld drift + optional shake
    hx = math.sin(f.gt * 0.7) * 0.05 + math.sin(f.gt * 23) * shake
    hy = math.cos(f.gt * 0.9) * 0.04 + math.cos(f.gt * 19) * shake
    eye = (eye[0] + hx, eye[1] + hy, eye[2])
    dist = math.dist(eye, tgt)
    if dof is None:
        dof = 0.45 if dist < 5.0 else 0.0
    img = renderer().render(sc, eye, tgt, env, f.gt, fov=fov * 0.92, dof=dof)
    blit(f.ctx, img)


def closeup_cam(x, z, yaw, dist=3.2, h=1.65, side=0.0, look_h=1.5):
    # humans: tighter, eye-level framing (waist-up)
    dist, side, h, look_h = dist * 0.62, side * 0.62, h * 1.02 + 0.05, look_h + 0.12
    dx, dz = math.sin(yaw), math.cos(yaw)
    eye = (x + dx * dist + dz * side, h, z + dz * dist - dx * side)
    return eye, (x, look_h, z)


def host_close(f, pose, dist=2.8, side=0.6, env=DAY, radius=None, lava=0.0, **kw):
    sc = base_scene(f, radius=radius, lava=lava, host_pose=pose, cam_pos=(0, 2, 22), **kw)
    hx, hz = HOST_POS
    e0, t0 = closeup_cam(hx, hz, math.pi, dist + 0.3, 1.9, side, 1.7)
    e1, t1 = closeup_cam(hx, hz, math.pi, dist, 1.8, side * 0.7, 1.7)
    shoot(f, sc, e0, t0, e1, t1, env=env)


def player_close(f, who, pose, dist=3.0, side=-0.5, env=DAY, lava=0.0, radius=None, others=None, h=1.55, **kw):
    radius = ring_at(f.gt) if radius is None else radius
    np_ = dict(others or {})
    np_[who] = (0.0, pose)
    x, z = spot(who, radius)
    sc = base_scene(f, radius=radius, lava=lava, named_pose=np_, cam_pos=None, clear=(x + side * 0.6, z + dist * 0.6), **kw)
    k = STYLES[who].size
    e0, t0 = closeup_cam(x, z, 0.0, dist + 0.25, h * k + 0.1, side, 1.45 * k)
    e1, t1 = closeup_cam(x, z, 0.0, dist, h * k, side * 0.8, 1.45 * k)
    shoot(f, sc, e0, t0, e1, t1, env=env)


# --------------------------------------------------------------------------
# Shots
# --------------------------------------------------------------------------


def hook(f):
    ctx, t = f.ctx, f.t
    c1, c2, c3 = f.cue(1), f.cue(2), f.cue(3)
    if t < c1:
        # drone sweep from above the prize toward the host
        sc = base_scene(f, radius=R0, host_pose=P(f, "host", arms="point", held="mic", expr="laugh"), cam_pos=(0, 14, 30))
        shoot(f, sc, (-22, 16, -30), (0, 1, -10), (6, 7, 28), (0, 1.5, 4), fov=60)
        if t > wt(f, 0, "million") - 0.1:
            gems_popup(ctx, t, wt(f, 0, "million") - 0.1, "1,000,000", x=1450, y=420)
    elif t < c2:
        r = R0 - 5.5 * ease_io(prog(t, c1 + 0.1, 1.8))
        sc = base_scene(f, radius=r, crowd_kw={"push": 1.0, "expr": "shocked"}, cam_pos=(0, 20, 0))
        shoot(f, sc, (0, 24, 10), (0, 0, 0), (0, 18, 8), (0, 0, 0), fov=60)
        headline(ctx, "SHRINKING CIRCLE", W / 2, 200, 96, color="#ffd60a")
    elif t < c3:
        lava = ease_out(prog(t, c2 - 0.2, 1.4))
        sc = base_scene(f, radius=6.5, lava=lava, crowd_kw={"panic": 1.0}, cam_pos=(0, 8, 14))
        shoot(f, sc, (14, 6, 12), (0, 0, 0), (10, 4, 9), (0, 0.5, 0), env=DAY, fov=58)
        headline(ctx, "THE FLOOR IS LAVA", W / 2, 200, 100, color="#ff7b00")
    else:
        host_close(f, P(f, "host", arms="hold", held="briefcase", expr="smug"), dist=3.0, side=0.8)
        if t > wt(f, 3, "bribe"):
            with at(ctx, 1500, 430, s=pop(t, wt(f, 3, "bribe")), rot=0.05):
                headline(ctx, "BRIBES", 0, 0, 130, color="#7cff6b", ow=14)
    slam = f.dur - 1.5
    if t > slam:
        ctx.set_source_rgba(0, 0, 0, 0.55 * prog(t, slam, 0.2))
        ctx.paint()
        G.title_slam(ctx, ["LAST TO LEAVE", "THE CIRCLE WINS", "1,000,000 GEMS"], t, slam, y=520, size=130,
                     colors=("#ffffff", "#ffffff", "#29d3ff"))


def meet(who, name, sub, color, arms="wave", expr="happy", held=None, side=-0.6):
    def draw(f):
        t = f.t
        player_close(f, who, P(f, who, arms=arms if t < 1.8 else "idle", expr=expr, held=held), side=side)
        name_tag(f.ctx, 1430, 520, name, sub, color, t, 0.1)
    return draw


def aside(f):
    host_close(f, P(f, "host", arms="point", held="mic", expr="smug"))


def rules(f):
    ctx, t = f.ctx, f.t
    sc = base_scene(f, crowd_kw={"expr": "determined"}, cam_pos=(0, 6, 22),
                    host_pose=P(f, "host", arms="point" if t > wt(f, 0, "three") else "hold", held="mic", expr="happy"))
    shoot(f, sc, (0, 4.5, 24), (0, 1, 0), (0, 3.2, 18), (0, 1, 4))
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
        go = wt(f, 0, "go")
        if t >= go:
            with at(ctx, W / 2, 420, s=pop(t, go, 0.3), rot=-0.05):
                headline(ctx, "GO!", 0, 0, 300, color="#7cff6b", ow=30)


def round1(f):
    ctx, t = f.ctx, f.t
    sc = base_scene(f, cam_pos=(0, 14, 24))
    shoot(f, sc, (-18, 12, 20), (0, 0, 2), (-8, 16, 24), (0, 0, 0), fov=58)
    round_banner(ctx, t, "ROUND 1", "the bribe", 0.0)
    if t > wt(f, 0, "ten", 1):
        gems_popup(ctx, t, wt(f, 0, "ten", 1), "10,000", x=1500, y=470, color="#7cff6b")


def pip_scoff(f):
    player_close(f, "pip", P(f, "pip", arms="shrug", expr="smug"), dist=2.6)


def golden_house(f):
    ctx, t = f.ctx, f.t
    build = prog(t, f.cue(0) + 1.2, 1.6)
    sc = base_scene(f, crowd_kw={"expr": "shocked" if t > f.cue(0) + 2 else "neutral"}, cam_pos=(10, 4, 18),
                    named_pose={"brick": (0.0, P(f, "brick", arms="panic" if f.talking("brick") else "idle",
                                                  expr="shocked" if t > f.cue(0) + 2 else "neutral"))})
    W3.golden_house(sc, 9.0, 18.0, f.gt, built=build, yaw=-0.6)
    W3.person(sc, W3.crowd_people()[95][0], 7.0, 20.5, -0.6, P(f, "pip", arms="cheer", expr="laugh", mouth=0))
    if t < f.cue(1):
        shoot(f, sc, (2, 3, 27), (8, 2, 18), (0, 3.2, 26), (7, 2, 18))
    else:
        x, z = spot("brick", R0)
        e, tg = closeup_cam(x, z, 0.0, 2.8, 1.8, 0.6, 1.65)
        shoot(f, sc, e, tg)
    if t > f.cue(0) + 2.6 and t < f.cue(1):
        with at(ctx, 1450, 300, s=pop(t, f.cue(0) + 2.6), rot=0.05):
            headline(ctx, "GOLDEN HOUSE!", 0, 0, 100, color="#ffd60a", ow=12)


def archery(f):
    ctx, t = f.ctx, f.t
    shoot_t = f.cue(2) + 0.2
    r = ring_at(f.gt)
    bx, bz = spot("brick", r)
    tx, tz = 0.0, -17.0
    sc = base_scene(f, named_pose={"brick": (math.pi, P(f, "brick", arms="bow", held="bow",
                                                        expr="determined" if t < shoot_t + 0.8 else "shocked"))},
                    cam_pos=(bx, 3, bz + 4), clear=(bx + 1.5, bz + 2.5))
    W3.target(sc, tx, 2.2, tz, 0.0)
    # arrow flight (misses wide, splashes into the hills)
    if t > shoot_t:
        q = clamp((t - shoot_t) / 0.9)
        ax = lerp(bx, 6.5, q)
        az = lerp(bz - 0.6, tz - 4, q)
        ay = 1.6 + math.sin(q * math.pi) * 2.4 + q * 0.4
        yaw = math.atan2(6.5 - bx, (tz - 4) - (bz - 0.6))
        W3.arrow(sc, T(ax, ay, az) @ RY(yaw))
    if t < f.cue(1):
        shoot(f, sc, (bx + 2.5, 2.2, bz + 3.5), (bx, 1.6, bz), (bx + 1.8, 2.0, bz + 2.8), (bx, 1.7, bz))
    elif t < shoot_t + 0.1:
        shoot(f, sc, (bx + 2.2, 2.6, bz + 3.0), (tx, 2.0, tz), (bx + 1.8, 2.5, bz + 2.6), (tx, 2.2, tz), fov=45)
    else:
        shoot(f, sc, (bx + 2.2, 2.6, bz + 2.8), (3, 2.4, tz - 2), (bx + 2.2, 2.6, bz + 2.8), (5, 2.0, tz - 3), fov=50)
    round_banner(ctx, t, "ROUND 2", "hit it or the circle shrinks", 0.0, color="#ffbe0b")
    if t > f.cue(3):
        with at(ctx, W / 2, 330, s=pop(t, f.cue(3)), rot=-0.04):
            headline(ctx, "MISSED!", 0, 0, 150, color="#ff4d4d", ow=16)


def shrink(f):
    ctx = f.ctx
    sc = base_scene(f, crowd_kw={"push": 1.0, "expr": "angry"}, cam_pos=(0, 20, 6))
    shoot(f, sc, (0, 26, 8), (0, 0, 0), (0, 20, 6), (0, 0, 0), fov=60, shake=0.03)
    round_banner(ctx, f.t, "CIRCLE SHRINKS", "one toe over = out", 0.0, color="#ffbe0b")


def brick_push(f):
    t = f.t
    shove = f.cue(0) + 0.3 < t < f.cue(1)
    r = ring_at(f.gt)
    others = {"brick": (0.6, P(f, "brick", arms="out" if shove else "idle", expr="angry"))}
    pip_pose = P(f, "pip", arms="panic" if t < f.cue(1) else "point_l", expr="shocked" if t < f.cue(1) else "angry",
                 roll=0.2 if shove else 0.0)
    player_close(f, "pip", pip_pose, dist=3.4, side=-0.9, others=others)


def rehook(f, text_="ROUND 4 ?!"):
    ctx, t = f.ctx, f.t
    host_close(f, P(f, "host", arms="hold", held="mic", expr="smug"), dist=3.0, side=-0.6)
    key = wt(f, 0, "four") if "four" in f.shot.lines[0].text else wt(f, 0, "smartest")
    if t > key:
        with at(ctx, 1500, 420, s=pop(t, key), rot=0.06):
            rrect(ctx, -230, -70, 460, 140, 24)
            fill(ctx, "#ff3b3b")
            headline(ctx, text_, 0, 0, 74, color="#ffffff", ow=8)


def round3(f):
    ctx, t = f.ctx, f.t
    lava = ease_out(prog(t, wt(f, 0, "lava") - 0.3, 2.2))
    sc = base_scene(f, lava=lava, crowd_kw={"panic": lava, "teleport": True}, cam_pos=(14, 6, 12))
    shoot(f, sc, (16, 9, 16), (0, 0, 0), (12, 5, 11), (0, 0.5, 0), fov=58, shake=0.04 * lava)
    round_banner(ctx, t, "ROUND 3", "the floor is lava", 0.0, color="#ff7b00")


def gus_quits(f):
    ctx, t = f.ctx, f.t
    gone = f.cue_end(0) + 0.2
    r = ring_at(f.gt)
    gx, gz = spot("gus", r)
    if t < gone:
        player_close(f, "gus", P(f, "gus", arms="panic", expr="scared", sweat=1.0, eye_x=math.sin(t * 6)),
                     lava=1.0, dist=2.6, side=0.6)
    else:
        sc = base_scene(f, lava=1.0, named=("pip", "brick", "zara", "dex"))
        W3.poof(sc, gx, 1.2, gz, prog(t, gone, 0.8), f.gt)
        e, tg = closeup_cam(gx, gz, 0.0, 2.6, 1.55, 0.6, 1.45)
        shoot(f, sc, e, tg)
        with at(ctx, W / 2, 420, s=pop(t, gone + 0.2)):
            headline(ctx, "GUS: OUT", 0, 0, 120, color="#ff4d4d")


def chest_shot(f):
    ctx, t = f.ctx, f.t
    dex_go = f.cue(2)
    open_t = f.cue(3)
    cx, cz = 0.0, -15.0
    r = ring_at(f.gt)
    dx0, dz0 = spot("dex", r)
    # Dex runs across the lava on a bridge of blocks that appears for him
    named = {"dex": (math.pi, P(f, "dex", arms="cheer" if t > open_t else "idle", expr="laugh" if t > open_t else "happy",
                                 walk=(f.gt * 2.4) if dex_go < t < dex_go + 2.2 else None))}
    sc = base_scene(f, lava=1.0, named_pose=named, named=("pip", "brick", "zara"),
                    crowd_kw={"expr": "shocked" if t > open_t else "neutral"}, cam_pos=(0, 5, 0))
    q = ease_io(prog(t, dex_go, 2.2))
    px, pz = lerp(dx0, cx, q), lerp(dz0, cz + 1.4, q)
    if t > dex_go:
        for k in range(int(abs(cz + 1.4 - dz0))):
            sc.block(-0.5, -1, int(dz0) - k - 1, "plank")
    W3.person(sc, DEX, px, pz, math.pi, named["dex"][1])
    W3.chest(sc, cx, cz, f.gt, open_=ease_out(prog(t, open_t, 0.6)), yaw=0.0, y=0.0)
    for k in range(-1, 2):
        for kk in range(-1, 2):
            sc.block(cx - 0.5 + k, -1, cz - 0.5 + kk, "stone")
    if t < dex_go:
        shoot(f, sc, (6, 6, 12), (0, 0.5, -6), (4, 5, 9), (0, 0.5, -9), fov=55)
    elif t < open_t:
        shoot(f, sc, (4, 3.5, pz + 5), (px, 1.2, pz - 2), (3, 3, cz + 5), (cx, 0.8, cz))
    else:
        shoot(f, sc, (2.4, 1.9, cz + 3.2), (cx, 0.9, cz), (1.8, 1.7, cz + 2.6), (cx, 1.0, cz), fov=50)
        gems_popup(ctx, t, open_t + 0.3, "100,000", x=W / 2, y=520)
    round_banner(ctx, t, "ROUND 4", "the mystery chest", 0.0, color="#8338ec")


def copycats(f):
    ctx, t = f.ctx, f.t
    sc = base_scene(f, lava=1.0, crowd_kw={"teleport": True}, cam_pos=(0, 10, 18))
    shoot(f, sc, (-10, 9, 16), (0, 0, 0), (-6, 7, 14), (0, 0.5, 0))
    no_t = wt(f, 1, "no")
    if t > no_t:
        with at(ctx, W / 2, 330, s=pop(t, no_t), rot=-0.04):
            rrect(ctx, -460, -80, 920, 160, 26)
            fill(ctx, "#111111")
            headline(ctx, "THERE WAS NO OTHER CHEST", 0, 0, 70, color="#ff4d4d", ow=6)


def night_round(f):
    ctx, t = f.ctx, f.t
    nk = ease_io(prog(t, 0.0, 2.6))
    env = Env.blend(SUNSET, NIGHT, nk) if nk > 0 else SUNSET
    sc = base_scene(f, lava=1.0, crowd_kw={"sleep": t > f.cue(1)}, cam_pos=(0, 10, 18))
    # beds on stone pads outside the ring
    for k in range(10):
        a = math.pi * 0.15 + k * 0.17
        x, z = math.cos(a) * 16.5, -math.sin(a) * 16.5
        for dx in (0, 1):
            for dz in (-1, 0, 1):
                sc.block(int(x) + dx - 1, -1, int(z) + dz, "stone")
        W3.bed(sc, x, z, yaw=a, color=("#e63946", "#3a86ff", "#06d6a0")[k % 3])
    shoot(f, sc, (-14, 11, 18), (2, 0, -4), (-9, 8, 15), (3, 0, -6), env=env)
    round_banner(ctx, t, "ROUND 5", "night falls", 0.2, color="#3a0ca3")


def snacks(f):
    t = f.t
    give = f.cue(0) + 0.4
    zara_pose = P(f, "zara", arms="point" if give - 0.2 < t < give + 0.6 else "idle", held="snack" if t < give + 0.6 else None,
                  expr="happy", look_yaw=0.5)
    pip_pose = P(f, "pip", arms="hold" if t > give + 0.6 else "hug", held="snack" if t > give + 0.6 else None,
                 expr="happy" if t > f.cue(1) else "sad", look_yaw=-0.5, bounce=math.sin(t * 30) * 0.01 if t < give else 0)
    player_close(f, "pip", pip_pose, dist=3.6, side=-1.2, env=NIGHT, lava=1.0, others={"zara": (0.4, zara_pose)})


def sunrise(f):
    ctx, t = f.ctx, f.t
    env = Env.blend(NIGHT, DAY, ease_io(prog(t, 0.0, 2.4)))
    sc = base_scene(f, lava=1.0, crowd_kw={"push": 1.0, "expr": "determined"}, cam_pos=(0, 8, 8))
    shoot(f, sc, (0, 14, 14), (0, 0, 0), (0, 7, 7), (0, 0, 0), env=env, shake=0.03)
    round_banner(ctx, t, "ROUND 6", "the size of a table", f.cue(1), color="#ff006e")


def zara_out(f):
    ctx, t = f.ctx, f.t
    shove = f.cue(0) + 0.8
    r = ring_at(f.gt)
    zx, zz = spot("zara", r)
    out = ease_out(prog(t, shove, 0.6))
    named = {
        "brick": (0.5, P(f, "brick", arms="out" if shove < t < shove + 0.8 else "idle", expr="smug")),
        "pip": (0.0, P(f, "pip", arms="panic" if t > shove else "idle", expr="shocked" if t > shove else "determined")),
        "zara": (0.0, P(f, "zara", arms="panic" if t > shove else "idle", expr="sad" if t > shove + 0.6 else "shocked",
                         roll=-0.35 * out, tears=prog(t, shove + 1.0, 0.5))),
    }
    sc = base_scene(f, lava=1.0, named_pose={k: v for k, v in named.items() if k != "zara"}, named=("pip", "brick"))
    if t < shove + 1.0:
        W3.person(sc, ZARA, zx - out * 1.6, zz + out * 0.4, 0.0, named["zara"][1])
    else:
        W3.poof(sc, zx - 1.6, 1.2, zz + 0.4, prog(t, shove + 1.0, 0.8), f.gt)
    shoot(f, sc, (0.4, 2.0, 5.0), (0, 1.35, 1.5), (0.3, 1.9, 4.4), (0, 1.4, 1.6))
    if t > f.cue(1):
        with at(ctx, W / 2, 300, s=pop(t, f.cue(1))):
            headline(ctx, "ZARA IS OUT!", 0, 0, 110, color="#ff4d4d")


def final_offer(idx):
    amounts = ["50,000", "100,000", "250,000", "500,000"]

    def draw(f):
        ctx, t = f.ctx, f.t
        out_t = f.cue_end(-1) - 0.3
        brick_out = idx == 3 and t > out_t
        r = ring_at(f.gt)
        bx, bz = spot("brick", r)
        named = {
            "brick": (0.0, P(f, "brick", arms="cheer" if brick_out else ("shrug" if idx >= 2 else "idle"),
                             expr=("laugh" if brick_out else ("determined", "smug", "scared", "shocked")[idx]),
                             sweat=1.0 if idx >= 2 else 0.0, walk=f.gt * 2.4 if brick_out else None)),
            "pip": (0.0, P(f, "pip", arms="idle", expr="determined")),
        }
        sc = base_scene(f, lava=1.0, named_pose={"pip": named["pip"]}, named=("pip",),
                        host_pose=P(f, "host", arms="hold", held="briefcase", expr="smug" if idx < 3 else "laugh"))
        if brick_out:
            q = ease_out(prog(t, out_t, 1.0))
            if q < 1:
                W3.person(sc, BRICK, bx + q * 2.5, bz + q * 1.5, 0.8, named["brick"][1])
            else:
                W3.poof(sc, bx + 2.5, 1.2, bz + 1.5, prog(t, out_t + 1.0, 0.7), f.gt)
        else:
            W3.person(sc, BRICK, bx, bz, 0.0, named["brick"][1])
        # host walks down to the ring edge with the briefcase for the offers
        px_, pz_ = spot("pip", r)
        mx, mz = (bx + px_) / 2, (bz + pz_) / 2
        shoot(f, sc, (mx + 0.2, 1.75, mz + 3.3), (mx, 1.45, mz), (mx + 0.1, 1.7, mz + 2.8), (mx, 1.5, mz), fov=52, dof=0.35)
        with at(ctx, W / 2, 300, s=pop(t, f.cue(0) + 0.5), rot=-0.04):
            burst(ctx, 0, 0, 320, n=18, c1=(1, 1, 1, 0.1), c2=(0, 0, 0, 0), rot=t * 0.5)
            B2.gem(ctx, 0, -90, 1.0, t, "#7cff6b")
            headline(ctx, amounts[idx], 0, 40, 130, color="#7cff6b", ow=14)
        if brick_out:
            with at(ctx, W / 2, 620, s=pop(t, out_t), rot=0.05):
                headline(ctx, "DEAL!", 0, 0, 170, color="#ffd60a", ow=18)
    return draw


def winner(f):
    ctx, t = f.ctx, f.t
    jump = abs(math.sin(t * 6)) * 0.5 if t < f.cue(1) else 0.0
    pose = P(f, "pip", arms="cheer" if t < f.cue(1) else "idle", expr="laugh" if t < f.cue(1) else "happy",
             bounce=jump, tears=0.6)
    r = ring_at(f.gt)
    x, z = spot("pip", r)
    sc = base_scene(f, lava=1.0, named_pose={"pip": (0.0, pose)}, named=("pip",))
    ang = -0.5 + f.t * 0.12
    e0 = (x + math.sin(ang) * 2.2, 1.55, z + math.cos(ang) * 2.2)
    shoot(f, sc, e0, (x, 1.35, z), env=DAY, fov=52)
    glow(ctx, W / 2, H / 2, 700, "#ffd60a", 0.18)
    confetti(ctx, t, 0.0)
    if t < f.cue(1):
        G.title_slam(ctx, ["PIP WINS!"], t, wt(f, 0, "won"), y=240, size=150, colors=("#ffd60a",))


def match(f):
    ctx, t = f.ctx, f.t
    zara_t = f.cue(1)
    r = ring_at(f.gt)
    sc = base_scene(f, lava=0.0, named=(), host=False, crowd=False)
    # everyone gathers on the stage
    W3.person(sc, HOST, -1.6, 19.5, 0.0, P(f, "host", arms="point" if t > wt(f, 0, "match") else "idle", expr="happy"))
    W3.person(sc, PIP, 0.0, 19.8, 0.0, P(f, "pip", arms="cheer" if t > zara_t else "idle", expr="happy"))
    W3.person(sc, ZARA, 1.5, 19.5, 0.0, P(f, "zara", arms="cheer" if t > zara_t else "idle",
                                         expr="laugh" if t > zara_t else "shocked", tears=0.7 if t > zara_t else 0))
    shoot(f, sc, (0.3, 1.8, 23.6), (0, 1.45, 19.6), (0.2, 1.75, 23.0), (0, 1.5, 19.6), dof=0.35)
    if t > wt(f, 0, "two"):
        gems_popup(ctx, t, wt(f, 0, "two"), "200,000", x=1450, y=360, color="#d0a8ff")
    confetti(ctx, t, zara_t)


def dream(f):
    t = f.t
    built = prog(t, f.cue(1), 3.2)
    sc = base_scene(f, lava=0.0, named=(), host=False, crowd=False, gems=False)
    W3.golden_house(sc, 3.0, 2.0, f.gt, built=built, yaw=-0.3)
    W3.person(sc, PIP, -1.5, 5.0, 0.4, P(f, "pip", arms="point" if t > f.cue(1) else "idle", expr="happy"))
    W3.person(sc, HOST, -3.2, 5.4, 0.6, P(f, "host", arms="hold", held="mic", expr="happy"))
    shoot(f, sc, (-4, 2.4, 10.5), (0.5, 1.6, 3), (-1.5, 3.0, 10), (2, 2.0, 2), env=Env.blend(DAY, SUNSET, 0.55))


def end_card(f):
    ctx, t = f.ctx, f.t
    # floating island preview in 3D
    sc = Scene()
    for x in range(-4, 4):
        for z in range(-4, 4):
            d = math.hypot(x + 0.5, z + 0.5)
            if d > 4.2:
                continue
            sc.block(x, 0, z, "grass")
            for y in range(1, int(5 - d) + 1):
                sc.block(x, -y, z, "dirt" if y < 2 else "stone")
    W3.person(sc, PIP, -1.0, 0.5, 0.3, _Pose(t=f.gt, arms="cheer", expr="laugh"), y=1.0)
    W3.person(sc, BRICK, 1.2, 0.0, -0.3, _Pose(t=f.gt + 1, arms="panic", expr="scared"), y=1.0)
    ang = f.gt * 0.4
    img = renderer().render(sc, (math.sin(ang) * 13, 4, math.cos(ang) * 13), (0, 0.5, 0), DAY, f.gt, fov=50,
                            shadow_extent=10)
    blit(ctx, img)
    ctx.set_source_rgba(0, 0, 0, 0.25)
    ctx.paint()
    G.title_slam(ctx, ["NEXT: LAST TO LEAVE", "THE FLOATING ISLAND"], t, 0.2, y=200, size=90, colors=("#ffffff", "#ffd60a"))
    sub_t = wt(f, 0, "subscribe")
    if t > sub_t:
        with at(ctx, W / 2, 900, s=pop(t, sub_t) * (1 + 0.04 * math.sin(t * 6))):
            rrect(ctx, -240, -60, 480, 120, 22)
            fill(ctx, "#ff0000")
            headline(ctx, "SUBSCRIBE", 0, 0, 70, color="#ffffff", ow=0, shadow=0)




def prize_tour(f):
    sc = base_scene(f, cam_pos=(0, 4, -16))
    ang = 0.6 - f.t * 0.12
    shoot(f, sc, (math.sin(ang) * 7, 3.2, -21.5 + math.cos(ang) * 7), (0, 1.0, -21.5), env=DAY, fov=50)
    gems_popup(f.ctx, f.t, 0.4, "1,000,000", x=W / 2, y=330)


def hot(f):
    player_close(f, "pip", P(f, "pip", arms="idle", expr="scared", sweat=1.0), lava=1.0, dist=2.5, side=-0.4)


def leaderboard(f):
    ctx, t = f.ctx, f.t
    sc = base_scene(f, lava=1.0, cam_pos=(0, 18, 0))
    shoot(f, sc, (0, 20, 2), (0, 0, 0), (0, 16, 1.5), (0, 0, 0), fov=55)
    cards = [("BRICK", "still here", "#d62828", "brick"), ("PIP", "still here", "#06d6a0", "pip"),
             ("ZARA", "still here", "#8338ec", "zara"), ("DEX", "100,000 GEMS", "#118ab2", "dex")]
    for i, (nm, sub, col, who) in enumerate(cards):
        ts = wt(f, 0, nm) if nm != "DEX" else wt(f, 0, "dex")
        if t > ts - 0.1:
            name_tag(ctx, 330 + i * 420, 700, nm, sub, col, t, ts - 0.1)


def brick_sleep(f):
    player_close(f, "brick", P(f, "brick", arms="idle", expr="sleep", lean=0.15, bounce=math.sin(f.t * 1.3) * 0.02),
                 env=NIGHT, lava=1.0, dist=2.8, side=0.6)
    ctx, t = f.ctx, f.t
    for k in range(4):
        ph = (t * 0.6 + k / 4) % 1
        text(ctx, "Z", 1100 + k * 50 + ph * 40, 380 - ph * 160, 50 + k * 8, (1, 1, 1, 1 - ph))


def why_win(f):
    t = f.t
    if t < f.cue(1):
        host_close(f, P(f, "host", arms="hold", held="mic", expr="neutral"), lava=1.0)
    elif t < f.cue(2):
        player_close(f, "brick", P(f, "brick", arms="idle", expr="smug"), lava=1.0, dist=2.7, side=0.6, named=("brick",))
    else:
        player_close(f, "pip", P(f, "pip", arms="idle", expr="sad" if t < f.cue(2) + 1.5 else "determined"),
                     lava=1.0, dist=2.4, side=-0.4, named=("pip",))


def brick_celebrates(f):
    ctx, t = f.ctx, f.t
    sc = base_scene(f, lava=1.0, named=(), crowd=False, host=False)
    W3.person(sc, BRICK, 0.0, 19.6, 0.0, P(f, "brick", arms="cheer", expr="laugh", held=None,
                                           bounce=abs(math.sin(t * 6)) * 0.4))
    W3.gem_pile(sc, 2.2, 0, 19.0, f.gt, n=30, s=0.6)
    shoot(f, sc, (0.4, 1.7, 22.4), (0, 1.5, 19.6), (0.3, 1.65, 22.0), (0, 1.5, 19.6))
    gems_popup(ctx, t, 0.2, "500,000", x=1450, y=380, color="#7cff6b")

# --------------------------------------------------------------------------
# Script
# --------------------------------------------------------------------------

L = Line


def RING(shot, r0, r1, start, d):
    shot.ring = (r0, r1, start, d)
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
    Shot("meet_pip", meet("pip", "PIP", "smallest player", "#06d6a0"),
         [L("host", "Before we start, meet a few of the players."), L("pip", "I'm Pip, and I'm not leaving. Ever.")],
         transition="whip", chapter="Meet The Players", day=1, sfx=[("L1", "pop")]),
    Shot("meet_brick", meet("brick", "BRICK", "never lost a game", "#d62828", arms="cheer", expr="smug", side=0.6),
         [L("brick", "I'm Brick. I've never lost a game in my life.")], transition="whip", day=1, sfx=[(0.1, "pop")]),
    Shot("meet_zara", meet("zara", "ZARA", "brought snacks", "#8338ec", arms="hold", held="snack"),
         [L("zara", "I'm Zara. And I brought snacks.")], transition="whip", day=1, sfx=[(0.1, "pop")]),
    Shot("aside", aside, [L("host", "Zara might be the smartest player here.")], transition="cut", day=1,
         sfx=[("L0e-0.3", "laugh_track", 0.5)]),
    Shot("rules", rules, [L("host", "The rules are simple. If any part of you leaves the circle, you're out. The last player standing wins the million. Three... two... one... go!")],
         transition="whip", chapter="The Rules", day=1,
         sfx=[("L0+2.0", "pop"), ("L0+4.0", "pop"), ("L0e-2.6", "tick"), ("L0e-1.7", "tick"), ("L0e-0.9", "tick"),
              ("L0e-0.2", "boom", 0.9)]),
    Shot("prize", prize_tour, [L("host", "And this is the prize. One million gems, just sitting right there.")],
         transition="whip", day=1, sfx=[(0.3, "sparkle", 0.8)]),
    E(Shot("round1", round1, [L("host", "Round one! The first ten players to leave right now get ten thousand gems each.", 0.4),
                              L("host", "Okay, that was fast. Like, really fast.")],
           transition="whip", chapter="Round 1: The Bribe", day=1,
           sfx=[(0.1, "boom", 0.6), ("L0e-0.6", "pop"), ("L0e", "whoosh", 0.7), ("L1-0.3", "laugh_track", 0.4)]),
      100, 90, "L0e-0.1", 1.2),
    Shot("pip_scoff", pip_scoff, [L("pip", "Ten thousand? I'm here for a million.")], transition="cut", day=1),
    Shot("golden_house", golden_house, [
        L("host", "Oh, and the very first player who left? He also gets... a golden house!", 0.3),
        L("brick", "Wait, WHAT?!", 0.2),
        L("host", "Should've left!")],
        transition="whip", day=1, sfx=[("L0+1.2", "riser", 0.5), ("L0+2.6", "sparkle", 0.9), ("L1", "boom", 0.5),
                                       ("L2+0.4", "laugh_track", 0.5)]),
    Shot("archery", archery, [
        L("host", "Round two is a side challenge.", 0.1),
        L("host", "Brick, hit this target from inside the circle, and the circle stays the same. Miss... and it shrinks.", 0.2),
        L("brick", "Easy. I never miss.", 1.4),
        L("host", "He missed!")],
        transition="whip", chapter="Round 2: The Side Challenge", day=1,
        sfx=[(0.1, "boom", 0.6), ("L2e+0.2", "whoosh", 0.8), ("L3", "sad_trombone", 0.6)]),
    E(RING(Shot("shrink", shrink, [L("host", "The circle shrinks! One toe over the line, and you're out.")],
                transition="cut", day=1, sfx=[(0.2, "riser", 0.6), ("L0+1.5", "pop"), ("L0+2.1", "pop"), ("L0+2.7", "pop")]),
           12.0, 9.0, 0.2, 2.4),
      90, 72, 0.9, 2.4),
    Shot("brick_push", brick_push, [L("brick", "Move it, little guy!", 0.2), L("pip", "Hey! I was here first!")],
         transition="cut", day=1, sfx=[("L0+0.3", "whoosh", 0.6)]),
    Shot("rehook", lambda f: rehook(f, "ROUND 4 ?!"),
         [L("host", "Seventy-two players left. And trust me... round four is where things get crazy.")],
         transition="whip", day=1, sfx=[("L0e-0.8", "riser", 0.5)]),
    E(Shot("round3", round3, [L("host", "Round three. I hope nobody's scared of lava.", 0.3),
                              L("host", "Tap out, and you're teleported to safety. But you lose the million.")],
           transition="whip", chapter="Round 3: The Floor Is Lava", music="tension", day=1,
           sfx=[(0.1, "boom", 0.6), ("L0e-0.4", "boom", 0.8), ("L1+1.0", "pop"), ("L1+1.6", "pop"), ("L1+2.2", "pop")]),
      72, 51, "L1", 3.0),
    Shot("hot", hot, [L("pip", "Is it getting hot in here, or is it just me?")], transition="cut", day=1,
         sfx=[("L0e", "laugh_track", 0.4)]),
    Shot("gus", gus_quits, [L("gus", "Nope. Nope! I'm out! I am so out!", 0.4)], transition="cut", day=1,
         sfx=[("L0e+0.2", "pop", 0.9), ("L0e+0.25", "laugh_track", 0.5)], post=1.0),
    Shot("halfway", lambda f: rehook(f, "SMARTEST MOVE?!"),
         [L("host", "We're halfway through, and one player is about to make the smartest move of the whole game.")],
         transition="whip", day=1, sfx=[("L0e-0.8", "riser", 0.5)]),
    E(Shot("chest", chest_shot, [L("host", "Round four. Out there is a mystery chest. One player can leave the circle and take whatever's inside.", 0.2),
                                 L("host", "It could be one gem... or it could be a lot more.", 0.2),
                                 L("dex", "I'm taking it!", 1.9),
                                 L("host", "One hundred thousand gems!")],
           transition="whip", chapter="Round 4: The Mystery Chest", music="curious", day=1,
           sfx=[(0.1, "boom", 0.6), ("L2", "whoosh", 0.6), ("L3-0.6", "riser", 0.5), ("L3", "sparkle", 0.9), ("L3+0.1", "boom", 0.7)]),
      51, 50, "L2+0.3", 0.4),
    E(Shot("copycats", copycats, [L("host", "And now twelve more players quit, hoping there's another chest.", 0.3),
                                  L("host", "There was no other chest.")],
           transition="cut", day=1, sfx=[("L0+1.0", "whoosh", 0.5), ("L1", "sad_trombone", 0.6)]),
      50, 38, "L0+0.6", 1.8),
    Shot("leaderboard", leaderboard, [L("host", "Thirty-eight players left. Brick is still here. Pip is still here. Zara is still here. And Dex is now the richest player on the whole server.")],
         transition="whip", day=1, sfx=[("L0+1.6", "pop"), ("L0+2.6", "pop"), ("L0+3.6", "pop"), ("L0+5.0", "ding", 0.6)]),
    E(RING(Shot("night", night_round, [L("host", "Night falls. It's cold, it's dark, and the circle shrinks again.", 0.3),
                                       L("host", "So I put warm beds outside the circle. Take one, and you're out.", 0.2),
                                       L("host", "Twenty-six players chose the bed.")],
                transition="fade", chapter="Round 5: Night", music="lonely", day=1,
                sfx=[("L0+1.5", "riser", 0.4), ("L2", "pop", 0.5), ("L2+0.5", "pop", 0.5), ("L2+1.0", "pop", 0.5)]),
           9.0, 6.2, "L0+1.2", 2.6),
      38, 12, "L1e", 3.0),
    Shot("brick_sleep", brick_sleep, [L("host", "Brick fell asleep standing up. Honestly, that's impressive.")],
         transition="cut", day=1, sfx=[("L0e", "laugh_track", 0.4)]),
    Shot("snacks", snacks, [L("zara", "Here. You look hungry.", 0.4), L("pip", "Thanks, Zara. I owe you one.", 0.4)],
         transition="cut", day=1, post=0.8),
    E(RING(Shot("sunrise", sunrise, [L("host", "By sunrise, only twelve players are left.", 0.2),
                                     L("host", "And the circle is now the size of a kitchen table!")],
                transition="fade", chapter="Round 6: Tiny Circle", music="tension", day=1,
                sfx=[("L1", "boom", 0.6), ("L1+1.2", "pop"), ("L1+1.8", "pop"), ("L1+2.4", "pop")]),
           6.2, 2.8, "L1", 2.0),
      12, 3, "L1+0.8", 2.6),
    E(Shot("zara_out", zara_out, [L("brick", "Sorry, Zara. Nothing personal.", 0.9), L("host", "Zara is out! And then there were two.")],
           transition="whip", day=1, sfx=[("L0e+0.3", "whoosh", 0.7), ("L1", "boom", 0.6)]),
      3, 2, "L0e+0.4", 0.4),
    Shot("why", why_win, [L("host", "Before the final round, I asked both of them why they deserve to win.", 0.3),
                          L("brick", "Because I'm the best. Obviously.", 0.3),
                          L("pip", "Because I promised my little sister I'd build her a house.", 0.4)],
         transition="whip", day=1, music="emotional", post=0.6),
    Shot("offer1", final_offer(0), [L("host", "Brick. Pip. This briefcase has fifty thousand gems. Leave right now, and it's yours.", 0.2),
                                    L("brick", "Not a chance.")],
         transition="whip", chapter="The Final Offer", music="tension", day=1, sfx=[("L0+1.2", "pop")]),
    Shot("offer2", final_offer(1), [L("host", "One hundred thousand.", 0.2), L("pip", "Nope.")], transition="cut", day=1,
         sfx=[(0.6, "pop")]),
    Shot("offer3", final_offer(2), [L("host", "Two hundred and fifty thousand!", 0.3), L("brick", "Hmm...", 0.3)],
         transition="cut", day=1, sfx=[(0.6, "pop"), ("L1", "heartbeat", 0.8)]),
    E(Shot("offer4", final_offer(3), [L("host", "Final offer. Five hundred thousand gems.", 0.6), L("brick", "...Deal. I'm out!")],
           transition="pop", day=1, post=1.4, sfx=[("L0", "riser", 0.6), ("L1e-0.3", "boom", 0.9)]),
      2, 1, "L1e", 0.3),
    Shot("brick_rich", brick_celebrates, [L("brick", "Five hundred thousand gems! Best day ever!", 0.2),
                                          L("host", "Honestly? Not a bad deal.")],
         transition="whip", day=1, sfx=[(0.2, "sparkle", 0.8), ("L1e", "laugh_track", 0.4)]),
    Shot("winner", winner, [L("host", "Pip! You just won one million gems!", 0.4),
                            L("pip", "Wait. Can I give some to Zara? She gave me her snacks last night.")],
         transition="flash", chapter="The Winner", music="triumph", day=1, sfx=[(0.1, "boom", 0.9), ("L0+1.0", "sparkle", 0.8)]),
    Shot("match", match, [L("host", "You know what? I'll match it. Zara gets two hundred thousand too!", 0.3),
                          L("zara", "No way! No way!")],
         transition="whip", music="emotional", day=1, sfx=[("L0+2.4", "sparkle", 0.8)]),
    Shot("dream", dream, [L("host", "Pip, what are you going to do with a million gems?", 0.3),
                          L("pip", "Build the biggest house in the world. With a room for everybody.", 0.6)],
         transition="fade", day=1, post=1.4),
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

In this 3D animated Last To Leave The Circle challenge, 100 players survive 6 rounds: a 10,000-gem bribe (and a golden house for the first quitter), an archery side challenge, the floor is lava, a mystery chest, a night round with warm beds outside the circle, and a final briefcase standoff worth 500,000 gems. Stay to the end for the twist.

Comment who you think wins BEFORE the end. Subscribe for the next one: Last To Leave The Floating Island!""",
    "sources": [],
    "footer": "#LastToLeave #Challenge #3DAnimation",
    "tags": [
        "last to leave", "last to leave circle", "last to leave the circle wins", "last to leave wins",
        "100 players", "100 players challenge", "1000000 challenge", "challenge video", "elimination challenge",
        "floor is lava", "lava challenge", "shrinking circle", "mystery chest", "bribe challenge",
        "3d animation", "3d animated challenge", "animated challenge video", "cartoon challenge", "who will win", "last one standing",
    ],
}


def _thumb_render(sc, eye, tgt, env=DAY, fov=50):
    return renderer().render(sc, eye, tgt, env, 0.5, fov=fov, dof=0.35)


def thumbnail(ctx):
    """A: the prize — one kid, tiny circle, lava, giant number."""
    sc = Scene()
    W3.build_world(sc, 0.5, 2.6, 1.0)
    W3.person(sc, PIP, 0.0, 0.0, 0.0, _Pose(t=0.5, arms="panic", expr="shocked", blink=0.0, sweat=1.0))
    W3.gem_pile(sc, 1.9, 0.0, -0.6, 0.5, n=70, s=0.75)
    blit(ctx, _thumb_render(sc, (-0.55, 1.62, 1.55), (0.35, 1.45, 0), fov=55))
    with at(ctx, 1380, 170, rot=0.05):
        headline(ctx, "1,000,000", 0, 0, 180, color="#29d3ff", ow=24)
    with at(ctx, 1380, 345, rot=0.05):
        headline(ctx, "GEMS", 0, 0, 150, color="#ffffff", ow=20)


def thumbnail_b(ctx):
    """B: 100 vs 1."""
    sc = Scene()
    W3.build_world(sc, 0.5, R0, 0.0)
    W3.crowd(sc, 0.5, 100, R0, expr="happy", cam_pos=(0, 20, 22))
    left = _thumb_render(sc, (0, 16, 22), (0, 0, 0), fov=55)
    sc2 = Scene()
    W3.build_world(sc2, 0.5, 2.4, 1.0)
    W3.person(sc2, PIP, 0.0, 0.0, 0.0, _Pose(t=0.5, arms="cheer", expr="laugh", blink=0.0))
    right = _thumb_render(sc2, (0, 1.75, 2.6), (0, 1.45, 0), fov=50)
    ctx.save()
    ctx.rectangle(0, 0, W / 2, H)
    ctx.clip()
    ctx.translate(-W / 4, 0)
    blit(ctx, left)
    ctx.restore()
    ctx.save()
    ctx.rectangle(W / 2, 0, W / 2, H)
    ctx.clip()
    ctx.translate(W / 4, 0)
    blit(ctx, right)
    ctx.restore()
    ctx.rectangle(W / 2 - 8, 0, 16, H)
    fill(ctx, "#ffffff")
    with at(ctx, 480, 170, rot=-0.04):
        headline(ctx, "100", 0, 0, 230, color="#ffffff", ow=26)
    with at(ctx, 1440, 170, rot=0.04):
        headline(ctx, "1", 0, 0, 260, color="#ffd60a", ow=28)


def thumbnail_c(ctx):
    """C: the bribe — sweating player vs pile of gems."""
    sc = Scene()
    W3.build_world(sc, 0.5, 2.6, 1.0)
    W3.person(sc, BRICK, -0.6, 0.0, -0.15, _Pose(t=0.5, arms="shrug", expr="shocked", blink=0.0, sweat=1.0, look_yaw=0.3, eye_x=1.0))
    W3.gem_pile(sc, 1.6, 0.0, -0.4, 0.5, n=80, s=0.8)
    blit(ctx, _thumb_render(sc, (-0.75, 1.68, 1.7), (0.3, 1.5, 0), fov=55))
    with at(ctx, 1380, 170, rot=0.04):
        headline(ctx, "TAKE IT", 0, 0, 170, color="#ffffff", ow=22)
    with at(ctx, 1380, 340, rot=0.04):
        headline(ctx, "OR STAY?", 0, 0, 150, color="#7cff6b", ow=20)


THUMBNAILS = {"A_prize": thumbnail, "B_100_vs_1": thumbnail_b, "C_bribe": thumbnail_c}

EPISODE = Episode(
    slug="last-to-leave-circle-humans",
    title=META["title"],
    cast={},
    voices=VOICES,
    caption_colors=CAPTION_COLORS,
    shots=SHOTS,
    meta=META,
    thumbnail=thumbnail,
    hud=hud,
)
