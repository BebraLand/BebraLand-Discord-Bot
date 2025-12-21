import discord
import config.constants as constants
from src.utils.logger import get_cool_logger
from src.utils.database import get_language
from src.languages.localize import _
from src.languages import lang_constants as lang_constants
from src.utils.get_embed_icon import get_embed_icon

logger = get_cool_logger(__name__)


async def send_dm_notification(user: discord.User, ticket_id: int, action: str, channel: discord.TextChannel = None, closed_by: discord.User = None, bot_user: discord.User = None):
    """Send DM notification to user about ticket action."""
    try:
        lang = await get_language(user.id)

        if action == "closed":
            closer_name = closed_by.name if closed_by else "Unknown"
            title = f"{lang_constants.LOCK_EMOJI} {_('tickets.closed', lang)}"
            description = _("tickets.dm.closed_by", lang).format(
                ticket_id=ticket_id, closer_name=closer_name)
        elif action == "reopened":
            reopener_name = closed_by.name if closed_by else "support staff"
            title = lang_constants.UNLOCK_EMOJI + " " + \
                _("tickets.reopened", lang)
            description = _("tickets.dm.reopened_by", lang).format(
                ticket_id=ticket_id, reopener_name=reopener_name)
            if channel:
                description += f"\n\n**Channel:** {channel.mention}"

        embed = discord.Embed(
            title=title, description=description, color=constants.DISCORD_EMBED_COLOR)

        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(bot_user))

        await user.send(embed=embed)
        logger.info(
            f"Sent DM notification to user {user.id} for ticket #{ticket_id} action: {action}")
    except discord.Forbidden:
        logger.warning(
            f"Could not send DM to user {user.id} - DMs are disabled")
    except Exception as e:
        logger.error(f"Error sending DM notification: {e}")
