"""Weather input boundary: explicit provenance, metric units, no silent gaps."""
import math
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def validate_weather(rows):
    if not rows:
        raise ValueError('Weather series is empty.')
    previous = None
    for row in rows:
        day = date.fromisoformat(row['date'])
        if previous and day != previous + timedelta(days=1):
            raise ValueError('Weather dates must be unique, ordered and contiguous.')
        previous = day
        for key in ('et0_mm', 'rain_mm', 'tmax_c', 'tmin_c'):
            value = row.get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f'Missing or invalid {key} on {day}.')
        if row['et0_mm'] < 0 or row['rain_mm'] < 0 or row['tmax_c'] < row['tmin_c']:
            raise ValueError('Weather values are out of bounds.')
    return rows


def demo_weather():
    start = datetime.now(ZoneInfo('Africa/Johannesburg')).date()
    return [dict(date=(start + timedelta(days=i)).isoformat(),
                 et0_mm=round(5.2 + 0.7 * math.sin(i / 2), 2),
                 rain_mm=3.0 if i in (4, 10) else 0.0,
                 tmax_c=29.0, tmin_c=16.0, kind='synthetic') for i in range(14)]


def fetch_forecast(latitude, longitude):
    import openmeteo_requests
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError('Invalid coordinates.')
    client = openmeteo_requests.Client()
    response = client.weather_api('https://api.open-meteo.com/v1/forecast', params={
        'latitude': latitude, 'longitude': longitude,
        'daily': ['et0_fao_evapotranspiration', 'precipitation_sum',
                  'temperature_2m_max', 'temperature_2m_min'],
        'timezone': 'Africa/Johannesburg', 'forecast_days': 7,
        'temperature_unit': 'celsius', 'precipitation_unit': 'mm',
    }, timeout=20)[0]
    daily = response.Daily()
    arrays = [daily.Variables(i).ValuesAsNumpy() for i in range(4)]
    count = int((daily.TimeEnd() - daily.Time()) / daily.Interval())
    if daily.Interval() != 86400 or count != 7 or any(len(a) != count for a in arrays):
        raise ValueError('Unexpected forecast shape or daily interval.')
    rows = []
    for i in range(count):
        local_day = datetime.fromtimestamp(daily.Time() + i * daily.Interval()
                                          + response.UtcOffsetSeconds(), timezone.utc).date()
        rows.append(dict(date=local_day.isoformat(), et0_mm=float(arrays[0][i]),
                         rain_mm=float(arrays[1][i]), tmax_c=float(arrays[2][i]),
                         tmin_c=float(arrays[3][i]), kind='forecast'))
    validate_weather(rows)
    return {'rows': rows, 'source': 'Open-Meteo forecast (modelled, not observed)',
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'timezone': 'Africa/Johannesburg', 'latitude': latitude, 'longitude': longitude}
