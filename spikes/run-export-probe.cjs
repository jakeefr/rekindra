// Developer-only browser automation, not a production engine dependency.
const { chromium } = require(process.env.REKINDRA_PLAYWRIGHT_PATH || 'playwright');
const path = require('node:path');
const fs = require('node:fs');
const { pathToFileURL } = require('node:url');
(async()=>{
  const output=path.resolve(__dirname,'../.local/browser-evidence');
  fs.mkdirSync(output,{recursive:true});
  const context=await chromium.launchPersistentContext(path.join(output,'profile'),{channel:'chrome',headless:true,viewport:{width:1000,height:850}});
  try {
    const page=await context.newPage();
    await page.goto(pathToFileURL(path.join(__dirname,'export.html')).href);
    const result=await page.evaluate(()=>runProbe());
    fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2));
    await page.screenshot({path:path.join(output,'probe.png'),fullPage:true});
    console.log(JSON.stringify(result,null,2));
    if(!result.codecs.some(c=>c.supported&&!c.error&&c.chunks===120&&c.bytes>0)) throw new Error('No codec passed 120-frame encoding');
  } finally {await context.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
