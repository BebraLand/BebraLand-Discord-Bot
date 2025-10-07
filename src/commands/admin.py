import discord
from discord.ext import commands
from discord import Option, OptionChoice
from src.utils.logger import get_cool_logger
from src.views.language_selector import LanguageSelector, build_language_selector_embed
from src.utils.auth import require_admin
import config.constants as constants


logger = get_cool_logger(__name__)


class admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    # Define SlashCommandGroup as a class attribute for proper Cog integration
    admin_group = discord.SlashCommandGroup("admin", "Admin related commands")

    @admin_group.command(name="language_dropdown",
                         description="Send a language dropdown message to the current channel",
                         description_localizations={
                             "ru": "Отправить сообщение с выбором языка",
                             "lt": "Siųsti žymėjimo lango pranešimą"
                         })
    async def language_dropdown(self, ctx: discord.ApplicationContext):
        if not await require_admin(ctx):
            logger.info(
                f"{ctx.user.name}({ctx.user.id}) used admin command without permissions")
            return

        await ctx.defer()

        try:
            logger.info(
                f"{ctx.user.name}({ctx.user.id}) used admin command with language dropdown")
            await ctx.channel.send(embed=build_language_selector_embed(ctx), view=LanguageSelector())
            await ctx.respond("Language dropdown message sent!", ephemeral=True, delete_after=0)
        except discord.errors.NotFound:
            logger.error(
                f"{ctx.user.name}({ctx.user.id}) used admin command with language dropdown, but the channel was not found")
            await ctx.respond(
                "Language dropdown message not found. Please make sure the bot has permissions to send messages in this channel.",
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )


def setup(bot: commands.Bot):
    bot.add_cog(admin(bot))
