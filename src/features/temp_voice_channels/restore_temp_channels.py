import discord

import src.languages.lang_constants as lang_constants
from src.features.temp_voice_channels.cleanup_orphaned_channels import (
    cleanup_orphaned_channels,
)
from src.features.temp_voice_channels.delete_temp_channel import delete_temp_channel
from src.utils.database import get_db
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


async def restore_temp_channels(bot):
    """
    Restore temp voice channels from database on bot startup.
    Re-register persistent views for control panels.

    Args:
        bot: The Discord bot instance
    """
    try:
        from src.features.temp_voice_channels.views.TempVoiceControlView import (
            TempVoiceControlView,
        )

        storage = await get_db()

        # Get all guilds
        for guild in bot.guilds:
            # Clean up orphaned channels first
            await cleanup_orphaned_channels(guild)

            # Get all temp channels for this guild
            temp_channels = await storage.get_all_temp_voice_channels(guild.id)

            for temp_vc in temp_channels:
                channel_id = temp_vc.get("channel_id")
                owner_id = temp_vc.get("owner_id")
                control_message_id = temp_vc.get("control_message_id")

                channel = guild.get_channel(channel_id)
                if channel and isinstance(channel, discord.VoiceChannel):
                    # Re-register view if control message exists
                    if control_message_id:
                        try:
                            await channel.fetch_message(control_message_id)
                            view = TempVoiceControlView(channel_id, owner_id)
                            bot.add_view(view, message_id=control_message_id)
                        except Exception:
                            pass

                    # Check if channel is empty and schedule deletion
                    if len(channel.members) == 0:
                        import asyncio

                        asyncio.create_task(
                            delete_temp_channel(channel_id, guild, "Empty on startup")
                        )

        logger.info(
            f"{lang_constants.SUCCESS_EMOJI} Temp voice channels restored successfully"
        )

    except Exception as e:
        logger.error(f"{lang_constants.ERROR_EMOJI} Error restoring temp channels: {e}")
