# BirdNET-Pi Monitoring

A reproducible observability and long-term data platform for a BirdNET-Pi station.

This project surrounds BirdNET-Pi with a small monitoring and data infrastructure built from:

- Grafana Alloy
- Grafana Cloud Loki
- PostgreSQL
- Open-Meteo
- Python
- systemd

BirdNET remains responsible for listening to the microphone and identifying birds. This repository does not replace BirdNET and does not contain the BirdNET application itself.

Instead, it answers a different set of questions:

- What is BirdNET detecting right now?
- Is the station healthy?
- What were the weather conditions when birds were active?
- How has bird activity changed over weeks, months, and seasons?
- Can historical bird and weather data eventually predict future activity?

The design deliberately separates **operational observability** from **long-term structured data**.

That distinction is the key to understanding the entire project.

---

## 1. The Big Picture

There are two parallel data paths.

### Operational path

BirdNET and weather events are sent to Grafana Cloud for recent monitoring and visualization.

    BirdNET journal ──► Grafana Alloy ──► Grafana Cloud Loki ──► Grafana

    Weather JSONL ────► Grafana Alloy ──► Grafana Cloud Loki ──► Grafana

This path answers questions such as:

> Is BirdNET running?

> What birds were detected recently?

> What weather data is arriving?

> Are logs still reaching Grafana Cloud?

### Historical data path

Structured bird detections and weather observations are stored permanently in PostgreSQL.

    BirdNET birds.db
          │
          ▼
    import_detections.py
          │
          ▼
      PostgreSQL
       detections


       Open-Meteo
          │
          ▼
       weather.py
          │
          ▼
      PostgreSQL
    weather_observations

This path answers questions such as:

> How many House Finches were detected last month?

> Does Black Phoebe activity increase after sunrise?

> Does wind speed reduce detection activity?

> Which weather conditions correlate with the greatest number of detections?

> Can tomorrow's weather be used to predict bird activity?

The long-term goal is therefore:

    BirdNET + Weather
           │
           ▼
       PostgreSQL
           │
           ▼
    Historical Analysis
           │
           ▼
    Prediction / ML

---

# 2. Why Both Loki and PostgreSQL?

At first glance it may seem redundant to store some information twice.

It is intentional.

## Grafana Cloud Loki

Loki is the **observability system**.

It stores logs and makes them easy to search and visualize in Grafana.

Examples:

- BirdNET journal messages
- parsed species labels
- confidence information
- weather JSON
- service activity

Loki is excellent for questions about what the system has been doing recently.

Think:

    "What did the system say?"

## PostgreSQL

PostgreSQL is the **historical dataset**.

It stores normalized records that can be queried with SQL and later consumed by data-analysis or machine-learning tools.

Think:

    "What do we know?"

PostgreSQL is intended to accumulate months and eventually years of:

- bird detections
- weather observations
- future weather forecasts

The database is therefore much more than another log destination.

It is the foundation of the future bird-activity model.

---

# 3. Data Sources

The system currently has three important sources of information.

## BirdNET journal

BirdNET's analysis service writes events into the systemd journal:

    birdnet_analysis.service

Grafana Alloy reads these messages directly from the journal.

For BirdNET detection messages, Alloy extracts:

- common species name
- Latin species name
- confidence
- confidence interval

These fields become Loki labels and can be used in Grafana queries.

This is the fast operational path.

---

## BirdNET SQLite database

BirdNET also maintains its own SQLite database:

    ~/BirdNET-Pi/scripts/birds.db

This database is the authoritative structured source for completed BirdNET detections.

It contains information such as:

- date
- time
- common species name
- scientific species name
- confidence
- latitude
- longitude
- cutoff
- week
- sensitivity
- overlap
- source recording filename

Rather than attempting to reconstruct permanent detection history from logs, this project imports the native BirdNET records into PostgreSQL.

That job belongs to:

    collector/import_detections.py

This is the durable historical path.

---

## Open-Meteo

Weather information comes from the Open-Meteo API.

