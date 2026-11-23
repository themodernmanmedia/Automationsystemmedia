"""Manim scene templates. Run by graphics/render_manim.py; params come from FINSTUDIO_PARAMS (JSON).

Every template:
  * fills exactly params["duration"] seconds, with animations placed on narration beats
    (params["beats"], seconds from scene start),
  * draws on the brand paper background (or transparent when params["transparent"]),
  * shows params["source"] - data on screen always carries where it came from.
"""
import json
import os

from manim import *  # noqa: F401,F403

P = json.load(open(os.environ["FINSTUDIO_PARAMS"]))
INK, PAPER, GREEN, RED, GOLD, MUTED, BLUE = "#2A2230", "#F6EFE3", "#2FA866", "#E0524A", "#E3A72F", "#8C8296", "#3E7C9B"
FONT = "Inter"


def T(text, size=0.5, color=INK, weight=BOLD):
    return Text(text, font=FONT, weight=weight, color=color).scale(size)


class Base(Scene):
    def setup(self):
        self.t = 0.0
        if not P.get("transparent"):
            self.camera.background_color = ManimColor(P.get("bg", PAPER))
            grid = VGroup(*[Line([x, -4.5, 0], [x, 4.5, 0], stroke_width=1, color="#E7DCC8") for x in range(-8, 9)],
                          *[Line([-8, y, 0], [8, y, 0], stroke_width=1, color="#E7DCC8") for y in range(-5, 6)])
            self.add(grid)
        if P.get("chapter"):
            chip = T(P["chapter"].upper(), 0.24, MUTED, SEMIBOLD).to_corner(UL, buff=0.45)
            self.add(chip)
        if P.get("source"):
            src = T("Source: " + P["source"], 0.25, MUTED, NORMAL)
            src.to_corner(DL, buff=0.35)
            if src.width > 13:
                src.scale_to_fit_width(13)
            self.add(src)

    def play_(self, *anims, rt=0.6):
        self.play(*anims, run_time=rt)
        self.t += rt

    def until(self, t):
        if t > self.t + 0.02:
            self.wait(t - self.t)
            self.t = t

    def finish(self):
        self.until(P["duration"])

    def beat(self, i, default):
        b = P.get("beats", [])
        return b[i] if i < len(b) else default


class BigNumber(Base):
    """A headline number counting up, with a label and optional sub-caption."""
    def construct(self):
        self.until(self.beat(0, 0.2))
        value, prefix, suffix, dec = P["value"], P.get("prefix", ""), P.get("suffix", ""), P.get("decimals", 0)
        tracker = ValueTracker(0)
        color = P.get("color", INK)

        def num():
            v = tracker.get_value()
            s = f"{prefix}{v:,.{dec}f}{suffix}"
            return T(s, 1.6, color, HEAVY).move_to(UP * 0.4)
        n = always_redraw(num)
        label = T(P["label"], 0.5, INK, SEMIBOLD).next_to(UP * 0.4, DOWN, buff=1.0)
        self.add(n)
        self.play_(tracker.animate.set_value(value), FadeIn(label, shift=UP * 0.2), rt=P.get("count_time", 1.4))
        if P.get("caption"):
            self.until(self.beat(1, self.t + 0.6))
            cap = T(P["caption"], 0.36, MUTED, NORMAL).next_to(label, DOWN, buff=0.35)
            self.play_(FadeIn(cap, shift=UP * 0.15), rt=0.5)
        self.finish()


class Bars(Base):
    """Vertical bars (positive/negative) revealed one by one on beats."""
    def construct(self):
        title = T(P["title"], 0.5).to_edge(UP, buff=0.9)
        self.play_(Write(title), rt=0.6)
        items = P["items"]
        vmax = max(abs(i["value"]) for i in items) or 1
        h = P.get("max_height", 4.0)
        has_neg = any(i["value"] < 0 for i in items)
        base_y = -0.6 if has_neg else -2.4
        n = len(items)
        width = min(1.4, 11.5 / n * 0.62)
        xs = [(-(n - 1) / 2 + k) * min(2.3, 12 / n) for k in range(n)]
        axis = Line([-6.6, base_y, 0], [6.6, base_y, 0], color=INK, stroke_width=4)
        self.play_(Create(axis), rt=0.3)
        for k, (x, it) in enumerate(zip(xs, items)):
            self.until(self.beat(k, self.t + 0.2))
            v = it["value"]
            bh = max(abs(v) / vmax * (h if not has_neg else h * 0.62), 0.05)
            col = it.get("color", GREEN if v >= 0 else RED)
            bar = Rectangle(width=width, height=bh, fill_color=col, fill_opacity=1, stroke_color=INK, stroke_width=3)
            bar.move_to([x, base_y + (bh / 2 if v >= 0 else -bh / 2), 0])
            val = T(it.get("text", f"{v:+.1f}%"), 0.4, col if col != GOLD else INK)
            val.next_to(bar, UP if v >= 0 else DOWN, buff=0.12)
            lab = T(it["label"], 0.27, INK, SEMIBOLD)
            lab.next_to([x, base_y, 0], DOWN if v >= 0 else UP, buff=0.22)
            self.play_(GrowFromEdge(bar, DOWN if v >= 0 else UP), FadeIn(val), FadeIn(lab), rt=0.45)
        if P.get("note"):
            self.until(self.beat(n, self.t + 0.4))
            note = T(P["note"], 0.32, MUTED, SEMIBOLD).to_edge(DOWN, buff=0.9)
            self.play_(FadeIn(note), rt=0.4)
        self.finish()


