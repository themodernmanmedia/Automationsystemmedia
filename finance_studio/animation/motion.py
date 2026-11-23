"""Character motion engine (pure Python, no Blender).

Turns a scene's high-level character directions (walk here, hold this up,
look worried, scratch head...) into per-frame rig channels. Blender only
applies these numbers, so all motion logic is unit-testable.

Conventions (character local space, facing screen-right):
  * x = forward, y = up, feet on y = 0.
  * Limb angles are degrees, counter-clockwise, 0 = hanging straight down;
    each child angle is relative to its parent segment.
  * Torso angle 0 = upright; negative leans forward.
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

SPEC_DIR = Path(__file__).resolve().parent.parent / "characters" / "specs"

JOINTS = ("torso", "head", "arm_f_up", "arm_f_lo", "hand_f", "arm_b_up", "arm_b_lo", "hand_b",
          "leg_f_up", "leg_f_lo", "foot_f", "leg_b_up", "leg_b_lo", "foot_b")
FACE = ("brow_f_dy", "brow_f_rot", "brow_b_dy", "brow_b_rot", "eye_open", "pupil_dx", "pupil_dy",
        "blush")


# --------------------------------------------------------------------------- easing
def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def in_out_cubic(t):
    t = clamp(t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def out_back(t, s=1.70158):
    t = clamp(t) - 1
    return 1 + (s + 1) * t ** 3 + s * t ** 2


def out_cubic(t):
    return 1 - (1 - clamp(t)) ** 3


EASES = {"linear": clamp, "smooth": smooth, "in_out_cubic": in_out_cubic,
         "out_back": out_back, "out_cubic": out_cubic, "hold": lambda t: 0.0}


def lerp(a, b, t):
    return a + (b - a) * t


class Track:
    """Piecewise keyframe track: [(time, value, ease_into_this_key), ...]."""

    def __init__(self, keys: list):
        if not keys:
            raise ValueError("Track needs at least one key")
        self.keys = sorted(((float(k[0]), k[1], k[2] if len(k) > 2 else "smooth") for k in keys),
                           key=lambda k: k[0])

    def __call__(self, t: float):
        ks = self.keys
        if t <= ks[0][0]:
            return ks[0][1]
        for (t0, v0, _), (t1, v1, ease) in zip(ks, ks[1:]):
            if t <= t1:
                if ease == "hold" or t1 == t0:
                    return v0
                f = EASES[ease]((t - t0) / (t1 - t0))
                if isinstance(v0, (list, tuple)):
                    return [lerp(a, b, f) for a, b in zip(v0, v1)]
                return lerp(v0, v1, f)
        return ks[-1][1]


def window(t, start, end, fade=0.25):
    """Weight 0->1->0 for an action active in [start, end] with eased edges."""
    if t < start or t > end:
        return 0.0
    fi = min(fade, (end - start) / 2) or 1e-6
    return smooth((t - start) / fi) * smooth((end - t) / fi)


# --------------------------------------------------------------------------- kinematics
def rot(v, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c)


def seg_dir(deg):
    """Unit direction of a segment at absolute angle `deg` (0 = straight down)."""
    a = math.radians(deg)
    return (math.sin(a), -math.cos(a))


def two_bone_ik(target, a, b, bend=1):
    """Angles (upper, lower) placing the chain end at `target` (relative to root).

    bend=+1 puts the middle joint on the counter-clockwise side of the root->target line.
    Unreachable targets are clamped so the chain stretches toward them.
    """
    d = math.hypot(*target)
    d = clamp(d, abs(a - b) + 1e-4, a + b - 1e-4)
    phi = math.degrees(math.atan2(target[0], -target[1]))
    alpha = math.degrees(math.acos(clamp((a * a + d * d - b * b) / (2 * a * d), -1, 1)))
    beta = math.degrees(math.acos(clamp((a * a + b * b - d * d) / (2 * a * b), -1, 1)))
    return phi + bend * alpha, -bend * (180 - beta)


def fk_chain(root, angles, lengths):
    pts, ang, p = [root], 0.0, root
    for a, ln in zip(angles, lengths):
        ang += a
        d = seg_dir(ang)
        p = (p[0] + d[0] * ln, p[1] + d[1] * ln)
        pts.append(p)
    return pts


# --------------------------------------------------------------------------- library
@dataclass
class Skeleton:
    hip: tuple
    neck: tuple
    head_pivot: tuple
    head_center: tuple
    shoulder_front: tuple
    shoulder_back: tuple
    upper_arm: float
    forearm: float
    hip_front: tuple
    hip_back: tuple
    thigh: float
    shin: float
    ankle_height: float
    torso_len: float = 1.5

    @classmethod
    def load(cls, character_id: str) -> "Skeleton":
        spec = json.loads((SPEC_DIR / f"{character_id}.json").read_text())
        return cls(**{k: tuple(v) if isinstance(v, list) else v for k, v in spec["skeleton"].items()})


# Upper-body poses as IK hand targets in the torso frame, relative to each shoulder.
# bend: elbow side. hand: wrist angle. Missing arm = keep base layer.
POSES: dict[str, dict] = {
    "hold_up":      {"front": {"target": (0.92, 0.08), "bend": -1, "hand": 25}},
    "present":      {"front": {"target": (0.78, 0.38), "bend": -1, "hand": 35}},
    "point":        {"front": {"target": (1.42, 0.18), "bend": -1, "hand": 5}},
    "point_up":     {"front": {"target": (0.75, 1.15), "bend": -1, "hand": 0}},
    "head_scratch": {"back": {"target": (0.16, 1.2), "bend": 1, "hand": 160, "wiggle": 0.035}},
    "hands_up":     {"front": {"target": (0.78, 0.2), "bend": -1, "hand": 150},
                     "back": {"target": (0.3, 0.32), "bend": -1, "hand": 160}},
    "worried_hands": {"front": {"target": (0.16, -0.42), "bend": -1, "hand": 70},
                      "back": {"target": (0.62, -0.4), "bend": -1, "hand": 80}},
    "shrug":        {"front": {"target": (0.5, -0.52), "bend": -1, "hand": 95},
                     "back": {"target": (-0.48, -0.5), "bend": 1, "hand": -95}},
    "think":        {"front": {"target": (0.13, 0.42), "bend": -1, "hand": 150}},
    "hand_on_hip":  {"back": {"target": (-0.3, -0.72), "bend": 1, "hand": 40}},
    "wave":         {"front": {"target": (0.5, 1.0), "bend": -1, "hand": 180, "wiggle": 0.08}},
}

EXPRESSIONS: dict[str, dict] = {
    #            brow_f_dy rot  brow_b_dy rot  eye  pdx  pdy  blush  mouth   head
    "neutral":   dict(face=(0.0, 0, 0.0, 0, 1.0, 0.15, 0.0, 0.0), mouth="rest", head=0),
    "happy":     dict(face=(0.035, 6, 0.035, -6, 0.9, 0.2, 0.05, 0.35), mouth="smile", head=3),
    "excited":   dict(face=(0.07, 8, 0.07, -8, 1.08, 0.2, 0.1, 0.6), mouth="grin", head=5),
    "confused":  dict(face=(0.08, 14, -0.025, -8, 1.0, -0.1, 0.35, 0.0), mouth="smirk", head=9),
    "worried":   dict(face=(0.045, 16, 0.045, -16, 1.02, 0.1, 0.25, 0.0), mouth="frown", head=-3),
    "surprised": dict(face=(0.11, 4, 0.11, -4, 1.22, 0.0, 0.0, 0.0), mouth="gasp", head=4),
    "sad":       dict(face=(0.02, 18, 0.02, -18, 0.78, 0.1, -0.45, 0.0), mouth="frown", head=-7),
    "determined": dict(face=(-0.03, -14, -0.03, 14, 0.92, 0.3, 0.0, 0.0), mouth="rest", head=-2),
}
MOUTHS = ("rest", "smile", "grin", "smirk", "frown", "gasp", "small", "open", "round", "wide")


# Foot-locked gait parameters (units: character units / seconds)
GAITS = {
    #        stride  cycle  stance  lift  hip_drop(min) bob(extra drop at double support / run bounce)
    "walk": dict(S=1.0, T=0.95, duty=0.58, lift=0.2, drop=0.03, bob=0.17, torso=-3, arm=17, elbow=14, run=False),
    "run":  dict(S=1.5, T=0.62, duty=0.4, lift=0.42, drop=0.3, bob=0.09, torso=-11, arm=36, elbow=88, run=True),
}


LEG_CHANNELS = ("leg_f_up", "leg_f_lo", "foot_f", "leg_b_up", "leg_b_lo", "foot_b")
SETTLE = 0.3


# --------------------------------------------------------------------------- animator
@dataclass
class CharacterDirection:
    """High-level direction for one character in one scene (from the scene JSON)."""
    character: str
    start_x: float = 0.0
    facing: int = 1
    actions: list = field(default_factory=list)      # walk/run/sit/stand/pose
    expressions: list = field(default_factory=list)  # [{at, name}]
    looks: list = field(default_factory=list)        # [{at, dx, dy}] pupil direction
    visemes: list = field(default_factory=list)      # [(t, mouth)] from lip-sync (optional)
    blink_seed: int = 7


class CharacterAnimator:
    def __init__(self, direction: CharacterDirection, fps: int):
        self.d = direction
        self.fps = fps
        self.sk = Skeleton.load(direction.character)

    # ---- leg layer
    def _stand_legs(self):
        return {"leg_f_up": 3.0, "leg_f_lo": -2.0, "foot_f": -1.0,
                "leg_b_up": -3.0, "leg_b_lo": -1.0, "foot_b": 4.0}

    def _sit_legs(self):
        return {"leg_f_up": 88.0, "leg_f_lo": -86.0, "foot_f": -2.0,
                "leg_b_up": 84.0, "leg_b_lo": -82.0, "foot_b": -2.0}

    def _foot_points(self, ch):
        sk = self.sk
        out = []
        for side, hip in (("f", sk.hip_front), ("b", sk.hip_back)):
            pts = fk_chain(hip, [ch[f"leg_{side}_up"], ch[f"leg_{side}_lo"]], [sk.thigh, sk.shin])
            out.append((pts[-1][0], pts[-1][1] - sk.ankle_height))
        return out

    def _ground_offset(self, ch):
        return -min(p[1] for p in self._foot_points(ch))

    # ---- arm layer
    def _arm_from_pose(self, side, spec, t):
        sk = self.sk
        a, b = sk.upper_arm, sk.forearm
        tx, ty = spec["target"]
        if spec.get("wiggle"):
            ty += spec["wiggle"] * math.sin(t * 2 * math.pi * 4.5)
            tx += spec["wiggle"] * 0.5 * math.cos(t * 2 * math.pi * 4.5)
        up, lo = two_bone_ik((tx, ty), a, b, spec.get("bend", 1))
        return {f"arm_{side}_up": up, f"arm_{side}_lo": lo, f"hand_{side}": spec.get("hand", 0.0)}

    # ---- full evaluation
    def bake(self, n_frames: int) -> dict:
        d, fps = self.d, self.fps
        actions = sorted(d.actions, key=lambda a: a["start"])
        chans = {k: [] for k in ("x", "y", "facing", *JOINTS, *FACE)}
        chans["mouth"], chans["expression"] = [], []
        rng = random.Random(d.blink_seed)
        blinks, tb = [], rng.uniform(0.6, 1.6)
        while tb < n_frames / fps + 5:
            blinks.append(tb)
            tb += rng.uniform(2.2, 4.8)
        for e in d.expressions:  # blink on expression changes reads as a thought beat
            if e["at"] > 0.2:
                blinks.append(e["at"] - 0.04)
        expr_keys = sorted(d.expressions, key=lambda e: e["at"]) or [{"at": 0, "name": "neutral"}]
        sk = self.sk
        hips = {"f": sk.hip_front, "b": sk.hip_back}
        root_u = 0.0                       # distance travelled along the facing direction
        phase = 0.0
        last_legs, last_move_end = None, 0.0
        feet = {k: {"u": hips[k][0] + (0.06 if k == "f" else -0.04), "h": 0.0, "mode": "stance", "lift_u": 0.0}
                for k in hips}
        for i in range(n_frames):
            t = i / fps
            ch = {j: 0.0 for j in JOINTS}
            # ----- base: stand with breathing
            ch.update(self._stand_legs())
            breathe = math.sin(t * 2 * math.pi / 3.6)
            ch["torso"] = 0.8 * breathe
            ch["head"] = -0.5 * breathe
            ch.update({"arm_f_up": 5 + 1.2 * breathe, "arm_f_lo": 10, "hand_f": 4,
                       "arm_b_up": -4 - 1.2 * breathe, "arm_b_lo": 8, "hand_b": -2})
            moving = None
            for a in actions:
                if a["type"] in ("walk", "run") and a["start"] <= t <= a["end"]:
                    moving = a
                if a["type"] == "sit":
                    w = window(t, a["start"], a["end"], a.get("fade", 0.45))
                    if w:
                        for k, v in self._sit_legs().items():
                            ch[k] = lerp(ch[k], v, w)
                        ch["torso"] = lerp(ch["torso"], 4.0, w)
            gait_y = None
            if moving:
                g = GAITS[moving["type"]]
                w = window(t, moving["start"], moving["end"], 0.35)
                speed = w * 2 * g["S"] / g["T"]
                root_u += speed / fps
                phase += w / (g["T"] * fps)
                for k, off in (("f", 0.0), ("b", 0.5)):
                    ft, pk = feet[k], (phase + off) % 1.0
                    if pk < g["duty"]:
                        ft["mode"], ft["h"] = "stance", 0.0          # planted: world position frozen
                    else:
                        if ft["mode"] == "stance":
                            ft["mode"], ft["lift_u"] = "swing", ft["u"]
                        sw = (pk - g["duty"]) / (1 - g["duty"])
                        remaining = (1 - sw) * (1 - g["duty"]) * g["T"]
                        land = root_u + speed * remaining + hips[k][0] + 0.5 * g["S"] * w
                        ft["u"] = lerp(ft["lift_u"], land, smooth(sw))
                        ft["h"] = g["lift"] * w * math.sin(math.pi * sw)
                cyc = math.cos(4 * math.pi * phase)
                # walk: hips highest at the passing pose (straight stance leg), lowest at double support;
                # run: lowest at contact, highest in the flight phase
                gait_y = -g["drop"] * w + (g["bob"] * w * (0.5 - 0.5 * cyc) if g["run"]
                                            else -g["bob"] * w * (0.5 + 0.5 * cyc) ** 1.5)
                for k in ("f", "b"):
                    hx, hy = hips[k]
                    tgt = (feet[k]["u"] - (root_u + hx), feet[k]["h"] + sk.ankle_height - (gait_y + hy))
                    up, lo = two_bone_ik(tgt, sk.thigh, sk.shin, bend=1)  # knees point forward
                    toe = 12 * math.sin(math.pi * min(1, feet[k]["h"] / max(g["lift"], 1e-6))) if feet[k]["h"] else 0
                    for name, v in ((f"leg_{k}_up", up), (f"leg_{k}_lo", lo), (f"foot_{k}", -(up + lo) + toe)):
                        ch[name] = v  # full IK while moving: w already scales stride, so feet never slide
                last_legs = {n: ch[n] for n in LEG_CHANNELS}
                last_move_end = moving["end"]
                swing = math.cos(2 * math.pi * phase)
                ch["arm_f_up"] = lerp(ch["arm_f_up"], -g["arm"] * swing, w)
                ch["arm_b_up"] = lerp(ch["arm_b_up"], g["arm"] * swing, w)
                ch["arm_f_lo"] = lerp(ch["arm_f_lo"], g["elbow"] + 8 * max(0, swing), w)
                ch["arm_b_lo"] = lerp(ch["arm_b_lo"], g["elbow"] + 8 * max(0, -swing), w)
                ch["torso"] = lerp(ch["torso"], g["torso"], w)
                ch["head"] = lerp(ch["head"], -0.6 * g["torso"], w)
            else:
                if last_legs is not None and t - last_move_end < SETTLE:  # ease from final stride into stance
                    f_ = smooth((t - last_move_end) / SETTLE)
                    for n in LEG_CHANNELS:
                        ch[n] = lerp(last_legs[n], ch[n], f_)
                for k in ("f", "b"):  # when idle, feet rest under the hips
                    feet[k]["u"] = root_u + hips[k][0] + (0.06 if k == "f" else -0.04)
                    feet[k]["h"], feet[k]["mode"] = 0.0, "stance"
            # ----- upper-body pose overlays
            for a in actions:
                if a["type"] != "pose":
                    continue
                w = window(t, a["start"], a["end"], a.get("fade", 0.3))
                if not w:
                    continue
                spec = POSES[a["name"]]
                for side_key, side in (("front", "f"), ("back", "b")):
                    if side_key in spec:
                        for k, v in self._arm_from_pose(side, spec[side_key], t).items():
                            ch[k] = lerp(ch[k], v, w)
                if a.get("head") is not None:
                    ch["head"] += a["head"] * w
            # ----- face
            ex_prev, ex_next, f = self._expr_blend(expr_keys, t)
            fa, fb = EXPRESSIONS[ex_prev]["face"], EXPRESSIONS[ex_next]["face"]
            face = [lerp(p, q, f) for p, q in zip(fa, fb)]
            ch["head"] += lerp(EXPRESSIONS[ex_prev]["head"], EXPRESSIONS[ex_next]["head"], f)
            look = self._look(t)
            if look:
                face[5], face[6] = look
            face[4] *= self._blink(blinks, t)
            for k, v in zip(FACE, face):
                chans[k].append(round(v, 4))
            ex_now = ex_next if f >= 0.5 else ex_prev
            chans["expression"].append(ex_now)
            chans["mouth"].append(self._viseme(t) or EXPRESSIONS[ex_now]["mouth"])
            # ----- root: grounded standing pose, or gait-driven hips while moving
            y = self._ground_offset(ch)
            if gait_y is not None:
                y = gait_y
            x = d.start_x + d.facing * root_u
            chans["x"].append(round(x, 4))
            chans["y"].append(round(y, 4))
            chans["facing"].append(d.facing)
            for j in JOINTS:
                chans[j].append(round(ch[j], 3))
        return chans

    def _expr_blend(self, keys, t, dur=0.22):
        prev = keys[0]["name"]
        for k in keys:
            if t < k["at"]:
                break
            if t < k["at"] + dur:
                return prev, k["name"], smooth((t - k["at"]) / dur)
            prev = k["name"]
        return prev, prev, 1.0

    def _look(self, t):
        if not self.d.looks:
            return None
        tr = Track([(k["at"], [k["dx"], k["dy"]], "smooth") for k in self.d.looks])
        return tr(t)

    @staticmethod
    def _blink(blinks, t):
        for b in blinks:
            dt = t - b
            if 0 <= dt < 0.16:
                return 0.08 + 0.92 * abs(dt - 0.07) / 0.09 if dt > 0.02 else 0.5
        return 1.0

    def _viseme(self, t):
        if not self.d.visemes:
            return None
        cur = None
        for tv, m in self.d.visemes:
            if tv > t:
                break
            cur = m
        return cur


def walk_distance(direction: CharacterDirection, fps: int, n_frames: int) -> float:
    xs = CharacterAnimator(direction, fps).bake(n_frames)["x"]
    return xs[-1] - xs[0]
