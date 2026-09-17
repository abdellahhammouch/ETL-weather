from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SILVER_DIR = PROJECT_ROOT / "silver"
GOLD_DIR = PROJECT_ROOT / "gold"

GOLD_DIR.mkdir(parents=True, exist_ok=True)

PRECIPITATION_WEIGHT = 0.40
WIND_WEIGHT = 0.30
TEMPERATURE_WEIGHT = 0.30


def find_latest_run_ts():
    """Trouve l'identifiant de la dernière exécution Silver disponible."""
    fichiers = list(SILVER_DIR.glob("previsions_*.csv"))
    if not fichiers:
        raise FileNotFoundError("Aucun fichier Silver trouvé. Lance d'abord transform_silver.py.")

    run_ts_list = [f.stem.replace("previsions_", "") for f in fichiers]
    dernier_run = max(run_ts_list)
    print(f"Run Silver le plus récent trouvé : {dernier_run}")
    return dernier_run


def load_silver(run_ts):
    """Charge les prévisions nettoyées de la couche Silver."""
    chemin_silver = SILVER_DIR / f"previsions_{run_ts}.csv"
    df = pd.read_csv(chemin_silver, parse_dates=["date_prevision"])
    print(f"Prévisions Silver chargées : {len(df)}")
    return df


def add_weather_categories(df):
    """Ajoute des catégories lisibles pour l'analyse des conditions météo."""
    df = df.copy()

    df["temperature_category"] = pd.cut(
        df["temperature_max"],
        bins=[float("-inf"), 25, 40, float("inf")],
        labels=["faible", "moyen", "élevé"],
        right=False,
    )
    df["precipitation_category"] = pd.cut(
        df["precipitation_sum"],
        bins=[float("-inf"), 5, 15, float("inf")],
        labels=["faible", "moyen", "élevé"],
        right=False,
    )
    df["wind_category"] = pd.cut(
        df["wind_gusts_max"],
        bins=[float("-inf"), 40, 60, float("inf")],
        labels=["faible", "moyen", "élevé"],
        right=False,
    )
    return df


def compute_risk_score(row):
    """Calcule le score de risque d'une prévision avec des règles de trois."""
    heat_risk = max(
        0,
        min(100, ((row["temperature_max"] - 25) / (55 - 25)) * 100),
    )
    cold_risk = max(
        0,
        min(100, ((10 - row["temperature_min"]) / (10 - (-5))) * 100),
    )
    temperature_risk = max(heat_risk, cold_risk)

    precipitation_risk = max(
        0,
        min(100, (row["precipitation_sum"] / 20) * 100),
    )
    wind_risk = max(
        0,
        min(100, (row["wind_gusts_max"] / 70) * 100),
    )

    score = (
        temperature_risk * TEMPERATURE_WEIGHT
        + precipitation_risk * PRECIPITATION_WEIGHT
        + wind_risk * WIND_WEIGHT
    )
    return round(score)


def calculate_risk_score(df):
    """Ajoute le score de risque à chaque prévision."""
    df = df.copy()
    df["risk_score"] = df.apply(compute_risk_score, axis=1)
    return df


def add_risk_level(df):
    """Transforme le score numérique en un niveau de risque métier."""
    df = df.copy()
    df["risk_level"] = pd.cut(
        df["risk_score"],
        bins=[-1, 30, 60, 101],
        labels=["faible", "moyen", "élevé"],
        right=False,
    )
    return df


def save_gold(df, run_ts):
    """Enregistre le résultat enrichi dans la couche Gold."""
    chemin_sortie = GOLD_DIR / f"risques_meteo_{run_ts}.csv"
    df.to_csv(chemin_sortie, index=False)
    print(f"Fichier Gold sauvegardé : {chemin_sortie}")
    return chemin_sortie


def main():
    run_ts = find_latest_run_ts()
    print(f"\n=== Démarrage du traitement Gold pour le run {run_ts} ===\n")

    df = load_silver(run_ts)
    df = add_weather_categories(df)
    df = calculate_risk_score(df)
    df = add_risk_level(df)
    save_gold(df, run_ts)

    print(f"\n=== Traitement Gold terminé pour le run {run_ts} ===")


if __name__ == "__main__":
    main()
