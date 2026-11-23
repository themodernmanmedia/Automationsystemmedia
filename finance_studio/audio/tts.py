"""Text-to-speech providers behind one interface, with caching and retries.

Production voice: ElevenLabs (paid plans include a commercial-use license).
`espeak` is a robotic local fallback for drafts/tests and is flagged as such
everywhere it is used - never publish it. `file` imports narration recorded
or generated elsewhere (one audio file per line).
"""
from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import requests

from core.cache import AssetCache, stable_hash
from core.logging_setup import get_logger
from core.retry import PermanentError, retry
from core.tools import ffmpeg_bin, find_tool, media_duration, run

log = get_logger("tts")
SAMPLE_RATE = 48000


class TTSUnavailable(RuntimeError):
    pass


@dataclass
class VoiceLine:
    index: int
    text: str
    path: Path
    duration: float
    provider: str
    draft: bool  # True = not acceptable for publishing


def to_wav48k(src: Path, dst: Path, trim_silence: bool = True) -> Path:
    """Normalize any audio to 48 kHz mono WAV; trim leading/trailing silence, clean low rumble."""
    af = ["highpass=f=70", "lowpass=f=16000"]
    if trim_silence:
        af += ["silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.02",
               "areverse", "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05",
               "areverse"]
    run([ffmpeg_bin(), "-y", "-v", "error", "-i", str(src), "-ac", "1", "-ar", str(SAMPLE_RATE),
         "-af", ",".join(af), "-c:a", "pcm_s16le", str(dst)])
    return dst


class Provider:
    name = "base"
    draft = False

    def synth(self, text: str, out: Path) -> Path:  # returns raw audio path (any format)
        raise NotImplementedError

    def cache_params(self) -> dict:
        return {}


class EspeakProvider(Provider):
    name, draft = "espeak", True

    def __init__(self, voice: str = "en-us", speed_wpm: int = 150, pitch: int = 45):
        self.bin = find_tool("espeak-ng")
        self.voice, self.speed, self.pitch = voice, speed_wpm, pitch

    def synth(self, text, out):
        run([self.bin, "-v", self.voice, "-s", str(self.speed), "-p", str(self.pitch), "-w", str(out), text])
        return out

    def cache_params(self):
        return {"voice": self.voice, "speed": self.speed, "pitch": self.pitch}


class ElevenLabsProvider(Provider):
    name = "elevenlabs"
    URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}"

    def __init__(self, api_key: str | None, voice_id: str | None, model_id: str = "eleven_multilingual_v2",
                 stability=0.5, similarity_boost=0.75, style=0.15, retries: int = 3):
        if not api_key:
            raise TTSUnavailable("ELEVENLABS_API_KEY is not set")
        if not voice_id:
            raise TTSUnavailable("No ElevenLabs voice id configured (tts.elevenlabs.voice_id / ELEVENLABS_VOICE_ID)")
        self.key, self.voice, self.model = api_key, voice_id, model_id
        self.settings = {"stability": stability, "similarity_boost": similarity_boost, "style": style,
                         "use_speaker_boost": True}
        self._post = retry(attempts=retries, backoff=2.0, exceptions=(requests.RequestException, IOError))(self._post_once)

    def _post_once(self, text, out, previous_text=None, next_text=None):
        body = {"text": text, "model_id": self.model, "voice_settings": self.settings}
        if previous_text:
            body["previous_text"] = previous_text  # keeps intonation continuous across lines
        if next_text:
            body["next_text"] = next_text
        r = requests.post(self.URL.format(voice=self.voice), json=body, timeout=120,
                          headers={"xi-api-key": self.key, "accept": "audio/mpeg"},
                          params={"output_format": "mp3_44100_192"})
        if r.status_code in (401, 403, 422):
            raise PermanentError(f"ElevenLabs rejected the request ({r.status_code}): {r.text[:200]}")
        if r.status_code == 429 or r.status_code >= 500:
            raise IOError(f"ElevenLabs temporary error {r.status_code}")
        r.raise_for_status()
        out.write_bytes(r.content)
        return out

    def synth(self, text, out, previous_text=None, next_text=None):
        return self._post(text, out.with_suffix(".mp3"), previous_text, next_text)

    def cache_params(self):
        return {"voice": self.voice, "model": self.model, **self.settings}


