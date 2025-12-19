import discord
from src.utils.logger import get_cool_logger
from src.utils.database import get_db
import config.constants as constants

logger = get_cool_logger(__name__)


class PermitUserModal(discord.ui.Modal):
    """Modal for permitting a user to join the channel."""

    def __init__(self, channel_id: int):
        super().__init__(title="Permit User")
        self.channel_id = channel_id

        self.user_input = discord.ui.InputText(
            label="User ID or Mention",
            placeholder="Enter user ID or @mention the user",
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
        
        # Get the channel
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            await interaction.response.send_message(
                "❌ Channel not found.",
                ephemeral=True
            )
            return
        
        try:
            # Add permission in database
            db = await get_db()
            await db.add_temp_voice_channel_permission(self.channel_id, user_id, "permit")
            
            # Set Discord permissions
            await channel.set_permissions(
                user,
                view_channel=True,
                connect=True
            )
            
            await interaction.response.send_message(
                f"✅ {user.mention} has been permitted to join the channel!",
                ephemeral=True
            )
            logger.info(f"User {interaction.user.id} permitted {user_id} in channel {self.channel_id}")
        except Exception as e:
            logger.error(f"Failed to permit user {user_id} in channel {self.channel_id}: {e}")
            await interaction.response.send_message(
                "❌ Failed to permit user.",
                ephemeral=True
            )
