import discord
from discord.ext import commands
from src.utils.logger import get_cool_logger
from src.languages.localize import _
from src.utils.database import get_language
from src.utils.clear_dm_messages import clear_dm_messages
import config.constants as constants
from src.languages import lang_constants as lang_constants
from src.utils.get_embed_icon import get_embed_icon


logger = get_cool_logger(__name__)


class clear_dm(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(name="clear_dm",
                            description="Clear the bot's DM",
                            description_localizations={
                                "ru": "Очистить DM с ботом",
                                "lt": "Išvalyti DM su botu"
                            },)
    async def clear_dm(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)

        current_lang = await get_language(ctx.user.id)
        deleted_count = await clear_dm_messages(ctx)

        if deleted_count > 0:
            description_text = _("dm.cleared_own", current_lang,).format(
                count=deleted_count)
        else:
            description_text = _("dm.no_messages_own", current_lang)
        embed = discord.Embed(
            title=f"{lang_constants.SUCCESS_EMOJI} {_('common.success', current_lang)}",
            description=description_text,
            color=discord.Color.green(),
        )
        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=get_embed_icon(ctx),
        )

        await ctx.followup.send(
            embed=embed,
            ephemeral=True,
            delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
        )
        logger.info(
            f"{ctx.user.name}({ctx.user.id}) cleared the bot's DM; deleted={deleted_count}"
        )


def setup(bot: commands.Bot):
    bot.add_cog(clear_dm(bot))
