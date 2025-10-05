import discord
from pycord.i18n import _
from src.utils.database import set_language
from src.utils.logger import get_cool_logger
import src.languages.lang_constants as lang_constants
import config.constants as constants

logger = get_cool_logger(__name__)

def build_language_selector_embed(ctx: discord.ApplicationContext) -> discord.Embed:
    embed = discord.Embed(
      title=_(":earth_africa: Language Selection"),
      description=_("Please select your preferred language from the dropdown below. This will be used for all bot interactions."),
      color=constants.DISCORD_EMBED_COLOR,
    )

    embed.add_field(name=lang_constants.US_FLAG + " " + lang_constants.ENGLISH, value=_("Select for English interface"), inline=True)
    embed.add_field(name=lang_constants.RU_FLAG + " " + lang_constants.RUSSIAN, value=_("Select for Russian interface"), inline=True)
    embed.add_field(name=lang_constants.LT_FLAG + " " + lang_constants.LITHUANIAN, value=_("Select for Lithuanian language"), inline=True)

    embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=ctx.bot.user.display_avatar.url)
    return embed

def build_selected_language_embed(interaction: discord.Interaction, lang: str) -> discord.Embed:
    embed = discord.Embed(
      title=_("Language set to {lang}!").format(lang=lang),
      color=constants.DISCORD_EMBED_COLOR,
    )
    
    embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=interaction.client.user.display_avatar.url)
    return embed

class LanguageSelector(discord.ui.View):
    @discord.ui.select(
        # Use plain text at import time; localized in __init__
        placeholder="Select your language",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label=lang_constants.ENGLISH, emoji=lang_constants.US_FLAG, description="Select for English interface", value="en"),
            discord.SelectOption(label=lang_constants.RUSSIAN, emoji=lang_constants.RU_FLAG, description="Select for Russian interface", value="ru"),
            discord.SelectOption(label=lang_constants.LITHUANIAN, emoji=lang_constants.LT_FLAG, description="Select for Lithuanian language", value="lt"),
        ],
    )
    async def select_callback(self, select, interaction):
        lang = select.values[0]
        await set_language(interaction.user.id, lang)
        await interaction.response.send_message(
            ephemeral=True,
            delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            embed=build_selected_language_embed(interaction, lang)
        )
        logger.info(f"{interaction.user.name} ({interaction.user.id}) set the bot's language to {lang}")

    def __init__(self):
        super().__init__(timeout=180)
        # Ensure placeholder and option descriptions are localized at runtime
        for child in self.children:
            if isinstance(child, discord.ui.Select):
                child.placeholder = _("Select your language")
                for opt in child.options:
                    if opt.label == lang_constants.ENGLISH:
                        opt.description = _("Select for English interface")
                    elif opt.label == lang_constants.RUSSIAN:
                        opt.description = _("Select for Russian interface")
                    elif opt.label == lang_constants.LITHUANIAN:
                        opt.description = _("Select for Lithuanian language")