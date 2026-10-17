import json
import math
import os

import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "kasungu_weather.json")

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession(os.path.join(BASE_DIR, ".cache"), expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

# Make sure all required weather variables are listed here
# The order of variables in hourly or daily is important to assign them correctly below
HOURLY_VARIABLES = ["temperature_2m", "soil_temperature_6cm"]
DAILY_VARIABLES = ["precipitation_sum", "rain_sum", "leaf_wetness_probability_mean", "relative_humidity_2m_mean"]

url = "https://api.open-meteo.com/v1/forecast"
params = {
	"latitude": -13.0333,
	"longitude": 33.4833,
	"daily": DAILY_VARIABLES,
	"hourly": HOURLY_VARIABLES,
}
responses = openmeteo.weather_api(url, params = params)

# Process first location. Add a for-loop for multiple locations or weather models
response = responses[0]


def time_index(block):
	return pd.date_range(
		start = pd.to_datetime(block.Time(), unit = "s", utc = True),
		end = pd.to_datetime(block.TimeEnd(), unit = "s", utc = True),
		freq = pd.Timedelta(seconds = block.Interval()),
		inclusive = "left"
	)


def build_dataframe(block, names):
	data = {"date": time_index(block)}
	for i, name in enumerate(names):
		data[name] = block.Variables(i).ValuesAsNumpy()
	return pd.DataFrame(data = data)


def clean(value):
	if isinstance(value, float) and math.isnan(value):
		return None
	return round(value, 3) if isinstance(value, float) else value


def records(df):
	rows = []
	for row in df.to_dict(orient = "records"):
		rows.append({
			key: (row[key].isoformat() if key == "date" else clean(float(row[key])))
			for key in row
		})
	return rows


hourly_dataframe = build_dataframe(response.Hourly(), HOURLY_VARIABLES)
daily_dataframe = build_dataframe(response.Daily(), DAILY_VARIABLES)

# Aggregate every hourly variable into one value per day (mean, min, max)
hourly_dataframe["day"] = hourly_dataframe["date"].dt.floor("D")
hourly_daily = hourly_dataframe.groupby("day")[HOURLY_VARIABLES].agg(["mean", "min", "max"])
hourly_daily.columns = [f"{name}_{stat}" for name, stat in hourly_daily.columns]
hourly_daily = hourly_daily.reset_index().rename(columns = {"day": "date"})
daily_dataframe = daily_dataframe.merge(hourly_daily, on = "date", how = "left")

output = {
	"location": {
		"name": "Kasungu, Malawi",
		"latitude": response.Latitude(),
		"longitude": response.Longitude(),
		"elevation_m": response.Elevation(),
		"utc_offset_seconds": response.UtcOffsetSeconds(),
	},
	"daily": records(daily_dataframe),
}

os.makedirs(DATA_DIR, exist_ok = True)
with open(OUTPUT_FILE, "w") as f:
	json.dump(output, f, indent = 2)

print(f"Saved {OUTPUT_FILE}")
print(f"Daily records: {len(output['daily'])}")
