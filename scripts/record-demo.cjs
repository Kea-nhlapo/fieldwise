// Plays the stage demo end to end at presenting pace and records a backup video.
// Run against a server you are happy to reset:
//   node scripts/record-demo.cjs http://127.0.0.1:8767
// Output: numbered screenshots in artifacts/demo-backup/ and a JSON log of the numbers seen at each step.
// Set VIDEO=1 to also record artifacts/demo-backup.webm (needs: npx playwright install ffmpeg).
const assert = require('node:assert/strict');
const fs = require('node:fs');
let playwright;
try {playwright=require('playwright');}
catch {playwright=require('C:/Users/DellUser/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');}
const BASE = process.argv[2] || 'http://127.0.0.1:8767';
const pause = ms => new Promise(r => setTimeout(r, ms));

(async()=>{
  const browser = await playwright.chromium.launch({headless:true, channel:'msedge'});
  const video = process.env.VIDEO === '1';
  const context = await browser.newContext({viewport:{width:1440,height:900}, ...(video ? {recordVideo:{dir:'artifacts/video-tmp', size:{width:1440,height:900}}} : {})});
  fs.rmSync('artifacts/demo-backup', {recursive:true, force:true}); fs.mkdirSync('artifacts/demo-backup', {recursive:true});
  let shot = 0;
  const snap = async (target, name) => { await pause(700); await target.screenshot({path:`artifacts/demo-backup/${String(++shot).padStart(2,'0')}-${name}.png`}); };
  const page = await context.newPage();
  const log = {}; const errors = [];
  page.on('pageerror', e=>errors.push(e.message));
  page.on('dialog', d=>d.accept());
  const scrollTo = async selector => { await page.locator(selector).scrollIntoViewIfNeeded(); await page.evaluate(s=>document.querySelector(s).scrollIntoView({block:'start'}), selector); await pause(1200); };
  try {
    // 0. Clean start.
    await page.goto(BASE + '/felix');
    await page.locator('[data-reset-demo]').click();
    await page.waitForLoadState('networkidle');
    await page.locator('#next-visit h2').waitFor();
    log.start = {nextVisit: await page.locator('#next-visit h2').innerText()};
    await snap(page, 'start-next-visit');

    // 1. Evidence with timestamps.
    await scrollTo('#evidence-flow');
    await page.locator('#fetch-evidence').click();
    await page.waitForFunction(()=>!document.querySelector('#fetch-evidence').disabled, null, {timeout:60000});
    await pause(2000);
    log.evidence = await page.locator('.evidence-state').allInnerTexts();
    await snap(page, 'live-evidence');

    // 2. Who to ask next, then queue the top target.
    await scrollTo('#ask-next');
    // Ask a farm outside today's top 3: a 'yes' moves it into Felix's visits.
    const row = page.locator('.ask-row').filter({hasText:/Now #[4-9]/}).first();
    const target = await row.locator('[data-ask]').getAttribute('data-ask');
    log.firstTarget = {id: target, row: await row.innerText()};
    await snap(page, 'who-to-ask');
    await row.locator('[data-ask]').click();
    await page.locator('#feedback').filter({hasText:'Survey invitation queued'}).waitFor();
    await pause(1500);

    // 3. Farmer answers on a basic phone.
    const phone = await context.newPage();
    await phone.goto(BASE + '/ussd-simulator');
    await phone.locator('#input').fill(`*384*${Number(target.slice(1))}#`);
    await pause(800);
    await phone.locator('#dial').click();
    for (const answer of ['1', '1', '2', '2']) {
      await phone.locator('#screen').filter({hasText:/\S/}).waitFor();
      await pause(400);
      await snap(phone, 'ussd-screen');
      await phone.locator('#input').fill(answer);
      await phone.locator('#entry button').click();
    }
    await phone.locator('#screen').filter({hasText:'Thank you'}).waitFor();
    log.ussd = await phone.locator('#log').innerText();
    await snap(phone, 'ussd-thank-you');
    await pause(2000);
    await phone.close();

    // 4. Back in Felix's workspace: the answer moved the farm.
    await page.bringToFront();
    await page.reload();
    await page.locator('#next-visit h2').waitFor();
    await page.locator(`[data-farm="${target}"]`).first().click();
    await scrollTo('#survey-impact');
    log.surveyImpact = await page.locator('#survey-impact').innerText();
    assert.match(log.surveyImpact, /\+55/);
    await snap(page, 'answer-changed-score');

    // 5. Felix visits and taps what he found; the model learns.
    await scrollTo('#farm-detail');
    await page.locator('[data-code="wilting"]').click();
    await page.locator('[data-code="followup"]').click();
    await pause(800);
    await page.locator('#save-visit').click();
    await page.locator('#feedback').filter({hasText:'Visit recorded'}).waitFor();
    await scrollTo('#ask-next');
    log.learning = await page.locator('#learning-table').innerText();
    assert.match(log.learning, /1 of 1 confirmed/);
    await snap(page, 'model-learned');
    await pause(2000);

    // 6. Maize at stake in the South Africa water model, and a farmer SMS reply.
    await page.goto(BASE + '/');
    await page.locator('#next-visit h2').waitFor();
    await pause(2000);
    log.saNextVisit = await page.locator('#next-visit').innerText();
    await snap(page, 'sa-maize-at-stake');
    await page.locator('[data-farm="makhaya"]').click();
    await page.locator('[data-reply="2"]').click();
    await page.locator('#toast').filter({hasText:/saved/i}).waitFor();
    await scrollTo('#scenario');
    log.atStake = await page.locator('#at-stake').innerText();
    await snap(page, 'sa-water-balance');
    await pause(2000);

    // 7. Impact and pilot plan.
    await page.goto(BASE + '/impact');
    await page.locator('.hero-stat').first().waitFor();
    await pause(3000);
    log.impactHero = await page.locator('#hero-stats').innerText();
    await snap(page, 'impact');
    await page.goto(BASE + '/pilot');
    await pause(1500);
    await scrollTo('#cost');
    log.pilotCost = await page.locator('.calc-out').innerText();
    await snap(page, 'pilot-cost');
    await pause(2500);
    log.pageErrors = errors;
    fs.writeFileSync('artifacts/demo-run.json', JSON.stringify(log, null, 2));
    console.log(JSON.stringify(log, null, 2));
  } finally {
    const recording = video ? page.video() : null;
    await context.close();
    await browser.close();
    if (recording) { fs.renameSync(await recording.path(), 'artifacts/demo-backup.webm'); fs.rmSync('artifacts/video-tmp', {recursive:true, force:true}); }
  }
})().catch(error=>{console.error(error); process.exit(1);});
