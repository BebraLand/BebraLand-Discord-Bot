import json
import logging
from typing import Optional, List, Dict, Any

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
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS scheduled_tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        type TEXT NOT NULL,
                        guild_id INTEGER,
                        channel_id INTEGER,
                        time TEXT NOT NULL,
                        run_at REAL NOT NULL,
                        payload TEXT
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

    # Scheduler task methods

    async def add_scheduled_task(self, task: Dict[str, Any]) -> Optional[int]:
        """Add a scheduled task and return its ID."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    """
                    INSERT INTO scheduled_tasks (type, guild_id, channel_id, time, run_at, payload)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task.get("type"),
                        task.get("guild_id"),
                        task.get("channel_id"),
                        task.get("time"),
                        task.get("run_at"),
                        json.dumps(task.get("payload", {}))
                    )
                )
                await db.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to add scheduled task: {e}")
            return None

    async def remove_scheduled_task(self, task_id: int) -> None:
        """Remove a scheduled task by ID."""
        if task_id is None:
            return
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to remove scheduled task {task_id}: {e}")

    async def get_all_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """Get all scheduled tasks."""
        tasks = []
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM scheduled_tasks") as cursor:
                    async for row in cursor:
                        tasks.append({
                            "id": row["id"],
                            "type": row["type"],
                            "guild_id": row["guild_id"],
                            "channel_id": row["channel_id"],
                            "time": row["time"],
                            "run_at": row["run_at"],
                            "payload": json.loads(row["payload"] or "{}")
                        })
        except Exception as e:
            logger.error(f"Failed to fetch scheduled tasks: {e}")
        return tasks