// Renders an episode folder (scene.html + timeline.json + soundtrack.wav) to <folder>/episode.mp4.
// Usage: node episodes/render.js episodes/ep01-noah [--preview]   (--preview = half-res, 15fps quick check)
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs'), path = require('path'), os = require('os');

const dir = path.resolve(process.argv[2] || '.');
const preview = process.argv.includes('--preview');
const WORKERS = Math.max(1, Math.min(6, os.cpus().length));
const frames = fs.mkdtempSync(path.join(os.tmpdir(), 'ep-frames-'));
const timeline = JSON.parse(fs.readFileSync(path.join(dir, 'timeline.json'), 'utf8'));

(async () => {
  const browser = await chromium.launch();
  const probe = await browser.newPage();
  await probe.addInitScript(tl => { window.TIMELINE = tl; }, timeline);
  await probe.goto('file://' + path.join(dir, 'scene.html'));
  const { DURATION, FPS } = await probe.evaluate(() => ({ DURATION: window.DURATION, FPS: window.FPS }));
  await probe.close();
  const fps = preview ? 15 : FPS, total = Math.round(DURATION * fps);
  let next = 0, done = 0;
  async function worker() {
    const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
    await page.addInitScript(tl => { window.TIMELINE = tl; }, timeline);
    await page.goto('file://' + path.join(dir, 'scene.html'));
    while (next < total) {
      const i = next++;
      const b64 = await page.evaluate(([t, small]) => {
        window.renderFrame(t);
        let cv = document.getElementById('c');
        if (small) { const s = document.createElement('canvas'); s.width = 540; s.height = 960; s.getContext('2d').drawImage(cv, 0, 0, 540, 960); cv = s; }
        return cv.toDataURL('image/jpeg', 0.92).split(',')[1];
      }, [i / fps, preview]);
      fs.writeFileSync(path.join(frames, `f${String(i).padStart(5, '0')}.jpg`), Buffer.from(b64, 'base64'));
      if (++done % 300 === 0) console.log(`${done}/${total}`);
    }
  }
  await Promise.all(Array.from({ length: WORKERS }, worker));
  await browser.close();
  const out = path.join(dir, preview ? 'preview.mp4' : 'episode.mp4');
  execFileSync('ffmpeg', ['-y', '-v', 'error', '-framerate', String(fps), '-i', path.join(frames, 'f%05d.jpg'),
    '-i', path.join(dir, 'soundtrack.wav'), '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'medium',
    '-crf', preview ? '26' : '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-shortest',
    '-movflags', '+faststart', out]);
  fs.rmSync(frames, { recursive: true });
  console.log('wrote', out, total, 'frames');
})();
