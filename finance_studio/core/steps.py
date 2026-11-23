"""Registry of the 14 production steps, in order.

Steps whose phase hasn't been built raise NotImplementedStep, so the pipeline
reports exactly how far real production gets instead of faking output.
"""
from __future__ import annotations

import json
from datetime import date

from .pipeline import (ApprovalRequired, Context, NotImplementedStep, Pipeline, Step,
                       StepResult, approval_path)


def _todo(phase: int, what: str):
    def fn(ctx: Context) -> StepResult:
        raise NotImplementedStep(f"{what} - scheduled for Phase {phase}")
    return fn


def research(ctx: Context) -> StepResult:
    """Phase 1: create the episode research dossier that every later step must fill.

    Automated source collection (FRED/BLS/Census APIs + LLM synthesis) lands in
    Phase 3; the dossier format is fixed now so fact-checking can rely on it.
    """
    path = ctx.episode.p("research", "dossier.json")
    if not path.exists():
        dossier = {
            "topic": ctx.episode.topic,
            "created": date.today().isoformat(),
            "status": "draft",
            "claims": [],  # each: {id, text, kind: fact|forecast|opinion, value, unit,
                           #        sources: [{title, publisher, url, published, accessed}],
                           #        calculation, context, uncertainty, verified: bool}
            "sources": [],
            "notes": "",
        }
        path.write_text(json.dumps(dossier, indent=2))
    return StepResult([path], "dossier ready")


def publish(ctx: Context) -> StepResult:
    if not approval_path(ctx).exists():
        raise ApprovalRequired(
            f"Publishing requires human approval. Review the package, then create "
            f"{approval_path(ctx)} (python main.py approve --topic ...)")
    raise NotImplementedStep("YouTube upload - scheduled for Phase 7")


def build_pipeline() -> Pipeline:
    return Pipeline([
        Step("research", "Research topic & open dossier", research, (), 1),
        Step("sources", "Collect primary sources", _todo(3, "source collection"), ("research",), 3),
        Step("script", "Generate script", _todo(3, "script engine"), ("sources",), 3),
        Step("factcheck", "Fact-check script", _todo(3, "fact-checker"), ("script",), 3),
        Step("scenes", "Break script into scenes", _todo(3, "scene breakdown"), ("factcheck",), 3),
        Step("narration", "Create narration", _todo(4, "voiceover"), ("scenes",), 4),
        Step("assets", "Generate / reuse animation assets", _todo(5, "asset resolver"), ("scenes",), 5),
        Step("render", "Render scenes", _todo(5, "scene renderer"), ("narration", "assets"), 5),
        Step("graphics", "Render financial graphics", _todo(5, "Manim graphics"), ("scenes",), 5),
        Step("assemble", "Assemble video", _todo(6, "editor"), ("render", "graphics"), 6),
        Step("subtitles", "Create subtitles", _todo(6, "subtitles"), ("narration",), 6),
        Step("thumbnails", "Generate three thumbnails", _todo(7, "thumbnail engine"), ("scenes",), 7),
        Step("export", "Export final video + QC report", _todo(6, "export & QC"), ("assemble", "subtitles"), 6),
        Step("package", "Build publishing package", _todo(7, "publishing package"), ("export", "thumbnails"), 7),
        Step("publish", "Publish (approval-gated)", publish, ("package",), 7),
    ])