def split_on_pauses(src: Path, n_lines: int, out_dir: Path, min_pause: float = 0.12) -> list[Path]:
    """Split one narration take into n_lines files at its n_lines-1 longest pauses.

    Generating a whole script in one take keeps the narrator's intonation natural;
    splitting at the sentence pauses restores per-line timing for animation sync.
    """
    import re
    out = run([ffmpeg_bin(), "-hide_banner", "-i", str(src), "-af", f"silencedetect=n=-40dB:d={min_pause}",
               "-f", "null", "-"]).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    total = media_duration(src)
    gaps = [(e - s, (s + e) / 2) for s, e in zip(starts, ends) if 0.05 < s and e < total - 0.05]
    if len(gaps) < n_lines - 1:
        raise TTSUnavailable(f"found only {len(gaps)} pauses in {src.name}, need {n_lines - 1} to split the lines")
    cuts = sorted(mid for _, mid in sorted(gaps, reverse=True)[: n_lines - 1])
    bounds = [0.0] + cuts + [total]
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, (a, b) in enumerate(zip(bounds, bounds[1:])):
        dst = out_dir / f"line_{i:02d}.wav"
        run([ffmpeg_bin(), "-y", "-v", "error", "-i", str(src), "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
             "-ac", "1", "-ar", str(SAMPLE_RATE), str(dst)])
        paths.append(dst)
    return paths


class FileProvider(Provider):
    """Narration supplied as files: <dir>/line_00.(wav|mp3), line_01... or one full take
    (<dir>/full.(mp3|wav)) which is split into lines at its longest pauses."""
    name = "file"

    def __init__(self, directory: Path, n_lines: int | None = None):
        self.dir = Path(directory)
        if not self.dir.is_dir():
            raise TTSUnavailable(f"narration directory not found: {self.dir}")
        full = sorted(self.dir.glob("full.*"))
        if full and n_lines:
            split_on_pauses(full[0], n_lines, self.dir / "split")
            self.dir = self.dir / "split"
        self._i = 0

    def synth(self, text, out):
        cands = sorted(self.dir.glob(f"line_{self._i:02d}.*"))
        if not cands:
            raise TTSUnavailable(f"missing narration file line_{self._i:02d}.* in {self.dir}")
        self._i += 1
        return cands[0]

    def cache_params(self):
        return {"dir": str(self.dir.resolve()), "i": self._i}


def make_provider(settings, override: str | None = None, n_lines: int | None = None) -> Provider:
    name = override or settings.get("tts.provider", "elevenlabs")
    if name.startswith("file:"):
        return FileProvider(Path(name[5:]), n_lines)
    if name == "elevenlabs":
        import os
        el = settings.get("tts.elevenlabs", {}) or {}
        try:
            return ElevenLabsProvider(settings.secret("ELEVENLABS_API_KEY"),
                                      el.get("voice_id") or os.environ.get("ELEVENLABS_VOICE_ID"),
                                      el.get("model_id", "eleven_multilingual_v2"), el.get("stability", 0.5),
                                      el.get("similarity_boost", 0.75), el.get("style", 0.15))
        except TTSUnavailable as exc:
            if override or not settings.get("tts.allow_draft_voice", False):
                raise
            log.warning("Production voice unavailable (%s) - falling back to DRAFT espeak voice", exc)
            name = settings.get("tts.fallback_provider", "espeak")
    if name == "espeak":
        es = settings.get("tts.espeak", {}) or {}
        return EspeakProvider(es.get("voice", "en-us"), es.get("speed_wpm", 150))
    raise TTSUnavailable(f"unknown TTS provider {name}")


def synthesize_lines(lines: list[str], provider: Provider, out_dir: Path, cache: AssetCache) -> list[VoiceLine]:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = []
    for i, text in enumerate(lines):
        key = stable_hash("tts-v2", provider.name, provider.cache_params(), text,
                          lines[i - 1] if i else None, lines[i + 1] if i + 1 < len(lines) else None)
        dst = out_dir / f"line_{i:02d}.wav"
        hit = cache.get("tts", key, ".wav")
        if hit and not isinstance(provider, FileProvider):
            shutil.copyfile(hit, dst)
            log.info("tts line %d: cache hit", i)
        else:
            with tempfile.TemporaryDirectory() as td:
                raw = Path(td) / f"raw_{i}.wav"
                if isinstance(provider, ElevenLabsProvider):
                    raw = provider.synth(text, raw, lines[i - 1] if i else None,
                                         lines[i + 1] if i + 1 < len(lines) else None)
                else:
                    raw = provider.synth(text, raw)
                to_wav48k(Path(raw), dst)
            cache.put("tts", key, dst)
            log.info("tts line %d: synthesized via %s", i, provider.name)
        result.append(VoiceLine(i, text, dst, media_duration(dst), provider.name, provider.draft))
    return result