The collector is:

    weather/weather.py

The station currently requests:

- temperature
- dew point
- relative humidity
- mean sea-level pressure
- precipitation
- cloud cover
- wind speed
- wind gusts
- wind direction
- weather code
- day/night state
- sunrise
- sunset

Temperature is requested in Fahrenheit and wind speed in mph.

The station timezone is explicitly configured as:

    America/Los_Angeles

The station location is currently configured directly in `weather.py`.

When deploying the repository to another location, review:

    LATITUDE
    LONGITUDE
    STATION_TIMEZONE_NAME

---

# 4. Bird Detection Synchronization

BirdNET's SQLite database and the PostgreSQL database have different jobs.

BirdNET owns:

    ~/BirdNET-Pi/scripts/birds.db

This project owns the PostgreSQL copy used for long-term analysis.

The synchronization path is:

    birds.db
       │
       ▼
    birdnet-db-sync.timer
       │
       ▼
    birdnet-db-sync.service
       │
       ▼
    import_detections.py
       │
       ▼
    PostgreSQL detections

The timer runs approximately once per minute.

---

## Incremental synchronization

The importer does not scan the entire BirdNET database every minute.

SQLite provides an internal `rowid` for each source record.

The importer remembers the last processed row using:

    ~/.local/state/birdnet-db-sync/last_rowid

For example:

    1200

On the next run it asks SQLite only for records where:

    rowid > 1200

This makes normal synchronization extremely small and inexpensive.

A typical run with no new detections looks like:

    Processed 0 detections, imported 0 new detections, last_rowid=1200

---

## Transaction safety

The synchronization state is advanced only after the PostgreSQL transaction succeeds.

Conceptually:

    read new SQLite rows
           │
           ▼
    insert into PostgreSQL
           │
           ▼
    PostgreSQL commit succeeds
           │
           ▼
    update last_rowid

If the PostgreSQL operation fails, the state file is not advanced.

The next synchronization can therefore retry those rows.

The state file itself is also replaced atomically rather than rewritten in place.

---

## BirdNET database rebuild protection

There is another important edge case.

If BirdNET is reinstalled or its SQLite database is recreated, SQLite row numbers may start again at a lower value.

Imagine the importer remembers:

    last_rowid = 1200

but a newly created BirdNET database contains:

    MAX(rowid) = 25

Without protection, the importer would wait forever for row 1201.

The importer therefore compares the current SQLite maximum with its stored state.

If:

    source MAX(rowid) < stored last_rowid

it assumes the source database has been reset and begins synchronization again from row 0.

PostgreSQL's detection uniqueness rule protects already-existing historical detections from being inserted again.

---

## Detection identity

PostgreSQL considers a detection unique using:

    station_id
    detected_at
    species_latin
    file_name

The corresponding unique index prevents accidental duplicate historical detections.

Each imported detection also stores:

    source_rowid

This provides traceability back to the original BirdNET SQLite record.

`source_rowid` itself is deliberately not globally unique because BirdNET may recreate its SQLite database and reuse row numbers.

---

# 5. Weather Collection

The weather service runs continuously:

    weather.service

Its application is deployed at:

    /home/birduser/weather/weather.py

The source-controlled copy lives at:

    weather/weather.py

The service waits:

    900 seconds

between collections, which is approximately 15 minutes.

---

## Weather request

The collector requests current conditions and daily sunrise/sunset information from Open-Meteo.

The HTTP client includes retries for temporary failures such as:

    HTTP 429
    HTTP 500
    HTTP 502
    HTTP 503
    HTTP 504

Connection and request timeouts prevent a failed API request from hanging the collector indefinitely.

The response is validated before it is accepted.

Required weather fields must be present before the observation is written.

This prevents an incomplete API response from silently becoming a malformed historical record.

---

## Observation time versus collection time

Two timestamps have different meanings.

Open-Meteo supplies:

    time

This is the weather observation timestamp.

The collector additionally creates:

    logged_at

