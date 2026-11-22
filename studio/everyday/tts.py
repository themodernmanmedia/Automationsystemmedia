"""Neural text-to-speech with Kokoro (local ONNX, no API key) + lip-sync envelopes."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import dataclass

import numpy as np
from scipy.signal import resample_poly

from .config import CACHE_DIR, FPS, KOKORO_MODEL, KOKORO_URLS, KOKORO_VOICES, MODELS_DIR, SAMPLE_RATE


@dataclass(frozen=True)
class Voice:
    voice: str
    speed: float = 1.0
    lang: str = "en-us"
    gain: float = 1.0


_kokoro = None


def ensure_models() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for path in (KOKORO_MODEL, KOKORO_VOICES):
        if not path.exists() or path.stat().st_size < 1000:
            url = KOKORO_URLS[path.name]
            print(f"  downloading {path.name} …")
            urllib.request.urlretrieve(url, path)


def _engine():
    global _kokoro
    if _kokoro is None:
        ensure_models()
        from kokoro_onnx import Kokoro

        _kokoro = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
    return _kokoro


def _trim(x: np.ndarray, sr: int, thresh=0.01, pad=0.04) -> np.ndarray:
    idx = np.where(np.abs(x) > thresh)[0]
    if len(idx) == 0:
        return x
    a = max(0, idx[0] - int(pad * sr))
    b = min(len(x), idx[-1] + int(pad * sr * 2))
    return x[a:b]


def synth(text: str, v: Voice) -> np.ndarray:
    """Return mono float32 audio at SAMPLE_RATE. Cached on disk."""
    key = hashlib.sha1(json.dumps([text, v.voice, v.speed, v.lang]).encode()).hexdigest()[:16]
    cache = CACHE_DIR / "tts"
    cache.mkdir(parents=True, exist_ok=True)
    f = cache / f"{key}.npy"
    if f.exists():
        return np.load(f)
    samples, sr = _engine().create(text, voice=v.voice, speed=v.speed, lang=v.lang)
    samples = _trim(np.asarray(samples, dtype=np.float32), sr)
    up = resample_poly(samples, SAMPLE_RATE, sr).astype(np.float32)
    peak = np.max(np.abs(up)) or 1.0
    up = up / peak * 0.89 * v.gain
    np.save(f, up)
    return up


def mouth_envelope(audio: np.ndarray, fps: int = FPS) -> np.ndarray:
    """Per-frame mouth openness 0..1 from speech energy (simple, reads well)."""
    hop = SAMPLE_RATE // fps
    n = int(np.ceil(len(audio) / hop))
    pad = np.zeros(n * hop, dtype=np.float32)
    pad[: len(audio)] = audio
    frames = pad.reshape(n, hop)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    if rms.max() > 0:
        rms = rms / np.percentile(rms, 95)
    env = np.clip((rms - 0.12) * 1.3, 0, 1)
    # attack fast / release slower, then add syllable flutter so mouths don't freeze open
    out = np.zeros_like(env)
    prev = 0.0
    for i, e in enumerate(env):
        prev = e if e > prev else prev * 0.55 + e * 0.45
        out[i] = prev
    flutter = 0.75 + 0.25 * np.abs(np.sin(np.arange(n) * 1.9))
    return np.clip(out * flutter, 0, 1).astype(np.float32)
