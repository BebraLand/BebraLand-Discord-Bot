import discord

from config.config import config as bot_config
from src.features.tickets.view.CloseTicketView import CloseTicketView
from src.languages import lang_constants as lang_constants
from src.languages.localize import _
from src.utils.database import get_db, get_language
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


async def create_ticket(
    user: discord.User,
    category_name: str,
    guild: discord.Guild,
    form_responses: dict = None,
) -> tuple[bool, str]:
    """Create a ticket for a user.

    Args:
        user: The user creating the ticket
        category_name: Name of the ticket category
        guild: The Discord guild
        form_responses: Optional dict of form responses {field_key: {"question": str, "value": str}}
    """
    db = await get_db()
    lang = await get_language(user.id)

    ticket_count = await db.ticket_count(str(user.id))
    if ticket_count >= bot_config.modules.tickets.max_per_user:
        logger.info(
            f"User {user.id} has reached the maximum number of tickets ({ticket_count}/{bot_config.modules.tickets.max_per_user})"
        )
        text = _("tickets.max_reached", lang).format(
            ticket_count=ticket_count, max=bot_config.modules.tickets.max_per_user
        )

        error_msg = f"{lang_constants.ERROR_EMOJI} {text}"
        return False, error_msg

    ticket_id = await db.create_ticket(str(user.id), category_name)
    if not ticket_id:
        logger.error(f"Failed to create ticket in database for user {user.id}")
        return (
            False,
            f"{lang_constants.ERROR_EMOJI} {_('tickets.creation_failed', lang)}",
        )

    category = guild.get_channel(bot_config.modules.tickets.category_id)
    if not category or not isinstance(category, discord.CategoryChannel):
        logger.error(
            f"Ticket category {bot_config.modules.tickets.category_id} not found or is not a category"
        )
        return (
            False,
            f"{lang_constants.ERROR_EMOJI} {_('tickets.not_configured', lang)}",
        )

    try:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                read_message_history=True,
            ),
            guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                manage_channels=True,
                manage_messages=True,
            ),
        }

        if bot_config.modules.tickets.support_role_id:
            support_role = guild.get_role(bot_config.modules.tickets.support_role_id)
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True,
                )

        if bot_config.modules.tickets.support_user_ids:
            for support_user_id in bot_config.modules.tickets.support_user_ids:
                support_user = guild.get_member(support_user_id)
                if support_user:
                    overwrites[support_user] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        attach_files=True,
                        embed_links=True,
                        read_message_history=True,
                        manage_messages=True,
                    )

        channel = await category.create_text_channel(
            name=f"ticket-{ticket_id}-{user.name}",
            overwrites=overwrites,
            topic=f"Ticket #{ticket_id} | User: {user.name} | Category: {category_name}",
        )

        await db.update_ticket_channel(ticket_id, channel.id)

        # Welcome message always in English
        embed = discord.Embed(
            title=f"{lang_constants.TICKET_EMOJI} Ticket #{ticket_id}",
            description=f"Welcome {user.mention}!\n\n**Category:** {category_name}\n\nPlease describe your issue or question. A staff member will assist you shortly.\n\nTo close this press the close button",
            color=bot_config.embeds.default_color,
        )
        embed.set_footer(
            text=bot_config.bot.trademark, icon_url=get_embed_icon(guild.me)
        )

        close_view = CloseTicketView(ticket_id, user, category_name)
        await channel.send(embed=embed, view=close_view)

        # If form responses exist, send an additional embed with the form data
        if form_responses:
            form_embed = discord.Embed(
                title=f"{lang_constants.FORM_EMOJI} Form Responses",
                description=f"{user.mention} provided the following information:",
                color=bot_config.embeds.default_color,
            )

            # Add each form response as a field
            for response in form_responses.values():
                question = response["question"]
                value = response["value"]

                # Truncate long values if necessary (embed field value max is 1024)
                if len(value) > 1024:
                    value = value[:1021] + "..."

                form_embed.add_field(name=question, value=value, inline=False)

            form_embed.set_footer(
                text=bot_config.bot.trademark,
                icon_url=get_embed_icon(guild.me),
            )
            await channel.send(embed=form_embed)

        # Log the ticket creation
        if bot_config.modules.tickets.log_channel_id:
            log_channel = guild.get_channel(bot_config.modules.tickets.log_channel_id)
            if log_channel:
                log_embed = discord.Embed(
                    title=f"{lang_constants.TICKET_EMOJI} New Ticket Created",
                    description=f"**Ticket ID:** {ticket_id}\n**User:** {user.mention}\n**Category:** {category_name}\n**Channel:** {channel.mention}",
                    color=bot_config.embeds.success_color,
                )
                log_embed.set_footer(
                    text=bot_config.bot.trademark,
                    icon_url=get_embed_icon(guild.me),
                )
                await log_channel.send(embed=log_embed)

        logger.info(
            f"Created ticket #{ticket_id} for user {user.id} in channel {channel.id}"
        )

        # Return success embed instead of plain text
        success_embed = discord.Embed(
            title=f"{lang_constants.SUCCESS_EMOJI} {_('tickets.created', lang)}",
            description=_("tickets.created_channel", lang).format(
                channel=channel.mention
            ),
            color=bot_config.embeds.success_color,
        )
        success_embed.set_footer(
            text=bot_config.bot.trademark, icon_url=get_embed_icon(guild.me)
        )
        return True, success_embed

    except Exception as e:
        logger.error(f"Failed to create ticket channel: {e}")
        await db.close_ticket(ticket_id)
        return (
            False,
            f"{lang_constants.ERROR_EMOJI} {_('tickets.channel_failed', lang)}",
        )