This is the time the Raspberry Pi retrieved the observation.

PostgreSQL uses the Open-Meteo observation time as:

    weather_observations.observed_at

This distinction matters later when correlating weather with bird detections.

---

## Weather duplicate protection

Open-Meteo can return the same current observation more than once.

This happens naturally if the weather service is restarted before Open-Meteo advances to its next observation.

PostgreSQL therefore enforces uniqueness on:

    station_id
    observed_at

The insert uses:

    ON CONFLICT ... DO NOTHING

A restart during the same weather interval therefore does not create another historical observation.

---

## Weather JSON and Loki

Weather is also written as JSON Lines to:

    /var/log/weather/weather.log

Each line contains one weather observation.

Grafana Alloy tails this file and forwards the records to Grafana Cloud Loki.

To avoid generating duplicate Loki events after service restarts, JSON is normally written only when PostgreSQL identifies the observation as new.

If PostgreSQL itself is unavailable, the weather collector still attempts to write the JSON record.

This preserves the operational weather path even during a database problem.

A normal successful collection looks similar to:

    Weather collected (new=True, log_written=True, database=True)

A repeated Open-Meteo observation may look like:

    Weather collected (new=False, log_written=False, database=True)

---

# 6. PostgreSQL

PostgreSQL is the permanent structured datastore for this project.

Current database:

    birdnet

Current application role:

    birdnet

The schema is stored in:

    database/schema.sql

---

## Tables

### detections

Stores the historical BirdNET detection dataset.

Important fields include:

    detected_at
    station_id
    species
    species_latin
    confidence
    latitude
    longitude
    cutoff
    week
    sensitivity
    overlap
    file_name
    source_rowid

---

### weather_observations

Stores actual observed weather conditions.

Important fields include:

    observed_at
    station_id
    temperature_f
    dew_point_f
    relative_humidity_pct
    pressure_msl_hpa
    precipitation_in
    cloud_cover_pct
    wind_speed_mph
    wind_gusts_mph
    wind_direction_deg
    weather_code
    is_day
    sunrise
    sunset

These observations can eventually be joined with BirdNET detections by timestamp.

---

### weather_forecasts

The `weather_forecasts` table stores historical snapshots of Open-Meteo hourly forecasts.

Forecast collection is handled by:

    weather/forecast.py

and scheduled through:

    birdnet-forecast.timer
        |
        v
    birdnet-forecast.service
        |
        v
    weather/forecast.py
        |
        v
    PostgreSQL weather_forecasts

The collector currently runs once per hour and requests a 48-hour hourly forecast.

Each stored row contains two important timestamps:

    forecast_created_at
    forecast_for

`forecast_created_at` identifies when the forecast snapshot was collected.

`forecast_for` identifies the future hour being predicted.

This means the same future hour can intentionally appear in many forecast snapshots.

For example:

    22:00 snapshot -> forecast for tomorrow 08:00
    23:00 snapshot -> forecast for tomorrow 08:00
    00:00 snapshot -> forecast for tomorrow 08:00

Those rows are not duplicates. They represent how the forecast for the same future hour changed as time progressed.

The table stores fields including:

- forecast creation time
- forecast target time
- temperature
- dew point
- humidity
- precipitation probability
- precipitation
- cloud cover
- wind speed
- wind gusts
- wind direction
- pressure
- UV index
- weather code

This historical forecast archive will later make it possible to compare forecasts with actual observations and to build bird-activity predictions using only information that was genuinely available at prediction time.

---

# 7. Database Backups

PostgreSQL contains the long-term dataset, so it must be protected independently of Git.

Git stores:

- source code
- configuration
- systemd definitions
- schema

Git does **not** store the database contents.

A daily backup system therefore creates PostgreSQL custom-format dumps.

Backup script:

    backup/backup_postgres.sh

Runtime backup directory:

    ~/backups/postgresql

Example:

    birdnet_2026-08-28_21-58-34.dump

The backup uses PostgreSQL's custom archive format:

    pg_dump --format=custom

