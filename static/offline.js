'use strict';
// Shared offline layer: registers the service worker, shows connection state,
// and holds writes in a device outbox until the server is reachable again.
(() => {
  const KEY = 'fieldwise-outbox-v1';
  // Live-data fetches need the internet anyway, so they are not queued.
  // Sign-in and demo reset only make sense live, so they are not queued either.
  const NOT_QUEUEABLE = /\/evidence\/|\/weather$|\/disease\/reference|\/api\/session|\/api\/demo\/reset/;
  let memory = [], cachedAt = null, syncing = false, failures = [], needsPin = false, signInPromise = null;

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
    if (pending) parts.push(`${pending} action${pending === 1 ? '' : 's'} waiting to sync.${needsPin ? ' Sign in with the officer PIN to send them.' : ''}`);
    if (failures.length) parts.push(`${failures.length} queued action${failures.length === 1 ? ' was' : 's were'} rejected by the server: ${failures.at(-1)}`);
    banner.querySelector('span').textContent = parts.join(' ');
    banner.querySelector('button').hidden = !pending || syncing;
    banner.querySelector('button').textContent = needsPin ? 'Sign in and sync' : 'Sync now';
  }

  const isAuthRefusal = async response => response.status === 401 && (await response.clone().json().catch(() => ({}))).auth === 'required';

  // Officer PIN dialog. Concurrent requests share one prompt; resolves true once signed in.
  function signIn() {
    if (signInPromise) return signInPromise;
    signInPromise = new Promise(resolve => {
      let dialog = document.getElementById('fw-signin');
      if (!dialog) {
        dialog = document.createElement('dialog');
        dialog.id = 'fw-signin';
        dialog.className = 'signin-dialog';
        dialog.setAttribute('aria-labelledby', 'fw-signin-title');
        dialog.innerHTML = '<form><h2 id="fw-signin-title">Officer sign-in</h2><p>Farm records, and any change to them, need the officer PIN.</p>'
          + '<label for="fw-pin">Officer PIN</label><input id="fw-pin" type="password" inputmode="numeric" autocomplete="off" maxlength="32" required>'
          + '<p class="signin-error" role="alert"></p><div class="signin-actions"><button type="button" class="text-button" data-cancel>Cancel</button>'
          + '<button type="submit" class="primary-button">Sign in</button></div></form>';
        document.body.append(dialog);
      }
      const form = dialog.querySelector('form'), input = dialog.querySelector('#fw-pin'), error = dialog.querySelector('.signin-error');
      const cancel = dialog.querySelector('[data-cancel]');
      error.textContent = ''; input.value = '';
      const done = ok => {
        form.onsubmit = cancel.onclick = dialog.oncancel = null;
        if (dialog.open) dialog.close();
        signInPromise = null;
        if (ok) { needsPin = false; render(); }
        resolve(ok);
      };
      cancel.onclick = () => done(false);
      dialog.oncancel = event => { event.preventDefault(); done(false); };
      form.onsubmit = async event => {
        event.preventDefault();
        const response = await fetch('/api/session', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({pin: input.value})}).catch(() => null);
        if (response && response.ok) return done(true);
        const body = response ? await response.json().catch(() => ({})) : {};
        error.textContent = body.detail || 'No connection to the Fieldwise server.';
        input.select();
      };
      dialog.showModal();
      input.focus();
    });
    return signInPromise;
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
        if (await isAuthRefusal(response)) { needsPin = true; break; }  // keep it queued until the officer signs in
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
      let response = await fetch(url, options);
      if (await isAuthRefusal(response) && await signIn()) response = await fetch(url, options);
      if (String(url).startsWith('/api/dashboard') || String(url).startsWith('/api/felix/dashboard')) {
        cachedAt = response.headers.get('X-Fieldwise-Offline') === 'cached' ? response.headers.get('X-Fieldwise-Cached-At') : null;
        render();
      }
      return response;
    }
    const item = {url: String(url), method, body: options.body ?? null, key: uuid(), queuedAt: new Date().toISOString(),
                  label: String(url).split('/').filter(Boolean).slice(-2).join(' ')};
    let response;
    try { response = await send(item); }
    catch (error) {
      if (NOT_QUEUEABLE.test(item.url)) throw new Error('Offline: live data needs a connection. Saved evidence remains visible.');
      write([...read(), item]);
      return new Response(JSON.stringify({queued: true, status: 'queued_offline', queued_at: item.queuedAt}),
                          {status: 202, headers: {'Content-Type': 'application/json'}});
    }
    if (await isAuthRefusal(response) && await signIn()) response = await send(item);
    return response;
  }

  function mount() {
    banner = document.createElement('div');
    banner.className = 'connection';
    banner.setAttribute('role', 'status');
    banner.setAttribute('aria-live', 'polite');
    banner.innerHTML = '<span></span><button type="button" class="text-button">Sync now</button>';
    banner.querySelector('button').addEventListener('click', async () => { if (needsPin && !(await signIn())) return; sync(); });
    (document.querySelector('main') || document.body).prepend(banner);
    render();
  }

  document.addEventListener('click', async event => {
    if (!event.target.closest('[data-reset-demo]')) return;
    if (!confirm('Reset all demo farms, surveys, visits and alerts? Live data receipts are kept, and impact metrics restart from now.')) return;
    const response = await fwFetch('/api/demo/reset', {method: 'POST'}).catch(() => null);
    if (!response || !response.ok) { alert('Reset needs a connection to the Fieldwise server.'); return; }
    write([]);
    location.reload();
  });

  window.Fieldwise = {fetch: fwFetch, sync, signIn, pending: () => read().length,
    queuedMessage: 'Saved on this device. It will sync automatically when the connection returns.'};
  addEventListener('online', () => { cachedAt = null; render(); sync(); });
  addEventListener('offline', render);
  setInterval(() => { if (read().length) sync(); }, 20000);
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', () => { mount(); sync(); }) : (mount(), sync());
  if ('serviceWorker' in navigator) addEventListener('load', () => navigator.serviceWorker.register('/sw.js', {scope: '/'}).catch(() => {}));
})();
