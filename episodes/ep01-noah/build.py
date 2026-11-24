"""Ep.1 — Noah's Building Permit.
Trims the voice clips, builds the shot/event timeline (timeline.json) and mixes soundtrack.wav.
Run:  python3 build.py && node ../render.js .
"""
import array, json, math, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
A = lambda f: os.path.join(HERE, "audio", f)
FPS, SR, GAP = 30, 16000, 0.22

# id, who, mood, caption
SCRIPT = [
    ("01", "clerk", "bored",   "Next."),
    ("02", "noah",  "happy",   "Good morning! I need a building permit."),
    ("03", "clerk", "bored",   "For what?"),
    ("04", "noah",  "proud",   "A boat."),
    ("05", "clerk", "bored",   "How big?"),
    ("06", "noah",  "proud",   "Three hundred cubits long. Fifty wide. Thirty high!"),
    ("07", "clerk", "bored",   "Sir. That's 450 feet. You live in the desert."),
    ("08", "noah",  "happy",   "It's for the rain."),
    ("09", "clerk", "shocked", "...What's rain?"),
    ("10", "noah",  "patient", "Water. From the sky. Forty days and forty nights."),
    ("11", "clerk", "bored",   "Uh huh. And who's on board?"),
    ("12", "noah",  "happy",   "My family. And two of every animal."),
    ("13", "clerk", "annoyed", "Is that a giraffe in my lobby?"),
    ("14", "noah",  "happy",   "Two giraffes. They came as a pair."),
    ("15", "clerk", "firm",    "Denied. Come back when it rains."),
    ("16", "clerk", "nervous", "So... about that permit."),
    ("17", "noah",  "happy",   "Sorry, ma'am. Boarding's closed."),
]
SHOT_FOR = {"clerk": "clerkCU", "noah": "noahCU"}

def run(*a): subprocess.run(a, check=True)

def trim(src, dst):
    f = ("silenceremove=start_periods=1:start_threshold=-42dB:start_silence=0.05,areverse,"
         "silenceremove=start_periods=1:start_threshold=-42dB:start_silence=0.08,areverse")
    run("ffmpeg", "-y", "-v", "error", "-i", src, "-af", f, "-ar", "44100", "-ac", "2", dst)

