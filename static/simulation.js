'use strict';
const $ = id => document.getElementById(id);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const RULES = [['rotation', 'Basic rotation'], ['officer', 'Experienced officer'], ['fieldwise', 'Fieldwise']];
const COLOR = {rotation: '#6f7871', officer: '#a5621b', fieldwise: '#2f6b43'};
const pct = v => `${Number(v).toFixed(1)}%`;
const pts = v => `${v > 0 ? '+' : v < 0 ? '−' : '±'}${Math.abs(v).toFixed(1)} points`;
const record = d => `ahead in ${d.ahead}, tied in ${d.tied}, behind in ${d.behind} of ${d.runs} seasons`;
let data, rule = 'fieldwise';

function bars(target, groups, opts = {}) {
  const width = opts.width || 720, height = opts.height || 260, left = 40, right = 10, top = 16, bottom = 36;
  const plotW = width - left - right, plotH = height - top - bottom, max = 100;
  const y = v => top + plotH - (v / max) * plotH;
  const groupW = plotW / groups.length, barW = Math.min(46, (groupW - 24) / RULES.length);
  let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(opts.label)}">`;
  for (const v of [0, 25, 50, 75, 100]) svg += `<line x1="${left}" x2="${width - right}" y1="${y(v)}" y2="${y(v)}" stroke="#e4e1d4"/><text x="${left - 6}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="#56635b">${v}%</text>`;
  groups.forEach((g, i) => {
    const x0 = left + i * groupW + (groupW - barW * RULES.length - 4 * (RULES.length - 1)) / 2;
    RULES.forEach(([key, name], j) => {
      const v = g.values[key], x = x0 + j * (barW + 4), h = Math.max(0, y(0) - y(v)), r = Math.min(4, h / 2);
      svg += `<g class="bar"><title>${esc(g.label)} · ${name}: ${pct(v)}${g.range ? ` (5–95%: ${pct(g.range[key][0])}–${pct(g.range[key][1])})` : ''}</title>`
        + `<rect x="${x - 2}" y="${top}" width="${barW + 4}" height="${plotH}" fill="transparent"/>`
        + (h ? `<path d="M${x},${y(0)} V${y(v) + r} q0,-${r} ${r},-${r} H${x + barW - r} q${r},0 ${r},${r} V${y(0)} Z" fill="${COLOR[key]}"/>` : '');
      if (g.range) { const [lo, hi] = g.range[key]; svg += `<line x1="${x + barW / 2}" x2="${x + barW / 2}" y1="${y(lo)}" y2="${y(hi)}" stroke="#14261f" stroke-width="1.5"/><line x1="${x + barW / 2 - 5}" x2="${x + barW / 2 + 5}" y1="${y(hi)}" y2="${y(hi)}" stroke="#14261f" stroke-width="1.5"/><line x1="${x + barW / 2 - 5}" x2="${x + barW / 2 + 5}" y1="${y(lo)}" y2="${y(lo)}" stroke="#14261f" stroke-width="1.5"/>`; }
      svg += `<text x="${x + barW / 2}" y="${(g.range ? y(g.range[key][1]) : y(v)) - 6}" text-anchor="middle" font-size="12" font-weight="600" fill="#14261f">${Math.round(v)}%</text></g>`;
    });
    svg += `<text x="${left + i * groupW + groupW / 2}" y="${height - 12}" text-anchor="middle" font-size="13" fill="#14261f">${esc(g.label)}</text>`;
  });
  $(target).innerHTML = svg + '</svg>';
}

function table(rows, head) {
  return `<table class="reference-table"><thead><tr>${head.map(h => `<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map((c, i) => i ? `<td>${c}</td>` : `<th scope="row">${c}</th>`).join('')}</tr>`).join('')}</tbody></table>`;
}

