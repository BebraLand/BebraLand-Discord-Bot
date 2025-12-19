import discord
from src.utils.logger import get_cool_logger
from src.utils.database import get_db
import config.constants as constants

logger = get_cool_logger(__name__)


class TransferOwnershipModal(discord.ui.Modal):
    """Modal for transferring ownership of the channel."""

    def __init__(self, channel_id: int):
        super().__init__(title="Transfer Ownership")
        self.channel_id = channel_id

        self.user_input = discord.ui.InputText(
            label="User ID or Mention",
            placeholder="Enter user ID or @mention the new owner",
            required=True
        )
        self.add_item(self.user_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        user_input = self.user_input.value.strip()
        
        # Extract user ID from mention or use as-is
        user_id = None
        if user_input.startswith("<@") and user_input.endswith(">"):
            # Extract ID from mention
            user_id_str = user_input[2:-1]
            if user_id_str.startswith("!"):
                user_id_str = user_id_str[1:]
            try:
                user_id = int(user_id_str)
            except ValueError:
                pass
        else:
            try:
                user_id = int(user_input)
            except ValueError:
                pass
        
        if not user_id:
            await interaction.response.send_message(
                "❌ Invalid user ID or mention.",
                ephemeral=True
            )
            return
        
        # Get the user
        try:
            user = await interaction.guild.fetch_member(user_id)
        except discord.NotFound:
            await interaction.response.send_message(
                "❌ User not found in this server.",
                ephemeral=True
            )
            return
        except Exception as e:
            logger.error(f"Failed to fetch user {user_id}: {e}")
            await interaction.response.send_message(
                "❌ Failed to fetch user.",
                ephemeral=True
            )
            return
        
        # Check if user is in the channel
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            await interaction.response.send_message(
                "❌ Channel not found.",
                ephemeral=True
            )
            return
        
        if not user.voice or user.voice.channel != channel:
            await interaction.response.send_message(
                "❌ The user must be in the voice channel to transfer ownership.",
                ephemeral=True
            )
            return
        
        try:
            # Update ownership in database
            db = await get_db()
            await db.update_temp_voice_channel_owner(self.channel_id, user_id)
            
            # Update the control panel message if it exists
            channel_data = await db.get_temp_voice_channel(self.channel_id)
            if channel_data and channel_data.get("control_message_id"):
                try:
                    # Try to fetch and update the message
                    async for message in channel.history(limit=50):
                        if message.id == channel_data["control_message_id"]:
                            from .ControlPanelView import build_control_panel_embed, ControlPanelView
                            embed = build_control_panel_embed(channel.name, user)
                            await message.edit(embed=embed, view=ControlPanelView())
                            break
                except Exception as e:
                    logger.error(f"Failed to update control panel message: {e}")
            
            await interaction.response.send_message(
                f"👑 Ownership transferred to {user.mention}!",
                ephemeral=True
            )
            logger.info(f"User {interaction.user.id} transferred ownership of channel {self.channel_id} to {user_id}")
        except Exception as e:
            logger.error(f"Failed to transfer ownership of channel {self.channel_id} to {user_id}: {e}")
            await interaction.response.send_message(
                "❌ Failed to transfer ownership.",
                ephemeral=True
            )
