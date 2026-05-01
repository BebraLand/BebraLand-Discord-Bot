import discord
import src.languages.lang_constants as lang_constants
from src.utils.database import get_db
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


async def transfer_ownership(
    channel_id: int, new_owner_id: int, guild: discord.Guild
) -> bool:
    """
    Transfer ownership of a temp voice channel.

    Args:
        channel_id: ID of the channel
        new_owner_id: ID of the new owner
        guild: The guild where the channel is located

    Returns:
        True if successful, False otherwise
    """
    try:
        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            return False

        new_owner = guild.get_member(new_owner_id)
        if not new_owner:
            return False

        # Get old owner to remove their manage_channels permission
        storage = await get_db()
        temp_vc = await storage.get_temp_voice_channel(channel_id)
        old_owner_id = temp_vc.get("owner_id") if temp_vc else None

        # Update database
        await storage.update_temp_voice_channel(channel_id, owner_id=new_owner_id)

        # Remove manage_channels from old owner (if they're still in the server)
        if old_owner_id:
            old_owner = guild.get_member(old_owner_id)
            if old_owner:
                await channel.set_permissions(
                    old_owner,
                    view_channel=True,
                    connect=True,
                    speak=True,
                    manage_channels=False,
                )

        # Give full control to new owner including manage_channels
        await channel.set_permissions(
            new_owner, view_channel=True, connect=True, speak=True, manage_channels=True
        )

        logger.info(
            f"{lang_constants.SUCCESS_EMOJI} Transferred ownership of temp voice channel {channel.name} ({channel.id}) to {new_owner}"
        )

        return True

    except Exception as e:
        logger.error(f"{lang_constants.ERROR_EMOJI} Error transferring ownership: {e}")
        return False
