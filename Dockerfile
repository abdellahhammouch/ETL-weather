FROM apache/airflow:3.3.1

COPY requirements.txt /requirements.txt


RUN pip install --no-cache-dir --user -r /requirements.txt