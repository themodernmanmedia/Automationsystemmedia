"""FFmpeg assembly: frames + graphic overlays + finishing + mixed audio -> delivery MP4."""
from __future__ import annotations

from pathlib import Path

from core.tools import ffmpeg_bin, run


def assemble(frames_dir: Path, fps: int, audio: Path, out: Path, *, overlays: list[dict] | None = None,
             duration: float | None = None, video_cfg: dict | None = None, grain: bool = True,
             fade_in: float = 0.4, fade_out: float = 0.5, log_file: Path | None = None) -> Path:
    """overlays: [{"path": mov_with_alpha, "start": seconds, "end": seconds|None, "fade": seconds}]"""
    v = {"codec": "libx264", "pix_fmt": "yuv420p", "crf": 18, "preset": "medium", "audio_codec": "aac",
         "audio_bitrate": "192k", "audio_sample_rate": 48000, "width": 1920, "height": 1080, **(video_cfg or {})}
    overlays = overlays or []
    cmd = [ffmpeg_bin(), "-y", "-v", "error", "-framerate", str(fps), "-start_number", "1",
           "-i", str(frames_dir / "f_%04d.png")]
    for ov in overlays:
        cmd += ["-itsoffset", f"{ov['start']:.3f}", "-i", str(ov["path"])]
    cmd += ["-i", str(audio)]
    audio_idx = 1 + len(overlays)
    chain = [f"[0:v]fps={fps},scale={v['width']}:{v['height']}:flags=lanczos,format=rgba[base0]"]
    cur = "base0"
    for k, ov in enumerate(overlays, start=1):
        end = ov.get("end")
        fade = ov.get("fade", 0.3)
        ochain = f"[{k}:v]format=rgba"
        if end is not None:
            ochain += f",fade=t=out:st={end - fade:.3f}:d={fade:.3f}:alpha=1"
        chain.append(f"{ochain}[ov{k}]")
        enable = f":enable='between(t,{ov['start']:.3f},{end:.3f})'" if end is not None else ""
        chain.append(f"[{cur}][ov{k}]overlay=0:0:eof_action=pass:format=auto{enable}[base{k}]")
        cur = f"base{k}"
    finish = [f"format=yuv420p"]
    if grain:
        # subtle paper/film texture + vignette: keeps flat vector art from looking sterile
        finish = ["vignette=angle=PI/5.5", "noise=alls=3:allf=t", "format=yuv420p"]
    if fade_in:
        finish.append(f"fade=t=in:st=0:d={fade_in}")
    if fade_out and duration:
        finish.append(f"fade=t=out:st={duration - fade_out:.3f}:d={fade_out}")
    chain.append(f"[{cur}]" + ",".join(finish) + "[vout]")
    afilter = f"[{audio_idx}:a]aresample={v['audio_sample_rate']}"
    if fade_out and duration:
        afilter += f",afade=t=out:st={duration - fade_out:.3f}:d={fade_out}"
    chain.append(afilter + "[aout]")
    cmd += ["-filter_complex", ";".join(chain), "-map", "[vout]", "-map", "[aout]",
            "-c:v", v["codec"], "-preset", v["preset"], "-crf", str(v["crf"]), "-pix_fmt", v["pix_fmt"],
            "-profile:v", "high", "-r", str(fps), "-g", str(fps * 2),
            "-c:a", v["audio_codec"], "-b:a", v["audio_bitrate"], "-ar", str(v["audio_sample_rate"]), "-ac", "2",
            "-movflags", "+faststart"]
    if duration:
        cmd += ["-t", f"{duration:.3f}"]
    cmd.append(str(out))
    out.parent.mkdir(parents=True, exist_ok=True)
    run(cmd, log_file=log_file, timeout=3600)
    return out
