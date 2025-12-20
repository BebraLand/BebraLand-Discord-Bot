import discord
from discord import ui
import traceback
from src.utils.logger import get_cool_logger
import config.constants as constants
import src.languages.lang_constants as lang_constants

logger = get_cool_logger(__name__)

class LimitModal(ui.Modal):
    """Modal to change the user limit."""

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(title="Change User Limit")
        self.channel = channel
        self.owner_id = owner_id
        
        self.limit = ui.InputText(
            label="User Limit (0 for unlimited)",
            placeholder="Enter user limit (0-99)",
            required=True,
            max_length=2,
            value=str(channel.user_limit)
        )
        self.add_item(self.limit)

    async def callback(self, interaction: discord.Interaction):
        try:
            limit_value = int(self.limit.value)
            if limit_value < 0 or limit_value > constants.TEMP_VOICE_MAX_LIMIT:
                await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} Limit must be between 0 and {constants.TEMP_VOICE_MAX_LIMIT}!", ephemeral=True)
                return

            logger.info(f"User {interaction.user.id} changing channel {self.channel.id} limit to {limit_value}")
            await self.channel.edit(user_limit=limit_value)
            limit_text = "unlimited" if limit_value == 0 else str(limit_value)
            await interaction.response.send_message(f"{lang_constants.SUCCESS_EMOJI} User limit set to: **{limit_text}**", ephemeral=True)
        except ValueError:
            await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} Invalid limit value!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error changing channel limit: {e}")
            logger.error(traceback.format_exc())
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", ephemeral=True)
                else:
                    await interaction.followup.send(f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", ephemeral=True)
            except:
                pass

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Limit modal error for user {interaction.user.id}: {error}")
        logger.error(traceback.format_exc())
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"{lang_constants.ERROR_EMOJI} An error occurred: {str(error)}", ephemeral=True)
            else:
                await interaction.followup.send(f"{lang_constants.ERROR_EMOJI} An error occurred: {str(error)}", ephemeral=True)
        except:
            pass