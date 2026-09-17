from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from common.db import get_engine



PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLD_DIR = PROJECT_ROOT / "gold"




def find_latest_run_ts():
    fichiers = list(GOLD_DIR.glob("risques_meteo_*.csv"))

    if len(fichiers) == 0:
        raise FileNotFoundError("Aucun fichier Gold trouvé. As-tu déjà lancé transform_gold.py ?")

    run_ts_list = [f.stem.replace("risques_meteo_", "") for f in fichiers]
    run_ts_list.sort()
    dernier_run = run_ts_list[-1]

    print(f"Run Gold le plus récent trouvé : {dernier_run}")
    return dernier_run




def load_gold(run_ts):
    chemin_gold = GOLD_DIR / f"risques_meteo_{run_ts}.csv"
    df = pd.read_csv(chemin_gold, parse_dates=["date_prevision"])
    print(f"Prévisions Gold chargées : {len(df)}")
    return df





def upsert_villes(df, engine):
    villes_uniques = df.drop_duplicates(subset=["city"])
    ville_id_par_nom = {}

    requete = text(
        """
        INSERT INTO villes (city, latitude, longitude, region)
        VALUES (:city, :latitude, :longitude, :region)
        ON CONFLICT (city)
        DO UPDATE SET
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            region = EXCLUDED.region
        RETURNING id;
        """
    )



    with engine.begin() as connexion:
        for _, ligne in villes_uniques.iterrows():
            resultat = connexion.execute(
                requete,
                {
                    "city": ligne["city"],
                    "latitude": ligne["latitude"],
                    "longitude": ligne["longitude"],
                    "region": ligne.get("region"),
                },
            )
            ville_id = resultat.scalar()
            ville_id_par_nom[ligne["city"]] = ville_id

    print(f"Villes insérées/mises à jour : {len(ville_id_par_nom)}")
    return ville_id_par_nom




def insert_previsions(df, engine, ville_id_par_nom, run_ts):
    retrieved_at = datetime.strptime(run_ts, "%Y%m%d_%H%M%S")

    requete = text(
        """
        INSERT INTO previsions (
            ville_id, date_prevision,
            temperature_max, temperature_min,
            precipitation_sum, precipitation_probability_max,
            wind_speed_max, wind_gusts_max, weather_code,
            temperature_category, precipitation_category, wind_category,
            risk_score, risk_level, retrieved_at
        )
        VALUES (
            :ville_id, :date_prevision,
            :temperature_max, :temperature_min,
            :precipitation_sum, :precipitation_probability_max,
            :wind_speed_max, :wind_gusts_max, :weather_code,
            :temperature_category, :precipitation_category, :wind_category,
            :risk_score, :risk_level, :retrieved_at
        )
        ON CONFLICT (ville_id, date_prevision, retrieved_at) DO NOTHING;
        """
    )

    nombre_inserees = 0

    with engine.begin() as connexion:
        for _, ligne in df.iterrows():
            resultat = connexion.execute(
                requete,
                {
                    "ville_id": ville_id_par_nom[ligne["city"]],
                    "date_prevision": ligne["date_prevision"].date(),
                    "temperature_max": ligne["temperature_max"],
                    "temperature_min": ligne["temperature_min"],
                    "precipitation_sum": ligne["precipitation_sum"],
                    "precipitation_probability_max": ligne["precipitation_probability_max"],
                    "wind_speed_max": ligne["wind_speed_max"],
                    "wind_gusts_max": ligne["wind_gusts_max"],
                    "weather_code": ligne["weather_code"],
                    "temperature_category": ligne["temperature_category"],
                    "precipitation_category": ligne["precipitation_category"],
                    "wind_category": ligne["wind_category"],
                    "risk_score": ligne["risk_score"],
                    "risk_level": ligne["risk_level"],
                    "retrieved_at": retrieved_at,
                },
            )
            nombre_inserees += resultat.rowcount

    print(f"Lignes de prévisions réellement insérées : {nombre_inserees} / {len(df)}")





def main():
    run_ts = find_latest_run_ts()
    print(f"\n=== Démarrage du chargement PostgreSQL pour le run {run_ts} ===\n")

    df = load_gold(run_ts)

    engine = get_engine()
    ville_id_par_nom = upsert_villes(df, engine)
    insert_previsions(df, engine, ville_id_par_nom, run_ts)

    print(f"\n=== Chargement PostgreSQL terminé pour le run {run_ts} ===")


if __name__ == "__main__":
    main()