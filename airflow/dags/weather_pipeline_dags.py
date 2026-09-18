"""
==================================================================
DAG — Orchestration quotidienne du pipeline météo
==================================================================
Exécute, dans l'ordre, extract.py -> transform_silver.py ->
transform_gold.py -> load_postgres.py, chaque jour à 6h00
(heure du Maroc). Chaque tâche réessaie automatiquement en cas
d'échec avant d'abandonner et de marquer le DAG en échec.
==================================================================
"""

from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

# Chemin du projet À L'INTÉRIEUR des conteneurs (voir le volume monté
# dans docker-compose.yaml : "${AIRFLOW_PROJ_DIR:-.}:/opt/airflow/project")
PROJECT_DIR = "/opt/airflow/project"


def alerter_echec(context):
    """
    Callback appelé automatiquement par Airflow quand une tâche échoue
    définitivement (après épuisement de ses tentatives). Pour l'instant,
    ça se contente de logger un message clair et visible dans les logs
    Airflow. Point d'extension facile pour un vrai envoi d'email/Slack
    plus tard (bonus "alertes en cas d'échec du DAG").
    """
    tache = context["task_instance"]
    print(
        f"[ALERTE] La tâche '{tache.task_id}' du DAG '{tache.dag_id}' "
        f"a échoué définitivement (run {context['run_id']})."
    )


default_args = {
    "owner": "weather-pipeline",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": alerter_echec,
}

with DAG(
    dag_id="weather_pipeline",
    description="Pipeline météo Bronze -> Silver -> Gold -> PostgreSQL",
    default_args=default_args,
    schedule="0 6 * * *",  # tous les jours à 6h00
    start_date=pendulum.datetime(2026, 9, 1, tz="Africa/Casablanca"),
    catchup=False,  # ne pas rattraper les exécutions passées si le DAG démarre en retard
    tags=["weather", "etl"],
) as dag:

    extraire = BashOperator(
        task_id="extract_bronze",
        bash_command=f"python {PROJECT_DIR}/Scripts/extract.py",
    )

    nettoyer = BashOperator(
        task_id="transform_silver",
        bash_command=f"python {PROJECT_DIR}/Scripts/transform_silver.py",
    )

    enrichir = BashOperator(
        task_id="transform_gold",
        bash_command=f"python {PROJECT_DIR}/Scripts/transform_gold.py",
    )

    charger = BashOperator(
        task_id="load_postgres",
        bash_command=f"python {PROJECT_DIR}/Scripts/load_postgres.py",
    )

    # Ordre d'exécution : chaque tâche ne démarre que si la précédente a réussi.
    extraire >> nettoyer >> enrichir >> charger