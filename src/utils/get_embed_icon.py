from config.constants import DISCORD_EMBED_FOOTER_ICON
import discord


def get_embed_icon(ctx: discord.ApplicationContext) -> str:
    """Return an avatar URL to use in embed footers.

    Priority:
    1. `DISCORD_EMBED_FOOTER_ICON` constant if set
    2. Bot user's `display_avatar`
    3. Guild bot member avatar (if available)
    4. Empty string fallback
    """
    if DISCORD_EMBED_FOOTER_ICON:
        return DISCORD_EMBED_FOOTER_ICON

    bot_user = getattr(ctx, "bot", None) and getattr(ctx.bot, "user", None)
    # Prefer display_avatar which always exists
    if bot_user is not None:
        try:
            return bot_user.display_avatar.url
        except Exception:
            pass

    # Fallback to guild member avatar if present
    guild = getattr(ctx, "guild", None)
    if guild is not None:
        me = getattr(guild, "me", None)
        if me is not None:
            try:
                return me.display_avatar.url
            except Exception:
                pass

    return ""