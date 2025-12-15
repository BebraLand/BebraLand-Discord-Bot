import discord
import io
from datetime import datetime
import config.constants as constants
from src.utils.logger import get_cool_logger
from src.utils.database import get_db, get_language
from src.languages.localize import translate
from src.languages import emoji_constants as emoji
from src.features.tickets.view.CloseTicketView import CloseTicketView

logger = get_cool_logger(__name__)


async def create_ticket(user: discord.User, category_name: str, guild: discord.Guild) -> tuple[bool, str]:
    """Create a ticket for a user."""
    db = await get_db()
    lang = await get_language(user.id)

    ticket_count = await db.ticket_count(str(user.id))
    if ticket_count >= constants.MAX_TICKETS_PER_USER:
        logger.info(
            f"User {user.id} has reached the maximum number of tickets ({ticket_count}/{constants.MAX_TICKETS_PER_USER})")
        error_msg = emoji.CROSS_EMOJI + " " + translate("You already have {ticket_count} open ticket(s). Please close an existing ticket before creating a new one. (Maximum: {max})", lang).format(
            ticket_count=ticket_count, max=constants.MAX_TICKETS_PER_USER)
        return False, error_msg

    ticket_id = await db.create_ticket(str(user.id), category_name)
    if not ticket_id:
        logger.error(f"Failed to create ticket in database for user {user.id}")
        return False, emoji.CROSS_EMOJI + " " + translate("Failed to create ticket. Please try again later.", lang)

    category = guild.get_channel(constants.TICKET_CATEGORY)
    if not category or not isinstance(category, discord.CategoryChannel):
        logger.error(
            f"Ticket category {constants.TICKET_CATEGORY} not found or is not a category")
        return False, emoji.CROSS_EMOJI + " " + translate("Ticket system is not properly configured. Please contact an administrator.", lang)

    try:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=True, manage_channels=True, manage_messages=True)
        }

        if constants.TICKET_SUPPORT_ROLE_ID:
            support_role = guild.get_role(constants.TICKET_SUPPORT_ROLE_ID)
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=True, attach_files=True, embed_links=True, read_message_history=True)

        if constants.TICKET_SUPPORT_USER_IDS:
            for support_user_id in constants.TICKET_SUPPORT_USER_IDS:
                support_user = guild.get_member(support_user_id)
                if support_user:
                    overwrites[support_user] = discord.PermissionOverwrite(
                        read_messages=True, send_messages=True, attach_files=True, embed_links=True, read_message_history=True, manage_messages=True)

        channel = await category.create_text_channel(
            name=f"ticket-{ticket_id}-{user.name}",
            overwrites=overwrites,
            topic=f"Ticket #{ticket_id} | User: {user.name} | Category: {category_name}"
        )

        await db.update_ticket_channel(ticket_id, channel.id)

        # Welcome message always in English
        embed = discord.Embed(
            title=f"{emoji.TICKET_EMOJI} Ticket #{ticket_id}",
            description=f"Welcome {user.mention}!\n\n**Category:** {category_name}\n\nPlease describe your issue or question. A staff member will assist you shortly.\n\nTo close this press the close button",
            color=constants.DISCORD_EMBED_COLOR
        )
        embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK,
                         icon_url=guild.me.avatar.url)

        close_view = CloseTicketView(ticket_id, user, category_name)
        await channel.send(embed=embed, view=close_view)

        # Log the ticket creation
        if constants.TICKET_LOG_CHANNEL_ID:
            log_channel = guild.get_channel(constants.TICKET_LOG_CHANNEL_ID)
            if log_channel:
                log_embed = discord.Embed(
                    title=f"{emoji.TICKET_EMOJI} New Ticket Created",
                    description=f"**Ticket ID:** {ticket_id}\n**User:** {user.mention}\n**Category:** {category_name}\n**Channel:** {channel.mention}",
                    color=0x00FF00
                )
                log_embed.set_footer(
                    text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=guild.me.avatar.url)
                await log_channel.send(embed=log_embed)

        logger.info(
            f"Created ticket #{ticket_id} for user {user.id} in channel {channel.id}")

        # Return success embed instead of plain text
        success_embed = discord.Embed(
            title=emoji.CHECK_EMOJI + " " + translate("Ticket Created", lang),
            description=translate("Your ticket has been created: {channel}", lang).format(
                channel=channel.mention),
            color=0x00FF00
        )
        success_embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK)
        return True, success_embed

    except Exception as e:
        logger.error(f"Failed to create ticket channel: {e}")
        await db.close_ticket(ticket_id)
        return False, emoji.CROSS_EMOJI + " " + translate("Failed to create ticket channel. Please try again later.", lang)
