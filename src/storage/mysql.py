import json
import logging
from typing import Optional, List, Dict, Any
import urllib.parse

try:
    import aiomysql
    AIOMYSQL_AVAILABLE = True
except ImportError:
    AIOMYSQL_AVAILABLE = False

from .base import LanguageStorage


logger = logging.getLogger(__name__)


class MySQLStorage(LanguageStorage):
    """MySQL/MariaDB database storage using aiomysql pool."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
        self._parse_url()

    def _parse_url(self):
        # Use a more robust parsing strategy that tolerates '@' in the password
        # by splitting at the last '@' and percent-decoding credentials.
        if self.database_url.startswith("mysql://"):
            url = self.database_url[8:]
            if "@" in url:
                # Split at the last '@' so any '@' characters in the password
                # (or username) don't confuse the host separator.
                auth, host_db = url.rsplit("@", 1)
                if ":" in auth:
                    self.user, self.password = auth.split(":", 1)
                else:
                    self.user, self.password = auth, ""
                # Percent-decode credentials to allow safe encoding in env vars
                self.user = urllib.parse.unquote(self.user)
                self.password = urllib.parse.unquote(self.password)
            else:
                self.user, self.password = "root", ""
                host_db = url

            if "/" in host_db:
                host_port, self.database = host_db.split("/", 1)
            else:
                host_port, self.database = host_db, "discord_bot"

            if ":" in host_port:
                self.host, port = host_port.split(":", 1)
                try:
                    self.port = int(port)
                except ValueError:
                    self.port = 3306
            else:
                self.host, self.port = host_port, 3306

    async def initialize(self) -> bool:
        if not AIOMYSQL_AVAILABLE:
            logger.error("aiomysql not installed. Install with: pip install aiomysql")
            return False

        try:
            self.pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.database,
                autocommit=True,
            )

            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # Suppress warnings for CREATE TABLE IF NOT EXISTS
                    await cursor.execute("SET sql_notes = 0")
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS user_languages (
                            user_id VARCHAR(255) PRIMARY KEY,
                            language VARCHAR(10) NOT NULL
                        )
                        """
                    )
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS scheduled_tasks (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            type VARCHAR(50) NOT NULL,
                            guild_id BIGINT,
                            channel_id BIGINT,
                            time VARCHAR(10) NOT NULL,
                            run_at DOUBLE NOT NULL,
                            payload TEXT
                        )
                        """
                    )
                    await cursor.execute("SET sql_notes = 1")

            logger.info("MySQL storage initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize MySQL: {e}")
            return False

    async def get(self, user_id: str) -> Optional[str]:
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT language FROM user_languages WHERE user_id = %s",
                        (user_id,),
                    )
                    row = await cursor.fetchone()
                    return row[0] if row else None
        except Exception as e:
            logger.error(f"Failed to get language: {e}")
            return None

    async def set(self, user_id: str, language: str) -> bool:
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO user_languages (user_id, language)
                        VALUES (%s, %s) AS new_values
                        ON DUPLICATE KEY UPDATE language = new_values.language
                        """,
                        (user_id, language),
                    )
            return True
        except Exception as e:
            logger.error(f"Failed to set language: {e}")
            return False

    async def remove(self, user_id: str) -> bool:
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "DELETE FROM user_languages WHERE user_id = %s",
                        (user_id,),
                    )
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to remove user: {e}")
            return False

    async def close(self) -> None:
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()

    # Scheduler task methods

    async def add_scheduled_task(self, task: Dict[str, Any]) -> Optional[int]:
        """Add a scheduled task and return its ID."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO scheduled_tasks (type, guild_id, channel_id, time, run_at, payload)
                        VALUES (%s, %s, %s, %s, %s, %s)
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
                    return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to add scheduled task: {e}")
            return None

    async def remove_scheduled_task(self, task_id: int) -> None:
        """Remove a scheduled task by ID."""
        if task_id is None:
            return
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("DELETE FROM scheduled_tasks WHERE id = %s", (task_id,))
        except Exception as e:
            logger.error(f"Failed to remove scheduled task {task_id}: {e}")

    async def get_all_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """Get all scheduled tasks."""
        tasks = []
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute("SELECT * FROM scheduled_tasks")
                    rows = await cursor.fetchall()
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