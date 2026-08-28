# BirdNET PostgreSQL Database

PostgreSQL provides long-term structured storage for the BirdNET monitoring project.

It complements Grafana Loki:

- Loki: recent logs and operational monitoring
- PostgreSQL: permanent structured data for analysis, statistics, and future prediction/ML

## Database

Database name:

    birdnet

Application role:

    birdnet

The PostgreSQL password is stored locally and must never be committed to Git.

## Tables

### detections

Stores BirdNET detections including:

- timestamp
- station
- common species name
- scientific species name
- confidence
- latitude and longitude
- BirdNET cutoff
- BirdNET week
- sensitivity
- overlap
- source audio filename

Detections originate from BirdNET's native SQLite database at:

    ~/BirdNET-Pi/scripts/birds.db

`collector/import_detections.py` synchronizes these records into PostgreSQL. The `birdnet-db-sync.timer` runs the importer approximately once per minute. Duplicate imports are prevented by a unique index on the detection timestamp, scientific species name, and source filename.

### weather_observations

Stores observed weather conditions including:

- temperature
- humidity
- atmospheric pressure
- precipitation
- cloud cover
- wind speed and direction
- weather code
- day/night state
- sunrise and sunset

### weather_forecasts

Stores weather forecasts separately from observations.

Keeping forecasts allows future models to compare what was predicted at the time with what actually happened.

Additional forecast fields include:

- precipitation probability
- UV index

## Initialize Database

Create the PostgreSQL role and database:

    sudo -u postgres psql

Then:

    CREATE USER birdnet WITH PASSWORD 'YOUR_PASSWORD';
    CREATE DATABASE birdnet OWNER birdnet;
    \q

Apply the schema:

    psql -h localhost -U birdnet -d birdnet -f database/schema.sql

## Verify

List the tables:

    psql -h localhost -U birdnet -d birdnet -c "\dt"

Expected tables:

    detections
    weather_observations
    weather_forecasts

## Security

Do not commit:

- PostgreSQL passwords
- Grafana Cloud tokens
- database dumps containing sensitive credentials

Credentials should remain outside the Git repository.

## Current Ingestion

Operational:

- BirdNET detections: BirdNET SQLite -> PostgreSQL
- weather observations: Open-Meteo -> weather logger -> PostgreSQL

Planned:

- collect and store weather forecasts
- configure database backups
- connect PostgreSQL to Grafana
- build historical analysis and prediction models
