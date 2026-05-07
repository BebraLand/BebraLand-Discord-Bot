import discord

import src.languages.lang_constants as lang_constants
from config.config import config as bot_config
from src.languages.localize import _
from src.utils.database import get_language
from src.utils.embeds import get_embed_icon


def is_admin(user_id: int) -> bool:
    return user_id in bot_config.bot.admin_list


async def require_admin(ctx) -> bool:
    if not is_admin(ctx.user.id):
        current_lang = await get_language(ctx.user.id)
        embed = discord.Embed(
            title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
            description=_("auth.not_authorized", current_lang),
            color=bot_config.embeds.failed_color,
        )

        embed.set_footer(
            text=bot_config.bot.trademark, icon_url=get_embed_icon(ctx)
        )
        await ctx.respond(
            embed=embed,
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )
        return False
    return True
