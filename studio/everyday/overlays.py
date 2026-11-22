"""Frame overlays: word-by-word captions, the DAY counter, transitions."""
from __future__ import annotations

import math
import re

from .config import FONT_HEADLINE, H, W
from .gfx import (
    alpha_group, at, clamp, ease_back, ease_out, fill, headline, hexc, lin_grad, line, pop, prog,
    rrect, saved, set_color, stroke, text, text_size,
)
from .timeline import Episode, Shot

CAPTION_SIZE = 74
CAPTION_Y = 952
HIGHLIGHT = "#ffe14d"


def _chunks(words: list[str], max_chars=20, max_words=4) -> list[list[int]]:
    out, cur, n = [], [], 0
    for i, w in enumerate(words):
        if cur and (n + len(w) > max_chars or len(cur) >= max_words):
            out.append(cur)
            cur, n = [], 0
        cur.append(i)
        n += len(w) + 1
        if re.search(r"[.!?,…]$", w) and n > 8:
            out.append(cur)
            cur, n = [], 0
    if cur:
        out.append(cur)
    return out


def _word_times(words: list[str], a: float, b: float):
    weights = [max(2, len(re.sub(r"\W", "", w))) + (3 if re.search(r"[.!?,…]$", w) else 0) + 1.5 for w in words]
    tot = sum(weights)
    times, t = [], a
    for wgt in weights:
        d = (b - a) * wgt / tot
        times.append((t, t + d))
        t += d
    return times


def draw_captions(ctx, ep: Episode, sh: Shot, t: float):
    if not sh.captions:
        return
    for ln, (a, b) in zip(sh.lines, sh.line_times):
        if not (a - 0.05 <= t < b + 0.25):
            continue
        cap = ln.caption if ln.caption is not None else ln.text
        if not cap:
            return
        words = cap.upper().split()
        times = _word_times(words, a, b)
        chunks = _chunks(words)
        tt = min(t, b - 0.01)
        cur_w = 0
        for i, (wa, wb) in enumerate(times):
            if wa <= tt:
                cur_w = i
        chunk = next(c for c in chunks if cur_w in c)
        chunk_start = times[chunk[0]][0]
        base_col = ep.caption_colors.get(ln.who, "#ffffff")
        size = CAPTION_SIZE
        # measure
        widths = [text_size(ctx, words[i], size)[0] for i in chunk]
        space = size * 0.28
        total = sum(widths) + space * (len(chunk) - 1)
        if total > W - 160:
            size *= (W - 160) / total
            widths = [w * (W - 160) / total for w in widths]
            space *= (W - 160) / total
            total = W - 160
        appear = ease_back(prog(t, chunk_start, 0.16), 2.2)
        x = W / 2 - total / 2
        with at(ctx, W / 2, CAPTION_Y, s=0.85 + 0.15 * appear):
            ctx.translate(-W / 2, -CAPTION_Y)
            # speaker tag for dialogue
            if ln.who != "narrator":
                tag = ln.who.upper()
                tw = text_size(ctx, tag, 34)[0]
                rrect(ctx, W / 2 - tw / 2 - 16, CAPTION_Y - size * 0.62 - 50, tw + 32, 46, 12)
                fill(ctx, base_col)
                text(ctx, tag, W / 2, CAPTION_Y - size * 0.62 - 27, 34, "#111111")
            for i, w in zip(chunk, widths):
                active = i == cur_w and t < b + 0.05
                s = 1.12 if active else 1.0
                col = HIGHLIGHT if (active and ln.who == "narrator") else base_col
                if active and ln.who != "narrator":
                    col = "#ffffff"
                with at(ctx, x + w / 2, CAPTION_Y, s=s, rot=(-0.03 if active else 0)):
                    headline(ctx, words[i], 0, 0, size, color=col, outline="#000000", ow=size * 0.2, shadow=size * 0.07)
                x += w + space
        return


def draw_day_badge(ctx, day: int, t_since_change: float, alpha=1.0):
    if day is None:
        return
    s = ease_back(clamp(t_since_change / 0.45), 2.6) if t_since_change < 0.45 else 1.0
    flash = max(0.0, 1 - t_since_change / 0.6)
    with alpha_group(ctx, alpha):
        with at(ctx, 190, 96, s=s):
            rrect(ctx, -150, -58, 300, 116, 22)
            fill(ctx, (0, 0, 0, 0.55))
            rrect(ctx, -150, -58, 300, 116, 22)
            stroke(ctx, (1, 0.88, 0.3, 0.6 + 0.4 * flash), 4)
            headline(ctx, f"DAY {day}", -10, -12, 62, color="#ffe14d", ow=8, shadow=4)
            text(ctx, "/30", 112, -2, 30, "#ffffff")
            # progress bar
            rrect(ctx, -124, 30, 248, 14, 7)
            fill(ctx, (1, 1, 1, 0.25))
            rrect(ctx, -124, 30, max(14, 248 * min(day, 30) / 30), 14, 7)
            ctx.set_source(lin_grad(-124, 0, 124, 0, [(0, "#ff4d4d"), (1, "#ffe14d")]))
            ctx.fill()


def draw_transition_in(ctx, kind: str, t: float, render_scene):
    """Calls render_scene() with transforms for the incoming transition."""
    d = 0.32
    if kind == "cut" or t >= d:
        render_scene()
        if kind == "flash" and t < 0.45:
            ctx.set_source_rgba(1, 1, 1, 1 - t / 0.45)
            ctx.paint()
        if kind == "fade" and t < 0.6:
            ctx.set_source_rgba(0, 0, 0, 1 - t / 0.6)
            ctx.paint()
        return
    p = ease_out(t / d)
    if kind == "whip":
        with saved(ctx):
            ctx.translate((1 - p) * W * 0.6, 0)
            render_scene()
        # motion streaks
        for k in range(14):
            y = (k * 97 + 31) % H
            x0 = (1 - p) * W * 0.6 - 200 - (k * 53) % 400
            line(ctx, x0, y, x0 + 600, y, (1, 1, 1, 0.35 * (1 - p)), 6 + k % 3 * 4)
    elif kind == "pop":
        with saved(ctx):
            s = 1.25 - 0.25 * p
            ctx.translate(W / 2, H / 2)
            ctx.scale(s, s)
            ctx.translate(-W / 2, -H / 2)
            render_scene()
    elif kind == "flash":
        render_scene()
        ctx.set_source_rgba(1, 1, 1, 1 - t / 0.45)
        ctx.paint()
    elif kind == "fade":
        render_scene()
        ctx.set_source_rgba(0, 0, 0, 1 - t / 0.6)
        ctx.paint()
    else:
        render_scene()
