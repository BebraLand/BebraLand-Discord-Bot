import logging
from typing import Optional

import aiosqlite

from .base import LanguageStorage


logger = logging.getLogger(__name__)


class SQLiteStorage(LanguageStorage):
    """SQLite database storage.

    Defaults to `data/data.db`. The storage creates a `user_languages` table
    inside the SQLite file to store preferences.
    """

    def __init__(self, db_path: str = "data/data.db"):
        self.db_path = db_path

    async def initialize(self) -> bool:
        try:
            # Ensure directory exists
            import pathlib
            pathlib.Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_languages (
                        user_id TEXT PRIMARY KEY,
                        language TEXT NOT NULL
                    )
                    """
                )
                await db.commit()

            logger.info(f"SQLite storage initialized: {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize SQLite: {e}")
            return False

    async def get(self, user_id: str) -> Optional[str]:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT language FROM user_languages WHERE user_id = ?",
                    (user_id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else None
        except Exception as e:
            logger.error(f"Failed to get language: {e}")
            return None

    async def set(self, user_id: str, language: str) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO user_languages (user_id, language) VALUES (?, ?)",
                    (user_id, language),
                )
                await db.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to set language: {e}")
            return False

    async def remove(self, user_id: str) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "DELETE FROM user_languages WHERE user_id = ?",
                    (user_id,),
                )
                await db.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to remove user: {e}")
            return False

    async def close(self) -> None:
        pass