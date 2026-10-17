# Offline-first, accessibility and impact metrics

## Offline-first

- **Service worker** (`static/sw.js`, served at `/sw.js`): caches every page, script, style and Tshego's map/weather files on first visit. It also pre-loads the latest dashboard data.
  - Pages load from the cache first.
  - API reads try the network first, then fall back to the last saved copy, stamped with the time it was saved.
- **Connection banner** on every page: *Online*, *Offline — showing data saved at …*, or *N actions waiting to sync*.
- **Outbox** (`static/offline.js`): farmer replies, check-ins, corrections, visits, shortlist changes and disease observations made offline are saved on the device. They sync automatically when the connection returns, or when Felix taps **Sync now**.
  - Each queued action carries an `Idempotency-Key`, so a retried action is never saved twice.
  - A rejected action is shown in the banner rather than silently dropped.
  - Live-data fetches (weather, soil, map, UW) are not queued, because they need the internet anyway.
- **Installable**: `manifest.webmanifest` and an icon, so the app can be added to a phone's home screen.

### Demo it

1. Open `http://127.0.0.1:8765/felix` once while online.
2. Press F12, open **Network**, and choose **Offline**. Or close the START-FIELDWISE window.
3. Reload. The page still loads, and the banner says it is offline and when the data was saved.
4. Record a visit. The banner shows "1 action waiting to sync".
5. Go back online. The action syncs, and **Impact → Offline submissions synced** goes up by one.

## Accessibility (WCAG 2.1 AA)

- Skip link, labelled navigation and landmarks; decorative glyphs are hidden from screen readers.
- Visible focus rings; the filter buttons announce their pressed state.
- Text colours darkened to at least 4.5:1 contrast; minimum text size raised from 8–10px to 11px.
- Reduced-motion and forced-colours support.
- The impact chart has a table view.
- **Verified:** axe-core 4.10.2 reports **0 violations** on `/`, `/felix` and `/impact` at desktop (1440px) and mobile (390px) widths, with no horizontal overflow.

## Impact metrics (`/impact`)

The metrics come from an append-only `impact_events` table. It stores only an event type, the workspace, a number and a timestamp: **no farm ID, name, phone number or survey answer**. So the counts survive a farmer's erasure request, which matches the POPIA approach.

| Group | What it means | Metrics |
|---|---|---|
| Measured outcomes | What Felix found, and how fast | Median report-to-visit hours · % of visits with an outcome that confirmed a problem |
| Activity | What people and the system did | Signals collected · survey response rate · % of answers that changed a priority · average priority movement · % of visits to flagged farms · officer reviews · live-data success · offline submissions synced and their delay · erasure requests honoured |
| Model estimates | Calculated, never measured | Maize at risk (FAO-33), counted once per irrigation interruption |

Each tile shows its numerator and denominator and how it is calculated. The page also shows a daily trend and the 25 most recent timestamped events, and the full log is downloadable from **Export event log (CSV)** (`/api/impact/export.csv`).

Counting starts from the first event after the latest demo reset. Nothing is back-filled, estimates are labelled as estimates, and a metric with no data shows "No data yet" rather than 0%.

## Verification

- `python -m unittest discover -s tests`: 47 passed, including 8 new tests in `tests/test_offline_impact.py`.
- `node scripts/offline-a11y-check.cjs http://127.0.0.1:<port>` (headless Edge, against a disposable database) checked:
  - the service worker installed and cached 25 resources;
  - all three pages opened offline;
  - a visit recorded offline was queued and then synced exactly once;
  - zero axe violations, and the first Tab press lands on the skip link.
- Screenshots: `artifacts/offline-queued.png`, `artifacts/impact-desktop.png`, `artifacts/impact-mobile.png`.

## Redesign (theme.css)

All three pages load `static/theme.css`. It adds a dark contour hero band, Bahnschrift display numbers (system font, works offline), status colours for urgent, watch and routine, score meters, and a 15px base text size. Interface copy was edited with the no-ai-slop rules. Before and after screenshots are in `artifacts/before` and `artifacts/after`; regenerate with `node scripts/screenshots.cjs artifacts/after`.

Fixed: online writes were sending the offline-replay header, so they were miscounted as offline syncs. Only outbox replays send it now. The browser check asserts this, and 3 false rows were removed from the saved database.

## Limits

The outbox lives in the browser's localStorage. If the browser's site data is cleared before the device reconnects, unsynced actions are lost. Offline mode shows the last data this device saw; it does not re-run the pyfao56 model on the device.
