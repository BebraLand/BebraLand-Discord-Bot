import discord
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

import config.constants as constants

# Threshold to distinguish between timestamps in seconds vs milliseconds
# Timestamps greater than this value are assumed to be in milliseconds
TIMESTAMP_MS_THRESHOLD = 10000000000


def get_bot_avatar_url(bot: Union[discord.Bot, discord.Client, discord.User, None]) -> str:
    """
    Get the bot avatar URL consistently.
    
    Args:
        bot: Bot instance, client, user object, or None
        
    Returns:
        str: Avatar URL or empty string if not available
    """
    if bot is None:
        return ""
    
    # Handle Bot or Client instances
    bot_user = getattr(bot, "user", bot)
    
    if bot_user is None:
        return ""
    
    if hasattr(bot_user, "avatar") and bot_user.avatar:
        return bot_user.avatar.url
    elif hasattr(bot_user, "default_avatar"):
        return bot_user.default_avatar.url
    
    return ""


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


def build_embed_from_data(data: Dict[str, Any]) -> discord.Embed:
    """
    Build a Discord embed from a processed JSON-like dict.
    Supports optional keys: title, description, url, author, footer,
    thumbnail, image, fields, timestamp, color.
    """
    # Color handling
    color = constants.DISCORD_EMBED_COLOR
    if "color" in data:
        color_value = data["color"]
        if isinstance(color_value, str):
            try:
                color = int(color_value.lstrip('#'), 16)
            except Exception:
                color = constants.DISCORD_EMBED_COLOR
        elif isinstance(color_value, int):
            color = color_value

    embed = discord.Embed(color=color)

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
        if ts > TIMESTAMP_MS_THRESHOLD:  # milliseconds
            ts = ts / 1000.0
        embed.timestamp = datetime.fromtimestamp(ts, tz=timezone.utc)

    return embed


def build_embed_from_template(
    template: Dict[str, Any],
    replacements: Dict[str, Any],
    default_footer: Optional[bool] = None,
) -> discord.Embed:
    """
    Apply replacements to a template and build an embed.
    If default_footer is True, override template footer using sensible defaults:
    - text: constants.DISCORD_MESSAGE_TRADEMARK
    - icon_url: derived from replacements ("{bot_avatar}" or "bot_avatar") when available
    """
    processed = replace_placeholders(template, replacements)

    if default_footer:
        processed["footer"] = {
            "text": constants.DISCORD_MESSAGE_TRADEMARK,
            "icon_url": replacements.get("{bot_avatar}") or replacements.get("bot_avatar"),
        }

    return build_embed_from_data(processed)


def build_news_embed(
    content_text: str,
    bot: Union[discord.Bot, discord.Client, None],
    embed_json: Optional[Dict[str, Any]] = None,
    image_url: str = "",
    use_default_footer: bool = True,
) -> Optional[discord.Embed]:
    """
    Build an embed for news broadcasts with consistent handling across the codebase.
    
    Args:
        content_text: The news content text
        bot: Bot instance for avatar URL
        embed_json: Optional custom embed JSON structure with placeholders
        image_url: Optional image URL (e.g., "attachment://filename.png")
        use_default_footer: Whether to add default footer
        
    Returns:
        discord.Embed or None if building fails
    """
    bot_avatar = get_bot_avatar_url(bot)
    
    replacements = {
        "{content}": content_text,
        "content": content_text,
        "{bot_avatar}": bot_avatar,
        "bot_avatar": bot_avatar,
        "{image_url}": image_url,
        "image_url": image_url,
    }
    
    # Prefer explicit embed JSON if provided
    if embed_json and isinstance(embed_json, dict):
        try:
            processed = replace_placeholders(embed_json, replacements)
            if use_default_footer:
                processed["footer"] = {
                    "text": constants.DISCORD_MESSAGE_TRADEMARK,
                    "icon_url": bot_avatar,
                }
            return build_embed_from_data(processed)
        except Exception:
            return None
    
    # Build a simple default embed
    try:
        default_data = {
            "description": content_text,
        }
        if image_url:
            default_data["image"] = {"url": image_url}
        if use_default_footer:
            default_data["footer"] = {
                "text": constants.DISCORD_MESSAGE_TRADEMARK,
                "icon_url": bot_avatar,
            }
        return build_embed_from_data(default_data)
    except Exception:
        return None