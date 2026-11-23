"""Episode 1 - Why Your Raise Feels Like a Pay Cut (Even When It Isn't).

Structure (target runtime 8-10 min): hook, mystery, characters, first revelation,
stakes, deeper explanation, biggest revelation, payoff. Every on-screen number
is listed with its source in sources.md. Maya and Dev are fictional; their
5% raise and $300k loan are illustrative examples and are labelled as such.
"""
from animation.director import SceneSpec

EPISODE = {
    "slug": "why-your-raise-feels-like-a-pay-cut",
    "title": "Why Your Raise Feels Like a Pay Cut (Even When It Isn't)",
    "chapters": {"hook": "A record year... so why broke?", "mystery": "The paycheck paradox",
                 "characters": "Maya and Dev", "reveal1": "Money illusion",
                 "stakes": "Locked in vs. exposed", "deeper": "Why prices never come back down",
                 "reveal2": "The biggest discovery", "payoff": "How to make a raise real"},
    "music": {"hook": {"chords": ["Am", "F"], "mood": "tension"},
              "mystery": {"chords": ["Am", "F", "Dm7", "Esus4"], "mood": "tension"},
              "characters": {"chords": ["Cmaj7", "Fmaj7", "Am7", "G6"], "mood": "hopeful"},
              "reveal1": {"chords": ["Fmaj7", "Cmaj7", "Am7", "G6"], "mood": "hopeful"},
              "stakes": {"chords": ["Am", "F", "Dm7", "E7"], "mood": "tension"},
              "deeper": {"chords": ["Dm7", "Am7", "Fmaj7", "G6"], "mood": "hopeful"},
              "reveal2": {"chords": ["Am", "Dm7", "F", "Esus4"], "mood": "tension"},
              "payoff": {"chords": ["Cmaj7", "G6", "Am7", "Fmaj7"], "mood": "hopeful"}},
}

G = -3.2  # ground line


# ----------------------------------------------------------------------------- staging helpers
def S(T, i):
    return T[i][0]


def E(T, i):
    return T[i][1]


def cam(dur, x0, x1=None, w0=16.0, w1=None, y0=0.2, y1=None):
    return [{"t": 0.0, "x": x0, "y": y0, "width": w0},
            {"t": dur, "x": x1 if x1 is not None else x0 + 0.4, "y": y1 if y1 is not None else y0,
             "width": w1 if w1 is not None else w0 * 0.96, "ease": "in_out_cubic"}]


def who(cid, character, x=0.0, facing=1, actions=(), expr=(("happy", 0),), looks=(), end_x=None, z=0.0):
    d = {"id": cid, "character": character, "start_x": x, "facing": facing, "z": z,
         "actions": list(actions), "expressions": [{"at": t, "name": n} for n, t in expr],
         "looks": [{"at": t, "dx": dx, "dy": dy} for t, dx, dy in looks]}
    if end_x is not None:
        d["end_x"] = end_x
    return d


def pose(name, a, b, fade=0.3):
    return {"type": "pose", "name": name, "start": a, "end": b, "fade": fade}


def walk(a, b):
    return {"type": "walk", "start": a, "end": b}


def sit(a, b):
    return {"type": "sit", "start": a, "end": b, "fade": 0.01}


def tag(pid, label, color, x, y, t_in, t_out, dur, rot=6):
    return {"id": pid, "kind": "price_tag", "label": label, "color": color, "z": 0.9, "bob": 0.05,
            "keys": [{"t": 0, "x": x, "y": y, "s": 0.0, "rot": rot}, {"t": t_in, "s": 0.0, "y": y},
                     {"t": t_in + 0.35, "s": 1.0, "ease": "out_back"},
                     {"t": min(t_out, dur), "s": 1.0, "y": y + 0.4, "ease": "linear"},
                     {"t": min(t_out + 0.3, dur), "s": 0.0, "y": y + 0.5}]}


def badge(pid, label, x, y, t_in, t_out, dur, color="#2FA866", s=1.15):
    return {"id": pid, "kind": "badge", "label": label, "color": color, "z": 0.9,
            "keys": [{"t": 0, "x": x, "y": y, "s": 0.0}, {"t": t_in, "s": 0.0},
                     {"t": t_in + 0.35, "s": s, "ease": "out_back"}, {"t": min(t_out, dur), "s": s},
                     {"t": min(t_out + 0.3, dur), "s": 0.0}]}


def pop(t):
    return {"t": t, "kind": "pop", "gain": 0.8, "pan": 0.3}


def apartment(**kw):
    return {"kind": "apartment_night", "table_x": 1.0, "chair_x": -1.0, **kw}


def studio(**kw):
    return {"kind": "studio", **kw}


def manim(template, beats=None, **params):
    d = {"template": template, "params": params}
    if beats is not None:
        d["beats"] = beats
    return d


