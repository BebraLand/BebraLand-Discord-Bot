import traceback

import discord
from discord import ui

import config.constants as constants
import src.languages.lang_constants as lang_constants
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


class BitrateModal(ui.Modal):
    """Modal to change the bitrate."""

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(title="Change Bitrate")
        self.channel = channel
        self.owner_id = owner_id

        self.bitrate = ui.InputText(
            label="Bitrate (in kbps)",
            placeholder=f"Enter bitrate ({constants.TEMP_VOICE_MIN_BITRATE // 1000}-{constants.TEMP_VOICE_MAX_BITRATE // 1000} kbps)",
            required=True,
            max_length=3,
            value=str(channel.bitrate // 1000),
        )
        self.add_item(self.bitrate)

    async def callback(self, interaction: discord.Interaction):
        try:
            bitrate_kbps = int(self.bitrate.value)
            bitrate_bps = bitrate_kbps * 1000

            # Get max bitrate based on server boost level
            guild = interaction.guild
            max_bitrate = constants.TEMP_VOICE_MAX_BITRATE

            if guild.premium_tier >= 3:
                max_bitrate = 384000
            elif guild.premium_tier == 2:
                max_bitrate = 256000
            elif guild.premium_tier == 1:
                max_bitrate = 128000

            if (
                bitrate_bps < constants.TEMP_VOICE_MIN_BITRATE
                or bitrate_bps > max_bitrate
            ):
                await interaction.response.send_message(
                    f"{lang_constants.ERROR_EMOJI} Bitrate must be between {constants.TEMP_VOICE_MIN_BITRATE // 1000} and {max_bitrate // 1000} kbps!",
                    ephemeral=True,
                )
                return

            logger.info(
                f"User {interaction.user.id} changing channel {self.channel.id} bitrate to {bitrate_kbps} kbps"
            )
            await self.channel.edit(bitrate=bitrate_bps)
            await interaction.response.send_message(
                f"{lang_constants.SUCCESS_EMOJI} Bitrate set to: **{bitrate_kbps} kbps**",
                ephemeral=True,
            )
        except ValueError:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Invalid bitrate value!", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error changing channel bitrate: {e}")
            logger.error(traceback.format_exc())
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", ephemeral=True
                    )
            except Exception:
                pass

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Bitrate modal error for user {interaction.user.id}: {error}")
        logger.error(traceback.format_exc())
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"{lang_constants.ERROR_EMOJI} An error occurred: {str(error)}",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    f"{lang_constants.ERROR_EMOJI} An error occurred: {str(error)}",
                    ephemeral=True,
                )
        except Exception:
            pass
