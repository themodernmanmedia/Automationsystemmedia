"""Narration timeline, ducked music, SFX and loudness-normalized final mix."""
from __future__ import annotations

import json
import re
import wave
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

from core.tools import ffmpeg_bin, run

from .synth import SR, write_wav


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        data = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float64) / 32768
    data = data.reshape(-1, ch).mean(axis=1) if ch > 1 else data
    if sr != SR:
        data = resample_poly(data, SR, sr)
    return data


def layout_lines(durations: list[float], lead: float = 0.5, gaps: list[float] | float = 0.35) -> list[tuple[float, float]]:
    """Start/end time for each narration line given pause lengths between lines."""
    out, t = [], lead
    for i, d in enumerate(durations):
        out.append((round(t, 3), round(t + d, 3)))
        g = gaps[i] if isinstance(gaps, list) and i < len(gaps) else (gaps if not isinstance(gaps, list) else 0.35)
        t += d + g
    return out


def narration_track(paths: list[Path], timings: list[tuple[float, float]], total: float) -> np.ndarray:
    buf = np.zeros(int(total * SR))
    for p, (t0, _) in zip(paths, timings):
        x = read_wav(p)
        i = int(t0 * SR)
        buf[i:i + len(x)] += x[: max(0, len(buf) - i)]
    return buf


def envelope(x: np.ndarray, attack=0.02, release=0.35) -> np.ndarray:
    """Smoothed amplitude envelope (peak follower) - used for ducking and lip-sync."""
    a, r = np.exp(-1 / (attack * SR)), np.exp(-1 / (release * SR))
    env = np.empty_like(x)
    level = 0.0
    ax = np.abs(x)
    # vectorize coarsely in 1 ms blocks for speed
    blk = SR // 1000
    blocks = ax[: len(ax) // blk * blk].reshape(-1, blk).max(axis=1)
    out = np.empty_like(blocks)
    ab, rb = a ** blk, r ** blk
    for i, v in enumerate(blocks):
        level = ab * level + (1 - ab) * v if v > level else rb * level + (1 - rb) * v
        out[i] = level
    env[: len(out) * blk] = np.repeat(out, blk)
    env[len(out) * blk:] = out[-1] if len(out) else 0
    return env


def db(x):
    return 10 ** (x / 20)


def mix(narration: np.ndarray, music: np.ndarray, sfx: np.ndarray, *, music_gain_db=-22.0,
        duck_db=-8.0, sfx_gain_db=-10.0) -> np.ndarray:
    n = len(narration)
    music = np.pad(music, ((0, max(0, n - len(music))), (0, 0)))[:n]
    sfx = np.pad(sfx, ((0, max(0, n - len(sfx))), (0, 0)))[:n]
    env = envelope(narration)
    speaking = np.clip(env / (np.percentile(env[env > 1e-4], 60) if (env > 1e-4).any() else 1), 0, 1)
    duck = db(music_gain_db) * (1 - speaking * (1 - db(duck_db)))
    voice = np.stack([narration, narration], 1)
    voice /= (np.max(np.abs(voice)) or 1)
    return voice * db(-3) + music / (np.max(np.abs(music)) or 1) * duck[:, None] \
        + sfx / (np.max(np.abs(sfx)) or 1) * db(sfx_gain_db)


def loudnorm(src: Path, dst: Path, lufs=-16.0, tp=-1.5, lra=11.0) -> dict:
    """Two-pass EBU R128 normalization. Returns measured stats of the output."""
    first = run([ffmpeg_bin(), "-hide_banner", "-i", str(src), "-af",
                 f"loudnorm=I={lufs}:TP={tp}:LRA={lra}:print_format=json", "-f", "null", "-"])
    m = json.loads(re.findall(r"\{[^{}]+\}", first.stderr)[-1])
    run([ffmpeg_bin(), "-y", "-v", "error", "-i", str(src), "-af",
         f"loudnorm=I={lufs}:TP={tp}:LRA={lra}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
         f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}"
         f":linear=true", "-ar", str(SR), "-c:a", "pcm_s16le", str(dst)])
    return measure_loudness(dst)


def measure_loudness(path: Path) -> dict:
    out = run([ffmpeg_bin(), "-hide_banner", "-i", str(path), "-af",
               "loudnorm=print_format=json", "-f", "null", "-"]).stderr
    m = json.loads(re.findall(r"\{[^{}]+\}", out)[-1])
    return {"integrated_lufs": float(m["input_i"]), "true_peak_db": float(m["input_tp"]),
            "lra": float(m["input_lra"])}


def save_mix(x: np.ndarray, path: Path) -> Path:
    return write_wav(path, x, peak_db=-3.0)
