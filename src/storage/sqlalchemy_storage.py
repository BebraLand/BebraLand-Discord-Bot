"""
Unified SQLAlchemy-based storage implementation.
Supports SQLite, PostgreSQL, MySQL, and MariaDB.
"""
import json
import logging
import time
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, quote_plus

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, delete, update
from sqlalchemy.exc import SQLAlchemyError

from .models import Base, UserLanguage, ScheduledTask, Ticket
from .base import LanguageStorage

logger = logging.getLogger(__name__)


class SQLAlchemyStorage(LanguageStorage):
    """
    Unified storage using SQLAlchemy ORM.
    Supports SQLite, PostgreSQL, MySQL, and MariaDB.
    """

    def __init__(self, database_url: str):
        """
        Initialize storage with a database URL.
        
        Args:
            database_url: SQLAlchemy database URL
                - SQLite: sqlite+aiosqlite:///data/bot.db
                - PostgreSQL: postgresql+asyncpg://user:pass@host/db
                - MySQL: mysql+aiomysql://user:pass@host/db
                - MariaDB: mysql+aiomysql://user:pass@host/db (same driver as MySQL)
        """
        self.database_url = database_url
        self.engine = None
        self.session_factory = None

    async def initialize(self) -> bool:
        """Initialize database connection and create tables."""
        try:
            # Create async engine
            self.engine = create_async_engine(
                self.database_url,
                echo=False,  # Set to True for SQL debugging
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600,  # Recycle connections after 1 hour
            )

            # Create session factory
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            # Create all tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            logger.info(f"SQLAlchemy storage initialized with {self.database_url.split('://')[0]}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize SQLAlchemy storage: {e}")
            return False

    async def close(self) -> None:
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection closed")

    # ==================== Language Storage Methods ====================

    async def get(self, user_id: str) -> Optional[str]:
        """Get user's language preference."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(UserLanguage).where(UserLanguage.user_id == user_id)
                )
                user_lang = result.scalar_one_or_none()
                return user_lang.language if user_lang else None
        except Exception as e:
            logger.error(f"Failed to get language for user {user_id}: {e}")
            return None

    async def set(self, user_id: str, language: str) -> bool:
        """Set user's language preference."""
        try:
            async with self.session_factory() as session:
                # Check if user already exists
                result = await session.execute(
                    select(UserLanguage).where(UserLanguage.user_id == user_id)
                )
                user_lang = result.scalar_one_or_none()

                if user_lang:
                    # Update existing
                    user_lang.language = language
                else:
                    # Create new
                    user_lang = UserLanguage(user_id=user_id, language=language)
                    session.add(user_lang)

                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to set language for user {user_id}: {e}")
            return False

    async def remove(self, user_id: str) -> bool:
        """Remove user's language preference."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    delete(UserLanguage).where(UserLanguage.user_id == user_id)
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to remove language for user {user_id}: {e}")
            return False

    # ==================== Scheduled Task Methods ====================

    async def add_scheduled_task(self, task: Dict[str, Any]) -> Optional[int]:
        """Add a scheduled task and return its ID."""
        try:
            async with self.session_factory() as session:
                scheduled_task = ScheduledTask(
                    type=task.get("type"),
                    guild_id=task.get("guild_id"),
                    channel_id=task.get("channel_id"),
                    time=task.get("time"),
                    run_at=task.get("run_at"),
                    payload=json.dumps(task.get("payload", {}))
                )
                session.add(scheduled_task)
                await session.commit()
                await session.refresh(scheduled_task)
                return scheduled_task.id
        except Exception as e:
            logger.error(f"Failed to add scheduled task: {e}")
            return None

    async def remove_scheduled_task(self, task_id: int) -> None:
        """Remove a scheduled task by ID."""
        if task_id is None:
            return
        try:
            async with self.session_factory() as session:
                await session.execute(
                    delete(ScheduledTask).where(ScheduledTask.id == task_id)
                )
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to remove scheduled task {task_id}: {e}")

    async def get_all_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """Get all scheduled tasks."""
        tasks = []
        try:
            async with self.session_factory() as session:
                result = await session.execute(select(ScheduledTask))
                for task in result.scalars():
                    tasks.append({
                        "id": task.id,
                        "type": task.type,
                        "guild_id": task.guild_id,
                        "channel_id": task.channel_id,
                        "time": task.time,
                        "run_at": task.run_at,
                        "payload": json.loads(task.payload or "{}")
                    })
        except Exception as e:
            logger.error(f"Failed to fetch scheduled tasks: {e}")
        return tasks

    # ==================== Ticket Methods ====================

    async def create_ticket(self, user_id: str, issue: str) -> Optional[int]:
        """Create a new ticket and return its ID."""
        try:
            async with self.session_factory() as session:
                ticket = Ticket(
                    user_id=user_id,
                    issue=issue,
                    created_at=time.time(),
                    status="open"
                )
                session.add(ticket)
                await session.commit()
                await session.refresh(ticket)
                return ticket.id
        except Exception as e:
            logger.error(f"Failed to create ticket: {e}")
            return None

    async def get_ticket(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        """Get a ticket by ID."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Ticket).where(Ticket.id == ticket_id)
                )
                ticket = result.scalar_one_or_none()
                if ticket:
                    return {
                        "id": ticket.id,
                        "user_id": ticket.user_id,
                        "issue": ticket.issue,
                        "channel_id": ticket.channel_id,
                        "status": ticket.status,
                        "created_at": ticket.created_at,
                        "closed_at": ticket.closed_at
                    }
                return None
        except Exception as e:
            logger.error(f"Failed to get ticket {ticket_id}: {e}")
            return None

    async def get_ticket_by_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """Get a ticket by channel ID."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Ticket).where(Ticket.channel_id == channel_id)
                )
                ticket = result.scalar_one_or_none()
                if ticket:
                    return {
                        "id": ticket.id,
                        "user_id": ticket.user_id,
                        "issue": ticket.issue,
                        "channel_id": ticket.channel_id,
                        "status": ticket.status,
                        "created_at": ticket.created_at,
                        "closed_at": ticket.closed_at
                    }
                return None
        except Exception as e:
            logger.error(f"Failed to get ticket by channel {channel_id}: {e}")
            return None

    async def ticket_count(self, user_id: str) -> int:
        """Get the count of open tickets for a user."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Ticket).where(
                        Ticket.user_id == user_id,
                        Ticket.status == "open"
                    )
                )
                return len(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to count tickets for user {user_id}: {e}")
            return 0

    async def close_ticket(self, ticket_id: int) -> bool:
        """Close a ticket."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    update(Ticket)
                    .where(Ticket.id == ticket_id, Ticket.status == "open")
                    .values(status="closed", closed_at=time.time())
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to close ticket {ticket_id}: {e}")
            return False

    async def reopen_ticket(self, ticket_id: int) -> bool:
        """Reopen a closed ticket."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    update(Ticket)
                    .where(Ticket.id == ticket_id, Ticket.status == "closed")
                    .values(status="open", closed_at=None)
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to reopen ticket {ticket_id}: {e}")
            return False

    async def update_ticket_channel(self, ticket_id: int, channel_id: int) -> bool:
        """Update the channel ID for a ticket."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    update(Ticket)
                    .where(Ticket.id == ticket_id)
                    .values(channel_id=channel_id)
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update ticket channel for {ticket_id}: {e}")
            return False

    async def delete_ticket(self, ticket_id: int) -> bool:
        """Delete a ticket from the database."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    delete(Ticket).where(Ticket.id == ticket_id)
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete ticket {ticket_id}: {e}")
            return False
