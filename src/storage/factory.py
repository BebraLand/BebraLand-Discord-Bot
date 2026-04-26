from typing import Optional

from .base import LanguageStorage
from .sqlalchemy_storage import SQLAlchemyStorage
from src.utils.logger import get_cool_logger


logger = get_cool_logger(__name__)


def create_storage(storage_type: str, database_url: str) -> LanguageStorage:
    """
    Create a unified SQLAlchemy-based storage backend.
    
    Args:
        storage_type: Legacy parameter (ignored, kept for compatibility)
        database_url: SQLAlchemy database URL or empty for default SQLite
        
    Returns:
        SQLAlchemyStorage instance configured for the specified database
        
    Supported database URLs:
        - SQLite: sqlite+aiosqlite:///data/data.db (or relative path)
        - PostgreSQL: postgresql+asyncpg://user:pass@host:port/db
        - MySQL: mysql+aiomysql://user:pass@host:port/db
        - MariaDB: mysql+aiomysql://user:pass@host:port/db (same as MySQL)
    """
    # If no database URL provided, default to SQLite
    if not database_url or not database_url.strip():
        database_url = "sqlite+aiosqlite:///data/data.db"
        logger.info("No DATABASE_URL provided, using default SQLite storage")
        return SQLAlchemyStorage(database_url)
    
    # Ensure async drivers are specified in the URL
    # Convert legacy URL formats to async driver formats
    url_lower = database_url.lower()
    
    # Check if async driver is already specified
    if "+aiosqlite" in url_lower or "+asyncpg" in url_lower or "+aiomysql" in url_lower:
        # Already has async driver, use as-is
        logger.info(f"Creating storage with URL: {database_url.split('://')[0]}://...")
        return SQLAlchemyStorage(database_url)
    
    # Convert legacy formats
    if url_lower.startswith("sqlite://"):
        # Convert sqlite:// to sqlite+aiosqlite://
        database_url = database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    elif url_lower.startswith(("postgresql://", "postgres://")):
        # Convert to asyncpg driver
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url_lower.startswith(("mysql://", "mariadb://")):
        # Convert to aiomysql driver
        database_url = database_url.replace("mysql://", "mysql+aiomysql://", 1)
        database_url = database_url.replace("mariadb://", "mysql+aiomysql://", 1)
    elif url_lower.endswith(".db"):
        # Plain file path - convert to SQLite URL
        database_url = f"sqlite+aiosqlite:///{database_url}"
    
    logger.info(f"Creating storage with URL: {database_url.split('://')[0]}://...")
    return SQLAlchemyStorage(database_url)