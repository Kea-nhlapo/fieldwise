'use strict';
const stamp = value => value ? `${new Date(value).toLocaleString()} (${value})` : 'Not supplied';
const signed = value => value>0 ? `+${value}` : String(value);
let evidenceBusy=false;

function renderEvidence(farm) {
  $('evidence-farm').innerHTML = data.farms.map(f=>`<option value="${esc(f.id)}">${esc(f.name)} · ${esc(f.id)}</option>`).join('');
  $('evidence-farm').value=selected;
  $('map-mode').textContent=mapData.mode==='live_fetch'?'FETCHED MAP':'BUNDLED MAP';
  const descriptions={
    weather:'Three-day rain and maximum temperature. Forecast grid cells can differ from the requested point.',
    soil:'Mapped clay at 0–5 cm, approximately 250 m resolution. Not current soil moisture.',
    map:'Roads and waterways for the shared Kasungu extent. Context only; no risk points.'
  };
  $('evidence-cards').innerHTML=Object.entries(farm.evidence).map(([source,context])=>{
    const good=context.used_receipt, previous=context.last_success, attempt=context.last_attempt;
    const labels={current:'Fetched · current cache',stale:'Stale · excluded',bundled:'Bundled · not live',missing:'Missing · unknown'};
    const failed=attempt && !attempt.success && attempt.completed_at;
    let value=source==='weather' ? (farm.rain_mm===null?'No current forecast':`${farm.rain_mm.toFixed(1)} mm · ${farm.heat_c.toFixed(1)} °C`) : source==='soil' ? (farm.clay_percent===null?'Clay unknown':`${farm.clay_percent.toFixed(1)}% clay`) : `${mapData.features.length} road / waterway features`;
    let validity=source==='weather' ? `${farm.weather.start} → ${farm.weather.end} · ${farm.weather.timezone}` : source==='soil' ? 'Soil observation / model issue time: not supplied' : `Map database time: ${mapData.map_base_at || 'not supplied for bundled extract'}`;
    const proof=good || previous || attempt;
    return `<article class="card evidence-card" id="evidence-${source}"><div class="evidence-heading"><h3>${esc(context.provider)}</h3><span class="evidence-state ${context.state}">${labels[context.state]}</span></div><strong class="evidence-value">${esc(value)}</strong><p>${esc(descriptions[source])}</p><p class="validity">${esc(validity)}</p><dl><dt>Last request attempted</dt><dd>${esc(attempt?stamp(attempt.attempted_at):'No request made by this app')}</dd><dt>Last successful retrieval</dt><dd>${esc(previous?stamp(previous.completed_at):'None · bundle download time unknown')}</dd><dt>Role in this profile</dt><dd>${source==='map'?'Location context only':context.used_in_score?'Fetched input used':source==='weather'&&context.state==='bundled'?'Bundled scenario used; demonstration only':'Excluded / unknown'}</dd></dl>${failed?`<p class="evidence-failure">Latest attempt failed${attempt.http_status?' · HTTP '+attempt.http_status:''}. ${esc(attempt.error)} ${good?'Earlier valid retrieval remains in use.':''}</p>`:''}<div class="evidence-actions"><button class="outline-button" data-fetch="${source}" type="button">Fetch ${source}</button>${proof?`<a href="/api/felix/evidence/${proof.id}" target="_blank" rel="noopener" class="text-button">View request & response <span class="ico" style="--ico:url(/static/icons/arrow-up-right.svg)" aria-hidden="true"></span></a>`:''}</div>${proof?.sha256?`<small class="digest">Response SHA-256: ${esc(proof.sha256)}</small>`:''}</article>`;
  }).join('');
  $('weather-basis').textContent=`WEATHER USED / ${farm.weather.mode==='live_fetch'?'FETCHED FORECAST':farm.weather.mode==='unavailable'?'STALE / EXCLUDED':'BUNDLED SCENARIO'}`;
  $('weather-explanation').textContent=farm.weather.mode==='live_fetch'?'Forecast downloaded by this app. Model issue time is not supplied; generationtime_ms is server processing duration, not a timestamp. Weather is excluded after six hours or when its first day is no longer today.':'The bundled window is a demonstration, not current evidence. A stale fetched forecast is excluded rather than silently replaced with the bundle.';
  const profile=farm.risk_profile;
  $('risk-breakdown').innerHTML=`<div><span class="eyebrow">RISK PROFILE / ${esc(profile.rule_version)}</span><h3>Why this farm is number ${farm.rank}.</h3><p>Water stress: <strong>${esc(profile.water_stress)}</strong> · Drainage: <strong>${esc(profile.drainage)}</strong></p><p class="hint">${esc(profile.confidence)}. Missing soil never means zero risk.${profile.learning_basis.length?` Learned: ${esc(profile.learning_basis.join('; '))}.`:''}</p></div><div class="score-equation"><span>${profile.environment_points}<small>environment</small></span><b>+</b><span>${profile.report_points}<small>farmer report</small></span><b>+</b><span>${profile.officer_points}<small>Felix correction</small></span><b>+</b><span>${profile.learning_points}<small>learned from visits</small></span><b>+</b><span>${profile.completion_adjustment}<small>completion</small></span><b>=</b><span>${farm.score}<small>triage points</small></span></div><details><summary>Show the rules and evidence used</summary><p>Dry flag: rain below 3 mm and maximum temperature at least 30 °C → 62 base points. Drainage flag: current forecast rain at least 25 mm and mapped clay at least 35% → 75. Otherwise 25 routine scheduling points. Unreviewed concern +55; normal answer without an open concern −15; officer correction +30 or −20; completion sets zero.</p><p>Weather receipt: ${profile.weather_receipt_id??'none / bundled or unavailable'} · Soil receipt: ${profile.soil_receipt_id??'none'} · Evaluated ${esc(stamp(profile.evaluated_at))}. The map adds no score. These thresholds are prototype rules and have not been tested against crop outcomes.</p></details>`;
  $('survey-target').textContent=`Current profile suggests asking: “${farm.question}”`;
  const queued=farm.surveys.find(s=>s.status==='queued');
  $('survey-invitation').innerHTML=queued?`<strong>LOCAL DRAFT #${queued.id} · not sent</strong><p>${esc(queued.question)}</p><small>Queued ${esc(stamp(queued.created_at))}<br>Trigger: ${esc(queued.trigger)}<br>At queue time: ${queued.before.score} points · rank ${queued.before.rank}</small>`:'<p class="hint">Queue the question to preserve the evidence that triggered it. You can also simulate a check-in directly.</p>';
  const answered=farm.surveys.find(s=>s.status==='answered');
  if(answered){
    const before=answered.response_before || answered.before, after=answered.after, delta=after.score-before.score;
    $('survey-impact').innerHTML=`<span class="eyebrow">SURVEY #${answered.id}</span><h2>What the farmer’s answer changed</h2><div class="impact-values"><div><strong>${before.score}</strong><span>before this reply · rank ${before.rank}</span></div><b>→</b><div><strong>${after.score}</strong><span>after this reply · rank ${after.rank}</span></div><div><strong>${signed(delta)}</strong><span>change in triage points</span></div></div><p><strong>Officer action:</strong> ${esc(after.action)} · ${esc(after.status)}.</p><p class="hint">Recorded ${esc(stamp(answered.responded_at))}. Participation choice: ${esc(answered.notice_version)} at ${esc(stamp(answered.consented_at))}. It records the score before and after the answer; it does not test whether the score was right. Felix still reviews the report.</p>`;
  } else $('survey-impact').innerHTML='<span class="eyebrow">WHAT WE CAN DO WITH THE DATA</span><h2>No farmer answer yet for this farm</h2><p>Run a simulated check-in above. This panel then shows the score and queue position before and after the answer, plus the resulting officer action.</p>';
  $('privacy-export').href=`/api/felix/farms/${encodeURIComponent(selected)}/privacy-export`;
}

