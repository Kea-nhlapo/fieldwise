let referenceSnapshot = null, referenceStale = false, diseaseFormFarm = null;
const observationLabels = {symptoms:'Symptoms noticed', none:'None noticed', uncertain:'Unsure / needs follow-up'};
function renderDisease(farm) {
  $('disease-farm-name').textContent = farm.name;
  if (diseaseFormFarm !== farm.id) {
    $('disease-notes').value = ''; $('disease-draft-result').textContent = '';
    diseaseFormFarm = farm.id;
  }
  const previousTopic = $('disease-topic').value;
  $('disease-topic').innerHTML = farm.disease.conditions.map(c=>`<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('');
  if ([...$('disease-topic').options].some(o=>o.value===previousTopic)) $('disease-topic').value = previousTopic;
  $('disease-cards').innerHTML = farm.disease.conditions.map(c=>`<article class="disease-condition"><div class="disease-condition-top"><h4>${esc(c.name)}</h4><span class="unassessed">${esc(c.assessment)}</span></div><p>${c.observation ? 'Latest simulated report: '+esc(observationLabels[c.observation.status]) : 'No farmer observation recorded.'}</p>${c.observation ? `<small>${esc(new Date(c.observation.recorded_at).toLocaleString('en-ZA'))}${c.observation.notes?' · '+esc(c.observation.notes):''}</small>` : ''}<small>No disease forecast is available for this field.</small>${c.alert?`<p class="disease-reason">Officer alert: ${esc(c.alert.state)}${c.alert.state!=='resolved'?' · priority floor '+c.alert.priority_floor:''}</p>`:''}</article>`).join('');
  const alerts = data.disease_alerts;
  const active = alerts.filter(a=>a.state!=='resolved');
  $('disease-alert-count').textContent = `${active.length} active alert${active.length===1?'':'s'}`;
  $('disease-alerts').innerHTML = alerts.length ? alerts.map(a=>{
    const name = data.farms.find(f=>f.id===a.farm_id)?.name || a.farm_id;
    return `<article class="officer-alert" data-alert-id="${a.id}"><div><h4>${esc(name)} · ${esc(a.disease_name)}</h4><p>${esc(a.summary)}</p><p>Last update ${esc(new Date(a.updated_at).toLocaleString('en-ZA'))}${a.state!=='resolved'?` · Inspection-priority floor ${a.priority_floor}`:''}</p></div><div class="alert-actions"><span class="state-pill ${a.state}">${esc(a.state)}</span>${a.state==='open'?`<button class="outline-button" data-review="acknowledged" data-id="${a.id}">Acknowledge</button>`:''}${a.state!=='resolved'?`<button class="outline-button" data-review="resolved" data-id="${a.id}">Resolve after review</button>`:''}</div></article>`;
  }).join('') : '<p class="empty">No disease-observation alerts. Record a farmer signal to add a local notification for Felix.</p>';
  document.querySelectorAll('[data-review]').forEach(button=>button.onclick=()=>action(button,async()=>{
    await api(`/api/disease/alerts/${button.dataset.id}`,{method:'PATCH',body:JSON.stringify({state:button.dataset.review})});
    await load(); invalidateRoute(); toast('Officer review saved. Inspection priorities updated.');
  }));
}

function renderReference() {
  const snapshot = referenceSnapshot;
  const provenance = $('reference-provenance');
  if (!snapshot) {
    provenance.textContent = 'No reference loaded for this selection. Fetch from UW, load a saved reference, or use the offline sample.';
    provenance.classList.remove('live'); $('reference-station').innerHTML = ''; $('reference-chart').innerHTML=''; $('reference-rows').innerHTML='';
    return;
  }
  provenance.classList.toggle('live',!snapshot.synthetic);
  provenance.textContent = snapshot.synthetic
    ? 'SYNTHETIC OFFLINE SAMPLE. Fictional stations and illustrative risk curves, not UW forecasts. Sample window: '+snapshot.target_date+'. This never changes local farm priorities.'
    : `${referenceStale?'STALE SAVED REFERENCE. ':''}${snapshot.source} · Wisconsin, USA · Forecast target ${snapshot.target_date}, ${snapshot.risk_days} day(s) · Retrieved ${new Date(snapshot.fetched_at).toLocaleString('en-ZA')}. Reference only; not applicable to local farms.`;
  const disease = $('reference-disease').value;
  const records = snapshot.records.filter(r=>r.disease_id===disease);
  const stations = [...new Map(records.map(r=>[r.station_id,r.station_name])).entries()];
  const previous = $('reference-station').value;
  $('reference-station').innerHTML = stations.map(([id,name])=>`<option value="${esc(id)}">${esc(name)}</option>`).join('');
  if(stations.some(([id])=>id===previous)) $('reference-station').value=previous;
  const rows = records.filter(r=>r.station_id===$('reference-station').value).sort((a,b)=>a.date.localeCompare(b.date));
  $('reference-rows').innerHTML = rows.map(r=>`<tr><td>${esc(r.date)}</td><td>${r.risk===null?'—':Number(r.risk).toFixed(2)}</td><td class="risk-${r.risk_class.toLowerCase().replaceAll(' ','-')}">${esc(r.risk_class)}</td></tr>`).join('');
  if(!rows.length) {$('reference-chart').innerHTML='<p class="empty">No station records for this disease.</p>';return;}
  const width=700,height=220,left=42,right=18,top=18,bottom=35;
  const x=i=>rows.length===1?width/2:left+i*(width-left-right)/(rows.length-1), y=v=>height-bottom-v*(height-top-bottom);
  let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${snapshot.synthetic?'Synthetic example':'UW reference'} disease risk trend, index from zero to one"><title>${snapshot.synthetic?'Synthetic illustrative curve, not a forecast':'Wisconsin reference risk trend'}</title>`;
  for(const v of [0,.25,.5,.75,1]) svg+=`<line x1="${left}" y1="${y(v)}" x2="${width-right}" y2="${y(v)}" stroke="#e6ecdf"/><text x="${left-10}" y="${y(v)+3}" text-anchor="end" font-size="10" fill="#829176">${v.toFixed(2)}</text>`;
  let segment=[];
  const flush=()=>{if(segment.length) svg+=`<polyline points="${segment.join(' ')}" fill="none" stroke="#769348" stroke-width="2.5"/>`;segment=[];};
  rows.forEach((r,i)=>{if(r.risk===null){flush();}else{segment.push(`${x(i)},${y(r.risk)}`);}});flush();
  rows.forEach((r,i)=>{if(r.risk!==null)svg+=`<circle cx="${x(i)}" cy="${y(r.risk)}" r="3.5" fill="#5a783b"/>`; if(i===0||i===rows.length-1||i===Math.floor(rows.length/2))svg+=`<text x="${x(i)}" y="${height-9}" text-anchor="middle" font-size="10" fill="#829176">${esc(r.date.slice(5))}</text>`;});
  if(rows.every(r=>r.risk===null))svg+=`<text x="${width/2}" y="${height/2}" text-anchor="middle" font-size="13" fill="#7c8a73">No active numeric risk values for this selection</text>`;
  $('reference-chart').innerHTML=svg+'</svg>';
}

document.addEventListener('DOMContentLoaded',()=>{
  $('disease-observation-form').onsubmit=event=>{
    event.preventDefault(); const fid=selected;
    action($('save-observation'),async()=>{
      await api(`/api/farms/${fid}/disease-observations`,{method:'POST',body:JSON.stringify({disease_id:$('disease-topic').value,status:$('disease-status').value,notes:$('disease-notes').value})});
      $('disease-notes').value=''; await load(); invalidateRoute(); toast('Observation saved. Felix’s local alert queue and priorities updated.');
    });
  };
  $('disease-draft').onclick=()=>action($('disease-draft'),async()=>{
    const fid=selected;
    const result=await api(`/api/farms/${fid}/disease-outreach`,{method:'POST',body:JSON.stringify({disease_id:$('disease-topic').value})});
    await load(); if(selected===fid)$('disease-draft-result').textContent='Local draft, not sent: '+result.text;
    toast('Disease question saved locally. No SMS sent.');
  });
  const query=()=>`?target_date=${encodeURIComponent($('reference-date').value)}&risk_days=${$('reference-days').value}`;
  $('fetch-reference').onclick=()=>action($('fetch-reference'),async()=>{
    const requested=query(); $('reference-error').hidden=true;
    try {
      const result=await api('/api/disease/reference'+requested,{method:'POST'});
      if(query()!==requested)return;
      referenceSnapshot=result.snapshot;referenceStale=false;renderReference();
    } catch(error) {
      $('reference-error').textContent=error.message+' No disease forecast was applied to local farms.';
      $('reference-error').hidden=false;
    }
  });
  $('cached-reference').onclick=()=>action($('cached-reference'),async()=>{
    const requested=query(); const result=await api('/api/disease/reference'+requested);
    if(query()!==requested)return;
    referenceSnapshot=result.snapshot;referenceStale=result.stale;renderReference();
    $('reference-error').hidden=true;
  });
  const sample=async()=>{
    referenceSnapshot=await api('/api/disease/reference/demo');referenceStale=false;
    $('reference-date').value=referenceSnapshot.target_date;$('reference-days').value=String(referenceSnapshot.risk_days);
    $('reference-error').hidden=true;renderReference();
  };
  $('sample-reference').onclick=()=>action($('sample-reference'),sample);
  ['reference-date','reference-days'].forEach(id=>$(id).onchange=()=>{referenceSnapshot=null;renderReference();$('reference-error').hidden=true;});
  ['reference-disease','reference-station'].forEach(id=>$(id).onchange=renderReference);
  sample().catch(error=>{$('reference-provenance').textContent=error.message;});
  if(data)renderDisease(data.farms.find(f=>f.id===selected)||data.farms[0]);
});
