// Builds static/kasungu/kasungu_detail.json: OpenStreetMap building footprints, parks,
// named rivers, route numbers and named places around the Kasungu demo farms, so the
// farm map can draw them offline. Roads cover the padded area so panning past the
// bundled extract's edge still shows streets. Run once with network access:
//   node scripts/build-map-detail.cjs
// Data © OpenStreetMap contributors, ODbL (credited on the map card).
'use strict';
const fs = require('fs');
const path = require('path');

// The bundled extract's bounds, padded so the wider desktop map frame is covered too.
const [S, W, N, E] = [-13.047, 33.480, -13.027, 33.500];
const BBOX = `(${S},${W},${N},${E})`;
const PLACES_BBOX = '(-13.07,33.46,-13.00,33.52)';
const QUERY = `[out:json][timeout:90];(
  way["building"]${BBOX};
  way["leisure"~"park|pitch|garden"]${BBOX};
  way["landuse"~"grass|forest|recreation_ground|cemetery"]${BBOX};
  way["amenity"="parking"]${BBOX};
  way["waterway"]["name"]${BBOX};
  way["highway"]${BBOX};
  node["amenity"]["name"]${BBOX};
  node["shop"]["name"]${BBOX};
  node["tourism"]["name"]${BBOX};
  node["place"]["name"]${PLACES_BBOX};
);out tags geom;`;

// Coordinates are stored as integer offsets from [S, W] in units of 1e-5 degrees (about 1 m).
const q = ([lat, lon]) => [Math.round((lon - W) * 1e5), Math.round((lat - S) * 1e5)];
const flat = geometry => {
  const out = [];
  let px = 0, py = 0;
  geometry.forEach((g, i) => {
    const [x, y] = q([g.lat, g.lon]);
    if (i === 0) out.push(x, y); else out.push(x - px, y - py);  // delta-encoded after the first point
    [px, py] = [x, y];
  });
  return out;
};
const tidy = name => name.replace(/^./, c => c.toUpperCase()).replace(/\s*\([^)]*\)\s*$/, '');

const POI_KINDS = {
  hospital:'health', clinic:'health', doctors:'health', pharmacy:'health',
  bank:'money', atm:'money', bureau_de_change:'money',
  fuel:'fuel', bus_station:'transport', taxi:'transport',
  restaurant:'food', cafe:'food', fast_food:'food', bar:'food',
  place_of_worship:'worship', school:'education', college:'education', university:'education',
  police:'civic', post_office:'civic', townhall:'civic', marketplace:'shop',
};

(async () => {
  const response = await fetch('https://overpass-api.de/api/interpreter', {
    method: 'POST', body: new URLSearchParams({data: QUERY}),
    headers: {'User-Agent': 'Fieldwise-demo-map-build'},
  });
  if (!response.ok) throw new Error(`Overpass returned ${response.status}`);
  const payload = await response.json();
  const out = {
    source: '© OpenStreetMap contributors, ODbL; retrieved through Overpass',
    osm_base: payload.osm3s?.timestamp_osm_base || null,
    origin: [S, W], unit: 1e-5,
    buildings: [], areas: [], waters: [], roads: [], pois: [], places: [],
  };
  for (const el of payload.elements) {
    const t = el.tags || {};
    if (el.type === 'way' && el.geometry?.length >= 2) {
      if (t.building) out.buildings.push(flat(el.geometry));
      else if (t.waterway) out.waters.push({name: t.name, kind: t.waterway, points: flat(el.geometry)});
      else if (t.highway) out.roads.push(t.ref ? {value: t.highway, ref: t.ref, points: flat(el.geometry)} : {value: t.highway, points: flat(el.geometry)});
      else out.areas.push({kind: t.amenity === 'parking' ? 'parking' : 'park', ring: flat(el.geometry)});
    } else if (el.type === 'node') {
      const at = q([el.lat, el.lon]);
      if (t.place) out.places.push({name: tidy(t.name), kind: t.place, at});
      else {
        const kind = POI_KINDS[t.amenity] || (t.shop ? 'shop' : t.tourism ? 'lodging' : null);
        if (kind) out.pois.push({name: tidy(t.name), kind, at});
      }
    }
  }
  const file = path.join(__dirname, '..', 'static', 'kasungu', 'kasungu_detail.json');
  fs.writeFileSync(file, JSON.stringify(out));
  console.log(`${out.buildings.length} buildings, ${out.areas.length} areas, ${out.waters.length} waterways, ${out.roads.length} roads, ${out.pois.length} places of interest, ${out.places.length} settlements → ${file} (${fs.statSync(file).size} bytes)`);
})().catch(error => { console.error(error); process.exit(1); });
