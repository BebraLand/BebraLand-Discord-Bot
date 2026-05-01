import discord
from discord.ext import commands
from src.utils.logger import get_cool_logger
import config.constants as constants
import json
from src.utils.embeds import build_embed_from_template

logger = get_cool_logger(__name__)


def create_welcome_embed(member: discord.Member, bot: commands.Bot = None):
    """
    Creates a Discord embed from a JSON template with dynamic placeholder replacement.

    Args:
        member: Discord member object

    Returns:
        tuple: (embed, error_message, error_file_path)
    """
    try:
        with open(
            "src/languages/messages/welcome_message.json", "r", encoding="utf-8"
        ) as f:
            welcome_message = json.load(f)
    except FileNotFoundError:
        logger.error("Error: welcome_message.json not found!")
        return None, None, "src/languages/messages/welcome_message.json"
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing welcome_message.json: {e}")
        return None, None, "src/languages/messages/welcome_message.json"

    trademark_text = constants.DISCORD_MESSAGE_TRADEMARK
    override_footer = constants.WELCOME_FORCE_DEFAULT_FOOTER

    # Prepare replacement values
    replacements = {
        "{guild_name}": member.guild.name,
        "{member_name}": member.display_name,
        "{member_mention}": member.mention,
        "{member_avatar}": member.avatar.url
        if member.avatar
        else member.default_avatar.url,
        "{bot_avatar}": bot.user.avatar.url
        if bot and bot.user.avatar
        else (bot.user.default_avatar.url if bot else ""),
        "{member_count}": str(member.guild.member_count),
        "{trademark}": trademark_text,
    }

    # Build the Discord embed using reusable utility
    try:
        embed = build_embed_from_template(
            template=welcome_message,
            replacements=replacements,
            default_footer=override_footer,
        )
        return embed, None, None
    except Exception as e:
        logger.error(f"Error creating embed: {e}")
        return None, str(e), None


async def sent_welcome_message(member: discord.Member, bot: commands.Bot = None):
    embed, error_message, _ = create_welcome_embed(member, bot)
    try:
        if embed is not None:
            await member.send(embed=embed)
        else:
            await member.send(error_message or "Welcome to the server!")
        logger.info(f"✅ Sent welcome message to {member.name}({member.id})")
    except discord.Forbidden:
        logger.warning(f"⚠️ Can't send DM to {member.name}({member.id}) (forbidden).")
