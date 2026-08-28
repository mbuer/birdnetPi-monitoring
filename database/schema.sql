-- BirdNET Monitoring Database Schema
-- Long-term storage for bird detections, weather observations,
-- and weather forecasts.

CREATE TABLE detections (
    id BIGSERIAL PRIMARY KEY,
    detected_at TIMESTAMPTZ NOT NULL,
    station_id TEXT NOT NULL DEFAULT 'birdnet',
    species TEXT NOT NULL,
    species_latin TEXT,
    confidence DOUBLE PRECISION
);

CREATE INDEX idx_detections_detected_at
    ON detections (detected_at);

CREATE INDEX idx_detections_species
    ON detections (species);


CREATE TABLE weather_observations (
    id BIGSERIAL PRIMARY KEY,
    observed_at TIMESTAMPTZ NOT NULL,
    station_id TEXT NOT NULL DEFAULT 'birdnet',

    temperature_f DOUBLE PRECISION,
    relative_humidity_pct DOUBLE PRECISION,
    pressure_msl_hpa DOUBLE PRECISION,
    precipitation_in DOUBLE PRECISION,
    cloud_cover_pct DOUBLE PRECISION,
    wind_speed_mph DOUBLE PRECISION,
    wind_direction_deg DOUBLE PRECISION,
    weather_code INTEGER,
    is_day BOOLEAN,

    sunrise TIMESTAMPTZ,
    sunset TIMESTAMPTZ
);

CREATE INDEX idx_weather_observations_observed_at
    ON weather_observations (observed_at);


CREATE TABLE weather_forecasts (
    id BIGSERIAL PRIMARY KEY,
    forecast_created_at TIMESTAMPTZ NOT NULL,
    forecast_for TIMESTAMPTZ NOT NULL,
    station_id TEXT NOT NULL DEFAULT 'birdnet',

    temperature_f DOUBLE PRECISION,
    relative_humidity_pct DOUBLE PRECISION,
    precipitation_probability_pct DOUBLE PRECISION,
    precipitation_in DOUBLE PRECISION,
    cloud_cover_pct DOUBLE PRECISION,
    wind_speed_mph DOUBLE PRECISION,
    wind_direction_deg DOUBLE PRECISION,
    pressure_msl_hpa DOUBLE PRECISION,
    uv_index DOUBLE PRECISION,
    weather_code INTEGER
);

CREATE INDEX idx_weather_forecasts_for
    ON weather_forecasts (forecast_for);

CREATE INDEX idx_weather_forecasts_created
    ON weather_forecasts (forecast_created_at);
