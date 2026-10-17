# Evidence → priority → farmer survey → officer action

Start `START-FIELDWISE.cmd`, open `http://127.0.0.1:8765/felix`, and select **Chimwemwe Farm (F014)**. This is a fictional Kasungu location from Tshego's source. The public provider responses are real; farm reports and telecom delivery are simulated.

## Presentation flow

1. **Explain the data boundary.** Environmental providers receive coordinates or the map extent, not farmer names or answers. Linking environmental data to identifiable farmers creates a different privacy problem. The introductory privacy statement makes that distinction before the survey.
2. **Show the retrieval receipts.** Open the weather and soil cards. Each shows the last attempt, last successful retrieval, current/bundled/stale/missing state, input role, and response hash. “View request & response” exposes the actual public request parameters, HTTP status, timestamps and original response text. “Fetch live evidence” makes new requests; loading a dashboard does not make hidden network calls.
3. **Explain the profile.** Show the weather window and soil depth. The risk panel separates environmental points, farmer reports, officer corrections and completion. It shows which receipt IDs contributed. The map provides spatial context and adds no points.
4. **Ask the targeted question.** A dry/hot flag asks about wilting; a rain/clay drainage flag asks about standing water; otherwise ask about a new crop problem. Queue the survey invitation to freeze its trigger, question, score and rank. It is labelled **LOCAL DRAFT, not sent**.
5. **Simulate voluntary participation.** Read the short purpose/data/retention notice and choose to participate. The API requires the choice too. No phone number, personal identifier or real farmer contact is collected. Declining or cancelling does not create a score penalty.
6. **Show what the answer changes.** A concern in the dry-weather scenario moves 62 → 117 points, a +55 report contribution. The impact panel preserves scores, ranks, action, response timestamp, notice version and participation timestamp. It compares immediately before/after the reply; the original queue-time snapshot is also retained. A receipt change between queueing and answering is therefore not attributed solely to the farmer.
7. **Let Felix decide.** Add a visit, correct the action or record completion. New concerns reopen a completed farm. The privacy panel exports the farm's report/survey/activity record or deletes only that farm's local reports, corrections and visit history.

## Actual retrieval verification, 17 October 2026

| Source | Verified result in the saved app database |
| --- | --- |
| Open-Meteo | HTTP 200 at **00:14:44 UTC / 02:14:44 SAST**; forecast 17–19 October; precipitation total **0.9 mm**, maximum temperature **33.0 °C**; receipt 4 |
| ISRIC SoilGrids | HTTP 200 at **00:14:45 UTC / 02:14:45 SAST**; mapped clay **16.6%**, depth **0–5 cm**; receipt 5 |
| OpenStreetMap / Overpass | First GET returned HTTP 406. Corrected, identified POST timed out at **00:15:11 UTC / 02:15:11 SAST**; receipt 6. The app shows the failed attempt and retains Tshego's labelled bundled map. **A live map retrieval has not been verified.** |

See `artifacts/live-evidence-verification.json`. No fixtures were used for these requests. The first weather/soil availability probes also succeeded, but the table refers specifically to the subsequent requests saved through the application. The verifier exits nonzero when any provider fails, even if the others work.

To make a new real check, run `.\.venv\Scripts\python.exe scripts\verify-live-evidence.py`. This saves new public-data receipts for F014 in the local app database. `--db PATH` selects a separate database. The script creates no survey and sends no messages.

## What a timestamp proves

The app records request start and response completion in UTC. It displays both local browser time and the ISO UTC timestamp. SHA-256 identifies the downloaded response bytes; it is a local integrity check, not provider-signed attestation.

Weather is a forecast, not a farm measurement. Open-Meteo's `generationtime_ms` is processing duration, not issue time. The UI shows a separate forecast window, timezone and returned grid coordinates in the receipt. No model-issue timestamp is invented. Units, three consecutive dates starting today, and finite values are validated. [Open-Meteo documentation](https://open-meteo.com/en/docs).

SoilGrids returns a mapped property. Clay uses the response's documented g/kg → percent conversion (divide by 10), with depth and unknown observation date shown. The mapped estimate is not current moisture. Calls are reserved transactionally and paced at one per 13 seconds, consistent with the provider's five-per-minute guidance. [ISRIC API guidance](https://rest.isric.org/), [SoilGrids documentation](https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs.html).

Overpass uses an identified POST and a fixed small extent; map calls are paced at one per 30 seconds. Partial responses with runtime warnings are rejected. A successful response would retain its OSM database timestamp separately from retrieval time. Failed requests preserve the bundle or previously valid retrieved geometry. [Overpass API documentation and usage guidance](https://wiki.openstreetmap.org/wiki/Overpass_API).

Weather expires after six hours or when its first forecast day is no longer today in Africa/Blantyre. Soil/map cache validity is a 30-day **demo policy**, not an agricultural validation claim. Last-success and last-attempt records remain distinct. An expired retrieved forecast is excluded rather than silently replaced by the bundled example. A never-fetched or initially failed weather source may use the explicitly labelled bundled scenario. Mixed source quality is labelled per farm.

## POPIA design scope

These controls are a prototype design response, not certification. Relevant POPIA principles include minimal collection, a specific purpose, justified retention, transparent notice, safeguards, and access/correction. Consent is one possible lawful basis, not the only one. Potentially significant decisions based solely on profiling need specific consideration; an officer override alone does not settle compliance. Cross-border disclosures also need assessment. [POPIA, sections 10–14, 18–24, 71–72](https://www.justice.gov.za/legislation/acts/2013-004.pdf).

Here, participation is explicitly simulated and recorded with notice version `fieldwise-demo-v1`. Responses stay locally until deleted; there is **no automatic retention job**. The app provides logical record deletion, not secure disk or backup erasure. It binds to loopback but has no application login, access roles or encrypted database. Before collecting real data, identify the responsible party/contact, applicable jurisdiction, lawful basis, retention schedule, security controls, operator arrangements and rights-request process. Malawi locations do not by themselves establish which law applies. [Information Regulator resources](https://inforegulator.org.za/popia/).

Actual USSD push is not provisioned or verified for this deployment. Africa's Talking's SDK alone does not create a working channel. A pilot must confirm operator/country support; an SMS invitation to a provisioned farmer-initiated service is a separate integration. The demo never labels a queued draft as delivered. [Provider USSD documentation](https://github.com/AfricasTalkingLtd/africastalking.Net#ussd).

## Implementation and checks

`fieldwise/evidence.py` handles public requests, validation, freshness and receipt persistence. `fieldwise/felix.py` joins evidence to the rules and stores survey snapshots. The original Flutter source and the South African water/disease workflows remain separate.

Automated provider tests use explicit fixtures, including failed and malformed responses. Browser checks use a disposable database. Real retrieval results above were verified separately; `scripts/live-evidence-browser-check.cjs` captures the saved receipts read-only. See `VALIDATION.md` for the final test results. No code was committed, pushed or deployed.
