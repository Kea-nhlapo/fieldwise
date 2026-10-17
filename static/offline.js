'use strict';
// Shared offline layer: registers the service worker, shows connection state,
// and holds writes in a device outbox until the server is reachable again.
(() => {
  const KEY = 'fieldwise-outbox-v1';
  // Live-data fetches need the internet anyway, so they are not queued.
  // Sign-in and demo reset only make sense live, so they are not queued either.
  const NOT_QUEUEABLE = /\/evidence\/|\/weather$|\/disease\/reference|\/api\/session|\/api\/demo\/reset|\/api\/ussd\/simulate/;
  let memory = [], cachedAt = null, syncing = false, failures = [], needsPin = false, signInPromise = null;
  const auth = {enabled: false, signedIn: false};
  const SIGNOUT_KEY = 'fieldwise-signout-pending';
  // Second credential next to the HttpOnly cookie (see fieldwise/auth.py). Deleting it signs this device out
  // at once, even offline and from any page, because the server refuses the cookie without it.
  const TOKEN_KEY = 'fieldwise-officer-token';
  let memoryToken = null;
  const getToken = () => { try { return localStorage.getItem(TOKEN_KEY); } catch { return memoryToken; } };
  const setToken = value => { memoryToken = value; try { value ? localStorage.setItem(TOKEN_KEY, value) : localStorage.removeItem(TOKEN_KEY); } catch {} };
  const withToken = (headers = {}) => { const token = getToken(); return token ? {...headers, 'X-Officer-Token': token} : {...headers}; };
  const channel = 'BroadcastChannel' in window ? new BroadcastChannel('fieldwise-session') : null;
  // Reads without farmer records (mirrors OPEN_READS in fieldwise/auth.py and static/sw.js).
  const OPEN_READS = ['/api/health', '/api/session', '/api/impact', '/api/simulation', '/api/disease/reference', '/api/felix/map'];
  const isRecord = path => path.startsWith('/api/') && !OPEN_READS.some(open => path.startsWith(open));

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
    banner.querySelector('[data-sign-out]').hidden = !(auth.enabled && auth.signedIn);
  }

  // Delete saved farm records from this device (service worker cache, plus the page's view of it).
  async function forgetRecords() {
    navigator.serviceWorker?.controller?.postMessage('forget-records');
    if (!('caches' in window)) return;
    for (const name of await caches.keys()) {
      const cache = await caches.open(name);
      for (const request of await cache.keys()) if (isRecord(new URL(request.url).pathname)) await cache.delete(request);
    }
  }

  // Signing out removes this device's copy of farm records and any unsynced actions.
  async function signOut() {
    if (read().length && navigator.onLine) await sync();
    const left = read().length;
    if (left && !confirm(`${left} action${left === 1 ? ' has' : 's have'} not reached the server yet. Signing out deletes ${left === 1 ? 'it' : 'them'} from this device. Sign out anyway?`)) return;
    setToken(null);   // first: from here on no request from this device counts as signed in
    channel?.postMessage('signed-out');
    write([]); failures = [];
    await forgetRecords();
    const ended = await fetch('/api/session', {method: 'DELETE'}).then(r => r.ok).catch(() => false);
    // Offline, the server session cannot end yet: remember to end it before anything else next time.
    try { ended ? localStorage.removeItem(SIGNOUT_KEY) : localStorage.setItem(SIGNOUT_KEY, '1'); } catch {}
    auth.signedIn = false;
    location.reload();
  }

  async function finishPendingSignOut() {
    let pending = false;
    try { pending = localStorage.getItem(SIGNOUT_KEY) === '1'; } catch {}
    if (!pending) return;
    const ended = await fetch('/api/session', {method: 'DELETE'}).then(r => r.ok).catch(() => false);
    if (ended) { try { localStorage.removeItem(SIGNOUT_KEY); } catch {} }
  }
  // Every request waits for this, so a page opened after an offline sign-out never shows records first.
  let ready = finishPendingSignOut();

  async function refreshSession() {
    const state = await fetch('/api/session', {headers: withToken()}).then(r => r.ok ? r.json() : null).catch(() => null);
    if (state) { auth.enabled = state.auth_enabled; auth.signedIn = state.signed_in; render(); }
  }

  const isAuthRefusal = async response => {
    if (response.status !== 401 || (await response.clone().json().catch(() => ({}))).auth !== 'required') return false;
    setToken(null);   // the server session is gone, so this device's token is stale
    return true;
  };

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
        if (response && response.ok) {
          const body = await response.json().catch(() => ({}));
          setToken(body.officer_token || null);
          auth.enabled = auth.signedIn = true;
          return done(true);
        }
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
    const headers = withToken({'Content-Type': 'application/json', 'Idempotency-Key': item.key});
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
    await ready;
    const method = (options.method || 'GET').toUpperCase();
    if (method === 'GET') {
      const get = () => fetch(url, {...options, headers: withToken(options.headers)});
      let response = await get();
      if (await isAuthRefusal(response) && await signIn()) response = await get();
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

  // Another tab signed out: stop showing records at once and reload into the signed-out state.
  function onSignedOutElsewhere() {
    document.body.style.visibility = 'hidden';
    location.reload();
  }
  channel?.addEventListener('message', event => { if (event.data === 'signed-out') onSignedOutElsewhere(); });
  addEventListener('storage', event => { if (event.key === TOKEN_KEY && !event.newValue && event.oldValue) onSignedOutElsewhere(); });

  function mount() {
    if (document.body.dataset.banner === 'off') return;
    banner = document.createElement('div');
    banner.className = 'connection';
    banner.setAttribute('role', 'status');
    banner.setAttribute('aria-live', 'polite');
    banner.innerHTML = '<span></span><button type="button" class="text-button">Sync now</button><button type="button" class="text-button" data-sign-out hidden>Sign out</button>';
    banner.querySelector('button').addEventListener('click', async () => { if (needsPin && !(await signIn())) return; sync(); });
    banner.querySelector('[data-sign-out]').addEventListener('click', signOut);
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

  window.Fieldwise = {fetch: fwFetch, sync, signIn, signOut, pending: () => read().length,
    queuedMessage: 'Saved on this device. It will sync automatically when the connection returns.'};
  addEventListener('online', () => { cachedAt = null; render(); ready = finishPendingSignOut().then(refreshSession); sync(); });
  addEventListener('offline', render);
  setInterval(() => { if (read().length) sync(); }, 20000);
  const start = () => { mount(); ready.then(refreshSession); sync(); };
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', start) : start();
  if ('serviceWorker' in navigator) addEventListener('load', () => navigator.serviceWorker.register('/sw.js', {scope: '/'}).catch(() => {}));
})();
