import discord
from pycord.i18n import _
from src.languages.localize import translate, locale_display_name
from src.utils.database import set_language, get_language
from src.utils.logger import get_cool_logger
import src.languages.lang_constants as lang_constants
import config.constants as constants
from src.utils.get_embed_icon import get_embed_icon

logger = get_cool_logger(__name__)

def build_language_selector_embed(ctx: discord.ApplicationContext) -> discord.Embed:
    embed = discord.Embed(
      title=":earth_africa: Language Selection / Выбор языка / Kalbos pasirinkimas",
      description=(
        f"**{lang_constants.ENGLISH}**: Please select your preferred language from the dropdown below. "
        "This will be used for all bot interactions.\n\n"
        f"**{lang_constants.RUSSIAN}**: Пожалуйста, выберите предпочитаемый язык из выпадающего списка ниже. "
        "Он будет использоваться для всех взаимодействий с ботом.\n\n"
        f"**{lang_constants.LITHUANIAN}**: Prašome pasirinkti pageidaujamą kalbą iš žemiau esančio sąrašo. "
        "Ji bus naudojama visoms bot sąveikoms."
      ),
      color=constants.DISCORD_EMBED_COLOR,
    )

    embed.add_field(name=lang_constants.US_FLAG + " " + lang_constants.ENGLISH, value="Select for English interface", inline=True)
    embed.add_field(name=lang_constants.RU_FLAG + " " + lang_constants.RUSSIAN, value="Выберите для русского интерфейса", inline=True)
    embed.add_field(name=lang_constants.LT_FLAG + " " + lang_constants.LITHUANIAN, value="Pasirinkite lietuvių kalbai", inline=True)

    embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(ctx))
    return embed

def build_selected_language_embed(interaction: discord.Interaction, lang: str) -> discord.Embed:
    # Use selection-based locale to translate the confirmation message
    localized_name = locale_display_name(lang)
    description_text = translate("Language set to {lang}!", lang).format(lang=localized_name)
    embed = discord.Embed(
      title=f"✅ {translate('Success', lang)}",
      description=description_text,
      color=discord.Color.green(),
    )
    
    embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(ctx))
    return embed

class LanguageSelector(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        # Use plain text at import time; localized in __init__
        placeholder="Select your language",
        min_values=1,
        max_values=1,
        custom_id="language_dropdown",
        options=[
            discord.SelectOption(label=lang_constants.ENGLISH, emoji=lang_constants.US_FLAG, description="Select for English interface", value="en"),
            discord.SelectOption(label=lang_constants.RUSSIAN, emoji=lang_constants.RU_FLAG, description="Выберите для русского интерфейса", value="ru"),
            discord.SelectOption(label=lang_constants.LITHUANIAN, emoji=lang_constants.LT_FLAG, description="Pasirinkite lietuvių kalbai", value="lt"),
        ],
    )
    async def select_callback(self, select, interaction):
        lang = select.values[0]
        current_lang = await get_language(interaction.user.id)

        if current_lang == lang:
            logger.info(
                f"{interaction.user.name} ({interaction.user.id}) tried to set the language to {lang}, but it is already set"
            )
            already_msg = translate("Your language is already {lang}.", current_lang).format(
                lang=locale_display_name(current_lang)
            )
            embed = discord.Embed(
                title=f"ℹ️ {translate('Info', current_lang)}",
                description=already_msg,
                color=discord.Color.blurple(),
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(ctx),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
            return

        await set_language(interaction.user.id, lang)
        await interaction.response.send_message(
            ephemeral=True,
            delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            embed=build_selected_language_embed(interaction, lang),
        )
        logger.info(
            f"{interaction.user.name} ({interaction.user.id}) set the bot's language to {lang}"
        )