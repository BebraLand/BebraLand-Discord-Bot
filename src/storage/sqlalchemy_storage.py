"""
Unified SQLAlchemy-based storage implementation.
Supports SQLite, PostgreSQL, MySQL, and MariaDB.
"""

import time
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, inspect, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.config import config as bot_config
from src.utils.logger import get_cool_logger

from .base import LanguageStorage
from .models import (
    Application,
    Base,
    Event,
    EventRegistration,
    GuildSetting,
    TempVoiceChannel,
    TempVoiceInvites,
    Ticket,
    TwitchStreamState,
    UserLanguage,
)

logger = get_cool_logger(__name__)


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
                    "server_settings": {"application_name": "discord_bot"},
                }

            # Create async engine
            self.engine = create_async_engine(self.database_url, **engine_kwargs)

            # Create session factory
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            # Create all tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await self._ensure_event_schema(conn)

            logger.info(
                f"SQLAlchemy storage initialized with {self.database_url.split('://')[0]}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to initialize SQLAlchemy storage: {e}")
            return False

    async def _ensure_event_schema(self, conn) -> None:
        """Add event columns missing from older local databases."""

        def get_column_names(sync_conn, table_name: str) -> set[str]:
            inspector = inspect(sync_conn)
            return {column["name"] for column in inspector.get_columns(table_name)}

        event_columns = await conn.run_sync(get_column_names, "events")
        registration_columns = await conn.run_sync(
            get_column_names, "event_registrations"
        )
        dialect_name = conn.dialect.name
        bool_default = "FALSE" if dialect_name == "postgresql" else "0"

        event_column_sql = {
            "reminder_minutes": "ALTER TABLE events ADD COLUMN reminder_minutes TEXT",
            "check_in_enabled": (
                "ALTER TABLE events ADD COLUMN "
                f"check_in_enabled BOOLEAN DEFAULT {bool_default}"
            ),
            "check_in_opens_minutes": (
                "ALTER TABLE events ADD COLUMN check_in_opens_minutes INTEGER DEFAULT 60"
            ),
        }
        for column_name, sql in event_column_sql.items():
            if column_name not in event_columns:
                await conn.execute(text(sql))

        if "checked_in_at" not in registration_columns:
            await conn.execute(
                text("ALTER TABLE event_registrations ADD COLUMN checked_in_at FLOAT")
            )

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

    # ==================== Ticket Methods ====================

    async def create_ticket(self, user_id: str, issue: str) -> Optional[int]:
        """Create a new ticket and return its ID."""
        try:
            async with self.session_factory() as session:
                ticket = Ticket(
                    user_id=user_id, issue=issue, created_at=time.time(), status="open"
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
                        "closed_at": ticket.closed_at,
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
                        "closed_at": ticket.closed_at,
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
                        Ticket.user_id == user_id, Ticket.status == "open"
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
                    tickets.append(
                        {
                            "id": t.id,
                            "user_id": t.user_id,
                            "issue": t.issue,
                            "channel_id": t.channel_id,
                            "status": t.status,
                            "created_at": t.created_at,
                            "closed_at": t.closed_at,
                        }
                    )
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

    # ==================== Guild Settings Methods ====================

    async def _get_guild_setting(
        self, guild_id: int, key: str, default: Any = None
    ) -> Any:
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(GuildSetting).where(
                        GuildSetting.guild_id == guild_id,
                        GuildSetting.key == key,
                    )
                )
                setting = result.scalar_one_or_none()
                return setting.value if setting else default
        except Exception as e:
            logger.error(f"Failed to get guild setting {key} for {guild_id}: {e}")
            return default

    async def _set_guild_setting(self, guild_id: int, key: str, value: Any) -> bool:
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(GuildSetting).where(
                        GuildSetting.guild_id == guild_id,
                        GuildSetting.key == key,
                    )
                )
                setting = result.scalar_one_or_none()
                if setting:
                    setting.value = value
                else:
                    setting = GuildSetting(guild_id=guild_id, key=key, value=value)
                    session.add(setting)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to set guild setting {key} for {guild_id}: {e}")
            return False

    # ==================== Application Methods ====================

    @staticmethod
    def _application_to_dict(application: Application) -> Dict[str, Any]:
        return {
            "id": application.id,
            "user_id": application.user_id,
            "guild_id": application.guild_id,
            "answers": application.answers or [],
            "status": application.status,
            "review_channel_id": application.review_channel_id,
            "review_message_id": application.review_message_id,
            "created_at": application.created_at,
            "decided_at": application.decided_at,
            "decided_by": application.decided_by,
            "decision_reason": application.decision_reason,
        }

    async def create_application(
        self, user_id: str, guild_id: int, answers: List[Dict[str, Any]]
    ) -> Optional[int]:
        """Create a new pending application and return its ID."""
        try:
            async with self.session_factory() as session:
                application = Application(
                    user_id=user_id,
                    guild_id=guild_id,
                    answers=answers,
                    created_at=time.time(),
                    status="pending",
                )
                session.add(application)
                await session.commit()
                await session.refresh(application)
                return application.id
        except Exception as e:
            logger.error(f"Failed to create application: {e}")
            return None

    async def get_application(
        self, application_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get an application by ID."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Application).where(Application.id == application_id)
                )
                application = result.scalar_one_or_none()
                return self._application_to_dict(application) if application else None
        except Exception as e:
            logger.error(f"Failed to get application {application_id}: {e}")
            return None

    async def get_pending_application_by_user(
        self, user_id: str, guild_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get a user's pending application for a guild."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Application)
                    .where(
                        Application.user_id == user_id,
                        Application.guild_id == guild_id,
                        Application.status == "pending",
                    )
                    .order_by(Application.created_at.desc())
                )
                application = result.scalars().first()
                return self._application_to_dict(application) if application else None
        except Exception as e:
            logger.error(f"Failed to get pending application for {user_id}: {e}")
            return None

    async def get_latest_application_by_user(
        self, user_id: str, guild_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get a user's latest application for a guild."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Application)
                    .where(
                        Application.user_id == user_id,
                        Application.guild_id == guild_id,
                    )
                    .order_by(Application.created_at.desc())
                )
                application = result.scalars().first()
                return self._application_to_dict(application) if application else None
        except Exception as e:
            logger.error(f"Failed to get latest application for {user_id}: {e}")
            return None

    async def get_application_by_user_status(
        self, user_id: str, guild_id: int, status: str
    ) -> Optional[Dict[str, Any]]:
        """Get a user's latest application with a specific status."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Application)
                    .where(
                        Application.user_id == user_id,
                        Application.guild_id == guild_id,
                        Application.status == status,
                    )
                    .order_by(Application.created_at.desc())
                )
                application = result.scalars().first()
                return self._application_to_dict(application) if application else None
        except Exception as e:
            logger.error(
                f"Failed to get {status} application for user {user_id}: {e}"
            )
            return None

    async def get_pending_applications(self) -> List[Dict[str, Any]]:
        """Return all pending applications."""
        applications = []
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Application).where(Application.status == "pending")
                )
                for application in result.scalars():
                    applications.append(self._application_to_dict(application))
        except Exception as e:
            logger.error(f"Failed to fetch pending applications: {e}")
        return applications

    async def delete_decided_applications_older_than(self, cutoff_time: float) -> int:
        """Delete rejected/revoked applications decided before cutoff_time."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    delete(Application).where(
                        Application.status.in_(("rejected", "revoked")),
                        Application.decided_at.is_not(None),
                        Application.decided_at < cutoff_time,
                    )
                )
                await session.commit()
                return result.rowcount or 0
        except Exception as e:
            logger.error(f"Failed to clean old decided applications: {e}")
            return 0

    async def update_application_review_message(
        self, application_id: int, review_channel_id: int, review_message_id: int
    ) -> bool:
        """Attach the Discord review message to an application."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    update(Application)
                    .where(Application.id == application_id)
                    .values(
                        review_channel_id=review_channel_id,
                        review_message_id=review_message_id,
                    )
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(
                f"Failed to update review message for application {application_id}: {e}"
            )
            return False

    async def decide_application(
        self,
        application_id: int,
        status: str,
        decided_by: str,
        reason: Optional[str] = None,
    ) -> bool:
        """Mark a pending application as accepted or rejected."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    update(Application)
                    .where(
                        Application.id == application_id,
                        Application.status == "pending",
                    )
                    .values(
                        status=status,
                        decided_at=time.time(),
                        decided_by=decided_by,
                        decision_reason=reason,
                    )
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to decide application {application_id}: {e}")
            return False

    async def update_application_status(
        self,
        application_id: int,
        status: str,
        decided_by: str,
        reason: Optional[str] = None,
    ) -> bool:
        """Update an application status regardless of its current state."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    update(Application)
                    .where(Application.id == application_id)
                    .values(
                        status=status,
                        decided_at=time.time(),
                        decided_by=decided_by,
                        decision_reason=reason,
                    )
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update application {application_id}: {e}")
            return False

    async def get_application_enabled(self, guild_id: int) -> bool:
        """Get whether applications are enabled for a guild."""
        value = await self._get_guild_setting(
            guild_id, "applications.enabled", True
        )
        return bool(value)

    async def set_application_enabled(self, guild_id: int, enabled: bool) -> bool:
        """Set whether applications are enabled for a guild."""
        return await self._set_guild_setting(
            guild_id, "applications.enabled", bool(enabled)
        )

    # ==================== Event Methods ====================

    @staticmethod
    def _event_to_dict(event: Event) -> Dict[str, Any]:
        return {
            "id": event.id,
            "guild_id": event.guild_id,
            "channel_id": event.channel_id,
            "message_id": event.message_id,
            "title": event.title,
            "description": event.description,
            "starts_at": event.starts_at,
            "languages": event.languages or [],
            "player_limit": event.player_limit,
            "reminder_minutes": SQLAlchemyStorage._parse_event_reminders(
                event.reminder_minutes
            ),
            "check_in_enabled": bool(event.check_in_enabled),
            "check_in_opens_minutes": event.check_in_opens_minutes,
            "status": event.status,
            "created_by_id": event.created_by_id,
            "created_at": event.created_at,
        }

    @staticmethod
    def _serialize_event_reminders(reminder_minutes: Optional[List[int]]) -> str:
        if not reminder_minutes:
            return ""
        return ",".join(str(minute) for minute in sorted(set(reminder_minutes)))

    @staticmethod
    def _parse_event_reminders(raw_value: Optional[str]) -> List[int]:
        if not raw_value:
            return []
        reminders = []
        for item in raw_value.split(","):
            try:
                minute = int(item.strip())
            except ValueError:
                continue
            if minute >= 0 and minute not in reminders:
                reminders.append(minute)
        return sorted(reminders, reverse=True)

    @staticmethod
    def _event_registration_to_dict(
        registration: EventRegistration,
    ) -> Dict[str, Any]:
        return {
            "id": registration.id,
            "event_id": registration.event_id,
            "user_id": registration.user_id,
            "status": registration.status,
            "position": registration.position,
            "registered_at": registration.registered_at,
            "checked_in_at": registration.checked_in_at,
            "added_by_id": registration.added_by_id,
        }

    async def create_event(
        self,
        guild_id: int,
        title: str,
        description: str,
        starts_at: float,
        languages: List[str],
        player_limit: int,
        created_by_id: str,
        reminder_minutes: Optional[List[int]] = None,
        check_in_enabled: bool = False,
        check_in_opens_minutes: int = 60,
    ) -> Optional[int]:
        """Create an open event and return its ID."""
        try:
            async with self.session_factory() as session:
                event = Event(
                    guild_id=guild_id,
                    title=title,
                    description=description,
                    starts_at=starts_at,
                    languages=languages,
                    player_limit=player_limit,
                    reminder_minutes=self._serialize_event_reminders(
                        reminder_minutes
                    ),
                    check_in_enabled=check_in_enabled,
                    check_in_opens_minutes=check_in_opens_minutes,
                    created_by_id=created_by_id,
                    created_at=time.time(),
                    status="open",
                )
                session.add(event)
                await session.commit()
                await session.refresh(event)
                return event.id
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            return None

    async def get_event(self, event_id: int) -> Optional[Dict[str, Any]]:
        """Get an event by ID."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Event).where(Event.id == event_id)
                )
                event = result.scalar_one_or_none()
                return self._event_to_dict(event) if event else None
        except Exception as e:
            logger.error(f"Failed to get event {event_id}: {e}")
            return None

    async def get_open_events(self) -> List[Dict[str, Any]]:
        """Return events that should keep persistent join buttons alive."""
        events = []
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Event).where(Event.status == "open")
                )
                for event in result.scalars():
                    events.append(self._event_to_dict(event))
        except Exception as e:
            logger.error(f"Failed to get open events: {e}")
        return events

    async def get_active_events(self) -> List[Dict[str, Any]]:
        """Return open/started events for restart recovery."""
        events = []
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Event).where(Event.status.in_(["open", "started"]))
                )
                for event in result.scalars():
                    events.append(self._event_to_dict(event))
        except Exception as e:
            logger.error(f"Failed to get active events: {e}")
        return events

    async def update_event_message(
        self, event_id: int, channel_id: int, message_id: int
    ) -> bool:
        """Attach a Discord panel message to an event."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    update(Event)
                    .where(Event.id == event_id)
                    .values(channel_id=channel_id, message_id=message_id)
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update event message for {event_id}: {e}")
            return False

    async def update_event(
        self,
        event_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        starts_at: Optional[float] = None,
        languages: Optional[List[str]] = None,
        player_limit: Optional[int] = None,
        reminder_minutes: Optional[List[int]] = None,
        check_in_enabled: Optional[bool] = None,
        check_in_opens_minutes: Optional[int] = None,
    ) -> bool:
        """Update event metadata."""
        update_values = {}
        if title is not None:
            update_values["title"] = title
        if description is not None:
            update_values["description"] = description
        if starts_at is not None:
            update_values["starts_at"] = starts_at
        if languages is not None:
            update_values["languages"] = languages
        if player_limit is not None:
            update_values["player_limit"] = player_limit
        if reminder_minutes is not None:
            update_values["reminder_minutes"] = self._serialize_event_reminders(
                reminder_minutes
            )
        if check_in_enabled is not None:
            update_values["check_in_enabled"] = bool(check_in_enabled)
        if check_in_opens_minutes is not None:
            update_values["check_in_opens_minutes"] = check_in_opens_minutes
        if not update_values:
            return False

        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    update(Event).where(Event.id == event_id).values(**update_values)
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update event {event_id}: {e}")
            return False

    async def set_event_status(self, event_id: int, status: str) -> bool:
        """Update event status."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    update(Event).where(Event.id == event_id).values(status=status)
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update event {event_id} status: {e}")
            return False

    async def get_event_registrations(
        self, event_id: int
    ) -> List[Dict[str, Any]]:
        """Return event registrations ordered by list position."""
        registrations = []
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(EventRegistration)
                    .where(EventRegistration.event_id == event_id)
                    .order_by(
                        EventRegistration.status.asc(),
                        EventRegistration.position.asc(),
                    )
                )
                for registration in result.scalars():
                    registrations.append(
                        self._event_registration_to_dict(registration)
                    )
        except Exception as e:
            logger.error(f"Failed to get registrations for event {event_id}: {e}")
        return registrations

    async def _next_event_position(
        self, session: AsyncSession, event_id: int, status: str
    ) -> int:
        result = await session.execute(
            select(EventRegistration)
            .where(
                EventRegistration.event_id == event_id,
                EventRegistration.status == status,
            )
            .order_by(EventRegistration.position.desc())
        )
        latest = result.scalars().first()
        return (latest.position + 1) if latest else 1

    async def _promote_first_backup(
        self, session: AsyncSession, event_id: int
    ) -> Optional[str]:
        result = await session.execute(
            select(EventRegistration)
            .where(
                EventRegistration.event_id == event_id,
                EventRegistration.status == "backup",
            )
            .order_by(EventRegistration.position.asc())
        )
        backup = result.scalars().first()
        if not backup:
            return None
        backup.status = "main"
        backup.position = await self._next_event_position(session, event_id, "main")
        return backup.user_id

    async def register_event_user(
        self,
        event_id: int,
        user_id: str,
        added_by_id: Optional[str] = None,
    ) -> Optional[str]:
        """Register user as main or backup. Returns status, exists, or None."""
        try:
            async with self.session_factory() as session:
                event_result = await session.execute(
                    select(Event).where(Event.id == event_id, Event.status == "open")
                )
                event = event_result.scalar_one_or_none()
                if not event:
                    return None

                existing_result = await session.execute(
                    select(EventRegistration).where(
                        EventRegistration.event_id == event_id,
                        EventRegistration.user_id == user_id,
                    )
                )
                if existing_result.scalar_one_or_none():
                    return "exists"

                main_result = await session.execute(
                    select(EventRegistration).where(
                        EventRegistration.event_id == event_id,
                        EventRegistration.status == "main",
                    )
                )
                main_count = len(main_result.scalars().all())
                status = "main" if main_count < event.player_limit else "backup"
                registration = EventRegistration(
                    event_id=event_id,
                    user_id=user_id,
                    status=status,
                    position=await self._next_event_position(
                        session, event_id, status
                    ),
                    registered_at=time.time(),
                    added_by_id=added_by_id,
                )
                session.add(registration)
                await session.commit()
                return status
        except Exception as e:
            logger.error(f"Failed to register user {user_id} for event {event_id}: {e}")
            return None

    async def unregister_event_user(
        self, event_id: int, user_id: str
    ) -> Optional[str]:
        """Remove own registration. Returns promoted user ID or removed status."""
        return await self.remove_event_user(event_id, user_id)

    async def remove_event_user(self, event_id: int, user_id: str) -> Optional[str]:
        """Remove a registration and promote first backup if main slot opens."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(EventRegistration).where(
                        EventRegistration.event_id == event_id,
                        EventRegistration.user_id == user_id,
                    )
                )
                registration = result.scalar_one_or_none()
                if not registration:
                    return None

                removed_status = registration.status
                await session.delete(registration)
                promoted_user_id = None
                if removed_status == "main":
                    promoted_user_id = await self._promote_first_backup(
                        session, event_id
                    )
                await session.commit()
                return promoted_user_id or f"removed_{removed_status}"
        except Exception as e:
            logger.error(f"Failed to remove user {user_id} from event {event_id}: {e}")
            return None

    async def check_in_event_user(
        self, event_id: int, user_id: str
    ) -> Optional[str]:
        """Mark a registered event user as checked in."""
        try:
            async with self.session_factory() as session:
                event_result = await session.execute(
                    select(Event).where(Event.id == event_id, Event.status == "open")
                )
                event = event_result.scalar_one_or_none()
                if not event or not event.check_in_enabled:
                    return None
                check_in_opens_at = event.starts_at - (
                    event.check_in_opens_minutes * 60
                )
                if time.time() < check_in_opens_at:
                    return "not_open_yet"

                registration_result = await session.execute(
                    select(EventRegistration).where(
                        EventRegistration.event_id == event_id,
                        EventRegistration.user_id == user_id,
                    )
                )
                registration = registration_result.scalar_one_or_none()
                if not registration:
                    return "not_registered"
                if registration.checked_in_at is not None:
                    return "already"

                registration.checked_in_at = time.time()
                await session.commit()
                return (
                    "backup_checked"
                    if registration.status == "backup"
                    else "checked"
                )
        except Exception as e:
            logger.error(
                f"Failed to check in user {user_id} for event {event_id}: {e}"
            )
            return None

    # NOTE: Twitch subscriptions are now role-based; DB-backed subscription
    # methods and models were removed. Use Discord role `bot_config.modules.twitch.ping_role_id`.

    # ==================== Twitch Stream State Methods ====================

    async def get_stream_state(self, twitch_username: str) -> Optional[Dict[str, Any]]:
        """Get the current stream state for a Twitch user."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(TwitchStreamState).where(
                        TwitchStreamState.twitch_username == twitch_username
                    )
                )
                state = result.scalar_one_or_none()
                if state:
                    return {
                        "twitch_username": state.twitch_username,
                        "is_live": bool(state.is_live),
                        "stream_id": state.stream_id,
                        "notification_message_id": state.notification_message_id,
                        "started_at": state.started_at,
                        "last_checked": state.last_checked,
                    }
                return None
        except Exception as e:
            logger.error(f"Failed to get stream state for {twitch_username}: {e}")
            return None

    async def update_stream_state(
        self,
        twitch_username: str,
        is_live: bool,
        stream_id: Optional[str] = None,
        notification_message_id: Optional[int] = None,
        started_at: Optional[str] = None,
    ) -> bool:
        """Update or create stream state for a Twitch user."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(TwitchStreamState).where(
                        TwitchStreamState.twitch_username == twitch_username
                    )
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
                        last_checked=time.time(),
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
                    states.append(
                        {
                            "twitch_username": state.twitch_username,
                            "is_live": bool(state.is_live),
                            "stream_id": state.stream_id,
                            "notification_message_id": state.notification_message_id,
                            "started_at": state.started_at,
                            "last_checked": state.last_checked,
                        }
                    )
                return states
        except Exception as e:
            logger.error(f"Failed to get all stream states: {e}")
            return []

    async def delete_stream_state(self, twitch_username: str) -> bool:
        """Delete stream state for a Twitch user."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    delete(TwitchStreamState).where(
                        TwitchStreamState.twitch_username == twitch_username
                    )
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete stream state for {twitch_username}: {e}")
            return False

    # ============================================
    # Temp Voice Channel Methods
    # ============================================

    async def create_temp_voice_channel(
        self,
        channel_id: int,
        owner_id: int,
        guild_id: int,
        control_message_id: Optional[int],
        created_at: float,
    ) -> bool:
        """Create a new temporary voice channel record."""
        try:
            async with self.session_factory() as session:
                temp_vc = TempVoiceChannel(
                    channel_id=channel_id,
                    owner_id=owner_id,
                    guild_id=guild_id,
                    control_message_id=control_message_id,
                    created_at=created_at,
                    permitted_users=[],
                    permitted_roles=[],
                    rejected_users=[],
                    rejected_roles=[],
                )
                session.add(temp_vc)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to create temp voice channel {channel_id}: {e}")
            return False

    async def get_temp_voice_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """Get a temporary voice channel by ID."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(TempVoiceChannel).where(
                        TempVoiceChannel.channel_id == channel_id
                    )
                )
                temp_vc = result.scalar_one_or_none()
                if temp_vc:
                    return {
                        "channel_id": temp_vc.channel_id,
                        "owner_id": temp_vc.owner_id,
                        "guild_id": temp_vc.guild_id,
                        "control_message_id": temp_vc.control_message_id,
                        "created_at": temp_vc.created_at,
                        "permitted_users": temp_vc.permitted_users or [],
                        "permitted_roles": temp_vc.permitted_roles or [],
                        "rejected_users": temp_vc.rejected_users or [],
                        "rejected_roles": temp_vc.rejected_roles or [],
                    }
                return None
        except Exception as e:
            logger.error(f"Failed to get temp voice channel {channel_id}: {e}")
            return None

    async def get_all_temp_voice_channels(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all temporary voice channels for a guild."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(TempVoiceChannel).where(
                        TempVoiceChannel.guild_id == guild_id
                    )
                )
                channels = []
                for temp_vc in result.scalars():
                    channels.append(
                        {
                            "channel_id": temp_vc.channel_id,
                            "owner_id": temp_vc.owner_id,
                            "guild_id": temp_vc.guild_id,
                            "control_message_id": temp_vc.control_message_id,
                            "created_at": temp_vc.created_at,
                            "permitted_users": temp_vc.permitted_users or [],
                            "permitted_roles": temp_vc.permitted_roles or [],
                            "rejected_users": temp_vc.rejected_users or [],
                            "rejected_roles": temp_vc.rejected_roles or [],
                        }
                    )
                return channels
        except Exception as e:
            logger.error(
                f"Failed to get all temp voice channels for guild {guild_id}: {e}"
            )
            return []

    async def update_temp_voice_channel(
        self,
        channel_id: int,
        owner_id: Optional[int] = None,
        control_message_id: Optional[int] = None,
        permitted_users: Optional[List[int]] = None,
        permitted_roles: Optional[List[int]] = None,
        rejected_users: Optional[List[int]] = None,
        rejected_roles: Optional[List[int]] = None,
    ) -> bool:
        """Update a temporary voice channel."""
        try:
            async with self.session_factory() as session:
                # Build update dict with only provided values
                update_values = {}
                if owner_id is not None:
                    update_values["owner_id"] = owner_id
                if control_message_id is not None:
                    update_values["control_message_id"] = control_message_id
                if permitted_users is not None:
                    update_values["permitted_users"] = permitted_users
                if permitted_roles is not None:
                    update_values["permitted_roles"] = permitted_roles
                if rejected_users is not None:
                    update_values["rejected_users"] = rejected_users
                if rejected_roles is not None:
                    update_values["rejected_roles"] = rejected_roles

                if update_values:
                    result = await session.execute(
                        update(TempVoiceChannel)
                        .where(TempVoiceChannel.channel_id == channel_id)
                        .values(**update_values)
                    )
                    await session.commit()
                    return result.rowcount > 0
                return False
        except Exception as e:
            logger.error(f"Failed to update temp voice channel {channel_id}: {e}")
            return False

    async def delete_temp_voice_channel(self, channel_id: int) -> bool:
        """Delete a temporary voice channel record."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    delete(TempVoiceChannel).where(
                        TempVoiceChannel.channel_id == channel_id
                    )
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete temp voice channel {channel_id}: {e}")
            return False

    # ==================== Temp Voice Invite Methods ====================

    async def get_invite_preference(self, user_id: int) -> bool:
        """
        Get user's invite preference.

        Args:
            user_id: Discord user ID

        Returns:
            True if invites are blocked, False if allowed (default)
        """
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(TempVoiceInvites).where(
                        TempVoiceInvites.user_id == str(user_id)
                    )
                )
                invite_pref = result.scalar_one_or_none()

                # If not in DB, return the inverse of the default state
                # bot_config.modules.temp_voice.invite_notification_default_state=True means invites are allowed by default (blocked=False)
                # bot_config.modules.temp_voice.invite_notification_default_state=False means invites are blocked by default (blocked=True)
                if invite_pref is None:
                    return not bot_config.modules.temp_voice.invite_notification_default_state

                return invite_pref.blocked
        except Exception as e:
            logger.error(f"Failed to get invite preference for user {user_id}: {e}")
            # On error, return the inverse of default state
            return not bot_config.modules.temp_voice.invite_notification_default_state

    async def set_invite_preference(self, user_id: int, blocked: bool) -> bool:
        """
        Set user's invite preference.
        Optimized to only store non-default values.

        Args:
            user_id: Discord user ID
            blocked: True to block invites, False to allow them

        Returns:
            True if successful, False otherwise
        """
        try:
            async with self.session_factory() as session:
                # Check if user already exists
                result = await session.execute(
                    select(TempVoiceInvites).where(
                        TempVoiceInvites.user_id == str(user_id)
                    )
                )
                invite_pref = result.scalar_one_or_none()

                # Calculate default state: bot_config.modules.temp_voice.invite_notification_default_state=True means blocked=False by default
                default_blocked = not bot_config.modules.temp_voice.invite_notification_default_state

                # If setting to default, delete the row to save space
                if blocked == default_blocked:
                    if invite_pref:
                        await session.delete(invite_pref)
                    # If not in DB and setting to default, nothing to do
                else:
                    # Non-default value, need to store it
                    if invite_pref:
                        # Update existing
                        invite_pref.blocked = blocked
                    else:
                        # Create new
                        invite_pref = TempVoiceInvites(
                            user_id=str(user_id), blocked=blocked
                        )
                        session.add(invite_pref)

                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to set invite preference for user {user_id}: {e}")
            return False

    async def toggle_invite_preference(self, user_id: int) -> bool:
        """
        Toggle user's invite preference.
        Optimized to only store non-default values.

        Args:
            user_id: Discord user ID

        Returns:
            The new state (True if now blocked, False if now allowed)
        """
        try:
            async with self.session_factory() as session:
                # Check if user already exists
                result = await session.execute(
                    select(TempVoiceInvites).where(
                        TempVoiceInvites.user_id == str(user_id)
                    )
                )
                invite_pref = result.scalar_one_or_none()

                # Calculate default state: bot_config.modules.temp_voice.invite_notification_default_state=True means blocked=False by default
                default_blocked = not bot_config.modules.temp_voice.invite_notification_default_state

                if invite_pref:
                    # Toggle existing
                    new_blocked = not invite_pref.blocked

                    # If toggling back to default, delete the row
                    if new_blocked == default_blocked:
                        await session.delete(invite_pref)
                    else:
                        invite_pref.blocked = new_blocked

                    new_state = new_blocked
                else:
                    # Not in DB, so currently at default. Toggle to non-default
                    new_blocked = not default_blocked
                    invite_pref = TempVoiceInvites(
                        user_id=str(user_id), blocked=new_blocked
                    )
                    session.add(invite_pref)
                    new_state = new_blocked

                await session.commit()
                return new_state
        except Exception as e:
            logger.error(f"Failed to toggle invite preference for user {user_id}: {e}")
            return default_blocked
