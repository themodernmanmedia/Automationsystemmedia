"""Thumbnail engine: Blender character art + bold, mobile-readable typography (1280x720).

Each concept = a Blender still (characters/props/background) + text blocks composited
with Pillow. A 160px-wide mobile preview is saved next to each thumbnail so readability
can be checked at the size viewers actually see.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from animation.motion import CharacterAnimator, CharacterDirection
from animation.render import FONTS, ROOT, run_job

W, H = 1280, 720
INK = "#2A2230"


def character_still(cid, character, x, expr, pose=None, facing=1, ground=-3.2, frame=30):
    acts = [{"type": "pose", "name": pose, "start": 0, "end": 5}] if pose else []
    d = CharacterDirection(character, start_x=x, facing=facing, actions=acts, expressions=[{"at": 0, "name": expr}],
                           looks=[{"at": 0, "dx": 0.0, "dy": 0.1}], blink_seed=999)
    ch = CharacterAnimator(d, 30).bake(frame + 1)
    ch = {k: [v[frame]] for k, v in ch.items()}
    ch["y"] = [ch["y"][0] + ground]
    return {"id": cid, "spec": str(ROOT / f"characters/specs/{character}.json"), "channels": ch, "shadow": False}


def render_art(out_png: Path, background: dict, characters: list, props: list, camera: dict) -> Path:
    job = {"fps": 30, "resolution": [W, H], "frame_start": 1, "frame_end": 1, "samples": 16,
           "output_dir": str(out_png.parent), "background": background, "ground_y": -3.2,
           "characters": characters, "props": props, "camera": {k: [v] for k, v in camera.items()},
           "still_frame": 1, "still_path": str(out_png)}
    run_job(job, out_png.with_suffix(".json"))
    return out_png


def _font(size, weight="black"):
    return ImageFont.truetype(FONTS[weight], size)


def text_block(img, text, xy, size, fill="#FFFFFF", stroke=INK, stroke_w=10, anchor="la", box=None, rotate=0):
    """Big outlined text, optionally on a colored slab, optionally rotated."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = _font(size)
    if box:
        bb = d.textbbox(xy, text, font=f, anchor=anchor, stroke_width=stroke_w)
        pad = int(size * 0.18)
        d.rounded_rectangle((bb[0] - pad, bb[1] - pad, bb[2] + pad, bb[3] + pad), radius=int(size * 0.15),
                            fill=box, outline=INK, width=8)
    d.text(xy, text, font=f, fill=fill, anchor=anchor, stroke_width=stroke_w, stroke_fill=stroke)
    if rotate:
        layer = layer.rotate(rotate, resample=Image.BICUBIC, center=xy)
    shadow = layer.split()[3].filter(ImageFilter.GaussianBlur(6)).point(lambda a: int(a * 0.45))
    sh = Image.new("RGBA", img.size, (20, 12, 30, 0))
    sh.putalpha(shadow)
    img.alpha_composite(sh, (6, 8))
    img.alpha_composite(layer)


def finish(art: Path, out: Path, texts: list[dict], darken_left: bool = False) -> Path:
    img = Image.open(art).convert("RGBA").resize((W, H))
    if darken_left:
        grad = Image.linear_gradient("L").rotate(90).resize((W, H)).point(lambda v: int(v * 0.55))
        dark = Image.new("RGBA", (W, H), (20, 14, 34, 0))
        dark.putalpha(grad)
        img.alpha_composite(dark)
    for t in texts:
        text_block(img, **t)
    img = img.convert("RGB")
    img.save(out, quality=95)
    img.resize((320, 180), Image.LANCZOS).save(out.with_name(out.stem + "_mobile.png"))
    return out


def contrast_ok(path: Path) -> dict:
    """Crude legibility check: luminance spread of the downscaled mobile thumbnail."""
    im = Image.open(path).convert("L").resize((160, 90))
    px = list(im.getdata())
    px.sort()
    lo, hi = px[len(px) // 20], px[-len(px) // 20]
    return {"ok": hi - lo > 120, "spread": hi - lo}
