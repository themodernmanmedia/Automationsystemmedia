"""Post-production for Episode 01: synthesises the sound design, burns in the
captions and encodes the final 1080x1920 Short.

    python3 build.py FRAMES_DIR OUT.mp4

Everything here is generated from scratch (no third-party audio or footage), so
the Short is free of copyright claims.
"""
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np

FRAMES, OUT = sys.argv[1], sys.argv[2]
FPS = 30
DUR = 630 / FPS  # 21.0 s
SR = 44100
FONT = "/usr/share/fonts/opentype/inter/Inter-Black.otf"

# Story beats, in seconds (mirror the frame numbers in scene.py).
SHRINKS = [75, 165, 255, 345]  # frame each shrink starts
FALLS = [84, 172, 176, 262, 412]  # Red, Orange, Yellow, Purple, Green
WIN = 450 / FPS
PAUSE = (13.0, 15.0)  # music drops out while Green makes their move

# ----------------------------------------------------------------- sound design
t = np.arange(int(SR * DUR)) / SR
mix = np.zeros_like(t)


def place(sig, at, gain=1.0):
    i = int(at * SR)
    j = min(len(mix), i + len(sig))
    if i < len(mix):
        mix[i:j] += gain * sig[: j - i]


def env(n, attack=0.005, decay=0.2):
    x = np.arange(n) / SR
    return np.minimum(1, x / attack) * np.exp(-x / decay)


def kick():
    n = int(0.35 * SR)
    x = np.arange(n) / SR
    f = 120 * np.exp(-x * 25) + 45
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.12)


def hat():
    n = int(0.06 * SR)
    noise = np.random.default_rng(1).standard_normal(n)
    noise = np.diff(noise, prepend=0)  # crude high-pass
    return noise * env(n, 0.001, 0.015) * 0.5


def tone(freq, length, decay=0.15, shape="square"):
    n = int(length * SR)
    x = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * x)
    if shape == "square":
        s = np.sign(s) * 0.5
    return s * env(n, 0.002, decay)


def sweep(f0, f1, length, gain=1.0):
    n = int(length * SR)
    x = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (x / length)
    return gain * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, x / 0.01) * (1 - x / length)


def whoosh(length=0.45):
    n = int(length * SR)
    rng = np.random.default_rng(3)
    s = rng.standard_normal(n)
    k = np.ones(40) / 40
    s = np.convolve(s, k, "same")
    x = np.arange(n) / SR
    return s * np.sin(np.pi * x / length) * 1.6


# 1. beat: 128 bpm kick + off-beat hats + bass, silent during the pause
beat = 60 / 128
b = 0.0
while b < DUR - 0.3:
    if not (PAUSE[0] <= b < PAUSE[1]):
        place(kick(), b, 0.9)
        place(hat(), b + beat / 2, 0.35)
        bass_note = [55, 55, 65.4, 49][int(b / (beat * 4)) % 4]
        place(tone(bass_note, beat * 0.9, 0.25, "sine"), b, 0.35)
    b += beat
# riser into the reveal
place(sweep(200, 1600, 2.0, 0.12), PAUSE[0])

# 2. warning beeps before each shrink (match the rim flashes) + shrink whoosh
for s in SHRINKS:
    for i in range(3):
        place(tone(988, 0.09, 0.05), (s - 24 + i * 8) / FPS, 0.25)
    place(whoosh(), s / FPS, 0.5)
    place(sweep(300, 90, 0.4, 0.5), s / FPS)

# 3. a falling slide-whistle per elimination, then a splash/thud
for f in FALLS:
    place(sweep(1400, 220, 0.75, 0.3), f / FPS)
    place(kick(), f / FPS + 0.8, 0.7)
    place(whoosh(0.3), f / FPS + 0.8, 0.4)

# 4. win: "ka-ching" + major arpeggio
place(tone(2093, 0.25, 0.1, "sine"), WIN, 0.4)
place(tone(2637, 0.35, 0.15, "sine"), WIN + 0.06, 0.4)
for i, fr in enumerate([523, 659, 784, 1047, 1319]):
    place(tone(fr, 0.6, 0.3), WIN + 0.15 + i * 0.09, 0.18)

