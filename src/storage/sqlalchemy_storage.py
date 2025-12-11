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
    String,
    Text,
    delete,
    func,
    select,
    update,
)
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .base import LanguageStorage


logger = logging.getLogger(__name__)
DEFAULT_SQLITE_URL = "sqlite+aiosqlite:///data/data.db"


class Base(DeclarativeBase):
    pass


class UserLanguage(Base):
    __tablename__ = "user_languages"

    user_id = Column(String(255), primary_key=True)
    language = Column(String(32), nullable=False)


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(50), nullable=False)
    guild_id = Column(BigInteger)
    channel_id = Column(BigInteger)
    time = Column(String(10), nullable=False)
    run_at = Column(Float, nullable=False)
    payload = Column(Text)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False)
    issue = Column(Text, nullable=False)
    channel_id = Column(BigInteger)
    status = Column(String(20), default="open", nullable=False)
    created_at = Column(Float, nullable=False)
    closed_at = Column(Float)


def normalize_database_url(database_url: str) -> str:
    """Ensure the provided URL uses an async-capable SQLAlchemy driver."""
    url = (database_url or "").strip()
    if not url:
        return DEFAULT_SQLITE_URL

    # Handle raw sqlite file paths (e.g., data/db.sqlite)
    if "://" not in url and url.endswith(".db"):
        return f"sqlite+aiosqlite:///{url}"

    try:
        parsed = make_url(url)
    except Exception:
        # Fall back to default sqlite when parsing fails
        return DEFAULT_SQLITE_URL

    driver = parsed.drivername.lower()
    if driver.startswith("postgres"):
        parsed = parsed.set(drivername="postgresql+asyncpg")
    elif driver.startswith("mysql") or driver.startswith("mariadb"):
        parsed = parsed.set(drivername="mysql+aiomysql")
    elif driver.startswith("sqlite"):
        parsed = parsed.set(drivername="sqlite+aiosqlite")

    # Ensure sqlite has a database path
    if parsed.drivername.startswith("sqlite") and not parsed.database:
        parsed = parsed.set(database="data/data.db")

    return str(parsed)


