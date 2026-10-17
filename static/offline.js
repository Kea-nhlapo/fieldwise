'use strict';
// Shared offline layer: registers the service worker, shows connection state,
// and holds writes in a device outbox until the server is reachable again.
(() => {
  const KEY = 'fieldwise-outbox-v1';
  // Live-data fetches need the internet anyway, so they are not queued.
  const NOT_QUEUEABLE = /\/evidence\/|\/weather$|\/disease\/reference/;
  let memory = [], cachedAt = null, syncing = false, failures = [];

  const read = () => { try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch { return memory; } };
  const write = items => { memory = items; try { localStorage.setItem(KEY, JSON.stringify(items)); } catch {} render(); };
  const uuid = () => (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2));
  const time = iso => new Date(iso).toLocaleString('en-ZA', {day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'});

  let banner;
  function render() {
    if (!banner) return;
    const pending = read().length;
    const offline = !navigator.onLine || cachedAt;
    banner.dataset.state = syncing ? 'syncing' : offline ? 'offline' : pending ? 'pending' : 'online';
    const parts = [];
    if (syncing) parts.push('Syncing saved actions…');
    else if (offline) parts.push(cachedAt ? `Offline. Showing data saved on this device at ${time(cachedAt)}.` : 'Offline. This device has no network connection.');
    else parts.push('Online. Data is current.');
    if (pending) parts.push(`${pending} action${pending === 1 ? '' : 's'} waiting to sync.`);
    if (failures.length) parts.push(`${failures.length} queued action${failures.length === 1 ? ' was' : 's were'} rejected by the server: ${failures.at(-1)}`);
    banner.querySelector('span').textContent = parts.join(' ');
    banner.querySelector('button').hidden = !pending || syncing;
  }

  // Only outbox replays carry X-Fieldwise-Queued-At; a direct online send is not an offline sync.
  async function send(item, replay = false) {
    const headers = {'Content-Type': 'application/json', 'Idempotency-Key': item.key};
    if (replay) headers['X-Fieldwise-Queued-At'] = item.queuedAt;
    return fetch(item.url, {method: item.method, body: item.body, headers});
  }

  async function sync() {
    if (syncing || !read().length) return;
    syncing = true; render();
    let delivered = 0;
    try {
      for (const item of read()) {
        let response;
        try { response = await send(item, true); } catch { break; }  // still offline: keep the rest in order
        if (response.status >= 500) break;
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          failures.push(`${item.label}: ${typeof body.detail === 'string' ? body.detail : 'HTTP ' + response.status}`);
        }
        write(read().filter(other => other.key !== item.key));
        delivered++;
      }
    } finally { syncing = false; render(); }
    if (delivered) document.dispatchEvent(new CustomEvent('fieldwise:synced', {detail: {delivered}}));
  }

  // Drop-in replacement for fetch() used by the page api() helpers.
  async function fwFetch(url, options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    if (method === 'GET') {
      const response = await fetch(url, options);
      if (String(url).startsWith('/api/dashboard') || String(url).startsWith('/api/felix/dashboard')) {
        cachedAt = response.headers.get('X-Fieldwise-Offline') === 'cached' ? response.headers.get('X-Fieldwise-Cached-At') : null;
        render();
      }
      return response;
    }
    const item = {url: String(url), method, body: options.body ?? null, key: uuid(), queuedAt: new Date().toISOString(),
                  label: String(url).split('/').filter(Boolean).slice(-2).join(' ')};
    try { return await send(item); }
    catch (error) {
      if (NOT_QUEUEABLE.test(item.url)) throw new Error('Offline: live data needs a connection. Saved evidence remains visible.');
      write([...read(), item]);
      return new Response(JSON.stringify({queued: true, status: 'queued_offline', queued_at: item.queuedAt}),
                          {status: 202, headers: {'Content-Type': 'application/json'}});
    }
  }

  function mount() {
    banner = document.createElement('div');
    banner.className = 'connection';
    banner.setAttribute('role', 'status');
    banner.setAttribute('aria-live', 'polite');
    banner.innerHTML = '<span></span><button type="button" class="text-button">Sync now</button>';
    banner.querySelector('button').addEventListener('click', sync);
    (document.querySelector('main') || document.body).prepend(banner);
    render();
  }

  document.addEventListener('click', async event => {
    if (!event.target.closest('[data-reset-demo]')) return;
    if (!confirm('Reset all demo farms, surveys, visits and alerts? Live data receipts are kept, and impact metrics restart from now.')) return;
    const response = await fetch('/api/demo/reset', {method: 'POST'}).catch(() => null);
    if (!response || !response.ok) { alert('Reset needs a connection to the Fieldwise server.'); return; }
    write([]);
    location.reload();
  });

  window.Fieldwise = {fetch: fwFetch, sync, pending: () => read().length,
    queuedMessage: 'Saved on this device. It will sync automatically when the connection returns.'};
  addEventListener('online', () => { cachedAt = null; render(); sync(); });
  addEventListener('offline', render);
  setInterval(() => { if (read().length) sync(); }, 20000);
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', () => { mount(); sync(); }) : (mount(), sync());
  if ('serviceWorker' in navigator) addEventListener('load', () => navigator.serviceWorker.register('/sw.js', {scope: '/'}).catch(() => {}));
})();
