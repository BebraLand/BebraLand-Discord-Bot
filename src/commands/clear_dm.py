import discord
from discord.ext import commands
from src.utils.logger import get_cool_logger
import config.constants


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
        await ctx.defer()
        logger.info(f"{ctx.user.name}({ctx.user.id}) cleared the bot's DM")
        await ctx.respond("DM cleared!", ephemeral=True, delete_after=config.constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)


def setup(bot: commands.Bot):
    bot.add_cog(clear_dm(bot))
