'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let data, mapData, selected = 'F014', answers = [], checkinFarm = null, activeSurvey = null;

async function api(path, body) {
  const response = await Fieldwise.fetch(path, body === undefined ? {} : {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.receipt?.error || (typeof result.detail === 'string' ? result.detail : 'Check the required fields and try again.'));
  return result;
}
function feedback(message, failed=false) {
  $('feedback').textContent = message;
  $('feedback').classList.toggle('failed', failed);
}
async function save(kind, body, message) {
  const fid = selected;
  document.querySelectorAll('button').forEach(button=>button.disabled=true);
  try {
    const result = await api(`/api/felix/farms/${encodeURIComponent(fid)}/${kind}`, body);
    data = await api('/api/felix/dashboard');
    if (result.queued) message = Fieldwise.queuedMessage;
    $('checkin').hidden = true;
    checkinFarm = null;
    render();
    feedback(message);
    return true;
  } catch (error) {
    feedback(error.message, true);
    return false;
  } finally {
    document.querySelectorAll('button').forEach(button=>button.disabled=false);
    if (data) $('plan-toggle').disabled = data.farms.find(f=>f.id===selected).completed;
  }
}
function selectFarm(fid) {
  selected = fid;
  checkinFarm = null;
  activeSurvey = null;
  $('survey-consent').checked = false;
  $('checkin').hidden = true;
  render();
}
function renderMap() {
  const [south, west, north, east] = mapData.bounds;
  const point = pair=>[(pair[1]-west)/(east-west)*600, (north-pair[0])/(north-south)*600];
  const lines = mapData.features.map(line=>{
    const points = line.points.map(p=>point(p).map(n=>n.toFixed(2)).join(',')).join(' ');
    const river = line.kind==='waterway', primary = line.value==='primary';
    return `<polyline points="${points}" fill="none" stroke="${river?'#7caeb1':primary?'#cbb48a':'#f9f7ef'}" stroke-width="${river?3:primary?6:3}"/>`;
  }).join('');
  const pins = data.farms.map((farm,i)=>{
    const [x,y] = point([farm.latitude,farm.longitude]);
    const tone = farm.completed ? 'done' : /today/i.test(farm.status) ? 'hot' : farm.status==='Watch' ? 'warm' : 'calm';
    return `<g class="map-pin pin-${tone} ${farm.id===selected?'active':''}" data-pin="${esc(farm.id)}" role="button" tabindex="0" aria-label="Select ${esc(farm.name)}" transform="translate(${x.toFixed(2)} ${y.toFixed(2)})"><title>${esc(farm.name)} · ${esc(farm.status)} · ${farm.score} points</title><circle r="17"/><text>${i+1}</text></g>`;
  }).join('');
  $('map').innerHTML = `<svg viewBox="0 0 600 600" role="group" aria-label="Offline Kasungu map with eight selectable farm pins">${lines}${pins}</svg>`;
}
function listItem(farm) {
  return `<button class="shortlist-item" data-select="${esc(farm.id)}"><span><strong>${esc(farm.name)}</strong><small>${esc(farm.action)} · ${esc(farm.status)}</small></span><b>${farm.score} points <span class="ico" style="--ico:url(/static/icons/arrow-right.svg)" aria-hidden="true"></span></b></button>`;
}
function renderList() {
  const query = $('search').value.toLowerCase().trim();
  $('farm-list').innerHTML = data.farms.map((f,i)=>({f,i})).filter(({f})=>`${f.name} ${f.crop} ${f.id}`.toLowerCase().includes(query)).map(({f,i})=>
    `<button class="felix-farm ${f.id===selected?'selected':''}" data-farm="${esc(f.id)}" aria-pressed="${f.id===selected}"><span class="rank">${i+1}</span>${cropIcon(f.crop)}<span class="farm-label"><strong>${esc(f.name)}</strong><small>${esc(f.crop)} · ${esc(f.status)}</small><small>${f.weather.mode==='live_fetch'?'Fetched forecast':f.weather.mode==='unavailable'?'Stale weather · incomplete':'Bundled scenario'}</small></span><span class="farm-points">${f.score}<span class="meter ${f.score>=75?'hot':f.score>=55?'warm':''}" aria-hidden="true"><i style="width:${Math.min(100,f.score/1.6)}%"></i></span></span></button>`
  ).join('') || '<p class="empty">No matching farms.</p>';
}
function render() {
  const farm = data.farms.find(f=>f.id===selected);
  $('farm-count').textContent = data.farms.length;
  $('concern-count').textContent = data.alerts.length;
  $('plan-count').textContent = data.plan.length;
  renderList(); renderMap(); renderLearning();
  const next = data.farms.find(f=>!f.completed);
  $('next-visit').innerHTML = next ? `${cropIcon(next.crop)}<div class="next-body"><span class="eyebrow">VISIT FIRST · RANK 1</span><h2 id="next-visit-title">${esc(next.name)} <span class="badge ${/today/i.test(next.status)?'urgent':next.status==='Watch'?'watch':'routine'}">${esc(next.status)} · ${next.score} points</span></h2><p>${esc(next.action)}. ${esc(next.why)}</p></div><div class="next-actions"><button class="primary-button" data-select="${esc(next.id)}" data-jump="farm-detail">Open this farm</button>${next.planned?'<span class="hint">On your shortlist</span>':''}</div>`
    : '<div class="next-body"><span class="eyebrow">VISIT FIRST</span><h2 id="next-visit-title">Every farm has a recorded visit</h2></div>';
  const weather = farm.weather;
  $('snapshot').textContent = weather.rain_mm===null ? 'Current weather unavailable. Refresh before relying on this profile.' : `${weather.start} → ${weather.end} · ${weather.rain_mm.toFixed(1)} mm precipitation · ${weather.heat_c.toFixed(2)} °C highest temperature`;
  $('selected-name').textContent = farm.name;
  $('selected-meta').textContent = `${farm.id} · ${farm.crop} · ${farm.latitude.toFixed(4)}, ${farm.longitude.toFixed(4)}`;
  $('selected-action').textContent = farm.completed ? 'Visit recorded' : farm.action;
  $('selected-status').textContent = farm.status;
  $('selected-score').textContent = farm.score;
  $('selected-why').textContent = farm.why;
  $('selected-success').textContent = farm.success;
  $('last-report').textContent = farm.report ? `Latest simulated report: ${farm.report} · ${farm.answer_summary} · ${new Date(farm.reported_at).toLocaleString()}` : 'No farmer check-in recorded yet.';
  $('last-visit').textContent = farm.visit_notes ? `Last visit note: ${farm.visit_notes}` : '';
  $('plan-toggle').textContent = farm.planned ? 'Remove from shortlist' : 'Add to shortlist';
  $('plan-toggle').disabled = farm.completed;
  $('correction-choice').value = farm.override || 'Reset';
  $('correction-note').value = farm.note || '';
  $('visit-notes').value = '';
  document.querySelectorAll('[data-outcome]').forEach(chip=>chip.removeAttribute('aria-pressed'));
  $('visit-plan').innerHTML = data.plan.map(listItem).join('') || '<p class="empty">Choose a farm and add it to your shortlist.</p>';
  $('alerts').innerHTML = data.alerts.map(listItem).join('') || '<p class="empty">No unreviewed farmer concerns.</p>';
  $('event-log').innerHTML = data.activity.map(event=>`<div class="activity-row"><time datetime="${esc(event.created_at)}">${esc(new Date(event.created_at).toLocaleString())}</time><span><strong>${esc(event.farm_id)}</strong> · ${esc(event.text)}</span></div>`).join('') || '<p class="empty">Check-ins, corrections and visits will appear here.</p>';
  renderEvidence(farm);
}
function renderLearning() {
  $('top-k').textContent = data.visits_per_day;
  const pct = p => `${Math.round(p*100)}%`;
  $('survey-targets').innerHTML = data.survey_targets.slice(0,4).map((t,i)=>`<div class="ask-row">${cropIcon(t.crop)}<div class="ask-body"><strong>${i+1}. ${esc(t.name)}</strong><small>Farmer dials <b>*384*${Number(t.id.slice(1))}#</b></small><small>Now #${t.rank_now} · “Yes” → #${t.rank_if_yes} · “No” → #${t.rank_if_no} · ${pct(t.p_concern)} chance of “yes”</small><span class="meter ${t.decision_change>=.5?'hot':t.decision_change>0?'warm':''}" aria-hidden="true"><i style="width:${Math.max(4,t.decision_change*100)}%"></i></span><small><b>${pct(t.decision_change)}</b> chance the answer changes today’s visits</small></div><button type="button" class="outline-button" data-ask="${esc(t.id)}">Queue survey</button></div>`).join('')
    || '<p class="empty">Every open farm already has a farmer answer.</p>';
  const t = data.survey_targets;
  if (t.length > 1 && t.every(x=>x.decision_change===t[0].decision_change && x.p_concern===t[0].p_concern))
    $('survey-targets').insertAdjacentHTML('afterbegin', '<p class="tie-note">These farms tie because they share the same bundled weather. Fetch live evidence, or record a farmer answer or a visit outcome, and the order will separate.</p>');
  $('learning-table').innerHTML = `<table class="reference-table"><caption class="visually-hidden">Problem rate by signal</caption><thead><tr><th scope="col">Signal at visit</th><th scope="col">Rule assumption</th><th scope="col">Learned now</th><th scope="col">Visits</th></tr></thead><tbody>${Object.values(data.learning).map(s=>`<tr><td>${esc(s.label)}</td><td>${pct(s.prior)}</td><td><strong>${pct(s.posterior)}</strong></td><td>${s.confirmed} of ${s.visits} confirmed</td></tr>`).join('')}</tbody></table>`;
}
function showQuestion() {
  const farm = data.farms.find(f=>f.id===checkinFarm);
  const queued = farm.surveys.find(s=>s.id===activeSurvey);
  const questions = [queued?.question || farm.question, 'Are several parts of the field affected?', 'How long have you noticed this?'];
  const options = [['Yes','No','Not sure'],['One area','Several areas','Not sure'],['Today','More than one day','Not sure']];
  $('checkin-question').textContent = questions[answers.length];
  $('checkin-options').innerHTML = options[answers.length].map((label,i)=>`<button type="button" data-answer="${i+1}">${i+1}. ${label}</button>`).join('');
}
document.addEventListener('DOMContentLoaded', async()=>{
  $('search').addEventListener('input',()=>{if(data)renderList();});
  document.addEventListener('click', event=>{
    const farm = event.target.closest('[data-farm],[data-pin],[data-select]');
    if (farm && data) selectFarm(farm.dataset.farm || farm.dataset.pin || farm.dataset.select);
  });
  $('map').addEventListener('keydown', event=>{
    const pin = event.target.closest('[data-pin]');
    if(pin && ['Enter',' '].includes(event.key)) {event.preventDefault();selectFarm(pin.dataset.pin);}
  });
  $('plan-toggle').addEventListener('click',()=>save('plan',{planned:!data.farms.find(f=>f.id===selected).planned},'Visit shortlist saved locally.'));
  $('correction-form').addEventListener('submit', event=>{
    event.preventDefault();
    save('correction',{decision:$('correction-choice').value, notes:$('correction-note').value},'Felix’s correction saved locally.');
  });
  $('visit-form').addEventListener('submit', event=>{
    event.preventDefault(); save('visit',{notes:$('visit-notes').value, outcomes:[...document.querySelectorAll('[data-outcome][aria-pressed=true]')].map(chip=>chip.dataset.code)},'Visit recorded locally; concern reviewed.');
  });
  $('start-checkin').addEventListener('click',()=>{
    if(!$('survey-consent').checked) {feedback('Read the notice and choose whether to participate. No answer has been stored.',true);return;}
    activeSurvey=data.farms.find(f=>f.id===selected).surveys.find(s=>s.status==='queued')?.id || null;
    answers=[];checkinFarm=selected;$('checkin').hidden=false;showQuestion();
  });
  document.addEventListener('click', event=>{
    const jump = event.target.closest('[data-jump]');
    if (jump) document.getElementById(jump.dataset.jump).scrollIntoView({block:'start'});
    const ask = event.target.closest('[data-ask]');
    if (ask) { selectFarm(ask.dataset.ask); save('surveys', {}, 'Survey invitation queued for this farm. Open the farm below to run the check-in.'); }
    const chip = event.target.closest('[data-outcome]');
    if (chip) { const notes=$('visit-notes'); notes.value = (notes.value.trim() + ' ' + chip.dataset.outcome).trim(); chip.setAttribute('aria-pressed','true'); }
  });
  $('cancel-checkin').addEventListener('click',()=>{$('checkin').hidden=true;checkinFarm=null;});
  $('checkin-options').addEventListener('click', async event=>{
    const button=event.target.closest('[data-answer]');
    if(!button)return;
    const choice=Number(button.dataset.answer);answers.push(choice);
    if((answers.length===1 && choice===2)||(answers.length===2 && choice===1)||answers.length===3) {
      const saved=await save('check-in',{answers:[...answers],consent:$('survey-consent').checked,survey_id:activeSurvey},'Check-in saved in Felix’s local queue. No USSD or message was sent.');
      if(!saved){answers.pop();showQuestion();}
      else {$('survey-consent').checked=false;activeSurvey=null;}
    } else showQuestion();
  });
  document.addEventListener('fieldwise:synced', async()=>{ try { data = await api('/api/felix/dashboard'); render(); feedback('Offline actions synced to the server.'); } catch {} });
  try {
    [data,mapData] = await Promise.all([api('/api/felix/dashboard'),api('/api/felix/map')]);
    render();
  } catch(error) { feedback(`Could not load Kasungu workspace: ${error.message}`,true); }
});
