import json
import logging
from typing import Optional, List, Dict, Any

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
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS scheduled_tasks (
                        id SERIAL PRIMARY KEY,
                        type TEXT NOT NULL,
                        guild_id BIGINT,
                        channel_id BIGINT,
                        time TEXT NOT NULL,
                        run_at DOUBLE PRECISION NOT NULL,
                        payload TEXT
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

    # Scheduler task methods

    async def add_scheduled_task(self, task: Dict[str, Any]) -> Optional[int]:
        """Add a scheduled task and return its ID."""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO scheduled_tasks (type, guild_id, channel_id, time, run_at, payload)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    task.get("type"),
                    task.get("guild_id"),
                    task.get("channel_id"),
                    task.get("time"),
                    task.get("run_at"),
                    json.dumps(task.get("payload", {}))
                )
                return row["id"] if row else None
        except Exception as e:
            logger.error(f"Failed to add scheduled task: {e}")
            return None

    async def remove_scheduled_task(self, task_id: int) -> None:
        """Remove a scheduled task by ID."""
        if task_id is None:
            return
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("DELETE FROM scheduled_tasks WHERE id = $1", task_id)
        except Exception as e:
            logger.error(f"Failed to remove scheduled task {task_id}: {e}")

    async def get_all_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """Get all scheduled tasks."""
        tasks = []
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM scheduled_tasks")
                for row in rows:
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