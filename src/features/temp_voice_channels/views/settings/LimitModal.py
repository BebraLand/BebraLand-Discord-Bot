import discord
from discord import ui
import traceback
from src.utils.logger import get_cool_logger
import config.constants as constants
import src.languages.lang_constants as lang_constants
from src.languages.localize import _
from src.utils.database import get_language
from src.utils.embeds import get_embed_icon

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
            value=str(channel.user_limit),
        )
        self.add_item(self.limit)

    async def callback(self, interaction: discord.Interaction):
        current_lang = await get_language(interaction.user.id)
        try:
            limit_value = int(self.limit.value)
            if limit_value < 0 or limit_value > constants.TEMP_VOICE_MAX_LIMIT:
                embed = discord.Embed(
                    title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
                    description=_(
                        "temp_voice.errors.limit_out_of_range", current_lang
                    ).format(max=constants.TEMP_VOICE_MAX_LIMIT),
                    color=constants.FAILED_EMBED_COLOR,
                )
                embed.set_footer(
                    text=constants.DISCORD_MESSAGE_TRADEMARK,
                    icon_url=get_embed_icon(interaction.guild.me),
                )
                await interaction.response.send_message(
                    embed=embed,
                    ephemeral=True,
                    delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
                )
                return

            logger.info(
                f"User {interaction.user.id} changing channel {self.channel.id} limit to {limit_value}"
            )
            await self.channel.edit(user_limit=limit_value)
            limit_text = (
                _("temp_voice.unlimited", current_lang)
                if limit_value == 0
                else str(limit_value)
            )
            embed = discord.Embed(
                title=f"{lang_constants.SUCCESS_EMOJI} {_('common.success', current_lang)}",
                description=_("temp_voice.user_limit_set_to", current_lang).format(
                    limit_text=limit_text
                ),
                color=constants.SUCCESS_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.edit_message(
                embed=embed,
                view=None,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
        except ValueError:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
                description=_("temp_voice.errors.invalid_limit_value", current_lang),
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.edit_message(
                embed=embed,
                view=None,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
            logger.info(
                f"User {interaction.user.id} provided invalid limit value: {self.limit.value}"
            )
        except Exception as e:
            logger.error(f"Error changing channel limit: {e}")
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
        logger.error(f"Limit modal error for user {interaction.user.id}: {error}")
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