This format can be inspected and restored using:

    pg_restore

---

## Backup schedule

The systemd timer is:

    birdnet-db-backup.timer

The job runs daily.

A randomized delay of up to 15 minutes avoids requiring an exact midnight execution time.

The timer is persistent, so systemd can catch up after downtime.

The backup service itself is:

    birdnet-db-backup.service

It is a `Type=oneshot` service.

Therefore this is normal after a successful backup:

    inactive (dead)

The timer, not the service, should remain active.

---

## Retention

The backup script currently retains approximately:

    14 days

of local PostgreSQL dumps.

Older matching dump files are automatically removed.

---

## What local backups protect against

These dumps provide protection against problems such as:

- accidental database changes
- damaged tables
- application mistakes
- needing to restore an earlier database state

They do **not** provide full disaster protection while they remain on the same Raspberry Pi.

If the SD card fails completely, both PostgreSQL and the local dumps could be lost.

A future improvement should therefore replicate these backups to another system such as:

- a NUC
- NAS
- another Linux server
- remote backup storage

---

# 8. Grafana Alloy

Grafana Alloy provides the operational log pipeline.

It currently ingests two sources.

## BirdNET journal

Alloy reads the systemd journal and identifies messages from:

    birdnet_analysis.service

For detection messages it extracts:

    species
    species_latin
    confidence

It also generates confidence interval labels.

The resulting logs are forwarded to Grafana Cloud Loki.

---

## Weather JSONL

Alloy watches:

    /var/log/weather/weather.log

with the Loki label:

    job = "weather"

These records are forwarded to the same Grafana Cloud Loki destination.

---

## Alloy configuration

Repository copies:

    alloy/config.alloy
    alloy/default-alloy

Runtime locations:

    /etc/alloy/config.alloy
    /etc/default/alloy

Alloy runtime state:

    /var/lib/alloy/data

The runtime state contains information such as file-tail positions.

It should normally be recreated after a fresh installation rather than restored from Git.

---

# 9. Grafana

The exported dashboard is stored at:

    grafana/Bird Home - Burbank.json

It visualizes the operational Loki data.

The dashboard currently depends on the Grafana Cloud Loki datasource used by the station.

If a rebuilt Grafana environment receives a different datasource UID or name, some panels may need to be pointed to the new datasource.

The dashboard export does not intentionally contain Grafana Cloud authentication credentials.

Long-term PostgreSQL visualization is a future phase.

---

# 10. Repository Structure

    birdnetPi-monitoring/
    │
    ├── alloy/
    │   ├── config.alloy
    │   └── default-alloy
    │
    ├── backup/
    │   └── backup_postgres.sh
    │
    ├── collector/
    │   └── import_detections.py
    │
    ├── database/
    │   ├── schema.sql
    │   └── README.md
    │
    ├── docs/
    │   ├── alloy-setup.md
    │   ├── weather-setup.md
    │   ├── alloy-version.txt
    │   └── package-version.txt
    │
    ├── grafana/
    │   └── Bird Home - Burbank.json
    │
    ├── systemd/
    │   ├── alloy.service.txt
    │   ├── birdnet-db-backup.service
    │   ├── birdnet-db-backup.timer
    │   ├── birdnet-db-sync.service
    │   ├── birdnet-forecast.service
    │   ├── birdnet-forecast.timer
    │   ├── birdnet-db-sync.timer
    │   └── weather.service
    │
    ├── weather/
    │   ├── forecast.py
    │   ├── weather.py
    │   └── requirements.txt
    │
    ├── .gitignore
    └── README.md

The repository contains the reproducible infrastructure around BirdNET.

It intentionally does not contain BirdNET itself or live runtime data.

---

# 11. Fresh Installation / Disaster Recovery

The recommended recovery order is:

