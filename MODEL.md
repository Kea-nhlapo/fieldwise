# South Africa water model

How the South Africa workspace (`/`) turns weather and soil assumptions into a water-stress priority. This workspace demonstrates the crop water model only; its five farms are fictional and nothing here is calibrated to a real field.

## Assumptions and interpretation

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
