import os
from pathlib import Path

from dotenv import load_dotenv



ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"



load_dotenv(dotenv_path=ENV_PATH)

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "weather_etl")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")