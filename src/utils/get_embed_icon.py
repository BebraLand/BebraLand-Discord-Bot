from config.constants import DISCORD_EMBED_FOOTER_ICON
import discord


def get_embed_icon(ctx) -> str:
    """Return an avatar URL to use in embed footers.

    Accepts various context-like objects: ApplicationContext, Interaction,
    a `discord.Bot`/`discord.Client`, `discord.Guild`, or `discord.User`/`Member`.

    Priority:
    1. `DISCORD_EMBED_FOOTER_ICON` constant if set
    2. Bot user's `display_avatar` / `avatar`
    3. Guild bot member avatar (if available)
    4. Empty string fallback
    """
    if DISCORD_EMBED_FOOTER_ICON:
        return DISCORD_EMBED_FOOTER_ICON

    bot_user = None

    # If caller passed a User/Member/ClientUser directly (check this first)
    if isinstance(ctx, (discord.User, discord.Member, discord.ClientUser)):
        bot_user = ctx
    # If caller passed a bot/client instance
    elif isinstance(ctx, (discord.Client, discord.Bot)):
        bot_user = getattr(ctx, "user", None)
    # If ctx is None, return empty string early
    elif ctx is None:
        return ""
    else:
        # If caller passed an ApplicationContext or Interaction
        bot = getattr(ctx, "bot", None) or getattr(ctx, "client", None)
        if bot:
            bot_user = getattr(bot, "user", None)

    # Try to return bot user's avatar
    if bot_user is not None:
        for attr in ("display_avatar", "avatar", "default_avatar"):
            try:
                avatar = getattr(bot_user, attr, None)
                if avatar is not None:
                    return avatar.url
            except Exception:
                continue

    # Fallback: if a guild-like object was passed, try its member avatar
    guild = getattr(ctx, "guild", None)
    if guild is not None:
        me = getattr(guild, "me", None)
        if me is not None:
            for attr in ("display_avatar", "avatar", "default_avatar"):
                try:
                    avatar = getattr(me, attr, None)
                    if avatar is not None:
                        return avatar.url
                except Exception:
                    continue

    return ""