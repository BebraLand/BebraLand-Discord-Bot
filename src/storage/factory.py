import logging
import os
from typing import Optional
from urllib.parse import quote_plus

from .base import LanguageStorage
from .sqlalchemy_storage import SQLAlchemyStorage


logger = logging.getLogger(__name__)


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


# Global storage instance
_storage: Optional[LanguageStorage] = None


def get_storage() -> LanguageStorage:
    """
    Get the global storage instance.
    Creates it if it doesn't exist using environment variables.
    
    Returns:
        Global storage instance
    """
    global _storage
    
    if _storage is None:
        # Get DATABASE_URL first (recommended way)
        database_url = os.getenv("DATABASE_URL", "").strip()
        
        # If DATABASE_URL is not provided, construct it from individual components
        if not database_url:
            db_type = os.getenv("DB_TYPE", "").lower().strip()
            db_host = os.getenv("DB_HOST", "").strip()
            db_port = os.getenv("DB_PORT", "").strip()
            db_user = os.getenv("DB_USER", "").strip()
            db_password = os.getenv("DB_PASSWORD", "").strip()
            db_name = os.getenv("DB_NAME", "").strip()
            db_path = os.getenv("DB_PATH", "").strip()
            db_ssl_mode = os.getenv("DB_SSL_MODE", "").strip()
            
            # Construct database URL based on DB_TYPE
            if db_type == "sqlite" or (not db_type and db_path):
                # SQLite with async driver
                path = db_path or "data/data.db"
                database_url = f"sqlite+aiosqlite:///{path}"
            elif db_type in ("postgresql", "postgres"):
                # PostgreSQL with asyncpg driver
                if db_host and db_name:
                    port = db_port or "5432"
                    if db_user:
                        if db_password:
                            auth = f"{quote_plus(db_user)}:{quote_plus(db_password)}@"
                        else:
                            auth = f"{db_user}@"
                    else:
                        auth = ""
                    database_url = f"postgresql+asyncpg://{auth}{db_host}:{port}/{db_name}"
                    
                    # Add SSL mode if specified
                    if db_ssl_mode:
                        database_url += f"?ssl={db_ssl_mode}"
            elif db_type in ("mysql", "mariadb"):
                # MySQL/MariaDB with aiomysql driver
                if db_host and db_name:
                    port = db_port or "3306"
                    if db_user:
                        if db_password:
                            auth = f"{quote_plus(db_user)}:{quote_plus(db_password)}@"
                        else:
                            auth = f"{db_user}@"
                    else:
                        auth = ""
                    database_url = f"mysql+aiomysql://{auth}{db_host}:{port}/{db_name}"
        
        # Create storage using the constructed or provided URL
        _storage = create_storage("sqlalchemy", database_url)
        logger.info("Global storage instance created")
    
    return _storage
