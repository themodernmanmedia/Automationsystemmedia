#!/usr/bin/env python3
"""Render every thumbnail variant of an episode (for YouTube Test & Compare)
plus a phone-size legibility sheet."""
import argparse
import sys
from importlib import import_module
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import everyday  # noqa: F401
import cairo
from everyday.config import H, OUT_DIR, W
from everyday.episodes import EPISODES

ap = argparse.ArgumentParser()
ap.add_argument("--episode", default="last-to-leave-circle")
a = ap.parse_args()
mod = import_module(EPISODES[a.episode])
variants = getattr(mod, "THUMBNAILS", {"main": mod.EPISODE.thumbnail})
out = OUT_DIR / mod.EPISODE.slug
out.mkdir(parents=True, exist_ok=True)
surfs = {}
for name, fn in variants.items():
    s = cairo.ImageSurface(cairo.FORMAT_RGB24, 1280, 720)
    c = cairo.Context(s)
    c.scale(1280 / W, 720 / H)
    fn(c)
    s.write_to_png(str(out / f"thumbnail_{name}.png"))
    surfs[name] = s
    print("wrote", out / f"thumbnail_{name}.png")
# legibility sheet: each variant at desktop (360px), mobile feed (246px) and sidebar (168px)
sizes = (360, 246, 168)
sheet = cairo.ImageSurface(cairo.FORMAT_RGB24, sum(sizes) + 80, len(surfs) * 220 + 20)
c = cairo.Context(sheet)
c.set_source_rgb(0.06, 0.06, 0.06)
c.paint()
for r, (name, s) in enumerate(surfs.items()):
    x = 20
    for w in sizes:
        c.save()
        c.translate(x, 20 + r * 220)
        c.scale(w / 1280, w / 1280)
        c.set_source_surface(s, 0, 0)
        c.paint()
        c.restore()
        x += w + 20
sheet.write_to_png(str(out / "thumbnail_size_test.png"))
print("wrote", out / "thumbnail_size_test.png")