function render() {
  const m = data.main, P = m.policies, vsRot = m.fieldwise_minus_rotation, vsOff = m.fieldwise_minus_officer;
  $('hero-stats').innerHTML = RULES.map(([k, name]) => `<div class="hero-stat"><strong>${Math.round(P[k].mean)}<small>%</small></strong><span>${name}</span><em>reached within 7 days · 5–95%: ${Math.round(P[k].p5)}–${Math.round(P[k].p95)}%</em></div>`).join('')
    + `<div class="hero-stat"><strong>${m.runs}</strong><span>simulated seasons, ${m.problems_per_run} new problems each on average</span></div>`;
  const mln = m.by_kind_vs_officer.mln, faw = m.by_kind_vs_officer.faw, s = data.no_signal_strict;
  $('verdict').innerHTML = [
    `Fieldwise reached <strong>${pct(P.fieldwise.mean)}</strong> of new problems within 7 days, against <strong>${pct(P.rotation.mean)}</strong> for a basic rotation. It did better than rotation in ${vsRot.ahead} of ${vsRot.runs} seasons.`,
    `An experienced officer who chases farmer reports reached <strong>${pct(P.officer.mean)}</strong>. Fieldwise’s overall edge over that officer is small and not consistent: ${pts(vsOff.mean)} on average, ${record(vsOff)}.`,
    `Most of the difference comes from MLN. Fieldwise reached ${pct(P.fieldwise.mln_reach)} of MLN cases against the officer’s ${pct(P.officer.mln_reach)}, by visiting farms next to known MLN. On fall armyworm they were level (${pct(P.fieldwise.faw_reach)} and ${pct(P.officer.faw_reach)}), because both act on farmer reports.`,
    `With every signal scrambled, Fieldwise was no better than rotation (${pts(s.fieldwise_minus_rotation.mean)}, ${record(s.fieldwise_minus_rotation)}). So the advantage comes from the data.`,
  ].map(t => `<li>${t}</li>`).join('');
  $('legend').innerHTML = RULES.map(([k, n]) => `<span><i style="background:${COLOR[k]}"></i>${n}</span>`).join('');
  const range = key => ({rotation: [P.rotation.p5, P.rotation.p95], officer: [P.officer.p5, P.officer.p95], fieldwise: [P.fieldwise.p5, P.fieldwise.p95]});
  bars('kind-chart', [
    {label: 'All problems', values: {rotation: P.rotation.mean, officer: P.officer.mean, fieldwise: P.fieldwise.mean}, range: range()},
    {label: 'Fall armyworm', values: Object.fromEntries(RULES.map(([k]) => [k, P[k].faw_reach]))},
    {label: 'Maize lethal necrosis', values: Object.fromEntries(RULES.map(([k]) => [k, P[k].mln_reach]))},
  ], {label: 'Bar chart of 7-day reach by problem type for each scheduling rule; values are in the table below.'});
  $('kind-table').innerHTML = table(RULES.map(([k, n]) => [n, pct(P[k].mean), `${pct(P[k].p5)}–${pct(P[k].p95)}`, pct(P[k].faw_reach), pct(P[k].mln_reach)]),
    ['Rule', 'All problems', '5–95% of seasons', 'Fall armyworm', 'MLN']);

  for (const [key, chart, text] of [['no_signal', 'chart-nosignal', 'text-nosignal'], ['no_signal_strict', 'chart-strict', 'text-strict']]) {
    const r = data[key];
    bars(chart, [{label: 'All problems', values: Object.fromEntries(RULES.map(([k]) => [k, r.policies[k].mean]))},
                 {label: 'MLN', values: Object.fromEntries(RULES.map(([k]) => [k, r.policies[k].mln_reach]))}],
         {width: 420, height: 220, label: `Bar chart of 7-day reach with ${r.signal} signals`});
    $(text).innerHTML = `Fieldwise vs rotation: <strong>${pts(r.fieldwise_minus_rotation.mean)}</strong>, ${record(r.fieldwise_minus_rotation)}.`;
  }
  $('text-nosignal').innerHTML += ' The remaining MLN gain comes from Felix’s own confirmed finds pointing to neighbouring farms. That is real information, so the stricter test removes it too.';
  $('text-strict').innerHTML += ' With no real signal, Fieldwise does no better than visiting farms in turn.';

  $('ablation').innerHTML = table(Object.entries(data.ablation).map(([name, v]) => [esc(name), pct(v.reach), pct(v.mln_reach), `${pts(v.vs_officer.mean)}<br><small>${v.vs_officer.ahead} ahead · ${v.vs_officer.tied} tied · ${v.vs_officer.behind} behind</small>`]),
    ['Fieldwise version', '7-day reach', 'MLN reach', 'vs experienced officer'])
    + '<p class="hint">Switching off weather made no difference in this simulation. Switching off nearby MLN took Fieldwise back to the officer’s level.</p>';
  $('sensitivity').innerHTML = table(Object.entries(data.sensitivity).map(([name, v]) => [esc(name), pct(v.reach), pts(v.vs_rotation.mean), pts(v.vs_officer.mean)]),
    ['Weather and neighbour weights', '7-day reach', 'vs rotation', 'vs officer']);

  bars('scale-chart', data.scale.map(sc => ({label: `${sc.farms.toLocaleString('en')} farms`, values: sc.policies})),
       {label: 'Bar chart of 7-day reach at 100, 250 and 1,000 farms per officer'});
  $('scale-table').innerHTML = table(data.scale.map(sc => [`${sc.farms.toLocaleString('en')} farms`, ...RULES.map(([k]) => pct(sc.policies[k])), `${pts(sc.vs_officer.mean)} (${sc.runs} seasons)`]),
    ['Caseload', ...RULES.map(r => r[1]), 'Fieldwise vs officer']);
  const [s100, s250, s1000] = data.scale;
  $('scale-text').innerHTML = `Reach falls for every rule as the caseload grows: rotation reaches ${pct(s1000.policies.rotation)} at 1,000 farms. Fieldwise trailed the officer at 250 farms (${pts(s250.vs_officer.mean)}) and led at 1,000 (${pts(s1000.vs_officer.mean)}, from ${s1000.runs} seasons). We report the 250-farm result as it came out.`;

  renderExample();
  const label = {farms: 'Farms', farms_per_cluster: 'Farms per village', days: 'Season length (days)', visits_per_day: 'Visits per day', working_days_per_week: 'Working days per week',
    centre: 'Area centre (lat, lon)', area_half_width_deg: 'Village spread for 100 farms (± degrees)', cluster_sd_deg: 'Farm spread within a village (degrees)', faw_daily_risk: 'Fall armyworm daily chance per farm',
    faw_weather_gain: 'Weather multiplier (risk 0–1)', mln_first_cases: 'First MLN cases', mln_background_risk: 'MLN background daily chance', mln_risk_per_infected_neighbour: 'Extra MLN daily chance per infected farm within 2 km',
    neighbour_km: 'Neighbour distance (km)', report_chance: 'Share of real problems reported', report_delay_days: 'Report delay (days)', false_reports_per_farm_day: 'False reports per farm per day',
    weather_noise: 'Weather error (±)', reach_window_days: 'Reach window (days)', daily_risk: 'Base daily risk', weather_gain: 'Weather weight', neighbour_gain: 'Weight per known MLN neighbour', report_weight: 'Chance a report is real'};
  const fmt = v => Array.isArray(v) ? v.join(', ') : v;
  $('assumption-table').innerHTML = table(Object.entries(data.assumptions).map(([k, v]) => [esc(label[k] || k), esc(fmt(v))]), ['Assumption', 'Value']);
  $('prior-table').innerHTML = table(Object.entries(data.fieldwise_prior).map(([k, v]) => [esc(label[k] || k), esc(fmt(v))]), ['Fieldwise weight', 'Value'])
    + '<p class="hint">Set from rules of thumb and deliberately different from the true rates. Fieldwise never sees the simulation’s formulas.</p>';
  $('provenance').textContent = `Generated ${new Date(data.generated_at).toLocaleString('en-GB')} from commit ${data.commit || 'unknown'} by scripts/run_simulation.py (seeded; rerun to reproduce).`;
}