class Compare(Base):
    """Two big labelled numbers side by side with a delta arrow."""
    def construct(self):
        title = T(P["title"], 0.5).to_edge(UP, buff=0.9)
        self.play_(Write(title), rt=0.6)
        cards = []
        for k, side in enumerate(P["sides"]):
            self.until(self.beat(k, self.t + 0.3))
            box = RoundedRectangle(corner_radius=0.3, width=5.2, height=3.4, fill_color=side.get("bg", "#FFFFFF"),
                                   fill_opacity=1, stroke_color=INK, stroke_width=4)
            box.move_to([-3.2 if k == 0 else 3.2, -0.2, 0])
            big = T(side["value"], 1.0, side.get("color", INK), HEAVY).move_to(box.get_center() + UP * 0.35)
            lab = T(side["label"], 0.32, INK, SEMIBOLD).move_to(box.get_center() + DOWN * 0.75)
            sub = T(side.get("sub", ""), 0.24, MUTED, NORMAL).move_to(box.get_center() + DOWN * 1.2)
            g = VGroup(box, big, lab, sub)
            self.play_(FadeIn(g, shift=UP * 0.3), rt=0.5)
            cards.append(g)
        if P.get("delta"):
            self.until(self.beat(2, self.t + 0.4))
            d = T(P["delta"], 0.45, RED, HEAVY).next_to(VGroup(*cards), DOWN, buff=0.45)
            self.play_(GrowFromCenter(d), rt=0.5)
        self.finish()


class Quote(Base):
    """Research citation card."""
    def construct(self):
        self.until(self.beat(0, 0.2))
        q = Paragraph(*P["lines"], font=FONT, alignment="center", line_spacing=0.8).scale(0.52)
        q.set_color(INK)
        mark = T("“", 2.4, GOLD, HEAVY).next_to(q, UP, buff=0.1)
        who = T(P["who"], 0.34, INK, SEMIBOLD).next_to(q, DOWN, buff=0.6)
        cite = T(P["cite"], 0.24, MUTED, NORMAL).next_to(who, DOWN, buff=0.2)
        self.play_(FadeIn(mark, scale=1.4), rt=0.4)
        self.play_(Write(q), rt=min(1.6, P["duration"] * 0.3))
        self.until(self.beat(1, self.t + 0.3))
        self.play_(FadeIn(who, shift=UP * 0.1), FadeIn(cite), rt=0.5)
        self.finish()


class PriceLevel(Base):
    """Concept: inflation rate falls but the price level keeps rising (not data)."""
    def construct(self):
        title = T(P.get("title", "Falling inflation is not falling prices"), 0.48).to_edge(UP, buff=0.85)
        self.play_(Write(title), rt=0.6)
        ax = Axes(x_range=[0, 10, 1], y_range=[0, 10, 2], x_length=10, y_length=5, tips=False,
                  axis_config={"color": INK, "stroke_width": 3, "include_ticks": False}).shift(DOWN * 0.5)
        xl = T("time", 0.3, MUTED, NORMAL).next_to(ax.x_axis, DOWN, buff=0.15)
        yl = T("price level", 0.3, MUTED, NORMAL).rotate(PI / 2).next_to(ax.y_axis, LEFT, buff=0.15)
        self.play_(Create(ax), FadeIn(xl), FadeIn(yl), rt=0.6)

        def f(x):  # gentle rise, a surge, then a slower (still rising) climb
            if x < 3:
                return 2 + 0.25 * x
            if x < 5.5:
                return 2.75 + 1.25 * (x - 3)
            return 5.875 + 0.32 * (x - 5.5)
        self.until(self.beat(0, self.t + 0.2))
        c1 = ax.plot(f, x_range=[0, 3], color=BLUE, stroke_width=7)
        self.play_(Create(c1), rt=0.9)
        self.until(self.beat(1, self.t + 0.2))
        c2 = ax.plot(f, x_range=[3, 5.5], color=RED, stroke_width=7)
        surge = T("inflation surge", 0.3, RED).next_to(ax.c2p(4.2, f(4.2)), LEFT, buff=0.25)
        self.play_(Create(c2), FadeIn(surge), rt=1.0)
        self.until(self.beat(2, self.t + 0.2))
        c3 = ax.plot(f, x_range=[5.5, 10], color=GOLD, stroke_width=7)
        cool = T("inflation 'cools'... prices still rise", 0.3, INK).next_to(ax.c2p(8, f(8)), UP, buff=0.35)
        self.play_(Create(c3), FadeIn(cool), rt=1.0)
        self.until(self.beat(3, self.t + 0.2))
        ghost = DashedLine(ax.c2p(3, f(3)), ax.c2p(10, 2 + 0.25 * 10), color=MUTED)
        gl = T("where prices would be without the surge", 0.26, MUTED, NORMAL).next_to(ghost, DOWN, buff=0.15)
        gap = DoubleArrow(ax.c2p(9.6, 2 + 0.25 * 9.6), ax.c2p(9.6, f(9.6)), color=RED, buff=0.05, stroke_width=4)
        gt = T("the gap stays", 0.3, RED).next_to(gap, RIGHT, buff=0.12)
        self.play_(Create(ghost), FadeIn(gl), GrowFromCenter(gap), FadeIn(gt), rt=0.9)
        self.finish()


