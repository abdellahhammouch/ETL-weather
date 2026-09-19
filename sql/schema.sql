CREATE TABLE IF NOT EXISTS villes (
    id          SERIAL PRIMARY KEY,
    city        VARCHAR(150) NOT NULL UNIQUE,
    latitude    NUMERIC(9, 6) NOT NULL,
    longitude   NUMERIC(9, 6) NOT NULL,
    region      VARCHAR(150)
);



CREATE TABLE IF NOT EXISTS previsions (
    id                              SERIAL PRIMARY KEY,
    ville_id                        INTEGER NOT NULL REFERENCES villes(id),

    date_prevision                  DATE NOT NULL,

    temperature_max                 NUMERIC(5, 2),
    temperature_min                 NUMERIC(5, 2),
    precipitation_sum               NUMERIC(6, 2),
    precipitation_probability_max   NUMERIC(5, 2),
    wind_speed_max                  NUMERIC(6, 2),
    wind_gusts_max                  NUMERIC(6, 2),
    weather_code                    INTEGER,

    temperature_category            VARCHAR(20),
    precipitation_category          VARCHAR(20),
    wind_category                   VARCHAR(20),
    risk_score                      INTEGER,
    risk_level                      VARCHAR(20),

    retrieved_at                    TIMESTAMP NOT NULL,

    UNIQUE (ville_id, date_prevision, retrieved_at)
);
