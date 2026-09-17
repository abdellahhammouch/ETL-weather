# Étend l'image officielle Airflow avec les bibliothèques dont nos scripts
# (extract.py, transform_silver.py, transform_gold.py, load_postgres.py) ont besoin.
# C'est l'approche recommandée par Airflow pour de vraies dépendances (par
# opposition à _PIP_ADDITIONAL_REQUIREMENTS, réservé aux tests rapides).
FROM apache/airflow:3.3.1

COPY requirements.txt /requirements.txt

# On ne réinstalle pas streamlit/plotly ici (inutiles pour Airflow, seulement
# utiles au conteneur streamlit), mais les garder ne casse rien non plus —
# on garde un seul fichier requirements.txt pour tout le projet, plus simple
# à maintenir qu'un fichier par service.
RUN pip install --no-cache-dir --user -r /requirements.txt