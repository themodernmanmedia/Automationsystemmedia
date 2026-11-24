const { chromium } = require('playwright');
(async()=>{
  const [dir,start,end]=[process.argv[2],+process.argv[3],+process.argv[4]];
  const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
  const p=await b.newPage({viewport:{width:1080,height:1920}});
  p.on('pageerror',e=>console.log('PAGEERR',e.message));
  await p.goto('http://localhost:8123/index.html'); await p.waitForFunction(()=>window.READY===true,null,{timeout:60000});
  for(let f=start;f<end;f++){ await p.evaluate(t=>window.renderFrame(t),f/30);
    await p.screenshot({path:`${dir}/f${String(f).padStart(5,'0')}.jpg`,type:'jpeg',quality:93}); }
  await b.close(); console.log('done',start,end);
})();