class Checklist(Base):
    """Numbered lessons appearing on beats."""
    def construct(self):
        title = T(P["title"], 0.55).to_edge(UP, buff=0.8)
        self.play_(Write(title), rt=0.6)
        rows = VGroup()
        for k, item in enumerate(P["items"]):
            badge = VGroup(Circle(radius=0.3, fill_color=GOLD, fill_opacity=1, stroke_color=INK, stroke_width=3),
                           T(str(k + 1), 0.42, INK, HEAVY))
            txt = T(item, 0.4, INK, SEMIBOLD)
            row = VGroup(badge, txt).arrange(RIGHT, buff=0.35)
            rows.add(row)
        rows.arrange(DOWN, aligned_edge=LEFT, buff=0.42).next_to(title, DOWN, buff=0.6)
        if rows.width > 13:
            rows.scale_to_fit_width(13)
        for k, row in enumerate(rows):
            self.until(self.beat(k, self.t + 0.3))
            self.play_(FadeIn(row, shift=RIGHT * 0.4), rt=0.45)
        self.finish()


class TitleCard(Base):
    """Chapter / episode title."""
    def construct(self):
        self.until(self.beat(0, 0.1))
        kicker = T(P.get("kicker", ""), 0.32, GOLD, HEAVY)
        title = Paragraph(*P["lines"], font=FONT, alignment="center", line_spacing=0.7).scale(0.95)
        title.set_color(INK)
        g = VGroup(kicker, title).arrange(DOWN, buff=0.4)
        bar = Rectangle(width=title.width + 1, height=0.12, fill_color=GOLD, fill_opacity=1,
                        stroke_width=0).next_to(title, DOWN, buff=0.35)
        self.play_(FadeIn(kicker, shift=DOWN * 0.2), Write(title), GrowFromEdge(bar, LEFT), rt=1.0)
        self.finish()


class Waterfall(Base):
    """Start value then signed steps; final total bar."""
    def construct(self):
        title = T(P["title"], 0.5).to_edge(UP, buff=0.9)
        self.play_(Write(title), rt=0.6)
        bars = P["bars"]
        vmax = max(abs(b["value"]) for b in bars) or 1
        base_y, scale = -2.3, 4.0 / vmax
        n = len(bars)
        slot = 11 / n
        x0 = -5.5 + slot / 2
        axis = Line([-6.4, base_y, 0], [6.4, base_y, 0], color=INK, stroke_width=4)
        self.play_(Create(axis), rt=0.3)
        level = 0.0
        for i, b in enumerate(bars):
            self.until(self.beat(i, self.t + 0.25))
            x, v, kind = x0 + i * slot, b["value"], b.get("kind", "delta")
            lo, hi = (0.0, level) if kind == "total" else ((level, level + v) if v >= 0 else (level + v, level))
            h = max((hi - lo) * scale, 0.04)
            col = MUTED if kind == "total" else (GREEN if v >= 0 else RED)
            rect = Rectangle(width=slot * 0.6, height=h, fill_color=col, fill_opacity=1, stroke_color=INK,
                             stroke_width=3).move_to([x, base_y + (lo + hi) / 2 * scale, 0])
            val = T(b["text"], 0.42, col if kind != "total" else INK).next_to(rect, UP, buff=0.12)
            lab = T(b["label"], 0.28, INK, SEMIBOLD).next_to([x, base_y, 0], DOWN, buff=0.2)
            self.play_(GrowFromEdge(rect, DOWN if v >= 0 else UP), FadeIn(val), FadeIn(lab), rt=0.5)
            if kind != "total":
                level += v
        self.finish()
