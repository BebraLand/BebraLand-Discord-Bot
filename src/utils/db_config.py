"""Database URL helpers shared by storage and scheduled jobs."""

import os

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

from config.constants import DEFAULT_DATABASE_URL
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)
_warned_default_database_url = False


def _clean_env_value(value: str | None) -> str:
    if value is None:
        return ""

    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1].strip()

    if value in ('""', "''") or value.startswith(('"" ', "'' ")):
        return ""

    return value


def get_database_url() -> str:
    """Return the configured async SQLAlchemy URL or the default local SQLite URL."""
    global _warned_default_database_url

    load_dotenv()

    database_url = _clean_env_value(os.getenv("DATABASE_URL"))
    if database_url:
        return database_url

    if not _warned_default_database_url:
        logger.warning(
            "DATABASE_URL is empty; using default local SQLite database: "
            f"{DEFAULT_DATABASE_URL}"
        )
        _warned_default_database_url = True

    return DEFAULT_DATABASE_URL


def get_scheduler_database_url() -> str:
    """Return a synchronous SQLAlchemy URL for APScheduler's SQLAlchemyJobStore."""
    url = make_url(get_database_url())
    sync_drivers = {
        "postgres": "postgresql",
        "sqlite+aiosqlite": "sqlite",
        "postgresql+asyncpg": "postgresql",
        "postgres+asyncpg": "postgresql",
        "mysql+aiomysql": "mysql",
        "mariadb+aiomysql": "mariadb",
    }
    drivername = sync_drivers.get(url.drivername, url.drivername)
    return url.set(drivername=drivername).render_as_string(hide_password=False)