SRC_CENSUS = "U.S. Census Bureau, Income in the United States: 2025 (P60-289), Sept 2026"
SRC_REAL = "BLS Real Earnings news releases (all employees, real avg. hourly earnings, 12-mo change)"


# ----------------------------------------------------------------------------- scenes
SCENES = [
    # ===================================================================== HOOK 0:00-0:20
    SceneSpec("s01_record", "hook", [
        "In twenty twenty-five, the typical American household earned eighty-seven thousand, four hundred sixty dollars.",
        "According to the Census Bureau, that's a record, even after adjusting for inflation.",
    ], "manim", lambda T, d: manim("BigNumber", [S(T, 0) + 0.3, S(T, 1) + 0.6], value=87460, prefix="$",
                                   label="Typical U.S. household income, 2025",
                                   caption="Highest on record, after adjusting for inflation",
                                   source=SRC_CENSUS, chapter="A record year")),
    SceneSpec("s02_broke", "hook", [
        "So why does Maya, who got a raise that same year, feel like she's going broke?",
    ], "blender", lambda T, d: {
        "background": apartment(), "camera": cam(d, 0.2, 0.0, 15.0, 12.5, 0.4, 0.8),
        "characters": [who("maya", "maya", -0.85, actions=[sit(0, d), pose("worried_hands", 0.2, d)],
                           expr=(("worried", 0), ("sad", E(T, 0) - 0.4)), looks=((0, 0.6, -0.4),))],
        "props": [tag("t_rent", "RENT DUE", "#E0524A", 3.4, 2.4, S(T, 0) + 1.0, d, d)],
        "sfx": [pop(S(T, 0) + 1.0)]}),
    SceneSpec("s03_title", "hook", [], "manim",
              lambda T, d: manim("TitleCard", [0.1], kicker="LEDGER & LANTERN",
                                 lines=["Why Your Raise", "Feels Like a Pay Cut"]), min_dur=3.2),

    # ===================================================================== MYSTERY 0:20-1:00
    SceneSpec("s04_strange", "mystery", [
        "Here's the strange part.",
        "Officially, incomes hit a record. But by September twenty twenty-six, the average worker's hourly pay, "
        "after inflation, was lower than it had been a year earlier.",
    ], "blender", lambda T, d: {
        "background": {"kind": "city_dusk", "seed": 7, "furniture_offset": 3.0},
        "camera": cam(d, -6.5, -2.4, 16.0, 15.0),
        "characters": [who("maya", "maya", 0, actions=[walk(0, min(S(T, 1) + 1.5, d - 1)),
                                                       pose("think", S(T, 1) + 1.6, d)],
                           expr=(("neutral", 0), ("confused", S(T, 1) + 1.6)), end_x=-3.6,
                           looks=((0, 0.3, 0), (S(T, 1) + 1.6, 0.4, 0.5)))],
        "props": [badge("b_record", "RECORD INCOME", -0.8, 2.75, S(T, 1) + 0.2, S(T, 1) + 2.6, d),
                  badge("b_pay", "REAL PAY -0.7%", -0.1, 1.45, S(T, 1) + 3.2, d, d, color="#E0524A")],
        "sfx": [pop(S(T, 1) + 0.2), pop(S(T, 1) + 3.2)]}),
    SceneSpec("s05_realpay", "mystery", [
        "That's from the Bureau of Labor Statistics. Real pay means pay adjusted for inflation.",
        "Paychecks lost ground through twenty twenty-two, finally pulled ahead in twenty twenty-three, "
        "and now they're slipping again.",
    ], "manim", lambda T, d: manim(
        "Bars", [S(T, 1) + 0.2 + k * 0.55 for k in range(6)] + [E(T, 1) - 0.6],
        title="Real hourly pay vs. a year earlier",
        items=[{"label": "Jun 2022", "value": -3.6}, {"label": "Sep 2022", "value": -3.0},
               {"label": "Apr 2023", "value": -0.5}, {"label": "May 2023", "value": 0.2},
               {"label": "Mar 2026", "value": 0.3}, {"label": "Sep 2026", "value": -0.7}],
        note="Selected months  |  all private-sector employees", source=SRC_REAL, chapter="The paycheck paradox")),
    SceneSpec("s06_quote", "mystery", [
        "And people feel it. When Harvard economist Stefanie Stantcheva surveyed Americans about inflation,",
        "most said they believe their wages simply don't keep up with prices.",
    ], "manim", lambda T, d: manim("Quote", [0.3, S(T, 0) + 2.5],
                                   lines=["Most people believe their wages", "don't keep up with prices."],
                                   who="Stefanie Stantcheva, Harvard University",
                                   cite="\"Why Do We Dislike Inflation?\" Brookings Papers on Economic Activity, 2024")),
    SceneSpec("s07_question", "mystery", [
        "So which is it? Are we getting richer, or poorer?",
        "And if your raise is real, why does it feel like a pay cut?",
    ], "blender", lambda T, d: {
        "background": studio(), "camera": cam(d, 0.0, 0.3, 14.0, 12.0, 0.6, 0.9),
        "characters": [who("maya", "maya", -1.2, actions=[pose("shrug", 0.3, S(T, 1) + 0.2),
                                                          pose("head_scratch", S(T, 1) + 0.1, d)],
                           expr=(("confused", 0), ("worried", S(T, 1))), looks=((0, 0.6, 0.3),))],
        "props": [badge("b_q1", "RICHER?", 2.6, 2.4, S(T, 0) + 0.8, d, d, color="#2FA866"),
                  badge("b_q2", "POORER?", 3.3, 0.9, S(T, 0) + 1.5, d, d, color="#E0524A")],
        "sfx": [pop(S(T, 0) + 0.8), pop(S(T, 0) + 1.5)]}),

    # ===================================================================== CHARACTERS 1:00-2:00
    SceneSpec("s08_maya", "characters", [
        "Meet Maya. She's thirty, she rents a one-bedroom apartment in the city,",
        "and last year she got a five percent raise.",
    ], "blender", lambda T, d: {
        "background": {"kind": "city_dusk", "seed": 7, "furniture_offset": 3.0},
        "camera": cam(d, -7.5, -3.0, 16.0, 14.5),
        "characters": [who("maya", "maya", 0, actions=[walk(0, S(T, 1) + 0.3), pose("hold_up", S(T, 1) + 0.2, d)],
                           expr=(("happy", 0), ("excited", S(T, 1) + 0.5)), end_x=-4.3,
                           looks=((0, 0.3, 0), (S(T, 1), 0.5, -0.1)))],
        "props": [{"id": "paycheck", "kind": "paycheck",
                   "attach": {"character": "maya", "joint": "hand_f", "offset": [0.0, -0.16], "z": 0.004,
                              "upright": 6.0}},
                  badge("b_raise", "+5% RAISE", -1.9, 1.75, S(T, 1) + 0.9, d, d)],
        "sfx": [{"t": S(T, 1) + 0.9, "kind": "coin", "gain": 0.9}]}),
    SceneSpec("s09_dev", "characters", [
        "This is her older brother, Dev. Same family. Same city. Same five percent raise.",
        "The difference? Dev bought a house back in twenty twenty-one.",
    ], "blender", lambda T, d: {
        "background": studio(), "camera": cam(d, 0.0, 0.5, 14.5, 13.0, 0.5, 0.7),
        "characters": [who("dev", "dev", -6.5, actions=[walk(0, 2.4), pose("wave", 2.3, S(T, 1)),
                                                        pose("present", S(T, 1) + 0.2, d)],
                           expr=(("happy", 0),), end_x=-1.4, looks=((0, 0.4, 0),))],
        "props": [badge("b_dev", "+5% RAISE", 2.4, 2.9, S(T, 0) + 3.0, S(T, 1), d),
                  badge("b_house", "BOUGHT A HOME IN 2021", 3.4, 0.2, S(T, 1) + 1.2, d, d, color="#3E7C9B", s=0.9)],
        "sfx": [pop(S(T, 0) + 3.0), pop(S(T, 1) + 1.2)]}),
    SceneSpec("s10_maya_costs", "characters", [
        "When Maya's lease renewed, her rent went up.",
        "Filling her gas tank started costing a lot more. And her car insurance bill jumped.",
        "She's careful with money. She doesn't feel careless. She feels like she's running in place.",
    ], "blender", lambda T, d: {
        "background": apartment(), "camera": cam(d, 0.6, 0.9, 15.5, 13.5, 0.5, 0.7),
        "characters": [who("maya", "maya", -0.85, actions=[sit(0, d), pose("worried_hands", S(T, 2), d)],
                           expr=(("neutral", 0), ("worried", S(T, 0) + 1.0), ("sad", S(T, 2) + 1.0)),
                           looks=((0, 0.6, 0.4),))],
        "props": [tag("t_rent", "RENT", "#E0524A", 2.6, 2.6, S(T, 0) + 1.0, S(T, 2), d),
                  tag("t_gas", "GAS", "#E3A72F", 4.6, 1.3, S(T, 1) + 0.6, S(T, 2), d, rot=-6),
                  tag("t_ins", "INSURANCE", "#3E7C9B", 3.6, -0.1, S(T, 1) + 2.4, S(T, 2), d, rot=4)],
        "sfx": [pop(S(T, 0) + 1.0), pop(S(T, 1) + 0.6), pop(S(T, 1) + 2.4)]}),
    SceneSpec("s11_two", "characters", [
        "Dev, on the other hand, says he's doing fine.",
        "Two people. Same raise. Completely different realities.",
        "To understand why, we first need to look at what a raise really is.",
    ], "blender", lambda T, d: {
        "background": studio(), "camera": cam(d, 0.0, 0.0, 15.5, 13.0, 0.5, 0.6),
        "characters": [
            who("dev", "dev", -2.8, actions=[pose("hand_on_hip", 0.2, d)], expr=(("happy", 0),),
                looks=((0, 0.5, 0),)),
            who("maya", "maya", 2.6, facing=-1, actions=[pose("worried_hands", 0.2, S(T, 2)),
                                                          pose("think", S(T, 2), d)],
                expr=(("worried", 0), ("determined", S(T, 2) + 0.4)), looks=((0, 0.5, 0),))],
        "props": [badge("b_ok", "DOING FINE", -2.6, 3.05, S(T, 0) + 0.6, S(T, 2), d, color="#2FA866"),
                  badge("b_ri", "RUNNING IN PLACE", 2.4, 3.05, S(T, 1) + 1.0, S(T, 2), d, color="#E0524A")],
        "sfx": [pop(S(T, 0) + 0.6), pop(S(T, 1) + 1.0)]}),

    # ===================================================================== FIRST REVELATION 2:00-3:30
    SceneSpec("s12_unit", "reveal1", [
        "A raise is a number. But money isn't really measured in dollars.",
        "It's measured in what those dollars can buy.",
    ], "manim", lambda T, d: manim("TitleCard", [0.2], kicker="FIRST REVELATION",
                                   lines=["Money is measured", "in what it can buy"])),
    SceneSpec("s13_waterfall", "reveal1", [
        "Maya's five percent raise sounds great.",
        "But over the twelve months ending in September twenty twenty-six, consumer prices rose three point seven percent.",
        "Subtract that, and her real raise is about one point three percent.",
        "Most of her raise was spoken for before her first bigger paycheck ever arrived.",
    ], "manim", lambda T, d: manim(
        "Waterfall", [S(T, 0) + 0.2, S(T, 1) + 1.8, S(T, 2) + 0.8],
        title="Maya's raise, in real terms (illustrative)",
        bars=[{"label": "Pay raise", "value": 5.0, "text": "+5.0%"},
              {"label": "Price increases", "value": -3.7, "text": "-3.7%"},
              {"label": "Real raise", "value": 0, "text": "+1.3%", "kind": "total"}],
        source="BLS CPI-U, 12 months ending Sept 2026 (+3.7%). Maya's 5% raise is a hypothetical example.",
        chapter="Money illusion")),
    SceneSpec("s14_illusion", "reveal1", [
        "Economists have a name for why this catches us off guard. It's called money illusion.",
        "In a famous nineteen ninety-seven study, Eldar Shafir, Peter Diamond, and Amos Tversky showed that people "
        "tend to think in dollar amounts, even when inflation is quietly changing what those dollars are worth.",
    ], "manim", lambda T, d: manim("Quote", [0.3, S(T, 1) + 0.5],
                                   lines=["We tend to think in dollar amounts,", "not in what the dollars buy."],
                                   who="Shafir, Diamond & Tversky, \"Money Illusion\"",
                                   cite="Quarterly Journal of Economics 112(2), 1997 (paraphrased)")),
    SceneSpec("s15_basket", "reveal1", [
        "And there's a second trap. The inflation rate you hear on the news is an average across a huge basket of things.",
        "But your basket is personal. If you drive a lot, gas matters more to you than it does to the average.",
        "In the year to September twenty twenty-six, gasoline prices rose about thirty-four percent,",
        "while groceries rose less than two percent.",
    ], "blender", lambda T, d: {
        "background": {"kind": "grocery_aisle", "seed": 5}, "camera": cam(d, 0.0, 0.6, 15.5, 14.0, 0.4, 0.5),
        "characters": [who("maya", "maya", -6.0, actions=[walk(0, 2.6), pose("point", S(T, 1) + 0.2, S(T, 2) + 2.0),
                                                          pose("hands_up", S(T, 2) + 0.4, S(T, 3)),
                                                          pose("think", S(T, 3) + 0.2, d)],
                           expr=(("neutral", 0), ("confused", S(T, 1)), ("surprised", S(T, 2) + 0.4),
                                 ("neutral", S(T, 3) + 0.6)), end_x=-2.2, looks=((0, 0.4, 0), (S(T, 2), 0.6, 0.4)))],
        "props": [tag("t_g", "GAS +34%", "#E0524A", 2.4, 2.4, S(T, 2) + 0.3, d, d),
                  tag("t_f", "GROCERIES +1.8%", "#2FA866", 3.4, 0.6, S(T, 3) + 0.3, d, d, rot=-4)],
        "sfx": [pop(S(T, 2) + 0.3), pop(S(T, 3) + 0.3)]}),
    SceneSpec("s16_feel", "reveal1", [
        "So two people can live through the exact same inflation, and feel completely different amounts of pain.",
    ], "blender", lambda T, d: {
        "background": studio(), "camera": cam(d, 0.0, 0.0, 15.0, 13.5, 0.5, 0.6),
        "characters": [who("dev", "dev", -2.8, actions=[pose("hand_on_hip", 0.1, d)], expr=(("happy", 0),)),
                       who("maya", "maya", 2.6, facing=-1, actions=[pose("worried_hands", 0.1, d)],
                           expr=(("worried", 0),))]}),

    # ===================================================================== STAKES 3:30-5:00
    SceneSpec("s17_mortgage", "stakes", [
        "Now back to Dev. In January twenty twenty-one, the average thirty-year mortgage rate fell to two point six "
        "five percent, the lowest Freddie Mac had ever recorded.",
        "Dev locked in close to that low. Today, mortgage rates are above seven percent.",
        "On the same three hundred thousand dollar loan, that's the difference between about twelve hundred dollars "
        "a month, and about two thousand.",
        "More than eight hundred dollars, every single month.",
    ], "manim", lambda T, d: manim(
        "Compare", [S(T, 0) + 1.0, S(T, 1) + 1.5, S(T, 3)],
        title="Same $300,000 loan, 30-year fixed (illustrative)",
        sides=[{"value": "$1,209", "label": "at 2.65% (Jan 2021)", "sub": "principal + interest per month"},
               {"value": "$2,018", "label": "at 7.11% (Nov 2026)", "sub": "principal + interest per month",
                "color": "#E0524A"}],
        delta="+$809 a month", chapter="Locked in vs. exposed",
        source="Freddie Mac PMMS weekly rates (Jan 7, 2021; Nov 12, 2026). Payment math: standard amortization.")),
    SceneSpec("s18_exposed", "stakes", [
        "Dev's biggest cost was frozen in place the day he signed.",
        "Maya's biggest cost resets every time her lease does.",
        "Same raise. But one of them is protected from rising prices, and the other is exposed.",
    ], "blender", lambda T, d: {
        "background": studio(), "camera": cam(d, 0.0, 0.2, 15.5, 14.0, 0.5, 0.6),
        "characters": [who("dev", "dev", -3.0, actions=[pose("present", 0.3, S(T, 1))], expr=(("happy", 0),)),
                       who("maya", "maya", 2.4, facing=-1, actions=[pose("worried_hands", S(T, 1), d)],
                           expr=(("neutral", 0), ("worried", S(T, 1) + 0.3)))],
        "props": [badge("b_lock", "LOCKED IN", -2.8, 3.05, S(T, 0) + 0.8, d, d, color="#3E7C9B"),
                  badge("b_exp", "EXPOSED", 2.4, 3.05, S(T, 1) + 0.8, d, d, color="#E0524A")],
        "sfx": [pop(S(T, 0) + 0.8), pop(S(T, 1) + 0.8)]}),
    SceneSpec("s19_insurance", "stakes", [
        "And some costs exploded. Car insurance prices rose fourteen percent in twenty twenty-two,",
        "and another twenty percent in twenty twenty-three alone.",
        "They've cooled since, but those higher premiums didn't go back to where they were.",
    ], "manim", lambda T, d: manim(
        "Bars", [S(T, 0) + 0.2, S(T, 0) + 1.3, S(T, 1) + 0.3, S(T, 2) + 0.2, S(T, 2) + 0.8],
        title="Motor vehicle insurance prices, change over each year",
        items=[{"label": "2021", "value": 4.1, "color": "#E3A72F"}, {"label": "2022", "value": 14.2, "color": "#E0524A"},
               {"label": "2023", "value": 20.3, "color": "#E0524A"}, {"label": "2024", "value": 11.3, "color": "#E3A72F"},
               {"label": "2025", "value": 2.8, "color": "#E3A72F"}],
        source="BLS, Consumer Price Index: 2025 in review (December-to-December changes)")),
    SceneSpec("s20_cards", "stakes", [
        "When paychecks fall behind, a lot of people fill the gap with credit cards.",
        "Americans now owe a record one point two eight five trillion dollars on them,",
        "at interest rates that average more than twenty percent.",
    ], "manim", lambda T, d: manim(
        "BigNumber", [0.4, S(T, 2) + 0.2], value=1.285, prefix="$", suffix=" trillion", decimals=3,
        label="U.S. credit card balances, Q3 2026 (a record)", color="#E0524A",
        caption="Average card interest rate: above 20%",
        source="New York Fed Household Debt and Credit Report (Nov 2026); Federal Reserve G.19 (Nov 2026)")),

    SceneSpec("s20b_interest", "stakes", [
        "Here's what that means in real life.",
        "Carry a five thousand dollar balance at twenty percent, and you'll pay roughly a thousand dollars a year in "
        "interest alone.",
        "That's money that never shows up as a purchase. It just quietly eats the raise you worked for.",
    ], "manim", lambda T, d: manim(
        "BigNumber", [0.4, S(T, 2)], value=1000, prefix="~$", suffix=" a year",
        label="Interest on a $5,000 card balance at 20% APR (illustrative)", color="#E0524A",
        caption="Before a single dollar of the balance is paid off",
        source="Simple-interest approximation: $5,000 x 20%. Actual cost depends on compounding and payments.")),

    # ===================================================================== DEEPER 5:00-7:00
    SceneSpec("s21_mechanism", "deeper", [
        "Here's the mechanism most people never hear explained.",
        "When the news says inflation is cooling, it doesn't mean prices are falling. It means they're rising more slowly.",
        "The surge of twenty twenty-one and twenty twenty-two lifted prices to a new, higher level.",
        "And that level isn't coming back down. The gap stays.",
    ], "manim", lambda T, d: manim("PriceLevel", [S(T, 0) + 0.6, S(T, 2), S(T, 1) + 1.0, S(T, 3)],
                                   title="Falling inflation is not falling prices (concept)",
                                   chapter="Why prices never come back down")),
    SceneSpec("s21b_escalator", "deeper", [
        "Think of it like walking up a down escalator.",
        "Rising prices are the escalator, pulling you down. A raise is you walking faster.",
        "If the escalator speeds up, you have to walk faster just to stay on the same step.",
        "Real wage growth is the only question that matters. Are you actually climbing?",
    ], "blender", lambda T, d: {
        "background": studio(top="#E3E8F2"), "camera": cam(d, 0.0, 0.0, 15.0, 13.0, 0.5, 0.7),
        "characters": [who("maya", "maya", -3.0, actions=[walk(0.4, S(T, 2) + 1.5), pose("think", S(T, 3), d)],
                           expr=(("determined", 0), ("worried", S(T, 2)), ("determined", S(T, 3))), end_x=-0.2)],
        "props": [badge("e1", "PRICES", 2.8, 2.7, S(T, 1) + 0.3, d, d, color="#E0524A"),
                  badge("e2", "YOUR PAY", 2.8, 1.4, S(T, 1) + 2.0, d, d, color="#2FA866"),
                  badge("e3", "REAL PAY = THE CLIMB", 3.7, 0.0, S(T, 3) + 0.5, d, d, color="#3E7C9B", s=0.9)],
        "sfx": [pop(S(T, 1) + 0.3), pop(S(T, 1) + 2.0), pop(S(T, 3) + 0.5)]}),
    SceneSpec("s22_peak", "deeper", [
        "At its peak, in June twenty twenty-two, inflation hit nine point one percent,",
        "the fastest pace in about forty years.",
    ], "manim", lambda T, d: manim("BigNumber", [S(T, 0) + 0.3, S(T, 1)], value=9.1, suffix="%", decimals=1,
                                   label="Consumer price inflation, 12 months to June 2022", color="#E0524A",
                                   caption="The largest 12-month increase since 1981",
                                   source="BLS Consumer Price Index news release, July 13, 2022")),
    SceneSpec("s23_fed", "deeper", [
        "And here's the part that surprises people. The Federal Reserve actually aims for prices to keep rising,",
        "about two percent a year, by its preferred measure.",
        "A little inflation is considered healthy for the economy. But it means your pay has to grow every year, "
        "just to stand still.",
    ], "manim", lambda T, d: manim("BigNumber", [1.2, S(T, 2) + 0.5], value=2, suffix="% a year",
                                   label="The Federal Reserve's long-run inflation goal",
                                   caption="So prices are designed to rise, slowly, every year",
                                   source="FOMC Statement on Longer-Run Goals (adopted Jan 2012); measured with PCE prices")),
    SceneSpec("s24_daily", "deeper", [
        "There's a psychological side, too.",
        "You get a raise maybe once a year. But you see prices every single day, at the pump, at the checkout, "
        "on every renewal notice.",
        "Each one feels like a small, fresh loss. By then, the raise already feels like old news.",
    ], "blender", lambda T, d: {
        "background": {"kind": "city_dusk", "seed": 11, "furniture_offset": 1.0},
        "camera": cam(d, -5.5, -1.5, 16.0, 14.5),
        "characters": [who("maya", "maya", 0, actions=[walk(0, S(T, 1) + 2.0), pose("worried_hands", S(T, 2), d)],
                           expr=(("neutral", 0), ("worried", S(T, 1) + 1.0), ("sad", S(T, 2) + 0.6)), end_x=-2.6)],
        "props": [tag("d1", "PUMP", "#E0524A", -0.2, 2.6, S(T, 1) + 1.6, d, d),
                  tag("d2", "CHECKOUT", "#E3A72F", 1.6, 1.4, S(T, 1) + 2.4, d, d, rot=-5),
                  tag("d3", "RENEWAL", "#3E7C9B", 3.0, 0.2, S(T, 1) + 3.3, d, d, rot=5)],
        "sfx": [pop(S(T, 1) + 1.6), pop(S(T, 1) + 2.4), pop(S(T, 1) + 3.3)]}),
    SceneSpec("s25_stress", "deeper", [
        "Stantcheva's research found that people rarely see any upside to inflation,",
        "and many feel real stress about it, especially lower-income households.",
    ], "blender", lambda T, d: {
        "background": apartment(), "camera": cam(d, 0.2, 0.2, 14.5, 12.5, 0.6, 0.9),
        "characters": [who("maya", "maya", -0.85, actions=[sit(0, d), pose("head_scratch", 0.3, S(T, 1)),
                                                            pose("worried_hands", S(T, 1), d)],
                           expr=(("worried", 0), ("sad", S(T, 1) + 0.5)))]}),

    # ===================================================================== BIGGEST REVELATION 7:00-8:45
    SceneSpec("s26_both", "reveal2", [
        "So here's the biggest discovery.",
        "The record household income and the shrinking paycheck are both true, at the same time.",
    ], "blender", lambda T, d: {
        "background": studio(top="#F3E3C6"), "camera": cam(d, 0.0, 0.0, 15.0, 12.5, 0.5, 0.8),
        "characters": [who("maya", "maya", 0.0, actions=[pose("hands_up", S(T, 1) + 0.4, d)],
                           expr=(("neutral", 0), ("surprised", S(T, 1) + 0.4)))],
        "props": [badge("b_rec", "RECORD INCOME", -3.4, 2.4, S(T, 1) + 0.8, d, d),
                  badge("b_shr", "SHRINKING PAY", 3.4, 2.4, S(T, 1) + 2.4, d, d, color="#E0524A")],
        "sfx": [pop(S(T, 1) + 0.8), pop(S(T, 1) + 2.4)]}),
    SceneSpec("s27_median", "reveal2", [
        "That record is a median household income for a whole year. It counts everyone earning in the home.",
        "Real hourly pay is a different number, tracked month by month, for workers.",
        "And not everyone moved up. The Census found incomes near the bottom showed no significant change.",
    ], "manim", lambda T, d: manim(
        "Compare", [S(T, 0) + 0.5, S(T, 1) + 0.5, S(T, 2) + 1.0],
        title="Two true numbers, measuring different things",
        sides=[{"value": "+2.6%", "label": "Median household income, 2025", "sub": "yearly, whole household",
                "color": "#2FA866"},
               {"value": "-0.7%", "label": "Real hourly pay, Sept 2026", "sub": "vs. a year earlier, per worker",
                "color": "#E0524A"}],
        delta="Bottom 10% of households: no significant change", chapter="The biggest discovery",
        source="Census Bureau P60-289 (Sept 2026); BLS Real Earnings (Oct 2026)")),
    SceneSpec("s28_memory", "reveal2", [
        "But the deepest reason is this. What you feel isn't the inflation rate. It's today's prices, compared "
        "to the prices you remember.",
        "Maya remembers what rent used to cost. The official average doesn't erase that memory.",
        "And Dev? He doesn't feel it the same way, because he locked in his biggest cost before prices jumped.",
        "Feeling poorer isn't a math mistake. It's what happens when your costs move faster than your contracts.",
    ], "blender", lambda T, d: {
        "background": studio(), "camera": cam(d, 0.0, 0.3, 15.5, 13.5, 0.5, 0.6),
        "characters": [
            who("maya", "maya", 2.4, facing=-1, actions=[pose("think", 0.3, S(T, 2)), pose("shrug", S(T, 3), d)],
                expr=(("confused", 0), ("worried", S(T, 1)), ("determined", S(T, 3) + 0.5))),
            who("dev", "dev", -3.0, actions=[pose("hand_on_hip", S(T, 2), d)], expr=(("neutral", 0), ("happy", S(T, 2))))],
        "props": [tag("m1", "RENT THEN", "#3E7C9B", -0.2, 2.8, S(T, 1) + 0.6, S(T, 3), d),
                  tag("m2", "RENT NOW", "#E0524A", -0.3, 1.5, S(T, 1) + 1.6, S(T, 3), d, rot=-5)],
        "sfx": [pop(S(T, 1) + 0.6), pop(S(T, 1) + 1.6)]}),

    SceneSpec("s28b_timing", "reveal2", [
        "Notice that Dev's advantage wasn't skill. It was timing.",
        "And lock-in cuts both ways. If Dev wanted to move today, he'd have to borrow at today's rates, just like "
        "everyone else.",
        "That's the hidden story behind so many money arguments right now. People aren't living in the same economy. "
        "They're living in the economy of the year they signed.",
    ], "blender", lambda T, d: {
        "background": apartment(bills=False), "camera": cam(d, 0.0, 0.4, 15.5, 13.5, 0.5, 0.7),
        "characters": [who("dev", "dev", -2.6, actions=[pose("think", 0.3, S(T, 1)), pose("shrug", S(T, 1) + 0.5, d)],
                           expr=(("neutral", 0), ("confused", S(T, 1) + 0.5), ("determined", S(T, 2))),
                           looks=((0, 0.5, 0),))],
        "props": [badge("tm1", "SIGNED 2021", 2.2, 2.5, S(T, 2) + 2.0, d, d, color="#3E7C9B"),
                  badge("tm2", "SIGNING 2026", 3.0, 1.2, S(T, 2) + 3.0, d, d, color="#E0524A")],
        "sfx": [pop(S(T, 2) + 2.0), pop(S(T, 2) + 3.0)]}),

    # ===================================================================== PAYOFF 8:45-10:00
    SceneSpec("s29_answer", "payoff", [
        "So, did Maya's raise disappear? Not exactly. It was smaller than it looked, from the very start.",
        "She measured it in dollars. The world measured it in prices.",
    ], "blender", lambda T, d: {
        "background": apartment(), "camera": cam(d, 0.4, 0.6, 15.0, 13.0, 0.5, 0.7),
        "characters": [who("maya", "maya", -0.85, actions=[sit(0, d), pose("think", 0.2, S(T, 1)),
                                                            pose("point", S(T, 1) + 0.3, d)],
                           expr=(("neutral", 0), ("determined", S(T, 1))))]}),
    SceneSpec("s30_lessons", "payoff", [
        "If you want your next raise to actually feel like one, start here.",
        "One. Subtract inflation from every raise, so you know your real number.",
        "Two. Track your own top five costs, because your inflation isn't the national average.",
        "Three. When you ask for a raise, bring the inflation numbers with you.",
        "Four. Pay down high-interest debt first. A card charging twenty percent will outrun almost any raise.",
        "Five. When you lock in a big fixed cost, like a lease or a loan, timing matters as much as price.",
    ], "manim", lambda T, d: manim(
        "Checklist", [S(T, k) for k in range(1, 6)], title="Make your next raise real",
        items=["Subtract inflation from every raise", "Track your own top five costs",
               "Bring inflation data to your raise talk", "Pay off 20%+ interest debt first",
               "Time your big fixed costs"], chapter="How to make a raise real")),
    SceneSpec("s31_end", "payoff", [
        "Your paycheck is just a number. What really matters is what it can buy.",
        "So what's your real raise this year? Do the math, and tell us in the comments.",
        "This video is for education only, not financial advice. If it helped, subscribe for the next story.",
    ], "blender", lambda T, d: {
        "background": {"kind": "city_dusk", "seed": 7, "furniture_offset": 3.0},
        "camera": cam(d, -4.0, -0.5, 14.0, 16.0),
        "characters": [who("maya", "maya", 0, actions=[pose("wave", S(T, 1), S(T, 2)), walk(S(T, 2), d)],
                           expr=(("determined", 0), ("happy", S(T, 1))), end_x=-1.0),
                       who("dev", "dev", -3.0, actions=[pose("wave", S(T, 1) + 0.3, S(T, 2)), walk(S(T, 2) + 0.3, d)],
                           expr=(("happy", 0),), end_x=-4.2)]}),
]

EPISODE.update({
    "hook": "In 2025 the typical American household earned a record $87,460, even after inflation. So why do so "
            "many people with fresh raises feel like they're falling behind? We follow Maya and her brother Dev "
            "through the data on real wages, money illusion and locked-in costs.",
    "title_options": [
        "Why Your Raise Feels Like a Pay Cut (Even When It Isn't)",
        "Record Income, Shrinking Paychecks: The Raise Paradox Explained",
        "Why a 5% Raise Isn't Really 5%",
        "The Real Reason Your Raise Disappears Every Year",
        "Inflation Is \"Cooling.\" So Why Do You Feel Poorer?",
        "Same Raise, Completely Different Life: Why Timing Beats Income",
        "Why Prices Never Come Back Down (And What It Does to Your Paycheck)",
        "Money Illusion: The Mind Trick That Eats Your Raise",
        "Why Americans Earn More but Feel Broke",
        "How to Tell If Your Raise Is Actually a Raise",
    ],
    "tags": ["raise", "inflation", "real wages", "money illusion", "personal finance", "cost of living",
             "mortgage rates", "credit card debt", "economics explained", "animated documentary"],
})
