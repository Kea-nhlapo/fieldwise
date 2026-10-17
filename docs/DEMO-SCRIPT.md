# Fieldwise: 6-minute demo script

Numbers below come from an automated run of this exact flow (`node scripts/record-demo.cjs`). Backup screenshots for every step are in `artifacts/demo-backup/`, in order. If the Wi-Fi or the laptop fails, present from those.

## Before you go on stage

1. Start the app: double-click `START-FIELDWISE.cmd`.
2. Open these tabs, in this order:
   - `127.0.0.1:8765/felix`
   - `127.0.0.1:8765/ussd-simulator`
   - `127.0.0.1:8765/`
   - `127.0.0.1:8765/simulation`
   - `127.0.0.1:8765/impact`
   - `127.0.0.1:8765/pilot`
3. Sign in when the PIN dialog appears. The demo PIN is shown in the START-FIELDWISE window (2468 unless you set FIELDWISE_OFFICER_PIN). The session lasts 12 hours.
4. On the Felix tab, click **Reset demo data** (bottom of the sidebar) and confirm.
5. Still on Felix, click **Fetch live evidence** once. This saves fresh weather and soil receipts, so if the venue Wi-Fi dies later the app still shows real, timestamped data. The OpenStreetMap request sometimes fails with a 502 or 429; the app keeps the previous map and says so on screen.
6. Zoom the browser to 110–125% so the back row can read it.
7. Reload every tab twice. The offline cache updates in the background, so the first load after a code change can still show the previous version.

## The script

**Name the three settings once, early.** Each place shows a different part, and none is one system validated on real farms:
- **Kasungu** shows the officer workflow.
- **South Africa** shows the water model.
- **Bomet** is the simulation.

The opening line below does this.

Which farm sits at **Now #4** depends on the live weather you fetch, so it can change between rehearsal and stage. The script works with whichever farm is there; the reveal is always 62 → 117 points and rank 4 → 1.

| Time | Say | Do |
|---|---|---|
| **0:00–0:40** | "Felix is a co-op field officer with about 100 farms and time for four visits a day. When a pest or disease starts on one of them, the question is how fast he gets there. Government officers carry far more: in Malawi, one extension worker for every 2,017 farmers, by the Ministry of Agriculture's own figure. Fieldwise tells Felix which farm to visit first, and why. You'll see three places today: Kasungu for the officer's workflow, South African farms for the water model, and Bomet in Kenya for a simulation. All the farms are fictional." | Felix tab, top of the page. Point at the **Visit first** card. |
| **0:40–1:20** | "Every score starts from public data. Each number shows where it came from and when we downloaded it: Open-Meteo weather, ISRIC soil, OpenStreetMap. Those providers only receive coordinates: never a farmer's name or answers. Farmers' answers travel over USSD to our server, and we never store their phone numbers." | Scroll to Step 1. Point at a **Fetched · current** badge and its retrieval time. |
| **1:20–2:00** | "Public data can't see a wilting field. So we ask farmers, but only the ones whose answer would change Felix's day. For each farm, Fieldwise scores both possible answers. This farm is fourth. If the farmer says yes, it jumps into today's top three." | Scroll to **Step 3 · Choose who to ask**. Find the row marked **Now #4** and note its dial code (for example `*384*56#`). Click **Queue survey** on that row. |
| **2:00–3:00** | "The farmer has a basic phone. They don't need an app or a data bundle; they dial a USSD code." Dial, then read the consent screen aloud: "They agree first; saying no saves nothing, and we never store the phone number." | USSD tab. Type the dial code from that row and press **Call**. Answer `1` (agree), `1` (yes, wilting), `2` (several areas), `2` (more than one day). |
| **3:00–3:40** | "Back with Felix: that farm went from 62 to 117 points, from fourth to first. It's on today's route because a farmer answered three questions." | Felix tab, reload. Click that farm in the ranked list. Scroll to **What the farmer's answer changed**: 62 → 117, rank 4 → 1, +55. |
| **3:40–4:20** | "Felix visits. He taps what he found, with no typing. Each outcome teaches the model. One confirmed visit moved 'hot, dry forecast' from 50% to 60%, so every other dry farm now ranks a little higher." | Scroll up to **Record a visit**. Tap **Wilting confirmed** and **Follow up in 3 days**, then **Save visit**. Scroll to **What Felix's visits have taught the model**. |
| **4:20–5:00** | "Does it actually get Felix there sooner? We simulated 200 seasons around Bomet, Kenya: 100 farms, 4 visits a day, fall armyworm and maize lethal necrosis appearing over time. Basic rotation reached 23% of new problems within 7 days. An experienced officer who chases reports reached 54%. Fieldwise reached 58%. Its edge over a good officer is small, and it all comes from MLN: following MLN to neighbouring farms took MLN reach from 54% to 65%. When we scrambled every signal, Fieldwise did no better than rotation, so the gain comes from the data." | Simulation tab. Point at the **SIMULATED** badge, the three headline numbers, then the MLN bars. If there's time, show **Example day**. |
| **5:00–5:30** | "And we measure ourselves. Every figure here comes from a log that stores no names and no phone numbers. It works offline, and syncs when the signal returns." | Impact tab. Point at the four headline numbers. |
| **5:30–6:00** | "Next: an 11-week pilot with three officers and 900 farms, Running costs (USSD sessions and the server) come to about 17 cents per farm per season, on assumed prices; staff time, training and phones come on top. It measures one thing: does Felix reach new problems within 7 days more often than routine visits? We're looking for a partner to run it with." | Pilot tab. Point at **$0.17 cost per farm**. Stop. |

