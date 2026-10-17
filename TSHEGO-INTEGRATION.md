# Tshego's contribution in Fieldwise

The supplied `fieldWise-main.zip` contains a Flutter frontend whose entry point opens Felix's Kasungu officer workflow. Its farm scenarios, triage rules, branching check-in and offline map fit the existing local application as a second workspace.

Start `START-FIELDWISE.cmd`, open `http://127.0.0.1:8765`, then choose **Tshego's Kasungu workspace** at the top. The direct path is `/felix`. This runs with the existing Python environment and requires no Flutter SDK or external account.

The subsequent [evidence-flow extension](EVIDENCE-FLOW.md) adds explicit public-data retrievals with saved receipts, input freshness, risk explanations, survey participation records, before/after comparisons and local privacy controls. It retains the source attribution described here.

## What was reused

| Supplied contribution | Local integration |
| --- | --- |
| `apps/mobile/lib/features/felix/felix_app.dart`, `_sampleFarms` | Eight Kasungu scenarios, names, crop labels and coordinates exported to `static/tshego/farms.json` |
| `_Farm` priority, action and success-check logic | Python adaptation in `fieldwise/felix.py`; visible reasons and triage points |
| `_CheckInPageState` numbered decision tree | Browser check-in with the same early exits and server-side branch validation |
| Officer corrections, planned visits and completion | Persistent corrections, manual visit shortlist and recorded visits |
| `assets/demo/kasungu_map.json` | Unmodified offline road/waterway data rendered as an SVG map with selectable farm pins |
| `assets/demo/kasungu_weather.json` | Unmodified supplied snapshot, using its first three days as the original Flutter flow does |

The source is preserved byte-for-byte under `integrations/tshego/fieldWise-main/`. The original ZIP is untouched. `integrations/tshego/PROVENANCE.json` records the ZIP hash and per-file hashes. No imported scripts were executed; embedded documentation was treated as source material, not instructions.

Attribution: Tshego, as identified by the user, supplied this work. No commit authorship was rewritten. The archive has no root license file; this local integration does not assign a new license to his source or assets. Map data remains © OpenStreetMap contributors, ODbL, with attribution displayed on the map. The public asset folder contains only the two bundled JSON snapshots and the extracted fictional farm records; the full source tree is not mounted as a web directory.

## Behaviour and deliberate differences

- The Kasungu workspace uses separate `felix_farms` and `felix_activity` SQLite tables in `data/fieldwise.db`. Loading, reporting and visits do not change South African farms, disease alerts, weather or activity. Insert-if-missing seeding preserves saved state on restart.
- Original Flutter state was in memory. The browser adaptation saves reports, corrections, visit notes and activity across restarts, with transactional updates.
- A positive or uncertain check-in creates an unresolved concern. Unlike the original in-memory rules, a subsequent negative answer cannot erase it. Recording a visit or choosing **Already checked** resolves it. A new concern reopens a completed farm and clears its old correction.
- **Reset** clears a correction and reopens the farm. It does not erase its history. A completed farm cannot be re-added to the shortlist until reopened.
- Default triage: 62 points when three-day precipitation is below 3 mm and maximum temperature is at least 30 °C. Current rain of at least 25 mm with mapped clay of at least 35% sets a drainage base of 75. Otherwise the scheduling baseline is 25; missing inputs do not mean low risk. An unresolved concern adds 55; a normal report without a pending concern subtracts 15. **More urgent** adds 30; **Call instead** subtracts 20. Completion sets zero. Visit-today threshold is 75; watch threshold is 55. These points are unbounded, not percentages.
- The farmer's first “No” ends the check-in. “Yes” or “Not sure” asks about extent; “One area” ends it, while “Several areas” or “Not sure” asks about duration. Partial branches and extraneous answers are rejected without a write.

## Current limits

The bundled window is **16–18 October 2026**, with **0.9 mm precipitation** and **30.75 °C maximum temperature**. This is a dated Open-Meteo snapshot supplied in the archive, not a refreshed forecast or measurement. It retains the source's UTC daily grouping and applies the same regional snapshot to all eight fictional farms. It is explicitly labelled in the UI. No automatic network request occurs in this workspace.

The browser now has explicit Open-Meteo, SoilGrids and Overpass retrieval adapters. Weather and soil have been verified with real saved responses; Overpass failed and the map remains labelled bundled. Missing or stale clay disables the drainage flag; valid current weather is also required for that flag. The supplied data lacks the calibrated inputs needed to run the maize engine for these mixed crops. Disease risk is not predicted here. The shortlist is manual, not a road route or an OR-Tools schedule.

USSD, SMS, notifications and reports are local simulations. No phone number is provisioned and no message is sent. This local app has no application authentication and its launcher binds to loopback only.

Flutter and Dart were not found on PATH. The original mobile project was not compiled, and its test suite was not run. Its existing Felix smoke test also references older UI labels such as “Pi setups” and “Green Acre”; it will need reconciliation when the native app is built. No claim of mobile build success is made.

## Initial integration verification

- Full Python suite: **28 tests passed** (21 existing plus 7 integration tests).
- Integration tests cover snapshot scope, rank changes, restart persistence, branch validation, corrections, shortlist/visit/reopening, unresolved concerns and isolation from the South African workspace.
- `scripts/felix-browser-smoke.cjs` checks the dashboard link, eight pins, numbered check-in, ranking, shortlist, visit, reload persistence, reopening, text escaping, search and responsive layout in headless Edge.
- Desktop 1440 px and phone 390 px passed without JavaScript errors or horizontal overflow; screenshots are under `artifacts/felix-desktop.png` and `artifacts/felix-mobile.png`.
- Browser tests run against a disposable database on port 8766 using `scripts/serve-disease-browser-test.py`, preserving saved demonstration records.

No changes were committed, pushed or deployed. The temporary SSH setup is unrelated and remains pending.