1. Install and verify BirdNET-Pi
2. Clone this repository
3. Install PostgreSQL
4. Create the database and schema
5. Configure PostgreSQL authentication
6. Restore the weather collector
7. Restore BirdNET-to-PostgreSQL synchronization
8. Restore automated database backups
9. Restore weather forecast collection
10. Install Grafana Alloy
11. Restore Alloy configuration and credentials
12. Import the Grafana dashboard
13. Verify every data path

BirdNET should be working before this monitoring layer is restored.

---

## Step 1 — Install BirdNET-Pi

Install BirdNET from the appropriate upstream project.

Before continuing, verify that BirdNET is detecting normally and that its database exists:

    ls -lh ~/BirdNET-Pi/scripts/birds.db

Also verify the analysis service:

    systemctl status birdnet_analysis.service --no-pager

This repository assumes that BirdNET itself is already functional.

---

## Step 2 — Clone this repository

Using SSH:

    cd ~
    git clone git@github.com:mbuer/birdnetPi-monitoring.git
    cd birdnetPi-monitoring

HTTPS may also be used when GitHub SSH authentication has not been configured.

---

## Step 3 — Install PostgreSQL

Install PostgreSQL and the Python PostgreSQL driver:

    sudo apt update
    sudo apt install -y postgresql python3-psycopg

Verify PostgreSQL:

    pg_isready

---

## Step 4 — Create the database

Open PostgreSQL as the administrative user:

    sudo -u postgres psql

Create the application role:

    CREATE USER birdnet WITH PASSWORD 'YOUR_PASSWORD';

Create the database:

    CREATE DATABASE birdnet OWNER birdnet;

Exit:

    \q

Apply the repository schema:

    psql -h localhost -U birdnet -d birdnet -f database/schema.sql

Expected tables:

    detections
    weather_observations
    weather_forecasts

---

## Step 5 — Configure PostgreSQL authentication

The Python applications do not contain the PostgreSQL password.

Create:

    ~/.pgpass

with:

    localhost:5432:birdnet:birdnet:YOUR_PASSWORD

Protect it:

    chmod 600 ~/.pgpass

Test passwordless application access:

    psql -h localhost -U birdnet -d birdnet -c "SELECT 1;"

The actual password must never be committed to this repository.

---

## Step 6 — Restore the weather collector

Install dependencies:

    sudo apt install -y python3-requests python3-psycopg

Create the runtime application directory:

    mkdir -p ~/weather

Deploy the repository copy:

    cp weather/weather.py ~/weather/weather.py

Create the weather log directory:

    sudo mkdir -p /var/log/weather
    sudo chown birduser:birduser /var/log/weather

Install the service:

    sudo cp systemd/weather.service /etc/systemd/system/weather.service
    sudo systemctl daemon-reload
    sudo systemctl enable --now weather.service

Verify:

    systemctl status weather.service --no-pager

Inspect recent activity:

    journalctl -u weather.service -n 20 --no-pager

Inspect the latest JSON observation:

    tail -1 /var/log/weather/weather.log

Remember that the repository copy and deployed runtime copy are separate files.

After changing:

    weather/weather.py

redeploy it with:

    cp weather/weather.py ~/weather/weather.py
    sudo systemctl restart weather.service

---

## Step 7 — Restore BirdNET detection synchronization

Install the synchronization service and timer:

    sudo cp systemd/birdnet-db-sync.service /etc/systemd/system/
    sudo cp systemd/birdnet-db-sync.timer /etc/systemd/system/

Reload systemd:

    sudo systemctl daemon-reload

Enable the timer:

    sudo systemctl enable --now birdnet-db-sync.timer

On a fresh installation, the importer has no state file and starts at rowid 0.

It therefore scans the existing BirdNET SQLite history and imports detections into PostgreSQL.

The PostgreSQL uniqueness rule prevents duplicate historical records.

After a successful run, the importer creates:

    ~/.local/state/birdnet-db-sync/last_rowid

Verify synchronization:

    journalctl -u birdnet-db-sync.service -n 20 --no-pager

Verify the timer:

    systemctl status birdnet-db-sync.timer --no-pager

