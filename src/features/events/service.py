from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import discord

from config.config import config as bot_config
from src.features.events.discord_scheduled import build_discord_scheduled_event_url
from src.languages.localize import _, locale_display_name
from src.utils.database import get_db
from src.utils.embeds import build_embed_from_data, get_embed_icon

LANGUAGE_CODES = {"en", "ru", "lt"}


def normalize_event_languages(raw_languages: str) -> List[str]:
    languages = []
    for item in raw_languages.replace(";", ",").replace(" ", ",").split(","):
        language = item.strip().lower()
        if language in LANGUAGE_CODES and language not in languages:
            languages.append(language)
    return languages


def parse_event_reminders(raw_reminders: Optional[str]) -> List[int]:
    if not raw_reminders:
        return []
    reminders = []
    for item in raw_reminders.replace(";", ",").replace(" ", ",").split(","):
        if not item:
            continue
        try:
            minutes = int(item)
        except ValueError:
            continue
        if minutes >= 0 and minutes not in reminders:
            reminders.append(minutes)
    return sorted(reminders, reverse=True)


def format_user_list(
    registrations: List[Dict[str, Any]],
    status: str,
    show_check_in: bool = False,
) -> str:
    users = [item for item in registrations if item["status"] == status]
    if not users:
        return "-"
    lines = []
    for index, item in enumerate(users[:20], start=1):
        prefix = ""
        if show_check_in:
            prefix = "✅ " if item.get("checked_in_at") is not None else "⏳ "
        lines.append(f"{index}. {prefix}<@{item['user_id']}>")
    if len(users) > 20:
        lines.append(f"... +{len(users) - 20}")
    return "\n".join(lines)


def format_player_capacity(main_count: int, player_limit: int) -> str:
    if player_limit == 0:
        return f"{main_count}/unlimited"
    return f"{main_count}/{player_limit}"


def build_calendar_url(event: Dict[str, Any]) -> str:
    starts_at = datetime.fromtimestamp(event["starts_at"], tz=timezone.utc)
    ends_at = starts_at + timedelta(hours=1)
    dates = f"{starts_at:%Y%m%dT%H%M%SZ}/{ends_at:%Y%m%dT%H%M%SZ}"
    query = urlencode(
        {
            "action": "TEMPLATE",
            "text": event["title"],
            "details": event["description"],
            "dates": dates,
        }
    )
    return f"https://calendar.google.com/calendar/render?{query}"


def build_event_message_url(event: Dict[str, Any]) -> str:
    if (
        not event.get("guild_id")
        or not event.get("channel_id")
        or not event.get("message_id")
    ):
        return ""
    return (
        "https://discord.com/channels/"
        f"{event['guild_id']}/{event['channel_id']}/{event['message_id']}"
    )


def event_cover_image_data(event: Dict[str, Any]) -> Optional[Dict[str, str]]:
    cover_image_url = str(event.get("cover_image_url") or "").strip()
    if not cover_image_url:
        return None
    return {"url": cover_image_url}


def event_embed_color(status: str) -> int:
    if status == "cancelled":
        return bot_config.embeds.failed_color
    if status == "closed":
        return bot_config.embeds.info_color
    return bot_config.embeds.default_color


def get_warning_color() -> int:
    return getattr(bot_config.embeds, "warning_color", bot_config.embeds.info_color)


def is_check_in_open(event: Dict[str, Any]) -> bool:
    if not event.get("check_in_enabled"):
        return False
    opens_minutes = int(event.get("check_in_opens_minutes") or 60)
    opens_at = event["starts_at"] - (opens_minutes * 60)
    return datetime.now(timezone.utc).timestamp() >= opens_at


