"""Procedural music beds, sound effects and the final mix (numpy only).

Everything is synthesised so the channel owns 100% of its audio: no
licensing, no Content ID claims.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

from .config import SAMPLE_RATE as SR

RNG = np.random.default_rng(7)


def note_hz(n: float) -> float:
    """MIDI note number -> Hz."""
    return 440.0 * 2 ** ((n - 69) / 12)


def env_adsr(n, a=0.005, d=0.1, s=0.6, r=0.2, length=None):
    length = length or n / SR
    t = np.arange(n) / SR
    e = np.ones(n)
    e = np.where(t < a, t / max(a, 1e-6), e)
    dm = (t >= a) & (t < a + d)
    e[dm] = 1 - (1 - s) * (t[dm] - a) / d
    e[t >= a + d] = s
    rel_start = max(length - r, a + d)
    rm = t >= rel_start
    e[rm] *= np.clip(1 - (t[rm] - rel_start) / max(r, 1e-6), 0, 1)
    return e


# --------------------------------------------------------------------------
# Instruments
# --------------------------------------------------------------------------


def piano(freq, dur, vel=0.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for h, amp in ((1, 1.0), (2, 0.45), (3, 0.22), (4, 0.12), (5, 0.06)):
        f = freq * h * (1 + 0.0004 * h * h)
        out += amp * np.sin(2 * np.pi * f * t) * np.exp(-t * (1.6 + h * 0.9))
    out *= np.minimum(1, t / 0.004)
    out *= np.clip(1 - (t - (dur - 0.08)) / 0.08, 0, 1)
    return out * vel * 0.35


def pluck(freq, dur, vel=0.5, bright=0.5):
    """Karplus-Strong plucked string."""
    n = int(dur * SR)
    period = max(2, int(SR / freq))
    buf = RNG.uniform(-1, 1, period)
    out = np.zeros(n)
    decay = 0.996 - (1 - bright) * 0.006
    # vectorised-ish KS: iterate per period
    idx = 0
    while idx < n:
        m = min(period, n - idx)
        out[idx: idx + m] = buf[:m]
        buf = decay * 0.5 * (buf + np.roll(buf, -1))
        idx += period
    out *= np.minimum(1, np.arange(n) / (0.002 * SR))
    return out * vel * 0.5


def pad(freq, dur, vel=0.25):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for det in (-0.12, 0.0, 0.11):
        f = freq * 2 ** (det / 12)
        out += np.sin(2 * np.pi * f * t + np.sin(2 * np.pi * 0.3 * t) * 0.5)
        out += 0.3 * np.sin(2 * np.pi * f * 2 * t)
    e = env_adsr(n, a=min(0.6, dur / 3), d=0.3, s=0.8, r=min(0.8, dur / 3), length=dur)
    return out * e * vel * 0.12


def bass(freq, dur, vel=0.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2 * t)
    e = env_adsr(n, a=0.005, d=0.15, s=0.7, r=0.08, length=dur)
    return np.tanh(out * 1.4) * e * vel * 0.35


def kick(vel=0.8):
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 50 + 90 * np.exp(-t * 30)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 9) * vel * 0.8


def snare(vel=0.5):
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    noise = RNG.uniform(-1, 1, n)
    sos = butter(2, [1500, 8000], btype="band", fs=SR, output="sos")
    noise = sosfilt(sos, noise)
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25)
    return (noise * np.exp(-t * 18) * 0.9 + body * 0.5) * vel * 0.6


def hat(vel=0.25, open_=False):
    n = int((0.25 if open_ else 0.06) * SR)
    t = np.arange(n) / SR
    noise = RNG.uniform(-1, 1, n)
    sos = butter(2, 7000, btype="high", fs=SR, output="sos")
    return sosfilt(sos, noise) * np.exp(-t * (12 if open_ else 60)) * vel * 0.5


def clap(vel=0.5):
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    noise = RNG.uniform(-1, 1, n)
    sos = butter(2, [900, 5000], btype="band", fs=SR, output="sos")
    noise = sosfilt(sos, noise)
    e = np.zeros(n)
    for off in (0, 0.012, 0.024):
        o = int(off * SR)
        e[o:] += np.exp(-(t[: n - o]) * 30)
    return noise * e * vel * 0.4


@lru_cache(maxsize=4)
def _reverb_ir(seconds=2.2, damp=3.2):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = RNG.normal(0, 1, (2, n)) * np.exp(-t * damp)
    sos = butter(1, 5000, btype="low", fs=SR, output="sos")
    ir = sosfilt(sos, ir, axis=1)
    ir[:, : int(0.012 * SR)] = 0
    return ir / np.sqrt((ir ** 2).sum(axis=1, keepdims=True)) * 0.9


def reverb(x: np.ndarray, wet=0.25, seconds=2.2) -> np.ndarray:
    """x mono -> stereo with reverb tail (same length)."""
    ir = _reverb_ir(seconds)
    out = np.stack([x, x])
    w = np.stack([fftconvolve(x, ir[0])[: len(x)], fftconvolve(x, ir[1])[: len(x)]])
    return out * (1 - wet) + w * wet


def place(buf: np.ndarray, sig: np.ndarray, t: float, gain=1.0):
    i = int(t * SR)
    if i >= len(buf) or i + len(sig) <= 0:
        return
    if i < 0:
        sig = sig[-i:]
        i = 0
    m = min(len(sig), len(buf) - i)
    buf[i: i + m] += sig[:m] * gain


# --------------------------------------------------------------------------
# Music styles
# --------------------------------------------------------------------------

# chords as MIDI root + quality
MAJ = (0, 4, 7)
MIN = (0, 3, 7)

STYLES = {
    # bpm, progression [(root, quality)], instrument flavour
    "upbeat": dict(bpm=118, prog=[(60, MAJ), (67, MAJ), (69, MIN), (65, MAJ)], drums="pop", lead="pluck"),
    "curious": dict(bpm=104, prog=[(62, MIN), (67, MAJ), (60, MAJ), (69, MIN)], drums="light", lead="pluck"),
    "science": dict(bpm=96, prog=[(57, MIN), (65, MAJ), (60, MAJ), (67, MAJ)], drums="light", lead="piano"),
    "chill": dict(bpm=84, prog=[(65, MAJ), (69, MIN), (62, MIN), (67, MAJ)], drums="soft", lead="piano"),
    "lonely": dict(bpm=68, prog=[(57, MIN), (53, MAJ), (60, MAJ), (55, MAJ)], drums=None, lead="piano_sparse"),
    "emotional": dict(bpm=70, prog=[(53, MAJ), (60, MAJ), (62, MIN), (58, MAJ)], drums=None, lead="piano"),
    "triumph": dict(bpm=112, prog=[(53, MAJ), (60, MAJ), (62, MIN), (58, MAJ)], drums="pop", lead="pluck"),
    "tension": dict(bpm=90, prog=[(57, MIN), (57, MIN), (58, MAJ), (56, MAJ)], drums="tick", lead=None),
}


def render_style(style: str, dur: float, seed: int = 0) -> np.ndarray:
    cfg = STYLES[style]
    beat = 60 / cfg["bpm"]
    bar = beat * 4
    n = int(dur * SR) + SR
    mono_inst = np.zeros(n)
    drums = np.zeros(n)
    rng = np.random.default_rng(seed)
    prog = cfg["prog"]
    bars = int(math.ceil(dur / bar)) + 1
    for b in range(bars):
        t0 = b * bar
        root, q = prog[b % len(prog)]
        notes = [root + i for i in q]
        # pad
        for nn in notes:
            place(mono_inst, pad(note_hz(nn - 12), bar + 0.4, 0.22), t0)
        # bass
        if cfg["drums"] not in (None,):
            for k in range(4 if cfg["drums"] == "pop" else 2):
                place(mono_inst, bass(note_hz(root - 24), beat * (1 if cfg["drums"] == "pop" else 2) * 0.9, 0.55),
                      t0 + k * beat * (1 if cfg["drums"] == "pop" else 2))
        else:
            place(mono_inst, bass(note_hz(root - 24), bar * 0.95, 0.3), t0)
        # lead / arps
        lead = cfg["lead"]
        if lead == "pluck":
            pattern = [0, 1, 2, 1, 2, 0, 1, 2]
            for k, pi in enumerate(pattern):
                nn = notes[pi] + (12 if k in (3, 6) else 0)
                place(mono_inst, pluck(note_hz(nn), beat * 0.9, 0.42 + 0.1 * rng.random(), bright=0.7), t0 + k * beat / 2)
        elif lead == "piano":
            pattern = [0, 2, 1, 2, 0, 2, 1, 2]
            for k, pi in enumerate(pattern):
                nn = notes[pi] + 12
                place(mono_inst, piano(note_hz(nn), beat * 1.5, 0.45 + 0.1 * rng.random()), t0 + k * beat / 2)
            if b % 2 == 1:
                mel = notes[rng.integers(0, 3)] + 24
                place(mono_inst, piano(note_hz(mel), beat * 2, 0.35), t0 + beat * 2.5)
        elif lead == "piano_sparse":
            for k, pi in enumerate((0, 1, 2)):
                place(mono_inst, piano(note_hz(notes[pi] + 12), bar, 0.42), t0 + k * beat * 1.33)
            if b % 2 == 0:
                place(mono_inst, piano(note_hz(notes[2] + 24), beat * 3, 0.28), t0 + beat * 3)
        # drums
        d = cfg["drums"]
        if d == "pop":
            for k in range(4):
                if k in (0, 2):
                    place(drums, kick(0.75), t0 + k * beat)
                else:
                    place(drums, clap(0.5), t0 + k * beat)
                place(drums, hat(0.22), t0 + k * beat + beat / 2)
                place(drums, hat(0.12), t0 + k * beat)
        elif d == "light":
            place(drums, kick(0.6), t0)
            place(drums, kick(0.45), t0 + beat * 2.5)
            for k in range(8):
                place(drums, hat(0.13 if k % 2 else 0.2), t0 + k * beat / 2)
            place(drums, snare(0.25), t0 + beat * 3)
        elif d == "soft":
            place(drums, kick(0.45), t0)
            place(drums, kick(0.3), t0 + beat * 2)
            for k in range(4):
                place(drums, hat(0.08), t0 + k * beat + beat / 2)
        elif d == "tick":
            for k in range(4):
                place(drums, hat(0.18), t0 + k * beat)
            place(drums, kick(0.5), t0)
    wet = 0.35 if style in ("lonely", "emotional", "chill") else 0.2
    st = reverb(mono_inst, wet=wet, seconds=2.6 if wet > 0.3 else 1.6)
    st += np.stack([drums, drums]) * 0.9
    st = st[:, : int(dur * SR)]
    return st


def build_music(cues: list[tuple[float, float, str]], total: float) -> np.ndarray:
    """cues: (start, end, style). Returns stereo buffer with crossfades."""
    n = int(total * SR) + SR
    out = np.zeros((2, n))
    xf = 0.8
    for i, (s, e, style) in enumerate(cues):
        if style is None:
            continue
        s0 = max(0.0, s - xf / 2)
        e0 = min(total, e + xf / 2)
        seg = render_style(style, e0 - s0, seed=i)
        m = seg.shape[1]
        fade = np.ones(m)
        k = int(xf * SR)
        if s0 > 0:
            fade[:k] = np.linspace(0, 1, k)
        if e0 < total:
            fade[-k:] = np.minimum(fade[-k:], np.linspace(1, 0, k))
        else:
            k2 = int(2.0 * SR)
            fade[-k2:] = np.minimum(fade[-k2:], np.linspace(1, 0, k2))
        i0 = int(s0 * SR)
        out[:, i0: i0 + m] += seg * fade
    return out[:, : int(total * SR)]


# --------------------------------------------------------------------------
# Sound effects
# --------------------------------------------------------------------------


def _noise(n):
    return RNG.uniform(-1, 1, n)


def sfx(name: str) -> np.ndarray:
    """Return mono SFX."""
    if name == "whoosh":
        n = int(0.55 * SR)
        t = np.arange(n) / SR
        x = _noise(n)
        out = np.zeros(n)
        # sweep a band-pass by chunks
        chunks = 24
        for c in range(chunks):
            a, b = c * n // chunks, (c + 1) * n // chunks
            f = 400 + 3800 * math.sin(math.pi * c / chunks)
            sos = butter(2, [f * 0.6, min(f * 1.6, SR / 2 - 100)], btype="band", fs=SR, output="sos")
            out[a:b] = sosfilt(sos, x[a:b])
        e = np.sin(np.pi * t / t[-1]) ** 2
        return out * e * 0.9
    if name == "pop":
        n = int(0.12 * SR)
        t = np.arange(n) / SR
        f = 900 - 500 * t / t[-1]
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 35) * 0.6
    if name == "ding":
        n = int(1.0 * SR)
        t = np.arange(n) / SR
        x = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, a, d in ((1318, 1, 4), (1976, 0.5, 6), (2637, 0.25, 9)))
        return x * 0.35
    if name == "boom":
        n = int(1.6 * SR)
        t = np.arange(n) / SR
        f = 30 + 70 * np.exp(-t * 6)
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.5)
        sos = butter(2, 300, btype="low", fs=SR, output="sos")
        rumble = sosfilt(sos, _noise(n)) * np.exp(-t * 3) * 2
        return np.tanh((body + rumble) * 1.5) * 0.8
    if name == "riser":
        n = int(1.5 * SR)
        t = np.arange(n) / SR
        f = 200 + 1400 * (t / t[-1]) ** 2
        tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.2
        sos = butter(2, 3000, btype="high", fs=SR, output="sos")
        nz = sosfilt(sos, _noise(n)) * 0.4
        return (tone + nz) * (t / t[-1]) ** 2 * 0.7
    if name == "buzz":
        n = int(0.5 * SR)
        t = np.arange(n) / SR
        x = np.sign(np.sin(2 * np.pi * 170 * t)) * 0.3 * (np.sin(2 * np.pi * 18 * t) > 0)
        sos = butter(2, 600, btype="low", fs=SR, output="sos")
        return sosfilt(sos, x) * 0.9
    if name == "tick":
        n = int(0.05 * SR)
        t = np.arange(n) / SR
        return np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 120) * 0.4
    if name == "knock":
        out = np.zeros(int(0.7 * SR))
        for k in range(3):
            n = int(0.12 * SR)
            t = np.arange(n) / SR
            k_ = np.sin(2 * np.pi * 140 * t) * np.exp(-t * 40) + sosfilt(butter(2, 900, fs=SR, output="sos"), _noise(n)) * np.exp(-t * 50)
            place(out, k_ * 0.6, k * 0.2)
        return out
    if name == "sparkle":
        out = np.zeros(int(1.0 * SR))
        for k, nn in enumerate((84, 88, 91, 96)):
            n = int(0.5 * SR)
            t = np.arange(n) / SR
            place(out, np.sin(2 * np.pi * note_hz(nn) * t) * np.exp(-t * 8) * 0.2, k * 0.07)
        return out
    if name == "sad_trombone":
        out = np.zeros(int(2.2 * SR))
        for k, nn in enumerate((55, 54, 53, 52)):
            dur = 0.45 if k < 3 else 1.0
            n = int(dur * SR)
            t = np.arange(n) / SR
            vib = 1 + (0.01 * np.sin(2 * np.pi * 6 * t) if k == 3 else 0)
            f = note_hz(nn) * vib
            ph = 2 * np.pi * np.cumsum(f * np.ones(n)) / SR
            tone = sum(np.sin(ph * h) / h for h in range(1, 6))
            place(out, tone * env_adsr(n, 0.03, 0.1, 0.8, 0.1, dur) * 0.25, k * 0.45)
        return out
    if name == "heartbeat":
        out = np.zeros(int(1.0 * SR))
        place(out, kick(0.7)[: int(0.2 * SR)], 0)
        place(out, kick(0.5)[: int(0.2 * SR)], 0.22)
        return out
    if name == "ring":
        out = np.zeros(int(2.0 * SR))
        n = int(0.9 * SR)
        t = np.arange(n) / SR
        tone = (np.sin(2 * np.pi * 440 * t) + np.sin(2 * np.pi * 480 * t)) * 0.2 * (np.sin(2 * np.pi * 20 * t) > -0.3)
        place(out, tone * env_adsr(n, 0.01, 0.05, 1, 0.05, 0.9), 0)
        return out
    if name == "camera":
        n = int(0.25 * SR)
        t = np.arange(n) / SR
        return sosfilt(butter(2, 2000, btype="high", fs=SR, output="sos"), _noise(n)) * (np.exp(-t * 40) + 0.6 * np.exp(-(t - 0.1).clip(0) * 40) * (t > 0.1)) * 0.5
    if name == "laugh_track":
        n = int(1.4 * SR)
        t = np.arange(n) / SR
        x = np.zeros(n)
        for k in range(14):
            f0 = 180 + RNG.random() * 250
            st = RNG.random() * 0.3
            mod = (np.sin(2 * np.pi * (5 + RNG.random() * 2) * t) > 0).astype(float)
            x += np.sin(2 * np.pi * f0 * t) * mod * np.exp(-(t - st).clip(0) * 1.5) * (t > st)
        sos = butter(2, [200, 2500], btype="band", fs=SR, output="sos")
        return sosfilt(sos, x) * 0.08
    raise KeyError(name)


# --------------------------------------------------------------------------
# Mix
# --------------------------------------------------------------------------


def duck_curve(voice: np.ndarray, depth=0.6, attack=0.05, release=0.4) -> np.ndarray:
    """Gain curve (0..1) for music, lowered while voice is present."""
    hop = 480
    n = int(np.ceil(len(voice) / hop))
    v = np.zeros(n * hop)
    v[: len(voice)] = np.abs(voice)
    lvl = v.reshape(n, hop).max(axis=1)
    on = (lvl > 0.02).astype(float)
    g = np.zeros(n)
    cur = 0.0
    a = hop / SR / attack
    r = hop / SR / release
    for i in range(n):
        cur = min(1, cur + a) if on[i] else max(0, cur - r)
        g[i] = cur
    gain = 1 - depth * g
    return np.repeat(gain, hop)[: len(voice)]


def master(voice: np.ndarray, music: np.ndarray, fx: np.ndarray, music_level=0.42) -> np.ndarray:
    n = max(len(voice), music.shape[1], fx.shape[1] if fx.ndim == 2 else len(fx))
    out = np.zeros((2, n))
    out[:, : len(voice)] += voice
    g = duck_curve(np.pad(voice, (0, n - len(voice))))
    out[:, : music.shape[1]] += music * music_level * g[: music.shape[1]]
    out[:, : fx.shape[1]] += fx
    # gentle bus compression / limiting
    peak = np.max(np.abs(out)) or 1
    out = np.tanh(out / peak * 1.3) / np.tanh(1.3) * 0.94
    return out.astype(np.float32)
