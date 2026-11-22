#!/usr/bin/env python3
"""Render an Everyday Beast episode to a finished YouTube upload package.

Examples
  python make_video.py                              # full 1080p render
  python make_video.py --preview                    # fast 540p render
  python make_video.py --contact-sheet              # one still per shot, as a grid
  python make_video.py --still 12.5 --still 80     # single frames
  python make_video.py --from 60 --to 90 --preview # render a slice
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import everyday  # noqa: E402,F401  (font setup)
import cairo  # noqa: E402

from everyday.config import H, OUT_DIR, W  # noqa: E402
from everyday.episodes import EPISODES, load  # noqa: E402
from everyday.render import build_audio, mux, render_still, render_video, write_metadata  # noqa: E402
from everyday.timeline import build  # noqa: E402


def contact_sheet(ep, path: Path, cols=6, scale=0.25):
    tw, th = int(W * scale), int(H * scale)
    n = len(ep.shots)
    rows = (n + cols - 1) // cols
    sheet = cairo.ImageSurface(cairo.FORMAT_RGB24, cols * tw, rows * th)
    sctx = cairo.Context(sheet)
    from everyday.render import draw_frame

    for i, sh in enumerate(ep.shots):
        gt = sh.start + sh.dur * 0.62
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, tw, th)
        ctx = cairo.Context(surf)
        ctx.scale(scale, scale)
        draw_frame(ctx, ep, gt)
        sctx.set_source_surface(surf, (i % cols) * tw, (i // cols) * th)
        sctx.paint()
        sctx.set_source_rgb(1, 1, 0)
        sctx.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        sctx.set_font_size(16)
        sctx.move_to((i % cols) * tw + 8, (i // cols) * th + 20)
        sctx.show_text(f"{i + 1}. {sh.name}")
    sheet.write_to_png(str(path))


def render_thumbnail(ep, path: Path):
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 1280, 720)
    ctx = cairo.Context(surf)
    ctx.scale(1280 / W, 720 / H)
    ep.thumbnail(ctx)
    surf.write_to_png(str(path))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episode", default="ignore-everyone-30-days", choices=sorted(EPISODES))
    ap.add_argument("--preview", action="store_true", help="render at 960x540")
    ap.add_argument("--scale", type=float, default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=None)
    ap.add_argument("--still", type=float, action="append", default=[])
    ap.add_argument("--contact-sheet", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    ep = load(args.episode)
    folder = args.out / ep.slug
    folder.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    print(f"▶ {ep.title}\n• synthesising voices & timing")
    build(ep)
    print(f"• total runtime {ep.total // 60:.0f}:{ep.total % 60:04.1f}")

    if args.still or args.contact_sheet:
        for s in args.still:
            p = folder / f"still_{s:07.2f}.png"
            render_still(ep, s, p, scale=args.scale or 1.0)
            print(f"  wrote {p}")
        if args.contact_sheet:
            p = folder / "contact_sheet.png"
            contact_sheet(ep, p)
            print(f"  wrote {p}")
        return

    scale = args.scale or (0.5 if args.preview else 1.0)
    print("• mixing audio (voices, music, sfx)")
    wav = build_audio(ep, folder / "audio.wav")
    print(f"• rendering frames at {int(W * scale)}x{int(H * scale)}")
    silent, tmp = render_video(ep, folder / "video.mp4", scale=scale, workers=args.workers, crf=args.crf,
                               t0=args.t0, t1=args.t1)
    suffix = "_preview" if scale < 1 else ""
    if args.t0 or args.t1:
        suffix += f"_{int(args.t0)}-{int(args.t1 or ep.total)}"
    final = folder / f"{ep.slug}{suffix}.mp4"
    mux(silent, wav, final, args.t0, args.t1)
    shutil.rmtree(tmp, ignore_errors=True)
    print("• thumbnail & metadata")
    render_thumbnail(ep, folder / "thumbnail.png")
    write_metadata(ep, folder)
    print(f"✔ done in {time.time() - t_start:.0f}s → {final}")


if __name__ == "__main__":
    main()
