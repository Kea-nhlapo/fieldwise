// Read-only UI check against the real receipts already saved in the local app.
const assert=require('node:assert/strict');
const fs=require('node:fs');
let playwright;
try {playwright=require('playwright');}
catch {playwright=require('C:/Users/DellUser/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');}
(async()=>{
  const browser=await playwright.chromium.launch({headless:true,channel:'msedge'});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1050}});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.goto('http://127.0.0.1:8765/felix');
    await page.locator('#evidence-weather').filter({hasText:'Fetched · current cache'}).waitFor();
    await page.locator('#evidence-soil').filter({hasText:'16.6% clay'}).waitFor();
    assert.match(await page.locator('#evidence-weather').innerText(),/2026-10-17.*2026-10-19/s);
    assert.match(await page.locator('#evidence-weather').innerText(),/T00:14:44/);
    const link=await page.locator('#evidence-weather a').getAttribute('href');
    const receipt=await (await page.request.get('http://127.0.0.1:8765'+link)).json();
    assert.equal(receipt.http_status,200);
    assert.equal(JSON.parse(receipt.response_text).daily.precipitation_sum[0],.9);
    assert.match(await page.locator('#evidence-map').innerText(),/Latest attempt failed/);
    assert.match(await page.locator('#map-mode').innerText(),/BUNDLED/);
    fs.mkdirSync('artifacts',{recursive:true});
    await page.screenshot({path:'artifacts/live-evidence-desktop.png'});
    await page.setViewportSize({width:390,height:844});
    await page.locator('#evidence-flow').scrollIntoViewIfNeeded();
    await page.screenshot({path:'artifacts/live-evidence-mobile.png'});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    assert.deepEqual(errors,[]);
    console.log('PASS: actual saved weather/soil receipts, ISO timestamps, original response link and honest map failure/fallback are visible.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
