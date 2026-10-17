# FieldWise

Field officer decision support for Kasungu, Malawi. The Flutter frontend lives
in [`apps/mobile`](apps/mobile/). The Kasungu weather fetch script and its dated
JSON output remain in [`src`](src/).

## Run the mobile app

Install Flutter 3.47.1 or a compatible SDK, then:

```sh
cd apps/mobile
flutter pub get --enforce-lockfile
flutter run
```

`lib/main.dart` opens the Felix field officer experience. No backend is needed
to navigate the current frontend. See
[`apps/mobile/lib/features/felix/README.md`](apps/mobile/lib/features/felix/README.md)
for the demo flow and data limitations.

The app bundles the dated Kasungu forecast from `src/data/kasungu_weather.json`
for offline use, then requests fresh weather from Open-Meteo and mapped clay
from SoilGrids when connected. The map includes an offline Kasungu road and
waterway extract from OpenStreetMap data (© OpenStreetMap contributors, ODbL).

Farmer records, USSD answers, and notifications in the frontend are simulated
and stored only in memory. Real USSD and device push delivery require a service
integration.
