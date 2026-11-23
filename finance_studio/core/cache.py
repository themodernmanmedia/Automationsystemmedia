"""Content-addressed asset cache.

A cache key is a hash of everything that determines an output (inputs, params,
code version). If the key exists, the expensive step (TTS call, Blender render)
is skipped. Changing any input changes the key, so stale reuse is impossible.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def stable_hash(*parts: Any) -> str:
    h = hashlib.sha256()
    for p in parts:
        if isinstance(p, Path):
            p = p.read_bytes() if p.is_file() else str(p)
        if isinstance(p, bytes):
            h.update(p)
        else:
            h.update(json.dumps(p, sort_keys=True, default=str).encode())
        h.update(b"\x00")
    return h.hexdigest()[:24]


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:24]


class AssetCache:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def _path(self, namespace: str, key: str, suffix: str) -> Path:
        return self.root / namespace / key[:2] / f"{key}{suffix}"

    def get(self, namespace: str, key: str, suffix: str) -> Path | None:
        p = self._path(namespace, key, suffix)
        return p if p.exists() and p.stat().st_size > 0 else None

    def put(self, namespace: str, key: str, src: Path) -> Path:
        dst = self._path(namespace, key, src.suffix)
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_suffix(dst.suffix + ".tmp")
        shutil.copyfile(src, tmp)
        tmp.replace(dst)  # atomic: never leave a half-written cache entry
        return dst
