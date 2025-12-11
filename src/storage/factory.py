import logging

from .base import LanguageStorage
from .sqlalchemy_storage import SQLAlchemyStorage, normalize_database_url

logger = logging.getLogger(__name__)


def create_storage(storage_type: str, database_url: str) -> LanguageStorage:
    """Create a unified SQLAlchemy-backed storage instance."""
    st = (storage_type or "").lower().strip()
    normalized_url = normalize_database_url(database_url)

    if not database_url and st in ("postgresql", "postgres", "mysql", "mariadb"):
        selected_backend = (st or "database").upper()
        logger.warning(
            "%s selected but no DATABASE_URL provided; falling back to SQLite",
            selected_backend,
        )
        normalized_url = normalize_database_url("")

    return SQLAlchemyStorage(normalized_url)
