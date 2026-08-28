#!/usr/bin/env python3

import json
import time
from datetime import datetime

import psycopg
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

DB_DSN = "host=localhost dbname=birdnet user=birdnet"


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
        current["sunrise_unix"] = int(
            datetime.fromisoformat(sunrise).timestamp()
        )
        current["sunset_unix"] = int(
            datetime.fromisoformat(sunset).timestamp()
        )

        current["logged_at"] = datetime.now().isoformat()

        # Existing JSONL output used by Grafana Alloy / Loki
        with open(LOGFILE, "a") as f:
            f.write(json.dumps(current) + "\n")

        # Permanent structured storage in PostgreSQL
        with psycopg.connect(DB_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO weather_observations (
                        observed_at,
                        station_id,
                        temperature_f,
                        relative_humidity_pct,
                        pressure_msl_hpa,
                        precipitation_in,
                        cloud_cover_pct,
                        wind_speed_mph,
                        wind_direction_deg,
                        weather_code,
                        is_day,
                        sunrise,
                        sunset
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        current["logged_at"],
                        "birdnet",
                        current.get("temperature_2m"),
                        current.get("relative_humidity_2m"),
                        current.get("pressure_msl"),
                        current.get("precipitation"),
                        current.get("cloud_cover"),
                        current.get("wind_speed_10m"),
                        current.get("wind_direction_10m"),
                        current.get("weather_code"),
                        bool(current.get("is_day")),
                        current.get("sunrise"),
                        current.get("sunset"),
                    ),
                )

        print(
            f"{datetime.now().isoformat()} Weather logged",
            flush=True,
        )

    except Exception as e:
        print(
            f"{datetime.now().isoformat()} ERROR: {e}",
            flush=True,
        )

    # Wait 15 minutes before collecting the next sample
    time.sleep(900)
