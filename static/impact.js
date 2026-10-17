'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// The headline row shows activity and a measured outcome only; model estimates stay in their own group.
const HERO = {
  farmer_signals: 'farmer signals collected',
  survey_response: 'of survey invitations answered',
  decisions_changed: 'of answers moved a farm’s priority',
  confirmed_visits: 'of visits with an outcome confirmed a problem',
};
const LABELS = {farmer_signal:'Farmer signal', priority_shift:'Priority shift', survey_queued:'Survey queued', survey_answered:'Survey answered',
  visit_recorded:'Visit recorded', officer_override:'Officer review', evidence_fetch:'Live data fetch', offline_sync:'Offline sync', erasure:'Erasure'};
const when = iso => new Date(iso).toLocaleString('en-ZA', {day:'numeric', month:'short', hour:'2-digit', minute:'2-digit', second:'2-digit'});

function tile(m) {
  const ratio = m.denominator != null ? `<span class="ratio">${m.numerator} of ${m.denominator}</span>` : '';
  const value = m.value == null ? '<strong class="none">No data yet</strong>' : `<strong>${esc(m.value)}<small>${m.unit === '%' ? '%' : ' ' + esc(m.unit)}</small></strong>`;
  const bar = m.unit === '%' && m.value != null ? `<span class="meter" aria-hidden="true"><i style="width:${m.value}%"></i></span>` : '';
  const badge = m.group === 'estimate' ? '<span class="estimate-badge">MODEL ESTIMATE</span>' : '';
  return `<article class="impact-tile${m.group === 'estimate' ? ' estimate' : ''}">${badge}<h3>${esc(m.label)}</h3>${value}${bar}${ratio}<p>${esc(m.definition)}</p></article>`;
}

function chart(days) {
  if (!days.length) { $('trend-chart').innerHTML = '<p class="empty">No events yet. Record a farmer reply or check-in to start the log.</p>'; return; }
  const width = 640, height = 200, left = 34, right = 8, top = 12, bottom = 28;
  const max = Math.max(4, ...days.map(d => d.signals));
  const step = (width - left - right) / days.length, bar = Math.min(28, step * .6);
  const y = v => height - bottom - v / max * (height - top - bottom);
  let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Bar chart of farmer signals collected per day; the same figures are in the table below.">`;
  for (const v of [0, Math.round(max / 2), max]) svg += `<line x1="${left}" x2="${width - right}" y1="${y(v)}" y2="${y(v)}" stroke="#e4e9df"/><text x="${left - 6}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="#56635b">${v}</text>`;
  days.forEach((d, i) => {
    const x = left + i * step + (step - bar) / 2, h = Math.max(0, y(0) - y(d.signals));
    // Square bottom on the baseline, 4px rounded top; a wider transparent hit target carries the tooltip.
    const r = Math.min(4, h / 2, bar / 2);
    svg += `<g class="bar"><title>${esc(d.date)}: ${d.signals} farmer signal${d.signals === 1 ? '' : 's'}, ${d.visits} visit${d.visits === 1 ? '' : 's'}</title>`
      + `<rect x="${left + i * step}" y="${top}" width="${step}" height="${height - top - bottom}" fill="transparent"/>`
      + (h ? `<path d="M${x},${y(0)} V${y(0) - h + r} q0,-${r} ${r},-${r} H${x + bar - r} q${r},0 ${r},${r} V${y(0)} Z" fill="#34674e"/>` : '') + '</g>';
    if (days.length <= 10 || i === 0 || i === days.length - 1) svg += `<text x="${x + bar / 2}" y="${height - 8}" text-anchor="middle" font-size="11" fill="#56635b">${esc(d.date.slice(5))}</text>`;
  });
  $('trend-chart').innerHTML = svg + '</svg>';
}

async function load() {
  const response = await Fieldwise.fetch('/api/impact');
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || 'Could not load impact metrics.');
  const byId = Object.fromEntries(data.metrics.map(m => [m.id, m]));
  $('hero-stats').innerHTML = Object.entries(HERO).map(([id, label]) => { const m = byId[id];
    return `<div class="hero-stat" title="${esc(m.definition)}"><strong>${m.value == null ? '–' : esc(m.value)}${m.unit === '%' && m.value != null ? '<small>%</small>' : ''}</strong><span>${esc(label)}</span>${m.denominator != null ? `<em>${m.numerator} of ${m.denominator}</em>` : ''}</div>`; }).join('');
  for (const group of ['outcome', 'activity', 'estimate'])
    $('tiles-' + group).innerHTML = data.metrics.filter(m => m.group === group && !(m.id in HERO)).map(tile).join('') || '<p class="empty">No metrics in this group yet.</p>';
  $('tracking').textContent = data.tracking_since ? `Tracking since ${when(data.tracking_since)}` : 'No events logged yet';
  const cached = response.headers.get('X-Fieldwise-Offline') === 'cached';
  $('generated').textContent = `${data.event_count} events · computed ${when(data.generated_at)}${cached ? ' · offline copy' : ''}`;
  $('privacy-note').textContent = data.privacy;
  chart(data.daily);
  $('trend-rows').innerHTML = data.daily.map(d => `<tr><td>${esc(d.date)}</td><td>${d.signals}</td><td>${d.visits}</td></tr>`).join('') || '<tr><td colspan="3">No events yet.</td></tr>';
  $('workspace-split').textContent = Object.values(data.workspaces).map(w => `${w.label}: ${w.signals} signal${w.signals === 1 ? '' : 's'}, ${w.visits} visit${w.visits === 1 ? '' : 's'}`).join(' · ');
  $('log-rows').innerHTML = data.recent.map(e => `<tr><td><time datetime="${esc(e.created_at)}">${esc(when(e.created_at))}</time></td><td>${esc(LABELS[e.kind] || e.kind)}</td><td>${e.workspace === 'sa' ? 'South Africa' : 'Kasungu'}</td><td>${esc(e.detail)}</td><td>${e.value == null ? '—' : esc(Math.round(e.value * 10) / 10)}</td></tr>`).join('') || '<tr><td colspan="5">No events yet.</td></tr>';
}

document.addEventListener('fieldwise:synced', () => load().catch(() => {}));
document.addEventListener('DOMContentLoaded', () => load().catch(error => { $('privacy-note').textContent = error.message; }));