def pcm(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return array.array("h", raw)

def envelope(s):
    hop = SR // FPS
    env = [math.sqrt(sum(x * x for x in s[i:i + hop]) / max(len(s[i:i + hop]), 1)) for i in range(0, len(s), hop)]
    pk = max(env) or 1
    return [round(max(0, (e / pk - 0.08) / 0.92), 3) for e in env]

def segment_starts(env, low=0.1, min_gap=5):
    starts, quiet = [], min_gap
    for i, v in enumerate(env):
        if v > low and quiet >= min_gap: starts.append(i / FPS)
        quiet = quiet + 1 if v <= low else 0
    return starts

os.makedirs(os.path.join(HERE, "trimmed"), exist_ok=True)
lines, shots, punches, shakes, ev, sfx = [], [], [], [], {}, []
def shot(id_, t0, **kw): shots.append({"id": id_, "t0": round(t0, 3), **kw})
def add_sfx(name, t, vol=1.0): sfx.append((name, round(t, 3), vol))

t = 0.0
shot("wide", 0, focus=[540, 1100])
ev["walkEnd"] = 2.0
for n, (cid, who, mood, text) in enumerate(SCRIPT):
    dst = os.path.join(HERE, "trimmed", cid + ".wav"); trim(A(cid + ".mp3"), dst)
    s = pcm(dst); dur = len(s) / SR; env = envelope(s)
    i = n + 1
    if i == 1: t = 0.5
    elif i == 9: t += 0.55                       # comedic beat before "What's rain?"
    elif i == 13:                                # lobby reveal pan before the giraffe line
        ev["lobby"] = round(t + 0.1, 3); shot("lobby", t + 0.1, t1=round(t + 2.4, 3), trans="whip")
        add_sfx("sfx_whoosh", t + 0.05, 0.5); ev["elephant"] = round(t + 1.3, 3); add_sfx("sfx_elephant", t + 1.3, 0.8)
        t += 2.5
    elif i == 16:                                # stamp insert, then the storm, then the ark
        st = t + 0.1; shot("stamp", st, focus=[540, 1100]); add_sfx("sfx_whoosh", st - 0.05, 0.5)
        ev["stamp"] = round(st + 0.4, 3); add_sfx("sfx_stamp", st + 0.4, 1.0)
        shakes.append({"t": ev["stamp"], "d": 0.35, "amt": 40}); punches.append({"t": ev["stamp"], "amt": 0.08})
        sm = st + 1.3; shot("storm", sm, focus=[540, 1000], trans="cut")
        ev["thunder"] = round(sm + 0.15, 3); add_sfx("sfx_thunder", sm + 0.15, 0.9)
        shakes.append({"t": ev["thunder"], "d": 0.7, "amt": 50})
        ak = sm + 3.4; shot("ark", ak, focus=[770, 1020]); add_sfx("sfx_whoosh", ak - 0.05, 0.5)
        t = ak + 0.5
    else: t += GAP
    t0 = t
    # shots for this line
    if i == 1: pass                               # still in the wide establishing shot
    elif i == 6:
        shot("blueprint", t0 - 0.15, focus=[540, 900]); add_sfx("sfx_unroll", t0 - 0.15, 0.7)
        segs = segment_starts(env); ev["bpDims"] = [round(t0 + x, 3) for x in (segs + [dur * .5, dur * .75])[:3]]
    elif i in (16, 17): pass                      # both in the ark shot
    else: shot(SHOT_FOR[who], t0 - 0.12, focus=[540, 900])
    if i in (4, 13): punches.append({"t": round(t0 + 0.05, 3), "amt": 0.12})
    if i == 9: punches.append({"t": round(t0 + 0.1, 3), "amt": 0.22})
    if i == 17: punches.append({"t": round(t0, 3), "amt": 0.3})
    if i in (2, 3, 4, 5, 7, 8, 10, 11, 12, 14, 15): add_sfx("sfx_whoosh", t0 - 0.14, 0.18)
    lines.append({"id": cid, "who": who, "mood": mood, "text": text, "t0": round(t0, 3), "t1": round(t0 + dur, 3), "env": env})
    t = t0 + dur

ev["shutter"] = round(t + 0.3, 3); add_sfx("sfx_stamp", t + 0.35, 0.6)
end_t = t + 1.2; shot("end", end_t, focus=[540, 960]); add_sfx("sfx_whoosh", end_t - 0.05, 0.5)
duration = round(end_t + 3.4, 2)

json.dump({"lines": lines, "shots": shots, "ev": ev, "punches": punches, "shakes": shakes, "duration": duration},
          open(os.path.join(HERE, "timeline.json"), "w"))

# ---------- mix ----------
inputs, fl, labels = [], [], []
def add(path, delay, vol, extra=""):
    k = len(inputs) // 2; inputs.extend(["-i", path]); ms = int(delay * 1000)
    fl.append(f"[{k}:a]aresample=44100,aformat=channel_layouts=stereo,{extra}volume={vol},adelay={ms}|{ms}[a{k}]")
    labels.append(f"[a{k}]")
for L in lines: add(os.path.join(HERE, "trimmed", L["id"] + ".wav"), L["t0"], 1.0)
for name, at, vol in sfx:
    extra = f"afade=t=out:st={duration - ev['thunder'] - 1.8}:d=1.5," if name == "sfx_thunder" else ""
    add(A(name + ".mp3"), at, vol, extra)
# music bed: low under dialogue, dips during the storm, fades at the end
mus_vol = (f"volume='if(between(t,{ev['thunder']},{shots[-1]['t0']}),0.05,0.13)':eval=frame,"
           f"afade=t=out:st={duration - 2}:d=2,")
add(A("music.mp3"), 0, 1.0, f"atrim=0:{duration},{mus_vol}")
fl.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest,atrim=0:{duration},"
          "alimiter=limit=0.9,loudnorm=I=-14:TP=-1.5[out]")
run("ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fl), "-map", "[out]", "-ar", "44100",
    os.path.join(HERE, "soundtrack.wav"))
print("duration", duration, "shots", len(shots))
