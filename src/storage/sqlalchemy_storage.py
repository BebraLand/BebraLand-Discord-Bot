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

from .models import Base, UserLanguage, ScheduledTask, Ticket, TwitchSubscription, TwitchStreamState
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
                - SQLite: sqlite+aiosqlite:///data/data.db
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
            # For SQLite, ensure the directory exists
            if self.database_url.startswith("sqlite"):
                import pathlib
                # Extract path from URL (after sqlite+aiosqlite:///)
                db_path = self.database_url.split("///", 1)[-1]
                if db_path:
                    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Configure engine options based on database type
            engine_kwargs = {
                "echo": False,  # Set to True for SQL debugging
                "pool_pre_ping": True,  # Verify connections before using
                "pool_recycle": 3600,  # Recycle connections after 1 hour
            }
            
            # For PostgreSQL with asyncpg, disable prepared statements for poolers (pgbouncer)
            # This ensures compatibility with all pgbouncer-based poolers:
            # - Transaction Pooler (REQUIRED): does not support prepared statements
            # - Session Pooler: supports prepared statements but disabled for consistency
            # - Direct Connection: supports prepared statements but disabled for compatibility
            # This is a conservative approach that ensures the bot works with any connection type
            if self.database_url.startswith("postgresql+asyncpg"):
                engine_kwargs["connect_args"] = {
                    # Disable asyncpg's statement cache so prepared statements are not used.
                    # This is required when connecting through pgbouncer in "transaction" mode.
                    "statement_cache_size": 0,
                    "server_settings": {
                        "application_name": "discord_bot"
                    }
                }
            
            # Create async engine
            self.engine = create_async_engine(
                self.database_url,
                **engine_kwargs
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
            from sqlalchemy import func
            async with self.session_factory() as session:
                result = await session.execute(
                    select(func.count(Ticket.id)).where(
                        Ticket.user_id == user_id,
                        Ticket.status == "open"
                    )
                )
                count = result.scalar()
                return count or 0
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

    async def get_all_tickets(self) -> List[Dict[str, Any]]:
        """Return all tickets (open and closed) as list of dicts."""
        tickets = []
        try:
            async with self.session_factory() as session:
                result = await session.execute(select(Ticket))
                for t in result.scalars():
                    tickets.append({
                        "id": t.id,
                        "user_id": t.user_id,
                        "issue": t.issue,
                        "channel_id": t.channel_id,
                        "status": t.status,
                        "created_at": t.created_at,
                        "closed_at": t.closed_at
                    })
        except Exception as e:
            logger.error(f"Failed to fetch all tickets: {e}")
        return tickets

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

    # ==================== Twitch Subscription Methods ====================

    async def subscribe_twitch(self, user_id: str) -> bool:
        """Subscribe a user to Twitch notifications."""
        try:
            async with self.session_factory() as session:
                # Check if already subscribed
                result = await session.execute(
                    select(TwitchSubscription).where(TwitchSubscription.user_id == user_id)
                )
                existing = result.scalar_one_or_none()
                
                if not existing:
                    subscription = TwitchSubscription(
                        user_id=user_id,
                        subscribed_at=time.time()
                    )
                    session.add(subscription)
                    await session.commit()
                    return True
                return False  # Already subscribed
        except Exception as e:
            logger.error(f"Failed to subscribe user {user_id} to Twitch: {e}")
            return False

    async def unsubscribe_twitch(self, user_id: str) -> bool:
        """Unsubscribe a user from Twitch notifications."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    delete(TwitchSubscription).where(TwitchSubscription.user_id == user_id)
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to unsubscribe user {user_id} from Twitch: {e}")
            return False

    async def is_subscribed_twitch(self, user_id: str) -> bool:
        """Check if a user is subscribed to Twitch notifications."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(TwitchSubscription).where(TwitchSubscription.user_id == user_id)
                )
                return result.scalar_one_or_none() is not None
        except Exception as e:
            logger.error(f"Failed to check subscription for user {user_id}: {e}")
            return False

    async def get_all_twitch_subscribers(self) -> List[str]:
        """Get all user IDs subscribed to Twitch notifications."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(select(TwitchSubscription))
                return [sub.user_id for sub in result.scalars()]
        except Exception as e:
            logger.error(f"Failed to get Twitch subscribers: {e}")
            return []

    # ==================== Twitch Stream State Methods ====================

    async def get_stream_state(self, twitch_username: str) -> Optional[Dict[str, Any]]:
        """Get the current stream state for a Twitch user."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(TwitchStreamState).where(TwitchStreamState.twitch_username == twitch_username)
                )
                state = result.scalar_one_or_none()
                if state:
                    return {
                        "twitch_username": state.twitch_username,
                        "is_live": bool(state.is_live),
                        "stream_id": state.stream_id,
                        "notification_message_id": state.notification_message_id,
                        "started_at": state.started_at,
                        "last_checked": state.last_checked
                    }
                return None
        except Exception as e:
            logger.error(f"Failed to get stream state for {twitch_username}: {e}")
            return None

    async def update_stream_state(self, twitch_username: str, is_live: bool, 
                                   stream_id: Optional[str] = None,
                                   notification_message_id: Optional[int] = None,
                                   started_at: Optional[str] = None) -> bool:
        """Update or create stream state for a Twitch user."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(TwitchStreamState).where(TwitchStreamState.twitch_username == twitch_username)
                )
                state = result.scalar_one_or_none()

                if state:
                    # Update existing
                    state.is_live = 1 if is_live else 0
                    state.stream_id = stream_id
                    if notification_message_id is not None:
                        state.notification_message_id = notification_message_id
                    if started_at is not None:
                        state.started_at = started_at
                    state.last_checked = time.time()
                else:
                    # Create new
                    state = TwitchStreamState(
                        twitch_username=twitch_username,
                        is_live=1 if is_live else 0,
                        stream_id=stream_id,
                        notification_message_id=notification_message_id,
                        started_at=started_at,
                        last_checked=time.time()
                    )
                    session.add(state)

                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to update stream state for {twitch_username}: {e}")
            return False

    async def get_all_stream_states(self) -> List[Dict[str, Any]]:
        """Get all stream states from the database."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(select(TwitchStreamState))
                states = []
                for state in result.scalars():
                    states.append({
                        "twitch_username": state.twitch_username,
                        "is_live": bool(state.is_live),
                        "stream_id": state.stream_id,
                        "notification_message_id": state.notification_message_id,
                        "started_at": state.started_at,
                        "last_checked": state.last_checked
                    })
                return states
        except Exception as e:
            logger.error(f"Failed to get all stream states: {e}")
            return []

    async def delete_stream_state(self, twitch_username: str) -> bool:
        """Delete stream state for a Twitch user."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    delete(TwitchStreamState).where(TwitchStreamState.twitch_username == twitch_username)
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete stream state for {twitch_username}: {e}")
            return False
