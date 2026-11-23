"""Three thumbnail concepts for episode 1. Run: python -m episodes.raise_pay_cut.thumbnails (from finance_studio/)."""
from pathlib import Path

from animation.render import ROOT
from thumbnails.engine import character_still, contrast_ok, finish, render_art

OUT = ROOT / "output" / "why-your-raise-feels-like-a-pay-cut" / "thumbnails"


def tag(pid, label, color, x, y, rot, s=1.0):
    return {"id": pid, "kind": "price_tag", "label": label, "color": color, "z": 0.9,
            "tracks": {"x": [x], "y": [y], "s": [s], "rot": [rot]}}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    # A - the shocked paycheck: Maya gasps as her paycheck shrinks
    art = render_art(OUT / "a_art.png", {"kind": "apartment_night", "table_x": 3.5, "chair_x": 9.0, "bills": False},
                     [character_still("maya", "maya", 2.45, "surprised", "hold_up")],
                     [{"id": "pc", "kind": "paycheck", "attach": {"character": "maya", "joint": "hand_f",
                                                                  "offset": [0.0, -0.16], "rot": 25, "z": 0.004}},
                      ],
                     {"x": 1.0, "y": 0.6, "width": 6.4})
    a = finish(art, OUT / "A_raise_vs_paycut.jpg", [
        {"text": "MY RAISE", "xy": (50, 70), "size": 120, "fill": "#FFFFFF"},
        {"text": "= PAY CUT?", "xy": (50, 215), "size": 120, "fill": "#FFD54A"},
    ], darken_left=True)
    # B - the paradox numbers
    art = render_art(OUT / "b_art.png", {"kind": "studio", "top": "#F3E3C6", "coins": 6},
                     [character_still("maya", "maya", 3.3, "confused", "head_scratch")], [],
                     {"x": 1.5, "y": 0.6, "width": 6.6})
    b = finish(art, OUT / "B_record_income_shrinking_pay.jpg", [
        {"text": "RECORD INCOME", "xy": (40, 60), "size": 92, "fill": "#FFFFFF", "box": "#2FA866"},
        {"text": "REAL PAY ↓", "xy": (40, 250), "size": 118, "fill": "#FFFFFF", "box": "#E0524A", "rotate": 3},
    ])
    # C - same raise, different life (Dev relaxed, Maya stressed)
    art = render_art(OUT / "c_art.png", {"kind": "studio", "coins": 4},
                     [character_still("dev", "dev", -2.4, "happy", "hand_on_hip"),
                      character_still("maya", "maya", 2.2, "worried", "worried_hands", facing=-1)], [],
                     {"x": 0.0, "y": 0.5, "width": 8.6})
    c = finish(art, OUT / "C_same_raise_different_life.jpg", [
        {"text": "SAME RAISE.", "xy": (640, 40), "size": 96, "fill": "#FFFFFF", "anchor": "ma"},
        {"text": "DIFFERENT LIFE.", "xy": (640, 600), "size": 96, "fill": "#FFD54A", "anchor": "ma"},
    ])
    for p in (a, b, c):
        report[p.name] = contrast_ok(p)
    print(report)
    return [a, b, c]


if __name__ == "__main__":
    main()
