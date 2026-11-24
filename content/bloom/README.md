# Bloom: mental-health explainer character

Bloom is an original 3D cartoon character: a soft, round, mint figure with a sprout on its head.
The sprout is the brand's visual metaphor. It **droops when Bloom is overwhelmed** and **grows a flower when Bloom feels better**.
Pip is a small peach-colored friend character, used for "reach out" moments.

Episode 1: **Feeling Overwhelmed** (about 80s, 1080x1920 vertical, for Reels, TikTok and Shorts)

| Time | Beat |
| --- | --- |
| 0–10s | Hook: Bloom says hi, and worry boxes (Work, Bills, Emails...) pile up |
| 10–23s | Name the feeling ("overload, not weakness") |
| 23–35s | Step 1: Breathe (in 4, hold 4, out 6) |
| 35–44s | Step 2: Write it down (brain dump onto a notepad, and the worries shrink) |
| 44–53s | Step 3: One tiny step (pick one, check it off, the sprout regrows) |
| 53–59s | Step 4: Reach out (Pip arrives) |
| 59–67s | When to get professional help (doctor/counselor; 988 in the US) |
| 67–80s | Recap checklist, then the flower blooms on the end card |

## How it's built
- `index.html`: the three.js scene, characters, timeline, captions and overlays. `window.renderFrame(t)` is deterministic.
- `data.js`: word timings (for karaoke captions) and the voice amplitude envelope (for lip sync).
- `render.js`: renders frames with Playwright. `stills.js` renders preview stills.
- Voice: ElevenLabs (voice "Yasmin", eleven_v4). Music and SFX are synthesized.

Render (needs `three@0.170.0` in `node_modules` next to `index.html`, served on port 8123):
```
npx http-server -p 8123 .   # in this folder
node render.js frames 0 2400
ffmpeg -framerate 30 -i frames/f%05d.jpg -i voice.mp3 -i music.wav ... bloom.mp4
```
