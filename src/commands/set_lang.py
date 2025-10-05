import discord
from discord.ext import commands
from discord import Option, OptionChoice
from src.utils.logger import get_cool_logger
from src.utils.database import get_language, set_language
import config.constants as constants
from src.views.language_selector import LanguageSelector, build_language_selector_embed


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
        lang: Option(
            str,
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
            current_lang = await get_language(ctx.user.id)
            if current_lang == lang:
                await ctx.respond(
                    f"ℹ️ Your language is already **{lang}**.",
                    ephemeral=True,
                    delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
                )
                return

            try:
                await set_language(ctx.user.id, lang)
            except Exception as e:
                logger.error(f"Error setting language for {ctx.user.name} ({ctx.user.id}): {e}")
                await ctx.respond("❌ An error occurred while setting the language.", ephemeral=True)
                return

            logger.info(f"{ctx.user.name} ({ctx.user.id}) set the bot's language to {lang}")
            await ctx.respond(f"✅ Language set to **{lang}**!", ephemeral=True, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)
        else:
            await ctx.respond(
                embed=build_language_selector_embed(ctx),
                view=LanguageSelector(),
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )


def setup(bot: commands.Bot):
    bot.add_cog(SetLang(bot))