# fade the last half-second so the loop restart isn't a click
fade = int(0.5 * SR)
mix[-fade:] *= np.linspace(1, 0, fade)
mix = np.tanh(mix * 1.2) * 0.85  # gentle limiter

tmp = tempfile.mkdtemp()
wav = os.path.join(tmp, "audio.wav")
with wave.open(wav, "w") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix * 32767).astype(np.int16).tobytes())

# --------------------------------------------------------------------- captions
# (start, end, text, y, size, color). Coordinates are for the 1080x1920 output.
CAPTIONS = [
    (0.0, 2.6, "LAST ONE IN THE CIRCLE", 260, 92, "white"),
    (0.0, 2.6, "WINS $1,000,000", 370, 118, "#FFD21F"),
    (2.6, 5.4, "IT SHRINKS EVERY 3 SECONDS", 300, 70, "white"),
    (2.95, 4.6, "RED IS OUT!", 1150, 120, "#FF3B3B"),
    (5.8, 8.4, "ORANGE AND YELLOW", 300, 84, "white"),
    (5.8, 8.4, "WERE TOO SLOW", 400, 84, "white"),
    (8.75, 10.8, "PURPLE THOUGHT", 300, 90, "#B57BFF"),
    (8.75, 10.8, "THEY WERE SAFE...", 405, 90, "white"),
    (11.0, 12.9, "FINAL 2. ONE SPOT LEFT.", 300, 80, "white"),
    (13.0, 13.75, "GREEN HAS A PLAN...", 300, 88, "#3BE36B"),
    (13.75, 15.0, "...BAD PLAN", 300, 110, "#FF3B3B"),
    (15.0, 18.6, "BLUE WINS", 260, 130, "#4C8DFF"),
    (15.0, 18.6, "$1,000,000!", 390, 130, "#FFD21F"),
    (18.6, 21.0, "WHO WOULD YOU", 260, 100, "white"),
    (18.6, 21.0, "HAVE BET ON?", 370, 100, "#FFD21F"),
]
# players-left counter, top-right
COUNTER = [(2.6, 2.95, "6 LEFT"), (2.95, 5.85, "5 LEFT"), (5.85, 8.8, "3 LEFT"),
           (8.8, 13.8, "2 LEFT"), (13.8, 15.0, "1 LEFT")]

filters = ["scale=1080:1920:flags=lanczos", "eq=saturation=1.12:contrast=1.04"]


def fit(text, size, max_w=930):
    """Shrink the font size until the line fits inside the safe width."""
    from PIL import ImageFont
    w = ImageFont.truetype(FONT, 100).getlength(text) / 100
    return min(size, int(max_w / w))


def dt(text, a, b, x, y, size, color, pop=True, idx=[0]):
    idx[0] += 1
    size = fit(text, size)
    path = os.path.join(tmp, f"c{idx[0]}.txt")
    with open(path, "w") as fh:
        fh.write(text)
    fs = f"'{size}*min(1,0.55+(t-{a})*5)'" if pop else str(size)
    return (f"drawtext=fontfile={FONT}:textfile={path}:fontsize={fs}:fontcolor={color}"
            f":borderw=10:bordercolor=black:shadowx=0:shadowy=8:shadowcolor=black@0.6"
            f":x={x}:y={y}-th/2:enable='between(t,{a},{b})'")


for a, b, text, y, size, color in CAPTIONS:
    filters.append(dt(text, a, b, "(w-tw)/2", y, size, color))
for a, b, text in COUNTER:
    filters.append(dt(text, a, b, "w-tw-50", 130, 58, "white", pop=False))

fg = os.path.join(tmp, "filters.txt")
with open(fg, "w") as fh:
    fh.write("[0:v]" + ",".join(filters) + "[v]")

cmd = [
    "ffmpeg", "-y", "-loglevel", "error",
    "-framerate", str(FPS), "-i", os.path.join(FRAMES, "f_%04d.png"),
    "-i", wav,
    "-filter_complex_script", fg, "-map", "[v]", "-map", "1:a",
    "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT,
]
subprocess.run(cmd, check=True)
print("wrote", OUT)
