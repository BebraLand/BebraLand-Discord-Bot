async def cleanup_orphaned_channels(guild: discord.Guild):
    """
    Clean up temp voice channels that are in the database but no longer exist.
    
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
                # Channel doesn't exist, remove from database
                logger.info(f"{lang_constants.INFO_EMOJI} Cleaning up orphaned temp voice channel ID {channel_id}")
                await storage.delete_temp_voice_channel(channel_id)

    except Exception as e:
        logger.error(f"{lang_constants.ERROR_EMOJI} Error cleaning up orphaned channels: {e}")