const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
let playwright;
try { playwright = require('playwright'); }
catch { playwright = require('C:/Users/DellUser/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'); }
(async () => {
  const errors = [];
  const browser = await playwright.chromium.launch({headless:true, channel:'msedge'});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1100}});
    page.on('pageerror', e => errors.push(e.message));
    await page.goto('http://127.0.0.1:8765');
    await page.locator('.farm-row').first().waitFor();
    assert.equal(await page.locator('.farm-row').count(), 5);
    await page.locator('[data-farm="makhaya"]').click();
    const before = parseFloat(await page.locator('#depletion').innerText());
    await page.locator('[data-reply="2"]').click();
    await page.waitForFunction(() => document.querySelector('[data-reply="2"]').getAttribute('aria-pressed') === 'true');
    const after = parseFloat(await page.locator('#depletion').innerText());
    assert(after > before + 15, 'Interrupted irrigation must increase projected depletion');
    await page.locator('#draft').click();
    await page.locator('#draft-result').filter({hasText:'not sent'}).waitFor();
    await page.locator('#budget').selectOption('120');
    await page.locator('#plan').click();
    await page.locator('.route-summary').waitFor();
    assert((await page.locator('.route-summary').innerText()).includes('120 minutes'));
    await page.getByRole('button',{name:'Urgent',exact:true}).click();
    assert(await page.locator('.farm-row').count() > 0);
    await page.getByRole('button',{name:'All fields',exact:true}).click();
    fs.mkdirSync('artifacts',{recursive:true});
    await page.screenshot({path:'artifacts/fieldwise-desktop.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:'artifacts/fieldwise-mobile.png',fullPage:true});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile overflow');
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({browser:'Edge',farms:5,before_mm:before,after_mm:after,route:'passed',mobile:'passed',page_errors:errors}));
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
