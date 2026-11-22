# Everyday Beast — Python 2D animation studio

A code-only pipeline for a MrBeast-style **everyday-life animation channel**:
ordinary situations turned into big questions, challenges and experiments,
acted out by 2D animated characters, narrated, scored and captioned —
rendered straight to an upload-ready YouTube package.

Episode 1: **"What Happens If You Ignore Everyone for 30 Days?"** (~5½ min)

## What it makes

`output/<episode>/`

| File | What |
| --- | --- |
| `<episode>.mp4` | 1920×1080, 30 fps, H.264 + AAC |
| `thumbnail.png` | 1280×720 thumbnail |
| `description.txt` | YouTube description with auto chapters + research sources |
| `metadata.json` | title, alternate titles, tags, chapters, duration |
| `captions.srt` | subtitles for upload |
| `script.txt` | timestamped script |

## How it works

| Module | Role |
| --- | --- |
| `everyday/rig.py` | Procedural character rig (cairo vectors): 13 expressions, ~20 arm poses, blinking, gaze, walk cycles, sitting, tears/sweat, held props, lip sync. Plus a dog. |
| `everyday/sets.py` | Backgrounds: kitchen, bedroom (day/night), office, street with parallax, park, grandma's kitchen, hallway door, phone UI. |
| `everyday/graphics.py` | Explainer graphics: brain, bar charts, stat cards, rule cards, icons, title slams. |
| `everyday/tts.py` | Local neural voices via Kokoro (ONNX, no API key). Per-character voice casting; speech energy drives mouth animation. |
| `everyday/audio.py` | Fully synthesised music beds (8 moods) and SFX (whoosh, boom, ding, riser…), voice ducking, mastering. No licensing or Content ID risk. |
| `everyday/overlays.py` | Word-by-word pop captions, DAY x/30 counter, whip/pop/flash transitions. |
| `everyday/timeline.py` | Script → timeline. Line audio sets shot length; animations key off line/word timings. |
| `everyday/render.py` | Multiprocess frame render → ffmpeg segments → concat → mux; metadata writers. |
| `everyday/episodes/*.py` | An episode = cast + voices + list of `Shot`s (lines + draw function) + META + thumbnail. |

## Run

```bash
pip install -r requirements.txt     # plus ffmpeg on PATH
python make_video.py --contact-sheet        # one still per shot, check the look (seconds)
python make_video.py --preview              # 960x540 quick render
python make_video.py                        # final 1080p render
python make_video.py --from 240 --to 300    # render a slice
```

The Kokoro model (~350 MB) downloads into `models/` on first run.

## Making the next episode

Copy `everyday/episodes/ignore_everyone_30_days.py`, write new `Shot`s,
and register the slug in `everyday/episodes/__init__.py`. Formula that works:

1. **Hook** (0–10 s): the question + the stakes + a promised twist.
2. **Rules / setup**: make it a challenge with a counter (DAY x/30).
3. **Escalation** every 20–40 s: a new day, a new character, a new reaction.
4. **Real science** in short, visual bites (with sources in the description).
5. **Funny beat** before the turn (the dog didn't file a report).
6. **Emotional twist** and payoff.
7. **Takeaway + tiny real-world challenge + next-episode tease.**

Stories are dramatized; keep the research claims accurate and cite them.
