import discord
from discord import Option
from discord.ext import commands
from pycord.multicog import subcommand

import config.command as COMMAND_ENABLED
import src.languages.lang_constants as lang_constants
from config.config import config as bot_config
from src.commands.radio import _fetch_nowplaying, _radio_embed, _write_message_state
from src.languages.localize import _
from src.utils.auth import require_admin
from src.utils.database import get_language
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


class AdminRadioPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @subcommand("admin")
    @discord.slash_command(
        name="radio_panel",
        description="Post the auto-updating BebraLand FM panel",
    )
    async def radio_panel(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel = Option(
            discord.TextChannel,
            name="channel",
            description="Channel to post the radio panel in",
            required=False,
            default=None,
        ),
    ):
        await ctx.defer(ephemeral=True)

        if not await require_admin(ctx):
            logger.info(
                f"{ctx.user.name}({ctx.user.id}) used admin radio_panel without permissions"
            )
            return

        locale = await get_language(ctx.user.id)
        target_channel = channel or ctx.channel

        try:
            data = await _fetch_nowplaying()
        except Exception as error:
            logger.error(f"AzuraCast fetch failed: {error}")
            await ctx.followup.send(_("radio.unavailable", locale), ephemeral=True)
            return

        message = await target_channel.send(
            embed=_radio_embed(data, self.bot, bot_config.bot.default_language)
        )
        await _write_message_state(ctx.guild.id, target_channel.id, message.id)

        embed = discord.Embed(
            title=f"{lang_constants.SUCCESS_EMOJI} {_('common.success', locale)}",
            description=_("radio.panel_sent", locale).format(
                channel=target_channel.mention
            ),
            color=bot_config.embeds.success_color,
        )
        embed.set_footer(text=bot_config.bot.trademark, icon_url=get_embed_icon(ctx))
        await ctx.followup.send(
            embed=embed,
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )


def setup(bot: commands.Bot):
    if COMMAND_ENABLED.RADIO:
        bot.add_cog(AdminRadioPanel(bot))
