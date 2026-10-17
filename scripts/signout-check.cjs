// Signing out must lock this device's saved farm records, online or offline.
// Run against a server started with a PIN (2468 here):
//   node scripts/signout-check.cjs http://127.0.0.1:8769
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
    page.on('dialog', d=>{ report.lastDialog = d.message(); d.accept(); });
    const records = () => page.evaluate(async()=>{ const r = await fetch('/api/felix/dashboard'); const b = await r.json().catch(()=>({})); return {status: r.status, farms: (b.farms || []).length}; });
    const signIn = async () => { await page.locator('#fw-signin').waitFor({state:'visible'}); await page.fill('#fw-pin', PIN); await page.click('#fw-signin button[type=submit]'); await page.locator('#fw-signin').waitFor({state:'hidden'}); };

    // Signed in, with the service worker in control and records cached.
    await page.goto(BASE + '/felix');
    await signIn();
    await page.locator('[data-farm]').first().waitFor();
    await page.evaluate(()=>navigator.serviceWorker.ready);
    await page.reload();
    await page.waitForFunction(()=>!!navigator.serviceWorker.controller);
    await page.locator('[data-farm]').first().waitFor();
    assert.equal((await records()).farms, 8);

    // A. The reviewer's steps: sign out through the API, confirm 401, then go offline.
    await page.evaluate(()=>fetch('/api/session', {method: 'DELETE'}));
    report.afterApiSignOut = await records();
    assert.equal(report.afterApiSignOut.status, 401);
    await context.setOffline(true);
    report.offlineAfterApiSignOut = await records();
    assert.equal(report.offlineAfterApiSignOut.farms, 0, 'cached records must not be readable after sign-out');
    await context.setOffline(false);

    // B. The Sign out button, used offline with an unsynced visit in the outbox.
    await page.reload();
    await signIn();
    await page.locator('[data-farm="F014"]').waitFor();
    await page.locator('[data-sign-out]').waitFor({state:'visible'});
    await context.setOffline(true);
    await page.locator('[data-farm="F014"]').click();
    await page.locator('#visit-notes').fill('Private note captured offline');
    await page.locator('#save-visit').click();
    await page.locator('#feedback').filter({hasText:'Saved on this device'}).waitFor();
    assert.equal(await page.evaluate(()=>Fieldwise.pending()), 1);
    await Promise.all([page.waitForEvent('load'), page.locator('[data-sign-out]').click()]);
    report.signOutWarning = report.lastDialog;
    assert.match(report.signOutWarning, /not reached the server/);
    report.outboxAfterSignOut = await page.evaluate(()=>{ try { return JSON.parse(localStorage.getItem('fieldwise-outbox-v1') || '[]').length; } catch { return -1; } });
    assert.equal(report.outboxAfterSignOut, 0);
    report.offlineAfterButtonSignOut = await records();
    assert.equal(report.offlineAfterButtonSignOut.farms, 0);
    report.pendingServerSignOut = await page.evaluate(()=>localStorage.getItem('fieldwise-signout-pending'));
    assert.equal(report.pendingServerSignOut, '1', 'offline sign-out is remembered for the server');

    // C. Back online: the server session ends before any records are requested.
    await context.setOffline(false);
    await page.evaluate(()=>window.dispatchEvent(new Event('online')));
    await page.waitForFunction(async()=>!(await (await fetch('/api/session')).json()).signed_in, null, {timeout:10000});
    report.serverSessionEnded = true;
    assert.equal(await page.evaluate(()=>localStorage.getItem('fieldwise-signout-pending')), null);
    report.pageErrors = errors;
    assert.deepEqual(errors, []);
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error); process.exit(1);});
