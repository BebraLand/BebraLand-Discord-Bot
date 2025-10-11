import discord
from typing import Optional
from src.utils.logger import get_cool_logger
import config.constants as constants

logger = get_cool_logger(__name__)


async def clear_dm_messages(
    ctx: discord.ApplicationContext,
    target_user: Optional[discord.abc.User] = None,
):
    # Use the provided target_user if given (admin use-case), otherwise the invoking user
    user = target_user or ctx.user
    dm_channel = await user.create_dm()

    deleted_count = 0
    try:
        async for message in dm_channel.history(limit=constants.CLEAR_COMMAND_LIMIT):
            if message.author.id == ctx.bot.user.id:
                try:
                    await message.delete()
                    deleted_count += 1
                except discord.HTTPException:
                    # Ignore messages that can't be deleted (permissions/age/etc.)
                    pass
    except Exception as e:
        logger.exception("Failed to clear DM messages", exc_info=e)
    return deleted_count


async def clear_all_dm_messages(
    ctx: discord.ApplicationContext,
):
    """
    Clear the bot's DM messages with users from the current guild only.

    This restricts the clearing scope to members of the guild where
    the command was invoked, rather than all existing DM channels.
    """
    total_deleted = 0
    try:
        # Ensure the command was invoked in a guild context
        if not ctx.guild:
            return 0

        # Iterate over members of the current guild, skipping bots
        for member in ctx.guild.members:
            if member.bot:
                continue

            # Open or get DM channel with the member
            dm_channel = await member.create_dm()

            # Delete messages authored by this bot in that DM
            async for message in dm_channel.history(limit=constants.CLEAR_COMMAND_LIMIT):
                if message.author.id == ctx.bot.user.id:
                    try:
                        await message.delete()
                        total_deleted += 1
                    except discord.HTTPException:
                        # Skip messages that cannot be deleted
                        pass
    except Exception as e:
        logger.exception("Failed to clear all DM messages for current guild", exc_info=e)
    return total_deleted
