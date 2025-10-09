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
    total_deleted = 0
    try:
        for channel in ctx.bot.private_channels:
            # Only process 1:1 DMs (skip group DMs if present)
            if isinstance(channel, discord.DMChannel):
                async for message in channel.history(limit=constants.CLEAR_COMMAND_LIMIT):
                    if message.author.id == ctx.bot.user.id:
                        try:
                            await message.delete()
                            total_deleted += 1
                        except discord.HTTPException:
                            pass
    except Exception as e:
        logger.exception("Failed to clear all DM messages", exc_info=e)
    return total_deleted
