import json
from typing import Any

import discord

from config.config import config as bot_config
from src.utils.embeds import (
    build_embed_from_data,
    build_embed_from_template,
    get_embed_icon,
    replace_placeholders,
)
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)

RULES_MESSAGE_PATH = "src/languages/messages/rules.json"


def _load_rules_message() -> dict:
    try:
        with open(RULES_MESSAGE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Rules message config not found: {RULES_MESSAGE_PATH}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse {RULES_MESSAGE_PATH}: {e}")

    return {
        "embed": {
            "title": "Rules unavailable",
            "description": "The rules message configuration could not be loaded.",
            "color": bot_config.embeds.failed_color,
        },
        "buttons": [],
    }


def _rules_replacements(source, message: dict) -> dict:
    links = message.get("links", {})
    bot_avatar = get_embed_icon(source)
    return {
        "{rules_url}": links.get("rules", ""),
        "{banned_words_url}": links.get("banned_words", ""),
        "{support_url}": links.get("support", ""),
        "{trademark}": bot_config.bot.trademark,
        "{bot_avatar}": bot_avatar,
        "rules_url": links.get("rules", ""),
        "banned_words_url": links.get("banned_words", ""),
        "support_url": links.get("support", ""),
        "trademark": bot_config.bot.trademark,
        "bot_avatar": bot_avatar,
    }


def build_rules_embed(source) -> discord.Embed:
    message = _load_rules_message()
    return build_embed_from_template(
        template=message.get("embed", {}),
        replacements=_rules_replacements(source, message),
    )


def build_rules_embeds(source) -> list[discord.Embed]:
    message = _load_rules_message()
    replacements = _rules_replacements(source, message)

    if isinstance(message.get("embeds"), list):
        embeds = []
        for embed_data in message["embeds"][:10]:
            if isinstance(embed_data, dict):
                processed = replace_placeholders(embed_data, replacements)
                embeds.append(build_embed_from_data(processed, default_color=None))

        if embeds:
            return embeds

    return [build_rules_embed(source)]


def _iter_link_buttons(message: dict[str, Any]):
    for button in message.get("buttons", []):
        if isinstance(button, dict):
            yield button

    for row in message.get("components", []):
        if not isinstance(row, dict) or row.get("type") != 1:
            continue

        for component in row.get("components", []):
            if (
                isinstance(component, dict)
                and component.get("type") == 2
                and component.get("style") == 5
            ):
                yield component


class RulesView(discord.ui.View):
    def __init__(self, source=None):
        super().__init__(timeout=None)
        message = _load_rules_message()
        replacements = _rules_replacements(source, message)

        for button in _iter_link_buttons(message):
            label = button.get("label")
            url = button.get("url")
            if not label or not url:
                continue

            for placeholder, value in replacements.items():
                url = url.replace(placeholder, str(value))

            self.add_item(
                discord.ui.Button(
                    label=label,
                    style=discord.ButtonStyle.link,
                    url=url,
                    emoji=self._button_emoji(button.get("emoji")),
                )
            )

    @staticmethod
    def _button_emoji(emoji):
        if isinstance(emoji, dict):
            return emoji.get("name")
        if isinstance(emoji, str):
            return emoji
        return None
