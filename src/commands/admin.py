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

    @commands.slash_command(
        name="admin",
        default_member_permissions=discord.Permissions(administrator=True),
        contexts={discord.InteractionContextType.guild},
        description="Admin commands",
        description_localizations={
            "ru": "Административные команды",
            "lt": "Administracijos komandos"
        },
    )
    async def admin(
        self,
        ctx: discord.ApplicationContext,
        type: Option(
            str,
            description="Choose admin action",
            description_localizations={
                "ru": "Выбрать действие администратора",
                "lt": "Pasirinkti administratoriaus veiksmą",
            },
            required=False,
            choices=[
                OptionChoice(
                    name="Language dropdown",
                    value="language_dropdown",
                    name_localizations={
                        "ru": "Выпадающий список языка",
                        "lt": "Kalbos meniu",
                    },
                ),
            ],
        )
    ):
        if not await require_admin(ctx):
            logger.info(f"{ctx.user.name}({ctx.user.id}) used admin command without permissions")
            return

        await ctx.defer()

        if type == "language_dropdown":
            try:
                logger.info(f"{ctx.user.name}({ctx.user.id}) used admin command with language dropdown")
                await ctx.channel.send(embed=build_language_selector_embed(ctx), view=LanguageSelector())
                await ctx.respond("Language dropdown message sent!", ephemeral=True, delete_after=0)
            except discord.errors.NotFound:
                logger.error(f"{ctx.user.name}({ctx.user.id}) used admin command with language dropdown, but the channel was not found")
                await ctx.respond("Language dropdown message not found. Please make sure the bot has permissions to send messages in this channel.", ephemeral=True, delete_after=1)
        else:
            logger.info(f"{ctx.user.name}({ctx.user.id}) used admin command")
            await ctx.respond("Admin command used!", ephemeral=True, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)



def setup(bot: commands.Bot):
    bot.add_cog(admin(bot))
