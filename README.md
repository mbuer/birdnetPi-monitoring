# BirdNET-Pi Monitoring

Monitoring, observability, and long-term data collection for a BirdNET-Pi station using Grafana Alloy, Grafana Cloud Loki, PostgreSQL, and a custom weather logger.

The goal of this repository is to make the custom monitoring environment reproducible. After rebuilding or replacing the BirdNET-Pi, the monitoring pipeline can be restored from this repository instead of being recreated manually.

## Architecture

Bird detections and weather data are collected through two complementary storage paths:

- Grafana Cloud Loki for operational monitoring and recent log analysis
- PostgreSQL for permanent structured history, analysis, and future prediction/ML

### BirdNET detections

BirdNET writes analysis events into the systemd journal:

    birdnet_analysis.service
              |
              v
        Grafana Alloy
              |
        parse / label
              |
              v
      Grafana Cloud Loki
              |
              v
           Grafana

Alloy extracts information from BirdNET detection messages including:

- common species name
- Latin species name
- confidence
- confidence interval

### Weather

A small Python service retrieves weather information from Open-Meteo every 15 minutes:

    Open-Meteo API
          |
          v
      weather.py
        /       \
       v         v
 weather.log   PostgreSQL
       |
       v
 Grafana Alloy
       |
       v
 Grafana Cloud Loki
       |
       v
    Grafana

Weather records are written as one JSON object per line for Alloy/Loki and are also stored in PostgreSQL for permanent historical analysis.

Collected fields include:

- temperature
- relative humidity
- atmospheric pressure
- precipitation
- cloud cover
- wind speed
- wind direction
- weather code
- day/night state
- sunrise
- sunset

The current weather configuration uses Fahrenheit and mph.

## Repository Structure

    birdnetPi-monitoring/
    ├── alloy/
    │   ├── config.alloy
    │   └── default-alloy
    │
    ├── weather/
    │   ├── weather.py
    │   └── requirements.txt
    │
    ├── database/
    │   ├── schema.sql
    │   └── README.md
    │
    ├── systemd/
    │   ├── alloy.service.txt
    │   └── weather.service
    │
    ├── grafana/
    │   └── Bird Home - Burbank.json
    │
    ├── docs/
    │   ├── alloy-setup.md
    │   ├── weather-setup.md
    │   ├── alloy-version.txt
    │   └── package-version.txt
    │
    └── README.md

## Important

Secrets are deliberately NOT stored in this repository.

The Alloy configuration contains placeholders:

    GRAFANA_CLOUD_USERNAME
    GRAFANA_CLOUD_PASSWORD

Replace these with the appropriate Grafana Cloud Loki credentials during installation.

Never commit real Grafana credentials, API tokens, passwords, or other secrets.

---

# Fresh Installation / Recovery

The recommended restore order is:

1. Install and verify BirdNET-Pi
2. Clone this repository
3. Restore the weather logger
4. Install and initialize PostgreSQL
5. Install and configure Grafana Alloy
6. Add Grafana Cloud credentials
7. Start the services
8. Import the Grafana dashboard
9. Verify end-to-end ingestion

Keeping BirdNET itself separate from this repository makes it easier to update or reinstall BirdNET without mixing application code with the monitoring configuration.

## 1. Clone the Repository

    cd ~
    git clone git@github.com:mbuer/birdnetPi-monitoring.git
    cd birdnetPi-monitoring

HTTPS can also be used if SSH access has not yet been configured.

## 2. Restore the Weather Logger

Install Python requirements:

    sudo apt update
    sudo apt install -y python3-pip python3-venv

Create the runtime directory:

    mkdir -p ~/weather
    cp weather/weather.py ~/weather/weather.py

Create a dedicated Python virtual environment:

    python3 -m venv ~/weather/.venv
    ~/weather/.venv/bin/pip install -r weather/requirements.txt

Create the weather log directory:

    sudo mkdir -p /var/log/weather
    sudo chown birduser:birduser /var/log/weather

Install the systemd service:

    sudo cp systemd/weather.service /etc/systemd/system/weather.service
    sudo systemctl daemon-reload
    sudo systemctl enable --now weather.service

NOTE:

The saved service currently reflects the working installation. Check that its ExecStart points to the Python interpreter you intend to use.

If using the virtual environment above, the preferred command is:

    ExecStart=/home/birduser/weather/.venv/bin/python -u /home/birduser/weather/weather.py

Verify the service:

    systemctl status weather.service --no-pager

Watch its journal:

    journalctl -u weather.service -f

Check generated weather data:

    tail -f /var/log/weather/weather.log

A new weather record should normally appear approximately every 15 minutes.

For additional information see:

    docs/weather-setup.md

## 3. Install Grafana Alloy

Install Grafana Alloy using Grafana's official Debian/Raspberry Pi installation instructions.

The installed Alloy service runs approximately as:

    /usr/bin/alloy run \
      --storage.path=/var/lib/alloy/data \
      /etc/alloy/config.alloy

The package-managed systemd service is documented in:

    systemd/alloy.service.txt

Do not blindly replace the package-provided Alloy systemd service with this file. It is primarily preserved as documentation of the known-working installation.

