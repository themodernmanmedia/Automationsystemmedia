"""Frame rendering, audio assembly and encoding (cairo -> ffmpeg)."""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import shutil
import subprocess
import time
from pathlib import Path

import cairo
import numpy as np
import soundfile as sf

from . import audio as A
from .config import FPS, H, OUT_DIR, SAMPLE_RATE, W
from .gfx import vignette
from .overlays import draw_captions, draw_day_badge, draw_transition_in
from .timeline import Episode, Frame, locate, resolve_time

_EP: Episode | None = None


# --------------------------------------------------------------------------
# Frames
# --------------------------------------------------------------------------


def day_at(ep: Episode, gt: float):
    day, changed = None, 0.0
    for sh in ep.shots:
        if sh.start > gt:
            break
        if sh.day is not None:
            if sh.day != day:
                changed = sh.start
            day = sh.day if sh.day > 0 else None
    return day, gt - changed


def draw_frame(ctx: cairo.Context, ep: Episode, gt: float):
    idx, sh, t = locate(ep, gt)
    f = Frame(ctx, ep, sh, t, gt)

    def scene():
        ctx.save()
        sh.draw(f)
        ctx.restore()

    draw_transition_in(ctx, sh.transition, t, scene)
    vignette(ctx, W, H, 0.22)
    day, since = day_at(ep, gt)
    if day and getattr(sh, "badge", True) and not sh.name.startswith(("day_card", "title", "end")):
        if ep.hud:
            ep.hud(ctx, ep, gt, day, since)
        else:
            draw_day_badge(ctx, day, since)
    draw_captions(ctx, ep, sh, t)


def render_still(ep: Episode, gt: float, path: Path, scale=1.0):
    w, h = int(W * scale), int(H * scale)
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
    ctx = cairo.Context(surf)
    ctx.scale(scale, scale)
    draw_frame(ctx, ep, gt)
    surf.write_to_png(str(path))


def _worker(args):
    seg_path, f0, f1, scale, crf = args
    ep = _EP
    w, h = int(W * scale) // 2 * 2, int(H * scale) // 2 * 2
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
    ctx = cairo.Context(surf)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra",
        "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
        "-g", str(FPS * 2), str(seg_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fi in range(f0, f1):
        ctx.save()
        ctx.set_source_rgb(0, 0, 0)
        ctx.paint()
        ctx.scale(scale, scale)
        draw_frame(ctx, ep, fi / FPS)
        ctx.restore()
        surf.flush()
        proc.stdin.write(surf.get_data())
    proc.stdin.close()
    proc.wait()
    return seg_path, f1 - f0


def render_video(ep: Episode, out: Path, scale=1.0, workers=None, crf=18, t0=0.0, t1=None, log=print):
    global _EP
    _EP = ep
    t1 = ep.total if t1 is None else min(t1, ep.total)
    f0, f1 = int(t0 * FPS), int(t1 * FPS)
    workers = workers or max(1, os.cpu_count() or 1)
    tmp = out.parent / f".{out.stem}_segments"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    n = f1 - f0
    per = int(np.ceil(n / (workers * 3)))
    jobs = []
    for k, a in enumerate(range(f0, f1, per)):
        jobs.append((tmp / f"seg{k:04d}.mp4", a, min(f1, a + per), scale, crf))
    start = time.time()
    done = 0
    ctx_mp = mp.get_context("fork")
    with ctx_mp.Pool(workers) as pool:
        for seg, cnt in pool.imap_unordered(_worker, jobs):
            done += cnt
            el = time.time() - start
            log(f"  frames {done}/{n}  ({done / max(el, 1e-3):.1f} fps, eta {el / done * (n - done):.0f}s)")
    listing = tmp / "list.txt"
    listing.write_text("".join(f"file '{j[0].name}'\n" for j in jobs))
    silent = tmp / "video.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", str(silent)], check=True)
    return silent, tmp


# --------------------------------------------------------------------------
# Audio
# --------------------------------------------------------------------------


