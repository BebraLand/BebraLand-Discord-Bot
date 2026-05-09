from typing import Any, Dict, List, Optional

import discord

from config.config import config as bot_config
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


def format_user_list(registrations: List[Dict[str, Any]], status: str) -> str:
    users = [item for item in registrations if item["status"] == status]
    if not users:
        return "-"
    lines = []
    for index, item in enumerate(users[:20], start=1):
        lines.append(f"{index}. <@{item['user_id']}>")
    if len(users) > 20:
        lines.append(f"... +{len(users) - 20}")
    return "\n".join(lines)


async def build_event_embed(
    event: Dict[str, Any],
    bot: Optional[discord.Client] = None,
) -> discord.Embed:
    db = await get_db()
    registrations = await db.get_event_registrations(event["id"])
    main_count = len([r for r in registrations if r["status"] == "main"])
    backup_count = len([r for r in registrations if r["status"] == "backup"])
    languages = ", ".join(
        locale_display_name(language) for language in event["languages"]
    )

    embed_data = {
        "title": event["title"],
        "description": event["description"],
        "color": bot_config.embeds.default_color,
        "fields": [
            {
                "name": "Time",
                "value": f"<t:{int(event['starts_at'])}:F> (<t:{int(event['starts_at'])}:R>)",
                "inline": False,
            },
            {
                "name": "Languages",
                "value": languages or "-",
                "inline": True,
            },
            {
                "name": "Players",
                "value": f"{main_count}/{event['player_limit']}",
                "inline": True,
            },
            {
                "name": "Backup",
                "value": str(backup_count),
                "inline": True,
            },
            {
                "name": "Main",
                "value": format_user_list(registrations, "main"),
                "inline": False,
            },
            {
                "name": "Backup list",
                "value": format_user_list(registrations, "backup"),
                "inline": False,
            },
        ],
        "footer": {
            "text": f"Event #{event['id']} | {event['status'].title()}",
            "icon_url": get_embed_icon(bot),
        },
    }
    return build_embed_from_data(embed_data)


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

        view = EventRegistrationView(event_id, disabled=event["status"] != "open")
        await message.edit(embed=await build_event_embed(event, bot), view=view)
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
    if not event:
        return False

    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.DiscordException:
            return False

    message = await channel.send(
        embed=await build_event_embed(event, bot),
        view=EventRegistrationView(event_id),
    )
    await db.update_event_message(event_id, channel.id, message.id)
    bot.add_view(EventRegistrationView(event_id), message_id=message.id)
    return True


def build_event_response_embed(
    key: str,
    locale: str,
    ctx: Any,
    *,
    success: bool = True,
) -> discord.Embed:
    color = (
        bot_config.embeds.success_color
        if success
        else bot_config.embeds.failed_color
    )
    title_key = "common.success" if success else "common.info"
    locale = str(locale).split("-")[0]
    embed = discord.Embed(
        title=_(title_key, locale),
        description=event_text(key, locale),
        color=color,
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
