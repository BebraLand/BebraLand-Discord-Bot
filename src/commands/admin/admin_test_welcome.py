import discord
from discord.ext import commands
from discord import Option
from src.utils.logger import get_cool_logger
from src.languages.localize import _
from src.utils.database import get_language
from src.utils.auth import require_admin
import config.constants as constants
from src.languages import lang_constants as lang_constants
from pycord.multicog import subcommand
from src.utils.get_embed_icon import get_embed_icon
from src.utils.welcome import sent_welcome_message


logger = get_cool_logger(__name__)


class adminTestWelcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    
    @subcommand("admin")
    @discord.slash_command(
        name="test_welcome_admin",
        description="Test welcome message for the user",
        description_localizations={
            "ru": "Тестовое приветственное сообщение для пользователя",
            "lt": "Testinis pasveikinimo pranešimas vartotojui"
        }
    )
    async def test_welcome_admin(
        self,
        ctx: discord.ApplicationContext,
        user: discord.User = Option(
            discord.User,
            name="user",
            name_localizations={
                "ru": "пользователь",
                "lt": "naudotojas"
            },
            description="Target user",
            description_localizations={
                "ru": "Целевой пользователь",
                "lt": "Tikslo naudotojas"
            },
            required=False
        )
    ):
        await ctx.defer(ephemeral=True)

        if not await require_admin(ctx):
            logger.info(
                f"{ctx.user.name}({ctx.user.id}) used admin command without permissions")
            return

        current_lang = await get_language(ctx.user.id)

        target_user = user or ctx.user

        if target_user.bot:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
                description=_(
                    "dm.cant_clear_bot_dm", current_lang),
                color=discord.Color.red(),
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(ctx),
            )
            await ctx.respond(embed=embed, ephemeral=True, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)
            return

        await sent_welcome_message(target_user, ctx.bot)


        embed = discord.Embed(
            title=f"{lang_constants.SUCCESS_EMOJI} {_('common.success', current_lang)}",
            description=_(
                "welcome.test_sent", current_lang).format(user=target_user.mention),
            color=discord.Color.green(),
        )
        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=get_embed_icon(ctx),
        )
        await ctx.respond(embed=embed, ephemeral=True, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)
        logger.info(
            f"Admin {ctx.user.name}({ctx.user.id}) tested welcome message for {target_user.name}({target_user.id})"
        )


def setup(bot: commands.Bot):
    bot.add_cog(adminTestWelcome(bot))