#!/usr/bin/env python3

import sqlite3
from datetime import datetime
from pathlib import Path

import psycopg

SQLITE_DB = Path.home() / "BirdNET-Pi" / "scripts" / "birds.db"
DB_DSN = "host=localhost dbname=birdnet user=birdnet"

SELECT_SQL = """
SELECT
    Date,
    Time,
    Sci_Name,
    Com_Name,
    Confidence,
    Lat,
    Lon,
    Cutoff,
    Week,
    Sens,
    Overlap,
    File_Name
FROM detections
ORDER BY Date, Time
"""

INSERT_SQL = """
INSERT INTO detections (
    detected_at,
    station_id,
    species,
    species_latin,
    confidence,
    latitude,
    longitude,
    cutoff,
    week,
    sensitivity,
    overlap,
    file_name
)
VALUES (
    %s, 'birdnet', %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s
)
ON CONFLICT (detected_at, species_latin, file_name)
DO NOTHING
"""


def main():
    sqlite_conn = sqlite3.connect(f"file:{SQLITE_DB}?mode=ro", uri=True)

    inserted = 0

    with psycopg.connect(DB_DSN) as pg_conn:
        with pg_conn.cursor() as cur:
            for row in sqlite_conn.execute(SELECT_SQL):
                (
                    date,
                    time,
                    sci_name,
                    com_name,
                    confidence,
                    lat,
                    lon,
                    cutoff,
                    week,
                    sens,
                    overlap,
                    file_name,
                ) = row

                detected_at = datetime.fromisoformat(f"{date}T{time}")

                cur.execute(
                    INSERT_SQL,
                    (
                        detected_at,
                        com_name,
                        sci_name,
                        confidence,
                        lat,
                        lon,
                        cutoff,
                        week,
                        sens,
                        overlap,
                        file_name,
                    ),
                )

                inserted += cur.rowcount

    sqlite_conn.close()

    print(f"Imported {inserted} new detections")


if __name__ == "__main__":
    main()