`birdnet-db-sync.service` is a oneshot service and normally returns to:

    inactive (dead)

after each successful synchronization.

That is expected.

---

## Step 8 — Restore PostgreSQL backups

Install the backup service and timer:

    sudo cp systemd/birdnet-db-backup.service /etc/systemd/system/
    sudo cp systemd/birdnet-db-backup.timer /etc/systemd/system/

Reload systemd:

    sudo systemctl daemon-reload

Enable the timer:

    sudo systemctl enable --now birdnet-db-backup.timer

Test a backup manually:

    sudo systemctl start birdnet-db-backup.service

Check the result:

    ls -lh ~/backups/postgresql

Verify a dump archive:

    pg_restore --list ~/backups/postgresql/birdnet_*.dump | head

The backup service being inactive after completion is normal.

The backup timer should remain active.

---

## Step 9 — Restore weather forecast collection

Install the forecast service and timer:

    sudo cp systemd/birdnet-forecast.service /etc/systemd/system/
    sudo cp systemd/birdnet-forecast.timer /etc/systemd/system/

Reload systemd:

    sudo systemctl daemon-reload

Enable the hourly timer:

    sudo systemctl enable --now birdnet-forecast.timer

The collector requests a 48-hour hourly forecast from Open-Meteo and stores one historical forecast snapshot per hour.

Test the collector manually:

    python3 weather/forecast.py

Verify the timer:

    systemctl status birdnet-forecast.timer --no-pager

Inspect recent forecast runs:

    journalctl -u birdnet-forecast.service -n 20 --no-pager

Verify the database:

    psql -h localhost -U birdnet -d birdnet -c "
    SELECT
        COUNT(*) AS rows,
        COUNT(DISTINCT forecast_created_at) AS snapshots,
        MAX(forecast_created_at) AS latest_snapshot,
        MAX(forecast_for) AS forecast_horizon
    FROM weather_forecasts;
    "

`birdnet-forecast.service` is a oneshot service and normally returns to `inactive (dead)` after a successful run.

That is expected.

---

## Step 10 — Install Grafana Alloy

Install Grafana Alloy using Grafana's official Debian/Raspberry Pi installation procedure.

The package-managed Alloy service runs approximately as:

    /usr/bin/alloy run \
      --storage.path=/var/lib/alloy/data \
      /etc/alloy/config.alloy

The known package service configuration is documented in:

    systemd/alloy.service.txt

Do not blindly replace Grafana's package-provided systemd service with this file.

It is retained primarily as documentation of the known-working installation.

---

## Step 11 — Restore Alloy configuration

Create the configuration directory if necessary:

    sudo mkdir -p /etc/alloy

Copy the repository configuration:

    sudo cp alloy/config.alloy /etc/alloy/config.alloy
    sudo cp alloy/default-alloy /etc/default/alloy

The repository deliberately contains placeholders:

    GRAFANA_CLOUD_USERNAME
    GRAFANA_CLOUD_PASSWORD

Edit the runtime configuration:

    sudo nano /etc/alloy/config.alloy

Replace the placeholders with the current Grafana Cloud Loki credentials.

Restart Alloy:

    sudo systemctl enable alloy
    sudo systemctl restart alloy

Verify:

    systemctl status alloy --no-pager

Inspect recent logs:

    journalctl -u alloy -n 50 --no-pager

---

## Step 12 — Restore Grafana

Import:

    grafana/Bird Home - Burbank.json

into Grafana.

Verify that its panels reference the correct Grafana Cloud Loki datasource.

---

# 12. System Verification

After installation or major changes, verify the stack from the source outward.

## BirdNET

    systemctl status birdnet_analysis.service --no-pager

    journalctl -u birdnet_analysis.service -n 20 --no-pager

---

## BirdNET SQLite source

    sqlite3 ~/BirdNET-Pi/scripts/birds.db \
      'SELECT MAX(rowid), COUNT(*) FROM detections;'

---

## Detection synchronization

    systemctl status birdnet-db-sync.timer --no-pager

    journalctl -u birdnet-db-sync.service -n 20 --no-pager