def build_audio(ep: Episode, path: Path, log=print):
    total = ep.total
    n = int(total * SAMPLE_RATE) + SAMPLE_RATE
    voice = np.zeros(n, dtype=np.float32)
    fx = np.zeros((2, n), dtype=np.float32)
    cues = []
    cur_style, cur_start = None, 0.0
    for sh in ep.shots:
        for ln, (a, b), au in zip(sh.lines, sh.line_times, sh.line_audio):
            A.place(voice, au, sh.start + a)
        for item in sh.sfx:
            spec, name = item[0], item[1]
            gain = item[2] if len(item) > 2 else 0.8
            tt = sh.start + resolve_time(sh, spec)
            sig = A.sfx(name)
            pan = 0.0
            A.place(fx[0], sig * (1 - pan) * gain, tt)
            A.place(fx[1], sig * (1 + pan) * gain, tt)
        if sh.transition in ("whip",):
            A.place(fx[0], A.sfx("whoosh") * 0.45, sh.start - 0.15)
            A.place(fx[1], A.sfx("whoosh") * 0.45, sh.start - 0.15)
        if sh.music:
            if cur_style is not None:
                cues.append((cur_start, sh.start, cur_style))
            cur_style = None if sh.music == "off" else sh.music
            cur_start = sh.start
    if cur_style:
        cues.append((cur_start, total, cur_style))
    log(f"  music cues: {[(round(a, 1), round(b, 1), s) for a, b, s in cues]}")
    music = A.build_music(cues, total + 1)
    mix = A.master(voice[: n], music, fx)
    mix = mix[:, : int(total * SAMPLE_RATE)]
    sf.write(str(path), mix.T, SAMPLE_RATE, subtype="PCM_16")
    return path


def mux(video: Path, audio_path: Path, out: Path, t0=0.0, t1=None):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-ss", f"{t0:.3f}"]
    if t1 is not None:
        cmd += ["-to", f"{t1:.3f}"]
    cmd += ["-i", str(audio_path), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)


# --------------------------------------------------------------------------
# Metadata
# --------------------------------------------------------------------------


def chapters(ep: Episode) -> list[tuple[str, str]]:
    out = []
    for sh in ep.shots:
        if sh.chapter:
            s = int(sh.start)
            out.append((f"{s // 60}:{s % 60:02d}", sh.chapter))
    if out and out[0][0] != "0:00":
        out.insert(0, ("0:00", "Intro"))
    return out


def write_metadata(ep: Episode, folder: Path):
    m = dict(ep.meta)
    ch = chapters(ep)
    desc = m.get("description", "").strip() + "\n\n"
    desc += "CHAPTERS\n" + "\n".join(f"{a} {b}" for a, b in ch) + "\n\n"
    if m.get("sources"):
        desc += "SOURCES\n" + "\n".join(f"• {s}" for s in m["sources"]) + "\n\n"
    desc += m.get("footer", "")
    (folder / "description.txt").write_text(desc)
    script = []
    for sh in ep.shots:
        s = int(sh.start)
        for ln, (a, _) in zip(sh.lines, sh.line_times):
            tt = int(sh.start + a)
            script.append(f"[{tt // 60}:{tt % 60:02d}] {ln.who.upper()}: {ln.text}")
    (folder / "script.txt").write_text("\n".join(script) + "\n")
    srt = []
    k = 1
    for sh in ep.shots:
        for ln, (a, b) in zip(sh.lines, sh.line_times):
            def ts(x):
                ms = int(round(x * 1000))
                return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
            srt.append(f"{k}\n{ts(sh.start + a)} --> {ts(sh.start + b)}\n{ln.text}\n")
            k += 1
    (folder / "captions.srt").write_text("\n".join(srt))
    info = {
        "title": m.get("title", ep.title),
        "alt_titles": m.get("alt_titles", []),
        "tags": m.get("tags", []),
        "duration_seconds": round(ep.total, 2),
        "chapters": ch,
    }
    (folder / "metadata.json").write_text(json.dumps(info, indent=2))
