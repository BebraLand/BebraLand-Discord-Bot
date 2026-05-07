import discord
from discord import ui

import src.languages.lang_constants as lang_constants
from config.config import config as bot_config
from src.languages.localize import _
from src.utils.database import get_language
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


class KickUserSelect(ui.Select):
    """User select for kicking users from the channel."""

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(
            placeholder="Select a user to kick",
            min_values=1,
            max_values=1,
            select_type=discord.ComponentType.user_select,
        )
        self.channel = channel
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction):
        current_lang = await get_language(interaction.user.id)

        if interaction.user.id != self.owner_id:
            return

        selected_user = self.values[0]

        # Check if selected user is a bot
        if selected_user.bot:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
                description=_("temp_voice.errors.cannot_kick_bots", current_lang),
                color=bot_config.embeds.failed_color,
            )
            embed.set_footer(
                text=bot_config.bot.trademark,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.edit_message(
                embed=embed,
                view=None,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
            return

        # Check if trying to kick themselves
        if selected_user.id == self.owner_id:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
                description=_("temp_voice.errors.cannot_kick_self", current_lang),
                color=bot_config.embeds.failed_color,
            )
            embed.set_footer(
                text=bot_config.bot.trademark,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.edit_message(
                embed=embed,
                view=None,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
            return

        # Check if user is in the voice channel
        if selected_user not in self.channel.members:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
                description=_(
                    "temp_voice.errors.not_in_voice_channel", current_lang
                ).format(selected_user=selected_user),
                color=bot_config.embeds.failed_color,
            )
            embed.set_footer(
                text=bot_config.bot.trademark,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.edit_message(
                embed=embed,
                view=None,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
            return

        try:
            # Disconnect user from the channel
            await selected_user.move_to(None)
            logger.info(
                f"User {interaction.user.id} kicked {selected_user.id} from channel {self.channel.id}"
            )
            embed = discord.Embed(
                title=f"{lang_constants.SUCCESS_EMOJI} {_('common.success', current_lang)}",
                description=_("temp_voice.kicked", current_lang).format(
                    selected_user=selected_user
                ),
                color=bot_config.embeds.success_color,
            )
            embed.set_footer(
                text=bot_config.bot.trademark,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.edit_message(
                embed=embed,
                view=None,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Missing permissions to kick {selected_user.mention}.",
                ephemeral=True,
            )
            logger.warning(
                f"Missing permissions to kick user {selected_user.id} from channel {self.channel.id}"
            )
        except Exception as e:
            logger.error(f"Error kicking user: {e}")
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", ephemeral=True
            )
