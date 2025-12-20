import discord
from discord import ui
import traceback
from src.utils.logger import get_cool_logger
import src.languages.lang_constants as lang_constants

logger = get_cool_logger(__name__)

class NameModal(ui.Modal):
    """Modal to change the channel name."""

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(title="Change Channel Name")
        self.channel = channel
        self.owner_id = owner_id
        
        self.name = ui.InputText(
            label="Channel Name",
            placeholder="Enter new channel name",
            required=True,
            max_length=100,
            min_length=1,
            value=channel.name
        )
        self.add_item(self.name)

    async def callback(self, interaction: discord.Interaction):
        logger.info(f"User {interaction.user.id} submitted name change modal for channel {self.channel.id}")
        try:
            logger.info(f"User {interaction.user.id} changing channel {self.channel.id} name to '{self.name.value}'")
            await self.channel.edit(name=self.name.value)
            await interaction.response.send_message(f"{lang_constants.SUCCESS_EMOJI} Channel name changed to: **{self.name.value}**", ephemeral=True)
        except Exception as e:
            logger.error(f"Error changing channel name: {e}")
            logger.error(traceback.format_exc())
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", ephemeral=True)
                else:
                    await interaction.followup.send(f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", ephemeral=True)
            except:
                pass

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Modal error for user {interaction.user.id}: {error}")
        logger.error(traceback.format_exc())
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} An error occurred: {str(error)}", ephemeral=True)
            else:
                await interaction.followup.send(f"{lang_constants.ERROR_EMOJI} An error occurred: {str(error)}", ephemeral=True)
        except:
            pass