async function reloadEvidence() {
  [data,mapData]=await Promise.all([api('/api/felix/dashboard'),api('/api/felix/map')]);
  render();
}

async function fetchEvidence(sources) {
  if(evidenceBusy)return;
  evidenceBusy=true;
  const fid=selected;
  document.querySelectorAll('button,select,input,textarea').forEach(el=>el.disabled=true);
  feedback(`Requesting ${sources.join(', ')} for ${fid}. Waiting for provider responses…`);
  try {
    const results=await Promise.allSettled(sources.map(source=>api(`/api/felix/farms/${fid}/evidence/${source}`,{})));
    await reloadEvidence();
    const messages=results.map((result,i)=>result.status==='fulfilled'?`${sources[i]}: retrieval saved`:`${sources[i]}: ${result.reason.message}`);
    feedback(messages.join(' · '),results.some(r=>r.status==='rejected'));
  } catch(error){feedback(error.message,true);}
  finally {
    evidenceBusy=false;
    document.querySelectorAll('button,select,input,textarea').forEach(el=>el.disabled=false);
    if(data)$('plan-toggle').disabled=data.farms.find(f=>f.id===selected).completed;
  }
}

document.addEventListener('DOMContentLoaded',()=>{
  $('evidence-farm').addEventListener('change',event=>selectFarm(event.target.value));
  $('fetch-evidence').addEventListener('click',()=>fetchEvidence(['weather','soil','map']));
  $('evidence-cards').addEventListener('click',event=>{
    const button=event.target.closest('[data-fetch]');if(button)fetchEvidence([button.dataset.fetch]);
  });
  $('queue-survey').addEventListener('click',()=>save('surveys',{},'Survey invitation queued locally. No message was sent.'));
  $('erase-reports').addEventListener('click',async()=>{
    if(!confirm('Delete this demo farm’s local survey history, reports, corrections and visit notes? Environmental evidence and other farms remain.'))return;
    try {
      const response=await Fieldwise.fetch(`/api/felix/farms/${encodeURIComponent(selected)}/reports`,{method:"DELETE"});
      if(!response.ok)throw new Error('Could not delete the local reports.');
      $('checkin').hidden=true;$('survey-consent').checked=false;activeSurvey=null;
      await reloadEvidence();feedback('Selected farm’s local reports deleted. Public environmental evidence retained.');
    } catch(error){feedback(error.message,true);}
  });
});
