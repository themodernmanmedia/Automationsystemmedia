# Finance Studio

Automated production of original 2D animated finance documentaries for YouTube:
Python orchestrates **Blender** (characters + environments), **Manim** (financial
charts) and **FFmpeg** (mix, assembly, export).

> Channel: **Cents Unseen** (@centsunseen), "The hidden side of money, animated."

## Quick start

```bash
sudo apt install blender ffmpeg xvfb espeak-ng libpango1.0-dev pkg-config   # Linux
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add ELEVENLABS_API_KEY + ELEVENLABS_VOICE_ID for the real narrator
python main.py doctor         # inspect the machine
python -m pytest              # automated tests
python main.py test-scene     # render the 15-second prototype scene
python -m characters.model_sheet maya   # character pose/expression sheet
python main.py --topic "Why Americans Are Getting Poorer Even When They Earn More"
```

## Status (honest)

| Phase | What | State |
|---|---|---|
| 1 | Config, logging, retries, cache, resumable pipeline, doctor, CLI, tests | **Built + tested** |
| 2 | Original character rig (Maya), expressions, mouths, poses, IK, foot-locked walk/run | **Built + tested** |
| 3 | Topic research, scripts, fact-checking, scene breakdown | Scene schema + validator built; research/script/fact-check **not built** |
| 4 | Voiceover + sync | ElevenLabs/espeak/file providers, line timing **built**; ElevenLabs path **untested** (no key in this environment); lip-sync from audio **not built** |
| 5 | Animation + graphics rendering | Blender renderer, city environment, props, Manim waterfall **built + used in the test** |
| 6 | Editing + export | Mixer (ducking, EBU R128), FFmpeg assembly, SRT, QC report **built + used in the test** |
| 7 | Thumbnails + publishing package | **Not built**. Publishing is hard-gated behind `python main.py approve` |
| 8 | Full episode | **Not started** |

`python main.py --topic ...` runs the 15-step pipeline and stops at the first
step that is not built yet, recording it as `not_implemented`. It never fakes output.

## Layout

```
main.py              CLI
config.yaml          all non-secret settings (env override: FINSTUDIO__SECTION__KEY)
core/                config, logging (secret scrubbing), retry, cache, pipeline state, doctor
animation/
  motion.py          pure-Python motion engine: poses, 2-bone IK, foot-locked gait, expressions, blinks
  scene_schema.py    scene JSON schema + validator (missing assets, timing errors)
  bake.py            scene -> per-frame channels; FK for props held in hands
  render.py          headless Blender driver (resumable, multi-process)
  prototype.py       the 15-second test scene, end to end
  blender/           code that runs inside Blender: drawing lib, rig, environments, props
characters/specs/    character model specs (proportions + palette = consistency)
graphics/charts.py   Manim charts (transparent overlays)
audio/               TTS providers, original procedural music/SFX, mixer + loudness
editing/             FFmpeg assembly, subtitles, QC
assets/fonts/        Inter (SIL OFL)
output/<episode>/    per-episode workspace + state.json
```

## Design rules enforced in code

* **Consistency:** characters are drawn from a spec; every scene uses the same rig.
* **Sync:** every animation beat is anchored to measured narration timings.
* **Regeneration:** scenes render independently; frames are cached by a hash of the
  scene *and* the Blender code, so only changed scenes re-render. Renders resume.
* **Honesty:** charts must carry a caption; illustrative numbers say so on screen.
  The draft espeak voice is flagged in QC as not publishable.
* **Licensing:** music and SFX are synthesized by this code; fonts are SIL OFL;
  narration must come from a commercially licensed TTS plan (ElevenLabs paid tier).
* **Secrets:** only in `.env` / environment; scrubbed from logs.
* **Publishing:** impossible without an explicit, typed human approval.
