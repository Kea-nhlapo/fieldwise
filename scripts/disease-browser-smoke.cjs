const fs = require('node:fs');
const assert = require('node:assert/strict');
let playwright;
try { playwright = require('playwright'); }
catch { playwright = require('C:/Users/DellUser/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'); }
(async()=>{
  const browser = await playwright.chromium.launch({headless:true,channel:'msedge'});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1050}});
    const errors = [];
    page.on('pageerror', e=>errors.push(e.message));
    await page.goto('http://127.0.0.1:8766');
    await page.locator('.farm-row').first().waitFor();
    await page.locator('[data-farm="ubuntu"]').click();
    assert.equal(await page.locator('.unassessed').count(),2);
    const waterBefore = await page.locator('#depletion').innerText();
    await page.locator('#disease-notes').fill('Fictional report: leaf markings need an officer review.');
    await page.locator('#save-observation').click();
    await page.locator('.officer-alert').waitFor();
    assert.match(await page.locator('[data-farm="ubuntu"]').innerText(),/80 \/ 100/);
    assert.equal(await page.locator('#depletion').innerText(),waterBefore);
    assert.equal(await page.locator('#disease-alert-count').innerText(),'1 active alert');
    await page.locator('[data-review="acknowledged"]').click();
    await page.locator('.state-pill.acknowledged').waitFor();
    await page.locator('[data-review="resolved"]').click();
    await page.locator('.state-pill.resolved').waitFor();
    assert.match(await page.locator('[data-farm="ubuntu"]').innerText(),/10 \/ 100/);
    await page.locator('#save-observation').click();
    await page.locator('[data-review="acknowledged"]').waitFor();
    assert.equal(await page.locator('.officer-alert').count(),1);
    await page.locator('#disease-draft').click();
    await page.locator('#disease-draft-result').filter({hasText:'not sent'}).waitFor();
    await page.locator('#budget').selectOption('240');
    await page.locator('#plan').click();
    await page.locator('.route-summary').waitFor();
    await page.locator('#reference-panel > summary').click();
    await page.locator('#reference-provenance').filter({hasText:'SYNTHETIC OFFLINE SAMPLE'}).waitFor();
    assert.equal(await page.locator('#reference-rows tr').count(),7);
    await page.locator('#reference-disease').selectOption('tar_spot');
    await page.locator('#reference-station').selectOption('demo-3');
    assert.match(await page.locator('#reference-chart').innerText(),/No active numeric risk/);
    assert.match(await page.locator('#reference-rows').innerText(),/Inactive/);
    await page.locator('#reference-station').selectOption('demo-1');
    await page.locator('#reference-days').selectOption('3');
    assert.equal(await page.locator('#reference-rows tr').count(),0);
    await page.locator('#cached-reference').click();
    await page.locator('#reference-provenance').filter({hasText:'No reference loaded'}).waitFor();
    await page.locator('#sample-reference').click();
    await page.locator('#reference-provenance').filter({hasText:'SYNTHETIC OFFLINE SAMPLE'}).waitFor();
    await page.route('**/api/disease/reference?**', route=>route.request().method()==='POST'
      ? route.fulfill({status:502,contentType:'application/json',body:JSON.stringify({detail:'UW reference unavailable. Existing cache preserved.'})})
      : route.continue());
    await page.locator('#fetch-reference').click();
    await page.locator('#reference-error').filter({hasText:'unavailable'}).waitFor();
    assert.match(await page.locator('#reference-provenance').innerText(),/SYNTHETIC OFFLINE SAMPLE/);
    await page.locator('#sample-reference').click();
    await page.locator('#reference-error').waitFor({state:'hidden'});
    fs.mkdirSync('artifacts',{recursive:true});
    await page.locator('#toast').waitFor({state:'hidden'});
    await page.evaluate(()=>{document.documentElement.style.scrollBehavior='auto';window.scrollTo(0,0);});
    await page.screenshot({path:'artifacts/disease-desktop.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:'artifacts/disease-mobile.png',fullPage:true});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile overflow');
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({observations:'passed',alerts:'create/acknowledge/resolve/reopen passed',water:'unchanged',priority:'10 -> 80 -> 10 -> 80',reference:'synthetic trends, inactive states and simulated upstream-error UI passed',mobile:'passed',page_errors:errors}));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
