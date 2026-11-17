# Ep. 01: "Last One In The Circle Wins $1,000,000"

An original 3D animated challenge Short (21 s, 1080×1920, 30 fps), built
entirely in code with Blender (`scene.py`) and ffmpeg (`build.py`). The
characters, music and sound effects are all made from scratch, so there is
nothing to get a copyright claim on.

## How the big challenge-Shorts format works

I did **not** download or rip anyone's video. That breaks YouTube's Terms of
Service, and the footage is copyrighted. These are the patterns that show up
again and again in top challenge Shorts, plus the principles in MrBeast's
widely circulated production memo:

| Technique | What it means | Where it is in Ep. 01 |
| --- | --- | --- |
| **Stakes in frame 1** | Show the prize and the rule within the first second, with no intro and no logo | 0:00: tight on the cash, caption "LAST ONE IN THE CIRCLE WINS $1,000,000" |
| **One-sentence premise** | A viewer should be able to explain the video in one line | The title *is* the rules |
| **A beat every 2–3 s** | Something changes constantly: a cut, a reveal, someone eliminated | A shrink every 3 s, an elimination on each one |
| **Visible progress** | A counter or countdown so viewers know where they are | "6 LEFT → 1 LEFT" counter, top right |
| **Escalation** | Each beat is bigger or tenser than the last | 1 out → 2 out → "thought they were safe" → final 2 |
| **A twist before the payoff** | Break the pattern right before the end | Green tries to shove Blue and falls off instead |
| **Music drops for tension** | Silence before the big moment makes the payoff hit harder | The beat cuts out at 0:13 and a riser plays into the win |
| **Big captions, few words** | Most people watch muted; 3–5 words per card, high contrast | Black-stroke Inter Black captions, at most 5 words |
| **Payoff = emotion** | Celebrate the win visually | Cash rain plus Blue's victory jumps |
| **Loop ending** | The last frame flows back into the first, so replays count | The camera ends on the same cash close-up it opens on |
| **Comment bait** | End on a question | "WHO WOULD YOU HAVE BET ON?" |

## Beat sheet

| Time | Frames | Beat |
| --- | --- | --- |
| 0:00–0:02.5 | 0–75 | Hook: cash close-up, then the camera snaps back to reveal 6 players over lava |
| 0:02.5 | 75 | The rim flashes red three times, the circle shrinks, Red falls |
| 0:05.5 | 165 | Shrink 2: Orange and Yellow fall |
| 0:08.5 | 255 | Shrink 3: Purple "thought they were safe" |
| 0:11.5 | 345 | Shrink 4: final 2, room for one |
| 0:13–0:15 | 390–450 | Music drops. Green charges, Blue hops aside, Green falls |
| 0:15–0:18.6 | 450–560 | Blue wins: cash rain and celebration |
| 0:18.6–0:21 | 560–629 | Question card, camera returns to the cash (loop) |

## Rebuild it

```bash
pip install bpy            # Blender 5.x as a Python module
python3 scene.py --out frames/ --res 540 --samples 10   # ~1.5 h on 4 CPU cores
python3 build.py frames/ ep01.mp4
```

Use `--res 1080 --samples 32` for a sharper final render if you have a GPU or more
time. Use `--still N` to preview a single frame and `--blend ep01.blend` to open
the scene in the Blender app.

## Before posting

- Add a real voiceover (hype narrator) and a licensed or YouTube Audio Library
  track if you want more energy than the synthesized beat.
- Upload title: **Last One In The Circle Wins $1,000,000**
- Pin a comment: "Who should be in Episode 2?"
