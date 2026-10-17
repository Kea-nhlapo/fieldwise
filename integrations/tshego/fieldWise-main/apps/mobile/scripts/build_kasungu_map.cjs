// Convert a bounded OpenStreetMap API extract to a compact offline map asset.
// Source: https://api.openstreetmap.org/api/0.6/map?bbox=33.482,-13.045,33.498,-13.029
// Map data © OpenStreetMap contributors (ODbL).
const fs = require('node:fs');
const path = require('node:path');

const folder = path.join(__dirname, '..', 'assets', 'demo');
async function main() {
const response = await fetch('https://api.openstreetmap.org/api/0.6/map?bbox=33.482%2C-13.045%2C33.498%2C-13.029');
if (!response.ok) throw new Error(`OpenStreetMap download failed: ${response.status}`);
const xml = await response.text();
const nodes = new Map();
for (const match of xml.matchAll(/<node\s+([^>]+)\/>/g)) {
  const attrs = match[1];
  const id = /\bid="([^"]+)"/.exec(attrs)?.[1];
  const lat = Number(/\blat="([^"]+)"/.exec(attrs)?.[1]);
  const lon = Number(/\blon="([^"]+)"/.exec(attrs)?.[1]);
  if (id && Number.isFinite(lat) && Number.isFinite(lon)) nodes.set(id, [lat, lon]);
}

const features = [];
for (const match of xml.matchAll(/<way\b[^>]*>([\s\S]*?)<\/way>/g)) {
  const body = match[1];
  const tag = /<tag k="(highway|waterway|landuse|natural)" v="([^"]+)"\/>/.exec(body);
  if (!tag) continue;
  const [kind, value] = tag.slice(1);
  if (kind === 'landuse' && !['farmland', 'forest', 'grass', 'residential'].includes(value)) continue;
  if (kind === 'natural' && !['water', 'wood'].includes(value)) continue;
  const points = [...body.matchAll(/<nd ref="([^"]+)"\/>/g)]
    .map((m) => nodes.get(m[1]))
    .filter(Boolean)
    .map(([lat, lon]) => [Number(lat.toFixed(6)), Number(lon.toFixed(6))]);
  if (points.length > 1) features.push({ kind, value, points });
}
fs.writeFileSync(
  path.join(folder, 'kasungu_map.json'),
  JSON.stringify({ bounds: [-13.045, 33.482, -13.029, 33.498], features }),
);
console.log(`${features.length} map features`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
