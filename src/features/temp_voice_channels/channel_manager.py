"""
Helper functions for managing temporary voice channels.
"""
import discord
import asyncio
from typing import Optional, List
from src.utils.logger import get_cool_logger
from src.utils.database import get_db
from src.utils.scheduler import get_scheduler
import config.constants as constants

logger = get_cool_logger(__name__)


async def create_temp_voice_channel(member: discord.Member, lobby_channel: discord.VoiceChannel) -> Optional[discord.VoiceChannel]:
    """
    Create a temporary voice channel for a member.
    
    Args:
        member: The member who joined the lobby
        lobby_channel: The lobby channel they joined
        
    Returns:
        The created voice channel or None if creation failed
    """
    try:
        guild = member.guild
        category = guild.get_channel(constants.TEMP_VOICE_CHANNEL_CATEGORY_ID)
        
        if not category or not isinstance(category, discord.CategoryChannel):
            logger.error(f"Temp voice category {constants.TEMP_VOICE_CHANNEL_CATEGORY_ID} not found")
            return None
        
        # Get the default role
        default_role = guild.get_role(constants.DEFAULT_USER_ROLE_ID)
        everyone_role = guild.default_role
        
        # Create channel with permissions
        overwrites = {
            everyone_role: discord.PermissionOverwrite(
                view_channel=False,
                connect=False
            ),
            member: discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                stream=True,
                manage_channels=True,
                move_members=True
            )
        }
        
        # Add default role permissions if it exists
        if default_role:
            overwrites[default_role] = discord.PermissionOverwrite(
                view_channel=True,
                connect=True
            )
        
        # Create the channel
        channel_name = f"{member.display_name}'s Channel"
        temp_channel = await category.create_voice_channel(
            name=channel_name,
            overwrites=overwrites,
            user_limit=constants.TEMP_VOICE_DEFAULT_USER_LIMIT,
            bitrate=min(constants.TEMP_VOICE_MAX_BITRATE, guild.bitrate_limit)
        )
        
        # Store in database
        db = await get_db()
        await db.create_temp_voice_channel(
            channel_id=temp_channel.id,
            owner_id=str(member.id),
            guild_id=guild.id
        )
        
        logger.info(f"Created temp voice channel {temp_channel.id} for {member.name} ({member.id})")
        return temp_channel
        
    except Exception as e:
        logger.error(f"Failed to create temp voice channel: {e}")
        return None


async def update_channel_permissions(channel: discord.VoiceChannel, channel_data: dict):
    """
    Update channel permissions based on database state.
    
    Args:
        channel: The voice channel to update
        channel_data: Database record with permission settings
    """
    try:
        guild = channel.guild
        owner = guild.get_member(int(channel_data["owner_id"]))
        default_role = guild.get_role(constants.DEFAULT_USER_ROLE_ID)
        everyone_role = guild.default_role
        
        # Base permissions
        overwrites = {
            everyone_role: discord.PermissionOverwrite(
                view_channel=not channel_data["is_ghost"],
                connect=False
            )
        }
        
        # Owner permissions
        if owner:
            overwrites[owner] = discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                stream=True,
                manage_channels=True,
                move_members=True
            )
        
        # Default role permissions
        if default_role:
            if channel_data["is_locked"]:
                overwrites[default_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    connect=False
                )
            elif channel_data["is_ghost"]:
                overwrites[default_role] = discord.PermissionOverwrite(
                    view_channel=False,
                    connect=False
                )
            else:
                overwrites[default_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True
                )
        
        # Permitted users
        for user_id in channel_data["permitted_users"]:
            user = guild.get_member(int(user_id))
            if user:
                overwrites[user] = discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True
                )
        
        # Rejected users
        for user_id in channel_data["rejected_users"]:
            user = guild.get_member(int(user_id))
            if user:
                overwrites[user] = discord.PermissionOverwrite(
                    view_channel=not channel_data["is_ghost"],
                    connect=False
                )
        
        # Apply all overwrites at once
        await channel.edit(overwrites=overwrites)
        
    except Exception as e:
        logger.error(f"Failed to update channel permissions: {e}")


