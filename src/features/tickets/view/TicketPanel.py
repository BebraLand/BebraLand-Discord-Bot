import discord
import json
from pycord.i18n import _
from src.utils.logger import get_cool_logger
import config.constants as constants
from ..create_ticket import create_ticket

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
        category_name = select.values[0]
        
        # Defer the response as ticket creation might take a moment
        await interaction.response.defer(ephemeral=True)
        
        # Create the ticket
        success, message = await create_ticket(interaction.user, category_name, interaction.guild)
        
        # Send the response - message can be either a string or an embed
        if isinstance(message, discord.Embed):
            await interaction.followup.send(
                embed=message,
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                message,
                ephemeral=True
            )
        
        logger.info(f"Ticket creation attempt by {interaction.user.id} for category '{category_name}': {'Success' if success else 'Failed'}")
