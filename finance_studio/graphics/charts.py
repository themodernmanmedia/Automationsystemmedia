"""Manim financial graphics, rendered with a transparent background for compositing.

Each chart reads its parameters from a JSON file named by FINSTUDIO_CHART_PARAMS,
so the pipeline can render data-driven charts without editing code.

Every chart carries a source/caption line. Illustrative (hypothetical)
numbers must say so on screen - the pipeline enforces a non-empty caption.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from core.tools import ToolFailed, run

BRAND = {"ink": "#2A2230", "paper": "#FBF6EC", "green": "#2FA866", "red": "#E0524A", "gold": "#E3A72F",
         "muted": "#8C8296"}
FONT = "Inter"


def _scene_code() -> str:
    return r'''
import json, os
from manim import *

P = json.load(open(os.environ["FINSTUDIO_CHART_PARAMS"]))
B = P["brand"]
FONT = P.get("font", "Inter")


class Waterfall(Scene):
    def construct(self):
        self.camera.background_color = ManimColor("#000000")
        # panel occupies a region of the 16:9 frame given in frame units (frame is 14.22 x 8)
        px, py, pw, ph = P["panel"]
        panel = RoundedRectangle(corner_radius=0.28, width=pw, height=ph, fill_color=B["paper"], fill_opacity=0.97,
                                 stroke_color=B["ink"], stroke_width=5).move_to([px, py, 0])
        shadow = panel.copy().set_fill(B["ink"], 0.35).set_stroke(width=0).shift(RIGHT * 0.1 + DOWN * 0.12)
        title = Text(P["title"], font=FONT, weight=BOLD, color=B["ink"]).scale(0.42)
        title.move_to([px, py + ph / 2 - 0.55, 0])
        cap = Text(P["caption"], font=FONT, color=B["muted"]).scale(0.26)
        cap.move_to([px, py - ph / 2 + 0.38, 0])
        self.play(FadeIn(shadow, shift=LEFT * 0.4), FadeIn(panel, shift=LEFT * 0.4), run_time=0.45)
        self.play(Write(title), FadeIn(cap), run_time=0.45)

        bars = P["bars"]
        vmax = max(abs(b["value"]) for b in bars) or 1
        base_y = py - ph / 2 + 1.25
        top_y = py + ph / 2 - 1.35
        scale = (top_y - base_y) / vmax
        n = len(bars)
        slot = (pw - 1.0) / n
        x0 = px - pw / 2 + 0.5 + slot / 2
        axis = Line([px - pw / 2 + 0.35, base_y, 0], [px + pw / 2 - 0.35, base_y, 0], color=B["ink"], stroke_width=4)
        self.play(Create(axis), run_time=0.3)
        level = 0.0
        step_t = P.get("step_time", 0.6)
        for i, b in enumerate(bars):
            x = x0 + i * slot
            v = b["value"]
            kind = b.get("kind", "delta")
            if kind == "total":
                lo, hi = 0.0, level
            else:
                lo, hi = (level, level + v) if v >= 0 else (level + v, level)
            h = max((hi - lo) * scale, 0.04)
            color = B["green"] if (v > 0 and kind != "total") else (B["red"] if v < 0 else B["muted"])
            rect = Rectangle(width=slot * 0.62, height=h, fill_color=color, fill_opacity=1, stroke_color=B["ink"],
                             stroke_width=4)
            rect.move_to([x, base_y + (lo + hi) / 2 * scale, 0])
            label = Text(b["label"], font=FONT, weight=SEMIBOLD, color=B["ink"]).scale(0.27)
            label.next_to([x, base_y, 0], DOWN, buff=0.18)
            val = Text(b["text"], font=FONT, weight=BOLD, color=color if kind != "total" else B["ink"]).scale(0.36)
            val.next_to(rect, UP, buff=0.12)
            if kind == "total" and h <= 0.05:
                val.move_to([x, base_y + 0.35, 0])
            grow_from = DOWN if v >= 0 else UP
            if kind == "total" and h <= 0.05:
                self.play(FadeIn(label), FadeIn(val, scale=1.4), run_time=step_t)
            else:
                self.play(GrowFromEdge(rect, grow_from), FadeIn(label), FadeIn(val, shift=UP * 0.1), run_time=step_t)
            if kind != "total" and i + 1 < len(bars):
                nxt = level + v
                conn = DashedLine([x + slot * 0.31, base_y + nxt * scale, 0],
                                  [x + slot * 0.69, base_y + nxt * scale, 0], color=B["ink"], stroke_width=3,
                                  dash_length=0.08)
                self.add(conn)
            if kind != "total":
                level += v
        self.wait(P.get("hold", 1.0))
'''


def render_waterfall(params: dict, out_mov: Path, fps: int = 30, size=(1920, 1080)) -> Path:
    if not params.get("caption"):
        raise ValueError("charts must carry a caption (source or 'Illustrative example')")
    params = {"brand": BRAND, "font": FONT, **params}
    out_mov.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "scene.py").write_text(_scene_code())
        (td / "params.json").write_text(json.dumps(params))
        manim = shutil.which("manim") or str(Path(os.sys.executable).parent / "manim")
        try:
            run([manim, "render", "-q", "h", "--fps", str(fps), "-r", f"{size[0]},{size[1]}", "-t",
                 "--format", "mov", "--media_dir", str(td / "media"), "--disable_caching", str(td / "scene.py"),
                 "Waterfall"], cwd=td, env={"FINSTUDIO_CHART_PARAMS": str(td / "params.json")}, timeout=900)
        except ToolFailed as exc:
            raise ToolFailed(f"manim render failed: {exc}") from exc
        movs = list((td / "media").rglob("Waterfall.mov"))
        if not movs:
            raise ToolFailed("manim produced no Waterfall.mov")
        shutil.copyfile(movs[0], out_mov)
    return out_mov
