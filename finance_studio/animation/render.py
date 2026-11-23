"""Host-side Blender driver: writes render jobs and runs Blender headless."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from core.logging_setup import get_logger
from core.tools import ToolFailed, blender_bin

log = get_logger("render")
BL_DIR = Path(__file__).resolve().parent / "blender"
ROOT = Path(__file__).resolve().parent.parent
FONTS = {
    "regular": str(ROOT / "assets/fonts/Inter-Regular.otf"),
    "bold": str(ROOT / "assets/fonts/Inter-Bold.otf"),
    "black": str(ROOT / "assets/fonts/Inter-Black.otf"),
}


def blender_cmd(job_path: Path, use_xvfb: bool) -> list[str]:
    cmd = [blender_bin(), "-b", "--factory-startup", "-noaudio", "-P", str(BL_DIR / "bl_render.py"), "--",
           str(job_path)]
    if use_xvfb and shutil.which("xvfb-run"):
        cmd = ["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24"] + cmd
    return cmd


def run_job(job: dict, job_path: Path, use_xvfb: bool = True, timeout: float = 6 * 3600) -> None:
    job.setdefault("fonts", FONTS)
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text(json.dumps(job))
    log_path = job_path.with_suffix(".log")
    t0 = time.time()
    with log_path.open("w") as lf:
        proc = subprocess.run(blender_cmd(job_path, use_xvfb), stdout=lf, stderr=subprocess.STDOUT,
                              timeout=timeout)
    text = log_path.read_text(errors="replace")
    if proc.returncode != 0 or "FINSTUDIO_RENDER_OK" not in text:
        tail = "\n".join(l for l in text.splitlines()[-40:])
        raise ToolFailed(f"Blender render failed (exit {proc.returncode}); log {log_path}:\n{tail}")
    log.info("blender job %s finished in %.1fs", job_path.name, time.time() - t0)


def render_frames(job: dict, work_dir: Path, workers: int = 1, use_xvfb: bool = True) -> Path:
    """Render all frames of `job` into job['output_dir'], split across `workers` processes.

    Frames already on disk are skipped by Blender itself, so this is resumable.
    """
    out = Path(job["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    # remove zero-byte placeholders left by a crashed worker so they re-render
    for f in out.glob("f_*.png"):
        if f.stat().st_size == 0:
            f.unlink()
    if workers <= 1:
        run_job(job, work_dir / "job.json", use_xvfb)
        return out
    # every worker builds the full scene but all share one output dir; Blender's
    # placeholder files make them claim frames without duplicating work
    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(run_job, {**job, "threads": max(1, job.get("threads", 0))}, work_dir / f"job_{w}.json",
                          use_xvfb) for w in range(workers)]
        for f in futs:
            f.result()
    return out


def missing_frames(out_dir: Path, start: int, end: int) -> list[int]:
    return [f for f in range(start, end + 1)
            if not (out_dir / f"f_{f:04d}.png").exists() or (out_dir / f"f_{f:04d}.png").stat().st_size == 0]
