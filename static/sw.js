'use strict';
// Fieldwise offline-first service worker.
// App shell: cache-first, refreshed in the background. GET /api/*: network-first,
// falling back to the last saved response, stamped with when it was saved.
// Writes are never cached here; static/offline.js queues them in an outbox.
const VERSION = 'fieldwise-v13';
const SHELL = [
  '/', '/felix', '/impact', '/pilot', '/simulation',
  '/static/style.css', '/static/disease.css', '/static/felix.css', '/static/evidence.css', '/static/a11y.css', '/static/theme.css', '/static/sidebar.css', '/static/icons.css', '/static/impact.css',
  '/static/app.js', '/static/disease.js', '/static/felix.js', '/static/evidence.js', '/static/offline.js', '/static/simulation.js', '/static/simulation.css', '/static/sim/results.json', '/static/crops.js', '/static/impact.js',
  '/static/manifest.webmanifest', '/static/icon.svg',
  '/static/photos/crop-groundnuts.jpg', '/static/photos/crop-maize.jpg', '/static/photos/crop-tobacco.jpg', '/static/photos/crop-vegetables.jpg', '/static/photos/hero-impact.jpg', '/static/photos/hero-kasungu.jpg', '/static/photos/hero-pilot.jpg', '/static/photos/hero-sa.jpg', '/static/photos/sidebar-maize-road.jpg',
  '/static/icons/arrow-left.svg', '/static/icons/arrow-right.svg', '/static/icons/arrow-up-right.svg', '/static/icons/bell.svg', '/static/icons/bug.svg', '/static/icons/chart-column.svg', '/static/icons/circle-dashed.svg', '/static/icons/clipboard-check.svg', '/static/icons/coins.svg', '/static/icons/droplets.svg', '/static/icons/flag.svg', '/static/icons/info.svg', '/static/icons/layout-dashboard.svg', '/static/icons/list.svg', '/static/icons/map-pin.svg', '/static/icons/map.svg', '/static/icons/route.svg', '/static/icons/smartphone.svg', '/static/icons/sprout.svg', '/static/icons/trending-up.svg', '/static/icons/triangle-alert.svg', '/static/icons/waves.svg', '/static/icons/wheat.svg',
  '/static/tshego/farms.json', '/static/tshego/kasungu_map.json', '/static/tshego/kasungu_detail.json', '/static/tshego/kasungu_weather.json',
];
// Reads that hold no farmer records (mirrors OPEN_READS in fieldwise/auth.py). Everything else under /api/
// is a farmer record: it is cached only while signed in and deleted when the session ends.
const OPEN_READS = ['/api/health', '/api/session', '/api/impact', '/api/simulation', '/api/disease/reference', '/api/felix/map'];
const isRecord = path => path.startsWith('/api/') && !OPEN_READS.some(open => path.startsWith(open));

async function forgetRecords() {
  for (const name of await caches.keys()) {
    const cache = await caches.open(name);
    for (const request of await cache.keys()) if (isRecord(new URL(request.url).pathname)) await cache.delete(request);
  }
}

const API_WARM = ['/api/dashboard', '/api/felix/dashboard', '/api/felix/map', '/api/impact', '/api/disease/reference/demo', '/api/simulation'];

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(VERSION);
    await cache.addAll(SHELL);
    // Warm the data cache so the first offline visit has something to show.
    await Promise.allSettled(API_WARM.map(url => fetch(url).then(response => response.ok && stamp(cache, url, response))));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) if (key !== VERSION) await caches.delete(key);
    await self.clients.claim();
  })());
});

async function stamp(cache, request, response) {
  const headers = new Headers(response.headers);
  headers.set('X-Fieldwise-Cached-At', new Date().toISOString());
  await cache.put(request, new Response(await response.clone().blob(), {status: response.status, headers}));
}

async function networkFirst(request) {
  const cache = await caches.open(VERSION);
  try {
    const response = await fetch(request);
    if (response.ok) await stamp(cache, request, response.clone());
    // The server says there is no session: nobody on this device may read the saved records any more.
    else if (response.status === 401 && isRecord(new URL(request.url).pathname)) await forgetRecords();
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (!cached) return new Response(JSON.stringify({detail: 'Offline and this data has not been saved on this device yet.', offline: true}),
      {status: 503, headers: {'Content-Type': 'application/json', 'X-Fieldwise-Offline': 'no-cache'}});
    const headers = new Headers(cached.headers);
    headers.set('X-Fieldwise-Offline', 'cached');
    return new Response(await cached.blob(), {status: cached.status, headers});
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(VERSION);
  const key = request.mode === 'navigate' ? new URL(request.url).pathname : request;
  const cached = await cache.match(key, {ignoreSearch: request.mode === 'navigate'});
  const refresh = fetch(request).then(response => { if (response.ok) cache.put(key, response.clone()); return response; });
  if (cached) { refresh.catch(() => {}); return cached; }
  try { return await refresh; }
  catch (error) { return (await cache.match('/')) || Response.error(); }
}

self.addEventListener('message', event => {
  if (event.data === 'forget-records') event.waitUntil(forgetRecords());
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  // Any sign-out, including a direct API call, clears saved records; the request itself goes to the network.
  if (event.request.method === 'DELETE' && url.pathname === '/api/session') { event.waitUntil(forgetRecords()); return; }
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/impact/export') || url.pathname.startsWith('/docs') || url.pathname === '/openapi.json') return;
  event.respondWith(url.pathname.startsWith('/api/') ? networkFirst(event.request) : cacheFirst(event.request));
});
