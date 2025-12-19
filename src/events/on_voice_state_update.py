"""
Event handler for voice state updates.
Handles temp voice channel creation, deletion, and ownership transfers.
"""
import discord
from discord.ext import commands
from src.utils.logger import get_cool_logger
from src.utils.database import get_db
import config.constants as constants
from src.languages import lang_constants as lang_constants
from src.features.temp_voice_channels.channel_manager import (
    create_temp_voice_channel,
    cleanup_temp_voice_channel,
    schedule_channel_deletion,
    find_new_owner,
    transfer_ownership
)
from src.features.temp_voice_channels.view.TempVoiceControlPanel import (
    TempVoiceControlPanel,
    build_control_panel_embed
)
from src.features.temp_voice_channels.view.TempVoiceSettingsPanel import (
    TempVoiceSettingsPanel,
    build_settings_panel_embed
)

logger = get_cool_logger(__name__)


class on_voice_state_update(commands.Cog):
    """Handle voice state updates for temporary voice channels."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        """Handle voice state changes."""
        try:
            # Check if user joined the lobby channel
            if after.channel and after.channel.id == constants.TEMP_VOICE_CHANNEL_LOBBY_ID:
                await self.handle_lobby_join(member, after.channel)
            
            # Check if user left a temp voice channel
            if before.channel:
                await self.handle_channel_leave(member, before.channel)
        
        except Exception as e:
            logger.error(f"Error in on_voice_state_update: {e}")
    
    async def handle_lobby_join(self, member: discord.Member, lobby_channel: discord.VoiceChannel):
        """Handle user joining the lobby channel."""
        try:
            # Create temporary voice channel
            temp_channel = await create_temp_voice_channel(member, lobby_channel)
            
            if not temp_channel:
                logger.error(f"Failed to create temp channel for {member.name}")
                return
            
            # Move user to the new channel
            try:
                await member.move_to(temp_channel, reason="Moved to temporary voice channel")
            except discord.Forbidden:
                logger.error(f"Missing permissions to move {member.name}")
                # Clean up the created channel if we can't move the user
                await temp_channel.delete(reason="Failed to move user")
                db = await get_db()
                await db.delete_temp_voice_channel(temp_channel.id)
                return
            except Exception as e:
                logger.error(f"Error moving user: {e}")
                return
            
            # Send control panel and settings panel to the channel
            control_embed = build_control_panel_embed(member, temp_channel)
            control_view = TempVoiceControlPanel(temp_channel.id, member.id)
            
            control_message = await temp_channel.send(embed=control_embed, view=control_view)
            
            # Store control message ID
            db = await get_db()
            await db.update_temp_voice_channel_control_message(temp_channel.id, control_message.id)
            
            # Send settings panel if enabled
            if constants.TEMP_VOICE_SETTINGS_ENABLED:
                settings_embed = build_settings_panel_embed(member, temp_channel)
                settings_view = TempVoiceSettingsPanel(temp_channel.id, member.id)
                await temp_channel.send(embed=settings_embed, view=settings_view)
            
            logger.info(f"Created and setup temp voice channel {temp_channel.id} for {member.name}")
            
        except Exception as e:
            logger.error(f"Error handling lobby join: {e}")
    
    async def handle_channel_leave(self, member: discord.Member, channel: discord.VoiceChannel):
        """Handle user leaving a voice channel."""
        try:
            db = await get_db()
            channel_data = await db.get_temp_voice_channel(channel.id)
            
            if not channel_data:
                # Not a temp voice channel
                return
            
            # Check if the channel is now empty
            if len(channel.members) == 0:
                # Schedule deletion after delay
                await schedule_channel_deletion(channel.id)
                logger.info(f"Scheduled deletion for empty temp channel {channel.id}")
                return
            
            # Check if the owner left
            if str(member.id) == channel_data["owner_id"]:
                # Find new owner from remaining members
                new_owner = await find_new_owner(channel, exclude_id=member.id)
                
                if new_owner:
                    # Transfer ownership to new member
                    await transfer_ownership(channel, new_owner, channel_data["owner_id"])
                    
                    # Update control panel
                    if channel_data.get("control_message_id"):
                        try:
                            control_msg = await channel.fetch_message(channel_data["control_message_id"])
                            new_control_view = TempVoiceControlPanel(channel.id, new_owner.id)
                            new_control_embed = build_control_panel_embed(new_owner, channel)
                            await control_msg.edit(embed=new_control_embed, view=new_control_view)
                            
                            # Find and update settings panel (should be the next message after control panel)
                            if constants.TEMP_VOICE_SETTINGS_ENABLED:
                                async for msg in channel.history(limit=10):
                                    if msg.embeds and "Voice Channel Settings" in msg.embeds[0].title:
                                        new_settings_view = TempVoiceSettingsPanel(channel.id, new_owner.id)
                                        new_settings_embed = build_settings_panel_embed(new_owner, channel)
                                        await msg.edit(embed=new_settings_embed, view=new_settings_view)
                                        break
                        except discord.NotFound:
                            logger.warning(f"Control message not found for channel {channel.id}")
                        except Exception as e:
                            logger.error(f"Error updating control panel: {e}")
                    
                    # Notify in channel
                    try:
                        notification_embed = discord.Embed(
                            title="👑 Ownership Transferred",
                            description=f"{new_owner.mention} is now the channel owner!",
                            color=constants.SUCCESS_EMBED_COLOR
                        )
                        notification_embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK)
                        await channel.send(embed=notification_embed, delete_after=10)
                    except discord.Forbidden:
                        logger.warning(f"Missing permissions to send notification in channel {channel.id}")
                    except Exception as e:
                        logger.error(f"Failed to send ownership transfer notification: {e}")
                    
                    logger.info(f"Transferred ownership of {channel.id} to {new_owner.id} (owner left)")
                else:
                    # No one to transfer to, schedule deletion
                    logger.info(f"No one to transfer ownership to for channel {channel.id}")
            
        except Exception as e:
            logger.error(f"Error handling channel leave: {e}")


def setup(bot: commands.Bot):
    bot.add_cog(on_voice_state_update(bot))
