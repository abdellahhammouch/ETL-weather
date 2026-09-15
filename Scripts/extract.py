import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


CITIES_URL = "https://simplemaps.com/static/data/country-cities/ma/ma.csv"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

FORECAST_DAYS = 7
BATCH_SIZE = 100
REQUEST_TIMEOUT = 15       
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

DAILY_VARIABLES = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "precipitation_probability_max",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "weather_code",
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRONZE_DIR = PROJECT_ROOT / "bronze"
BRONZE_CITIES_DIR = BRONZE_DIR / "Villes"
BRONZE_WEATHER_DIR = BRONZE_DIR / "Meteo"
LOGS_DIR = PROJECT_ROOT / "logs"

for d in (BRONZE_CITIES_DIR, BRONZE_WEATHER_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "extract.log"),
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger("extract")


def run_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")



def extract_cities(run_ts: str) -> pd.DataFrame:

    logger.info("Extraction des villes depuis SimpleMaps...")

    try:
        response = requests.get(CITIES_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error("Timeout lors de la récupération du CSV des villes.")
        raise
    except requests.exceptions.HTTPError as e:
        logger.error(f"Erreur HTTP lors de la récupération des villes : {e}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur réseau lors de la récupération des villes : {e}")
        raise

    raw_path = BRONZE_CITIES_DIR / f"villes_{run_ts}.csv"
    raw_path.write_bytes(response.content)
    logger.info(f"Villes sauvegardées en Bronze : {raw_path}")

    cities = pd.read_csv(raw_path)

    if cities.empty:
        raise ValueError("Le fichier des villes est vide.")
    cities = validate_cities(cities)

    logger.info(f"Nombre de villes récupérées : {len(cities)}")
    return cities



def _call_weather_api(lat_batch: list, lon_batch: list) -> list | None:

    params = {
        "latitude": ",".join(map(str, lat_batch)),
        "longitude": ",".join(map(str, lon_batch)),
        "daily": ",".join(DAILY_VARIABLES),
        "forecast_days": FORECAST_DAYS,
        "timezone": "auto",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(WEATHER_URL, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict):
                data = [data]

            if not isinstance(data, list) or len(data) != len(lat_batch):
                logger.warning(
                    f"Réponse météo incohérente (attendu {len(lat_batch)}, "
                    f"reçu {len(data) if isinstance(data, list) else 'objet unique'}). "
                    f"Tentative {attempt}/{MAX_RETRIES}."
                )
                continue

            return data

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout API météo (tentative {attempt}/{MAX_RETRIES}).")
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            logger.warning(f"Erreur HTTP {status} sur l'API météo (tentative {attempt}/{MAX_RETRIES}).")
            if status == 429:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)  # backoff plus long si rate-limit
        except requests.exceptions.RequestException as e:
            logger.warning(f"Erreur réseau sur l'API météo : {e} (tentative {attempt}/{MAX_RETRIES}).")
        except ValueError:
            logger.warning(f"Réponse JSON invalide (tentative {attempt}/{MAX_RETRIES}).")

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF_SECONDS)

    logger.error(f"Échec définitif de l'appel météo pour le lot de {len(lat_batch)} villes.")
    return None


def extract_weather(cities: pd.DataFrame, run_ts: str) -> list:

    logger.info("Extraction des prévisions météo depuis Open-Meteo...")

    all_records = []
    failed_cities = []

    n = len(cities)
    for start in range(0, n, BATCH_SIZE):
        batch = cities.iloc[start:start + BATCH_SIZE]
        lat_batch = batch["lat"].tolist()
        lon_batch = batch["lng"].tolist()

        logger.info(f"Lot {start // BATCH_SIZE + 1} : villes {start} à {start + len(batch) - 1}")

        weather_batch = _call_weather_api(lat_batch, lon_batch)

        if weather_batch is None:
            failed_cities.extend(batch["city"].tolist())
            continue

        for (_, city_row), weather in zip(batch.iterrows(), weather_batch):
            all_records.append({
                "city": city_row["city"],
                "lat": city_row["lat"],
                "lng": city_row["lng"],
                "weather_raw": weather,
            })

    raw_path = BRONZE_WEATHER_DIR / f"meteo_{run_ts}.json"
    raw_path.write_text(json.dumps(all_records, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Météo sauvegardée en Bronze : {raw_path}")

    if failed_cities:
        failures_path = LOGS_DIR / f"echecs_meteo_{run_ts}.json"
        failures_path.write_text(json.dumps(failed_cities, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.warning(f"{len(failed_cities)} ville(s) en échec, voir {failures_path}")

    logger.info(f"Prévisions météo récupérées pour {len(all_records)}/{n} villes.")
    return all_records



def main():
    run_ts = run_timestamp()
    logger.info(f"=== Démarrage du run Bronze : {run_ts} ===")

    cities = extract_cities(run_ts)
    weather_records = extract_weather(cities, run_ts)

    logger.info(f"=== Run Bronze terminé : {run_ts} ===")
    return run_ts, cities, weather_records


if __name__ == "__main__":
    main()
