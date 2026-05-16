from datetime import datetime
from typing import Any, Dict, Optional

import discord

from config.config import config as bot_config

EMBED_DATA_KEYS = {
    "title",
    "description",
    "url",
    "author",
    "footer",
    "thumbnail",
    "image",
    "fields",
    "timestamp",
    "color",
}


def replace_placeholders(data: Any, replacements: Dict[str, Any]) -> Any:
    """
    Recursively replace placeholders in strings, dicts, and lists.

    data: Any nested structure containing strings to process
    replacements: mapping of placeholder -> value
    """
    if isinstance(data, str):
        for placeholder, value in replacements.items():
            if value is not None:
                data = data.replace(placeholder, str(value))
        return data
    if isinstance(data, dict):
        return {k: replace_placeholders(v, replacements) for k, v in data.items()}
    if isinstance(data, list):
        return [replace_placeholders(v, replacements) for v in data]
    return data


def build_news_placeholders(
    content_text: str, bot_avatar: str = "", image_url: str = ""
) -> Dict[str, str]:
    """Build the standard placeholder mapping used by news-style embeds."""
    return {
        "{content}": content_text,
        "content": content_text,
        "{bot_avatar}": bot_avatar,
        "bot_avatar": bot_avatar,
        "{image_url}": image_url,
        "image_url": image_url,
    }


def build_embed_from_data(
    data: Dict[str, Any], default_color: Optional[int] = bot_config.embeds.default_color
) -> discord.Embed:
    """
    Build a Discord embed from a processed JSON-like dict.
    Supports optional keys: title, description, url, author, footer,
    thumbnail, image, fields, timestamp, color.
    """
    # Color handling
    color = default_color
    if "color" in data:
        color_value = data["color"]
        if isinstance(color_value, str):
            try:
                color = int(color_value.lstrip("#"), 16)
            except Exception:
                color = default_color
        elif isinstance(color_value, int):
            color = color_value

    embed = discord.Embed(color=color) if color is not None else discord.Embed()

    # Simple properties
    title = data.get("title")
    if title:
        embed.title = title

    description = data.get("description")
    if description:
        embed.description = description

    url = data.get("url")
    if url:
        embed.url = url

    # Author
    author = data.get("author")
    if isinstance(author, dict) and author.get("name"):
        embed.set_author(
            name=author.get("name"),
            url=author.get("url"),
            icon_url=author.get("icon_url"),
        )

    # Footer
    footer = data.get("footer")
    if isinstance(footer, dict) and footer.get("text"):
        embed.set_footer(text=footer.get("text"), icon_url=footer.get("icon_url"))

    # Thumbnail
    thumb = data.get("thumbnail")
    if isinstance(thumb, dict):
        turl = thumb.get("url")
        if turl:
            embed.set_thumbnail(url=turl)

    # Image
    image = data.get("image")
    if isinstance(image, dict):
        iurl = image.get("url")
        if iurl:
            embed.set_image(url=iurl)

    # Fields
    fields = data.get("fields")
    if isinstance(fields, list):
        for field in fields:
            if isinstance(field, dict) and field.get("name") and field.get("value"):
                embed.add_field(
                    name=field.get("name"),
                    value=field.get("value"),
                    inline=bool(field.get("inline", False)),
                )

    # Timestamp (seconds or milliseconds)
    ts = data.get("timestamp")
    if isinstance(ts, (int, float)):
        if ts > 10000000000:  # ms
            ts = ts / 1000.0
        embed.timestamp = datetime.utcfromtimestamp(ts)

    return embed


def build_embeds_from_message_data(
    data: Dict[str, Any],
    replacements: Optional[Dict[str, Any]] = None,
    default_color: Optional[int] = bot_config.embeds.default_color,
    fallback: Optional[Dict[str, Any]] = None,
    max_embeds: int = 10,
) -> list[discord.Embed]:
    """
    Build embeds from Discord-style message JSON.

    Supports:
    - {"embeds": [{...}, ...]}
    - {"embed": {...}}
    - direct embed data: {"title": "...", "description": "..."}
    """
    processed = replace_placeholders(data, replacements or {})

    raw_embeds = processed.get("embeds")
    if isinstance(raw_embeds, list):
        embeds = [
            build_embed_from_data(embed_data, default_color=default_color)
            for embed_data in raw_embeds[:max_embeds]
            if isinstance(embed_data, dict)
        ]
        if embeds:
            return embeds

    raw_embed = processed.get("embed")
    if isinstance(raw_embed, dict):
        return [build_embed_from_data(raw_embed, default_color=default_color)]

    has_embed_keys = any(key in processed for key in EMBED_DATA_KEYS)
    if "embeds" not in processed and "embed" not in processed and has_embed_keys:
        return [build_embed_from_data(processed, default_color=default_color)]

    if fallback is not None:
        fallback_data = replace_placeholders(fallback, replacements or {})
        return [build_embed_from_data(fallback_data, default_color=default_color)]

    return []


def build_embed_from_template(
    template: Dict[str, Any],
    replacements: Dict[str, Any],
    default_footer: Optional[bool] = None,
) -> discord.Embed:
    """
    Apply replacements to a template and build an embed.
    If default_footer is True, override template footer using sensible defaults:
    - text: bot_config.bot.trademark
    - icon_url: derived from replacements ("{bot_avatar}" or "bot_avatar") when available
    """
    processed = replace_placeholders(template, replacements)

    if default_footer:
        processed["footer"] = {
            "text": bot_config.bot.trademark,
            "icon_url": replacements.get("{bot_avatar}")
            or replacements.get("bot_avatar"),
        }

    return build_embed_from_data(processed)


def get_embed_icon(ctx) -> str:
    """Return an avatar URL to use in embed footers.

    Accepts various context-like objects: ApplicationContext, Interaction,
    a `discord.Bot`/`discord.Client`, `discord.Guild`, or `discord.User`/`Member`.

    Priority:
    1. `bot_config.embeds.footer_icon` constant if set
    2. Bot user's `display_avatar` / `avatar`
    3. Guild bot member avatar (if available)
    4. Empty string fallback
    """
    if bot_config.embeds.footer_icon:
        return bot_config.embeds.footer_icon

    bot_user = None

    # If caller passed a User/Member/ClientUser directly (check this first)
    if isinstance(ctx, (discord.User, discord.Member, discord.ClientUser)):
        bot_user = ctx
    # If caller passed a bot/client instance
    elif isinstance(ctx, (discord.Client, discord.Bot)):
        bot_user = getattr(ctx, "user", None)
    # If ctx is None, return empty string early
    elif ctx is None:
        return ""
    else:
        # If caller passed an ApplicationContext or Interaction
        bot = getattr(ctx, "bot", None) or getattr(ctx, "client", None)
        if bot:
            bot_user = getattr(bot, "user", None)

    # Try to return bot user's avatar
    if bot_user is not None:
        for attr in ("display_avatar", "avatar", "default_avatar"):
            try:
                avatar = getattr(bot_user, attr, None)
                if avatar is not None:
                    return avatar.url
            except Exception:
                continue

    # Fallback: if a guild-like object was passed, try its member avatar
    guild = getattr(ctx, "guild", None)
    if guild is not None:
        me = getattr(guild, "me", None)
        if me is not None:
            for attr in ("display_avatar", "avatar", "default_avatar"):
                try:
                    avatar = getattr(me, attr, None)
                    if avatar is not None:
                        return avatar.url
                except Exception:
                    continue

    return ""
