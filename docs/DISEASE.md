# Disease monitoring extension

## Two separate workflows

**Local farms:** grey leaf spot and tar spot monitoring for the fictional maize farms. Record a simulated observation (symptoms / none noticed / uncertain) and optional notes. Reports are stored in the farm's SQLite payload, with an activity log. Disease risk remains `null` / **Not assessed** because there is no locally validated disease model connected.

**Reference explorer:** a separate Wisconsin disease-forecast viewer informed by UW–Madison's documented API. It includes grey leaf spot and tar spot for maize, frogeye leaf spot for soybean, and the non-irrigated white-mould output for soybean. Other white-mould irrigation variants are not included. Reference records are never joined to South African farms and cannot create local alerts or change inspection priority.

The offline reference data is synthetic, uses fictional station labels and illustrative curves, and is prominently marked as such. It is neither UW output nor a local disease model. It is available without internet so the interface can be demonstrated.

## Alerts and priority

A positive symptom report automatically creates one local officer alert per farm/disease. Its priority floor is 80. An uncertain report uses 50. The final queue and OR-Tools routing use `max(water_priority, highest_unresolved_alert_floor)`, not the sum of unrelated disease probabilities.

- `open`: awaiting Felix's review.
- `acknowledged`: seen, still needs inspection; priority floor remains.
- `resolved`: review complete; that alert no longer raises priority.
- A new symptom/uncertain report reopens a resolved alert with the newly reported severity.
- Repeated reports update the same alert rather than creating duplicate notifications.
- A less severe report cannot downgrade an unresolved higher-priority alert. Its latest summary may change, while the previous high-priority floor remains until review.
- “None noticed” updates the observation but neither rules out disease nor closes an alert.

These are demonstration triage rules, not a clinical/agronomic diagnosis. No treatment recommendations are generated. Alerts are visible in the local application only; no SMS, email, browser push or external notification is sent. Disease questions can be saved as local SMS drafts.

## UW adapter and availability

Documented endpoint:

`GET https://connect.doit.wisc.edu/ag_forecasting_api/v2/ag_models_wrappers/wisconet_g`

For a requested forecast **target date**, the adapter sends the preceding day as the provider's `forecasting_date` and passes `risk_days` from 1 to 7, following upstream `features/api.py`. It reads station metadata and `timeseries[].data[]` key/value records following the documented schema. Field names are taken from upstream `features/config.py`.

The adapter accepts risk indices in [0,1], preserves provider classes, strips numerical class prefixes and treats `-1`/Inactive separately from missing/invalid data. Missing values are never converted to zero. It rejects duplicate station/date records, empty/malformed payloads and returned dates outside the requested window. Inactive or missing points break chart lines rather than being plotted as zero.

**Live verification on 17 October 2026:** a request for model-run date 2026-07-14 and seven risk days reached the documented endpoint and returned HTTP 404. The live integration therefore cannot currently be claimed operational. The app shows an explicit failure, retains any existing saved reference, and offers a separate offline-sample action; it never silently replaces a failed live request with synthetic data.

Successful future responses are stored in SQLite keyed by target date and horizon. **Load saved reference** reads only local storage. Snapshots older than 24 hours are labelled stale. Their original target dates and retrieval time remain visible. There is no automatic remote polling or scheduler: only **Fetch UW reference** performs an external request. It sends a date and horizon, not local farm coordinates or farmer notes.

## API

| Method and endpoint | Purpose |
| --- | --- |
| `POST /api/farms/{id}/disease-observations` | Body: `disease_id`, `status` (`symptoms`, `none`, `uncertain`), optional `notes` (500 characters max) |
| `POST /api/farms/{id}/disease-outreach` | Body: `disease_id`; saves a local question draft |
| `GET /api/disease/alerts` | Lists current and resolved local alerts |
| `PATCH /api/disease/alerts/{id}` | Body: `state` (`acknowledged` or `resolved`) |
| `GET /api/disease/reference/demo` | Explicit synthetic interface sample |
| `GET /api/disease/reference?target_date=YYYY-MM-DD&risk_days=N` | Reads a saved reference without network access |
| `POST /api/disease/reference?target_date=YYYY-MM-DD&risk_days=N` | Requests and validates UW reference data |

Existing `/api/dashboard` responses now include separate `water_priority`, combined `priority`, local disease status, catalogue and alerts. Existing water endpoints and calculations are unchanged. The SQLite update is additive: new tables use `CREATE TABLE IF NOT EXISTS`; existing farms and history are preserved. No new packages were required.

## Re-test locally

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check static\app.js
node --check static\disease.js
```

For browser checks, start a disposable server with `scripts/serve-test.py` (temporary database, so your saved demo activity is untouched) and run the checks listed in the README against it.

## What remains before real deployment

Identify and validate disease models suitable for the crop, season, location and available measurements. Some models need hourly humidity, leaf wetness, growth stage, previous observations or inoculum information that the existing water-balance inputs do not supply. Validate geographic applicability before connecting model output to local alerts. Add authenticated officer identities and genuine inbound messaging before representing a simulated report or review as a real person's action.

VIPS was retained as an architectural reference (model execution, observations, stored results and subscriptions), not installed as a Java/PostGIS service or incorporated as AGPL source. The rice-focused epicrop package was not installed in this maize prototype. The UW Streamlit frontend was not cloned into this app; Fieldwise uses its own existing dashboard and an original adapter to the documented public API. No upstream implementation code, logos or branding were copied.

Source inspected: https://github.com/UW-Madison-DSI/llm-ag-forecasting-app — README, `features/api.py`, `features/config.py` and `features/data.py`.