async def build_event_embed(
    event: Dict[str, Any],
    bot: Optional[discord.Client] = None,
) -> discord.Embed:
    db = await get_db()
    registrations = await db.get_event_registrations(event["id"])
    main_count = len([r for r in registrations if r["status"] == "main"])
    backup_count = len([r for r in registrations if r["status"] == "backup"])
    checked_main_count = len(
        [
            r
            for r in registrations
            if r["status"] == "main" and r.get("checked_in_at") is not None
        ]
    )
    checked_backup_count = len(
        [
            r
            for r in registrations
            if r["status"] == "backup" and r.get("checked_in_at") is not None
        ]
    )
    languages = ", ".join(
        locale_display_name(language) for language in event["languages"]
    )
    fields = [
        {
            "name": "Time",
            "value": f"<t:{int(event['starts_at'])}:F> (<t:{int(event['starts_at'])}:R>)",
            "inline": False,
        },
        {
            "name": "Calendar",
            "value": f"[Add to Google Calendar]({build_calendar_url(event)})",
            "inline": False,
        },
        {
            "name": "Languages",
            "value": languages or "-",
            "inline": True,
        },
        {
            "name": "Players",
            "value": format_player_capacity(main_count, int(event["player_limit"])),
            "inline": True,
        },
        {
            "name": "Backup",
            "value": str(backup_count),
            "inline": True,
        },
    ]
    if event.get("discord_event_id"):
        fields.append(
            {
                "name": "Discord Event",
                "value": (
                    "[Open native event]"
                    f"({build_discord_scheduled_event_url(event['guild_id'], event['discord_event_id'])})"
                ),
                "inline": False,
            }
        )
    if event.get("reminder_minutes"):
        reminders = ", ".join(
            "start" if minute == 0 else f"{minute}m"
            for minute in event["reminder_minutes"]
        )
        fields.append(
            {
                "name": "Reminders",
                "value": reminders,
                "inline": True,
            }
        )
    if event.get("check_in_enabled"):
        opens_minutes = int(event.get("check_in_opens_minutes") or 60)
        check_in_value = f"{checked_main_count}/{main_count}"
        if not is_check_in_open(event):
            opens_at = int(event["starts_at"] - (opens_minutes * 60))
            check_in_value += f"\nOpens <t:{opens_at}:R>"
        elif backup_count:
            check_in_value += f"\nBackup {checked_backup_count}/{backup_count}"
        fields.append(
            {
                "name": "Check-in",
                "value": check_in_value,
                "inline": True,
            }
        )
    fields.extend(
        [
            {
                "name": "Main",
                "value": format_user_list(
                    registrations,
                    "main",
                    show_check_in=event.get("check_in_enabled")
                    and is_check_in_open(event),
                ),
                "inline": False,
            },
            {
                "name": "Backup list",
                "value": format_user_list(
                    registrations,
                    "backup",
                    show_check_in=event.get("check_in_enabled")
                    and is_check_in_open(event),
                ),
                "inline": False,
            },
        ]
    )

    embed_data = {
        "title": event["title"],
        "description": event["description"],
        "color": event_embed_color(event["status"]),
        "fields": fields,
        "footer": {
            "text": f"Event #{event['id']} | {event['status'].title()}",
            "icon_url": get_embed_icon(bot),
        },
    }
    return build_embed_from_data(embed_data)


async def build_event_embeds(
    event: Dict[str, Any],
    bot: Optional[discord.Client] = None,
) -> list[discord.Embed]:
    cover_embed_data = {"color": event_embed_color(event["status"])}
    image = event_cover_image_data(event)
    if not image:
        return [await build_event_embed(event, bot)]

    cover_embed_data["image"] = image
    return [
        build_embed_from_data(cover_embed_data),
        await build_event_embed(event, bot),
    ]


async def refresh_event_message(bot: discord.Client, event_id: int) -> bool:
    db = await get_db()
    event = await db.get_event(event_id)
    if not event or not event["channel_id"] or not event["message_id"]:
        return False

    channel = bot.get_channel(event["channel_id"])
    if channel is None:
        try:
            channel = await bot.fetch_channel(event["channel_id"])
        except discord.DiscordException:
            return False

    try:
        message = await channel.fetch_message(event["message_id"])
        from src.features.events.view.EventRegistrationView import (
            EventRegistrationView,
        )

        view = EventRegistrationView(
            event_id,
            disabled=event["status"] != "open",
            check_in_enabled=event.get("check_in_enabled", False),
            check_in_open=is_check_in_open(event),
        )
        await message.edit(embeds=await build_event_embeds(event, bot), view=view)
        return True
    except discord.DiscordException:
        return False


async def send_event_panel(channel_id: int, event_id: int) -> bool:
    from src.features.events.view.EventRegistrationView import EventRegistrationView
    from src.utils.bot_instance import get_bot

    bot = get_bot()
    if bot is None:
        return False

    db = await get_db()
    event = await db.get_event(event_id)
    if not event or event["status"] == "cancelled":
        return False

    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.DiscordException:
            return False

    message = await channel.send(
        embeds=await build_event_embeds(event, bot),
        view=EventRegistrationView(
            event_id,
            check_in_enabled=event.get("check_in_enabled", False),
            check_in_open=is_check_in_open(event),
        ),
    )
    await db.update_event_message(event_id, channel.id, message.id)
    bot.add_view(
        EventRegistrationView(
            event_id,
            check_in_enabled=event.get("check_in_enabled", False),
            check_in_open=is_check_in_open(event),
        ),
        message_id=message.id,
    )
    return True


