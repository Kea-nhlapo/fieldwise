const pw=require('C:/Users/DellUser/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const out=process.argv[2]||'artifacts/before';
(async()=>{const b=await pw.chromium.launch({channel:'msedge'});
for(const [w,h,tag] of [[1440,900,'desktop'],[390,844,'mobile']]){const p=await b.newPage({viewport:{width:w,height:h}});
for(const [path,name] of [['/','sa'],['/felix','felix'],['/impact','impact']]){await p.goto('http://127.0.0.1:8765'+path);await p.waitForLoadState('networkidle');await p.waitForTimeout(600);
await p.screenshot({path:`${out}/${name}-${tag}.png`,fullPage:tag==='desktop'});}}
await b.close();})();
