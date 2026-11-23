"""SRT subtitles from timed narration lines, split into readable cues."""
from __future__ import annotations

import re
from pathlib import Path

MAX_CHARS = 42      # per line - standard broadcast/YouTube readability guideline
MAX_LINES = 2


def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _wrap(text: str, width: int = MAX_CHARS) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def split_cues(text: str, start: float, end: float) -> list[tuple[float, float, str]]:
    """Split a long line into cues of <= 2 x 42 chars, timing proportional to characters."""
    lines = _wrap(text)
    chunks = ["\n".join(lines[i:i + MAX_LINES]) for i in range(0, len(lines), MAX_LINES)]
    total = sum(len(c) for c in chunks) or 1
    out, t = [], start
    for c in chunks:
        d = (end - start) * len(c) / total
        out.append((t, t + d, c))
        t += d
    return out


def build_srt(lines: list[dict]) -> str:
    """lines: [{text, start, end}] -> SRT document."""
    cues = []
    for ln in lines:
        cues += split_cues(re.sub(r"\s+", " ", ln["text"]).strip(), ln["start"], ln["end"])
    return "\n".join(f"{i}\n{_ts(a)} --> {_ts(b)}\n{txt}\n" for i, (a, b, txt) in enumerate(cues, 1))


def write_srt(lines: list[dict], path: Path) -> Path:
    path.write_text(build_srt(lines), encoding="utf-8")
    return path
