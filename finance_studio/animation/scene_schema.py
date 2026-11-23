"""Scene JSON schema + validation.

A scene is the unit of regeneration: each one renders independently, so a
single scene can be fixed and re-rendered without rebuilding the episode.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from audio.synth import CHORDS, SFX_KINDS

from .motion import EASES, EXPRESSIONS, POSES, SPEC_DIR

BACKGROUNDS = {"city_dusk", "solid"}
PROP_KINDS = {"paycheck", "badge", "price_tag", "puff"}
GRAPHIC_SCENES = {"waterfall"}


class NarrationLine(BaseModel):
    text: str
    start: float
    end: float
    audio: Optional[str] = None


class Action(BaseModel):
    type: Literal["walk", "run", "sit", "pose"]
    start: float
    end: float
    name: Optional[str] = None  # pose name for type=pose
    head: Optional[float] = None
    fade: Optional[float] = None


class ExpressionKey(BaseModel):
    at: float
    name: str


class LookKey(BaseModel):
    at: float
    dx: float = Field(ge=-1, le=1)
    dy: float = Field(ge=-1, le=1)


class CharacterInScene(BaseModel):
    id: str
    character: str
    start_x: float = 0.0
    end_x: Optional[float] = None  # if set, start_x is solved so the walk ends here
    facing: Literal[1, -1] = 1
    z: float = 0.0
    actions: list[Action] = []
    expressions: list[ExpressionKey] = []
    looks: list[LookKey] = []


class Attach(BaseModel):
    character: str
    joint: str
    offset: list[float] = [0.0, 0.0]
    rot: float = 0.0
    z: float = 0.004
    upright: Optional[float] = None  # keep the prop at this world angle (deg) whatever the hand does


class PropKey(BaseModel):
    t: float
    x: Optional[float] = None
    y: Optional[float] = None
    s: Optional[float] = None
    rot: Optional[float] = None
    ease: str = "smooth"


class Prop(BaseModel):
    id: str
    kind: str
    label: Optional[str] = None
    color: Optional[str] = None
    z: float = 0.6
    attach: Optional[Attach] = None
    keys: list[PropKey] = []
    follow: Optional[dict] = None  # puff: {"character","joint","t","duration","offset"}
    bob: float = 0.0               # gentle float amplitude


class CameraKey(BaseModel):
    t: float
    x: float
    y: float = 0.0
    width: float = 16.0
    ease: str = "in_out_cubic"


class Graphic(BaseModel):
    id: str
    scene: str
    start: float
    end: float
    params: dict = {}


class SoundEvent(BaseModel):
    t: float
    kind: str
    gain: float = 1.0
    pan: float = 0.0


class MusicSection(BaseModel):
    start: float
    end: float
    chords: list[str]
    mood: Literal["hopeful", "tension", "resolve"] = "hopeful"


class Transition(BaseModel):
    type: Literal["cut", "fade", "whoosh"] = "cut"
    duration: float = 0.0


class Scene(BaseModel):
    scene_id: str
    duration: float = Field(gt=0)
    fps: int = 30
    narration: list[NarrationLine] = []
    background: dict = {"kind": "solid"}
    ground_y: float = -3.2
    characters: list[CharacterInScene] = []
    props: list[Prop] = []
    camera: list[CameraKey]
    graphics: list[Graphic] = []
    sfx: list[SoundEvent] = []
    music: list[MusicSection] = []
    transition_in: Transition = Transition()
    transition_out: Transition = Transition()
    notes: str = ""

    @model_validator(mode="after")
    def _non_empty_camera(self):
        if not self.camera:
            raise ValueError("camera needs at least one key")
        return self


def validate_scene(scene: Scene, base_dir: Path | None = None) -> list[str]:
    """Return human-readable problems: missing assets, unknown names, timing errors."""
    errs: list[str] = []
    D = scene.duration

    def in_range(label, t, allow_end=True):
        if t < 0 or (t > D + 1e-6 if allow_end else t >= D):
            errs.append(f"{label}: time {t:.2f}s outside scene (0..{D:.2f}s)")

    prev_end = -1.0
    for i, ln in enumerate(scene.narration):
        if ln.end <= ln.start:
            errs.append(f"narration[{i}] ends before it starts")
        if ln.start < prev_end - 1e-3:
            errs.append(f"narration[{i}] overlaps the previous line")
        in_range(f"narration[{i}].end", ln.end)
        if ln.audio and base_dir and not (base_dir / ln.audio).exists():
            errs.append(f"narration[{i}] audio missing: {ln.audio}")
        prev_end = ln.end
    if scene.background.get("kind") not in BACKGROUNDS:
        errs.append(f"unknown background kind {scene.background.get('kind')!r}")
    ids = set()
    for c in scene.characters:
        ids.add(c.id)
        if not (SPEC_DIR / f"{c.character}.json").exists():
            errs.append(f"character {c.id}: no spec for '{c.character}'")
        for a in c.actions:
            if a.end <= a.start:
                errs.append(f"character {c.id}: action {a.type} ends before it starts")
            in_range(f"character {c.id} action {a.type}", a.end)
            if a.type == "pose" and a.name not in POSES:
                errs.append(f"character {c.id}: unknown pose {a.name!r}")
        moves = sorted([a for a in c.actions if a.type in ("walk", "run")], key=lambda a: a.start)
        for a, b in zip(moves, moves[1:]):
            if b.start < a.end:
                errs.append(f"character {c.id}: overlapping locomotion at {b.start:.2f}s")
        for e in c.expressions:
            if e.name not in EXPRESSIONS:
                errs.append(f"character {c.id}: unknown expression {e.name!r}")
            in_range(f"character {c.id} expression", e.at)
    for p in scene.props:
        if p.kind not in PROP_KINDS:
            errs.append(f"prop {p.id}: unknown kind {p.kind!r}")
        if p.attach and p.attach.character not in ids:
            errs.append(f"prop {p.id}: attached to unknown character {p.attach.character!r}")
        if p.kind in ("badge", "price_tag") and not p.label:
            errs.append(f"prop {p.id}: {p.kind} needs a label")
        for k in p.keys:
            in_range(f"prop {p.id} key", k.t)
            if k.ease not in EASES:
                errs.append(f"prop {p.id}: unknown ease {k.ease!r}")
    for k in scene.camera:
        in_range("camera key", k.t)
        if k.width <= 0:
            errs.append("camera width must be positive")
    for g in scene.graphics:
        if g.scene not in GRAPHIC_SCENES:
            errs.append(f"graphic {g.id}: unknown graphic scene {g.scene!r}")
        if g.end <= g.start:
            errs.append(f"graphic {g.id}: ends before it starts")
        in_range(f"graphic {g.id}", g.end)
    for s in scene.sfx:
        if s.kind not in SFX_KINDS:
            errs.append(f"sfx at {s.t:.2f}s: unknown kind {s.kind!r}")
        in_range(f"sfx {s.kind}", s.t, allow_end=False)
    for m in scene.music:
        for ch in m.chords:
            if ch not in CHORDS:
                errs.append(f"music: unknown chord {ch!r}")
    return errs
