let data, selected = 'makhaya', filter = 'All', toastTimer, savedOffline = false;
const $ = id => document.getElementById(id);
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(url, options = {}) {
  const response = await Fieldwise.fetch(url, {headers: {'Content-Type':'application/json'}, ...options});
  const body = await response.json();
  if (body.queued) savedOffline = true;
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Please check the input and try again.');
  return body;
}
function toast(message) { if (savedOffline) { message = Fieldwise.queuedMessage; savedOffline = false; } $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 4200); }
async function action(button, task) {
  button.disabled = true; $('error').hidden = true;
  try { await task(); } catch (error) { $('error').textContent = error.message; $('error').hidden = false; toast(error.message); }
  finally { button.disabled = false; }
}
async function load() { data = await api('/api/dashboard'); render(); }
function chart(farm) {
  const wet = farm.scenarios.working, dry = farm.scenarios.interrupted;
  const width = 500, height = 190, left = 35, right = 12, top = 15, bottom = 30;
  const max = Math.ceil(Math.max(...dry.map(d => d.depletion_mm), ...wet.map(d => d.depletion_mm), dry[0].raw_mm) / 20) * 20 || 20;
  const x = i => left + i * (width-left-right)/(dry.length-1);
  const y = value => height-bottom-value/max*(height-top-bottom);
  const line = series => series.map((d,i) => `${x(i)},${y(d.depletion_mm)}`).join(' ');
  let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Projected root-zone depletion in millimetres, comparing working and interrupted irrigation"><title>Working versus interrupted irrigation</title>`;
  for(let i=0;i<=4;i++) { const v=max*i/4; svg += `<line x1="${left}" y1="${y(v)}" x2="${width-right}" y2="${y(v)}" stroke="#e9eee2"/><text x="${left-8}" y="${y(v)+3}" text-anchor="end" fill="#8a9682" font-size="9">${v}</text>`; }
  svg += `<line x1="${left}" y1="${y(dry[0].raw_mm)}" x2="${width-right}" y2="${y(dry[0].raw_mm)}" stroke="#939b85" stroke-dasharray="4 4"/>`;
  svg += `<polygon points="${x(0)},${y(0)} ${line(dry)} ${x(dry.length-1)},${y(0)}" fill="#f9e8d7" opacity=".45"/>`;
  svg += `<polyline points="${line(dry)}" fill="none" stroke="#d78745" stroke-width="2.5" stroke-linejoin="round"/><polyline points="${line(wet)}" fill="none" stroke="#34674e" stroke-width="2.5" stroke-linejoin="round"/>`;
  for(const i of [0,Math.floor(dry.length/2),dry.length-1]) svg += `<text x="${x(i)}" y="${height-8}" text-anchor="${i===0?'start':i===dry.length-1?'end':'middle'}" font-size="9" fill="#8a9682">${esc(new Date(dry[i].date+'T12:00:00').toLocaleDateString('en-ZA',{day:'numeric',month:'short'}))}</text>`;
  $('chart').innerHTML = svg + '</svg>';
}
function render() {
  $('farm-count').textContent = data.farms.length;
  $('urgent-count').textContent = data.farms.filter(f=>f.priority.label==='Urgent').length;
  $('unknown-count').textContent = data.farms.filter(f=>f.reply==='unknown').length;
  const farms = data.farms.filter(f=>filter==='All'||f.priority.label===filter);
  $('farm-list').innerHTML = farms.length ? farms.map(f=>`<button class="farm-row ${f.id===selected?'chosen':''}" data-farm="${esc(f.id)}" aria-pressed="${f.id===selected}">${cropIcon(f.crop)}<span class="farm-info"><strong>${esc(f.name)}</strong><small>${esc(f.area)} · ${f.root_m} m root zone${f.priority.disease_alert_count?' · <span class="ico" style="--ico:url(/static/icons/flag.svg)" aria-hidden="true"></span> disease review':''}</small></span><span class="farm-score"><span class="badge ${f.priority.label.toLowerCase()}">${f.priority.label}</span>${f.priority.score} / 100<span class="meter ${f.priority.score>=70?'hot':f.priority.score>=40?'warm':''}" aria-hidden="true"><i style="width:${Math.min(100,f.priority.score)}%"></i></span></span></button>`).join('') : '<p class="empty">No fields in this priority category.</p>';
  document.querySelectorAll('[data-farm]').forEach(b=>b.onclick=()=>{selected=b.dataset.farm; $('draft-result').textContent=''; render();});
  const next = data.farms[0];
  $('next-visit').innerHTML = `${cropIcon(next.crop)}<div class="next-body"><span class="eyebrow">VISIT FIRST</span><h2 id="next-visit-title">${esc(next.name)} <span class="badge ${next.priority.label.toLowerCase()}">${esc(next.priority.label)} · ${next.priority.score}</span></h2><p><strong>≈ ${next.yield_estimate.at_stake_kg.toLocaleString('en-ZA')} kg of maize at stake</strong> if irrigation stays off. ${esc(next.area)} · ${esc(next.priority.reason)}</p></div><div class="next-actions"><button class="primary-button" data-jump="${esc(next.id)}" data-target="scenario">See its water balance</button><a class="outline-button" href="#route">Plan the route</a></div>`;
  const farm = data.farms.find(f=>f.id===selected) || data.farms[0];
  selected = farm.id;
  const series = farm.scenarios[farm.selected_scenario], last=series.at(-1);
  $('selected-name').textContent = farm.name;
  $('depletion').innerHTML = `${last.depletion_mm.toFixed(1)} <small>mm</small>`;
  $('difference').innerHTML = `${(farm.scenarios.interrupted.at(-1).depletion_mm-farm.scenarios.working.at(-1).depletion_mm).toFixed(1)} <small>mm</small>`;
  const y = farm.yield_estimate;
  $('at-stake').innerHTML = `${y.at_stake_kg.toLocaleString('en-ZA')} <small>kg</small>`;
  $('yield-method').textContent = `${y.method} Interrupted irrigation: ${y.interrupted.loss_pct}% of a ${y.assumptions.potential_kg_per_ha.toLocaleString('en-ZA')} kg/ha season on ${y.field_ha} ha; Ky ${y.assumptions.ky}, seasonal crop water need ${y.assumptions.season_etm_mm} mm.`;
  $('window-label').textContent = `${farm.window.days}-day scenario · ${farm.window.start} → ${farm.window.end} · ${farm.selected_scenario==='working'?'Working irrigation assumed':'No irrigation assumed'}`;
  $('reason').textContent = farm.water_priority.reason;
  $('question').textContent = `Is irrigation working at ${farm.name}?`;
  $('inputs').innerHTML = `<div class="input-grid"><span>Field capacity: ${farm.theta_fc} m³/m³</span><span>Wilting point: ${farm.theta_wp} m³/m³</span><span>Starting depletion: ${farm.initial_depletion*100}%</span><span>Root depth: ${farm.root_m} m</span><span>Irrigation: ${farm.irrigation_mm} mm / ${farm.irrigation_interval_days} days</span><span>Application efficiency: 85%</span></div><p>${data.assumptions.map(esc).join('<br>')}</p>`;
  $('weather-source').textContent = farm.weather_source + (farm.weather_fetched_at ? ' · fetched '+new Date(farm.weather_fetched_at).toLocaleString('en-ZA') : ' · no internet needed');
  document.querySelectorAll('[data-reply]').forEach(b=>{b.classList.toggle('selected',b.dataset.reply===farm.reply);b.setAttribute('aria-pressed',String(b.dataset.reply===farm.reply));});
  chart(farm);
  if (typeof renderDisease === 'function') renderDisease(farm);
  $('activity-list').innerHTML = data.activity.length ? data.activity.slice(0,6).map(a=>`<div class="activity-row"><time>${esc(new Date(a.created_at).toLocaleTimeString('en-ZA',{hour:'2-digit',minute:'2-digit'}))}</time><span>${esc(data.farms.find(f=>f.id===a.farm_id)?.name || a.farm_id)} · ${esc(a.text)}</span></div>`).join('') : '<p class="empty">No signals yet. Simulate a farmer reply to start the conversation.</p>';
}
function invalidateRoute() { $('route-result').innerHTML='<p class="empty">Field assumptions changed. Plan visits again to update the route.</p>'; }
document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;document.querySelectorAll('[data-filter]').forEach(x=>{x.classList.toggle('selected',x===b);x.setAttribute('aria-pressed',String(x===b));});render();});
document.querySelectorAll('[data-reply]').forEach(b=>b.onclick=()=>action(b,async()=>{const fid=selected;await api(`/api/farms/${fid}/reply`,{method:'POST',body:JSON.stringify({reply:b.dataset.reply})});await load();invalidateRoute();toast('Farmer reply saved. Water balance and priorities updated.');}));
$('draft').onclick=()=>action($('draft'),async()=>{const r=await api(`/api/farms/${selected}/outreach`,{method:'POST'});$('draft-result').textContent='Local draft, not sent: '+r.text;await load();toast('SMS draft saved locally. No message was sent.');});
$('live-weather').onclick=()=>action($('live-weather'),async()=>{await api(`/api/farms/${selected}/weather`,{method:'POST'});await load();invalidateRoute();toast('7-day Open-Meteo forecast loaded for this field.');});
$('demo-weather').onclick=()=>action($('demo-weather'),async()=>{await api(`/api/farms/${selected}/weather`,{method:'DELETE'});await load();invalidateRoute();toast('Synthetic weather restored for this field.');});
$('budget').onchange=invalidateRoute;
$('plan').onclick=()=>action($('plan'),async()=>{
  const route=await api('/api/route?minutes='+$('budget').value);
  const time=m=>`${String(8+Math.floor(m/60)).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`;
  $('route-result').innerHTML=`<div class="route-summary"><strong>${route.visits.length} visits · ${route.total_minutes} of ${route.budget_minutes} minutes</strong><span>08:00 start → ${time(route.total_minutes)} return to depot</span></div><div class="route-stops">${route.visits.map((v,i)=>`<div class="stop"><span>0${i+1} / ${time(v.arrival_minutes)}</span><strong>${esc(v.name)}</strong><small>${v.visit_minutes} min inspection · Priority ${v.score}</small></div>`).join('')||'<p class="empty">No visits fit this time budget.</p>'}</div><p class="deferred">${route.deferred.length?'Deferred: '+route.deferred.map(id=>esc(data.farms.find(f=>f.id===id)?.name||id)).join(', '):'All fields fit within the available time.'}</p>`;
});
$('today').textContent = new Date().toLocaleDateString('en-ZA',{weekday:'long',day:'numeric',month:'long',timeZone:'Africa/Johannesburg'});
document.addEventListener('click', event => {
  const jump = event.target.closest('[data-jump]');
  if (!jump || !data) return;
  selected = jump.dataset.jump; render();
  document.getElementById(jump.dataset.target).scrollIntoView({block:'start'});
});
document.addEventListener('fieldwise:synced', () => load().catch(() => {}));
load().catch(error=>{$('error').textContent=error.message;$('error').hidden=false;});