function renderExample() {
  const e = data.example;
  if (!e) { $('example-title').textContent = 'No example day found'; return; }
  $('example-title').textContent = `Day ${e.day} of one simulated season`;
  $('example-note').textContent = 'Chosen to show both mechanisms on one day, not as a typical day. The averages above come from all 200 seasons.';
  const farms = e.farms, lats = farms.map(f => f.lat), lons = farms.map(f => f.lon);
  const [minLat, maxLat, minLon, maxLon] = [Math.min(...lats), Math.max(...lats), Math.min(...lons), Math.max(...lons)];
  const W = 520, H = 420, pad = 22;
  const sx = lon => pad + (lon - minLon) / (maxLon - minLon) * (W - 2 * pad), sy = lat => pad + (maxLat - lat) / (maxLat - minLat) * (H - 2 * pad);
  const probs = {}; e.problems_today.forEach(p => (probs[p.farm] = probs[p.farm] || []).push(p.kind));
  const picked = new Set(e.picks[rule].map(p => p.farm));
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Map of 100 simulated farms around Bomet. ${picked.size} farms visited today by ${esc(RULES.find(r => r[0] === rule)[1])}; details in the list beside the map.">`;
  svg += `<rect width="${W}" height="${H}" rx="12" fill="#eef1e4"/>`;
  for (const f of farms) {
    const x = sx(f.lon), y = sy(f.lat), k = probs[f.id] || [];
    svg += `<g><title>Farm ${f.id}${k.length ? ' · ' + k.map(v => v === 'faw' ? 'fall armyworm' : 'MLN').join(', ') : ''}${picked.has(f.id) ? ' · visited today' : ''}</title>`;
    if (k.includes('mln')) svg += `<circle cx="${x}" cy="${y}" r="9" fill="none" stroke="#7b3fa0" stroke-width="2.5"/>`;
    if (k.includes('faw')) svg += `<circle cx="${x}" cy="${y}" r="${k.includes('mln') ? 12.5 : 9}" fill="none" stroke="#c0662f" stroke-width="2.5"/>`;
    svg += `<circle cx="${x}" cy="${y}" r="${picked.has(f.id) ? 7 : 4}" fill="${picked.has(f.id) ? '#123329' : '#8a9488'}" stroke="#fff" stroke-width="${picked.has(f.id) ? 2 : 1}"/></g>`;
  }
  $('sim-map').innerHTML = svg + '</svg>';
  const kind = k => k === 'faw' ? 'fall armyworm' : 'MLN';
  $('picks').innerHTML = `<h3>${esc(RULES.find(r => r[0] === rule)[1])} visits on day ${e.day}</h3><ol class="sim-picks">${e.picks[rule].map(p => {
    const why = rule !== 'fieldwise' ? '' : [p.report ? `farmer reported ${kind(p.report)}` : '', p.mln_neighbours ? `${p.mln_neighbours} known MLN farm${p.mln_neighbours > 1 ? 's' : ''} within 2 km` : '',
      p.days_since_visit != null ? `${p.days_since_visit} days since last visit` : 'not visited yet this season'].filter(Boolean).join(' · ');
    return `<li><strong>Farm ${p.farm}</strong>${p.finds.length ? ` <span class="find">finds ${p.finds.map(kind).join(' and ')}</span>` : ' <span class="nofind">nothing new</span>'}${why ? `<small>${esc(why)}</small>` : ''}</li>`;
  }).join('')}</ol>`;
  const when = d => d == null ? 'not within the season' : `day ${d}`;
  $('spotlight').innerHTML = e.spotlight.map(s => `<div class="spot"><h4>${s.kind === 'faw' ? 'Farmer report: fall armyworm' : 'Nearby farms: MLN'} on farm ${s.farm}</h4><p>Started on day ${s.onset}${s.kind === 'mln' ? ', unreported' : ''}. First visit while present:</p><ul>${RULES.map(([k, n]) => `<li>${n}: <strong>${when(s.first_visit[k])}</strong></li>`).join('')}</ul></div>`).join('');
}

document.addEventListener('click', event => {
  const b = event.target.closest('[data-rule]');
  if (!b || !data) return;
  rule = b.dataset.rule;
  document.querySelectorAll('[data-rule]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  renderExample();
});
document.addEventListener('DOMContentLoaded', async () => {
  try {
    const response = await Fieldwise.fetch('/api/simulation');
    if (!response.ok) throw new Error('Simulation results are not available yet.');
    data = await response.json();
    render();
  } catch (error) { $('load-error').textContent = error.message; $('load-error').hidden = false; }
});