async def transfer_ownership(channel: discord.VoiceChannel, new_owner: discord.Member, old_owner_id: str):
    """
    Transfer ownership of a temp voice channel to a new member.
    
    Args:
        channel: The voice channel
        new_owner: The new owner
        old_owner_id: The previous owner's ID
    """
    try:
        db = await get_db()
        
        # Update database
        await db.update_temp_voice_channel_owner(channel.id, str(new_owner.id))
        
        # Update channel name
        await channel.edit(name=f"{new_owner.display_name}'s Channel")
        
        # Get current channel data
        channel_data = await db.get_temp_voice_channel(channel.id)
        if channel_data:
            await update_channel_permissions(channel, channel_data)
        
        logger.info(f"Transferred ownership of {channel.id} from {old_owner_id} to {new_owner.id}")
        
    except Exception as e:
        logger.error(f"Failed to transfer ownership: {e}")


async def schedule_channel_deletion(channel_id: int, delay: int = None):
    """
    Schedule a temporary voice channel for deletion if it remains empty.
    
    Args:
        channel_id: The channel ID to delete
        delay: Delay in seconds before deletion (uses constant if not provided)
    """
    if delay is None:
        delay = constants.DELETE_EMPTY_TEMP_VOICE_CHANNELS_AFTER_SECONDS
    
    try:
        scheduler = get_scheduler()
        
        # Schedule the deletion task
        await scheduler.schedule_task(
            type="delete_temp_voice_channel",
            channel_id=channel_id,
            delay=delay
        )
        
        logger.info(f"Scheduled deletion of temp voice channel {channel_id} in {delay} seconds")
        
    except Exception as e:
        logger.error(f"Failed to schedule channel deletion: {e}")


async def cleanup_temp_voice_channel(channel_id: int, bot: discord.Client):
    """
    Delete a temporary voice channel and its database record.
    
    Args:
        channel_id: The channel ID to delete
        bot: The Discord bot instance
    """
    try:
        db = await get_db()
        
        # Get channel data
        channel_data = await db.get_temp_voice_channel(channel_id)
        if not channel_data:
            logger.warning(f"No database record found for temp voice channel {channel_id}")
            return
        
        # Get the channel
        guild = bot.get_guild(channel_data["guild_id"])
        if guild:
            channel = guild.get_channel(channel_id)
            if channel:
                # Only delete if channel is empty
                if isinstance(channel, discord.VoiceChannel) and len(channel.members) == 0:
                    await channel.delete(reason="Temporary voice channel cleanup")
                    logger.info(f"Deleted empty temp voice channel {channel_id}")
                else:
                    logger.info(f"Temp voice channel {channel_id} not empty, skipping deletion")
                    return
        
        # Remove from database
        await db.delete_temp_voice_channel(channel_id)
        
    except discord.NotFound:
        # Channel already deleted, just clean up database
        db = await get_db()
        await db.delete_temp_voice_channel(channel_id)
        logger.info(f"Cleaned up database record for deleted channel {channel_id}")
    except Exception as e:
        logger.error(f"Failed to cleanup temp voice channel {channel_id}: {e}")


async def find_new_owner(channel: discord.VoiceChannel, exclude_id: int = None) -> Optional[discord.Member]:
    """
    Find a suitable new owner for a temp voice channel from current members.
    
    Args:
        channel: The voice channel
        exclude_id: User ID to exclude from selection
        
    Returns:
        A suitable member or None if no one is available
    """
    if not channel.members:
        return None
    
    # Filter out bots and the excluded user
    eligible_members = [
        m for m in channel.members 
        if not m.bot and (exclude_id is None or m.id != exclude_id)
    ]
    
    if not eligible_members:
        return None
    
    # Return the first eligible member (they were there first)
    return eligible_members[0]
