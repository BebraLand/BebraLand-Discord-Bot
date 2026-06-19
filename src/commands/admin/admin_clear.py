import discord
from discord import Option
from discord.ext import commands
from pycord.multicog import subcommand

from config.config import config as bot_config
from src.languages import lang_constants as lang_constants
from src.languages.localize import _
from src.utils.auth import require_admin
from src.utils.database import get_language
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


class AdminClear(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @subcommand("admin")
    @discord.slash_command(
        name="clear",
        description="Delete messages from this channel",
    )
    async def clear(
        self,
        ctx: discord.ApplicationContext,
        amount: str = Option(
            str,
            description="Number of messages to delete, or 'all'",
            required=True,
        ),
    ):
        if not await require_admin(ctx):
            return

        await ctx.defer(ephemeral=True)

        if amount.lower() == "all":
            purge_limit = None
        else:
            try:
                purge_limit = int(amount)
            except ValueError:
                purge_limit = 0

            if purge_limit < 1:
                current_lang = await get_language(ctx.user.id)
                embed = discord.Embed(
                    title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
                    description=_('clear.invalid_amount', current_lang),
                    color=bot_config.embeds.failed_color,
                )
                embed.set_footer(
                    text=bot_config.bot.trademark,
                    icon_url=get_embed_icon(ctx),
                )
                await ctx.followup.send(
                    embed=embed,
                    ephemeral=True,
                    delete_after=bot_config.messages.action_confirmation_delete_delay,
                )
                return

        deleted = await ctx.channel.purge(limit=purge_limit)

        current_lang = await get_language(ctx.user.id)
        embed = discord.Embed(
            title=f"{lang_constants.SUCCESS_EMOJI} {_('common.success', current_lang)}",
            description=_('clear.deleted', current_lang, count=len(deleted)),
            color=bot_config.embeds.success_color,
        )
        embed.set_footer(
            text=bot_config.bot.trademark,
            icon_url=get_embed_icon(ctx),
        )
        await ctx.followup.send(
            embed=embed,
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )
        logger.info(
            f"Admin {ctx.user.name}({ctx.user.id}) cleared {len(deleted)} messages "
            f"in channel {ctx.channel.id}"
        )


def setup(bot: commands.Bot):
    bot.add_cog(AdminClear(bot))
