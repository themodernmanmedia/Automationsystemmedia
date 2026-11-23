"""Import per-scene narration takes (e.g. ElevenLabs downloads) into per-line files.

    python -m audio.import_takes <takes_dir> <storyboard.py> <out_dir>

<takes_dir> holds one audio file per scene named <scene_id>.(mp3|wav) - or, if the
user downloaded them from ElevenLabs with default names, a takes.json manifest
mapping scene_id -> filename. Each take is split into that scene's lines at its
longest pauses, producing line_000.wav ... in global order, ready for
`python main.py episode <storyboard> --voice file:<out_dir>`.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from animation.director import load_storyboard

from .tts import split_on_pauses


def import_takes(takes_dir: Path, storyboard: Path, out_dir: Path) -> int:
    sb = load_storyboard(storyboard)
    manifest = {}
    if (takes_dir / "takes.json").exists():
        manifest = json.loads((takes_dir / "takes.json").read_text())
    out_dir.mkdir(parents=True, exist_ok=True)
    idx, missing = 0, []
    for sc in sb.SCENES:
        if not sc.lines:
            continue
        src = takes_dir / manifest[sc.id] if sc.id in manifest else next(
            (p for p in takes_dir.glob(f"{sc.id}.*") if p.suffix in (".mp3", ".wav")), None)
        if not src or not src.exists():
            missing.append(sc.id)
            idx += len(sc.lines)
            continue
        if len(sc.lines) == 1:
            parts = [src]
        else:
            parts = split_on_pauses(src, len(sc.lines), out_dir / "_split" / sc.id,
                                    weights=[len(l) for l in sc.lines])
        for p in parts:
            shutil.copyfile(p, out_dir / f"line_{idx:02d}{p.suffix}")
            idx += 1
    if missing:
        raise SystemExit(f"missing takes for: {', '.join(missing)}")
    return idx


if __name__ == "__main__":
    n = import_takes(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
    print(f"imported {n} narration lines")
