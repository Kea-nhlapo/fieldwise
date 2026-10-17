// Signing out must lock this device's saved farm records: online or offline, from any page and in
// every tab. Run against a server started with a PIN (2468 here):
//   node scripts/signout-check.cjs http://127.0.0.1:8769
const assert = require('node:assert/strict');
let playwright;
try {playwright=require('playwright');}
catch {playwright=require('C:/Users/DellUser/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');}
const BASE = process.argv[2] || 'http://127.0.0.1:8769';
const PIN = process.argv[3] || '2468';
const RECORDS = '**/api/felix/dashboard';

// Reads the dashboard the way a page would: with this device's officer token, if it still has one.
const records = page => page.evaluate(async () => {
  const token = localStorage.getItem('fieldwise-officer-token');
  const r = await fetch('/api/felix/dashboard', {headers: token ? {'X-Officer-Token': token} : {}});
  const body = await r.json().catch(() => ({}));
  return {status: r.status, farms: (body.farms || []).length};
});
const cachedRecordEntries = page => page.evaluate(async () => {
  let n = 0;
  for (const name of await caches.keys()) for (const req of await (await caches.open(name)).keys()) if (new URL(req.url).pathname === '/api/felix/dashboard') n++;
  return n;
});
async function signIn(page) {
  await page.locator('#fw-signin').waitFor({state: 'visible'});
  await page.fill('#fw-pin', PIN);
  await page.click('#fw-signin button[type=submit]');
  await page.locator('#fw-signin').waitFor({state: 'hidden'});
}
async function signedInWithCache(context) {
  const page = await context.newPage();
  page.on('dialog', d => d.accept());
  await page.goto(BASE + '/felix');
  await signIn(page);
  await page.locator('[data-farm]').first().waitFor();
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload();
  await page.waitForFunction(() => !!navigator.serviceWorker.controller);
  await page.locator('[data-farm]').first().waitFor();
  assert.equal((await records(page)).farms, 8);
  return page;
}

