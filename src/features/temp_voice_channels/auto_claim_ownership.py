import discord
from typing import Optional
import src.languages.lang_constants as lang_constants
from src.utils.database import get_db
from src.utils.logger import get_cool_logger
from src.features.temp_voice_channels.transfer_ownership import transfer_ownership

logger = get_cool_logger(__name__)

async def auto_claim_ownership(channel_id: int, guild: discord.Guild) -> Optional[int]:
    """
    Automatically transfer ownership to the next user in the channel.
    
    Args:
        channel_id: ID of the channel
        guild: The guild where the channel is located
        
    Returns:
        ID of the new owner or None if no one to transfer to
    """
    try:
        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            return None

        if len(channel.members) == 0:
            return None

        # Get first member in channel as new owner
        new_owner = channel.members[0]
        
        # Check if ownership actually needs to change
        storage = await get_db()
        temp_vc = await storage.get_temp_voice_channel(channel_id)
        
        if temp_vc and temp_vc.get("owner_id") == new_owner.id:
            # Owner is already the same person, no need to transfer
            return new_owner.id
        
        success = await transfer_ownership(channel_id, new_owner.id, guild)
        if success:
            # Update channel name if it contains old owner's name
            if temp_vc and temp_vc.get("owner_id"):
                old_owner_id = temp_vc.get("owner_id")
                old_owner = guild.get_member(old_owner_id)
                if old_owner and old_owner.display_name in channel.name:
                    try:
                        new_name = channel.name.replace(old_owner.display_name, new_owner.display_name)
                        await channel.edit(name=new_name)
                        logger.info(f"Updated channel name to: {new_name}")
                    except Exception as e:
                        logger.error(f"{lang_constants.ERROR_EMOJI} Error updating channel name: {e}")
            
            # Update control panel message
            if temp_vc and temp_vc.get("control_message_id"):
                try:
                    message = await channel.fetch_message(temp_vc["control_message_id"])
                    
                    # Update view with new owner
                    from features.temp_voice_channels.views.TempVoiceControlView import TempVoiceControlView
                    view = TempVoiceControlView(channel_id, new_owner.id)
                    
                    # Update embed
                    embed = message.embeds[0] if message.embeds else None
                    if embed:
                        embed.description = f"Ownership transferred to {new_owner.mention}!\n\nUse the buttons below to control your channel."
                        await message.edit(embed=embed, view=view)
                except Exception as e:
                    logger.error(f"{lang_constants.ERROR_EMOJI} Error updating control panel message: {e}")
            return new_owner.id
        
        
        return None

    except Exception as e:
        logger.error(f"{lang_constants.ERROR_EMOJI} Error auto-claiming ownership: {e}")
        return None