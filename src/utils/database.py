"""
Simple language preference storage for Discord bot.
Stores only non-English languages to save space.
"""

import json
import os
import asyncio
import aiosqlite
from typing import Dict, Optional, Union
from pathlib import Path
import logging

# Database imports (install with: pip install asyncpg aiomysql)
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False

try:
    import aiomysql
    AIOMYSQL_AVAILABLE = True
except ImportError:
    AIOMYSQL_AVAILABLE = False

logger = logging.getLogger(__name__)


class LocalFileStorage:
    """Local JSON file storage."""
    
    def __init__(self, file_path: str = "data/user_languages.json"):
        self.file_path = Path(file_path)
        self.data: Dict[str, str] = {}
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> bool:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            if self.file_path.exists():
                async with self._lock:
                    with open(self.file_path, 'r', encoding='utf-8') as f:
                        self.data = json.load(f)
            else:
                self.data = {}
                await self._save()
            
            logger.info(f"Local storage initialized: {self.file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize local storage: {e}")
            return False
    
    async def _save(self) -> None:
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    async def get(self, user_id: str) -> Optional[str]:
        async with self._lock:
            return self.data.get(user_id)
    
    async def set(self, user_id: str, language: str) -> bool:
        try:
            async with self._lock:
                self.data[user_id] = language
                await self._save()
            return True
        except Exception as e:
            logger.error(f"Failed to set language: {e}")
            return False
    
    async def remove(self, user_id: str) -> bool:
        try:
            async with self._lock:
                if user_id in self.data:
                    del self.data[user_id]
                    await self._save()
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to remove user: {e}")
            return False
    
    async def close(self) -> None:
        pass


class SQLiteStorage:
    """SQLite database storage."""
    
    def __init__(self, db_path: str = "data/user_languages.db"):
        self.db_path = db_path
    
    async def initialize(self) -> bool:
        try:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_languages (
                        user_id TEXT PRIMARY KEY,
                        language TEXT NOT NULL
                    )
                """)
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
                    (user_id,)
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
                    (user_id, language)
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
                    (user_id,)
                )
                await db.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to remove user: {e}")
            return False
    
    async def close(self) -> None:
        pass


class PostgreSQLStorage:
    """PostgreSQL database storage."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
    
    async def initialize(self) -> bool:
        if not ASYNCPG_AVAILABLE:
            logger.error("asyncpg not installed. Install with: pip install asyncpg")
            return False
        
        try:
            self.pool = await asyncpg.create_pool(self.database_url)
            
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_languages (
                        user_id TEXT PRIMARY KEY,
                        language TEXT NOT NULL
                    )
                """)
            
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
                    user_id
                )
                return row['language'] if row else None
        except Exception as e:
            logger.error(f"Failed to get language: {e}")
            return None
    
    async def set(self, user_id: str, language: str) -> bool:
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO user_languages (user_id, language)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) DO UPDATE SET language = EXCLUDED.language
                """, user_id, language)
            return True
        except Exception as e:
            logger.error(f"Failed to set language: {e}")
            return False
    
    async def remove(self, user_id: str) -> bool:
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM user_languages WHERE user_id = $1",
                    user_id
                )
                return result.split()[-1] != '0'
        except Exception as e:
            logger.error(f"Failed to remove user: {e}")
            return False
    
    async def close(self) -> None:
        if self.pool:
            await self.pool.close()


class MySQLStorage:
    """MySQL/MariaDB database storage."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
        self._parse_url()
    
    def _parse_url(self):
        if self.database_url.startswith('mysql://'):
            url = self.database_url[8:]
            if '@' in url:
                auth, host_db = url.split('@', 1)
                self.user, self.password = auth.split(':', 1) if ':' in auth else (auth, '')
            else:
                self.user, self.password = 'root', ''
                host_db = url
            
            if '/' in host_db:
                host_port, self.database = host_db.split('/', 1)
            else:
                host_port, self.database = host_db, 'discord_bot'
            
            if ':' in host_port:
                self.host, port = host_port.split(':', 1)
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
                autocommit=True
            )
            
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        CREATE TABLE IF NOT EXISTS user_languages (
                            user_id VARCHAR(255) PRIMARY KEY,
                            language VARCHAR(10) NOT NULL
                        )
                    """)
            
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
                        (user_id,)
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
                    await cursor.execute("""
                        INSERT INTO user_languages (user_id, language)
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE language = VALUES(language)
                    """, (user_id, language))
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
                        (user_id,)
                    )
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to remove user: {e}")
            return False
    
    async def close(self) -> None:
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()


