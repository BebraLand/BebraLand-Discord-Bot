import discord
import json
from src.utils.logger import get_cool_logger
import config.constants as constants
from src.languages import lang_constants as lang_constants
from src.languages.localize import _
from ..create_ticket import create_ticket
from src.utils.embeds import get_embed_icon
from .TicketFormModal import TicketFormModal
from src.utils.database import get_db, get_language

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
        title=f"{lang_constants.TICKET_EMOJI} Create a Ticket",
        description=f"Select a category below to create a ticket:\n\n{categories_text}",
        color=constants.DISCORD_EMBED_COLOR,
    )

    embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK,
                     icon_url=get_embed_icon(ctx))
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
        
        # Check ticket count BEFORE showing modal or creating ticket
        db = await get_db()
        lang = await get_language(interaction.user.id)
        ticket_count = await db.ticket_count(str(interaction.user.id))
        
        if ticket_count >= constants.MAX_TICKETS_PER_USER:
            logger.info(
                f"User {interaction.user.id} has reached the maximum number of tickets ({ticket_count}/{constants.MAX_TICKETS_PER_USER})")
            
            text = _('tickets.max_reached', lang).format(
                ticket_count=ticket_count,
                max=constants.MAX_TICKETS_PER_USER
            )
            error_msg = f"{lang_constants.ERROR_EMOJI} {text}"
            
            await interaction.response.send_message(error_msg, ephemeral=True)
            
            # Reset the dropdown selection
            try:
                await interaction.message.edit(view=TicketPanel())
            except:
                pass
            
            return
        
        # Find the category data
        category_data = next(
            (cat for cat in ticket_categories if cat['name'] == category_name),
            None
        )
        
        # Check if this category has forms
        if category_data and category_data.get("forms") and len(category_data["forms"]) > 0:
            # Show modal with forms
            modal = TicketFormModal(category_name, category_data, interaction.message)
            await interaction.response.send_modal(modal)
            
            # Reset the dropdown selection by editing the original message with a fresh view
            try:
                await interaction.message.edit(view=TicketPanel())
            except:
                pass  # Ignore if message cannot be edited
            
            logger.info(f"Showing form modal for category '{category_name}' to user {interaction.user.id}")
        else:
            # No forms, proceed with direct ticket creation
            # Defer the response as ticket creation might take a moment
            await interaction.response.defer(ephemeral=True)
            
            # Create the ticket without form responses
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
            
            # Reset the dropdown selection by editing the original message with a fresh view
            try:
                await interaction.message.edit(view=TicketPanel())
            except:
                pass  # Ignore if message cannot be edited
            
            logger.info(f"Ticket creation attempt by {interaction.user.id} for category '{category_name}': {'Success' if success else 'Failed'}")
