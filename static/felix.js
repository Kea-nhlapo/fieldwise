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
// Map drawing helpers. A street-map look drawn entirely offline: the roads and rivers from
// the bundled or fetched extract, plus real OpenStreetMap building footprints, river names,
// route numbers and named places from static/kasungu/kasungu_detail.json
// (built by scripts/build-map-detail.cjs). Farm pins are the fictional scenario locations.
let mapDetail = null, mapDetailCache = null, mapDragged = false;
const mapView = {zoom:1, cx:null, cy:null, shown:null};
const MAP_PAN = [-75, 675];  // projected extent covered by the detail file
const MAP_POI = {
  health:{color:'#d93025', glyph:'M-1.4-4.5h2.8v3.1h3.1v2.8h-3.1v3.1h-2.8v-3.1h-3.1v-2.8h3.1z'},
  food:{color:'#e8710a', glyph:'M-3.6-4.6h.7v3h.6v-3h.6v3h.6v-3h.7v3.4c0 .8-.5 1.3-1.1 1.5v4.3h-1V.3c-.6-.2-1.1-.7-1.1-1.5zM2.1-4.6c1.3 0 2 1.4 2 3.4v1.2h-1v4.6h-1z'},
  shop:{color:'#1a73e8', glyph:'M-4.2-1.8h8.4l-.8 6.3h-6.8zM-2.1-1.8v-.9a2.1 2.1 0 0 1 4.2 0v.9H1.2v-.9a1.2 1.2 0 0 0-2.4 0v.9z'},
  money:{color:'#188038', glyph:'M-4.6 3.4h9.2v1.2h-9.2zM0-5.2l4.8 2.6v.9h-9.6v-.9zM-3.6-1.2h1.4v4h-1.4zM-.7-1.2H.7v4H-.7zM2.2-1.2h1.4v4H2.2z'},
  fuel:{color:'#1a73e8', glyph:'M-4.2-4.6h5.4v9.2h-5.4zM-3.2-3.6v2.7h3.4v-2.7zM2-2.2l.7-.6 1.6 1.9v4.4a.9.9 0 0 1-1.8 0V1h-.5V.1h1.3v3.4h.2V-.6z'},
  transport:{color:'#1a73e8', glyph:'M-3.8-4.8h7.6a1 1 0 0 1 1 1v6.6h-1v1.6H2.3V2.8h-4.6v1.6h-1.5V2.8h-1v-6.6a1 1 0 0 1 1-1zM-3.4-3.4v2.8h6.8v-2.8zM-3 .7a.8.8 0 1 0 1.6 0a.8.8 0 1 0-1.6 0zM1.4.7a.8.8 0 1 0 1.6 0a.8.8 0 1 0-1.6 0z'},
  worship:{color:'#5f6368', glyph:'M-.8-5h1.6v2.6h2.6V-.8H.8V5H-.8V-.8h-2.6v-1.6h2.6z'},
  lodging:{color:'#d01884', glyph:'M-5 3.8v-7.6h1.4v4.3h3.1v-2.8h3.6a1.9 1.9 0 0 1 1.9 1.9v4.2H3.6V2.2h-7.2v1.6zM-2.1-1.6a1.2 1.2 0 1 0 0-.1z'},
  education:{color:'#8d6e63', glyph:'M0-4.2l5.6 2.7L0 1.2l-5.6-2.7zM-3.2.5v2.3c1.9 1.4 4.5 1.4 6.4 0V.5L0 2z'},
  civic:{color:'#5f6368', glyph:'M-4.6 3.4h9.2v1.2h-9.2zM0-5.2l4.8 2.6v.9h-9.6v-.9zM-3.6-1.2h1.4v4h-1.4zM-.7-1.2H.7v4H-.7zM2.2-1.2h1.4v4H2.2z'},
};
function mapLineClass(line) {
  const v = String(line.value);
  if (line.kind === 'waterway') return /river|canal/.test(v) ? 'river' : 'stream';
  if (/motorway|trunk|primary|secondary/.test(v)) return 'major';
  if (/tertiary|unclassified/.test(v)) return 'minor';
  if (/path|track|footway|bridleway|cycleway|steps|pedestrian/.test(v)) return 'path';
  return 'street';
}
function mapLoadDetail() {
  if (mapDetail !== null) return;
  mapDetail = 'loading';
  fetch('/static/kasungu/kasungu_detail.json')
    .then(response=>response.ok ? response.json() : Promise.reject(new Error('missing')))
    .then(detail=>{ mapDetail = detail; mapDetailCache = null; if (data && mapData) renderMap(); })
    .catch(()=>{ mapDetail = false; });  // the map still works from the roads and rivers alone
}
// Decodes the detail file (delta-encoded 1e-5 degree offsets) into map units, once.
function mapDetailLayers(point) {
  if (!mapDetail || typeof mapDetail !== 'object') return null;
  if (mapDetailCache) return mapDetailCache;
  const [s, w] = mapDetail.origin, u = mapDetail.unit;
  const at = ([x,y]) => point([s + y*u, w + x*u]);
  const decode = flat => { const pts = []; let x = 0, y = 0; for (let i = 0; i < flat.length; i += 2) { x = i ? x + flat[i] : flat[i]; y = i ? y + flat[i+1] : flat[i+1]; pts.push(at([x,y])); } return pts; };
  const ring = pts => 'M' + pts.map(p=>p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join('L') + 'Z';
  mapDetailCache = {
    buildings: mapDetail.buildings.map(b=>ring(decode(b))).join(''),
    areas: mapDetail.areas.map(a=>({kind:a.kind, d:ring(decode(a.ring))})),
    roads: mapDetail.roads.map(r=>({cls:mapLineClass({kind:'highway', value:r.value}), ref:r.ref, pts:decode(r.points)})),
    waters: mapDetail.waters.map(r=>({cls:mapLineClass({kind:'waterway', value:r.kind}), name:r.name, pts:decode(r.points)})),
    pois: mapDetail.pois.map(p=>({...p, xy:at(p.at)})),
    places: mapDetail.places.map(p=>({...p, xy:at(p.at)})),
  };
  return mapDetailCache;
}
// The longest run of a line that stays inside the view, thinned so labels follow it smoothly.
function mapVisibleRun(pts, vb, pad, spacing) {
  const inside = ([x,y]) => x > vb.x + pad && x < vb.x + vb.w - pad && y > vb.y + pad && y < vb.y + vb.h - pad;
  let best = [], run = [];
  for (const p of pts) { if (inside(p)) run.push(p); else { if (run.length > best.length) best = run; run = []; } }
  if (run.length > best.length) best = run;
  const thin = best.filter((p,i)=>i === 0 || i === best.length - 1 || i % spacing === 0);
  const length = thin.slice(1).reduce((sum,p,i)=>sum + Math.hypot(p[0]-thin[i][0], p[1]-thin[i][1]), 0);
  return {pts: thin[0] && thin[thin.length-1][0] < thin[0][0] ? thin.reverse() : thin, length};
}
function mapScaleBar(metresPerUnit, vb, k) {
  const metres = [10,20,50,100,200,250,500,1000,2000].filter(m => m / metresPerUnit <= 110*k).pop() || 10;
  const len = metres / metresPerUnit / k, label = metres >= 1000 ? `${metres/1000} km` : `${metres} m`;
  return `<g class="map-scale" aria-hidden="true" transform="translate(${(vb.x + vb.w - (len + 18)*k).toFixed(2)} ${(vb.y + vb.h - 12*k).toFixed(2)}) scale(${k})">`
    + `<rect x="-8" y="-19" width="${(len + 16).toFixed(1)}" height="25" rx="3"/>`
    + `<text x="${len.toFixed(1)}" y="-8" text-anchor="end">${label}</text><path d="M0-4V0H${len.toFixed(1)}V-4"/></g>`;
}
function mapZoomTo(zoom, centre) {
  mapView.zoom = Math.min(6, Math.max(1, zoom));
  if (centre) [mapView.cx, mapView.cy] = centre;
  if (mapView.zoom === 1) mapView.cx = mapView.cy = null;
  renderMap();
}
function renderMap() {
  mapLoadDetail();
  const [south, west, north, east] = mapData.bounds;
  const point = pair=>[(pair[1]-west)/(east-west)*600, (north-pair[0])/(north-south)*600];
  const narrow = window.matchMedia('(max-width:520px)').matches;
  // Wide cards show a taller window onto the padded extract (the detail runs past the bounds); phones keep it square.
  const base = narrow ? {x:0, y:0, w:600, h:600} : {x:-60, y:-70, w:720, h:740};
  const k = 1 / mapView.zoom, w = base.w * k, h = base.h * k;
  const clamp = (c, size) => Math.min(Math.max(c, MAP_PAN[0] + size/2), MAP_PAN[1] - size/2);
  const cx = mapView.cx === null ? base.x + base.w/2 : clamp(mapView.cx, w);
  const cy = mapView.cy === null ? base.y + base.h/2 : clamp(mapView.cy, h);
  const vb = {x:cx - w/2, y:cy - h/2, w, h};
  // When a different farm is picked while zoomed in, bring it into view.
  const picked = data.farms.find(f=>f.id===selected), pickedXY = picked && point([picked.latitude, picked.longitude]);
  if (selected !== mapView.shown && mapView.zoom > 1 && pickedXY && !(pickedXY[0] > vb.x && pickedXY[0] < vb.x + w && pickedXY[1] > vb.y + h*.15 && pickedXY[1] < vb.y + h)) {
    mapView.shown = selected; [mapView.cx, mapView.cy] = pickedXY; return renderMap();
  }
  mapView.shown = selected;
  const pinScale = (narrow ? 1.45 : 1.1) * k;
  const kt = k * (narrow ? 1.7 : 1.1);  // labels and cards: steady on-screen size, larger on phones
  const metresPerUnit = (east-west) * 111320 * Math.cos((north+south) / 2 * Math.PI / 180) / 600;
  const detail = mapDetailLayers(point);
  const str = pts=>pts.map(p=>p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
  const lines = mapData.features.map(f=>({cls:mapLineClass(f), pts:f.points.map(point)})).concat(detail ? detail.roads : [], detail ? detail.waters : []);
  const poly = (cls, css) => lines.filter(l=>l.cls===cls).map(l=>`<polyline class="${css}" points="${str(l.pts)}"/>`).join('');

  // Labels and markers keep a constant on-screen size, so they are drawn at scale k and
  // skipped where they would overlap something already placed.
  const boxes = [];
  const free = (x, y, bw, bh) => !boxes.some(b=>x < b[0] + b[2] && x + bw > b[0] && y < b[1] + b[3] && y + bh > b[1]);
  const take = (x, y, bw, bh) => boxes.push([x, y, bw, bh]);
  const inView = ([x,y], pad = 0) => x > vb.x + pad && x < vb.x + vb.w - pad && y > vb.y + pad && y < vb.y + vb.h - pad;

  // Farm pins, in ranked order so the numbers match the list and the tab order.
  const ranked = data.farms.map((farm,i)=>({farm, i, xy:point([farm.latitude,farm.longitude])}));
  ranked.forEach(({xy:[x,y]})=>take(x - 12*pinScale, y - 36*pinScale, 24*pinScale, 37*pinScale));
  const pins = ranked.map(({farm,i,xy:[x,y]})=>{
    const tone = farm.completed ? 'done' : /today/i.test(farm.status) ? 'hot' : farm.status==='Watch' ? 'warm' : 'calm';
    const active = farm.id===selected;
    return `<g class="map-pin pin-${tone} ${active?'active':''}" data-pin="${esc(farm.id)}" role="button" tabindex="0" aria-label="Select ${esc(farm.name)}" transform="translate(${x.toFixed(2)} ${y.toFixed(2)}) scale(${pinScale.toFixed(4)})"><title>${esc(farm.name)} · ${esc(farm.status)} · ${farm.score} points</title>`
      + `<g class="pin-mark"><ellipse class="pin-shadow" rx="6" ry="2.4"/>`
      + `<path class="pin-body" d="M0 0C-1.6-6.5-12-12.5-12-22.5a12 12 0 1 1 24 0C12-12.5 1.6-6.5 0 0z"/><text y="-22.5">${i+1}</text></g></g>`;
  }).join('');

  // An info card above the selected pin (decorative: the pin already names the farm).
  let callout = '';
  const chosen = ranked.find(p=>p.farm.id===selected);
  if (chosen && inView(chosen.xy)) {
    const {farm, xy:[x,y]} = chosen, name = farm.name.length > 26 ? farm.name.slice(0,25) + '…' : farm.name;
    const cw = Math.max(name.length*7.4, 100) + 24, ch = 42, lift = pinScale * 44 * 1.15 / kt + 10;
    const left = Math.min(Math.max(x - cw/2*kt, vb.x + 8*kt), vb.x + vb.w - (cw + 8)*kt);
    const above = y - (lift + ch)*kt > vb.y + 8*kt, top = above ? y - (lift + ch)*kt : y + 12*kt;
    const tip = Math.min(Math.max((x - left)/kt, 14), cw - 14);
    const arrow = above ? `M${(tip-7).toFixed(1)} ${ch}L${tip.toFixed(1)} ${ch+7}L${(tip+7).toFixed(1)} ${ch}Z` : `M${(tip-7).toFixed(1)} 0L${tip.toFixed(1)} -7L${(tip+7).toFixed(1)} 0Z`;
    take(left, top, cw*kt, ch*kt);
    callout = `<g class="map-callout" aria-hidden="true" transform="translate(${left.toFixed(2)} ${top.toFixed(2)}) scale(${kt})"><path class="map-callout-box" d="M0 8a8 8 0 0 1 8-8H${(cw-8).toFixed(1)}a8 8 0 0 1 8 8V${ch-8}a8 8 0 0 1-8 8H8a8 8 0 0 1-8-8Z${arrow}"/>`
      + `<text x="12" y="17" class="map-callout-name">${esc(name)}</text><text x="12" y="33">${farm.score} points · ${esc(farm.status)}</text></g>`;
  }

  let labels = '', defs = '';
  if (detail) {
    // Route shield on the longest visible stretch of each numbered road.
    const refs = [...new Set(detail.roads.filter(r=>r.ref).map(r=>r.ref))];
    refs.forEach(ref=>{
      const run = detail.roads.filter(r=>r.ref===ref).map(r=>mapVisibleRun(r.pts, vb, 20*kt, 1)).sort((a,b)=>b.length - a.length)[0];
      if (!run || run.pts.length < 2) return;
      const [x,y] = run.pts[Math.floor(run.pts.length/2)], sw = ref.length*7 + 10;
      if (!free(x - sw/2*kt, y - 8*kt, sw*kt, 16*kt)) return;
      take(x - sw/2*kt, y - 8*kt, sw*kt, 16*kt);
      labels += `<g class="map-shield" transform="translate(${x.toFixed(2)} ${y.toFixed(2)}) scale(${kt})"><rect x="${-sw/2}" y="-8" width="${sw}" height="16" rx="3"/><text>${esc(ref)}</text></g>`;
    });
    // River names along the water, one per river.
    const names = [...new Set(detail.waters.filter(r=>r.name).map(r=>r.name))];
    names.forEach((name, n)=>{
      const run = detail.waters.filter(r=>r.name===name).map(r=>mapVisibleRun(r.pts, vb, 10*kt, 4)).sort((a,b)=>b.length - a.length)[0];
      const need = (name.length*6.6 + 30) * kt;
      if (!run || run.length < need) return;
      defs += `<path id="map-river-${n}" d="M${run.pts.map(p=>p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join('L')}"/>`;
      labels += `<text class="map-river-label" style="font-size:${(11*kt).toFixed(3)}px;stroke-width:${(3*kt).toFixed(3)}px"><textPath href="#map-river-${n}" startOffset="50%" text-anchor="middle">${esc(name)}</textPath></text>`;
    });
    // Towns and villages.
    detail.places.filter(p=>inView(p.xy, 30*kt)).forEach(p=>{
      const size = p.kind === 'town' || p.kind === 'city' ? 15 : 12, lw = p.name.length*size*.62;
      const [x,y] = p.xy;
      if (!free(x - lw/2*kt, y - size*kt, lw*kt, size*1.2*kt)) return;
      take(x - lw/2*kt, y - size*kt, lw*kt, size*1.2*kt);
      labels += `<text class="map-place map-place-${p.kind === 'town' || p.kind === 'city' ? 'town' : 'village'}" transform="translate(${x.toFixed(2)} ${y.toFixed(2)}) scale(${kt})">${esc(p.name)}</text>`;
    });
    // Places of interest: a coloured badge, with its name where there is room.
    detail.pois.filter(p=>inView(p.xy, 8*kt)).forEach(p=>{
      const style = MAP_POI[p.kind] || MAP_POI.civic, [x,y] = p.xy;
      if (!free(x - 8*kt, y - 8*kt, 16*kt, 16*kt)) return;
      take(x - 8*kt, y - 8*kt, 16*kt, 16*kt);
      const lw = p.name.length*5.9 + 4;
      let text = '';
      if (free(x + 10*kt, y - 6*kt, lw*kt, 12*kt)) { take(x + 10*kt, y - 6*kt, lw*kt, 12*kt); text = `<text x="11" y="0" style="fill:${style.color}">${esc(p.name)}</text>`; }
      else if (free(x - (10 + lw)*kt, y - 6*kt, lw*kt, 12*kt)) { take(x - (10 + lw)*kt, y - 6*kt, lw*kt, 12*kt); text = `<text x="-11" y="0" text-anchor="end" style="fill:${style.color}">${esc(p.name)}</text>`; }
      labels += `<g class="map-poi" transform="translate(${x.toFixed(2)} ${y.toFixed(2)}) scale(${kt})"><circle r="7.5" style="fill:${style.color}"/><path d="${style.glyph}" transform="scale(.82)" fill-rule="evenodd"/>${text}</g>`;
    });
  }

  const hadFocus = document.activeElement?.closest?.('#map [data-pin]')?.dataset.pin;
  const zoomed = mapView.zoom > 1;
  $('map').innerHTML = `<svg viewBox="${vb.x.toFixed(2)} ${vb.y.toFixed(2)} ${vb.w.toFixed(2)} ${vb.h.toFixed(2)}" role="group" aria-label="Offline Kasungu map with eight selectable farm pins" class="${zoomed?'map-zoomed':''}" style="--z:${Math.pow(k, .6).toFixed(3)};--k:${k.toFixed(3)}">`
    + `<defs>${defs}</defs><g aria-hidden="true"><rect class="map-land" x="${MAP_PAN[0]-200}" y="${MAP_PAN[0]-200}" width="${MAP_PAN[1]-MAP_PAN[0]+400}" height="${MAP_PAN[1]-MAP_PAN[0]+400}"/>`
    + (detail ? detail.areas.map(a=>`<path class="map-area-${a.kind}" d="${a.d}"/>`).join('') : '')
    + `<g class="map-water">${poly('river','river')}${poly('stream','stream')}</g>`
    + (detail ? `<path class="map-building" d="${detail.buildings}"/>` : '')
    + `<g class="map-roads">${poly('path','path')}${poly('street','casing street')}${poly('minor','casing minor')}${poly('major','casing major')}`
    + `${poly('street','fill street')}${poly('minor','fill minor')}${poly('major','fill major')}</g>`
    + `<g class="map-labels">${labels}</g></g>`
    + `${pins}${callout}${mapScaleBar(metresPerUnit, vb, kt)}</svg>`
    + `<div class="map-zoom"><button type="button" data-map-zoom="in" aria-label="Zoom in" ${mapView.zoom >= 6 ? 'disabled' : ''}>+</button><button type="button" data-map-zoom="out" aria-label="Zoom out" ${zoomed ? '' : 'disabled'}>−</button></div>`;

  $('map').querySelectorAll('[data-map-zoom]').forEach(button=>button.onclick = ()=>{
    // The first zoom centres on the selected farm; later zooms keep the current centre.
    const focus = mapView.zoom === 1 && chosen ? chosen.xy : [cx, cy];
    mapZoomTo(button.dataset.mapZoom === 'in' ? mapView.zoom * 1.6 : mapView.zoom / 1.6, focus);
  });
  // Drag to pan once zoomed in. A drag never counts as a pin click.
  const svg = $('map').querySelector('svg');
  if (zoomed) {
    let start = null;
    svg.onpointerdown = event=>{ start = {x:event.clientX, y:event.clientY, cx, cy, scale:vb.w / svg.clientWidth}; mapDragged = false; };
    svg.onpointermove = event=>{
      if (!start) return;
      const dx = event.clientX - start.x, dy = event.clientY - start.y;
      if (!mapDragged && Math.hypot(dx, dy) < 5) return;
      if (!mapDragged) { mapDragged = true; svg.setPointerCapture(event.pointerId); svg.classList.add('map-dragging'); }
      mapView.cx = clamp(start.cx - dx*start.scale, w); mapView.cy = clamp(start.cy - dy*start.scale, h);
      svg.setAttribute('viewBox', `${(mapView.cx - w/2).toFixed(2)} ${(mapView.cy - h/2).toFixed(2)} ${w.toFixed(2)} ${h.toFixed(2)}`);
    };
    svg.onpointerup = svg.onpointercancel = ()=>{ if (start && mapDragged) renderMap(); start = null; };
    svg.addEventListener('click', event=>{ if (mapDragged) { event.stopPropagation(); mapDragged = false; } }, true);
  }
  if (hadFocus) document.querySelector(`#map [data-pin="${CSS.escape(hadFocus)}"]`)?.focus();
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