class LanguageManager:
    """Simple language preference manager."""
    
    def __init__(self, 
                 storage_type: str = "local",
                 database_url: str = ""):
        
        self.storage_type = storage_type.lower()
        self.database_url = database_url
        self.storage = None
        
        # Initialize storage
        self._init_storage()
    
    def _init_storage(self) -> None:
        """Initialize storage backend."""
        if self.storage_type == "local":
            self.storage = LocalFileStorage()
        elif self.storage_type == "sqlite":
            self.storage = SQLiteStorage()
        elif self.storage_type == "postgresql":
            if not self.database_url:
                logger.error("PostgreSQL selected but no database_url provided")
                self.storage = LocalFileStorage()
            else:
                self.storage = PostgreSQLStorage(self.database_url)
        elif self.storage_type == "mysql":
            if not self.database_url:
                logger.error("MySQL selected but no database_url provided")
                self.storage = LocalFileStorage()
            else:
                self.storage = MySQLStorage(self.database_url)
        else:
            # Auto-detect from URL
            if self.database_url:
                url_lower = self.database_url.lower()
                if url_lower.startswith(('postgresql://', 'postgres://')):
                    self.storage = PostgreSQLStorage(self.database_url)
                elif url_lower.startswith('mysql://'):
                    self.storage = MySQLStorage(self.database_url)
                elif url_lower.startswith('sqlite://') or url_lower.endswith('.db'):
                    self.storage = SQLiteStorage()
                else:
                    logger.error(f"Unknown database URL format")
                    self.storage = LocalFileStorage()
            else:
                self.storage = LocalFileStorage()
    
    async def initialize(self) -> bool:
        """Initialize the manager."""
        if not await self.storage.initialize():
            logger.error("Failed to initialize storage")
            return False
        
        logger.info("Language manager initialized")
        return True
    
    def _is_english(self, language: str) -> bool:
        """Check if language is English."""
        return language.lower() in ['en', 'en_us', 'en_gb', 'en-us', 'en-gb']
    
    async def set_language(self, user_id: Union[str, int], language: str) -> bool:
        """
        Set user language.
        If English - removes entry (saves space, falls back to default).
        If other language - saves to storage.
        """
        user_id = str(user_id)
        
        # English = remove entry (fallback to default)
        if self._is_english(language):
            await self.storage.remove(user_id)
            return True
        
        # Other language = save
        return await self.storage.set(user_id, language)
    
    async def get_language(self, user_id: Union[str, int]) -> str:
        """
        Get user language.
        Returns saved language or "en" if not found (default fallback).
        """
        user_id = str(user_id)
        language = await self.storage.get(user_id)
        return language if language else "en"
    
    async def close(self) -> None:
        """Close storage connections."""
        if self.storage:
            await self.storage.close()


# Global instance
_manager: Optional[LanguageManager] = None


async def get_manager() -> LanguageManager:
    """Get or create global manager instance."""
    global _manager
    
    if _manager is None:
        storage_type = os.getenv('STORAGE_TYPE', 'local')
        database_url = os.getenv('DATABASE_URL', '')
        
        _manager = LanguageManager(
            storage_type=storage_type,
            database_url=database_url
        )
        await _manager.initialize()
    
    return _manager


# Simple convenience functions
async def set_language(user_id: Union[str, int], language: str) -> bool:
    """Set user language. If 'en' - removes entry to save space."""
    manager = await get_manager()
    return await manager.set_language(user_id, language)


async def get_language(user_id: Union[str, int]) -> str:
    """Get user language. Returns 'en' if not found."""
    manager = await get_manager()
    return await manager.get_language(user_id)