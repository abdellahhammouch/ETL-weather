# Image dédiée au dashboard, séparée d'Airflow — plus légère, basée sur
# Python simple plutôt que sur l'image Airflow (inutilement lourde ici).
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# On copie tout le projet : le dashboard a besoin de Scripts/common/db.py
# (réutilisé pour la connexion à PostgreSQL), pas seulement de dashboard/.
COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]