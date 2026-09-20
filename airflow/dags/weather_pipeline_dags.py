from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG


PROJECT_DIR = "/opt/airflow/project"


def alerter_echec(context):
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
    schedule="0 6 * * *",
    start_date=pendulum.datetime(2026, 9, 1, tz="Africa/Casablanca"),
    catchup=False,
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


    extraire >> nettoyer >> enrichir >> charger