class SQLAlchemyStorage(LanguageStorage):
    """Unified storage backend powered by SQLAlchemy for all supported databases."""

    def __init__(self, database_url: str = ""):
        self.database_url = normalize_database_url(database_url)
        self.engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None
        self._initialized = False

    def _ensure_engine(self) -> None:
        if not self.engine:
            self.engine = create_async_engine(self.database_url, future=True)
            self._session_factory = async_sessionmaker(
                self.engine, expire_on_commit=False
            )

    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            ok = await self.initialize()
            if not ok:
                raise RuntimeError("SQLAlchemy storage failed to initialize")

    async def initialize(self) -> bool:
        if self._initialized:
            return True
        try:
            self._ensure_engine()
            parsed = make_url(self.database_url)
            if parsed.drivername.startswith("sqlite") and parsed.database not in (
                None,
                "",
                ":memory:",
            ):
                Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)

            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            logger.info("SQLAlchemy storage initialized using %s", self.database_url)
            self._initialized = True
            return True
        except Exception as e:
            logger.error("Failed to initialize SQLAlchemy storage: %s", e)
            return False

    async def get(self, user_id: str) -> Optional[str]:
        try:
            await self._ensure_initialized()
            async with self._session_factory() as session:
                result = await session.execute(
                    select(UserLanguage.language).where(
                        UserLanguage.user_id == str(user_id)
                    )
                )
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error("Failed to get language for %s: %s", user_id, e)
            return None

    async def set(self, user_id: str, language: str) -> bool:
        try:
            await self._ensure_initialized()
            async with self._session_factory() as session:
                await session.merge(
                    UserLanguage(user_id=str(user_id), language=language)
                )
                await session.commit()
            return True
        except Exception as e:
            logger.error("Failed to set language for %s: %s", user_id, e)
            return False

    async def remove(self, user_id: str) -> bool:
        try:
            await self._ensure_initialized()
            async with self._session_factory() as session:
                result = await session.execute(
                    delete(UserLanguage).where(UserLanguage.user_id == str(user_id))
                )
                await session.commit()
                return (result.rowcount or 0) > 0
        except Exception as e:
            logger.error("Failed to remove user %s: %s", user_id, e)
            return False

    async def close(self) -> None:
        if self.engine:
            await self.engine.dispose()

    # Scheduler task methods
    async def add_scheduled_task(self, task: Dict[str, Any]) -> Optional[int]:
        try:
            await self._ensure_initialized()
            async with self._session_factory() as session:
                payload = json.dumps(task.get("payload", {}))
                record = ScheduledTask(
                    type=task.get("type"),
                    guild_id=task.get("guild_id"),
                    channel_id=task.get("channel_id"),
                    time=task.get("time"),
                    run_at=float(task.get("run_at", 0)),
                    payload=payload,
                )
                session.add(record)
                await session.commit()
                await session.refresh(record)
                return record.id
        except Exception as e:
            logger.error("Failed to add scheduled task: %s", e)
            return None

    async def remove_scheduled_task(self, task_id: int) -> None:
        if task_id is None:
            return
        try:
            await self._ensure_initialized()
            async with self._session_factory() as session:
                await session.execute(
                    delete(ScheduledTask).where(ScheduledTask.id == int(task_id))
                )
                await session.commit()
        except Exception as e:
            logger.error("Failed to remove scheduled task %s: %s", task_id, e)

    async def get_all_scheduled_tasks(self) -> List[Dict[str, Any]]:
        tasks: List[Dict[str, Any]] = []
        try:
            await self._ensure_initialized()
            async with self._session_factory() as session:
                result = await session.execute(select(ScheduledTask))
                for row in result.scalars():
                    tasks.append(
                        {
                            "id": row.id,
                            "type": row.type,
                            "guild_id": row.guild_id,
                            "channel_id": row.channel_id,
                            "time": row.time,
                            "run_at": row.run_at,
                            "payload": json.loads(row.payload or "{}"),
                        }
                    )
        except Exception as e:
            logger.error("Failed to fetch scheduled tasks: %s", e)
        return tasks

    # Ticket methods
    async def create_ticket(self, user_id: str, issue: str) -> Optional[int]:
        try:
            await self._ensure_initialized()
            async with self._session_factory() as session:
                ticket = Ticket(
                    user_id=user_id,
                    issue=issue,
                    status="open",
                    created_at=time.time(),
                )
                session.add(ticket)
                await session.commit()
                await session.refresh(ticket)
                return ticket.id
        except Exception as e:
            logger.error("Failed to create ticket: %s", e)
            return None

    async def get_ticket(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        try:
            await self._ensure_initialized()
            async with self._session_factory() as session:
                result = await session.execute(
                    select(Ticket).where(Ticket.id == int(ticket_id))
                )
                ticket = result.scalar_one_or_none()
                return self._ticket_to_dict(ticket) if ticket else None
        except Exception as e:
            logger.error("Failed to fetch ticket %s: %s", ticket_id, e)
            return None

    async def get_ticket_by_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        try:
            await self._ensure_initialized()
            async with self._session_factory() as session:
                result = await session.execute(
                    select(Ticket).where(Ticket.channel_id == int(channel_id))
                )
                ticket = result.scalar_one_or_none()
                return self._ticket_to_dict(ticket) if ticket else None
        except Exception as e:
            logger.error("Failed to fetch ticket by channel %s: %s", channel_id, e)
            return None

    async def ticket_count(self, user_id: str) -> int:
        try:
            await self._ensure_initialized()
            async with self._session_factory() as session:
                result = await session.execute(
                    select(func.count()).select_from(Ticket).where(
                        Ticket.user_id == str(user_id), Ticket.status == "open"
                    )
                )
                return int(result.scalar_one() or 0)
        except Exception as e:
            logger.error("Failed to count tickets for %s: %s", user_id, e)
            return 0

    async def close_ticket(self, ticket_id: int) -> bool:
        try:
            await self._ensure_initialized()
            async with self._session_factory() as session:
                result = await session.execute(
                    update(Ticket)
                    .where(Ticket.id == int(ticket_id), Ticket.status == "open")
                    .values(status="closed", closed_at=time.time())
                )
                await session.commit()
                return (result.rowcount or 0) > 0
        except Exception as e:
            logger.error("Failed to close ticket %s: %s", ticket_id, e)
            return False

    async def reopen_ticket(self, ticket_id: int) -> bool:
        try:
            await self._ensure_initialized()
            async with self._session_factory() as session:
                result = await session.execute(
                    update(Ticket)
                    .where(Ticket.id == int(ticket_id), Ticket.status == "closed")
                    .values(status="open", closed_at=None)
                )
                await session.commit()
                return (result.rowcount or 0) > 0
        except Exception as e:
            logger.error("Failed to reopen ticket %s: %s", ticket_id, e)
            return False

    async def update_ticket_channel(self, ticket_id: int, channel_id: int) -> bool:
        try:
            await self._ensure_initialized()
            async with self._session_factory() as session:
                await session.execute(
                    update(Ticket)
                    .where(Ticket.id == int(ticket_id))
                    .values(channel_id=int(channel_id))
                )
                await session.commit()
                return True
        except Exception as e:
            logger.error("Failed to update channel for ticket %s: %s", ticket_id, e)
            return False

    async def delete_ticket(self, ticket_id: int) -> bool:
        try:
            await self._ensure_initialized()
            async with self._session_factory() as session:
                result = await session.execute(
                    delete(Ticket).where(Ticket.id == int(ticket_id))
                )
                await session.commit()
                return (result.rowcount or 0) > 0
        except Exception as e:
            logger.error("Failed to delete ticket %s: %s", ticket_id, e)
            return False

    @staticmethod
    def _ticket_to_dict(ticket: Ticket) -> Dict[str, Any]:
        return {
            "id": ticket.id,
            "user_id": ticket.user_id,
            "issue": ticket.issue,
            "channel_id": ticket.channel_id,
            "status": ticket.status,
            "created_at": ticket.created_at,
            "closed_at": ticket.closed_at,
        }
