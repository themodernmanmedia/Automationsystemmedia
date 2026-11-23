const { chromium } = require('playwright');
const [a, b] = process.argv.slice(2).map(Number);
(async () => {
  const br = await chromium.launch({ args: ['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'] });
  const p = await br.newPage({ viewport: { width: 1280, height: 720 } });
  p.on('pageerror', e => console.log('ERR', e.message));
  await p.goto('http://localhost:8765/index.html');
  await p.waitForFunction('window.READY', null, { timeout: 180000 });
  for (let f = a; f < b; f++) {
    await p.evaluate(t => renderAt(t), f / 30);
    await p.screenshot({ path: `frames/f${String(f).padStart(5,'0')}.jpg`, type: 'jpeg', quality: 92 });
    if (f % 100 === 0) console.log('frame', f);
  }
  await br.close(); console.log('DONE', a, b);
})();
