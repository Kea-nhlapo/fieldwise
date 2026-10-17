# FieldWise mobile

Flutter frontend for Felix, a field officer managing farms around Kasungu.

## Run

```sh
flutter pub get --enforce-lockfile
flutter run
```

The entrypoint is `lib/main.dart`. Its Home, Farm, Insights, and Profile shell
uses Farmable's cards and carousel. The Farm tab includes a bundled offline
Kasungu map. See `lib/features/felix/README.md` for the screen flow, weather
sources, and simulated interactions.

The internal Dart package is still named `almanac` because the inherited
Farmable source imports it by that name. The installed app is labelled
FieldWise.