Inspect synchronization state:

    cat ~/.local/state/birdnet-db-sync/last_rowid

---

## PostgreSQL

    pg_isready

Detection summary:

    psql -h localhost -U birdnet -d birdnet -c "
    SELECT
        COUNT(*) AS detections,
        MAX(detected_at) AS latest_detection,
        MAX(source_rowid) AS latest_source_rowid
    FROM detections;
    "

Weather summary:

    psql -h localhost -U birdnet -d birdnet -c "
    SELECT
        COUNT(*) AS observations,
        MAX(observed_at) AS latest_observation
    FROM weather_observations;
    "

---

## Weather

    systemctl status weather.service --no-pager

    journalctl -u weather.service -n 20 --no-pager

    tail -5 /var/log/weather/weather.log

---

## Database backups

    systemctl status birdnet-db-backup.timer --no-pager

    journalctl -u birdnet-db-backup.service -n 20 --no-pager

    ls -lh ~/backups/postgresql

---

## Weather forecasts

    systemctl status birdnet-forecast.timer --no-pager

    journalctl -u birdnet-forecast.service -n 20 --no-pager

    psql -h localhost -U birdnet -d birdnet -c "
    SELECT
        COUNT(*) AS rows,
        COUNT(DISTINCT forecast_created_at) AS snapshots,
        MAX(forecast_created_at) AS latest_snapshot,
        MAX(forecast_for) AS forecast_horizon
    FROM weather_forecasts;
    "

---

## Alloy

    systemctl status alloy.service --no-pager

    journalctl -u alloy.service -n 50 --no-pager

---

## Grafana

Finally verify that:

- new BirdNET detections appear
- species labels populate correctly
- confidence information is available
- weather observations continue updating
- dashboard panels return current data

This verifies the complete operational path:

    source
      │
      ▼
    local collector
      │
      ▼
    Alloy
      │
      ▼
    Loki
      │
      ▼
    Grafana

and the historical path:

    source
      │
      ▼
    collector/importer
      │
      ▼
    PostgreSQL

---

# 13. Runtime Data

The Git repository contains code and configuration.

It does not contain live telemetry.

Important runtime data includes:

| Data | Location | Purpose |
|---|---|---|
| BirdNET SQLite | `~/BirdNET-Pi/scripts/birds.db` | Native BirdNET detection source |
| Import state | `~/.local/state/birdnet-db-sync/last_rowid` | Last processed SQLite row |
| Weather JSONL | `/var/log/weather/weather.log` | Operational weather feed for Alloy |
| PostgreSQL | `birdnet` database | Permanent structured history |
| PostgreSQL dumps | `~/backups/postgresql` | Local database recovery |
| Alloy state | `/var/lib/alloy/data` | Alloy runtime/file-tail state |
| Alloy config | `/etc/alloy/config.alloy` | Live Alloy configuration |

These files have different recovery importance.

The most valuable long-term data is PostgreSQL.

The BirdNET SQLite database is also valuable because it remains the original BirdNET detection source.

Alloy runtime state can normally be recreated.

---

# 14. Security

Secrets are deliberately excluded from Git.

The repository Alloy configuration contains placeholders:

    GRAFANA_CLOUD_USERNAME
    GRAFANA_CLOUD_PASSWORD

Real Grafana Cloud credentials belong only in the live configuration:

    /etc/alloy/config.alloy

PostgreSQL credentials are supplied through:

    ~/.pgpass

The file should have permissions:

    600

Before pushing changes, the repository can be scanned with:

    grep -RniE \
      'password|token|secret|api[_-]?key|authorization|username' \
      --exclude-dir=.git .

Expected matches should be reviewed and should contain only documentation or placeholders.

Never commit:

- Grafana Cloud tokens
- PostgreSQL passwords
- API credentials
- private SSH keys
- other secrets

---

# 15. Known Runtime Paths

