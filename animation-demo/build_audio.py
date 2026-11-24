"""Lay the voice clips on a timeline, measure their loudness per video frame
(this drives the mouths), and mix the final soundtrack.

Writes timeline.json (read by scene.html) and soundtrack.wav.
"""
import array, json, math, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
FPS, SR = 25, 16000
GAP, START = 0.35, 0.4  # pause between lines, lead-in

LINES = [
    ("clerk", "1_clerk.mp3", "next"),
    ("guy",   "2_guy.mp3",   "hi, I just got abducted"),
    ("clerk", "3_clerk.mp3", "did you fill out form 7B"),
    ("guy",   "4_guy.mp3",   "I was asleep"),
    ("clerk", "5_clerk.mp3", "take a number"),
]

def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return array.array("h", raw)

def envelope(samples):
    hop = SR // FPS
    env = []
    for i in range(0, len(samples), hop):
        chunk = samples[i:i + hop]
        env.append(math.sqrt(sum(s * s for s in chunk) / max(len(chunk), 1)))
    peak = max(env) or 1
    # gate quiet frames so the mouth closes between words
    return [round(max(0.0, (e / peak - 0.08) / 0.92), 3) for e in env]

timeline, t = [], START
for who, f, text in LINES:
    s = decode(os.path.join(HERE, "audio", f))
    dur = len(s) / SR
    timeline.append({"who": who, "file": f, "text": text, "t0": round(t, 3),
                     "t1": round(t + dur, 3), "env": envelope(s)})
    t += dur + GAP

ding_at = timeline[-1]["t1"] + 0.3          # number board flips after "take a number"
wide = {"who": "wide", "t0": round(ding_at, 3), "t1": round(ding_at + 2.6, 3), "text": "", "env": []}
timeline.append(wide)
duration = round(wide["t1"], 2)

json.dump({"lines": timeline, "duration": duration, "ding": round(ding_at, 3)},
          open(os.path.join(HERE, "timeline.json"), "w"))

# ---- mix: voices + soft room tone + "ding" ----
inputs, filters = [], []
for i, L in enumerate(timeline[:-1]):
    inputs += ["-i", os.path.join(HERE, "audio", L["file"])]
    ms = int(L["t0"] * 1000)
    filters.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{i}]")
n = len(timeline) - 1
# room tone: quiet brown noise with low hum
inputs += ["-f", "lavfi", "-i", f"anoisesrc=color=brown:amplitude=0.02:d={duration}:r=44100"]
filters.append(f"[{n}:a]lowpass=f=400,aformat=channel_layouts=stereo[room]")
# ding: two sine tones with decay
inputs += ["-f", "lavfi", "-i", "sine=f=1318:d=1.2:r=44100", "-f", "lavfi", "-i", "sine=f=1046:d=1.2:r=44100"]
dms = int(ding_at * 1000)
filters.append(f"[{n+1}:a][{n+2}:a]amix=inputs=2,afade=t=out:st=0.05:d=1.1,volume=0.5,"
               f"aformat=channel_layouts=stereo,adelay={dms}|{dms}[ding]")
mix_in = "".join(f"[v{i}]" for i in range(n)) + "[room][ding]"
filters.append(f"{mix_in}amix=inputs={n+2}:normalize=0:duration=longest,"
               f"atrim=0:{duration},loudnorm=I=-14:TP=-1.5[out]")
subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters),
                "-map", "[out]", "-ar", "44100", os.path.join(HERE, "soundtrack.wav")], check=True)
print("duration", duration, "ding", ding_at)
