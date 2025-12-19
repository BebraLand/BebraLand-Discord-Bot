import discord
from discord.ext import commands
import config.constants as constants
from src.utils.logger import get_cool_logger
from src.utils.database import get_db
from src.utils.scheduler import get_scheduler
import time

logger = get_cool_logger(__name__)


async def create_temp_voice_channel(member: discord.Member, guild: discord.Guild):
    """Create a temporary voice channel for the user."""
    try:
        # Get the category
        category = guild.get_channel(constants.TEMP_VOICE_CHANNEL_CATEGORY_ID)
        if not category:
            logger.error(f"Temp voice category {constants.TEMP_VOICE_CHANNEL_CATEGORY_ID} not found")
            return None
        
        # Get the default role
        default_role = guild.get_role(constants.DEFAULT_USER_ROLE_ID)
        if not default_role:
            logger.error(f"Default role {constants.DEFAULT_USER_ROLE_ID} not found")
            return None
        
        # Get @everyone role
        everyone_role = guild.default_role
        
        # Create channel with permissions
        overwrites = {
            everyone_role: discord.PermissionOverwrite(
                view_channel=False,
                connect=False
            ),
            default_role: discord.PermissionOverwrite(
                view_channel=True,
                connect=True
            ),
            member: discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                manage_channels=False  # Owner can't delete the channel
            )
        }
        
        channel_name = f"{member.display_name}'s Channel"
        channel = await category.create_voice_channel(
            name=channel_name,
            overwrites=overwrites
        )
        
        # Store in database
        db = await get_db()
        await db.create_temp_voice_channel(
            channel_id=channel.id,
            owner_id=member.id,
            guild_id=guild.id
        )
        
        # Move user to the new channel
        await member.move_to(channel)
        
        # Send control panel embed in the voice channel's text chat (if enabled) or skip for now
        # Voice channels in Discord.py support sending messages when they have text chat enabled
        from src.features.temp_voice_channels.views.ControlPanelView import build_control_panel_embed, ControlPanelView
        
        try:
            embed = build_control_panel_embed(channel_name, member)
            message = await channel.send(embed=embed, view=ControlPanelView())
            
            # Store the control message ID
            await db.update_temp_voice_channel_control_message(channel.id, message.id)
        except discord.HTTPException:
            # Voice channel might not support text chat
            logger.warning(f"Could not send control panel to voice channel {channel.id}")
        
        logger.info(f"Created temp voice channel {channel.id} for user {member.id}")
        return channel
        
    except Exception as e:
        logger.error(f"Failed to create temp voice channel for user {member.id}: {e}")
        return None


async def schedule_channel_deletion(channel_id: int, guild_id: int):
    """Schedule deletion of an empty temp voice channel after the configured delay."""
    try:
        scheduler = get_scheduler()
        run_at = time.time() + constants.DELETE_EMPTY_TEMP_VOICE_CHANNELS_AFTER_SECONDS
        
        task = {
            "type": "delete_temp_voice_channel",
            "guild_id": guild_id,
            "channel_id": channel_id,
            "time": "",  # Not time-based
            "run_at": run_at,
            "payload": {"channel_id": channel_id}
        }
        
        task_id = await scheduler._add_task_to_db(task)
        if task_id:
            task["id"] = task_id
            await scheduler._schedule_task(task)
        
        logger.info(f"Scheduled deletion of temp voice channel {channel_id} in {constants.DELETE_EMPTY_TEMP_VOICE_CHANNELS_AFTER_SECONDS}s")
        
    except Exception as e:
        logger.error(f"Failed to schedule deletion of temp voice channel {channel_id}: {e}")


async def cancel_channel_deletion(channel_id: int):
    """Cancel the scheduled deletion of a temp voice channel."""
    try:
        # Find and remove the scheduled task
        scheduler = get_scheduler()
        tasks = await scheduler._get_all_tasks_from_db()
        
        for task in tasks:
            if (task.get("type") == "delete_temp_voice_channel" and 
                task.get("payload", {}).get("channel_id") == channel_id):
                task_id = task.get("id")
                if task_id:
                    # Cancel the asyncio task if it exists
                    if task_id in scheduler._scheduled_handles:
                        scheduler._scheduled_handles[task_id].cancel()
                        scheduler._scheduled_handles.pop(task_id, None)
                    # Remove from database
                    await scheduler._remove_task_from_db(task_id)
                    logger.info(f"Cancelled deletion of temp voice channel {channel_id}")
                break
                
    except Exception as e:
        logger.error(f"Failed to cancel deletion of temp voice channel {channel_id}: {e}")


