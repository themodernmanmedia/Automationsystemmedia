"""The first required test: a ~15-second animated documentary scene, end to end.

narration -> timing -> scene JSON (validated) -> baked animation -> Blender
frames -> Manim graphic -> music/SFX mix -> FFmpeg export -> SRT -> QC report.

Every beat is anchored to the *measured* narration timings, so swapping the
voice (draft espeak -> ElevenLabs) re-syncs the animation automatically.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from audio import mixer, synth
from audio.tts import make_provider, synthesize_lines
from core.cache import AssetCache, file_hash, stable_hash
from core.config import Settings
from core.logging_setup import get_logger
from editing.assemble import assemble
from editing.qc import qc_video, write_report
from editing.subtitles import write_srt
from graphics.charts import render_waterfall

from .bake import bake_scene, foot_contacts
from .render import missing_frames, render_frames
from .scene_schema import Scene, validate_scene

log = get_logger("prototype")

LINES = [
    "Meet Maya.",
    "Last year, she got a five percent raise.",
    "So why does it feel like she's falling behind?",
    "Her rent went up.",
    "Groceries went up.",
    "And by the end of the month, that raise has quietly disappeared.",
]
GAPS = [0.35, 0.5, 0.3, 0.25, 0.35]
LEAD, TAIL = 0.6, 0.75
CHART = {
    "title": "WHERE MAYA'S RAISE WENT",
    "caption": "Illustrative example - hypothetical numbers, not real data",
    "panel": [3.35, 0.45, 6.4, 5.5], "step_time": 0.5, "hold": 1.0,
    "bars": [{"label": "Raise", "value": 200, "text": "+$200"},
             {"label": "Rent", "value": -120, "text": "-$120"},
             {"label": "Groceries", "value": -80, "text": "-$80"},
             {"label": "Left over", "value": 0, "text": "$0", "kind": "total"}],
}


def build_scene(L: list[tuple[float, float]], duration: float, voice_files: list[str]) -> Scene:
    (s0, e0), (s1, e1), (s2, e2), (s3, e3), (s4, e4), (s5, e5) = L
    walk_end = s1 + 0.9
    mx = -4.3                       # where Maya stops
    poof_t = e5 - 0.55              # "...disappeared"
    tag_y = 1.2
    sc = {
        "scene_id": "test_015_maya_raise",
        "duration": duration,
        "narration": [{"text": t, "start": a, "end": b, "audio": f} for t, (a, b), f in zip(LINES, L, voice_files)],
        "background": {"kind": "city_dusk", "seed": 7, "furniture_offset": 3.0},
        "ground_y": -3.2,
        "characters": [{
            "id": "maya", "character": "maya", "end_x": mx, "facing": 1,
            "actions": [
                {"type": "walk", "start": 0.0, "end": walk_end},
                {"type": "pose", "name": "hold_up", "start": walk_end - 0.1, "end": s2 + 0.35},
                {"type": "pose", "name": "head_scratch", "start": s2 + 0.2, "end": s3 + 0.1, "fade": 0.35},
                {"type": "pose", "name": "worried_hands", "start": s3 + 0.15, "end": s5 + 0.3},
                {"type": "pose", "name": "hold_up", "start": s5 + 0.2, "end": poof_t + 0.1, "fade": 0.35},
                {"type": "pose", "name": "hands_up", "start": poof_t + 0.05, "end": duration, "fade": 0.2},
            ],
            "expressions": [
                {"at": 0.0, "name": "happy"}, {"at": s1 + 0.9, "name": "excited"},
                {"at": s2 + 0.15, "name": "confused"}, {"at": s3 + 0.1, "name": "worried"},
                {"at": s5 + 0.3, "name": "neutral"}, {"at": poof_t, "name": "surprised"},
                {"at": min(poof_t + 1.0, duration - 0.3), "name": "sad"},
            ],
            "looks": [
                {"at": 0.0, "dx": 0.25, "dy": 0.0}, {"at": walk_end, "dx": 0.5, "dy": -0.1},
                {"at": s2 + 0.2, "dx": 0.1, "dy": 0.45}, {"at": s3 + 0.2, "dx": 0.6, "dy": 0.5},
                {"at": s5 + 0.3, "dx": 0.55, "dy": -0.2}, {"at": poof_t + 0.1, "dx": 0.3, "dy": 0.1},
            ],
        }],
        "props": [
            {"id": "paycheck", "kind": "paycheck",
             "attach": {"character": "maya", "joint": "hand_f", "offset": [0.0, -0.16], "z": 0.004, "upright": 6.0},
             "keys": [{"t": 0, "s": 1.0}, {"t": poof_t, "s": 1.0}, {"t": poof_t + 0.18, "s": 0.0, "ease": "out_cubic"}]},
            {"id": "poof", "kind": "puff",
             "follow": {"character": "maya", "joint": "hand_f", "t": poof_t, "duration": 0.7, "offset": [0.4, -0.15],
                        "count": 10}, "z": 0.7},
            {"id": "raise_badge", "kind": "badge", "label": "+5% RAISE", "z": 0.8,
             "keys": [{"t": 0, "x": mx + 2.3, "y": 1.75, "s": 0.0}, {"t": s1 + 1.15, "s": 0.0},
                      {"t": s1 + 1.5, "s": 1.2, "ease": "out_back"}, {"t": s2 + 0.25, "s": 1.2},
                      {"t": s2 + 0.5, "s": 0.0, "ease": "smooth"}]},
            {"id": "tag_rent", "kind": "price_tag", "label": "RENT", "color": "#E0524A", "z": 0.8, "bob": 0.06,
             "keys": [{"t": 0, "x": mx + 3.5, "y": tag_y + 0.35, "s": 0.0, "rot": 8},
                      {"t": s3 + 0.05, "s": 0.0, "y": tag_y + 0.35},
                      {"t": s3 + 0.4, "s": 1.0, "ease": "out_back"},
                      {"t": s5 + 0.1, "s": 1.0, "y": tag_y + 0.95, "ease": "linear"},
                      {"t": s5 + 0.4, "s": 0.0, "y": tag_y + 1.05}]},
            {"id": "tag_groceries", "kind": "price_tag", "label": "GROCERIES", "color": "#E3A72F", "z": 0.85,
             "bob": 0.06,
             "keys": [{"t": 0, "x": mx + 4.4, "y": tag_y - 0.85, "s": 0.0, "rot": -6},
                      {"t": s4 + 0.05, "s": 0.0, "y": tag_y - 0.85},
                      {"t": s4 + 0.4, "s": 1.0, "ease": "out_back"},
                      {"t": s5 + 0.15, "s": 1.0, "y": tag_y - 0.35, "ease": "linear"},
                      {"t": s5 + 0.45, "s": 0.0, "y": tag_y - 0.25}]},
        ],
        "camera": [
            {"t": 0.0, "x": -8.2, "y": 0.2, "width": 16.0},
            {"t": walk_end + 0.2, "x": -3.2, "y": 0.2, "width": 16.0},
            {"t": s2 + 0.1, "x": -3.0, "y": 0.3, "width": 15.2},
            {"t": e2, "x": -2.3, "y": 0.4, "width": 13.2},
            {"t": s5, "x": -2.0, "y": 0.45, "width": 12.8, "ease": "linear"},
            {"t": s5 + 0.7, "x": -0.6, "y": 0.2, "width": 16.0},
            {"t": duration, "x": -0.45, "y": 0.2, "width": 15.6, "ease": "linear"},
        ],
        "graphics": [{"id": "waterfall", "scene": "waterfall", "start": s5 + 0.55, "end": duration, "params": CHART}],
        "sfx": [
            {"t": s1 + 1.2, "kind": "coin", "gain": 0.9},
            {"t": s3 + 0.08, "kind": "pop", "gain": 0.9, "pan": 0.4},
            {"t": s4 + 0.08, "kind": "pop", "gain": 0.9, "pan": 0.5},
            {"t": s5 + 0.3, "kind": "whoosh", "gain": 0.6},
            {"t": poof_t, "kind": "poof", "gain": 1.0},
            {"t": poof_t + 0.25, "kind": "downer", "gain": 0.7},
        ] + [{"t": s5 + 0.55 + 0.45 + 0.5 * k, "kind": "blip", "gain": 0.45, "pan": 0.5} for k in range(4)],
        "music": [{"start": 0.0, "end": s2, "chords": ["Cmaj7", "Fmaj7"], "mood": "hopeful"},
                  {"start": s2, "end": duration + 0.5, "chords": ["Am", "F", "Dm7", "Esus4"], "mood": "tension"}],
        "notes": "First required test. Narrator-led; Maya does not lip-sync because she is not speaking.",
    }
    return Scene.model_validate(sc)


def run_prototype(settings: Settings, voice: str | None = None, workers: int = 1) -> Path:
    t_start = time.time()
    out = settings.path("paths.output") / "test_scene"
    for sub in ("audio", "frames", "graphics", "scene", "logs"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    cache = AssetCache(settings.path("paths.cache"))
    fps = settings.get("video.fps")

    # 1. narration + timing
    provider = make_provider(settings, voice, len(LINES))
    vl = synthesize_lines(LINES, provider, out / "audio" / "lines", cache)
    timings = mixer.layout_lines([v.duration for v in vl], LEAD, GAPS)
    duration = round(timings[-1][1] + TAIL, 3)
    log.info("narration via %s (%s): %.2fs of speech, scene %.2fs", provider.name,
             "DRAFT" if provider.draft else "production", sum(v.duration for v in vl), duration)

    # 2. scene JSON + validation
    scene = build_scene(timings, duration, [str(v.path.relative_to(out)) for v in vl])
    problems = validate_scene(scene, out)
    (out / "scene" / "scene.json").write_text(scene.model_dump_json(indent=2))
    if problems:
        raise ValueError("scene validation failed:\n  " + "\n  ".join(problems))

    # 3. bake + Blender render (frames dir keyed by content hash -> unchanged scenes never re-render)
    baked = bake_scene(scene)
    job = {"fps": fps, "resolution": [settings.get("video.width"), settings.get("video.height")],
           "frame_start": 1, "frame_end": baked["frames"], "samples": settings.get("render.eevee_samples", 16),
           "engine": settings.get("render.blender_engine", "BLENDER_EEVEE"), **baked}
    rkey = stable_hash("render-v1", job, _code_version())
    frames = out / "frames" / rkey
    job["output_dir"] = str(frames)
    t0 = time.time()
    render_frames(job, out / "scene", workers=workers, use_xvfb=settings.get("render.use_xvfb", True))
    miss = missing_frames(frames, 1, baked["frames"])
    if miss:
        raise RuntimeError(f"{len(miss)} frames missing after render, e.g. {miss[:5]}")
    log.info("rendered %d frames in %.0fs", baked["frames"], time.time() - t0)

    # 4. graphics
    overlays = []
    for g in scene.graphics:
        gkey = stable_hash("chart-v1", g.params)
        mov = cache.get("charts", gkey, ".mov")
        if not mov:
            tmp = render_waterfall(g.params, out / "graphics" / f"{g.id}.mov", fps=fps)
            mov = cache.put("charts", gkey, tmp)
        overlays.append({"path": mov, "start": g.start, "end": g.end - 0.05, "fade": 0.3})

    # 5. audio: narration + music + sfx, ducked and loudness-normalized
    contacts = foot_contacts(baked["characters"][0]["channels"], fps)
    sfx_events = [s.model_dump() for s in scene.sfx] + [
        {"t": t, "kind": "footstep", "gain": 0.55, "pan": -0.2, "seed": 100 + k} for k, t in enumerate(contacts)]
    narr = mixer.narration_track([v.path for v in vl], timings, duration)
    music = synth.music_bed([m.model_dump() for m in scene.music], duration)
    sfx = synth.sfx_track(sfx_events, duration)
    raw_mix = mixer.save_mix(mixer.mix(narr, music, sfx, music_gain_db=settings.get("audio.music_gain_db"),
                                       duck_db=settings.get("audio.music_duck_db"),
                                       sfx_gain_db=settings.get("audio.sfx_gain_db")), out / "audio" / "mix_raw.wav")
    loud = mixer.loudnorm(raw_mix, out / "audio" / "mix.wav", settings.get("audio.narration_lufs"))
    log.info("mix loudness %s", loud)

    # 6. export + subtitles + QC
    final = out / "test_scene_15s.mp4"
    assemble(frames, fps, out / "audio" / "mix.wav", final, overlays=overlays, duration=duration,
             video_cfg=settings.get("video"), log_file=out / "logs" / "ffmpeg_assemble.log")
    srt = write_srt([{"text": n.text, "start": n.start, "end": n.end} for n in scene.narration],
                    out / "test_scene_15s.srt")
    extra = {"production voice": {"ok": not provider.draft, "severity": "warning",
                                  "detail": f"{provider.name}" + (" - DRAFT voice, do not publish" if provider.draft
                                                                   else "")},
             "scene validation": {"ok": not problems, "detail": "no missing assets or timing errors"}}
    report = qc_video(final, expect={"width": settings.get("video.width"), "height": settings.get("video.height"),
                                     "fps": fps, "duration": duration}, srt=srt, extra=extra)
    report["render_seconds"] = round(time.time() - t_start, 1)
    report["narration_provider"] = provider.name
    write_report(report, out / "qc_report.json", out / "qc_report.md")
    _contact_sheet(final, out / "contact_sheet.png", duration)
    log.info("QC %s - %s", "PASS" if report["passed"] else "FAIL", out / "qc_report.md")
    return final


def _contact_sheet(video: Path, png: Path, duration: float, n: int = 8) -> None:
    from core.tools import ffmpeg_bin, run
    step = duration / n
    run([ffmpeg_bin(), "-y", "-v", "error", "-i", str(video), "-vf",
         f"fps=1/{step:.3f},scale=480:-1,tile=4x2:padding=6:color=white", "-frames:v", "1", str(png)])


def _code_version() -> str:
    """Hash of the Blender-side code so rig/environment changes invalidate cached frames."""
    bl = Path(__file__).parent / "blender"
    return stable_hash(*[file_hash(p) for p in sorted(bl.glob("*.py"))],
                       file_hash(Path(__file__).parent.parent / "characters/specs/maya.json"))
