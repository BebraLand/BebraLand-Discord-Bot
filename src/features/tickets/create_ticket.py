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


async def send_dm_notification(user: discord.User, ticket_id: int, action: str, channel: discord.TextChannel = None, closed_by: discord.User = None, bot_user: discord.User = None):
    """Send DM notification to user about ticket action."""
    try:
        lang = await get_language(user.id)

        if action == "closed":
            closer_name = closed_by.name if closed_by else "Unknown"
            title = emoji.LOCK_EMOJI + " " + translate("Ticket Closed", lang)
            description = translate("Your ticket **#{ticket_id}** has been closed by **{closer_name}**.\nThank you for contacting support!", lang).format(
                ticket_id=ticket_id, closer_name=closer_name)
        elif action == "reopened":
            reopener_name = closed_by.name if closed_by else "support staff"
            title = emoji.UNLOCK_EMOJI + " " + \
                translate("Ticket Reopened", lang)
            description = translate("Your ticket **#{ticket_id}** has been reopened by **{reopener_name}**.\nYou can continue the conversation.", lang).format(
                ticket_id=ticket_id, reopener_name=reopener_name)
            if channel:
                description += f"\n\n**Channel:** {channel.mention}"

        embed = discord.Embed(
            title=title, description=description, color=constants.DISCORD_EMBED_COLOR)
        # Prefer explicit bot_user's avatar for footer icon; fall back to channel guild bot avatar when available
        icon_url = None
        if bot_user:
            try:
                icon_url = bot_user.display_avatar.url
            except Exception:
                icon_url = None
        elif channel and getattr(channel, "guild", None) and channel.guild.me:
            try:
                icon_url = channel.guild.me.avatar.url
            except Exception:
                icon_url = None

        if icon_url:
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=icon_url)
        else:
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK)

        await user.send(embed=embed)
        logger.info(
            f"Sent DM notification to user {user.id} for ticket #{ticket_id} action: {action}")
    except discord.Forbidden:
        logger.warning(
            f"Could not send DM to user {user.id} - DMs are disabled")
    except Exception as e:
        logger.error(f"Error sending DM notification: {e}")


async def create_transcript(channel: discord.TextChannel) -> io.BytesIO:
    """Create a text transcript of all messages in a channel."""
    transcript = io.StringIO()
    transcript.write(f"Transcript of #{channel.name}\n")
    transcript.write(
        f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
    transcript.write("=" * 80 + "\n\n")

    messages = []
    async for message in channel.history(limit=None, oldest_first=True):
        messages.append(message)

    for message in messages:
        timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S')
        transcript.write(
            f"[{timestamp}] {message.author.name} (ID: {message.author.id})\n")
        if message.content:
            transcript.write(f"{message.content}\n")
        if message.attachments:
            transcript.write("Attachments:\n")
            for attachment in message.attachments:
                transcript.write(
                    f"  - {attachment.filename} ({attachment.url})\n")
        if message.embeds:
            transcript.write(f"[{len(message.embeds)} embed(s)]\n")
        transcript.write("\n")

    transcript.write("=" * 80 + "\n")
    transcript.write(f"End of transcript - Total messages: {len(messages)}\n")

    transcript_bytes = io.BytesIO(transcript.getvalue().encode('utf-8'))
    transcript_bytes.seek(0)
    return transcript_bytes


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
