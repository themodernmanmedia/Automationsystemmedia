"""Render a character model sheet: poses x expressions, for consistency review.

    python -m characters.model_sheet maya
"""
from __future__ import annotations

import sys
from pathlib import Path

from animation.motion import CharacterAnimator, CharacterDirection
from animation.render import ROOT, run_job

SHEET = [
    ("stand", "neutral", [], 0.0),
    ("walk", "happy", [{"type": "walk", "start": 0, "end": 5}], 0.0),
    ("run", "determined", [{"type": "run", "start": 0, "end": 5}], 0.0),
    ("hold_up", "excited", [{"type": "pose", "name": "hold_up", "start": 0, "end": 5}], 0.0),
    ("point", "happy", [{"type": "pose", "name": "point", "start": 0, "end": 5}], 0.0),
    ("head_scratch", "confused", [{"type": "pose", "name": "head_scratch", "start": 0, "end": 5}], 0.0),
    ("worried_hands", "worried", [{"type": "pose", "name": "worried_hands", "start": 0, "end": 5}], 0.0),
    ("hands_up", "surprised", [{"type": "pose", "name": "hands_up", "start": 0, "end": 5}], 0.0),
    ("shrug", "sad", [{"type": "pose", "name": "shrug", "start": 0, "end": 5}], 0.0),
    ("sit", "neutral", [{"type": "sit", "start": 0, "end": 5}], 0.0),
]


def build_job(character: str, out_png: Path) -> dict:
    fps, sample_frame = 30, 40  # mid-action, after blends settle; not on a blink
    chars = []
    cols, spacing = 5, 5.2
    for i, (pose, expr, actions, _) in enumerate(SHEET):
        col, row = i % cols, i // cols
        x = (col - (cols - 1) / 2) * spacing
        y = 1.2 - row * 7.0
        d = CharacterDirection(character, start_x=0.0, actions=actions,
                               expressions=[{"at": 0, "name": expr}], blink_seed=1000 + i)
        ch = CharacterAnimator(d, fps).bake(sample_frame + 1)
        ch = {k: [v[sample_frame]] for k, v in ch.items()}
        ch["x"] = [x]
        ch["y"] = [ch["y"][0] + y]
        chars.append({"id": f"{character}{i}", "spec": str(ROOT / f"characters/specs/{character}.json"),
                      "channels": ch, "shadow": False})
    return {"fps": fps, "resolution": [1920, 1080], "frame_start": 1, "frame_end": 1, "samples": 8,
            "output_dir": str(out_png.parent), "background": {"kind": "solid", "color": "#EFE8DC"},
            "characters": chars, "camera": {"x": [0.0], "y": [-1.6], "width": [27.5]},
            "still_frame": 1, "still_path": str(out_png)}


def main(character: str = "maya") -> Path:
    out = ROOT / "output" / "model_sheets" / f"{character}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    run_job(build_job(character, out), out.parent / f"{character}_job.json")
    return out


if __name__ == "__main__":
    print(main(*(sys.argv[1:] or ["maya"])))