Source for the opening figure: Government of Malawi, Ministry of Agriculture, *2021-2022 Agriculture Sector Performance Report*, November 2022, section 3.5, p. 19 ([PDF](https://docs.dcafs-tipdep-donors-mw.org/dt_docs/DOC20230126080437.pdf)). The same paragraph says government already uses mobile phones as extension channels.

If you're running long, cut the visit-learning step (3:40–4:20). Keep the simulation step: it answers "does it work?".

Avoid crop-loss claims on stage. No study measures how much loss comes from late detection, so we lead on speed and coverage (7-day reach). The South Africa workspace still shows an estimated "maize at stake" figure; leave it out of the pitch.

## Questions judges will ask

**"Where's the AI?"**
Two parts. First, a Bayesian model learns from Felix's visit outcomes how often each signal turns out to be a real problem, and adjusts the scores. Second, survey targeting: we simulate both possible farmer answers and ask the farms whose answer would change the visit plan. We chose models that work with ten visits rather than ten thousand, and that run offline on a cheap server.

**"Are these real farms?"**
No. The eight Kasungu farms and the five South African farms are fictional scenarios. The weather, soil and map data are real, live requests with receipts. The water model is the real pyfao56 library.

**"Is the 445 kg real?"**
It's a model estimate, using FAO-33's maize yield response factor (Ky 1.25), 600 mm of seasonal crop water and 6 t/ha potential yield on 1 ha. It's counted once per interruption, however many times the farmer reports it. It isn't a loss avoided, and we keep it out of the pitch.

**"Can I trust every impact number?"**
The Impact page separates three kinds of number. *Measured outcomes* are what Felix found and how fast, including the share of visits that confirmed a problem. *Activity* is what people and the system did. *Model estimates* are labelled as estimates. Each tile shows its count and definition, and the event log underneath can be downloaded.

**"Why should we trust a simulation?"**
We fixed the assumptions and committed them to git before the first run; the history shows the order. Every rule faces the same 200 seasons, and Fieldwise never sees the simulation's true rates. When we scrambled reports, weather and Felix's own finds, Fieldwise fell to rotation's level. The page lists every assumption, and one command reproduces the numbers.

**"Does it beat an experienced officer?"**
Not reliably overall: +3.4 points on average, ahead in 125 of 200 seasons, tied in 20, behind in 55. It's level on fall armyworm, because both chase farmer reports, and ahead on MLN, because it follows MLN to the neighbours. At 250 farms per officer it trailed by 3.5 points; we show that on the page.

**"Why Bomet and MLN?"**
MLN spreads between neighbouring farms, so a neighbour's case says something about yours. Fall armyworm moths travel tens of kilometres a night, so a neighbour's report says little. We chose Bomet for the farm layout. If it's confirmed, mention that MLN was first reported in Kenya there in 2011; check the source before saying it.

**"Does the USSD actually work?"**
The menus speak Africa's Talking's callback format: same fields, and `CON`/`END` replies. The real callback, `/ussd`, is switched off until a secret key is set; the gateway is then registered as `/ussd?key=…`, so a random caller can't submit answers. The phone simulator uses an officer-only route with the same menus.

One step is still open: proving which farm a caller answers for. Our proposal is a short farm code on each farmer's card, so we never need to store phone numbers. It's in the pilot plan.

**"What about data protection?"**
In Malawi, the Data Protection Act 2024 applies, with MACRA as the regulator. In South Africa, it's POPIA. Fieldwise asks for consent before any question, stores farm numbers instead of phone numbers, lets a farm's reports be exported or deleted, and keeps impact counts free of personal data. We haven't had a compliance assessment yet; that's in pilot week 1.

**"What does it cost?"**
About $0.17 per farm per season for running costs only: USSD sessions and the server, at assumed prices the pilot page labels as assumptions. It leaves out staff time, officer training, phones and transport, which a pilot budget has to add. Weather, soil and map data are free open sources. We need a real Africa's Talking quote.

**"What if there's no signal?"**
The app keeps working offline. Actions wait in an outbox and sync once when the connection returns; a test checks that nothing is saved twice. Farmers only need a basic phone with network coverage for USSD.

**"Why would officers trust the score?"**
They can see every point: environment, farmer report, learned adjustment, their own correction. Felix can override any score, and the app counts how often he does.

## Facts to have ready

| Item | Value |
|---|---|
| Tests | 76 automated tests, all passing |
| Accessibility | axe-core: 0 WCAG 2.1 AA violations on all pages, desktop and mobile |
| Offline | Service worker caches every page, icon, photo and the simulation results; outbox syncs once, no duplicates |
| Data sources | Open-Meteo (weather), ISRIC SoilGrids (soil, CC BY 4.0), OpenStreetMap (ODbL) |
| Models | pyfao56 (FAO-56 water balance), Beta-Bernoulli learning, OR-Tools routing, 7-day-reach simulation (200 seeded seasons) |