async def delete_temp_voice_channel(channel_id: int, bot: discord.Bot):
    """Delete a temporary voice channel and clean up database."""
    try:
        db = await get_db()
        
        # Get channel data
        channel_data = await db.get_temp_voice_channel(channel_id)
        if not channel_data:
            logger.warning(f"Temp voice channel {channel_id} not found in database")
            return
        
        # Get the channel
        channel = bot.get_channel(channel_id)
        if channel:
            # Check if channel is still empty
            if len(channel.members) > 0:
                logger.info(f"Temp voice channel {channel_id} is no longer empty, skipping deletion")
                return
            
            # Delete the channel
            await channel.delete(reason="Temporary voice channel cleanup - empty for configured duration")
            logger.info(f"Deleted temp voice channel {channel_id}")
        else:
            logger.warning(f"Temp voice channel {channel_id} not found in guild, cleaning up database")
        
        # Clean up database
        await db.delete_temp_voice_channel(channel_id)
        
    except Exception as e:
        logger.error(f"Failed to delete temp voice channel {channel_id}: {e}")


async def handle_ownership_transfer(channel: discord.VoiceChannel):
    """Handle automatic ownership transfer when the owner leaves."""
    try:
        db = await get_db()
        channel_data = await db.get_temp_voice_channel(channel.id)
        
        if not channel_data:
            return
        
        # Check if there are any members left in the channel
        if len(channel.members) == 0:
            # Schedule deletion
            await schedule_channel_deletion(channel.id, channel.guild.id)
            return
        
        # Transfer ownership to the first member in the channel
        new_owner = channel.members[0]
        await db.update_temp_voice_channel_owner(channel.id, new_owner.id)
        
        # Update the control panel message if it exists
        if channel_data.get("control_message_id"):
            try:
                # Fetch the control panel message directly
                message = await channel.fetch_message(channel_data["control_message_id"])
                from src.features.temp_voice_channels.views.ControlPanelView import build_control_panel_embed, ControlPanelView
                embed = build_control_panel_embed(channel.name, new_owner)
                await message.edit(embed=embed, view=ControlPanelView())
                
                # Send notification
                await channel.send(
                    f"👑 {new_owner.mention} is now the owner of this channel!",
                    delete_after=10
                )
            except Exception as e:
                logger.error(f"Failed to update control panel for ownership transfer: {e}")
        
        logger.info(f"Transferred ownership of channel {channel.id} to {new_owner.id}")
        
    except Exception as e:
        logger.error(f"Failed to handle ownership transfer for channel {channel.id}: {e}")


class TempVoiceChannelHandler(commands.Cog):
    """Event handler for temporary voice channels."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, 
        member: discord.Member, 
        before: discord.VoiceState, 
        after: discord.VoiceState
    ):
        """Handle voice state updates for temporary voice channels."""
        try:
            # Check if user joined the lobby channel
            if after.channel and after.channel.id == constants.TEMP_VOICE_CHANNEL_LOBBY_ID:
                # Create a new temp voice channel
                await create_temp_voice_channel(member, member.guild)
            
            # Check if user left a temp voice channel
            if before.channel:
                db = await get_db()
                channel_data = await db.get_temp_voice_channel(before.channel.id)
                
                if channel_data:
                    # Check if the owner left
                    if member.id == channel_data["owner_id"]:
                        # Handle ownership transfer
                        await handle_ownership_transfer(before.channel)
                    else:
                        # Check if channel is now empty
                        if len(before.channel.members) == 0:
                            # Schedule deletion
                            await schedule_channel_deletion(before.channel.id, before.channel.guild.id)
            
            # Check if user joined a temp voice channel
            if after.channel:
                db = await get_db()
                channel_data = await db.get_temp_voice_channel(after.channel.id)
                
                if channel_data:
                    # Cancel scheduled deletion if it exists
                    await cancel_channel_deletion(after.channel.id)
                    
        except Exception as e:
            logger.error(f"Error in temp voice channel handler: {e}")


def setup(bot: commands.Bot):
    bot.add_cog(TempVoiceChannelHandler(bot))
