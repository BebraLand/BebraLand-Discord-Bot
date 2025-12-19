"""
Register persistent views for temp voice channels.
This ensures views work after bot restarts.
"""
import discord
from src.utils.logger import get_cool_logger
from src.utils.database import get_db
from src.features.temp_voice_channels.view.TempVoiceControlPanel import TempVoiceControlPanel
from src.features.temp_voice_channels.view.TempVoiceSettingsPanel import TempVoiceSettingsPanel
import config.constants as constants

logger = get_cool_logger(__name__)


async def register_persistent_temp_voice_views(bot: discord.Bot):
    """
    Register persistent views for all active temp voice channels.
    This should be called on bot startup to restore functionality after restarts.
    """
    try:
        db = await get_db()
        channels = await db.get_all_temp_voice_channels()
        
        registered_count = 0
        for channel_data in channels:
            try:
                channel_id = channel_data["channel_id"]
                owner_id = int(channel_data["owner_id"])
                
                # Create persistent views
                control_view = TempVoiceControlPanel(channel_id, owner_id)
                settings_view = TempVoiceSettingsPanel(channel_id, owner_id)
                
                # Register views with bot
                bot.add_view(control_view)
                if constants.TEMP_VOICE_SETTINGS_ENABLED:
                    bot.add_view(settings_view)
                
                registered_count += 1
                
            except Exception as e:
                logger.error(f"Failed to register views for temp channel {channel_data.get('channel_id')}: {e}")
        
        if registered_count > 0:
            logger.info(f"Registered persistent views for {registered_count} temp voice channels")
        
    except Exception as e:
        logger.error(f"Failed to register persistent temp voice views: {e}")
