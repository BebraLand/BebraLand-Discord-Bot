"""
Language preference service facade.
Backends are implemented in src/storage/* modules.
"""

import os
from typing import Optional, Union

from src.storage.factory import create_storage
from src.storage.base import LanguageStorage
from src.utils.logger import get_cool_logger
import config.constants as constants


logger = get_cool_logger(__name__)


class LanguageManager:
    """Simple language preference manager using pluggable storage backends."""

    def __init__(self, storage_type: str = "local", database_url: str = ""):
        self.storage_type = storage_type.lower()
        self.database_url = database_url
        self.storage: LanguageStorage = create_storage(self.storage_type, self.database_url)
        self.initialized = False

    async def initialize(self) -> bool:
        if not await self.storage.initialize():
            logger.error("Failed to initialize storage")
            self.initialized = False
            return False
        self.initialized = True
        logger.info("Language manager initialized")
        return True

    def _is_english(self, language: str) -> bool:
        return language.lower() in ["en", "en_us", "en_gb", "en-us", "en-gb"]

    async def set_language(self, user_id: Union[str, int], language: str) -> bool:
        user_id = str(user_id)
        if self._is_english(language):
            await self.storage.remove(user_id)
            return True
        return await self.storage.set(user_id, language)

    async def get_language(self, user_id: Union[str, int]) -> str:
        user_id = str(user_id)
        language = await self.storage.get(user_id)
        return language if language else constants.DEFAULT_LANGUAGE

    async def close(self) -> None:
        if self.storage:
            await self.storage.close()


# Global instance
_manager: Optional[LanguageManager] = None


async def get_manager() -> LanguageManager:
    global _manager
    if _manager is None:
        from urllib.parse import quote_plus
        
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
                    
                    # Add SSL mode if specified (for cloud databases like Supabase)
                    # Note: DB_SSL_MODE is PostgreSQL-specific. For MySQL SSL, use DATABASE_URL with ssl_ca, ssl_cert, ssl_key params
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
            else:
                # Default to SQLite if nothing is specified
                database_url = f"sqlite+aiosqlite:///{db_path or 'data/data.db'}"
        
        # Legacy STORAGE_TYPE support (ignored, kept for backward compatibility)
        storage_type = os.getenv("STORAGE_TYPE", "")
        
        manager = LanguageManager(storage_type=storage_type, database_url=database_url)
        initialized = await manager.initialize()

        # If configured storage fails, fall back to local SQLite so bot features continue working.
        if not initialized:
            fallback_url = "sqlite+aiosqlite:///data/data.db"
            logger.error(
                "Primary storage initialization failed for DATABASE_URL/DB_* config. "
                f"Falling back to local SQLite: {fallback_url}"
            )
            manager = LanguageManager(storage_type="local", database_url=fallback_url)
            if not await manager.initialize():
                raise RuntimeError("Failed to initialize storage (primary and fallback SQLite)")

        _manager = manager
    elif not _manager.initialized:
        # Recover from a stale manager instance that was not initialized.
        if not await _manager.initialize():
            raise RuntimeError("Storage manager exists but could not be initialized")
    return _manager


async def set_language(user_id: Union[str, int], language: str) -> bool:
    manager = await get_manager()
    return await manager.set_language(user_id, language)


async def get_language(user_id: Union[str, int]) -> str:
    manager = await get_manager()
    return await manager.get_language(user_id)


async def get_db() -> LanguageStorage:
    """
    Get the storage instance directly.
    This is useful for accessing ticket methods and other storage functionality.
    """
    manager = await get_manager()
    return manager.storage