import logging
from typing import Optional

from .base import LanguageStorage
from .sqlite import SQLiteStorage
from .postgres import PostgreSQLStorage
from .mysql import MySQLStorage


logger = logging.getLogger(__name__)


def _sqlite_path_from_url(url: str) -> str:
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path or ""
        if url.startswith("sqlite:////"):
            return path or "data/data.db"
        return (path.lstrip("/") or "data/data.db")
    except Exception:
        return "data/data.db"


def create_storage(storage_type: str, database_url: str) -> LanguageStorage:
    """Create a storage backend instance based on type or URL."""
    # Normalize requested storage type
    st = (storage_type or "").lower().strip()

    # No JSON/local file backend: only database backends are supported.
    # (If you need a file-backed DB, SQLite is the default.)

    # Prefer database backends when a URL is provided (auto-detect)
    if database_url:
        url_lower = database_url.lower()
        if url_lower.startswith(("postgresql://", "postgres://")):
            return PostgreSQLStorage(database_url)
        elif url_lower.startswith(("mysql://", "mariadb://", "mysql+pymysql://")):
            return MySQLStorage(database_url)
        elif url_lower.startswith("sqlite://"):
            return SQLiteStorage(_sqlite_path_from_url(database_url))
        elif url_lower.endswith(".db"):
            return SQLiteStorage(database_url)

    # If the user explicitly requested a particular backend type, honor it
    if st in ("sqlite", "database", "db"):
        return SQLiteStorage()
    elif st in ("postgresql", "postgres"):
        if not database_url:
            logger.error("PostgreSQL selected but no database_url provided; falling back to sqlite")
            return SQLiteStorage()
        return PostgreSQLStorage(database_url)
    elif st in ("mysql", "mariadb"):
        if not database_url:
            logger.error("MySQL/MariaDB selected but no database_url provided; falling back to sqlite")
            return SQLiteStorage()
        return MySQLStorage(database_url)

    # Default: prefer a lightweight local SQLite database
    return SQLiteStorage()