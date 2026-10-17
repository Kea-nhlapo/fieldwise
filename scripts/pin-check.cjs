// Officer PIN flow in a real browser. Run against a server started with a PIN (2468 here):
//   node scripts/pin-check.cjs http://127.0.0.1:8769
const assert = require('node:assert/strict');
let playwright;
try {playwright=require('playwright');}
catch {playwright=require('C:/Users/DellUser/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');}
const BASE = process.argv[2] || 'http://127.0.0.1:8769';
const PIN = process.argv[3] || '2468';

(async()=>{
  const browser = await playwright.chromium.launch({headless:true, channel:'msedge'});
  const report = {};
  try {
    const context = await browser.newContext({viewport:{width:1440,height:900}});
    const page = await context.newPage();
    const errors = []; page.on('pageerror', e=>errors.push(e.message));
    await page.goto(BASE + '/felix');
    const dialog = page.locator('#fw-signin');
    await dialog.waitFor({state:'visible'});
    report.dialogShown = true;

    // Accessibility of the dialog itself.
    await page.addScriptTag({url:'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js'});
    report.axe = await page.evaluate(async()=>(await axe.run('#fw-signin', {runOnly:{type:'tag', values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(v=>v.id));
    assert.deepEqual(report.axe, []);
    assert.equal(await page.evaluate(()=>document.activeElement.id), 'fw-pin', 'focus starts in the PIN field');

    await page.fill('#fw-pin', '0000');
    await page.click('#fw-signin button[type=submit]');
    await page.locator('.signin-error').filter({hasText:'not right'}).waitFor();
    report.wrongPin = await page.locator('.signin-error').innerText();

    await page.fill('#fw-pin', PIN);
    await page.click('#fw-signin button[type=submit]');
    await dialog.waitFor({state:'hidden'});
    await page.locator('[data-farm]').first().waitFor();
    report.farmsLoaded = await page.locator('[data-farm]').count();

    await page.locator('[data-farm="F014"]').click();
    await page.locator('#visit-notes').fill('Checked after signing in');
    await page.locator('#save-visit').click();
    await page.locator('#feedback').filter({hasText:'Visit recorded'}).waitFor();
    report.visitSaved = true;

    // Signed out with an action waiting in the outbox: it stays queued until the officer signs in.
    await context.setOffline(true);
    await page.locator('[data-farm="F027"]').click();
    await page.locator('#visit-notes').fill('Captured offline');
    await page.locator('#save-visit').click();
    await page.locator('#feedback').filter({hasText:'Saved on this device'}).waitFor();
    await context.clearCookies();             // session ends while the device is offline
    await context.setOffline(false);
    await page.evaluate(()=>window.dispatchEvent(new Event('online')));
    await page.locator('.connection').filter({hasText:'Sign in with the officer PIN'}).waitFor();
    assert.equal(await page.evaluate(()=>Fieldwise.pending()), 1, 'refused action stays in the outbox');
    await page.locator('.connection button').click();
    await page.fill('#fw-pin', PIN);
    await page.click('#fw-signin button[type=submit]');
    await page.waitForFunction(()=>Fieldwise.pending()===0, null, {timeout:15000});
    report.outboxSyncedAfterSignIn = true;
    report.pageErrors = errors;
    assert.deepEqual(errors, []);
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error); process.exit(1);});
