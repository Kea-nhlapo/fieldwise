# Fieldwise — local hackathon prototype

A working Python application connecting maize water-balance scenarios, farmer replies, inspection priorities, and a feasible visit plan. No GitHub account, cloud deployment, or SMS credentials are needed to run it.

Tshego's Kasungu officer workflow is available from **Tshego's Kasungu workspace** at the top of the dashboard, or directly at `/felix`. It now presents timestamped environmental retrievals → an explained risk/priority profile → a targeted simulated survey → before/after officer action. Weather and soil retrievals have real saved receipts; live map retrieval failed and its bundled fallback is labelled. See [EVIDENCE-FLOW.md](EVIDENCE-FLOW.md) for the demonstration and privacy design, and [TSHEGO-INTEGRATION.md](TSHEGO-INTEGRATION.md) for source attribution.

## Start on this computer

Double-click **START-FIELDWISE.cmd**, keep its terminal open, then visit **http://127.0.0.1:8765**. Press Ctrl+C in that terminal to stop.

Or, in PowerShell:

```powershell
cd C:\Users\DellUser\fieldwise
.\start.ps1
```

The server binds only to this computer. There is no application login: do not expose it to a network. The API reference is at `/docs`. Port already in use means another copy may be running; open the URL or choose another port with `start.ps1 -Port 8766`.

## Demo in two minutes

1. Select **Makhaya Maize**. Compare working irrigation and interrupted irrigation on the water-depletion chart.
2. Click **2 Interrupted** to simulate a farmer reply. Watch the projected depletion and priority increase. Click **1 Working** to compare again.
3. Click **Create local SMS draft**. The question is saved in the activity log; no text message is sent.
4. Choose a 2-, 4-, or 8-hour day and click **Plan Felix's visits**. The planner includes 35-minute inspections and the return to the depot; it identifies deferred farms.
5. Optionally select **Fetch 7-day forecast** for the selected farm. An explicit request goes to Open-Meteo for its coordinates. Network failures preserve the previous data. **Use demo weather** restores the synthetic 14-day dry spell.
6. Select **Ubuntu Fields**, then under **Disease monitoring**, save a simulated grey-leaf-spot symptom report. Its inspection-priority floor becomes 80 and an alert appears for Felix. Acknowledge it, then resolve it after review. Water calculations stay unchanged.
7. Open **Explore disease forecast trends**. The default is an explicitly synthetic offline sample. Switch between maize/soybean diseases and reference stations. **Fetch UW reference** requests Wisconsin station forecasts only; the documented upstream endpoint returned HTTP 404 during verification, so live disease retrieval is currently unverified/unavailable. These references never affect local farms.

Replies, outreach drafts and downloaded forecasts persist in `data/fieldwise.db`. The five farms are fictional. Initial seeded replies are demo assumptions, not real messages. Forecasts are snapshots with a visible retrieval timestamp; refresh them before reuse. Scenario day 1 uses assumed starting moisture, not a moisture estimate carried forward from previous runs.

## What is implemented

| Component | Implementation |
| --- | --- |
| Crop water balance | Actual pyfao56 1.4.3 calculations; both irrigation scenarios |
| Weather | Offline synthetic daily data and Open-Meteo Python client, seven local-calendar forecast days |
| Farmer responses | Local simulator with input validation and persistent event log |
| Disease monitoring | Maize grey leaf spot / tar spot observations; no locally validated disease prediction |
| Officer alerts | Persistent local queue with acknowledgement, resolution, deduplication and priority floors |
| Disease reference explorer | UW API adapter, saved snapshots, trend chart, four crop/disease options, and labelled synthetic sample |
| Outreach | Local SMS drafts; Africa's Talking SDK installed for a later integration |
| Inspection priority | Explicit rule using water depletion, days above threshold and reported interruption |
| Visit scheduling | OR-Tools with service time, day budget, depot return and weighted penalties for omitted visits |
| UI | Responsive, locally served dashboard; no frontend build or external assets |

Live Africa's Talking delivery, inbound SMS/USSD webhooks, farmer registration, authentication, real road routing, and production deployment are **not implemented**. Do not supply credentials until a real provider integration is agreed. AquaCrop was intentionally not added: one crop engine is enough for this milestone.

The disease extension is documented in [DISEASE.md](DISEASE.md). It does not install the UW Streamlit app, VIPS services or the R epicrop model. No LLM is used. UW reference data is for Wisconsin and cannot be assigned to the South African demo farms. Local disease risk remains **Not assessed**, including after a symptom report; observations request inspection and do not diagnose a disease.

## Model assumptions and interpretation

The dashboard demonstrates a short **mature maize** scenario. A pyfao56 `Update` holds the basal crop coefficient at 1.1 and plant height at 2 m; root depth is fixed per farm. This is not a sowing-to-harvest crop-growth prediction. Soil field capacity, wilting point, rooting depth and initial depletion vary across the fictional farms. They are not copied from the upstream Colorado trial and are not calibrated for South Africa.

