from sqlalchemy import create_engine

from common import config


def get_engine():
    url = (
        f"postgresql+psycopg2://{config.DB_USER}:{config.DB_PASSWORD}"
        f"@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"
    )
    engine = create_engine(url)
    return engine