(async () => {
  const browser = await playwright.chromium.launch({headless: true, channel: 'msedge'});
  const report = {};
  const errors = [];
  const fresh = async () => { const c = await browser.newContext({viewport: {width: 1280, height: 860}}); c.on('page', p => p.on('pageerror', e => errors.push(e.message))); return c; };
  try {
    // A. Sign out through the API, confirm 401, go offline: no records.
    {
      const context = await fresh();
      const page = await signedInWithCache(context);
      await page.evaluate(() => fetch('/api/session', {method: 'DELETE'}));
      report.A_afterApiSignOut = await records(page);
      assert.equal(report.A_afterApiSignOut.status, 401);
      await context.setOffline(true);
      report.A_offline = await records(page);
      assert.equal(report.A_offline.farms, 0);
      await context.close();
    }

    // B + C. Button sign-out offline with an unsynced visit; reconnecting ends the server session.
    {
      const context = await fresh();
      const page = await signedInWithCache(context);
      let warning = null;
      page.removeAllListeners('dialog');
      page.on('dialog', d => { warning = d.message(); d.accept(); });
      await context.setOffline(true);
      await page.locator('[data-farm="F014"]').click();
      await page.locator('#visit-notes').fill('Private note captured offline');
      await page.locator('#save-visit').click();
      await page.locator('#feedback').filter({hasText: 'Saved on this device'}).waitFor();
      await Promise.all([page.waitForEvent('load'), page.locator('[data-sign-out]').click()]);
      report.B_warning = warning;
      assert.match(warning, /not reached the server/);
      assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('fieldwise-outbox-v1') || '[]').length), 0);
      report.B_offline = await records(page);
      assert.equal(report.B_offline.farms, 0);
      assert.equal(await page.evaluate(() => localStorage.getItem('fieldwise-signout-pending')), '1');
      await context.setOffline(false);
      await page.evaluate(() => window.dispatchEvent(new Event('online')));
      await page.waitForFunction(() => localStorage.getItem('fieldwise-signout-pending') === null, null, {timeout: 10000});
      report.C_serverSessionEnded = true;
      await context.close();
    }

    // D. Review finding 1: a records response that was in flight during sign-out must not come back.
    {
      const context = await fresh();
      const page = await signedInWithCache(context);
      let release, holding = false;
      const gate = new Promise(r => { release = r; });
      let held = false;
      await context.route(RECORDS, async route => { if (holding) { held = true; await gate; } await route.continue(); });
      holding = true;
      const delayed = page.evaluate(() => {
        const token = localStorage.getItem('fieldwise-officer-token');
        return fetch('/api/felix/dashboard', {headers: {'X-Officer-Token': token}}).then(r => r.status).catch(() => 'aborted');
      }).catch(() => 'page reloaded');   // the page navigates away during sign-out
      await page.waitForTimeout(400);                       // request is now waiting at the gate
      const reloaded = page.waitForEvent('load');
      await page.evaluate(() => Fieldwise.signOut());
      await reloaded;
      assert.ok(held, 'the in-flight request really was held during sign-out');
      report.D_requestHeldDuringSignOut = held;
      report.D_cacheAfterSignOut = await cachedRecordEntries(page);
      assert.equal(report.D_cacheAfterSignOut, 0);
      holding = false;
      release();                                            // the old response now completes
      await delayed.catch(() => {});
      await page.waitForTimeout(800);
      report.D_cacheAfterLateResponse = await cachedRecordEntries(page);
      assert.equal(report.D_cacheAfterLateResponse, 0, 'late response must not be cached');
      await context.setOffline(true);
      report.D_offline = await records(page);
      assert.equal(report.D_offline.farms, 0, 'late response must not be served offline');
      await context.close();
    }

    // E. Review finding 2: offline sign-out, all tabs closed, reconnect, open the phone simulator first.
    {
      const context = await fresh();
      const page = await signedInWithCache(context);
      await context.setOffline(true);
      await Promise.all([page.waitForEvent('load'), page.evaluate(() => Fieldwise.signOut())]);
      assert.equal(await page.evaluate(() => localStorage.getItem('fieldwise-signout-pending')), '1');
      await page.close();
      await context.setOffline(false);
      const phone = await context.newPage();
      await phone.goto(BASE + '/ussd-simulator');
      await phone.locator('#input').fill('*384*14#');
      await phone.locator('#dial').click();
      await phone.locator('#fw-signin').waitFor({state: 'visible'});   // no session: the PIN dialog, not a menu
      report.E_simulatorAskedForPin = true;
      report.E_pendingCleared = await phone.evaluate(() => localStorage.getItem('fieldwise-signout-pending'));
      assert.equal(report.E_pendingCleared, null, 'the pending sign-out completed before the simulator request');
      report.E_session = await phone.evaluate(async () => (await (await fetch('/api/session')).json()).signed_in);
      assert.equal(report.E_session, false);
      await phone.keyboard.press('Escape');
      await phone.locator('#screen').filter({hasText: 'sign-in is needed'}).waitFor();
      await context.close();
    }

    // G. Second review: sign-out while a record's body is still downloading (headers already arrived).
    //    Needs scripts/serve-test.py, which holds the body for requests carrying X-Test-Slow-Body.
    {
      const context = await fresh();
      const page = await signedInWithCache(context);
      const started = Date.now();
      const slow = page.evaluate(async () => {
        const token = localStorage.getItem('fieldwise-officer-token');
        const r = await fetch('/api/felix/dashboard', {headers: {'X-Officer-Token': token, 'X-Test-Slow-Body': '3'}});
        const body = await r.json().catch(() => ({}));
        return {status: r.status, farms: (body.farms || []).length};
      });
      await page.waitForTimeout(1000);                      // headers are in, body still held
      await page.evaluate(() => fetch('/api/session', {method: 'DELETE'}));
      report.G_slowBodyAfterSignOut = await slow;
      report.G_bodyReallyDelayed = Date.now() - started >= 2500;
      assert.ok(report.G_bodyReallyDelayed, 'the body was still downloading during sign-out');
      assert.equal(report.G_slowBodyAfterSignOut.farms, 0, 'a body that finishes after sign-out must not reach the page');
      assert.equal(report.G_slowBodyAfterSignOut.status, 401);
      report.G_cacheAfter = await cachedRecordEntries(page);
      assert.equal(report.G_cacheAfter, 0);
      await context.close();
    }

    // F. Review finding 4: signing out in one tab clears every other tab.
    {
      const context = await fresh();
      const first = await signedInWithCache(context);
      const second = await context.newPage();
      second.on('dialog', d => d.accept());
      await second.goto(BASE + '/felix');
      await second.locator('[data-farm]').first().waitFor();
      report.F_secondTabFarmsBefore = await second.locator('[data-farm]').count();
      const secondReloaded = second.waitForEvent('load');
      await Promise.all([first.waitForEvent('load'), first.locator('[data-sign-out]').click()]);
      await secondReloaded;
      await second.locator('#fw-signin').waitFor({state: 'visible'});
      report.F_secondTabFarmsAfter = await second.locator('[data-farm]').count();
      assert.equal(report.F_secondTabFarmsAfter, 0);
      await context.close();
    }

    report.pageErrors = errors;
    assert.deepEqual(errors, []);
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
