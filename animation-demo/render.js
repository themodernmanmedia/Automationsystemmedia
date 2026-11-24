// Renders scene.html frame-by-frame with headless Chromium, then encodes an MP4 with ffmpeg.
// Usage: python3 build_audio.py && node render.js [out.mp4]
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs'), path = require('path');

const FPS = 25;
const out = process.argv[2] || path.join(__dirname, 'demo.mp4');
const framesDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'frames-'));

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 720, height: 1280 } });
  const timeline = JSON.parse(fs.readFileSync(path.join(__dirname, 'timeline.json'), 'utf8'));
  await page.addInitScript(tl => { window.TIMELINE = tl; }, timeline);
  await page.goto('file://' + path.join(__dirname, 'scene.html'));
  const duration = await page.evaluate(() => window.DURATION);
  const total = Math.round(duration * FPS);
  for (let i = 0; i < total; i++) {
    await page.evaluate(t => window.renderFrame(t), i / FPS);
    const b64 = await page.evaluate(() => document.getElementById('c').toDataURL('image/png').split(',')[1]);
    fs.writeFileSync(path.join(framesDir, `f${String(i).padStart(5, '0')}.png`), Buffer.from(b64, 'base64'));
  }
  await browser.close();
  execFileSync('ffmpeg', ['-y', '-v', 'error', '-framerate', String(FPS), '-i', path.join(framesDir, 'f%05d.png'),
    '-i', path.join(__dirname, 'soundtrack.wav'), '-c:a', 'aac', '-b:a', '192k', '-shortest',
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', out]);
  fs.rmSync(framesDir, { recursive: true });
  console.log('wrote', out, total, 'frames');
})();
