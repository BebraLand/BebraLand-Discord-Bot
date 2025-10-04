import logging
from typing import Optional

from .base import LanguageStorage
from .local import LocalFileStorage
from .sqlite import SQLiteStorage
from .postgres import PostgreSQLStorage
from .mysql import MySQLStorage


logger = logging.getLogger(__name__)


def create_storage(storage_type: str, database_url: str) -> LanguageStorage:
    """Create a storage backend instance based on type or URL."""
    st = (storage_type or "").lower()

    if st in ("local", "json"):
        return LocalFileStorage()
    elif st == "sqlite":
        return SQLiteStorage()
    elif st == "postgresql":
        if not database_url:
            logger.error("PostgreSQL selected but no database_url provided; falling back to local")
            return LocalFileStorage()
        return PostgreSQLStorage(database_url)
    elif st == "mysql":
        if not database_url:
            logger.error("MySQL selected but no database_url provided; falling back to local")
            return LocalFileStorage()
        return MySQLStorage(database_url)

    # Auto-detect from URL
    if database_url:
        url_lower = database_url.lower()
        if url_lower.startswith(("postgresql://", "postgres://")):
            return PostgreSQLStorage(database_url)
        elif url_lower.startswith("mysql://"):
            return MySQLStorage(database_url)
        elif url_lower.startswith("sqlite://") or url_lower.endswith(".db"):
            return SQLiteStorage()
        else:
            logger.error("Unknown database URL format; falling back to local")

    return LocalFileStorage()