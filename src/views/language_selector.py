import json

import discord

import src.languages.lang_constants as lang_constants
from config.config import config as bot_config
from src.languages.localize import _, locale_display_name
from src.utils.database import get_language, set_language
from src.utils.embeds import build_embeds_from_message_data, get_embed_icon
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)

LANGUAGE_MESSAGE_PATH = "src/languages/messages/language.json"


def _load_language_message() -> dict:
    try:
        with open(LANGUAGE_MESSAGE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Language message config not found: {LANGUAGE_MESSAGE_PATH}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse {LANGUAGE_MESSAGE_PATH}: {e}")

    return {
        "embeds": [
            {
                "title": "Language selection unavailable",
                "description": "The language message configuration could not be loaded.",
                "color": bot_config.embeds.failed_color,
            }
        ]
    }


def _language_replacements(source) -> dict:
    bot_avatar = get_embed_icon(source)
    return {
        "{trademark}": bot_config.bot.trademark,
        "{bot_avatar}": bot_avatar,
        "trademark": bot_config.bot.trademark,
        "bot_avatar": bot_avatar,
    }


def build_language_selector_embeds(source) -> list[discord.Embed]:
    message = _load_language_message()
    return build_embeds_from_message_data(
        message,
        replacements=_language_replacements(source),
        default_color=None,
        fallback={
            "title": "Language selection unavailable",
            "description": "The language message configuration could not be loaded.",
            "color": bot_config.embeds.failed_color,
        },
    )


def build_language_selector_embed(source) -> discord.Embed:
    return build_language_selector_embeds(source)[0]


def build_selected_language_embed(
    interaction: discord.Interaction, lang: str
) -> discord.Embed:
    # Use selection-based locale to translate the confirmation message
    localized_name = locale_display_name(lang)
    description_text = _("language.set", lang).format(lang=localized_name)
    embed = discord.Embed(
        title=f"{lang_constants.SUCCESS_EMOJI} {_('common.success', lang)}",
        description=description_text,
        color=bot_config.embeds.success_color,
    )

    embed.set_footer(
        text=bot_config.bot.trademark, icon_url=get_embed_icon(interaction)
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
                color=bot_config.embeds.info_color,
            )
            embed.set_footer(
                text=bot_config.bot.trademark,
                icon_url=get_embed_icon(interaction),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
            return

        await set_language(interaction.user.id, lang)
        await interaction.response.send_message(
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
            embed=build_selected_language_embed(interaction, lang),
        )
        logger.info(
            f"{interaction.user.name} ({interaction.user.id}) set the bot's language to {lang}"
        )
