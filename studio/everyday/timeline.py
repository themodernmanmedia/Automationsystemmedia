"""Script -> timed timeline.

An episode is a list of ``Shot``s. Each shot owns some narration/dialogue
``Line``s and a draw function. Line audio decides how long the shot lasts, and
the draw function receives a ``Frame`` that knows exactly when each line
starts, so animation stays locked to the voice-over.
"""
from __future__ import annotations

import math
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from .config import FPS, H, W
from .tts import Voice, mouth_envelope, synth


@dataclass
class Line:
    who: str
    text: str
    pause: float = 0.22          # silence after the line
    caption: Optional[str] = None  # override caption text
    speed: Optional[float] = None


@dataclass
class Shot:
    name: str
    draw: Callable
    lines: list[Line] = field(default_factory=list)
    pre: float = 0.15
    post: float = 0.25
    min_dur: float = 0.0
    music: Optional[str] = None      # start a music style at this shot ("off" to stop)
    sfx: list = field(default_factory=list)  # [(time | "L<i>" | "L<i>+0.3" | "end-0.5", name, gain)]
    day: Optional[int] = None
    chapter: Optional[str] = None
    transition: str = "cut"          # cut | whip | flash | pop | fade
    captions: bool = True

    # filled by build()
    start: float = 0.0
    dur: float = 0.0
    line_times: list = field(default_factory=list)   # [(start, end)] local
    line_audio: list = field(default_factory=list)
    line_env: list = field(default_factory=list)


@dataclass
class Episode:
    slug: str
    title: str
    cast: dict            # who -> Character/Dog (for drawing helpers)
    voices: dict          # who -> Voice
    caption_colors: dict  # who -> colour
    shots: list[Shot]
    meta: dict = field(default_factory=dict)
    thumbnail: Optional[Callable] = None
    hud: Optional[Callable] = None   # hud(ctx, ep, gt, value, since_change)
    total: float = 0.0


def build(ep: Episode, log=print) -> Episode:
    t = 0.0
    for si, sh in enumerate(ep.shots):
        sh.start = t
        cur = sh.pre
        sh.line_times, sh.line_audio, sh.line_env = [], [], []
        for ln in sh.lines:
            v = ep.voices[ln.who]
            if ln.speed:
                v = Voice(v.voice, ln.speed, v.lang, v.gain)
            audio = synth(ln.text, v)
            d = len(audio) / 48000
            sh.line_times.append((cur, cur + d))
            sh.line_audio.append(audio)
            sh.line_env.append(mouth_envelope(audio))
            cur += d + ln.pause
        sh.dur = max(cur - (sh.lines[-1].pause if sh.lines else 0) + sh.post, sh.min_dur)
        t += sh.dur
        log(f"  [{si + 1:02d}/{len(ep.shots)}] {sh.name:<28} {sh.dur:5.1f}s  @ {sh.start:6.1f}s")
    ep.total = t
    return ep


def resolve_time(sh: Shot, spec) -> float:
    if isinstance(spec, (int, float)):
        return float(spec)
    s = str(spec)
    if s.startswith("end"):
        return sh.dur + float(s[3:] or 0)
    if s.startswith("L"):
        rest = s[1:]
        off = 0.0
        for sign in ("+", "-"):
            if sign in rest:
                a, b = rest.split(sign, 1)
                rest, off = a, float(b) * (1 if sign == "+" else -1)
                break
        if rest.endswith("e"):
            return sh.line_times[int(rest[:-1])][1] + off
        return sh.line_times[int(rest)][0] + off
    raise ValueError(spec)


class Frame:
    """Everything a shot's draw function needs for one frame."""

    def __init__(self, ctx, ep: Episode, shot: Shot, t: float, gt: float):
        self.ctx = ctx
        self.ep = ep
        self.shot = shot
        self.t = t
        self.gt = gt
        self.dur = shot.dur
        self.p = t / shot.dur if shot.dur else 1.0
        self.W, self.H = W, H

    # --- line timing -----------------------------------------------------
    def cue(self, i: int) -> float:
        i = i if i >= 0 else len(self.shot.line_times) + i
        return self.shot.line_times[i][0] if self.shot.line_times else 0.0

    def cue_end(self, i: int) -> float:
        i = i if i >= 0 else len(self.shot.line_times) + i
        return self.shot.line_times[i][1] if self.shot.line_times else self.dur

    def at(self, spec) -> float:
        return resolve_time(self.shot, spec)

    def since(self, spec) -> float:
        return self.t - self.at(spec)

    def line_prog(self, i: int) -> float:
        a, b = self.shot.line_times[i]
        return min(1.0, max(0.0, (self.t - a) / max(b - a, 1e-6)))

    def mouth(self, who: str) -> float:
        for ln, (a, b), env in zip(self.shot.lines, self.shot.line_times, self.shot.line_env):
            if ln.who == who and a <= self.t < b:
                i = int((self.t - a) * FPS)
                return float(env[min(i, len(env) - 1)])
        return 0.0

    def talking(self, who: str) -> bool:
        for ln, (a, b) in zip(self.shot.lines, self.shot.line_times):
            if ln.who == who and a <= self.t < b + 0.1:
                return True
        return False

    # --- camera ----------------------------------------------------------
    @contextmanager
    def cam(self, zoom=1.0, cx=W / 2, cy=H / 2, rot=0.0, shake=0.0):
        ctx = self.ctx
        ctx.save()
        sx = sy = 0.0
        if shake:
            sx = math.sin(self.t * 71.3) * shake + math.sin(self.t * 37.1) * shake * 0.5
            sy = math.cos(self.t * 63.7) * shake
        ctx.translate(W / 2 + sx, H / 2 + sy)
        if rot:
            ctx.rotate(rot)
        ctx.scale(zoom, zoom)
        ctx.translate(-cx, -cy)
        try:
            yield ctx
        finally:
            ctx.restore()


def locate(ep: Episode, gt: float) -> tuple[int, Shot, float]:
    lo, hi = 0, len(ep.shots) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if ep.shots[mid].start <= gt:
            lo = mid
        else:
            hi = mid - 1
    sh = ep.shots[lo]
    return lo, sh, gt - sh.start
