import discord
import src.languages.lang_constants as lang_constants
from src.utils.database import get_db
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


async def cleanup_orphaned_channels(guild: discord.Guild):
    """
    Clean up temp voice channels that are in the database but no longer exist in Discord.
    Only removes DB entries for channels that don't exist anymore.

    Args:
        guild: The guild to clean up
    """
    try:
        storage = await get_db()
        all_temp_channels = await storage.get_all_temp_voice_channels(guild.id)

        for temp_vc in all_temp_channels:
            channel_id = temp_vc.get("channel_id")
            channel = guild.get_channel(channel_id)

            if not channel:
                # Channel doesn't exist in Discord, remove from database
                logger.info(
                    f"{lang_constants.INFO_EMOJI} Cleaning up orphaned DB entry for temp voice channel ID {channel_id}"
                )
                await storage.delete_temp_voice_channel(channel_id)

    except Exception as e:
        logger.error(
            f"{lang_constants.ERROR_EMOJI} Error cleaning up orphaned channels: {e}"
        )
