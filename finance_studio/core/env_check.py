"""`python main.py doctor` - inspect the machine and report what the studio can do."""
from __future__ import annotations

import importlib
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def _version(cmd: list[str], pattern: str) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(pattern, out.stdout + out.stderr)
    return m.group(1) if m else None


def _mem_gb() -> float | None:
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024 / 1024
    except OSError:
        pass
    try:
        import ctypes  # macOS / fallback
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3
    except (ValueError, OSError, AttributeError):
        return None


def run_checks() -> list[Check]:
    checks: list[Check] = []
    py_ok = sys.version_info >= (3, 11)
    checks.append(Check("Python", py_ok, platform.python_version() + ("" if py_ok else " (need >= 3.11)")))
    checks.append(Check("OS", True, f"{platform.system()} {platform.release()} {platform.machine()}", False))
    mem = _mem_gb()
    checks.append(Check("Memory", mem is None or mem >= 8, f"{mem:.1f} GB" if mem else "unknown", False))
    checks.append(Check("CPU cores", True, str(os.cpu_count()), False))
    disk = shutil.disk_usage(".")
    checks.append(Check("Free disk", disk.free > 10 * 1024**3, f"{disk.free / 1024**3:.1f} GB", False))

    bl = shutil.which(os.environ.get("FINSTUDIO_BLENDER_BIN") or "blender")
    blv = _version([bl, "--version"], r"Blender (\d+\.\d+(?:\.\d+)?)") if bl else None
    checks.append(Check("Blender", bool(blv) and tuple(map(int, blv.split(".")[:2])) >= (4, 0),
                        f"{blv} at {bl}" if blv else "not found (apt install blender / blender.org)"))
    for tool in ("ffmpeg", "ffprobe"):
        p = shutil.which(tool)
        v = _version([p, "-version"], r"version (\S+)") if p else None
        checks.append(Check(tool, bool(v), f"{v} at {p}" if v else "not found"))
    if platform.system() == "Linux" and not os.environ.get("DISPLAY"):
        checks.append(Check("xvfb-run (headless EEVEE)", bool(shutil.which("xvfb-run")),
                            shutil.which("xvfb-run") or "not found (apt install xvfb)", False))
    checks.append(Check("espeak-ng (draft voice)", bool(shutil.which("espeak-ng")),
                        shutil.which("espeak-ng") or "not found", False))

    for mod, req in (("yaml", True), ("pydantic", True), ("numpy", True), ("PIL", True),
                     ("requests", True), ("manim", True), ("pytest", False)):
        try:
            m = importlib.import_module(mod)
            checks.append(Check(f"py:{mod}", True, getattr(m, "__version__", "installed"), req))
        except Exception as exc:  # manim can fail on missing system libs, not just ImportError
            checks.append(Check(f"py:{mod}", False, f"import failed: {exc.__class__.__name__}: {exc}", req))

    for key, purpose in (("ELEVENLABS_API_KEY", "production narration"),
                         ("ANTHROPIC_API_KEY", "script generation"),
                         ("FRED_API_KEY", "economic data")):
        checks.append(Check(f"secret:{key}", bool(os.environ.get(key)),
                            f"set ({purpose})" if os.environ.get(key) else f"not set - needed for {purpose}", False))
    return checks


def format_report(checks: list[Check]) -> str:
    lines = ["Finance Studio environment report", "=" * 34]
    for c in checks:
        mark = "OK  " if c.ok else ("FAIL" if c.required else "WARN")
        lines.append(f"[{mark}] {c.name:<28} {c.detail}")
    fails = [c for c in checks if c.required and not c.ok]
    lines.append("")
    lines.append("Ready." if not fails else f"{len(fails)} required check(s) failing.")
    return "\n".join(lines)
