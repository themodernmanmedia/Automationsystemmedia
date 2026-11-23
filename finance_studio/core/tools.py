"""Locating and running external tools (Blender, FFmpeg) safely."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .logging_setup import get_logger

log = get_logger("tools")


class ToolMissing(RuntimeError):
    pass


class ToolFailed(RuntimeError):
    pass


def find_tool(name: str, env_override: str | None = None) -> str:
    if env_override and os.environ.get(env_override):
        path = os.environ[env_override]
        if Path(path).exists():
            return path
        raise ToolMissing(f"{env_override}={path} does not exist")
    found = shutil.which(name)
    if not found:
        raise ToolMissing(f"'{name}' not found on PATH")
    return found


def blender_bin() -> str:
    return find_tool("blender", "FINSTUDIO_BLENDER_BIN")


def ffmpeg_bin() -> str:
    return find_tool("ffmpeg", "FINSTUDIO_FFMPEG_BIN")


def ffprobe_bin() -> str:
    return find_tool("ffprobe")


def run(cmd: list[str], *, cwd: Path | None = None, timeout: float | None = None,
        log_file: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a command (no shell), capture output, raise ToolFailed with the tail on error."""
    log.debug("run: %s", " ".join(map(str, cmd)))
    proc = subprocess.run([str(c) for c in cmd], cwd=cwd, timeout=timeout, capture_output=True,
                          text=True, env={**os.environ, **(env or {})})
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text(f"$ {' '.join(map(str, cmd))}\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}")
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or proc.stdout).strip().splitlines()[-25:])
        raise ToolFailed(f"{Path(str(cmd[0])).name} exited {proc.returncode}:\n{tail}")
    return proc


def media_duration(path: Path) -> float:
    out = run([ffprobe_bin(), "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)]).stdout.strip()
    return float(out)


def probe_streams(path: Path) -> list[dict]:
    import json
    out = run([ffprobe_bin(), "-v", "error", "-show_streams", "-of", "json", str(path)]).stdout
    return json.loads(out).get("streams", [])
