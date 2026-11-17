"""Post-production for Ep. 02: mixes narration + synthesized music/SFX, burns in
word-synced captions and fact labels, and encodes the final 1080x1920 Short.

    python3 build.py FRAMES_DIR OUT.mp4
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import wave

import numpy as np
import soundfile as sf
from PIL import ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES, OUT = sys.argv[1], sys.argv[2]
FPS, NFRAMES = 30, 885
DUR = NFRAMES / FPS
SR = 44100
FONT = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
CUTS = [50, 80, 218, 378, 578, 718]  # frame of each camera cut

timing = json.load(open(os.path.join(HERE, "timing.json")))

# --------------------------------------------------------------------- audio
voice, vsr = sf.read(os.path.join(HERE, "narration.wav"))
voice = np.interp(np.arange(int(len(voice) * SR / vsr)) * vsr / SR, np.arange(len(voice)), voice)
n = int(DUR * SR)
t = np.arange(n) / SR
rng = np.random.default_rng(5)
sfx = np.zeros(n)


def place(sig, at, gain=1.0):
    i = int(at * SR)
    j = min(n, i + len(sig))
    if 0 <= i < n:
        sfx[i:j] += gain * sig[: j - i]


def env(length, a=0.005, d=0.2):
    x = np.arange(int(length * SR)) / SR
    return np.minimum(1, x / a) * np.exp(-x / d)


def lowpass(sig, k):
    return np.convolve(sig, np.ones(k) / k, "same")


def noise(length):
    return rng.standard_normal(int(length * SR))


def sine(f, length):
    return np.sin(2 * np.pi * f * np.arange(int(length * SR)) / SR)


# music: low suspense pad (minor chord drones) + soft heartbeat pulse
music = np.zeros(n)
chords = [(55.0, 65.4, 82.4), (49.0, 58.3, 73.4), (43.65, 55.0, 65.4), (49.0, 61.7, 73.4)]
seg = 4.0
for k in range(int(DUR / seg) + 1):
    a, b = k * seg, min(DUR, (k + 1) * seg + 0.5)
    i0, i1 = int(a * SR), int(b * SR)
    tt = np.arange(i1 - i0) / SR
    fade = np.minimum(1, np.minimum(tt / 0.4, (tt[-1] - tt) / 0.4 + 1e-9))
    for f in chords[k % 4]:
        for det in (1.0, 2.0, 1.003):
            music[i0:i1] += 0.05 * np.sin(2 * np.pi * f * det * tt) * fade
beat = 0.0
while beat < DUR:
    if beat < 18.9 or beat > 19.4:
        for off, g in ((0, 1.0), (0.18, 0.6)):
            i = int((beat + off) * SR)
            hb = sine(50, 0.25) * env(0.25, 0.003, 0.07)
            music[i:i + len(hb)] += 0.35 * g * hb[: max(0, min(len(hb), n - i))]
    beat += 0.85 if beat < 19 else 0.7
# happy lift at the end
for i, f in enumerate((523.3, 659.3, 784.0, 1046.5)):
    place(sine(f, 1.2) * env(1.2, 0.01, 0.5), 27.9 + i * 0.12, 0.08)

# SFX
for st in np.arange(0.1, 0.75, 0.3):                    # footsteps on dry sand
    place(lowpass(noise(0.12), 6) * env(0.12, 0.002, 0.03), st, 0.35)
for st in (0.75, 1.05, 1.4, 1.8):                       # squelch into the pit
    place(lowpass(noise(0.3), 40) * env(0.3, 0.01, 0.1), st, 0.9)
place(lowpass(noise(1.5), 80) * env(1.5, 0.05, 0.6), 3.3, 0.9)   # long sinking glug
for c in CUTS:                                          # whoosh on each cut
    w = lowpass(noise(0.35), 12)
    place(w * np.sin(np.pi * np.arange(len(w)) / len(w)), c / FPS - 0.15, 0.45)
place(sine(880, 0.15) * env(0.15, 0.002, 0.05), 16.4, 0.3)       # car pop
place(lowpass(noise(0.08), 3) * env(0.08, 0.001, 0.02), 16.4, 0.6)
for st in np.arange(19.8, 23.5, 0.23):                  # bubbles while wiggling
    f = rng.uniform(300, 700)
    x = np.arange(int(0.07 * SR)) / SR
    place(np.sin(2 * np.pi * (f + 3000 * x) * x) * env(0.07, 0.002, 0.02), st + rng.uniform(0, 0.1), 0.18)
for st in (5.0,):                                       # rewind zip
    x = np.arange(int(0.8 * SR)) / SR
    place(np.sign(np.sin(2 * np.pi * (200 + 1800 * x) * x)) * 0.3 * (1 - x / 0.8), st, 0.25)

mix = sfx + music
v = np.zeros(n)
v[: min(n, len(voice))] = voice[:n]
# duck music/SFX under the narration
duck = np.convolve((np.abs(v) > 0.02).astype(float), np.ones(int(0.25 * SR)) / int(0.25 * SR), "same")
mix = mix * (1 - 0.45 * np.clip(duck * 3, 0, 1)) + v * 1.6
mix = np.tanh(mix * 1.1) * 0.9
mix[-int(0.4 * SR):] *= np.linspace(1, 0, int(0.4 * SR))

tmp = tempfile.mkdtemp()
wav = os.path.join(tmp, "mix.wav")
with wave.open(wav, "w") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype(np.int16).tobytes())

# ------------------------------------------------------------------ captions
def chunks(line, start, end, max_words=3):
    """Split a narration line into short word groups, timed by character count."""
    words = line.split()
    groups, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) == max_words or re.search(r"[.,!?]$", w):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    weights = [sum(len(w) + 1 for w in g) + (4 if re.search(r"[.,!?]$", g[-1]) else 0) for g in groups]
    total = sum(weights)
    out, t0 = [], start
    for g, wt in zip(groups, weights):
        t1 = t0 + (end - start) * wt / total
        out.append((t0, t1, " ".join(g).upper().rstrip(".,")))
        t0 = t1
    return out


def fit(text, size, max_w=940):
    w = ImageFont.truetype(FONT, 100).getlength(text) / 100
    return min(size, int(max_w / w))


idx = [0]


def dt(text, a, b, y, size, color, border=12, pop=True):
    idx[0] += 1
    path = os.path.join(tmp, f"c{idx[0]}.txt")
    open(path, "w").write(text)
    size = fit(text, size)
    fs = f"'{size}*min(1,0.7+(t-{a:.3f})*6)'" if pop else str(size)
    return (f"drawtext=fontfile={FONT}:textfile={path}:fontsize={fs}:fontcolor={color}"
            f":borderw={border}:bordercolor=black:shadowx=0:shadowy=6:shadowcolor=black@0.5"
            f":x=(w-tw)/2:y={y}-th/2:enable='between(t,{a:.3f},{b:.3f})'")


filters = ["scale=1080:1920:flags=lanczos",
           # movie-myth section: warm, desaturated "film" look
           "colorchannelmixer=.55:.35:.1:0:.3:.5:.2:0:.25:.3:.45:0:enable='between(t,2.68,5.0)'",
           "vignette=PI/4:enable='between(t,2.68,5.0)'"]
for line in timing:
    for a, b, text in chunks(line["line"], line["start"], line["end"]):
        filters.append(dt(text, a, b, 1360, 96, "white"))

LABELS = [  # (start, end, text, color)
    (2.7, 5.0, "MOVIE MYTH", "#FF4040"),
    (8.4, 12.4, "2X DENSER THAN YOU", "#FFD21F"),
    (13.0, 16.3, "STUCK", "#FF4040"),
    (16.45, 19.1, "= LIFTING A CAR", "#FFD21F"),
    (19.4, 23.8, "WIGGLE YOUR LEGS", "#5CD3FF"),
    (24.0, 29.5, "LEAN BACK AND FLOAT", "#7CFF8A"),
]
for a, b, text, color in LABELS:
    filters.append(dt(text, a, b, 300, 104, color, border=14))

fg = os.path.join(tmp, "filters.txt")
open(fg, "w").write("[0:v]" + ",".join(filters) + "[v]")
subprocess.run([
    "ffmpeg", "-y", "-loglevel", "error",
    "-framerate", str(FPS), "-i", os.path.join(FRAMES, "f_%04d.png"), "-i", wav,
    "-filter_complex_script", fg, "-map", "[v]", "-map", "1:a",
    "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT,
], check=True)
print("wrote", OUT)
