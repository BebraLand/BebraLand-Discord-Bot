import discord
import json
from pycord.i18n import _
from src.languages.localize import translate, locale_display_name
from src.utils.database import set_language, get_language
from src.utils.logger import get_cool_logger
from src.views.language_selector import build_selected_language_embed
import src.languages.lang_constants as lang_constants
import config.constants as constants

logger = get_cool_logger(__name__)

with open("config/tickets.json", "r", encoding="utf-8") as f:
    ticket_data = json.load(f)

ticket_categories = ticket_data["ticketCategories"]


def build_ticket_panel_embed(ctx: discord.ApplicationContext) -> discord.Embed:
    categories_text = "\n".join(
        f"{cat['emoji']} **{cat['name']}** — {cat['description']}"
        for cat in ticket_categories
    )

    embed = discord.Embed(
        title="🎫 Create a Ticket",
        description=f"Select a category below to create a ticket:\n\n{categories_text}",
        color=constants.DISCORD_EMBED_COLOR,
    )

    embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK,
                     icon_url=ctx.bot.user.display_avatar.url)
    return embed


class TicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        # Use plain text at import time; localized in __init__
        placeholder="Select a ticket category",
        min_values=1,
        max_values=1,
        custom_id="ticket_dropdown",
        options=[
            discord.SelectOption(label=cat['name'], emoji=cat['emoji'],
                                 description=cat['description'], value=cat['name'])
            for cat in ticket_categories
        ],
    )
    async def select_callback(self, select, interaction):
        await interaction.response.send_message(
            f"You selected the **{select.values[0]}** category. A ticket will be created for you shortly.",
            ephemeral=True)
