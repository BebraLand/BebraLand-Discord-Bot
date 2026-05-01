"""
Language preference service facade.
Backends are implemented in src/storage/* modules.
"""

import os
from typing import Optional, Union

import config.constants as constants
from src.storage.base import LanguageStorage
from src.storage.factory import create_storage
from src.utils.db_config import DEFAULT_DATABASE_URL, get_database_url
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


class LanguageManager:
    """Simple language preference manager using pluggable storage backends."""

    def __init__(self, storage_type: str = "local", database_url: str = ""):
        self.storage_type = storage_type.lower()
        self.database_url = database_url
        self.storage: LanguageStorage = create_storage(
            self.storage_type, self.database_url
        )
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
        database_url = get_database_url()

        # Legacy STORAGE_TYPE support (ignored, kept for backward compatibility)
        storage_type = os.getenv("STORAGE_TYPE", "")

        manager = LanguageManager(storage_type=storage_type, database_url=database_url)
        initialized = await manager.initialize()

        # If configured storage fails, fall back to local SQLite so bot features continue working.
        if not initialized:
            logger.error(
                "Primary storage initialization failed for DATABASE_URL/DB_* config. "
                f"Falling back to local SQLite: {DEFAULT_DATABASE_URL}"
            )
            manager = LanguageManager(
                storage_type="local", database_url=DEFAULT_DATABASE_URL
            )
            if not await manager.initialize():
                raise RuntimeError(
                    "Failed to initialize storage (primary and fallback SQLite)"
                )

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