## 4. Restore Alloy Configuration

Copy the saved configuration:

    sudo mkdir -p /etc/alloy
    sudo cp alloy/config.alloy /etc/alloy/config.alloy
    sudo cp alloy/default-alloy /etc/default/alloy

Edit:

    sudo nano /etc/alloy/config.alloy

Replace:

    GRAFANA_CLOUD_USERNAME
    GRAFANA_CLOUD_PASSWORD

with the current Grafana Cloud Loki credentials.

Then restart Alloy:

    sudo systemctl enable alloy
    sudo systemctl restart alloy

Verify:

    systemctl status alloy --no-pager

Inspect recent logs:

    journalctl -u alloy -n 50 --no-pager

For additional information see:

    docs/alloy-setup.md

---

# Alloy Pipeline

The Alloy configuration currently contains two ingestion paths.

## BirdNET journal

Alloy reads the systemd journal and labels entries with their systemd unit.

For:

    birdnet_analysis.service

the processing pipeline extracts BirdNET detection information from the log message.

The parsed fields include:

    species
    species_latin
    confidence

The configuration also generates confidence interval labels.

These logs are then forwarded to Grafana Cloud Loki.

## Weather log

Alloy watches:

    /var/log/weather/weather.log

with:

    job = "weather"

The weather log is then forwarded to the same Grafana Cloud Loki destination.

---

# Weather Logger

The weather logger lives at:

    /home/birduser/weather/weather.py

It queries the Open-Meteo forecast API and writes to:

    /var/log/weather/weather.log

The service runs continuously and waits 900 seconds between requests.

Each successful collection is written both to the JSONL weather log and to the PostgreSQL `weather_observations` table.

Example record:

    {
      "temperature_2m": 82.8,
      "relative_humidity_2m": 63,
      "pressure_msl": 1011.0,
      "precipitation": 0.0,
      "cloud_cover": 0,
      "wind_speed_10m": 4.8,
      "wind_direction_10m": 143,
      "weather_code": 0,
      "is_day": 0
    }

The actual log also contains timestamps and sunrise/sunset information.

The weather location is currently configured directly inside `weather.py`. Review the latitude and longitude before deploying this repository to another station.

---

# Grafana Dashboard

The exported Grafana dashboard is stored in:

    grafana/Bird Home - Burbank.json

Import it into Grafana using the dashboard import functionality.

The dashboard expects the Grafana Cloud Loki datasource used by the original installation.

If the datasource name or UID changes after rebuilding the Grafana environment, some panels may need to be pointed at the new Loki datasource.

The dashboard JSON does not intentionally contain Grafana Cloud authentication credentials.

---

# Verification

After a rebuild, verify each layer independently.

## Weather process

    systemctl status weather.service --no-pager

## Weather output

    tail -5 /var/log/weather/weather.log

## Alloy

    systemctl status alloy --no-pager

## Alloy logs

    journalctl -u alloy -n 50 --no-pager

Look for successful startup and file tailing of:

    /var/log/weather/weather.log

## BirdNET

Confirm that BirdNET analysis events exist:

    journalctl -u birdnet_analysis.service -n 20 --no-pager

## End-to-end

Finally verify in Grafana that:

- new BirdNET detections appear
- weather data continues updating
- species labels populate correctly
- confidence information is available
- dashboard panels return data

---

# Runtime Data

The repository stores configuration and code, not runtime telemetry.

The following are intentionally not stored in Git:

    /var/log/weather/weather.log
    /var/lib/alloy/data

`/var/lib/alloy/data` contains Alloy runtime state, including positions used when tailing sources.

Normally this state should be recreated on a fresh installation rather than treated as configuration.

Historical weather logs can be backed up separately if preserving the local history is important.

Grafana Cloud Loki remains the primary remote observability store.

PostgreSQL provides the permanent structured dataset used for historical analysis and future prediction/ML. Database contents are runtime data and are not stored in Git.

---

# Security

Before every push, a simple repository scan can be performed:

    grep -RniE 'password|token|secret|api[_-]?key|authorization|username' \
      --exclude-dir=.git .

Expected matches include only placeholders such as:

    GRAFANA_CLOUD_USERNAME
    GRAFANA_CLOUD_PASSWORD

Never commit the real values.

---

# Known Runtime Paths

BirdNET repository:

    /home/birduser/BirdNET-Pi

Weather application:

    /home/birduser/weather

Weather log:

    /var/log/weather/weather.log

Alloy configuration:

    /etc/alloy/config.alloy

Alloy defaults:

    /etc/default/alloy

Alloy runtime state:

    /var/lib/alloy/data

PostgreSQL schema:

    database/schema.sql

Database setup and recovery documentation:

    database/README.md

---

# Purpose

This repository is intended to serve as both:

1. a backup of the custom BirdNET-Pi monitoring configuration
2. documentation for rebuilding the observability stack from scratch
3. definition of the long-term BirdNET and weather dataset used for historical analysis and future prediction/ML

The BirdNET application itself is not backed up here. It should be installed from its appropriate upstream project first, after which this repository restores the custom monitoring layer.
