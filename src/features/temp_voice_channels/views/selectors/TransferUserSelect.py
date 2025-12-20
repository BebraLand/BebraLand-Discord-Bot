import discord
from discord import ui
from src.utils.database import get_db
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


class TransferUserSelect(ui.Select):
    """User select for transferring channel ownership."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int, current_owner: discord.Member):
        # Create a filtered list of non-bot members
        super().__init__(
            placeholder="Select a user to transfer ownership to",
            min_values=1,
            max_values=1,
            select_type=discord.ComponentType.user_select
        )
        self.channel = channel
        self.owner_id = owner_id
        self.current_owner = current_owner

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can transfer ownership!", ephemeral=True)
            return

        selected_user = self.values[0]
        
        # Check if selected user is a bot
        if selected_user.bot:
            await interaction.response.send_message("❌ Cannot transfer ownership to a bot!", ephemeral=True)
            return
        
        if selected_user.id == self.owner_id:
            await interaction.response.send_message("❌ You already own this channel!", ephemeral=True)
            return
        
        # Check if selected user is in the voice channel
        if not selected_user.voice or selected_user.voice.channel != self.channel:
            await interaction.response.send_message(f"❌ {selected_user.mention} must be in the voice channel to receive ownership!", ephemeral=True)
            return
        
        try:
            logger.info(f"Starting ownership transfer: channel {self.channel.id}, from {self.owner_id} to {selected_user.id}")
            
            # Update database
            storage = await get_db()
            temp_vc = await storage.get_temp_voice_channel(self.channel.id)
            logger.info(f"Current temp_vc data: {temp_vc}")
            
            await storage.update_temp_voice_channel(self.channel.id, owner_id=selected_user.id)
            logger.info(f"Updated database with new owner_id: {selected_user.id}")
            
            # Verify update
            updated_vc = await storage.get_temp_voice_channel(self.channel.id)
            logger.info(f"Verified temp_vc data after update: {updated_vc}")
            
            # Update channel permissions
            # Remove manage permissions from old owner
            await self.channel.set_permissions(self.current_owner, manage_channels=None)
            logger.info(f"Removed manage permissions from old owner {self.current_owner.id}")
            
            # Grant manage permissions to new owner
            await self.channel.set_permissions(selected_user, manage_channels=True, connect=True, speak=True, view_channel=True)
            logger.info(f"Granted manage permissions to new owner {selected_user.id}")
            
            # Update channel name if it contains old owner's name
            if self.current_owner.display_name in self.channel.name:
                new_name = self.channel.name.replace(self.current_owner.display_name, selected_user.display_name)
                await self.channel.edit(name=new_name)
                logger.info(f"Updated channel name to: {new_name}")
            
            # Update control panel message with new owner
            if temp_vc and temp_vc.get("control_message_id"):
                try:
                    control_message = await self.channel.fetch_message(temp_vc["control_message_id"])
                    # Update embed to mention new owner
                    embed = control_message.embeds[0]
                    embed.description = f"Welcome to your temporary voice channel, {selected_user.mention}!\n\nUse the buttons below to control your channel."
                    await control_message.edit(embed=embed)
                    logger.info(f"Updated control panel message with new owner mention")
                except Exception as e:
                    logger.error(f"Error updating control panel message: {e}")
            
            await interaction.response.send_message(f"✅ Transferred ownership to {selected_user.mention}! They can now use the control panel.\n\nUse the buttons below to control your channel.", ephemeral=True)
            logger.info(f"✅ Channel {self.channel.id} ownership transferred from {self.owner_id} to {selected_user.id}")
        except Exception as e:
            logger.error(f"Error transferring channel ownership: {e}")
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)