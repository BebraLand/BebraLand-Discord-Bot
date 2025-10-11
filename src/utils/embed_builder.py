import discord
from datetime import datetime
from typing import Any, Dict, Optional

import config.constants as constants


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
        if ts > 10000000000:  # ms
            ts = ts / 1000.0
        embed.timestamp = datetime.utcfromtimestamp(ts)

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