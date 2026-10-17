# Upstream maize inputs

Downloaded from the public `kthorp/pyfao56` repository, `tests/test05`, on 17 October 2026 (Africa/Johannesburg):

- `E12FF2022.par`: trial crop and soil parameters
- `E12FF2022.irr`: irrigation schedule
- `LIRF.wth`: trial weather

Source: https://github.com/kthorp/pyfao56/tree/main/tests/test05

The trial is the E12 full-irrigation maize treatment at the Limited Irrigation Research Farm, Greeley, Colorado, 2022. The reproduction script uses the basic model from 2022-129 to 2022-299 with `cons_p=True`, then repeats without irrigation. It does not use the layered-soil or canopy-update variants.

Files were downloaded through GitHub's contents API and decoded without edits. `SHA256.json` records their local hashes. `LICENSE.md` is copied from the installed pyfao56 1.4.3 distribution: public-domain/CC0 terms. No endorsement by the upstream authors is implied.

These trial inputs are used only by `scripts/run_maize_example.py`, not as calibrated South African farm parameters.
