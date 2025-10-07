import logging
from typing import Optional

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
        if self.database_url.startswith("mysql://"):
            url = self.database_url[8:]
            if "@" in url:
                auth, host_db = url.split("@", 1)
                self.user, self.password = auth.split(":", 1) if ":" in auth else (auth, "")
            else:
                self.user, self.password = "root", ""
                host_db = url

            if "/" in host_db:
                host_port, self.database = host_db.split("/", 1)
            else:
                host_port, self.database = host_db, "discord_bot"

            if ":" in host_port:
                self.host, port = host_port.split(":", 1)
                self.port = int(port)
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
                    await cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS user_languages (
                            user_id VARCHAR(255) PRIMARY KEY,
                            language VARCHAR(10) NOT NULL
                        )
                        """
                    )

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
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE language = VALUES(language)
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