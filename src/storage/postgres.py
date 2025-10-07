import logging
from typing import Optional

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False

from .base import LanguageStorage


logger = logging.getLogger(__name__)


class PostgreSQLStorage(LanguageStorage):
    """PostgreSQL database storage using asyncpg pool."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None

    async def initialize(self) -> bool:
        if not ASYNCPG_AVAILABLE:
            logger.error("asyncpg not installed. Install with: pip install asyncpg")
            return False

        try:
            self.pool = await asyncpg.create_pool(self.database_url, statement_cache_size=0)

            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_languages (
                        user_id TEXT PRIMARY KEY,
                        language TEXT NOT NULL
                    )
                    """
                )

            logger.info("PostgreSQL storage initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL: {e}")
            return False

    async def get(self, user_id: str) -> Optional[str]:
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT language FROM user_languages WHERE user_id = $1",
                    user_id,
                )
                return row["language"] if row else None
        except Exception as e:
            logger.error(f"Failed to get language: {e}")
            return None

    async def set(self, user_id: str, language: str) -> bool:
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO user_languages (user_id, language)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) DO UPDATE SET language = EXCLUDED.language
                    """,
                    user_id,
                    language,
                )
            return True
        except Exception as e:
            logger.error(f"Failed to set language: {e}")
            return False

    async def remove(self, user_id: str) -> bool:
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM user_languages WHERE user_id = $1",
                    user_id,
                )
                return result.split()[-1] != "0"
        except Exception as e:
            logger.error(f"Failed to remove user: {e}")
            return False

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()