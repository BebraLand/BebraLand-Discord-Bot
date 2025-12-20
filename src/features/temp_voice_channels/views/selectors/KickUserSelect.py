import discord
from discord import ui
from src.utils.logger import get_cool_logger
import src.languages.lang_constants as lang_constants

logger = get_cool_logger(__name__)

class KickUserSelect(ui.Select):
    """User select for kicking users from the channel."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(placeholder="Select a user to kick", min_values=1, max_values=1, select_type=discord.ComponentType.user_select)
        self.channel = channel
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} Only the channel owner can kick users!", ephemeral=True)
            return

        selected_user = self.values[0]

        # Check if selected user is a bot
        if selected_user.bot:
            await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} Cannot kick bots!", ephemeral=True)
            return
        
        # Check if trying to kick themselves
        if selected_user.id == self.owner_id:
            await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} You cannot kick yourself!", ephemeral=True)
            return
        
        # Check if user is in the voice channel
        if selected_user not in self.channel.members:
            await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} {selected_user.mention} is not in the voice channel!", ephemeral=True)
            return

        try:
            # Disconnect user from the channel
            await selected_user.move_to(None)
            logger.info(f"User {interaction.user.id} kicked {selected_user.id} from channel {self.channel.id}")
            await interaction.response.send_message(f"{lang_constants.SUCCESS_EMOJI} Kicked {selected_user.mention} from the channel!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} Missing permissions to kick {selected_user.mention}.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error kicking user: {e}")
            await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", ephemeral=True)