| Component | Path |
|---|---|
| BirdNET | `/home/birduser/BirdNET-Pi` |
| BirdNET SQLite | `/home/birduser/BirdNET-Pi/scripts/birds.db` |
| Monitoring repository | `/home/birduser/birdnetPi-monitoring` |
| Detection importer | `/home/birduser/birdnetPi-monitoring/collector/import_detections.py` |
| Import state | `/home/birduser/.local/state/birdnet-db-sync/last_rowid` |
| Weather application | `/home/birduser/weather/weather.py` |
| Weather log | `/var/log/weather/weather.log` |
| PostgreSQL backups | `/home/birduser/backups/postgresql` |
| Alloy configuration | `/etc/alloy/config.alloy` |
| Alloy defaults | `/etc/default/alloy` |
| Alloy runtime state | `/var/lib/alloy/data` |

---

# 16. Current System Boundaries

Understanding what the project does **not** currently do is just as important as understanding what it does.

The current system does not yet:

- use PostgreSQL as a Grafana datasource
- generate bird-activity predictions
- train machine-learning models
- replicate database backups off the Raspberry Pi
- replace or modify BirdNET's detection engine

These are future layers built on top of the current data foundation.

---

# 17. Where This Is Going

The current project establishes the data pipeline first.

That is deliberate.

A useful prediction model needs historical examples of:

    bird activity + time + weather

The database is now accumulating exactly that information.

Future analysis can derive features such as:

- hour of day
- day of year
- season
- minutes since sunrise
- minutes until sunset
- recent detection activity
- temperature
- dew point
- humidity
- wind
- wind gusts
- precipitation
- cloud cover
- pressure
- weather trends

These features do not need to be permanently stored in the raw observation tables.

They can be calculated from the historical dataset when models are trained.

---

## First prediction target

A useful initial question might be:

> Given the current time, recent bird activity, and weather conditions, how likely is a bird detection during the next hour?

Later models could become species-specific:

> What is the probability of detecting a Black Phoebe during the next hour?

The first models should remain simple and interpretable.

Potential starting points include:

- logistic regression
- simple statistical baselines
- random forests
- gradient boosting

The current hand-built bird-activity score can remain as a baseline.

A future machine-learning model should prove that it predicts activity better than that simple heuristic before replacing it.

---

## Longer-term vision

With enough historical data, the project can evolve from:

    "What birds did I hear?"

to:

    "When do birds usually appear?"

and eventually:

    "What am I likely to hear next, when, and under what conditions?"

That is why PostgreSQL was introduced early.

The database is not merely another monitoring component.

It is the historical memory of the station.

---

# 18. Design Philosophy

A few principles guide this project.

### Keep BirdNET independent

BirdNET should remain replaceable and upgradeable without entangling it with the monitoring repository.

### Preserve the native source

BirdNET's SQLite database remains the source for detection ingestion.

### Logs are not the historical database

Loki provides excellent operational observability.

PostgreSQL provides durable structured history.

Each tool has a clear job.

### Prefer simple components

The workload is small enough that PostgreSQL, Python, systemd, Alloy, and a few small scripts are sufficient.

There is no need to introduce a larger orchestration platform simply because one exists.

### Make failures recoverable

Important state is either reproducible from Git or backed up separately.

### Build the dataset before the model

Prediction comes after reliable collection.

A sophisticated model built on unreliable data would be less useful than a simple model built on a trustworthy dataset.

---

# 19. Project Purpose

This repository serves four purposes:

1. **Reproducibility**
   Preserve the custom BirdNET monitoring infrastructure as code.

2. **Disaster recovery**
   Make it possible to rebuild the monitoring stack without reconstructing it from memory.

3. **Long-term data collection**
   Build a durable historical dataset combining BirdNET detections with environmental conditions.

4. **Future analysis and prediction**
   Provide the foundation for understanding and eventually predicting bird activity at this station.

BirdNET itself is installed and maintained separately.

This repository begins where BirdNET ends: observing the system, preserving its data, and turning that data into something that can be understood over time.
