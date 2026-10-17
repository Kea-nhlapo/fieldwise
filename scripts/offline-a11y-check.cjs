// Offline-first and accessibility check. Run against a disposable server:
//   node scripts/offline-a11y-check.cjs http://127.0.0.1:8767
const assert = require('node:assert/strict');
let playwright;
try {playwright=require('playwright');}
catch {playwright=require('C:/Users/DellUser/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');}
const BASE = process.argv[2] || 'http://127.0.0.1:8767';
const AXE = 'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js';

(async()=>{
  const browser = await playwright.chromium.launch({headless:true, channel:'msedge'});
  const report = {};
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}});
    const page = await context.newPage();
    const errors = []; page.on('pageerror', e=>errors.push(e.message));

    // 1. Install: service worker takes control and caches the shell + data.
    await page.goto(BASE + '/felix');
    await page.evaluate(()=>navigator.serviceWorker.ready);
    await page.reload();
    await page.waitForFunction(()=>!!navigator.serviceWorker.controller);
    await page.locator('[data-farm="F014"]').waitFor();
    report.cached = await page.evaluate(async()=>{let n=0; for (const k of await caches.keys()) n += (await (await caches.open(k)).keys()).length; return n;});
    assert.ok(report.cached > 20, 'service worker cached the app shell');

    const synced = async()=>(await (await page.request.get(BASE + '/api/impact')).json()).metrics.find(m=>m.id==='offline_synced').value;
    const visits = async()=>(await (await page.request.get(BASE + '/api/felix/farms/F014/privacy-export')).json()).activity.filter(a=>a.kind==='visit').length;
    const before = {synced: await synced(), visits: await visits()};
    // An online write must not be counted as an offline sync.
    await page.evaluate(()=>Fieldwise.fetch('/api/felix/farms/F027/plan', {method:'POST', body:JSON.stringify({planned:true})}));
    assert.equal(await synced(), before.synced, 'online write miscounted as offline sync');

    // 2. Offline: every page still opens from the cache, and the banner says how old the data is.
    await context.setOffline(true);
    for (const path of ['/', '/felix', '/impact']) {
      await page.goto(BASE + path);
      await page.locator('.connection[data-state="offline"]').waitFor({timeout:8000});
    }
    await page.goto(BASE + '/felix');
    await page.locator('[data-farm="F014"]').click();
    report.offlineBanner = await page.locator('.connection').innerText();
    assert.match(report.offlineBanner, /Offline/);

    // 3. A visit captured offline goes to the outbox.
    await page.locator('#visit-notes').fill('Checked wilting with no signal (offline test)');
    await page.locator('#save-visit').click();
    await page.locator('#feedback').filter({hasText:'Saved on this device'}).waitFor();
    assert.equal(await page.evaluate(()=>Fieldwise.pending()), 1);
    await page.screenshot({path:'artifacts/offline-queued.png'});

    // 4. Back online: the outbox syncs once, and the impact log records it.
    await context.setOffline(false);
    await page.evaluate(()=>window.dispatchEvent(new Event('online')));
    await page.waitForFunction(()=>Fieldwise.pending()===0, null, {timeout:15000});
    report.offlineSynced = await synced() - before.synced;
    assert.equal(report.offlineSynced, 1);
    assert.equal(await visits() - before.visits, 1, 'visit saved exactly once');

    // 5. Accessibility: axe-core WCAG 2.1 A/AA on each page, desktop and mobile.
    report.axe = {};
    for (const [label, viewport] of [['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]]) {
      await page.setViewportSize(viewport);
      for (const path of ['/', '/felix', '/impact', '/pilot', '/ussd-simulator']) {
        await page.goto(BASE + path);
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(900);  // let entrance animations finish before contrast checks
        await page.addScriptTag({url: AXE});
        const result = await page.evaluate(async()=>(await axe.run(document, {runOnly:{type:'tag', values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}}))
          .violations.map(v=>({id:v.id, impact:v.impact, nodes:v.nodes.length, sample:v.nodes[0]?.target.join(' ')})));
        report.axe[`${label} ${path}`] = result;
        const overflow = await page.evaluate(()=>document.documentElement.scrollWidth > innerWidth + 1);
        assert.equal(overflow, false, `horizontal overflow on ${label} ${path}`);
      }
      await page.goto(BASE + '/impact');
      await page.screenshot({path:`artifacts/impact-${label}.png`, fullPage:true});
    }
    // Keyboard: the first Tab lands on the skip link.
    await page.keyboard.press('Tab');
    report.firstTab = await page.evaluate(()=>document.activeElement.textContent);
    assert.equal(report.firstTab, 'Skip to main content');
    report.pageErrors = errors;
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error); process.exit(1);});
