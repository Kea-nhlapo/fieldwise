# Fieldwise

Fieldwise helps a field officer decide which farm to visit first, and shows why. It combines:
- public weather, soil and map data;
- short USSD check-ins that farmers answer on a basic phone;
- what the officer finds on each visit.

It runs offline in the field and syncs when the signal returns.

Hackathon prototype: the farms are fictional, and nothing has been validated on real farms yet.

## Three settings, three roles

Each setting demonstrates a different part of the idea. They are not one system validated in one place.

| Setting | What it shows | Open it |
|---|---|---|
| **Kasungu, Malawi** (Tshego's eight scenario farms) | The officer workflow: timestamped evidence → explained priority → USSD survey → visit → learning from the visit outcome | `/felix` |
| **South Africa** (five fictional maize farms) | The crop water model (pyfao56): how a farmer's "irrigation stopped" reply changes water stress and priority | `/` |
| **Bomet County, Kenya** (100 simulated farms) | A simulation of 7-day reach: how often new fall armyworm and MLN problems get a visit within a week under three scheduling rules | `/simulation` |

## Run it

Double-click **START-FIELDWISE.cmd** and open **http://127.0.0.1:8765**. Keep the window open; Ctrl+C stops it.

- **Officer PIN:** the launcher sets a demo PIN of **2468** and prints it. Set `FIELDWISE_OFFICER_PIN` yourself for anything beyond a demo.
- **USSD phone simulator:** `/ussd-simulator`. Sign in on another page first, because the simulator needs an officer session.
- **Docker:**
  ```bash
  docker build -t fieldwise .
  docker run -p 8765:8765 -v fieldwise-data:/app/data -e FIELDWISE_OFFICER_PIN=<pin> fieldwise
  ```
- **Setup on a new computer** (Python 3.12):
  ```bash
  python -m venv .venv
  .venv/Scripts/python.exe -m pip install -r requirements.txt
  ```

The 6-minute pitch, with clicks and expected numbers, is in [DEMO-SCRIPT.md](DEMO-SCRIPT.md).

## What works

| Area | Status |
|---|---|
| Live public data | Open-Meteo weather, ISRIC SoilGrids soil and OpenStreetMap requests, each saved with a timestamped receipt. Failures are shown, not hidden. |
| Explained priority | Every score breaks down into environment, farmer report, officer correction and learned points. The officer can override it. |
| Survey targeting | For each farm, Fieldwise scores both possible answers and asks the farmers whose answer would change the day's visits. |
| USSD check-in | `/ussd` answers in Africa's Talking's callback format (`CON`/`END`), with consent first and branching questions. It is fuzz-tested so bad farmer input never produces an error page. The provider callback only accepts requests carrying `FIELDWISE_USSD_KEY`; the in-app phone simulator uses an officer-only route. Telecom delivery is **not** provisioned. |
| Learning from visits | One-tap visit outcomes update a Beta–Bernoulli estimate of how often each signal turns out to be a real problem. |
| Offline-first | A service worker caches the app. An outbox holds offline actions and syncs each one exactly once. |
| Officer access | A PIN guards every change and every read of farmer records. Sessions last 12 hours, and five wrong PINs lock sign-in for 5 minutes. **Sign out** deletes cached farm records and unsynced actions from the device. |
| Impact metrics | `/impact`, split into measured outcomes, activity and labelled model estimates. Each metric has a definition, and the de-identified event log is downloadable. |
| Simulation | `/simulation`: 200 seeded seasons, with an experienced-officer comparison, no-signal controls, ablation, weight sensitivity and a scale test. See [SIMULATION.md](SIMULATION.md). |
| Water model | pyfao56 water balance for the South Africa farms. See [MODEL.md](MODEL.md). |
| Accessibility | axe-core finds 0 WCAG 2.1 AA violations on every page at desktop and mobile sizes. |

## What the simulation does and doesn't show

In simulation, Fieldwise reached 58% of new problems within 7 days. Basic rotation reached 23%, and an experienced officer who chases farmer reports reached 54%.

- **Its edge over that officer is small and inconsistent:** ahead in 125 of 200 seasons, tied in 20, behind in 55.
- **The edge comes from MLN.** Fieldwise follows MLN to neighbouring farms.
- **It disappears when every signal is scrambled.**
- **The comparison was designed in advance.** Its design and expected results were committed to git before the first comparison ran.

We make no claim about crop losses avoided.

## Before a real pilot

These are known gaps, not oversights:

- **USSD delivery.** Register `/ussd` with a USSD code from a provider, and set `FIELDWISE_USSD_KEY`. Without that key the callback is switched off.
- **Tying a caller to a farm.** Anyone who knows a farm number can answer for it. The proposed fix is a short farm code printed on each farmer's card: it avoids storing phone numbers, at the cost of one extra step. See the pilot plan (`/pilot`).
- **Offline data at rest.** Cached records are deleted on sign-out, but they are not encrypted while signed in.
- **Accounts.** There is one shared officer PIN, with no per-officer accounts or audit trail of who changed what.
- **Validation.** Thresholds and simulation rates are plausible assumptions. A pilot has to measure them.
- **Legal.** Data protection duties under Malawi's Data Protection Act 2024 (MACRA), and under POPIA in South Africa, need a compliance assessment.

## Privacy choices

- Weather, soil and map providers receive only coordinates or a map area. They never receive a farmer's name or answers.
- Farmers agree before any question, and saying no saves nothing.
- Fieldwise never stores phone numbers.
- A farm's reports can be exported or deleted. Impact counts contain no personal data, so they survive deletion.

## Checks

```bash
.venv/Scripts/python.exe -m unittest discover -s tests
node scripts/offline-a11y-check.cjs http://127.0.0.1:<port>
node scripts/pin-check.cjs http://127.0.0.1:<port>
node scripts/record-demo.cjs http://127.0.0.1:<port>
.venv/Scripts/python.exe scripts/run_simulation.py
```

What each one does:
- **Unit tests:** 90+ tests.
- **`offline-a11y-check.cjs`:** offline install, outbox sync and accessibility.
- **`pin-check.cjs`:** the sign-in and sign-out flow. Run it against a server started with a PIN.
- **`record-demo.cjs`:** plays the whole stage demo and saves screenshots.
- **`run_simulation.py`:** reproduces the simulation results (seeded, about a minute).

Run the browser scripts against a throwaway server, not the live demo: they reset demo data.

## More detail

- [EVIDENCE-FLOW.md](EVIDENCE-FLOW.md): evidence receipts and the privacy design in the Kasungu workflow.
- [TSHEGO-INTEGRATION.md](TSHEGO-INTEGRATION.md): how Tshego's Flutter app was adapted.
- [OFFLINE-AND-IMPACT.md](OFFLINE-AND-IMPACT.md): offline layer and impact metrics.
- [DISEASE.md](DISEASE.md): disease observations and the UW reference explorer.
- [DESIGN.md](DESIGN.md): design references.
- [TRANSLATION.md](TRANSLATION.md): farmer-facing text, ready for a Chichewa translator.

## Sources and licences

- [pyfao56](https://github.com/kthorp/pyfao56), [OR-Tools](https://developers.google.com/optimization).
- [Open-Meteo](https://open-meteo.com) (check terms before commercial use), [ISRIC SoilGrids](https://soilgrids.org) (CC BY 4.0), map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) (ODbL).
- Photos are public domain or CC0, credited in `static/photos/CREDITS.md`. Icons are Health Icons (CC0) and Lucide (ISC), see `static/icons/LICENSE.txt`.
- The extension-worker figure (2,017 farmers per worker in 2021/22) is from the Government of Malawi Ministry of Agriculture's *2021–2022 Agriculture Sector Performance Report*, p. 19.
