"""Render a Manim template to a video file (opaque MP4, or transparent MOV for overlays)."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from core.tools import ToolFailed, run

TEMPLATES = Path(__file__).resolve().parent / "manim_templates.py"
SCENES = {"BigNumber", "Bars", "Compare", "Quote", "PriceLevel", "Checklist", "TitleCard", "Waterfall"}


def render_template(scene: str, params: dict, out: Path, fps: int = 30, size=(1920, 1080)) -> Path:
    if scene not in SCENES:
        raise ValueError(f"unknown manim template {scene}")
    if scene not in ("TitleCard", "PriceLevel", "Checklist", "Quote") and not params.get("source"):
        raise ValueError(f"{scene} shows data, so it needs a 'source' line")
    transparent = bool(params.get("transparent"))
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "params.json").write_text(json.dumps(params))
        shutil.copyfile(TEMPLATES, td / "scene.py")
        manim = shutil.which("manim") or str(Path(os.sys.executable).parent / "manim")
        cmd = [manim, "render", "-q", "h", "--fps", str(fps), "-r", f"{size[0]},{size[1]}", "--media_dir",
               str(td / "media"), "--disable_caching", str(td / "scene.py"), scene]
        if transparent:
            cmd[2:2] = ["-t", "--format", "mov"]
        try:
            run(cmd, cwd=td, env={"FINSTUDIO_PARAMS": str(td / "params.json")}, timeout=1800)
        except ToolFailed as exc:
            raise ToolFailed(f"manim {scene} failed: {exc}") from exc
        files = list((td / "media").rglob(f"{scene}.mov" if transparent else f"{scene}.mp4"))
        if not files:
            raise ToolFailed(f"manim produced no output for {scene}")
        shutil.copyfile(files[0], out)
    return out
