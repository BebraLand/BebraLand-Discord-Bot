import discord

import config.constants as constants
import src.languages.lang_constants as lang_constants
from src.utils.database import get_db
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


async def delete_temp_channel(
    channel_id: int, guild: discord.Guild, reason: str = "Channel empty"
):
    """
    Delete a temporary voice channel after a delay.

    Args:
        channel_id: ID of the channel to delete
        guild: The guild where the channel is located
        reason: Reason for deletion
    """
    import asyncio

    try:
        # Wait before deleting
        await asyncio.sleep(constants.DELETE_EMPTY_TEMP_VOICE_CHANNELS_AFTER_SECONDS)

        channel = guild.get_channel(channel_id)
        if channel and isinstance(channel, discord.VoiceChannel):
            # Check if still empty
            if len(channel.members) == 0:
                # Delete from Discord first
                try:
                    await channel.delete(reason=reason)
                    logger.info(
                        f"{lang_constants.SUCCESS_EMOJI} Deleted temp voice channel {channel.name} ({channel.id}) - {reason}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error deleting channel {channel_id} from Discord: {e}"
                    )

                # Remove from database (even if Discord deletion failed, to prevent orphaned DB entries)
                storage = await get_db()
                await storage.delete_temp_voice_channel(channel_id)
        else:
            # Channel doesn't exist in Discord, just remove from database
            storage = await get_db()
            await storage.delete_temp_voice_channel(channel_id)
            logger.info(
                f"{lang_constants.INFO_EMOJI} Removed temp voice channel {channel_id} from database (channel not found in Discord)"
            )

    except Exception as e:
        logger.error(f"Error deleting temp channel: {e}")
