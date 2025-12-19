import discord
from src.utils.logger import get_cool_logger
from src.utils.database import get_db
import config.constants as constants

logger = get_cool_logger(__name__)


class InviteUserModal(discord.ui.Modal):
    """Modal for inviting a user via DM."""

    def __init__(self, channel_id: int, channel_name: str):
        super().__init__(title="Invite User")
        self.channel_id = channel_id
        self.channel_name = channel_name

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
            # Send DM to the user
            invite_embed = discord.Embed(
                title="📨 Voice Channel Invitation",
                description=f"{interaction.user.mention} has invited you to join their voice channel!",
                color=constants.DISCORD_EMBED_COLOR
            )
            invite_embed.add_field(
                name="Channel",
                value=f"🎙️ {self.channel_name}",
                inline=False
            )
            invite_embed.add_field(
                name="Server",
                value=interaction.guild.name,
                inline=False
            )
            invite_embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK)
            
            await user.send(embed=invite_embed)
            
            await interaction.response.send_message(
                f"📨 Invite sent to {user.mention}!",
                ephemeral=True
            )
            logger.info(f"User {interaction.user.id} invited {user_id} to channel {self.channel_id}")
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ Could not send DM to {user.mention}. They may have DMs disabled.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Failed to invite user {user_id} to channel {self.channel_id}: {e}")
            await interaction.response.send_message(
                "❌ Failed to send invite.",
                ephemeral=True
            )
