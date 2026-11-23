"""Persistent per-episode pipeline state, enabling resumable runs.

Each step records status, timestamps, an input fingerprint and its outputs in
``output/<episode>/state.json``. On re-run, a step whose fingerprint is
unchanged and whose outputs still exist is skipped.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path


class Status(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"          # needs human action (approval, credential)
    NOT_IMPLEMENTED = "not_implemented"


@dataclass
class StepRecord:
    status: Status = Status.PENDING
    fingerprint: str | None = None      # hash of the step's inputs
    output_digest: str | None = None    # hash of the step's output content (feeds downstream)
    outputs: list[str] = field(default_factory=list)
    started_at: float | None = None
    finished_at: float | None = None
    message: str = ""
    attempts: int = 0


class EpisodeState:
    def __init__(self, path: Path):
        self.path = path
        self.steps: dict[str, StepRecord] = {}
        self.meta: dict = {}
        if path.exists():
            raw = json.loads(path.read_text())
            self.meta = raw.get("meta", {})
            for name, rec in raw.get("steps", {}).items():
                rec["status"] = Status(rec["status"])
                self.steps[name] = StepRecord(**rec)

    def record(self, name: str) -> StepRecord:
        return self.steps.setdefault(name, StepRecord())

    def is_fresh(self, name: str, fingerprint: str, base: Path) -> bool:
        rec = self.steps.get(name)
        if not rec or rec.status != Status.DONE or rec.fingerprint != fingerprint:
            return False
        return all((base / o).exists() for o in rec.outputs)

    def start(self, name: str) -> None:
        rec = self.record(name)
        rec.status, rec.started_at, rec.message = Status.RUNNING, time.time(), ""
        rec.attempts += 1
        self.save()

    def finish(self, name: str, status: Status, fingerprint: str | None = None,
               outputs: list[str] | None = None, message: str = "",
               output_digest: str | None = None) -> None:
        rec = self.record(name)
        if output_digest is not None:
            rec.output_digest = output_digest
        rec.status, rec.finished_at, rec.message = status, time.time(), message
        if fingerprint is not None:
            rec.fingerprint = fingerprint
        if outputs is not None:
            rec.outputs = outputs
        self.save()

    def invalidate(self, name: str) -> None:
        if name in self.steps:
            self.steps[name] = StepRecord()
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"meta": self.meta,
                "steps": {k: {**asdict(v), "status": v.status.value} for k, v in self.steps.items()}}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self.path)

    def summary(self) -> list[tuple[str, str, str]]:
        return [(k, v.status.value, v.message) for k, v in self.steps.items()]
