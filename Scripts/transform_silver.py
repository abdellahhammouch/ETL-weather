import json
from pathlib import Path
from datetime import datetime

import pandas as pd

from common.logging_utils import get_logger

logger = get_logger("transform_silver")


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRONZE_CITIES_DIR = PROJECT_ROOT / "bronze" / "villes"
BRONZE_WEATHER_DIR = PROJECT_ROOT / "bronze" / "meteo"
SILVER_DIR = PROJECT_ROOT / "silver"

SILVER_DIR.mkdir(parents=True, exist_ok=True)


TEMP_MIN_POSSIBLE = -10
TEMP_MAX_POSSIBLE = 55
PRECIPITATION_MAX_POSSIBLE = 500
VENT_MAX_POSSIBLE = 250




def find_latest_run_ts():
    fichiers = list(BRONZE_CITIES_DIR.glob("villes_*.csv"))

    if len(fichiers) == 0:
        raise FileNotFoundError("Aucun fichier Bronze trouvé. As-tu déjà lancé extract.py ?")

    run_ts_list = []
    for f in fichiers:
        nom_sans_extension = f.stem
        run_ts = nom_sans_extension.replace("villes_", "")
        run_ts_list.append(run_ts)

    run_ts_list.sort()
    dernier_run = run_ts_list[-1]

    logger.info(f"Run Bronze le plus récent trouvé : {dernier_run}")
    return dernier_run



def load_bronze(run_ts):
    chemin_villes = BRONZE_CITIES_DIR / f"villes_{run_ts}.csv"
    chemin_meteo = BRONZE_WEATHER_DIR / f"meteo_{run_ts}.json"

    cities_df = pd.read_csv(chemin_villes)

    with open(chemin_meteo, "r", encoding="utf-8") as f:
        weather_records = json.load(f)

    logger.info(f"Villes chargées : {len(cities_df)}")
    logger.info(f"Enregistrements météo chargés : {len(weather_records)}")

    return cities_df, weather_records




def flatten_weather(weather_records, run_ts):
    lignes = []

    for enregistrement in weather_records:
        ville = enregistrement["city"]
        latitude = enregistrement["lat"]
        longitude = enregistrement["lng"]
        daily = enregistrement["weather_raw"]["daily"]

        dates = daily["time"]
        nombre_de_jours = len(dates)

        for i in range(nombre_de_jours):
            ligne = {
                "city": ville,
                "latitude": latitude,
                "longitude": longitude,
                "date_prevision": dates[i],
                "retrieved_at": run_ts,
                "temperature_max": daily["temperature_2m_max"][i],
                "temperature_min": daily["temperature_2m_min"][i],
                "precipitation_sum": daily["precipitation_sum"][i],
                "precipitation_probability_max": daily["precipitation_probability_max"][i],
                "wind_speed_max": daily["wind_speed_10m_max"][i],
                "wind_gusts_max": daily["wind_gusts_10m_max"][i],
                "weather_code": daily["weather_code"][i],
            }
            lignes.append(ligne)

    df = pd.DataFrame(lignes)
    logger.info(f"Nombre de lignes après transformation (ville x jour) : {len(df)}")
    return df



def merge_with_cities(df, cities_df):
    """Jointure entre les prévisions météo et le référentiel des villes.

    Le nom de ville présent dans le Bronze météo permet déjà de relier
    chaque prévision à ses coordonnées, mais le référentiel SimpleMaps
    contient des informations supplémentaires (région, population) qui ne
    sont récupérées nulle part ailleurs dans le pipeline. On les rapatrie
    ici, comme demandé par le cahier des charges (jointure villes x météo).
    """

    colonnes_villes = cities_df[["city", "admin_name", "population"]].rename(
        columns={"admin_name": "region"}
    )

    doublons_villes = colonnes_villes["city"].duplicated().sum()
    if doublons_villes > 0:
        logger.warning(
            f"Attention : {doublons_villes} ville(s) en double dans le référentiel "
            "SimpleMaps, on garde la première occurrence pour la jointure."
        )
        colonnes_villes = colonnes_villes.drop_duplicates(subset=["city"], keep="first")

    df = df.merge(colonnes_villes, on="city", how="left")

    villes_sans_correspondance = df.loc[df["region"].isna(), "city"].unique()
    if len(villes_sans_correspondance) > 0:
        logger.warning(
            f"Attention : {len(villes_sans_correspondance)} ville(s) sans région "
            f"après la jointure : {list(villes_sans_correspondance)}"
        )

    logger.info("Jointure villes x météo effectuée (région, population).")
    return df



