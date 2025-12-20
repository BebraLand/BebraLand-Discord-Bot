"""
Event handler for voice state updates.
Handles temp voice channel creation and deletion.
"""
import discord
from discord.ext import commands
import asyncio
import time
from config import constants
from src.utils.database import get_db
from src.features.temp_voice_channels.create_temp_channel import create_temp_channel
from src.features.temp_voice_channels.delete_temp_channel import delete_temp_channel
from src.features.temp_voice_channels.auto_claim_ownership import auto_claim_ownership
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


class OnVoiceStateUpdate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.deletion_tasks = {}  # Track scheduled deletion tasks
        self.creation_cooldowns = {}  # Track user creation cooldowns
        self.COOLDOWN_SECONDS = constants.TEMP_VOICE_COOLDOWN_SECONDS_BETWEEN_CREATIONS

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        """Handle voice state changes."""
        
        # Handle joining the lobby to create a temp channel
        if after.channel and after.channel.id == constants.TEMP_VOICE_CHANNEL_LOBBY_ID:
            await self._handle_lobby_join(member, after.channel)
        
        # Handle joining a temp channel (for auto-claim ownership)
        if after.channel and after.channel != before.channel:
            await self._handle_channel_join(member, after.channel)
        
        # Handle leaving a temp channel
        if before.channel:
            await self._handle_channel_leave(member, before.channel)

    async def _handle_lobby_join(self, member: discord.Member, lobby: discord.VoiceChannel):
        """Handle when a user joins the lobby channel."""
        try:
            # Clean up old cooldowns (older than 10 minutes)
            current_time = time.time()
            self.creation_cooldowns = {
                user_id: timestamp 
                for user_id, timestamp in self.creation_cooldowns.items() 
                if current_time - timestamp < 600  # 10 minutes
            }
            
            # Check if user already has an empty temp voice channel
            storage = await get_db()
            all_user_channels = await storage.get_all_temp_voice_channels(member.guild.id)
            
            existing_empty_channel = None
            for channel_data in all_user_channels:
                if channel_data.get("owner_id") == member.id:
                    channel_id = channel_data.get("channel_id")
                    channel = member.guild.get_channel(channel_id)
                    if channel and isinstance(channel, discord.VoiceChannel) and len(channel.members) == 0:
                        existing_empty_channel = channel
                        break
            
            if existing_empty_channel:
                # Cancel any pending deletion for this channel
                if existing_empty_channel.id in self.deletion_tasks:
                    self.deletion_tasks[existing_empty_channel.id].cancel()
                    del self.deletion_tasks[existing_empty_channel.id]
                
                # Move user to their existing empty channel
                try:
                    await member.move_to(existing_empty_channel)
                    try:
                        await member.send(f"🔄 Moved you back to your existing channel: **{existing_empty_channel.name}**", delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)
                        logger.info(f"✅ Moved {member.id} back to existing temp voice channel {existing_empty_channel.id}")
                    except discord.HTTPException:
                        pass  # Can't DM user, just silently ignore
                    return
                except discord.HTTPException:
                    # If move fails, continue with creation logic
                    pass
            
            # Check cooldown to prevent channel spam (only if no existing empty channel)
            last_creation = self.creation_cooldowns.get(member.id, 0)
            
            if current_time - last_creation < self.COOLDOWN_SECONDS:
                # User is on cooldown, don't create channel
                remaining = int(self.COOLDOWN_SECONDS - (current_time - last_creation))
                try:
                    await member.send(f"⏰ Please wait {remaining} seconds before creating another temp voice channel.", delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)
                except discord.HTTPException:
                    pass  # Can't DM user, just silently ignore
                return
            
            # Create temp channel
            channel = await create_temp_channel(member, member.guild)
            
            if channel:
                # Update cooldown timestamp
                self.creation_cooldowns[member.id] = current_time
                
                # Move user to the new channel
                try:
                    await member.move_to(channel)
                except discord.HTTPException:
                    # If move fails, delete the channel
                    await channel.delete(reason="Failed to move user")
                    storage = await get_db()
                    await storage.delete_temp_voice_channel(channel.id)
        
        except Exception as e:
            print(f"Error handling lobby join: {e}")

    async def _handle_channel_join(self, member: discord.Member, channel: discord.VoiceChannel):
        """Handle when a user joins a voice channel."""
        try:
            # Check if it's a temp channel
            storage = await get_db()
            temp_vc = await storage.get_temp_voice_channel(channel.id)
            
            if not temp_vc:
                return  # Not a temp channel
            
            # Cancel any pending deletion for this channel
            if channel.id in self.deletion_tasks:
                self.deletion_tasks[channel.id].cancel()
                del self.deletion_tasks[channel.id]
                logger.debug(f"Cancelled deletion task for channel {channel.id} (user joined)")
            
            # Check if the current owner is still in the channel
            owner_id = temp_vc.get("owner_id")
            owner = channel.guild.get_member(owner_id)
            
            # If owner is not in the channel, auto-claim ownership
            if not owner or owner not in channel.members:
                new_owner_id = await auto_claim_ownership(channel.id, member.guild)
                if new_owner_id and new_owner_id != owner_id:
                    # Notify the new owner
                    try:
                        await channel.send(
                            f"👑 {member.mention} is now the channel owner!",
                            delete_after=constants.DELETE_TRANSFERRED_OWNED_CHANNELS_AFTER_SECONDS
                        )
                        logger.info(f"✅ Channel {channel.id} ownership auto-claimed by {new_owner_id} (joined empty/ownerless channel)")
                    except:
                        pass
        
        except Exception as e:
            logger.error(f"Error handling channel join: {e}")

    async def _handle_channel_leave(self, member: discord.Member, channel: discord.VoiceChannel):
        """Handle when a user leaves a voice channel."""
        try:
            # Check if it's a temp channel
            storage = await get_db()
            temp_vc = await storage.get_temp_voice_channel(channel.id)
            
            if not temp_vc:
                return  # Not a temp channel
            
            owner_id = temp_vc.get("owner_id")
            
            # If owner left
            if member.id == owner_id:
                # If there are still people in the channel
                if len(channel.members) > 0:
                    # Auto-transfer ownership to next person
                    new_owner_id = await auto_claim_ownership(channel.id, member.guild)
                    # Only notify if ownership actually changed to a different person
                    if new_owner_id and new_owner_id != owner_id:
                        # Notify in channel
                        try:
                            new_owner = member.guild.get_member(new_owner_id)
                            if new_owner:
                                await channel.send(
                                    f"👑 {new_owner.mention} is now the channel owner!",
                                    delete_after=constants.DELETE_TRANSFERRED_OWNED_CHANNELS_AFTER_SECONDS
                                )
                                logger.info(f"✅ Channel {channel.id} ownership auto-transferred to {new_owner_id}")
                        except:
                            pass
                else:
                    # Channel is empty, schedule deletion
                    await self._schedule_deletion(channel.id, member.guild)
            
            # If not owner but channel is now empty
            elif len(channel.members) == 0:
                await self._schedule_deletion(channel.id, member.guild)
        
        except Exception as e:
            print(f"Error handling channel leave: {e}")

    async def _schedule_deletion(self, channel_id: int, guild: discord.Guild):
        """Schedule a channel for deletion if it remains empty."""
        # Cancel any existing deletion task for this channel
        if channel_id in self.deletion_tasks:
            self.deletion_tasks[channel_id].cancel()
        
        # Create new deletion task
        task = asyncio.create_task(delete_temp_channel(channel_id, guild))
        self.deletion_tasks[channel_id] = task
        
        # Clean up task reference when done
        def cleanup(t):
            if channel_id in self.deletion_tasks:
                del self.deletion_tasks[channel_id]
        
        task.add_done_callback(cleanup)


def setup(bot):
    bot.add_cog(OnVoiceStateUpdate(bot))
