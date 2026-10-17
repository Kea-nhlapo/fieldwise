# Validation — 17 October 2026

## Tshego integration verification

- Full Python suite: **28 tests passed**, including seven tests for the new Kasungu workflow. The existing Starlette/httpx deprecation warning remains.
- Edge checked navigation from the original dashboard, eight offline map pins, branching farmer check-in, 117-point concern ranking, saved shortlist, visit completion, persistence after reload, reopening and safe rendering of user-entered notes.
- Desktop 1440 px and mobile 390 px checks passed with no page errors or horizontal overflow. Both screenshots were visually reviewed.
- Original Flutter source was preserved. Flutter/Dart were not found on PATH; native build and native tests were not run. See [TSHEGO-INTEGRATION.md](TSHEGO-INTEGRATION.md).

## Disease extension verification

- Full suite after disease changes: **21 tests passed** (the original 9 plus 12 disease-adapter/workflow tests).
- JavaScript checks passed for `static/app.js` and `static/disease.js`; no new dependencies were added and `pip check` still passes.
- Headless Edge verified symptoms → automatic local alert → acknowledgement → resolution → reopening. Ubuntu's combined inspection priority went **10 → 80 → 10 → 80**, while its water-depletion result stayed unchanged.
- The browser also verified disease-question drafts, route generation, four reference disease options, synthetic trend rendering, missing/inactive values and cache selection. A simulated upstream failure exercised the visible error state without relabelling the synthetic sample as live data.
- Desktop (1440 px) and mobile (390 px) checks passed with no page errors or horizontal overflow. Screenshots were visually reviewed; `artifacts/disease-desktop.png` and `artifacts/disease-mobile.png` show the new sections.
- UI tests used a separate temporary SQLite database on port 8766. The saved application database still contains its five farms, zero disease alerts and zero activity entries after testing.
- **Live UW provider test did not succeed:** the documented public endpoint returned HTTP 404 for model-run date 2026-07-14 and a seven-day horizon. Successful parsing/date mapping is fixture-tested; live disease forecasting is not verified operational. Local farms retain `Not assessed` disease risk, and Wisconsin/synthetic reference records never affect local priorities.
- No live messaging, model scheduling, cloud deployment or Git operations were performed. The test server is stopped after verification.

## Passed

- Python 3.12.14 isolated environment; all installed versions pinned in `requirements.txt`.
- `python -m unittest discover -s tests -v`: **9 tests passed**.
- `python -m pip check`: no broken requirements.
- `node --check static/app.js`: JavaScript syntax valid.
- Full 171-day upstream pyfao56 maize example ran with irrigation and with irrigation removed. Average depletion: **44.03 vs 73.94 mm**. Total actual evapotranspiration: **723.70 vs 218.72 mm**. CSVs, JSON and a PNG are in `artifacts/`.
- Open-Meteo Python client fetched seven valid forecast days for the fictional Delmas plot. First day: 2026-10-17; ET0 6.2548 mm, precipitation 0 mm, Tmax 30.95 °C, Tmin 16.30 °C. This was an actual provider request, not a fixture.
- Headless Microsoft Edge exercised selection, simulated farmer response, local outreach draft, route planning and priority filtering. Makhaya's projected end depletion changed **10.5 → 97.8 mm** after an interruption response.
- Browser checks at 1440 px and 390 px: no JavaScript page errors and no mobile horizontal overflow. Screenshots were visually inspected.
- Real HTTP server served the application on `127.0.0.1:8765` during browser tests.

## Verification environment notes

Windows sandbox restrictions blocked loopback socket creation, so FastAPI integration tests and the preview server were run with approved access outside the sandbox. An early model initialization error and SQLite connection cleanup issue were fixed before the passing run. The test runner emits upstream Starlette/httpx and OR-Tools SWIG deprecation warnings; they do not fail the tests.

## Boundaries

No live SMS was sent. Africa's Talking SDK installation does not imply provider provisioning or delivery verification. Travel times are estimates, farms are fictional, and crop/soil assumptions have not been field-calibrated. No real farm forecasts or operational irrigation recommendations have been validated. Automatic GitHub SSH revocation and repository authentication remain separate pending tasks. Nothing was committed, pushed or deployed.

The test preview is stopped after verification. Start the app with `START-FIELDWISE.cmd` or `start.ps1` when needed.
