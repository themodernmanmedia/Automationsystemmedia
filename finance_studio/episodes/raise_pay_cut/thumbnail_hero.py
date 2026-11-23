"""Hero thumbnail + Test & Compare variants for episode 1 (3840x2160, < 2 MB JPG).

Design is driven by research (see thumbnail_research.md):
  * one clear contrast (pay vs. prices) shown as an outcome, not a process
  * 4 words of text that add to the title instead of repeating it
  * one arrow to guide the eye; nothing important in the bottom-right timestamp zone
  * an illustrated character with a story-true reaction (not exaggerated shock)
  * every claim on the thumbnail is delivered in the video
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from animation.render import FONTS, ROOT, run_job
from thumbnails.engine import character_still

S = 3  # design at 1280x720, render at 3x = 3840x2160
W, H = 1280 * S, 720 * S
INK, PAPER, GREEN, RED, GOLD = "#2A2230", "#F6EFE3", "#2FA866", "#E0524A", "#FFD54A"
OUT = ROOT / "output" / "why-your-raise-feels-like-a-pay-cut" / "thumbnails"


def f(size, w="black"):
    return ImageFont.truetype(FONTS[w], size * S)


def maya(name, expr, pose, facing=-1, x=0.0, cam_x=-0.1, cam_y=0.25, width=4.4, res=(1100, 1240)):
    png = OUT / "hero" / f"{name}.png"
    c = character_still("maya", "maya", x, expr, pose, facing=facing)
    job = {"fps": 30, "resolution": list(res), "frame_start": 1, "frame_end": 1, "samples": 32,
           "output_dir": str(png.parent), "background": {"kind": "none"}, "transparent": True, "characters": [c],
           "camera": {"x": [cam_x], "y": [cam_y], "width": [width]}, "still_frame": 1, "still_path": str(png)}
    run_job(job, png.with_suffix(".json"))
    return Image.open(png).convert("RGBA")


def paper_bg():
    img = Image.new("RGBA", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    for x in range(0, W, 60 * S):
        d.line([(x, 0), (x, H)], fill="#E7DCC8", width=2 * S)
    for y in range(0, H, 60 * S):
        d.line([(0, y), (W, y)], fill="#E7DCC8", width=2 * S)
    return img


def shadowed(img, layer, offset=(5, 7), blur=7, alpha=0.4):
    sh = layer.split()[3].filter(ImageFilter.GaussianBlur(blur * S)).point(lambda a: int(a * alpha))
    s = Image.new("RGBA", img.size, (20, 12, 30, 0))
    s.putalpha(sh)
    img.alpha_composite(s, (offset[0] * S, offset[1] * S))
    img.alpha_composite(layer)


def text(img, s, xy, size, fill="#FFFFFF", stroke=INK, sw=9, anchor="la", box=None, pad=16, rot=0):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    xy = (xy[0] * S, xy[1] * S)
    if box:
        bb = d.textbbox(xy, s, font=f(size), anchor=anchor, stroke_width=sw * S)
        d.rounded_rectangle((bb[0] - pad * S, bb[1] - pad * S, bb[2] + pad * S, bb[3] + pad * S), radius=14 * S,
                            fill=box, outline=INK, width=7 * S)
    d.text(xy, s, font=f(size), fill=fill, anchor=anchor, stroke_width=sw * S, stroke_fill=stroke)
    if rot:
        layer = layer.rotate(rot, resample=Image.BICUBIC, center=xy)
    shadowed(img, layer)


def chart(img, box=(60, 330, 720, 690)):
    """Stylized pay-vs-prices lines: prices overtake pay and a red gap opens (concept, matches the video)."""
    x0, y0, x1, y1 = [v * S for v in box]
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.line([(x0, y1), (x1, y1)], fill=INK, width=8 * S)
    d.line([(x0, y0), (x0, y1)], fill=INK, width=8 * S)

    def pt(u, v):  # u, v in 0..1
        return (x0 + u * (x1 - x0), y1 - v * (y1 - y0))
    us = [i / 60 for i in range(61)]
    pay = [pt(u, 0.12 + 0.30 * u) for u in us]
    prices = [pt(u, 0.10 + (0.22 * u if u < 0.35 else 0.077 + 1.55 * (u - 0.35) ** 1.15)) for u in us]
    cross = next(i for i in range(len(us)) if prices[i][1] < pay[i][1])
    gap = prices[cross:] + list(reversed(pay[cross:]))
    d.polygon(gap, fill=(224, 82, 74, 95))
    d.line(pay, fill=GREEN, width=16 * S, joint="curve")
    d.line(prices, fill=RED, width=16 * S, joint="curve")
    for p, col in ((pay[-1], GREEN), (prices[-1], RED)):
        r = 14 * S
        d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=col, outline=INK, width=5 * S)
    shadowed(img, layer, (4, 5), 5, 0.25)
    text(img, "PRICES", (prices[-1][0] / S - 52, prices[-1][1] / S + 92), 50, fill=RED, stroke="#FFFFFF", sw=8,
         anchor="rt")
    text(img, "YOUR PAY", (pay[-1][0] / S - 10, pay[-1][1] / S + 26), 50, fill=GREEN, stroke="#FFFFFF", sw=8,
         anchor="rt")
    return pay, prices


def arrow(img, tail, head, color=INK, width=12):
    import math
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    tx, ty, hx, hy = tail[0] * S, tail[1] * S, head[0] * S, head[1] * S
    d.line([(tx, ty), (hx, hy)], fill=color, width=width * S)
    a = math.atan2(hy - ty, hx - tx)
    L = 34 * S
    pts = [(hx + 10 * S * math.cos(a), hy + 10 * S * math.sin(a)),
           (hx - L * math.cos(a - 0.5), hy - L * math.sin(a - 0.5)),
           (hx - L * math.cos(a + 0.5), hy - L * math.sin(a + 0.5))]
    d.polygon(pts, fill=color)
    shadowed(img, layer, (3, 4), 4, 0.3)


def save(img, name):
    rgb = img.convert("RGB")
    path = OUT / f"{name}.jpg"
    q = 92
    while True:
        rgb.save(path, quality=q, optimize=True)
        if path.stat().st_size < 1_900_000 or q <= 70:
            break
        q -= 4
    rgb.resize((1280, 720), Image.LANCZOS).save(OUT / f"{name}_1280.jpg", quality=92)
    rgb.resize((168, 94), Image.LANCZOS).save(OUT / f"{name}_mobile.png")  # mobile list size check
    return path


def hero():
    img = paper_bg()
    pay, prices = chart(img)
    m = maya("hero_maya", "shocked", "worried_hands")
    m = m.resize((int(m.width * 0.7 * S), int(m.height * 0.7 * S)), Image.LANCZOS)
    shadowed(img, Image.new("RGBA", img.size, (0, 0, 0, 0)))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    layer.alpha_composite(m, (W - m.width + 130 * S, H - m.height + 190 * S))
    shadowed(img, layer, (6, 8), 8, 0.35)
    text(img, "RECORD INCOME.", (50, 40), 86, fill="#FFFFFF", box=GREEN, pad=14)
    text(img, "STILL BROKE?", (56, 168), 104, fill=GOLD, sw=11, rot=2)
    gx, gy = prices[-1][0] / S, (prices[-1][1] + pay[-1][1]) / 2 / S
    arrow(img, (gx + 120, gy + 120), (gx + 28, gy + 20), color=INK, width=13)
    return save(img, "HERO_record_income_still_broke")


def variant_math():
    """Variant 2: the 'real math' contrast - raise vs real raise (both numbers are in the video)."""
    img = paper_bg()
    m = maya("v2_maya", "worried", "hold_up", facing=1, cam_x=0.35)
    m = m.resize((int(m.width * 0.66 * S), int(m.height * 0.66 * S)), Image.LANCZOS)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    layer.alpha_composite(m, (-60 * S, H - m.height + 120 * S))
    shadowed(img, layer, (6, 8), 8, 0.35)
    text(img, "+5% RAISE", (880, 210), 100, fill="#FFFFFF", box=GREEN, anchor="mm", pad=18)
    text(img, "REALLY +1.3%", (880, 450), 100, fill="#FFFFFF", box=RED, anchor="mm", pad=18, rot=-2)
    arrow(img, (880, 290), (880, 360), color=INK, width=14)
    return save(img, "V2_raise_vs_real_raise")


def variant_siblings():
    """Variant 3: same raise, different life - Dev (locked in) vs Maya (exposed)."""
    img = paper_bg()
    for cid, ch, x, expr, pose, facing in (("v3_dev", "dev", -2.35, "happy", "hand_on_hip", 1),
                                         ("v3_maya", "maya", 2.15, "shocked", "worried_hands", -1)):
        c = character_still(cid, ch, x, expr, pose, facing=facing)
        png = OUT / "hero" / f"{cid}.png"
        job = {"fps": 30, "resolution": [W // S, H // S], "frame_start": 1, "frame_end": 1, "samples": 32,
               "output_dir": str(png.parent), "background": {"kind": "none"}, "transparent": True, "characters": [c],
               "camera": {"x": [0.0], "y": [1.15], "width": [10.4]}, "still_frame": 1, "still_path": str(png)}
        run_job(job, png.with_suffix(".json"))
        lay = Image.open(png).convert("RGBA").resize((W, H), Image.LANCZOS)
        shadowed(img, lay, (6, 8), 8, 0.35)
    text(img, "SAME RAISE.", (640, 30), 104, anchor="ma")
    text(img, "DIFFERENT LIFE.", (640, 600), 104, fill=GOLD, anchor="ma", sw=11)
    text(img, "2.65%", (175, 470), 66, fill="#FFFFFF", box="#3E7C9B", anchor="mm", pad=12)
    text(img, "7.11%", (1110, 470), 66, fill="#FFFFFF", box=RED, anchor="mm", pad=12)
    return save(img, "V3_same_raise_different_life")


if __name__ == "__main__":
    (OUT / "hero").mkdir(parents=True, exist_ok=True)
    for p in (hero(), variant_math(), variant_siblings()):
        print(p, p.stat().st_size // 1024, "KB")
