import logging

from .base import LanguageStorage
from .sqlalchemy_storage import SQLAlchemyStorage


logger = logging.getLogger(__name__)


def create_storage(storage_type: str, database_url: str) -> LanguageStorage:
    """Create a unified SQLAlchemy storage backend based on type or URL."""
    st = (storage_type or "").lower().strip()
    db_url = (database_url or "").strip()

    # Prefer provided URL (supports sqlite/postgres/mysql; async driver is handled in backend)
    if db_url:
        url_lower = db_url.lower()
        if url_lower.startswith("sqlite://"):
            return SQLAlchemyStorage(db_url)
        if url_lower.startswith(("postgresql://", "postgres://", "postgresql+")):
            return SQLAlchemyStorage(db_url)
        if url_lower.startswith(("mysql://", "mariadb://", "mysql+")):
            return SQLAlchemyStorage(db_url)
        if url_lower.endswith(".db"):
            return SQLAlchemyStorage(f"sqlite:///{db_url}")

    # Explicit type without URL
    if st in ("postgresql", "postgres", "mysql", "mariadb"):
        logger.error(f"{st} selected but no database_url provided; falling back to sqlite")
        return SQLAlchemyStorage("sqlite:///data/data.db")

    # Default: lightweight local SQLite database
    return SQLAlchemyStorage("sqlite:///data/data.db")
