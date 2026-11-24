const { chromium } = require('playwright');
const path=require('path');
(async()=>{
  const dir=process.argv[2]; const times=process.argv.slice(3).map(Number);
  const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
  const p=await b.newPage({viewport:{width:1080,height:1920}});
  p.on('console',m=>{if(m.type()==='error')console.log('ERR',m.text())}); p.on('pageerror',e=>console.log('PAGEERR',e.message));
  await p.goto('http://localhost:8123/index.html'); await p.waitForFunction(()=>window.READY===true,null,{timeout:60000});
  for(const t of times){const s=Date.now(); await p.evaluate(t=>window.renderFrame(t),t); await p.screenshot({path:path.join(dir,`still_${t}.jpg`),quality:85,type:'jpeg'}); console.log(t,Date.now()-s,'ms');}
  await b.close();
})();
