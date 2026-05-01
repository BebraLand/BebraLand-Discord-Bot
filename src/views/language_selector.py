import discord

import config.constants as constants
import src.languages.lang_constants as lang_constants
from src.languages.localize import _, locale_display_name
from src.utils.database import get_language, set_language
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger

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

    embed.add_field(
        name=lang_constants.US_FLAG + " " + lang_constants.ENGLISH,
        value="Select for English interface",
        inline=True,
    )
    embed.add_field(
        name=lang_constants.RU_FLAG + " " + lang_constants.RUSSIAN,
        value="Выберите для русского интерфейса",
        inline=True,
    )
    embed.add_field(
        name=lang_constants.LT_FLAG + " " + lang_constants.LITHUANIAN,
        value="Pasirinkite lietuvių kalbai",
        inline=True,
    )

    embed.set_footer(
        text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(ctx)
    )
    return embed


def build_selected_language_embed(
    interaction: discord.Interaction, lang: str
) -> discord.Embed:
    # Use selection-based locale to translate the confirmation message
    localized_name = locale_display_name(lang)
    description_text = _("language.set", lang).format(lang=localized_name)
    embed = discord.Embed(
        title=f"{lang_constants.SUCCESS_EMOJI} {_('common.success', lang)}",
        description=description_text,
        color=constants.SUCCESS_EMBED_COLOR,
    )

    embed.set_footer(
        text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction)
    )
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
            discord.SelectOption(
                label=lang_constants.ENGLISH,
                emoji=lang_constants.US_FLAG,
                description="Select for English interface",
                value="en",
            ),
            discord.SelectOption(
                label=lang_constants.RUSSIAN,
                emoji=lang_constants.RU_FLAG,
                description="Выберите для русского интерфейса",
                value="ru",
            ),
            discord.SelectOption(
                label=lang_constants.LITHUANIAN,
                emoji=lang_constants.LT_FLAG,
                description="Pasirinkite lietuvių kalbai",
                value="lt",
            ),
        ],
    )
    async def select_callback(self, select, interaction):
        lang = select.values[0]
        current_lang = await get_language(interaction.user.id)

        if current_lang == lang:
            logger.info(
                f"{interaction.user.name} ({interaction.user.id}) tried to set the language to {lang}, but it is already set"
            )
            embed = discord.Embed(
                title=f"{lang_constants.INFO_EMOJI} {_('common.info', current_lang)}",
                description=_("language.already_set", current_lang).format(
                    lang=locale_display_name(current_lang)
                ),
                color=constants.INFO_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction),
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
