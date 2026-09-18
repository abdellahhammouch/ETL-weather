# ETL météo — risques pour les livraisons au Maroc

## Présentation

Ce projet construit un pipeline de données permettant d'anticiper les perturbations météorologiques pour les opérations de livraison dans les villes marocaines.

Il collecte les villes et leurs coordonnées, récupère les prévisions quotidiennes, contrôle la qualité des données, calcule un score de risque météo, puis charge le résultat dans PostgreSQL. Un dashboard Streamlit permet ensuite de répondre rapidement à la question métier suivante :

> Où et quand faut-il être particulièrement vigilant pour les livraisons dans les prochains jours ?

Le projet suit l'architecture **Bronze → Silver → Gold**, est orchestré quotidiennement avec Airflow et est conteneurisé avec Docker Compose.

## Sources de données

| Source | Usage dans le projet | Données utilisées |
|---|---|---|
| [SimpleMaps — villes du Maroc](https://simplemaps.com/data/ma-cities) | Référentiel géographique | Nom des villes, coordonnées, région et population |
| [Open-Meteo Forecast API](https://open-meteo.com/en/docs) | Prévisions météorologiques quotidiennes | Températures min./max., précipitations, probabilité de pluie, vent, rafales et code météo |

Open-Meteo est interrogée à partir de la latitude et de la longitude de chaque ville. Les variables quotidiennes correspondent aux facteurs pouvant perturber les livraisons : chaleur ou froid, pluie et rafales.

## Architecture

```text
SimpleMaps                  Open-Meteo
    │                           │
    └───────────┬───────────────┘
                ▼
        Bronze — données brutes
                │
                ▼
     Silver — nettoyage et qualité
                │
                ▼
 Gold — catégories et score de risque
                │
                ▼
      PostgreSQL — entrepôt de données
                │
                ▼
        Streamlit — dashboard métier

Airflow orchestre les quatre traitements chaque jour.
```

### Bronze — extraction

`Scripts/extract.py` télécharge le CSV des villes depuis SimpleMaps, appelle Open-Meteo par lots de coordonnées et enregistre les réponses sans les modifier dans `bronze/`. Il journalise les traitements dans `logs/` et gère les délais dépassés, erreurs HTTP, erreurs réseau et réponses invalides avec des tentatives supplémentaires.

Les fichiers Bronze sont immuables : ils constituent la trace des données reçues depuis les sources.

### Silver — nettoyage et contrôle qualité

`Scripts/transform_silver.py` sélectionne la dernière exécution Bronze, transforme le JSON météo imbriqué en table, standardise les types, retire les doublons et supprime les lignes incohérentes. Les contrôles portent notamment sur les températures, les précipitations, la vitesse du vent et les rafales.

Le résultat est enregistré dans `silver/previsions_<horodatage>.csv`.

### Gold — indicateurs métier

`Scripts/transform_gold.py` ajoute des catégories `faible`, `moyen` et `élevé` pour la température, les précipitations et les rafales, puis calcule un `risk_score` entre zéro et cent ainsi qu'un `risk_level`.

```text
risk_score = risque_température × 30 %
           + risque-précipitations × 40 %
           + risque-rafales × 30 %
```

Les sous-scores sont calculés par règle de trois et bornés entre zéro et cent. La température utilise le risque le plus élevé entre chaleur et froid. Le résultat est enregistré dans `gold/risques_meteo_<horodatage>.csv`.

## Entrepôt de données PostgreSQL

Le schéma est défini dans [`sql/schema.sql`](sql/schema.sql).

```text
┌──────────────────────────┐       ┌───────────────────────────────┐
│          villes          │       │           previsions          │
├──────────────────────────┤       ├───────────────────────────────┤
│ id (PK)                  │◄──────│ ville_id (FK)                 │
│ city (unique)            │       │ id (PK)                       │
│ latitude                 │       │ date_prevision                │
│ longitude                │       │ températures, pluie, vent     │
│ region                   │       │ catégories météo              │
└──────────────────────────┘       │ risk_score, risk_level        │
                                   │ retrieved_at                  │
                                   └───────────────────────────────┘
```

La contrainte d'unicité `(ville_id, date_prevision, retrieved_at)` évite les doublons pour une même version de prévision et conserve l'historique lors des mises à jour de l'API.

`Scripts/load_postgres.py` insère ou met à jour les villes et charge les prévisions Gold avec `ON CONFLICT`. Les six requêtes d'analyse métier sont disponibles dans [`sql/requetes_analyse.sql`](sql/requetes_analyse.sql).

## Installation

### Prérequis

- Docker Desktop avec Docker Compose ;
- Python 3.11 ou version plus récente, uniquement pour une exécution hors conteneur ;
- un accès Internet pour SimpleMaps et Open-Meteo.

### Configuration

Copiez le modèle puis renseignez les secrets locaux dans `.env` :

```powershell
Copy-Item env.example .env
```

Variables à définir :

```dotenv
DB_HOST=postgres_app
DB_PORT=5432
DB_NAME=weather_etl
DB_USER=postgres
DB_PASSWORD=un_mot_de_passe_solide
AIRFLOW_UID=50000
FERNET_KEY=une_cle_fernet
_AIRFLOW_WWW_USER_USERNAME=admin
_AIRFLOW_WWW_USER_PASSWORD=un_mot_de_passe_airflow
```

Générez la clé Fernet et copiez-la dans `FERNET_KEY` :

```powershell
docker run --rm apache/airflow:3.3.1 python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Ne versionnez jamais le fichier `.env`.

### Dépendances Python locales

Uniquement pour une exécution hors Docker :

```powershell
python -m pip install -r requirements.txt
```

## Exécution avec Docker Compose

### Préparer le DAG

Le fichier Compose monte le dossier racine `dags/`, tandis que le DAG est actuellement dans `airflow/dags/`. Copiez-le avant le démarrage :

```powershell
New-Item -ItemType Directory -Force dags
Copy-Item airflow/dags/weather_pipeline_dags.py dags/weather_pipeline_dags.py
```

### Démarrer les services

```powershell
docker compose build
docker compose up airflow-init
docker compose up -d
```

| Service | Adresse | Rôle |
|---|---|---|
| Airflow | <http://localhost:8080> | Orchestration et suivi des tâches |
| Streamlit | <http://localhost:8501> | Dashboard métier |
| PostgreSQL métier | `postgres_app:5432` dans Docker | Stockage des villes et prévisions |

Connectez-vous à Airflow avec les identifiants définis dans `.env`, activez `weather_pipeline` ou déclenchez-le manuellement. Le DAG est planifié chaque jour à six heures, heure de Casablanca, et exécute :

```text
extract_bronze → transform_silver → transform_gold → load_postgres
```

Chaque tâche est réessayée deux fois avec un délai de cinq minutes. En cas d'échec définitif, une alerte est écrite dans les logs Airflow.

Pour arrêter les services :

```powershell
docker compose down
```

Pour supprimer aussi les volumes de données locaux :

```powershell
docker compose down -v
```

> Attention : cette dernière commande supprime les bases PostgreSQL locales.

## Exécution manuelle du pipeline

### Depuis Docker

Après `docker compose up -d`, lancez les étapes dans cet ordre :

```powershell
docker compose exec airflow-scheduler python /opt/airflow/project/Scripts/extract.py
docker compose exec airflow-scheduler python /opt/airflow/project/Scripts/transform_silver.py
docker compose exec airflow-scheduler python /opt/airflow/project/Scripts/transform_gold.py
docker compose exec airflow-scheduler python /opt/airflow/project/Scripts/load_postgres.py
```

### Hors Docker

Une instance PostgreSQL accessible doit être disponible. Définissez `DB_HOST=localhost` dans `.env`, créez le schéma puis lancez :

```powershell
psql -U postgres -d weather_etl -f sql/schema.sql
python Scripts/extract.py
python Scripts/transform_silver.py
python Scripts/transform_gold.py
python Scripts/load_postgres.py
```

Pour ouvrir le dashboard hors Docker :

```powershell
streamlit run dashboard/app.py
```

## Dashboard Streamlit

Le dashboard présente :

- les indicateurs clés : nombre de villes, température maximale, précipitations maximales, périodes à risque élevé et ville la plus à risque ;
- des filtres par ville, période, date et niveau de risque ;
- une carte interactive des villes ;
- le classement des dix villes au risque moyen le plus élevé ;
- un tableau détaillé des prévisions.

### Captures d'écran

Ajoutez les captures réelles après le premier chargement de données dans `docs/images/` : une vue d'ensemble, le classement des villes à risque et des filtres appliqués.

```markdown
![Vue générale du dashboard](docs/images/dashboard-overview.png)
![Analyse des villes à risque](docs/images/dashboard-risques.png)
```

## Structure du projet

```text
.
├── Scripts/
│   ├── extract.py                 # Bronze
│   ├── transform_silver.py        # Silver
│   ├── transform_gold.py          # Gold
│   ├── load_postgres.py           # Chargement PostgreSQL
│   └── common/                    # Configuration et connexion à la base
├── sql/                           # Schéma et requêtes métier
├── airflow/dags/                  # Définition du DAG
├── dashboard/app.py               # Application Streamlit
├── docker-compose.yaml            # Services Docker
├── requirements.txt               # Dépendances Python
└── env.example                    # Modèle de variables d'environnement
```
