"""Episode director: storyboard -> narrated, animated, assembled long-form video.

A storyboard is a Python module exposing EPISODE (metadata) and SCENES (list of
SceneSpec). Each scene's `build(T, dur)` receives its narration line timings
(T = [(start, end), ...] relative to the scene) and returns either a Blender
scene dict (scene_schema.Scene fields) or a Manim template spec. Because every
scene is cached by a content hash, editing one scene re-renders only that scene.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from audio import mixer, synth
from audio.tts import make_provider, synthesize_lines
from core.cache import AssetCache, file_hash, stable_hash
from core.config import Settings
from core.logging_setup import get_logger
from core.tools import ffmpeg_bin, media_duration, run
from editing.qc import qc_video, write_report
from editing.subtitles import write_srt
from graphics.render_manim import render_template

from .bake import bake_scene, foot_contacts
from .render import missing_frames, render_frames
from .scene_schema import Scene, validate_scene

log = get_logger("director")
LEAD, GAP, TAIL = 0.35, 0.32, 0.45


@dataclass
class SceneSpec:
    id: str
    section: str
    lines: list[str]
    kind: str                       # "blender" | "manim"
    build: Callable[[list, float], dict]
    min_dur: float = 0.0
    tail: float = TAIL
    sfx: list = field(default_factory=list)  # extra [{t, kind, gain, pan}] relative to scene


@dataclass
class Rendered:
    spec: SceneSpec
    start: float
    duration: float
    timings: list
    segment: Path
    sfx: list
    footsteps: list


def load_storyboard(path: Path):
    spec = importlib.util.spec_from_file_location("storyboard", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _code_version() -> str:
    here = Path(__file__).parent
    files = sorted((here / "blender").glob("*.py")) + [here / "motion.py", here / "bake.py"] + \
        sorted((here.parent / "characters" / "specs").glob("*.json"))
    return stable_hash(*[file_hash(p) for p in files])


def _normalize(src: Path, dst: Path, dur: float, fps: int, size=(1920, 1080), from_frames: bool = False) -> Path:
    """Re-encode any scene output to identical H.264 settings and an exact frame count."""
    n = int(round(dur * fps))
    inp = ["-framerate", str(fps), "-start_number", "1", "-i", str(src / "f_%04d.png")] if from_frames else ["-i", str(src)]
    run([ffmpeg_bin(), "-y", "-v", "error", *inp, "-vf",
         f"scale={size[0]}:{size[1]}:flags=lanczos,fps={fps},tpad=stop_mode=clone:stop_duration=5,format=yuv420p",
         "-frames:v", str(n), "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p",
         "-r", str(fps), str(dst)], timeout=3600)
    return dst


def _overlay(base: Path, mov: Path, start: float, end: float, dst: Path, fps: int) -> Path:
    run([ffmpeg_bin(), "-y", "-v", "error", "-i", str(base), "-itsoffset", f"{start:.3f}", "-i", str(mov),
         "-filter_complex", f"[1:v]format=rgba[o];[0:v][o]overlay=0:0:eof_action=pass:enable='between(t,{start:.3f},"
                            f"{end:.3f})',format=yuv420p[v]", "-map", "[v]", "-c:v", "libx264", "-crf", "14",
         "-preset", "medium", "-r", str(fps), str(dst)], timeout=3600)
    return dst


class Director:
    def __init__(self, settings: Settings, storyboard: Path, voice: str | None = None, workers: int = 2):
        self.s = settings
        self.sb = load_storyboard(storyboard)
        self.meta = self.sb.EPISODE
        self.out = settings.path("paths.output") / self.meta["slug"]
        for sub in ("audio", "scenes", "segments", "logs", "publish"):
            (self.out / sub).mkdir(parents=True, exist_ok=True)
        self.cache = AssetCache(settings.path("paths.cache"))
        self.fps = settings.get("video.fps")
        self.voice = voice
        self.workers = workers

    # ------------------------------------------------------------------ narration
    def narrate(self):
        lines = [ln for sc in self.sb.SCENES for ln in sc.lines]
        provider = make_provider(self.s, self.voice, len(lines))
        vl = synthesize_lines(lines, provider, self.out / "audio" / "lines", self.cache)
        self.provider = provider
        it = iter(vl)
        return {sc.id: [next(it) for _ in sc.lines] for sc in self.sb.SCENES}

    # ------------------------------------------------------------------ scenes
    def render_scene(self, sc: SceneSpec, voice_lines, start: float) -> Rendered:
        durs = [v.duration for v in voice_lines]
        T = mixer.layout_lines(durs, LEAD, GAP) if durs else []
        dur = round(max((T[-1][1] + sc.tail) if T else 0.0, sc.min_dur), 3)
        spec = sc.build(T, dur)
        seg = self.out / "segments" / f"{sc.id}.mp4"
        key = stable_hash("scene-v2", sc.id, sc.kind, spec, dur, _code_version() if sc.kind == "blender" else
                          file_hash(Path(__file__).parent.parent / "graphics" / "manim_templates.py"))
        stamp = seg.with_suffix(".key")
        sfx = [dict(e) for e in spec.pop("sfx", [])] + [dict(e) for e in sc.sfx] if isinstance(spec, dict) else []
        footsteps = []
        if sc.kind == "blender":
            scene_dict = {"scene_id": sc.id, "duration": dur, "fps": self.fps,
                          "narration": [{"text": t, "start": a, "end": b} for t, (a, b) in zip(sc.lines, T)], **spec}
            scene = Scene.model_validate(scene_dict)
            problems = validate_scene(scene)
            if problems:
                raise ValueError(f"scene {sc.id} invalid:\n  " + "\n  ".join(problems))
            (self.out / "scenes" / f"{sc.id}.json").write_text(scene.model_dump_json(indent=2))
            baked = bake_scene(scene)
            for c in baked["characters"]:
                footsteps += foot_contacts(c["channels"], self.fps)
            sfx += [s.model_dump() for s in scene.sfx]
            if not (seg.exists() and stamp.exists() and stamp.read_text() == key):
                frames = self.out / "frames" / sc.id
                job = {"fps": self.fps, "resolution": [self.s.get("video.width"), self.s.get("video.height")],
                       "frame_start": 1, "frame_end": baked["frames"], "samples": self.s.get("render.eevee_samples"),
                       "engine": self.s.get("render.blender_engine"), "output_dir": str(frames), **baked}
                fkey = stable_hash(job, _code_version())
                if (frames / ".key").exists() and (frames / ".key").read_text() != fkey:
                    shutil.rmtree(frames)
                frames.mkdir(parents=True, exist_ok=True)
                (frames / ".key").write_text(fkey)
                t0 = time.time()
                render_frames(job, self.out / "scenes" / f"{sc.id}_job", workers=self.workers,
                              use_xvfb=self.s.get("render.use_xvfb", True))
                miss = missing_frames(frames, 1, baked["frames"])
                if miss:
                    raise RuntimeError(f"scene {sc.id}: {len(miss)} frames missing")
                _normalize(frames, seg, dur, self.fps, from_frames=True)
                for g in scene.graphics:  # transparent Manim overlays on top of the animation
                    mov = render_template(g.scene, {**g.params, "duration": g.end - g.start, "transparent": True},
                                          self.out / "scenes" / f"{sc.id}_{g.id}.mov", self.fps)
                    tmp = seg.with_name(seg.stem + "_ov.mp4")
                    _overlay(seg, mov, g.start, g.end, tmp, self.fps)
                    tmp.replace(seg)
                stamp.write_text(key)
                log.info("scene %s rendered (%d frames) in %.0fs", sc.id, baked["frames"], time.time() - t0)
            else:
                log.info("scene %s up to date", sc.id)
        elif sc.kind == "manim":
            if not (seg.exists() and stamp.exists() and stamp.read_text() == key):
                params = {**spec["params"], "duration": dur}
                if "beats" in spec:
                    params["beats"] = spec["beats"]
                raw = render_template(spec["template"], params, self.out / "scenes" / f"{sc.id}_raw.mp4", self.fps)
                _normalize(raw, seg, dur, self.fps)
                stamp.write_text(key)
                log.info("scene %s (manim %s) rendered", sc.id, spec["template"])
        else:
            raise ValueError(f"unknown scene kind {sc.kind}")
        return Rendered(sc, start, dur, [(start + a, start + b) for a, b in T], seg,
                        [{**e, "t": start + e["t"]} for e in sfx], [start + t for t in footsteps])

    # ------------------------------------------------------------------ assembly
    def run(self, only: list[str] | None = None) -> Path:
        t_all = time.time()
        voice = self.narrate()
        rendered, t = [], 0.0
        for sc in self.sb.SCENES:
            if only and sc.id not in only:  # still advance the clock so timings stay consistent
                durs = [v.duration for v in voice[sc.id]]
                T = mixer.layout_lines(durs, LEAD, GAP) if durs else []
                t += round(max((T[-1][1] + sc.tail) if T else 0.0, sc.min_dur), 3)
                continue
            r = self.render_scene(sc, voice[sc.id], t)
            rendered.append(r)
            t += r.duration
        if only:
            return self.out
        total = round(t, 3)
        # video: concat normalized segments losslessly
        lst = self.out / "segments" / "concat.txt"
        lst.write_text("".join(f"file '{r.segment.name}'\n" for r in rendered))
        concat = self.out / "segments" / "_concat.mp4"
        run([ffmpeg_bin(), "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(concat)])
        # audio
        all_lines = [v for sc in self.sb.SCENES for v in voice[sc.id]]
        all_t = [tt for r in rendered for tt in r.timings]
        narr = mixer.narration_track([v.path for v in all_lines], all_t, total)
        sections = self._music_sections(rendered, total)
        music = synth.music_bed(sections, total)
        events = [e for r in rendered for e in r.sfx] + \
                 [{"t": tt, "kind": "footstep", "gain": 0.5, "pan": -0.15, "seed": k}
                  for k, tt in enumerate(x for r in rendered for x in r.footsteps)]
        events += [{"t": r.start, "kind": "whoosh", "gain": 0.4} for i, r in enumerate(rendered)
                   if i and r.spec.section != rendered[i - 1].spec.section]
        sfx = synth.sfx_track(events, total)
        raw = mixer.save_mix(mixer.mix(narr, music, sfx, music_gain_db=self.s.get("audio.music_gain_db"),
                                       duck_db=self.s.get("audio.music_duck_db"),
                                       sfx_gain_db=self.s.get("audio.sfx_gain_db")), self.out / "audio" / "mix_raw.wav")
        mixer.loudnorm(raw, self.out / "audio" / "mix.wav", self.s.get("audio.narration_lufs"))
        # final encode: grain + vignette + fades
        final = self.out / f"{self.meta['slug']}.mp4"
        v = self.s.get("video")
        run([ffmpeg_bin(), "-y", "-v", "error", "-i", str(concat), "-i", str(self.out / "audio" / "mix.wav"),
             "-filter_complex", f"[0:v]vignette=angle=PI/5.5,noise=alls=3:allf=t,fade=t=in:st=0:d=0.4,"
                                f"fade=t=out:st={total - 0.6:.3f}:d=0.6,format=yuv420p[v];"
                                f"[1:a]afade=t=out:st={total - 0.6:.3f}:d=0.6[a]",
             "-map", "[v]", "-map", "[a]", "-c:v", v["codec"], "-preset", v["preset"], "-crf", str(v["crf"]),
             "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(self.fps), "-g", str(self.fps * 2),
             "-c:a", "aac", "-b:a", v["audio_bitrate"], "-ar", "48000", "-ac", "2", "-movflags", "+faststart",
             "-t", f"{total:.3f}", str(final)], timeout=7200)
        srt = write_srt([{"text": ln, "start": a, "end": b} for ln, (a, b) in
                         zip([ln for sc in self.sb.SCENES for ln in sc.lines], all_t)],
                        self.out / f"{self.meta['slug']}.srt")
        chapters = self._chapters(rendered)
        (self.out / "publish" / "chapters.txt").write_text(chapters)
        extra = {"production voice": {"ok": not self.provider.draft, "severity": "warning",
                                      "detail": self.provider.name + (" - DRAFT voice, do not publish"
                                                                      if self.provider.draft else "")},
                 "runtime 8-10 min": {"ok": 480 <= total <= 600, "detail": f"{total / 60:.2f} min"}}
        report = qc_video(final, expect={"width": v["width"], "height": v["height"], "fps": self.fps,
                                         "duration": total}, srt=srt, extra=extra)
        report["sections"] = [{"section": r.spec.section, "scene": r.spec.id, "start": round(r.start, 2),
                               "duration": r.duration} for r in rendered]
        report["build_seconds"] = round(time.time() - t_all)
        write_report(report, self.out / "qc_report.json", self.out / "qc_report.md")
        log.info("episode %s: %.1f min, QC %s", self.meta["slug"], total / 60, "PASS" if report["passed"] else "FAIL")
        return final

    def _music_sections(self, rendered, total):
        moods = self.meta.get("music", {})
        out, cur, start = [], None, 0.0
        for r in rendered + [None]:
            sec = r.spec.section if r else None
            if sec != cur:
                if cur is not None:
                    m = moods.get(cur, {"chords": ["Cmaj7", "Fmaj7"], "mood": "hopeful"})
                    n = max(1, int((r.start if r else total) - start) // 6)
                    chords = (m["chords"] * 20)[:max(len(m["chords"]), n)]
                    out.append({"start": start, "end": (r.start if r else total) + (0.5 if not r else 0),
                                "chords": chords, "mood": m["mood"]})
                cur, start = sec, (r.start if r else total)
        return out

    def _chapters(self, rendered):
        names = self.meta.get("chapters", {})
        lines, seen = [], set()
        for r in rendered:
            if r.spec.section not in seen:
                seen.add(r.spec.section)
                m, s = divmod(int(r.start), 60)
                lines.append(f"{m}:{s:02d} {names.get(r.spec.section, r.spec.section.title())}")
        return "\n".join(lines) + "\n"
