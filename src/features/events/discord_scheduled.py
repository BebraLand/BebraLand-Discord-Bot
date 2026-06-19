from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import discord

from config.config import config as bot_config
from src.utils.database import get_db
from src.utils.logger import get_cool_logger

DISCORD_EVENT_LOCATION_TYPES = {"external", "voice", "stage"}
DISCORD_EVENT_LOCATION_ALIASES = {
    "somewhere_else": "external",
    "somewhere else": "external",
    "elsewhere": "external",
    "external": "external",
    "voice_channel": "voice",
    "voice channel": "voice",
    "voice": "voice",
    "stage_channel": "stage",
    "stage channel": "stage",
    "stage": "stage",
}
DEFAULT_DISCORD_EVENT_DURATION_MINUTES = 60
DEFAULT_DISCORD_EVENT_LOCATION = "BebraLand Minecraft server"
MAX_COVER_IMAGE_BYTES = 10 * 1024 * 1024

logger = get_cool_logger(__name__)


def normalize_discord_event_location_type(raw_value: Optional[str]) -> str:
    value = (raw_value or "external").strip().lower().replace("-", "_")
    return DISCORD_EVENT_LOCATION_ALIASES.get(value, "external")


def coerce_discord_event_duration_minutes(raw_value: object) -> int:
    try:
        duration = int(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_DISCORD_EVENT_DURATION_MINUTES
    if duration < 1:
        return DEFAULT_DISCORD_EVENT_DURATION_MINUTES
    return duration


def discord_event_end_time(starts_at: datetime, duration_minutes: object) -> datetime:
    return starts_at + timedelta(
        minutes=coerce_discord_event_duration_minutes(duration_minutes)
    )


def build_discord_scheduled_event_url(guild_id: int, event_id: int) -> str:
    return f"https://discord.com/events/{guild_id}/{event_id}"


def _get_config_value(path: str, default: Any = None) -> Any:
    value = bot_config
    for key in path.split("."):
        if value is None:
            return default
        value = getattr(value, key, default)
    return value


def discord_scheduled_events_enabled() -> bool:
    return bool(
        _get_config_value(
            "modules.events.discord_scheduled_events.enabled",
            True,
        )
    )


def discord_event_user_sync_enabled() -> bool:
    return bool(
        _get_config_value(
            "modules.events.discord_scheduled_events.sync_interested_users",
            True,
        )
    )


def default_discord_event_location() -> str:
    return str(
        _get_config_value(
            "modules.events.discord_scheduled_events.default_location",
            DEFAULT_DISCORD_EVENT_LOCATION,
        )
        or DEFAULT_DISCORD_EVENT_LOCATION
    )


def default_discord_event_duration_minutes() -> int:
    return coerce_discord_event_duration_minutes(
        _get_config_value(
            "modules.events.discord_scheduled_events.default_duration_minutes",
            DEFAULT_DISCORD_EVENT_DURATION_MINUTES,
        )
    )


async def read_cover_image_bytes(
    cover_image: Optional[discord.Attachment],
) -> Optional[bytes]:
    if cover_image is None:
        return None

    content_type = (cover_image.content_type or "").lower()
    if content_type and not content_type.startswith("image/"):
        raise ValueError("Cover image must be an image attachment.")

    size = int(cover_image.size or 0)
    if size > MAX_COVER_IMAGE_BYTES:
        raise ValueError("Cover image must be 10 MB or smaller.")

    return await cover_image.read()


def resolve_discord_event_location(
    location_type: Optional[str],
    *,
    voice_channel: Optional[discord.VoiceChannel] = None,
    stage_channel: Optional[discord.StageChannel] = None,
    external_location: Optional[str] = None,
    default_to_external: bool = True,
) -> str | discord.VoiceChannel | discord.StageChannel | None:
    has_location_input = any(
        [location_type, voice_channel, stage_channel, external_location]
    )
    if not has_location_input and not default_to_external:
        return None

    normalized = normalize_discord_event_location_type(location_type)
    if voice_channel is not None and location_type is None:
        normalized = "voice"
    if stage_channel is not None and location_type is None:
        normalized = "stage"
    if external_location and location_type is None:
        normalized = "external"

    if normalized == "voice":
        if voice_channel is None:
            raise ValueError("Choose a voice channel for Discord event location.")
        return voice_channel
    if normalized == "stage":
        if stage_channel is None:
            raise ValueError("Choose a stage channel for Discord event location.")
        return stage_channel

    return (external_location or default_discord_event_location()).strip()


def _event_start_datetime(event: dict[str, Any]) -> datetime:
    return datetime.fromtimestamp(float(event["starts_at"]), tz=timezone.utc)


async def create_discord_scheduled_event(
    guild: discord.Guild,
    event: dict[str, Any],
    *,
    location_type: Optional[str],
    voice_channel: Optional[discord.VoiceChannel] = None,
    stage_channel: Optional[discord.StageChannel] = None,
    external_location: Optional[str] = None,
    cover_image: Optional[discord.Attachment] = None,
) -> Optional[discord.ScheduledEvent]:
    if not discord_scheduled_events_enabled():
        return None

    location = resolve_discord_event_location(
        location_type,
        voice_channel=voice_channel,
        stage_channel=stage_channel,
        external_location=external_location,
    )
    starts_at = _event_start_datetime(event)
    image = await read_cover_image_bytes(cover_image)
    kwargs: dict[str, Any] = {
        "name": event["title"],
        "description": event["description"],
        "start_time": starts_at,
        "end_time": discord_event_end_time(
            starts_at,
            default_discord_event_duration_minutes(),
        ),
        "location": location,
        "reason": f"BebraLand event #{event['id']} mirror",
    }
    if image is not None:
        kwargs["image"] = image

    try:
        scheduled_event = await guild.create_scheduled_event(**kwargs)
        if scheduled_event is None:
            return None

        db = await get_db()
        await db.update_event_discord_event(event["id"], scheduled_event.id)
        return scheduled_event
    except discord.DiscordException as error:
        logger.error(
            f"Failed to create Discord scheduled event #{event['id']}: {error}"
        )
        return None


async def fetch_discord_scheduled_event(
    guild: discord.Guild,
    event: dict[str, Any],
) -> Optional[discord.ScheduledEvent]:
    discord_event_id = event.get("discord_event_id")
    if not discord_event_id:
        return None

    scheduled_event = guild.get_scheduled_event(int(discord_event_id))
    if scheduled_event is not None:
        return scheduled_event

    try:
        return await guild.fetch_scheduled_event(int(discord_event_id))
    except discord.NotFound:
        db = await get_db()
        await db.update_event_discord_event(event["id"], None)
        logger.info(
            f"Discord scheduled event {discord_event_id} no longer exists; "
            f"cleared mirror for event #{event['id']}"
        )
        return None
    except discord.DiscordException as error:
        logger.warning(
            f"Failed to fetch Discord scheduled event {discord_event_id}: {error}"
        )
        return None


async def update_discord_scheduled_event(
    guild: discord.Guild,
    event: dict[str, Any],
    *,
    location_type: Optional[str] = None,
    voice_channel: Optional[discord.VoiceChannel] = None,
    stage_channel: Optional[discord.StageChannel] = None,
    external_location: Optional[str] = None,
    cover_image: Optional[discord.Attachment] = None,
) -> bool:
    if not discord_scheduled_events_enabled() or not event.get("discord_event_id"):
        return False

    scheduled_event = await fetch_discord_scheduled_event(guild, event)
    if scheduled_event is None:
        return False

    starts_at = _event_start_datetime(event)
    kwargs: dict[str, Any] = {
        "name": event["title"],
        "description": event["description"],
        "start_time": starts_at,
        "end_time": discord_event_end_time(
            starts_at,
            default_discord_event_duration_minutes(),
        ),
        "reason": f"BebraLand event #{event['id']} sync",
    }
    location = resolve_discord_event_location(
        location_type,
        voice_channel=voice_channel,
        stage_channel=stage_channel,
        external_location=external_location,
        default_to_external=False,
    )
    if location is not None:
        kwargs["location"] = location

    image = await read_cover_image_bytes(cover_image)
    if image is not None:
        kwargs["image"] = image

    try:
        await scheduled_event.edit(**kwargs)
        return True
    except discord.DiscordException as error:
        logger.error(
            f"Failed to update Discord scheduled event #{event['id']}: {error}"
        )
        return False


async def cancel_discord_scheduled_event(
    guild: discord.Guild,
    event: dict[str, Any],
    *,
    reason: Optional[str] = None,
) -> bool:
    if not event.get("discord_event_id"):
        return False

    scheduled_event = await fetch_discord_scheduled_event(guild, event)
    if scheduled_event is None:
        return False

    reason_text = reason or f"BebraLand event #{event['id']} cancelled"
    try:
        if scheduled_event.status is discord.ScheduledEventStatus.active:
            await scheduled_event.complete(reason=reason_text)
        else:
            await scheduled_event.cancel(reason=reason_text)
    except discord.DiscordException:
        try:
            await scheduled_event.delete()
        except discord.DiscordException as error:
            logger.error(
                f"Failed to cancel Discord scheduled event #{event['id']}: {error}"
            )
            return False

    db = await get_db()
    await db.update_event_discord_event(event["id"], None)
    return True