def standardize_types(df):
    df["date_prevision"] = pd.to_datetime(df["date_prevision"], errors="coerce")

    colonnes_numeriques = [
        "latitude", "longitude", "temperature_max", "temperature_min",
        "precipitation_sum", "precipitation_probability_max",
        "wind_speed_max", "wind_gusts_max", "weather_code", "population",
    ]
    for colonne in colonnes_numeriques:
        df[colonne] = pd.to_numeric(df[colonne], errors="coerce")

    logger.info("Types de données standardisés.")
    return df



def remove_duplicates(df):
    nombre_avant = len(df)

    df = df.drop_duplicates(subset=["city", "date_prevision"], keep="first")

    nombre_apres = len(df)
    nombre_supprimes = nombre_avant - nombre_apres

    if nombre_supprimes > 0:
        logger.warning(f"{nombre_supprimes} doublon(s) supprimé(s).")
    else:
        logger.info("Aucun doublon trouvé.")

    return df



def detect_inconsistencies(df):
    lignes_incoherentes = []

    for index, ligne in df.iterrows():
        probleme_trouve = False

        if (
            pd.notna(ligne["temperature_min"])
            and pd.notna(ligne["temperature_max"])
            and ligne["temperature_min"] > ligne["temperature_max"]
        ):
            probleme_trouve = True

        if pd.notna(ligne["temperature_max"]) and (
            ligne["temperature_max"] < TEMP_MIN_POSSIBLE
            or ligne["temperature_max"] > TEMP_MAX_POSSIBLE
        ):
            probleme_trouve = True

        if pd.notna(ligne["temperature_min"]) and (
            ligne["temperature_min"] < TEMP_MIN_POSSIBLE
            or ligne["temperature_min"] > TEMP_MAX_POSSIBLE
        ):
            probleme_trouve = True

        if pd.notna(ligne["precipitation_sum"]) and (
            ligne["precipitation_sum"] < 0
            or ligne["precipitation_sum"] > PRECIPITATION_MAX_POSSIBLE
        ):
            probleme_trouve = True

        if pd.notna(ligne["wind_speed_max"]) and (
            ligne["wind_speed_max"] < 0
            or ligne["wind_speed_max"] > VENT_MAX_POSSIBLE
        ):
            probleme_trouve = True

        if pd.notna(ligne["wind_gusts_max"]) and (
            ligne["wind_gusts_max"] < 0
            or ligne["wind_gusts_max"] > VENT_MAX_POSSIBLE
        ):
            probleme_trouve = True

        if probleme_trouve:
            lignes_incoherentes.append(index)

    df = df.drop(index=lignes_incoherentes).copy()
    logger.warning(f"Nombre de lignes incohérentes supprimées : {len(lignes_incoherentes)}") if lignes_incoherentes else logger.info("Aucune ligne incohérente détectée.")
    return df



def quality_checks(df, nombre_villes_bronze):
    if len(df) == 0:
        raise ValueError("Le tableau Silver est vide ! Quelque chose s'est mal passé.")

    nombre_villes_silver = df["city"].nunique()
    if nombre_villes_silver < nombre_villes_bronze:
        logger.warning(f"Attention : seulement {nombre_villes_silver}/{nombre_villes_bronze} villes sont présentes en Silver.")

    for colonne in ["city", "date_prevision", "latitude", "longitude", "region"]:
        nombre_manquant = df[colonne].isna().sum()
        if nombre_manquant > 0:
            logger.warning(f"Attention : {nombre_manquant} valeur(s) manquante(s) dans la colonne '{colonne}'.")

    logger.info("Contrôles qualité terminés.")



def save_silver(df, run_ts):
    chemin_sortie = SILVER_DIR / f"previsions_{run_ts}.csv"
    df.to_csv(chemin_sortie, index=False)
    logger.info(f"Fichier Silver sauvegardé : {chemin_sortie}")
    return chemin_sortie



def main():
    run_ts = find_latest_run_ts()

    logger.info(f"=== Démarrage du traitement Silver pour le run {run_ts} ===")

    cities_df, weather_records = load_bronze(run_ts)

    df = flatten_weather(weather_records, run_ts)
    df = merge_with_cities(df, cities_df)
    df = standardize_types(df)
    df = remove_duplicates(df)
    df = detect_inconsistencies(df)
    quality_checks(df, nombre_villes_bronze=len(cities_df))

    save_silver(df, run_ts)


    logger.info(f"=== Traitement Silver terminé pour le run {run_ts} ===")


if __name__ == "__main__":
    main()
    