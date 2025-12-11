import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BigInteger,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    delete,
    exists,
    func,
    insert,
    select,
    update,
    text as sql_text,
)
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.exc import ArgumentError, SQLAlchemyError

from .base import LanguageStorage, TicketStorage


logger = logging.getLogger(__name__)

# Shared table metadata used by all supported databases
metadata = MetaData()

user_languages = Table(
    "user_languages",
    metadata,
    Column("user_id", String, primary_key=True),
    Column("language", String, nullable=False),
)

scheduled_tasks = Table(
    "scheduled_tasks",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("type", String, nullable=False),
    Column("guild_id", BigInteger),
    Column("channel_id", BigInteger),
    Column("time", String, nullable=False),
    Column("run_at", Float, nullable=False),
    Column("payload", Text),
)

tickets = Table(
    "tickets",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", String, nullable=False),
    Column("issue", Text, nullable=False),
    Column("channel_id", BigInteger),
    Column("status", String, nullable=False, server_default="open"),
    Column("created_at", Float, nullable=False),
    Column("closed_at", Float),
)


class SQLAlchemyStorage(LanguageStorage, TicketStorage):
    DEFAULT_SQLITE_URL = "sqlite:///data/data.db"
    """
    Unified SQLAlchemy-based storage backend supporting SQLite, PostgreSQL,
    and MySQL/MariaDB using a single implementation.
    """

    def __init__(self, database_url: str = ""):
        self.database_url = database_url or self.DEFAULT_SQLITE_URL
        self.engine = None
        self.sessionmaker: Optional[async_sessionmaker] = None

    def _extract_pk(self, result) -> Optional[int]:
        pk = getattr(result, "inserted_primary_key", None)
        if pk and len(pk) > 0 and pk[0] is not None:
            try:
                return int(pk[0])
            except (TypeError, ValueError):
                return None
        return None

    def _session_factory(self) -> async_sessionmaker:
        if not self.sessionmaker:
            logger.error("SQLAlchemy storage not initialized; call initialize() first.")
            raise RuntimeError("SQLAlchemy storage not initialized")
        return self.sessionmaker

    def _build_async_url(self) -> str:
        url = (self.database_url or "").strip() or self.DEFAULT_SQLITE_URL
        try:
            parsed = make_url(url)
        except ArgumentError:
            # Treat plain paths as SQLite files
            safe_path = Path(url).expanduser().resolve()
            parsed = make_url(f"sqlite:///{safe_path}")

        driver = parsed.drivername
        if driver.startswith("sqlite"):
            db_path = parsed.database
            if db_path and db_path not in (":memory:", ""):
                resolved_path = Path(db_path).expanduser().resolve()
                resolved_path.parent.mkdir(parents=True, exist_ok=True)
                parsed = parsed.set(database=str(resolved_path))
            parsed = parsed.set(drivername="sqlite+aiosqlite")
        elif driver in ("postgres", "postgresql"):
            parsed = parsed.set(drivername="postgresql+asyncpg")
        elif driver.startswith("postgresql+") and "asyncpg" not in driver:
            parsed = parsed.set(drivername="postgresql+asyncpg")
        elif driver in ("mysql", "mariadb"):
            parsed = parsed.set(drivername="mysql+aiomysql")
        elif driver.startswith("mysql+") and "aiomysql" not in driver:
            parsed = parsed.set(drivername="mysql+aiomysql")

        return str(parsed)

    async def initialize(self) -> bool:
        try:
            async_url = self._build_async_url()
            self.engine = create_async_engine(async_url, future=True)
            self.sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)

            async with self.engine.begin() as conn:
                try:
                    await conn.run_sync(metadata.create_all)
                except SQLAlchemyError as e:
                    logger.error(f"Failed to create database schema: {e}")
                    raise

            try:
                safe_url = make_url(async_url).render_as_string(hide_password=True)
            except ArgumentError:
                safe_url = "database URL (hidden)"
            logger.info(f"SQLAlchemy storage initialized using {safe_url}")
            return True
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemy initialization failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error initializing SQLAlchemy storage: {e}")
            return False

    async def get(self, user_id: str) -> Optional[str]:
        try:
            session_factory = self._session_factory()
            async with session_factory() as session:
                result = await session.execute(
                    select(user_languages.c.language).where(user_languages.c.user_id == user_id)
                )
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to fetch language for {user_id}: {e}")
            return None

    async def set(self, user_id: str, language: str) -> bool:
        try:
            session_factory = self._session_factory()
            async with session_factory() as session:
                exists_stmt = select(
                    exists().where(user_languages.c.user_id == user_id)
                )
                if await session.scalar(exists_stmt):
                    await session.execute(
                        update(user_languages)
                        .where(user_languages.c.user_id == user_id)
                        .values(language=language)
                    )
                else:
                    await session.execute(
                        insert(user_languages).values(user_id=user_id, language=language)
                    )
                await session.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to set language for {user_id}: {e}")
            return False

    async def remove(self, user_id: str) -> bool:
        try:
            session_factory = self._session_factory()
            async with session_factory() as session:
                result = await session.execute(
                    delete(user_languages).where(user_languages.c.user_id == user_id)
                )
                await session.commit()
                return (result.rowcount or 0) > 0
        except Exception as e:
            logger.error(f"Failed to remove language for {user_id}: {e}")
            return False

    async def close(self) -> None:
        if self.engine:
            await self.engine.dispose()

    # Scheduler task methods
    async def add_scheduled_task(self, task: Dict[str, Any]) -> Optional[int]:
        try:
            session_factory = self._session_factory()
            async with session_factory() as session:
                result = await session.execute(
                    insert(scheduled_tasks).values(
                        type=task.get("type"),
                        guild_id=task.get("guild_id"),
                        channel_id=task.get("channel_id"),
                        time=task.get("time"),
                        run_at=task.get("run_at"),
                        payload=json.dumps(task.get("payload", {})),
                    )
                )
                await session.commit()
                return self._extract_pk(result)
        except Exception as e:
            logger.error(f"Failed to add scheduled task: {e}")
            return None

    async def remove_scheduled_task(self, task_id: int) -> None:
        if task_id is None:
            return
        try:
            session_factory = self._session_factory()
            async with session_factory() as session:
                await session.execute(
                    delete(scheduled_tasks).where(scheduled_tasks.c.id == task_id)
                )
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to remove scheduled task {task_id}: {e}")

    async def get_all_scheduled_tasks(self) -> List[Dict[str, Any]]:
        tasks: List[Dict[str, Any]] = []
        try:
            session_factory = self._session_factory()
            async with session_factory() as session:
                result = await session.execute(select(scheduled_tasks))
                for row in result.mappings():
                    try:
                        payload_data = json.loads(row.get("payload") or "{}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid payload for scheduled task {row.get('id')}: {e}")
                        payload_data = {}
                    else:
                        if not isinstance(payload_data, dict):
                            logger.warning(
                                f"Unexpected payload type for scheduled task {row.get('id')}: {type(payload_data)}"
                            )
                            payload_data = {}
                    tasks.append(
                        {
                            "id": row.get("id"),
                            "type": row.get("type"),
                            "guild_id": row.get("guild_id"),
                            "channel_id": row.get("channel_id"),
                            "time": row.get("time"),
                            "run_at": row.get("run_at"),
                            "payload": payload_data,
                        }
                    )
        except Exception as e:
            logger.error(f"Failed to fetch scheduled tasks: {e}")
        return tasks

    # Ticket methods
    async def create_ticket(self, user_id: str, issue: str) -> Optional[int]:
        try:
            session_factory = self._session_factory()
            async with session_factory() as session:
                result = await session.execute(
                    insert(tickets).values(
                        user_id=user_id, issue=issue, created_at=time.time()
                    )
                )
                await session.commit()
                return self._extract_pk(result)
        except Exception as e:
            logger.error(f"Failed to create ticket: {e}")
            return None

    async def get_ticket(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        try:
            session_factory = self._session_factory()
            async with session_factory() as session:
                result = await session.execute(
                    select(tickets).where(tickets.c.id == ticket_id)
                )
                row = result.mappings().first()
                if not row:
                    return None
                return dict(row)
        except Exception as e:
            logger.error(f"Failed to fetch ticket {ticket_id}: {e}")
            return None

    async def get_ticket_by_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        try:
            session_factory = self._session_factory()
            async with session_factory() as session:
                result = await session.execute(
                    select(tickets).where(tickets.c.channel_id == channel_id)
                )
                row = result.mappings().first()
                if not row:
                    return None
                return dict(row)
        except Exception as e:
            logger.error(f"Failed to fetch ticket for channel {channel_id}: {e}")
            return None

    async def ticket_count(self, user_id: str) -> int:
        try:
            session_factory = self._session_factory()
            async with session_factory() as session:
                result = await session.execute(
                    select(func.count()).select_from(tickets).where(
                        tickets.c.user_id == user_id, tickets.c.status == "open"
                    )
                )
                return int(result.scalar() or 0)
        except Exception as e:
            logger.error(f"Failed to count tickets for {user_id}: {e}")
            return 0

    async def close_ticket(self, ticket_id: int) -> bool:
        try:
            session_factory = self._session_factory()
            async with session_factory() as session:
                result = await session.execute(
                    update(tickets)
                    .where(tickets.c.id == ticket_id, tickets.c.status == "open")
                    .values(status="closed", closed_at=time.time())
                )
                await session.commit()
                return (result.rowcount or 0) > 0
        except Exception as e:
            logger.error(f"Failed to close ticket {ticket_id}: {e}")
            return False

    async def reopen_ticket(self, ticket_id: int) -> bool:
        try:
            session_factory = self._session_factory()
            async with session_factory() as session:
                result = await session.execute(
                    update(tickets)
                    .where(tickets.c.id == ticket_id, tickets.c.status == "closed")
                    .values(status="open", closed_at=None)
                )
                await session.commit()
                return (result.rowcount or 0) > 0
        except Exception as e:
            logger.error(f"Failed to reopen ticket {ticket_id}: {e}")
            return False

    async def update_ticket_channel(self, ticket_id: int, channel_id: int) -> bool:
        try:
            session_factory = self._session_factory()
            async with session_factory() as session:
                await session.execute(
                    update(tickets)
                    .where(tickets.c.id == ticket_id)
                    .values(channel_id=channel_id)
                )
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to update channel for ticket {ticket_id}: {e}")
            return False

    async def delete_ticket(self, ticket_id: int) -> bool:
        try:
            session_factory = self._session_factory()
            async with session_factory() as session:
                result = await session.execute(
                    delete(tickets).where(tickets.c.id == ticket_id)
                )
                await session.commit()
                return (result.rowcount or 0) > 0
        except Exception as e:
            logger.error(f"Failed to delete ticket {ticket_id}: {e}")
            return False