Working irrigation applies **30 mm every four days**, starting on the first model day, at **85% efficiency**. Interrupted and rainfed scenarios apply zero irrigation for the entire window. The available-water depletion fraction is fixed at 0.55. Wind uses pyfao56's 2 m/s default; minimum humidity is estimated by pyfao56 from daily minimum/maximum temperatures. Daily reference evapotranspiration is supplied directly. These assumptions are disclosed in the UI.

`Dr` is root-zone water depletion in mm; larger values mean drier soil. `TAW` is total available root-zone water. `RAW` is readily available water; depletion beyond RAW marks the stress threshold used by this prototype. `Ks` ranges from 0 to 1. Synthetic and forecast weather are never labelled as measurements. Dates, finite numbers, nonnegative precipitation/ET0 and daily continuity are validated; missing weather is rejected, not silently replaced with zero.

Priority = min(100, rounded(60 × end depletion/TAW + 25 × fraction of days above RAW + 15 if interruption reported)). Urgent ≥70; Watch ≥40; otherwise Routine. Unknown replies provisionally use functioning irrigation and are flagged as unconfirmed. A farmer reply changes the scenario, not the model's calibration or confidence. Confidence remains low. Changing assumptions invalidates the displayed route until you replan.

That formula remains the **water priority**. Final inspection priority is the maximum of water priority and unresolved disease-observation floors: 80 for symptoms and 50 for uncertainty. These are explicit hackathon triage rules, not disease probabilities. Acknowledgement preserves the floor; resolution removes it. A later positive/uncertain report reopens the same alert. A report of no symptoms does not automatically resolve an officer alert.

Route travel times use great-circle distance ×1.3 at 45 km/h, rounded up to minutes. The illustrative depot is (-26.05, 28.55). Omitted-visit penalties are 1000 +100×priority score. The solver has a 250 ms search budget and returns a feasible plan, not a guarantee of the global optimum. Travel estimates are not driving directions, and no appointment windows are supplied yet. Replace this matrix with road travel times for real operations.

## Reproduce the upstream maize milestone

```powershell
.\.venv\Scripts\python.exe scripts\run_maize_example.py
```

This runs the basic test05 parameters, weather and irrigation schedule from pyfao56's **Greeley, Colorado, 2022** maize example over 171 days, then repeats with irrigation removed. It writes CSVs, a PNG chart and JSON summary into `artifacts/`. These input files are kept under `examples/upstream-maize/` with provenance and license information. The upstream data is only used by this reproduction script, not the dashboard's fictional South African fields.

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
node --check static\app.js
```

The suite checks scenario differences, bounded stress coefficients, invalid soil/weather, SQLite persistence and cleanup, reply validation, local-only drafts, route budgets and deferred visits. Browser smoke checks live in `scripts/browser-smoke.cjs`; use Playwright with Edge and a running local server. They modify demo replies/drafts, so run them against a disposable database or reset those demo values afterward. Screenshots are written to `artifacts/`.

## Setup on another computer

Use Python 3.12. In the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start.ps1
```

The installed environment on this computer uses the existing Codex Python 3.12 runtime, because the system `python` command is a nonworking Windows Store alias. The launcher calls the project environment directly. Do not copy `.venv` between computers; recreate it from the pinned requirements. Runtime data, environments, logs and `.env` files are ignored by Git. No Git repository, remote, commit or push was created by this setup.

## Handoff structure

- `fieldwise/engine.py`: pyfao56 adapter and priority rules
- `fieldwise/weather.py`: validated synthetic weather and Open-Meteo adapter
- `fieldwise/storage.py`: SQLite persistence and fictional seed farms
- `fieldwise/planning.py`: OR-Tools route planning
- `fieldwise/disease.py`: crop/disease catalogue, observation triage and UW reference adapter
- `fieldwise/app.py`: FastAPI endpoints
- `static/`: browser dashboard
- `tests/`: local integration and calculation checks
- `scripts/run_maize_example.py`: reproducible upstream milestone

Next integration work: real farm inputs and moisture initialization, agronomist-reviewed calibration/priority thresholds, provider sandbox callbacks, authenticated users, and a road-time matrix. GitHub authentication can be configured later when Tshegofatso is available; this app does not use the temporary SSH key.

## Sources

- pyfao56: https://github.com/kthorp/pyfao56
- Upstream maize example: https://github.com/kthorp/pyfao56/tree/main/tests/test05
- Open-Meteo: https://open-meteo.com/en/docs — weather data attribution to Open-Meteo; check service terms before production/commercial use.
- OR-Tools routing: https://developers.google.com/optimization/routing/penalties
- Africa's Talking SDK (future integration): https://github.com/AfricasTalkingLtd/africastalking-python
- UW disease-reference API contract: https://github.com/UW-Madison-DSI/llm-ag-forecasting-app
