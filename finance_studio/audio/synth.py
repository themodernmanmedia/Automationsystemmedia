"""Original procedural music beds and sound effects.

Everything here is synthesized from oscillators and noise by this code, so
the studio owns it outright - no sample libraries, no licensing exposure.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000
NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def hz(name: str) -> float:
    """'A4' -> 440.0, 'C#3' -> ..."""
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((NOTE[pitch] + 12 * (octave + 1) - 69) / 12)


def _t(dur):
    return np.arange(int(dur * SR)) / SR


def _filt(x, kind, f, order=2):
    if isinstance(f, (list, tuple)):
        f = [min(max(v, 20), SR / 2 - 100) for v in f]
    else:
        f = min(max(f, 20), SR / 2 - 100)
    return sosfilt(butter(order, f, btype=kind, fs=SR, output="sos"), x, axis=0)


def env_adsr(n, a=0.01, d=0.1, s=0.7, r=0.2):
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    s_n = max(n - a_n - d_n - r_n, 0)
    e = np.concatenate([np.linspace(0, 1, a_n, endpoint=False), np.linspace(1, s, d_n, endpoint=False),
                        np.full(s_n, s), np.linspace(s, 0, r_n)])
    return np.pad(e, (0, max(0, n - len(e))))[:n]


def reverb(x, seconds=1.8, mix=0.25, seed=3):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    ir = rng.standard_normal((n, 2)) * np.exp(-np.linspace(0, 7, n))[:, None]
    ir = _filt(ir, "lowpass", 6000)
    ir /= np.sqrt((ir ** 2).sum(axis=0))
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    wet = np.stack([fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], 1)
    return (1 - mix) * x + mix * wet


def write_wav(path: Path, x: np.ndarray, peak_db: float = -1.0) -> Path:
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    pk = np.max(np.abs(x)) or 1.0
    x = x / pk * 10 ** (peak_db / 20)
    data = (np.clip(x, -1, 1) * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    return path


def _place(buf, sig, t0, pan=0.0, gain=1.0):
    i = int(t0 * SR)
    if i >= len(buf):
        return
    sig = sig[: len(buf) - i]
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[i:i + len(sig), 0] += sig * l * gain
    buf[i:i + len(sig), 1] += sig * r * gain


# ----------------------------------------------------------------- instruments
def keys_note(f, dur=1.2, bright=1.0):
    t = _t(dur)
    x = (np.sin(2 * np.pi * f * t) + 0.35 * bright * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 4)
         + 0.12 * bright * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t * 7))
    return x * np.exp(-t * 2.6) * env_adsr(len(t), 0.004, 0.05, 1.0, 0.08)


def pad_chord(freqs, dur, rng):
    t = _t(dur)
    x = np.zeros_like(t)
    for f in freqs:
        for det in (-0.25, 0.0, 0.3):
            ph = rng.uniform(0, 2 * np.pi)
            ff = f * 2 ** (det / 1200 * 12)
            x += sum(np.sin(2 * np.pi * ff * k * t + ph) / k ** 1.3 for k in (1, 2, 3, 4))
    x = _filt(x, "lowpass", 1800)
    return x * env_adsr(len(t), 0.9, 0.3, 0.85, 0.9) / (len(freqs) * 3)


def bass_note(f, dur):
    t = _t(dur)
    x = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t)
    return x * env_adsr(len(t), 0.01, 0.3, 0.55, 0.3)


def soft_kick(dur=0.35):
    t = _t(dur)
    f = 50 + 70 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11)


def tick(dur=0.05, seed=0):
    rng = np.random.default_rng(seed)
    n = rng.standard_normal(int(dur * SR))
    return _filt(n, "highpass", 7000) * np.exp(-_t(dur) * 90)


CHORDS = {
    "Cmaj7": ["C3", "E3", "G3", "B3"], "Fmaj7": ["F2", "A3", "C4", "E4"], "Am7": ["A2", "C4", "E4", "G4"],
    "G6": ["G2", "B3", "D4", "E4"], "Am": ["A2", "C4", "E4", "A4"], "F": ["F2", "A3", "C4", "F4"],
    "Dm7": ["D3", "F3", "A3", "C4"], "Esus4": ["E2", "A3", "B3", "E4"], "E7": ["E2", "G#3", "B3", "D4"],
}


def music_bed(sections: list[dict], total: float, bpm: float = 84, seed: int = 11) -> np.ndarray:
    """sections: [{start, end, chords:[...], mood: 'hopeful'|'tension'|'resolve'}]"""
    rng = np.random.default_rng(seed)
    buf = np.zeros((int((total + 2.5) * SR), 2))
    beat = 60 / bpm
    for sec in sections:
        chords, mood = sec["chords"], sec.get("mood", "hopeful")
        span = sec["end"] - sec["start"]
        per = span / len(chords)
        for ci, name in enumerate(chords):
            t0 = sec["start"] + ci * per
            notes = [hz(n) for n in CHORDS[name]]
            _place(buf, pad_chord(notes, per + 0.9, rng), t0, 0.0, 0.55)
            _place(buf, bass_note(notes[0] / (1 if notes[0] < 90 else 2), per), t0, 0, 0.5)
            n_eighths = int(per / (beat / 2))
            arp = notes[1:] + [notes[1] * 2]
            for k in range(n_eighths):
                if mood == "tension" and k % 2:
                    continue
                f = arp[(k * (1 if mood != "tension" else 3)) % len(arp)] * (2 if mood == "hopeful" else 1)
                _place(buf, keys_note(f, 1.1, 0.8 if mood == "tension" else 1.0),
                       t0 + k * beat / 2 + rng.normal(0, 0.004), pan=0.35 * (-1) ** k,
                       gain=0.22 * (1.0 if k % 4 == 0 else 0.75))
            if mood == "tension":
                for k in range(int(per / beat)):
                    _place(buf, soft_kick(), t0 + k * beat, 0, 0.35)
                    _place(buf, tick(seed=k), t0 + k * beat + beat / 2, 0.25, 0.06)
    out = reverb(buf, 2.2, 0.32)
    fade = int(1.2 * SR)
    end = int((total + 0.5) * SR)
    out = out[:end]
    out[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return out


# ----------------------------------------------------------------- sound effects
def sfx(kind: str, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if kind == "footstep":
        d = 0.09
        n = rng.standard_normal(int(d * SR))
        x = _filt(n, "bandpass", [180, 1600]) * np.exp(-_t(d) * 55)
        return x * (0.8 + 0.4 * rng.random())
    if kind == "coin":
        x = np.zeros(int(1.1 * SR))
        for j, f in enumerate((hz("E7"), hz("B7"))):
            t = _t(1.1 - j * 0.07)
            s = sum(a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * dcy)
                    for m, a, dcy in ((1, 1, 5), (2.76, 0.5, 9), (5.4, 0.25, 14)))
            x[int(j * 0.07 * SR):int(j * 0.07 * SR) + len(s)] += s * 0.6
        cha = _filt(rng.standard_normal(int(0.08 * SR)), "highpass", 4000) * np.exp(-_t(0.08) * 50)
        x[: len(cha)] += cha * 0.5
        return x
    if kind == "pop":
        d = 0.12
        t = _t(d)
        f = 420 + 900 * (t / d)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 32)
    if kind == "whoosh":
        d = 0.75
        t = _t(d)
        n = rng.standard_normal(len(t))
        lo = _filt(n, "bandpass", [300, 1200])
        hi = _filt(n, "bandpass", [1200, 5000])
        mixf = np.sin(np.pi * t / d)
        return (lo * (1 - mixf) + hi * mixf) * np.sin(np.pi * t / d) ** 2
    if kind == "poof":
        d = 0.5
        t = _t(d)
        n = _filt(rng.standard_normal(len(t)), "lowpass", 1400) * np.exp(-t * 9)
        bloop = np.sin(2 * np.pi * np.cumsum(520 * np.exp(-t * 5)) / SR) * np.exp(-t * 10)
        return n * 0.8 + bloop * 0.5
    if kind == "blip":
        d = 0.15
        t = _t(d)
        return np.sin(2 * np.pi * 880 * t) * np.exp(-t * 25) + 0.3 * np.sin(2 * np.pi * 1760 * t) * np.exp(-t * 40)
    if kind == "downer":  # two soft descending notes - "that didn't go as planned"
        x = np.zeros(int(1.3 * SR))
        for j, f in enumerate((hz("E4"), hz("C4"))):
            s = keys_note(f, 1.0, 0.6)
            x[int(j * 0.28 * SR):int(j * 0.28 * SR) + len(s)] += s
        return x
    raise ValueError(f"unknown sfx kind {kind}")


SFX_KINDS = ("footstep", "coin", "pop", "whoosh", "poof", "blip", "downer")


def sfx_track(events: list[dict], total: float) -> np.ndarray:
    """events: [{t, kind, gain?, pan?, seed?}] -> stereo buffer"""
    buf = np.zeros((int((total + 1.5) * SR), 2))
    for i, e in enumerate(events):
        _place(buf, sfx(e["kind"], e.get("seed", i)), e["t"], e.get("pan", 0.0), e.get("gain", 1.0))
    return reverb(buf, 0.9, 0.12)[: int(total * SR)]
