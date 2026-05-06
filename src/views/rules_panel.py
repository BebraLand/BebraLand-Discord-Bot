import json

import discord

import config.constants as constants
from src.utils.embeds import build_embed_from_template, get_embed_icon
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
            "color": constants.FAILED_EMBED_COLOR,
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
        "{trademark}": constants.DISCORD_MESSAGE_TRADEMARK,
        "{bot_avatar}": bot_avatar,
        "rules_url": links.get("rules", ""),
        "banned_words_url": links.get("banned_words", ""),
        "support_url": links.get("support", ""),
        "trademark": constants.DISCORD_MESSAGE_TRADEMARK,
        "bot_avatar": bot_avatar,
    }


def build_rules_embed(source) -> discord.Embed:
    message = _load_rules_message()
    return build_embed_from_template(
        template=message.get("embed", {}),
        replacements=_rules_replacements(source, message),
    )


class RulesView(discord.ui.View):
    def __init__(self, source=None):
        super().__init__(timeout=None)
        message = _load_rules_message()
        replacements = _rules_replacements(source, message)

        for button in message.get("buttons", []):
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
                )
            )
