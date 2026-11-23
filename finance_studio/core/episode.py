"""Episode workspace: one folder per episode under output/."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .progress import EpisodeState


def slugify(text: str, max_len: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].rstrip("-") or "untitled"


@dataclass
class Episode:
    topic: str
    root: Path

    @classmethod
    def create(cls, topic: str, output_dir: Path) -> "Episode":
        ep = cls(topic=topic, root=output_dir / slugify(topic))
        for sub in ep.SUBDIRS:
            (ep.root / sub).mkdir(parents=True, exist_ok=True)
        st = ep.state
        st.meta.setdefault("topic", topic)
        st.save()
        return ep

    SUBDIRS = ("research", "script", "scenes", "audio", "renders", "graphics",
               "edit", "thumbnails", "publish", "shorts", "logs")

    @property
    def state(self) -> EpisodeState:
        return EpisodeState(self.root / "state.json")

    def p(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)
