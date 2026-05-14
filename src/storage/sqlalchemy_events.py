import time
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.logger import get_cool_logger

from .models import Event, EventRegistration

logger = get_cool_logger(__name__)


def event_registration_status(main_count: int, player_limit: int) -> str:
    if player_limit == 0:
        return "main"
    return "main" if main_count < player_limit else "backup"


class SQLAlchemyEventMixin:
    @staticmethod
    def _event_to_dict(event: Event) -> Dict[str, Any]:
        return {
            "id": event.id,
            "guild_id": event.guild_id,
            "channel_id": event.channel_id,
            "message_id": event.message_id,
            "discord_event_id": event.discord_event_id,
            "cover_image_url": event.cover_image_url,
            "title": event.title,
            "description": event.description,
            "starts_at": event.starts_at,
            "languages": event.languages or [],
            "player_limit": event.player_limit,
            "reminder_minutes": SQLAlchemyEventMixin._parse_event_reminders(
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
        cover_image_url: Optional[str] = None,
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
                    cover_image_url=cover_image_url,
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

    async def get_event_by_discord_event_id(
        self, discord_event_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get an event linked to a Discord scheduled event."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Event).where(Event.discord_event_id == discord_event_id)
                )
                event = result.scalar_one_or_none()
                return self._event_to_dict(event) if event else None
        except Exception as e:
            logger.error(
                f"Failed to get event by Discord scheduled event {discord_event_id}: {e}"
            )
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

    async def update_event_discord_event(
        self, event_id: int, discord_event_id: Optional[int]
    ) -> bool:
        """Attach or clear a Discord scheduled event mirror."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    update(Event)
                    .where(Event.id == event_id)
                    .values(discord_event_id=discord_event_id)
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update Discord scheduled event for {event_id}: {e}")
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
        cover_image_url: Optional[str] = None,
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
        if cover_image_url is not None:
            update_values["cover_image_url"] = cover_image_url
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
                status = event_registration_status(main_count, event.player_limit)
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
