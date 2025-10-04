"""
Language preference service facade.
Backends are implemented in src/storage/* modules.
"""

import os
import logging
from typing import Optional, Union

from src.storage.factory import create_storage
from src.storage.base import LanguageStorage


logger = logging.getLogger(__name__)


class LanguageManager:
    """Simple language preference manager using pluggable storage backends."""

    def __init__(self, storage_type: str = "local", database_url: str = ""):
        self.storage_type = storage_type.lower()
        self.database_url = database_url
        self.storage: LanguageStorage = create_storage(self.storage_type, self.database_url)

    async def initialize(self) -> bool:
        if not await self.storage.initialize():
            logger.error("Failed to initialize storage")
            return False
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
        return language if language else "en"

    async def close(self) -> None:
        if self.storage:
            await self.storage.close()


# Global instance
_manager: Optional[LanguageManager] = None


async def get_manager() -> LanguageManager:
    global _manager
    if _manager is None:
        storage_type = os.getenv("STORAGE_TYPE", "local")
        database_url = os.getenv("DATABASE_URL", "")
        _manager = LanguageManager(storage_type=storage_type, database_url=database_url)
        await _manager.initialize()
    return _manager


async def set_language(user_id: Union[str, int], language: str) -> bool:
    manager = await get_manager()
    return await manager.set_language(user_id, language)


async def get_language(user_id: Union[str, int]) -> str:
    manager = await get_manager()
    return await manager.get_language(user_id)