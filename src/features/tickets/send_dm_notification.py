import discord
import config.constants as constants
from src.utils.logger import get_cool_logger
from src.utils.database import get_language
from src.languages.localize import translate
from src.languages import emoji_constants as emoji

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