"""Automated quality control for exported videos. Every check is measured, never assumed."""
from __future__ import annotations

import json
import re
from pathlib import Path

from audio.mixer import measure_loudness
from core.tools import ffmpeg_bin, media_duration, probe_streams, run


def _detect(path: Path, vf: str, pattern: str) -> list[str]:
    out = run([ffmpeg_bin(), "-hide_banner", "-i", str(path), "-vf", vf, "-an", "-f", "null", "-"]).stderr
    return re.findall(pattern, out)


def qc_video(path: Path, *, expect: dict, srt: Path | None = None, extra: dict | None = None) -> dict:
    checks = []

    def check(name, ok, detail, severity="error"):
        checks.append({"check": name, "ok": bool(ok), "detail": detail, "severity": severity})

    streams = probe_streams(path)
    v = next((s for s in streams if s["codec_type"] == "video"), None)
    a = next((s for s in streams if s["codec_type"] == "audio"), None)
    check("video stream present", v is not None, "h264 expected")
    check("audio stream present", a is not None, "aac expected")
    if v:
        num, den = map(int, v["r_frame_rate"].split("/"))
        check("resolution", (v["width"], v["height"]) == (expect["width"], expect["height"]),
              f"{v['width']}x{v['height']}")
        check("frame rate", abs(num / den - expect["fps"]) < 0.01, f"{num / den:.3f} fps")
        check("video codec", v["codec_name"] == "h264", v["codec_name"])
        check("pixel format", v.get("pix_fmt") == "yuv420p", v.get("pix_fmt"))
        dar = v["width"] / v["height"]
        check("aspect 16:9", abs(dar - 16 / 9) < 0.01, f"{dar:.4f}")
    if a:
        check("audio codec", a["codec_name"] == "aac", a["codec_name"])
        check("audio sample rate", int(a["sample_rate"]) == 48000, a["sample_rate"])
    dur = media_duration(path)
    if expect.get("duration"):
        check("duration", abs(dur - expect["duration"]) < 0.25, f"{dur:.2f}s (expected {expect['duration']:.2f}s)")
    if v and a:
        vd, ad = float(v.get("duration", dur)), float(a.get("duration", dur))
        check("A/V duration match", abs(vd - ad) < 0.1, f"video {vd:.2f}s / audio {ad:.2f}s")
    loud = measure_loudness(path)
    check("integrated loudness", -18.0 <= loud["integrated_lufs"] <= -13.0, f"{loud['integrated_lufs']:.1f} LUFS")
    check("true peak", loud["true_peak_db"] <= -1.0, f"{loud['true_peak_db']:.1f} dBTP")
    blacks = _detect(path, "blackdetect=d=0.5:pix_th=0.10", r"black_start:(\S+) black_end:(\S+)")
    check("no long black segments", not blacks, f"{len(blacks)} found" if blacks else "none")
    freezes = _detect(path, "freezedetect=n=0.001:d=2.5", r"freeze_start: (\S+)")
    check("no frozen video >2.5s", not freezes, f"starts at {freezes}" if freezes else "none", "warning")
    silences = run([ffmpeg_bin(), "-hide_banner", "-i", str(path), "-af", "silencedetect=n=-45dB:d=2.0", "-vn", "-f",
                    "null", "-"]).stderr
    sil = re.findall(r"silence_start: (\S+)", silences)
    check("no dead air >2s", not sil, f"at {sil}" if sil else "none", "warning")
    if srt:
        txt = srt.read_text() if srt.exists() else ""
        cues = len(re.findall(r"-->", txt))
        check("subtitles", cues > 0, f"{cues} cues in {srt.name}")
    for k, val in (extra or {}).items():
        if isinstance(val, dict) and "ok" in val:
            check(k, val["ok"], val.get("detail", ""), val.get("severity", "error"))
    passed = all(c["ok"] for c in checks if c["severity"] == "error")
    return {"file": str(path), "duration": round(dur, 3), "loudness": loud, "passed": passed, "checks": checks}


def write_report(report: dict, json_path: Path, md_path: Path) -> None:
    json_path.write_text(json.dumps(report, indent=2))
    lines = [f"# QC report - {Path(report['file']).name}", "",
             f"**Result: {'PASS' if report['passed'] else 'FAIL'}**  (duration {report['duration']}s)", "",
             "| Check | Result | Detail |", "|---|---|---|"]
    for c in report["checks"]:
        mark = "pass" if c["ok"] else ("FAIL" if c["severity"] == "error" else "warn")
        lines.append(f"| {c['check']} | {mark} | {c['detail']} |")
    md_path.write_text("\n".join(lines) + "\n")