def cancel_event_jobs(event_id: int) -> None:
    from src.utils.scheduler import scheduler

    for job in scheduler.get_jobs():
        if job.id.startswith(f"event_{event_id}_"):
            scheduler.remove_job(job.id)


def cancel_event_reminder_jobs(event_id: int) -> None:
    from src.utils.scheduler import scheduler

    for job in scheduler.get_jobs():
        if job.id.startswith(f"event_{event_id}_reminder_"):
            scheduler.remove_job(job.id)


def cancel_event_check_in_jobs(event_id: int) -> None:
    from src.utils.scheduler import scheduler

    for job in scheduler.get_jobs():
        if job.id.startswith(f"event_{event_id}_check_in_"):
            scheduler.remove_job(job.id)


def cancel_event_start_jobs(event_id: int) -> None:
    from src.utils.scheduler import scheduler

    for job in scheduler.get_jobs():
        if job.id.startswith(f"event_{event_id}_start"):
            scheduler.remove_job(job.id)


def schedule_event_start_notification(event: Dict[str, Any]) -> None:
    from src.utils.scheduler import scheduler

    cancel_event_start_jobs(event["id"])
    starts_at = datetime.fromtimestamp(event["starts_at"], tz=timezone.utc)
    if starts_at <= datetime.now(timezone.utc):
        return

    scheduler.add_job(
        send_event_started,
        trigger="date",
        run_date=starts_at,
        args=[event["id"]],
        id=f"event_{event['id']}_start",
        replace_existing=True,
        misfire_grace_time=3600,
    )


def schedule_event_check_in_open(event: Dict[str, Any]) -> None:
    from src.utils.scheduler import scheduler

    cancel_event_check_in_jobs(event["id"])
    if not event.get("check_in_enabled"):
        return

    opens_minutes = int(event.get("check_in_opens_minutes") or 60)
    opens_at = datetime.fromtimestamp(event["starts_at"], tz=timezone.utc) - timedelta(
        minutes=opens_minutes
    )
    if opens_at <= datetime.now(timezone.utc):
        return

    scheduler.add_job(
        open_event_check_in,
        trigger="date",
        run_date=opens_at,
        args=[event["id"]],
        id=f"event_{event['id']}_check_in_open",
        replace_existing=True,
        misfire_grace_time=3600,
    )


async def open_event_check_in(event_id: int) -> None:
    from src.utils.bot_instance import get_bot
    from src.utils.database import get_language

    bot = get_bot()
    if bot is None:
        return

    db = await get_db()
    event = await db.get_event(event_id)
    if not event or event["status"] != "open" or not event.get("check_in_enabled"):
        return

    await refresh_event_message(bot, event_id)
    registrations = await db.get_event_registrations(event_id)
    for registration in registrations:
        if registration["status"] != "main":
            continue
        try:
            locale = await get_language(registration["user_id"])
            user = await bot.fetch_user(int(registration["user_id"]))
            await user.send(
                embed=build_event_notice_embed(
                    event,
                    locale,
                    "check_in_open_title",
                    "check_in_open_description",
                    bot,
                    tone="warning",
                )
            )
        except discord.DiscordException:
            continue


def schedule_event_reminders(event: Dict[str, Any]) -> None:
    from src.utils.scheduler import scheduler

    cancel_event_reminder_jobs(event["id"])
    now = datetime.now(timezone.utc)
    starts_at = datetime.fromtimestamp(event["starts_at"], tz=timezone.utc)
    for minutes in event.get("reminder_minutes", []):
        run_at = starts_at - timedelta(minutes=minutes)
        if run_at <= now:
            continue
        scheduler.add_job(
            send_event_reminder,
            trigger="date",
            run_date=run_at,
            args=[event["id"], minutes],
            id=f"event_{event['id']}_reminder_{minutes}",
            replace_existing=True,
            misfire_grace_time=3600,
        )


async def send_event_reminder(event_id: int, minutes: int) -> None:
    from src.utils.bot_instance import get_bot
    from src.utils.database import get_language

    bot = get_bot()
    if bot is None:
        return

    db = await get_db()
    event = await db.get_event(event_id)
    if not event or event["status"] != "open":
        return
    if minutes > 0 and datetime.now(timezone.utc).timestamp() >= event["starts_at"]:
        return

    registrations = await db.get_event_registrations(event_id)
    for registration in registrations:
        if registration["status"] not in {"main", "backup"}:
            continue
        try:
            locale = await get_language(registration["user_id"])
            user = await bot.fetch_user(int(registration["user_id"]))
            await user.send(
                embed=build_event_notice_embed(
                    event,
                    locale,
                    "reminder_title",
                    "reminder_description",
                    bot,
                    tone="info",
                    minutes=minutes,
                    status=registration["status"],
                )
            )
        except discord.DiscordException:
            continue


