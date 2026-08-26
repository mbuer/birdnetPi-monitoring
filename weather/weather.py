#!/usr/bin/env python3

import json
import time
from datetime import datetime

import requests

URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=34.18"
    "&longitude=-118.31"
    "&current="
    "temperature_2m,"
    "relative_humidity_2m,"
    "pressure_msl,"
    "precipitation,"
    "cloud_cover,"
    "wind_speed_10m,"
    "wind_direction_10m,"
    "weather_code,"
    "is_day"

    "&daily="
    "sunrise,"
    "sunset"

    "&timezone=auto"

    "&temperature_unit=fahrenheit"
    "&wind_speed_unit=mph"
)

LOGFILE = "/var/log/weather/weather.log"

while True:
    try:
        response = requests.get(URL, timeout=10)
        response.raise_for_status()

        weather = response.json()

        current = weather["current"]

        sunrise = weather["daily"]["sunrise"][0]
        sunset = weather["daily"]["sunset"][0]

        current["sunrise"] = sunrise
        current["sunset"] = sunset

        # Unix timestamps (seconds since Jan 1, 1970)
        current["sunrise_unix"] = int(datetime.fromisoformat(sunrise).timestamp())
        current["sunset_unix"] = int(datetime.fromisoformat(sunset).timestamp())

        current["logged_at"] = datetime.now().isoformat()

        with open(LOGFILE, "a") as f:
            f.write(json.dumps(current) + "\n")

        print(f"{datetime.now().isoformat()} Weather logged", flush=True)

    except Exception as e:
        print(f"{datetime.now().isoformat()} ERROR: {e}", flush=True)

    # Wait 15 minutes before collecting the next sample
    time.sleep(900)
