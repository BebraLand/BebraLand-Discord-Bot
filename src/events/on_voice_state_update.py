"""
Event handler for voice state updates.
Handles temp voice channel creation and deletion.
"""
import discord
from discord.ext import commands
import asyncio
from config import constants
from src.utils.database import get_db
from src.features.temp_voice_channels.utils import (
    create_temp_channel,
    delete_temp_channel,
    auto_claim_ownership
)


class OnVoiceStateUpdate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.deletion_tasks = {}  # Track scheduled deletion tasks

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
        
        # Handle leaving a temp channel
        if before.channel:
            await self._handle_channel_leave(member, before.channel)

    async def _handle_lobby_join(self, member: discord.Member, lobby: discord.VoiceChannel):
        """Handle when a user joins the lobby channel."""
        try:
            # Create temp channel
            channel = await create_temp_channel(member, member.guild)
            
            if channel:
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
                    if new_owner_id:
                        # Notify in channel
                        try:
                            new_owner = member.guild.get_member(new_owner_id)
                            if new_owner:
                                await channel.send(
                                    f"👑 {new_owner.mention} is now the channel owner!",
                                    delete_after=10
                                )
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
