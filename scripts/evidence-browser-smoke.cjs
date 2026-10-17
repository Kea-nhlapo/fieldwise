const assert = require('node:assert/strict');
const fs = require('node:fs');
let playwright;
try {playwright=require('playwright');}
catch {playwright=require('C:/Users/DellUser/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');}
(async()=>{
  const browser=await playwright.chromium.launch({headless:true,channel:'msedge'});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.goto('http://127.0.0.1:8766/felix');
    await page.locator('[data-farm="F014"]').click();
    await page.locator('#evidence-flow').waitFor({timeout:5000});
    assert.match(await page.locator('#evidence-weather').innerText(),/Bundled/);
    assert.match(await page.locator('#evidence-soil').innerText(),/Missing/);
    assert.match(await page.locator('#privacy-summary').innerText(),/personal information/);
    // Provider failure fixture is clearly only a browser resilience test.
    await page.route('**/api/felix/farms/F014/evidence/weather',route=>route.fulfill({
      status:502,contentType:'application/json',body:JSON.stringify({receipt:{success:false,error:'Test provider unavailable'}})
    }));
    await page.locator('[data-fetch="weather"]').click();
    await page.locator('#feedback').filter({hasText:'Test provider unavailable'}).waitFor();
    assert.match(await page.locator('#evidence-weather').innerText(),/Bundled/);
    await page.locator('#queue-survey').click();
    await page.locator('#survey-invitation').filter({hasText:'LOCAL DRAFT'}).waitFor();
    assert.match(await page.locator('#survey-invitation').innerText(),/wilting/);
    await page.locator('#start-checkin').click();
    assert.equal(await page.getByRole('button',{name:'1. Yes',exact:true}).count(),0,'Must require consent first');
    await page.locator('#survey-consent').check();
    await page.locator('#start-checkin').click();
    await page.getByRole('button',{name:'1. Yes',exact:true}).click();
    await page.getByRole('button',{name:'1. One area',exact:true}).click();
    await page.locator('#survey-impact').filter({hasText:'+55'}).waitFor();
    assert.match(await page.locator('#survey-impact').innerText(),/62.*117/s);
    await page.reload();
    await page.locator('[data-farm="F014"]').click();
    await page.locator('#survey-impact').filter({hasText:'+55'}).waitFor();
    const exported=await page.request.get('http://127.0.0.1:8766/api/felix/farms/F014/privacy-export');
    assert.equal((await exported.json()).surveys.at(-1).notice_version,'fieldwise-demo-v1');
    await page.locator('#privacy-details').evaluate(el=>el.open=true);
    page.once('dialog',dialog=>dialog.accept());
    await page.locator('#erase-reports').click();
    await page.locator('#feedback').filter({hasText:'reports deleted'}).waitFor();
    assert.match(await page.locator('#last-report').innerText(),/No farmer check-in/);
    fs.mkdirSync('artifacts',{recursive:true});
    await page.evaluate(()=>window.scrollTo(0,0));
    await page.screenshot({path:'artifacts/evidence-desktop.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:'artifacts/evidence-mobile.png',fullPage:true});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile overflow');
    assert.deepEqual(errors,[]);
    console.log('PASS: evidence states, failed retrieval, privacy notice, targeted survey, consent, before/after, persistence, export, scoped deletion and responsive layout.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
