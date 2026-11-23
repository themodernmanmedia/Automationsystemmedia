"""The 14-step production pipeline with resumable, fingerprinted steps.

Each step is a function ``(ctx) -> StepResult``. A step that is not built yet
raises ``NotImplementedStep``; the pipeline records that honestly and stops,
rather than pretending to produce output. Publishing is a hard gate that
never runs without an explicit approval file written by a human.
"""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .cache import AssetCache, file_hash, stable_hash
from .config import Settings
from .episode import Episode
from .logging_setup import get_logger
from .progress import EpisodeState, Status

log = get_logger("pipeline")


class NotImplementedStep(Exception):
    """The step exists in the plan but is not built yet (see the phase noted)."""


class ApprovalRequired(Exception):
    """A human must act before this step can run."""


@dataclass
class StepResult:
    outputs: list[Path] = field(default_factory=list)
    message: str = ""


@dataclass
class Context:
    settings: Settings
    episode: Episode
    state: EpisodeState
    cache: AssetCache
    options: dict = field(default_factory=dict)


@dataclass
class Step:
    name: str
    title: str
    fn: Callable[[Context], StepResult]
    depends_on: tuple[str, ...] = ()
    phase: int = 1

    def fingerprint(self, ctx: Context) -> str:
        upstream = [ctx.state.record(d).output_digest for d in self.depends_on]
        return stable_hash(self.name, ctx.episode.topic, upstream, ctx.options.get(self.name, {}))


class Pipeline:
    def __init__(self, steps: list[Step]):
        names = [s.name for s in steps]
        if len(set(names)) != len(names):
            raise ValueError("duplicate step names")
        for s in steps:
            for d in s.depends_on:
                if d not in names or names.index(d) >= names.index(s.name):
                    raise ValueError(f"step {s.name} depends on {d}, which must come earlier")
        self.steps = steps

    def run(self, ctx: Context, *, only: list[str] | None = None, force: list[str] | None = None,
            stop_after: str | None = None) -> bool:
        force = set(force or [])
        for step in self.steps:
            if only and step.name not in only:
                continue
            fp = step.fingerprint(ctx)
            if step.name not in force and ctx.state.is_fresh(step.name, fp, ctx.episode.root):
                log.info("[skip] %-12s up to date", step.name)
                continue
            log.info("[run ] %-12s %s", step.name, step.title)
            ctx.state.start(step.name)
            t0 = time.time()
            try:
                result = step.fn(ctx)
            except NotImplementedStep as exc:
                ctx.state.finish(step.name, Status.NOT_IMPLEMENTED, message=str(exc))
                log.warning("[todo] %-12s not built yet: %s", step.name, exc)
                return False
            except ApprovalRequired as exc:
                ctx.state.finish(step.name, Status.BLOCKED, message=str(exc))
                log.warning("[wait] %-12s %s", step.name, exc)
                return False
            except Exception as exc:
                ctx.state.finish(step.name, Status.FAILED, message=f"{exc.__class__.__name__}: {exc}")
                log.error("[fail] %-12s %s\n%s", step.name, exc, traceback.format_exc())
                return False
            rel = [str(p.relative_to(ctx.episode.root)) if p.is_absolute() else str(p) for p in result.outputs]
            digest = stable_hash(fp, [file_hash(p) if p.is_file() else str(p) for p in
                                      (q if q.is_absolute() else ctx.episode.root / q for q in result.outputs)])
            ctx.state.finish(step.name, Status.DONE, fingerprint=fp, outputs=rel,
                             message=result.message, output_digest=digest)
            log.info("[done] %-12s %.1fs %s", step.name, time.time() - t0, result.message)
            if stop_after == step.name:
                break
        return True


def make_context(settings: Settings, topic: str, options: dict | None = None) -> Context:
    ep = Episode.create(topic, settings.path("paths.output"))
    return Context(settings=settings, episode=ep, state=ep.state,
                   cache=AssetCache(settings.path("paths.cache")), options=options or {})


def approval_path(ctx: Context) -> Path:
    return ctx.episode.p("publish", "APPROVED")
