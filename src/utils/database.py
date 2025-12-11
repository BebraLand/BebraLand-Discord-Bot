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

    def __init__(self, db_type: str = "", database_url: str = ""):
        self.db_type = db_type.lower()
        self.database_url = database_url
        self.storage: LanguageStorage = create_storage(self.db_type, self.database_url)

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
        database_url = os.getenv("DATABASE_URL", "").strip()
        db_type = os.getenv("DB_TYPE", "").lower().strip()

        # If a full DATABASE_URL wasn't provided, construct it from individual
        # environment variables. This is useful in deployment environments that
        # supply secrets separately (DB_USER, DB_PASSWORD, etc.).
        if not database_url:
            db_user = os.getenv("DB_USER", "").strip()
            db_password = os.getenv("DB_PASSWORD", "").strip()
            db_host = os.getenv("DB_HOST", "").strip()
            db_port = os.getenv("DB_PORT", "").strip()
            db_name = os.getenv("DB_NAME", "").strip()
            db_path = os.getenv("DB_PATH", "").strip()

            # Build URL based on DB_TYPE or infer from available variables
            if db_type in ("sqlite",) or (not db_type and db_path):
                if db_path:
                    database_url = f"sqlite:///{db_path}"
            elif db_type in ("postgresql", "postgres") or (not db_type and db_name and db_host):
                if db_user and db_name and db_host:
                    auth = f"{db_user}:{db_password}@" if db_password else f"{db_user}@"
                    port = f":{db_port}" if db_port else ""
                    database_url = f"postgresql://{auth}{db_host}{port}/{db_name}"
            elif db_type in ("mysql", "mariadb"):
                if db_user and db_name and db_host:
                    auth = f"{db_user}:{db_password}@" if db_password else f"{db_user}@"
                    port = f":{db_port}" if db_port else ""
                    database_url = f"mysql://{auth}{db_host}{port}/{db_name}"

        _manager = LanguageManager(db_type=db_type, database_url=database_url)
        await _manager.initialize()
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