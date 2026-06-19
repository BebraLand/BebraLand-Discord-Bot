import re
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord

from config.config import config as bot_config
from src.languages import lang_constants
from src.languages.localize import _
from src.utils.database import get_language
from src.utils.embeds import get_embed_icon
from src.utils.normalize_unix import normalize_unix_timestamp

DEFAULT_SCHEDULE_TIMEZONE = "Europe/Vilnius"


def get_schedule_timezone() -> ZoneInfo:
    timezone_name = getattr(
        getattr(bot_config, "bot", {}),
        "timezone",
        DEFAULT_SCHEDULE_TIMEZONE,
    )
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_SCHEDULE_TIMEZONE)


def parse_human_schedule_time(value: str) -> int:
    """Parse admin-friendly schedule text into a future Unix timestamp."""
    raw = (value or "").strip().lower()
    if not raw:
        raise ValueError("Invalid time format")

    schedule_timezone = get_schedule_timezone()
    now = datetime.now(schedule_timezone)

    if raw == "now":
        return int(now.timestamp())

    in_match = re.match(
        r"^in\s+(\d+)\s*(m|min|mins|minute|minutes|h|hr|hour|hours)$", raw
    )
    if in_match:
        amount = int(in_match.group(1))
        unit = in_match.group(2)
        delta = (
            timedelta(hours=amount)
            if unit.startswith("h")
            else timedelta(minutes=amount)
        )
        return int((now + delta).timestamp())

    time_match = re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", raw)
    if time_match:
        hour, minute = time_match.groups()
        scheduled = now.replace(
            hour=int(hour), minute=int(minute), second=0, microsecond=0
        )
        if scheduled <= now:
            scheduled += timedelta(days=1)
        return int(scheduled.timestamp())

    day_match = re.match(r"^(today|tomorrow)\s+([01]?\d|2[0-3]):([0-5]\d)$", raw)
    if day_match:
        day, hour, minute = day_match.groups()
        scheduled = now.replace(
            hour=int(hour), minute=int(minute), second=0, microsecond=0
        )
        if day == "tomorrow":
            scheduled += timedelta(days=1)
        if scheduled <= now:
            raise ValueError("Schedule time must be in the future")
        return int(scheduled.timestamp())

    return normalize_unix_timestamp(value, require_future=True)


async def parse_and_validate_schedule(
    ctx: discord.ApplicationContext, schedule_time: str
) -> Optional[int]:
    """Parse schedule time. Sends error embed and returns None if invalid."""
    if not schedule_time:
        return None

    try:
        return parse_human_schedule_time(schedule_time)
    except ValueError as e:
        current_lang = await get_language(ctx.user.id)
        timezone_name = getattr(
            getattr(bot_config, "bot", {}),
            "timezone",
            DEFAULT_SCHEDULE_TIMEZONE,
        )
        desc = (
            f"**{str(e)}**\n\n"
            "Use `19:00`, `in 30m`, `in 2h`, `today 20:00`, `tomorrow 18:30`, "
            "or a Discord/Unix timestamp like <t:1777217700:F>.\n"
            f"Human times use `{timezone_name}`."
        )
        embed = discord.Embed(
            title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
            description=desc,
            color=bot_config.embeds.failed_color,
        )
        embed.set_footer(text=bot_config.bot.trademark, icon_url=get_embed_icon(ctx))

        # Determine if we should use respond or followup based on if deferred
        send_method = (
            ctx.followup.send if ctx.interaction.response.is_done() else ctx.respond
        )

        await send_method(
            embed=embed,
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )
        return None