async def send_event_started(event_id: int) -> None:
    from src.utils.bot_instance import get_bot
    from src.utils.database import get_language

    bot = get_bot()
    if bot is None:
        return

    db = await get_db()
    event = await db.get_event(event_id)
    if not event or event["status"] != "open":
        return
    if event["status"] == "open":
        await db.set_event_status(event_id, "started")
        event = await db.get_event(event_id)
        await refresh_event_message(bot, event_id)

    registrations = await db.get_event_registrations(event_id)
    for registration in registrations:
        if registration["status"] not in {"main", "backup"}:
            continue
        try:
            locale = await get_language(registration["user_id"])
            user = await bot.fetch_user(int(registration["user_id"]))
            await user.send(
                embed=build_event_notice_embed(
                    event,
                    locale,
                    "started_title",
                    "started_dm_description",
                    bot,
                    tone="success",
                    status=registration["status"],
                )
            )
        except discord.DiscordException:
            continue


async def notify_event_cancelled(event_id: int, reason: Optional[str] = None) -> None:
    from src.utils.bot_instance import get_bot
    from src.utils.database import get_language

    bot = get_bot()
    if bot is None:
        return

    db = await get_db()
    event = await db.get_event(event_id)
    if not event:
        return

    registrations = await db.get_event_registrations(event_id)
    for registration in registrations:
        try:
            locale = await get_language(registration["user_id"])
            user = await bot.fetch_user(int(registration["user_id"]))
            await user.send(
                embed=build_event_notice_embed(
                    event,
                    locale,
                    "cancelled_title",
                    "cancelled_description",
                    bot,
                    tone="failed",
                    reason=reason or "-",
                )
            )
        except discord.DiscordException:
            continue


def build_event_notice_embed(
    event: Dict[str, Any],
    locale: str,
    title_key: str,
    description_key: str,
    ctx: Any = None,
    *,
    tone: str = "info",
    **kwargs: Any,
) -> discord.Embed:
    colors = {
        "info": bot_config.embeds.info_color,
        "success": bot_config.embeds.success_color,
        "warning": get_warning_color(),
        "failed": bot_config.embeds.failed_color,
    }
    if "minutes" in kwargs:
        minutes = int(kwargs["minutes"])
        kwargs["when_text"] = event_text(
            "reminder_when_start" if minutes == 0 else "reminder_when_minutes",
            locale,
            minutes=minutes,
        )
    description = event_text(
        description_key,
        locale,
        title=event["title"],
        time=f"<t:{int(event['starts_at'])}:F>",
        relative_time=f"<t:{int(event['starts_at'])}:R>",
        calendar_url=build_calendar_url(event),
        event_link=(
            f"[{event_text('event_panel_link', locale)}]({build_event_message_url(event)})"
            if build_event_message_url(event)
            else "-"
        ),
        **kwargs,
    )
    embed = discord.Embed(
        title=event_text(title_key, locale),
        description=description,
        color=colors.get(tone, bot_config.embeds.info_color),
    )
    embed.set_footer(text=bot_config.bot.trademark, icon_url=get_embed_icon(ctx))
    return embed


def build_event_response_embed(
    key: str,
    locale: str,
    ctx: Any,
    *,
    tone: str = "success",
) -> discord.Embed:
    colors = {
        "success": bot_config.embeds.success_color,
        "info": bot_config.embeds.info_color,
        "default": bot_config.embeds.default_color,
        "failed": bot_config.embeds.failed_color,
    }
    title_keys = {
        "success": "common.success",
        "info": "common.info",
        "default": "common.info",
        "failed": "common.error",
    }
    locale = str(locale).split("-")[0]
    embed = discord.Embed(
        title=_(title_keys.get(tone, "common.info"), locale),
        description=event_text(key, locale),
        color=colors.get(tone, bot_config.embeds.default_color),
    )
    embed.set_footer(text=bot_config.bot.trademark, icon_url=get_embed_icon(ctx))
    return embed


def event_text(key: str, locale: str, **kwargs: Any) -> str:
    locale = str(locale).split("-")[0]
    text = _(f"events.{key}", locale)
    try:
        return text.format(**kwargs)
    except Exception:
        return text
