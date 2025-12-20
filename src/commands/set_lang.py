import discord
from discord.ext import commands
from discord import Option, OptionChoice
from src.utils.logger import get_cool_logger
from src.utils.database import get_language, set_language
from src.utils.get_embed_icon import get_embed_icon
import config.constants as constants
from src.languages import lang_constants as lang_constants
from src.views.language_selector import LanguageSelector, build_language_selector_embed
from src.languages.localize import _, locale_display_name


logger = get_cool_logger(__name__)


class SetLang(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(
        name="set_lang",
        description="Set the bot's language",
        description_localizations={
            "ru": "Установить язык бота",
            "lt": "Nustatyti boto kalbą"
        }
    )
    async def set_lang(
        self,
        ctx: discord.ApplicationContext,
        lang = Option(
            str,
            name="language",
            name_localizations={
                "ru": "язык",
                "lt": "kalba"
            },
            description="Choose a language",
            description_localizations={
                "ru": "Выберите язык",
                "lt": "Pasirinkite kalbą"
            },
            required=False,
            choices=[
                OptionChoice(
                    name="English",
                    value="en",
                    name_localizations={
                        "ru": "Английский",
                        "lt": "Anglų"
                    }
                ),
                OptionChoice(
                    name="Русский",
                    value="ru",
                    name_localizations={
                        "lt": "Rusų"
                    }
                ),
                OptionChoice(
                    name="Lietuvių",
                    value="lt",
                    name_localizations={
                        "ru": "Литовский"
                    }
                )
            ]
        )
    ):
        if lang:
            # Check current language first; short-circuit if unchanged
            logger.info(
                f"{ctx.user.name} ({ctx.user.id}) requested to set the language to {lang}")
            current_lang = await get_language(ctx.user.id)
            if current_lang == lang:
                logger.info(
                    f"{ctx.user.name} ({ctx.user.id}) tried to set the language to {lang}, but it is already set")
                already_msg = _("language.already_set", current_lang).format(
                    lang=locale_display_name(current_lang)
                )
                embed = discord.Embed(
                    title=f"{lang_constants.INFO_EMOJI} {_('common.info', current_lang)}",
                    description=already_msg,
                    color=discord.Color.blurple(),
                )

                embed.set_footer(
                    text=constants.DISCORD_MESSAGE_TRADEMARK,
                    icon_url=get_embed_icon(ctx))

                await ctx.respond(
                    embed=embed,
                    ephemeral=True,
                    delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
                )
                return

            try:
                logger.info(
                    f"{ctx.user.name} ({ctx.user.id}) is setting the bot's language to {lang}")
                await set_language(ctx.user.id, lang)
            except Exception as e:
                logger.error(
                    f"Error setting language for {ctx.user.name} ({ctx.user.id}): {e}")
                err_msg = _("common.error", current_lang)
                await ctx.respond(f"{lang_constants.ERROR_EMOJI} {err_msg}", ephemeral=True)
                return

            logger.info(
                f"{ctx.user.name} ({ctx.user.id}) set the bot's language to {lang}")
            ok_msg = _("language.set", lang).format(
                lang=locale_display_name(lang)
            )

            embed = discord.Embed(
                title=f"{lang_constants.SUCCESS_EMOJI} {_('common.success', lang)}",
                description=ok_msg,
                color=discord.Color.green(),
            )

            await ctx.respond(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
        else:
            logger.info(
                f"{ctx.user.name} ({ctx.user.id}) requested the language selector")
            # Localized prompt for selector when no language option is provided
            current_lang = await get_language(ctx.user.id)
            await ctx.respond(
                embed=build_language_selector_embed(ctx),
                view=LanguageSelector(),
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )


def setup(bot: commands.Bot):
    bot.add_cog(SetLang(bot))
