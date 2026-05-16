import json

import discord
from discord.ext import commands

from config.config import config as bot_config
from src.utils.embeds import build_embeds_from_message_data
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)

WELCOME_MESSAGE_PATH = "src/languages/messages/welcome.json"


def _avatar_url(user) -> str:
    avatar = getattr(user, "avatar", None) or getattr(user, "default_avatar", None)
    return getattr(avatar, "url", "") if avatar else ""


def _load_welcome_message() -> tuple[dict | None, str | None, str | None]:
    try:
        with open(WELCOME_MESSAGE_PATH, "r", encoding="utf-8") as f:
            return json.load(f), None, None
    except FileNotFoundError:
        logger.error(f"Welcome message config not found: {WELCOME_MESSAGE_PATH}")
        return None, None, WELCOME_MESSAGE_PATH
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse {WELCOME_MESSAGE_PATH}: {e}")
        return None, None, WELCOME_MESSAGE_PATH


def _welcome_replacements(member: discord.Member, bot: commands.Bot = None) -> dict:
    bot_user = getattr(bot, "user", None) if bot else None
    return {
        "{guild_name}": member.guild.name,
        "{member_name}": member.display_name,
        "{member_mention}": member.mention,
        "{member_avatar}": _avatar_url(member),
        "{bot_avatar}": _avatar_url(bot_user) if bot_user else "",
        "{member_count}": str(member.guild.member_count),
        "{trademark}": bot_config.bot.trademark,
        "guild_name": member.guild.name,
        "member_name": member.display_name,
        "member_mention": member.mention,
        "member_avatar": _avatar_url(member),
        "bot_avatar": _avatar_url(bot_user) if bot_user else "",
        "member_count": str(member.guild.member_count),
        "trademark": bot_config.bot.trademark,
    }


def create_welcome_embeds(member: discord.Member, bot: commands.Bot = None):
    """
    Creates Discord embeds from welcome JSON with dynamic placeholder replacement.

    Returns:
        tuple: (embeds, error_message, error_file_path)
    """
    welcome_message, error_message, error_path = _load_welcome_message()
    if welcome_message is None:
        return [], error_message, error_path

    try:
        embeds = build_embeds_from_message_data(
            welcome_message,
            replacements=_welcome_replacements(member, bot),
            default_color=None,
        )
        return embeds, None, None
    except Exception as e:
        logger.error(f"Error creating welcome embeds: {e}")
        return [], str(e), None


def create_welcome_embed(member: discord.Member, bot: commands.Bot = None):
    """
    Backward-compatible single-embed wrapper.

    Returns:
        tuple: (embed, error_message, error_file_path)
    """
    embeds, error_message, error_path = create_welcome_embeds(member, bot)
    return (embeds[0] if embeds else None), error_message, error_path


async def sent_welcome_message(member: discord.Member, bot: commands.Bot = None):
    embeds, error_message, _ = create_welcome_embeds(member, bot)
    try:
        if embeds:
            await member.send(embeds=embeds)
        else:
            await member.send(error_message or "Welcome to the server!")
        logger.info(f"Sent welcome message to {member.name}({member.id})")
    except discord.Forbidden:
        logger.warning(f"Can't send DM to {member.name}({member.id}) (forbidden).")
