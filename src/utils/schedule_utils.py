from typing import Optional

import discord

import config.constants as constants
from src.languages import lang_constants
from src.languages.localize import _
from src.utils.database import get_language
from src.utils.embeds import get_embed_icon
from src.utils.normalize_unix import normalize_unix_timestamp


async def parse_and_validate_schedule(
    ctx: discord.ApplicationContext, schedule_time: str
) -> Optional[int]:
    """Parse schedule time. Sends error embed and returns None if invalid."""
    if not schedule_time:
        return None

    try:
        return normalize_unix_timestamp(schedule_time, require_future=True)
    except ValueError as e:
        current_lang = await get_language(ctx.user.id)
        desc = (
            f"**{str(e)}**\n\n"
            "Use a future Unix UTC timestamp in seconds, milliseconds, "
            "microseconds, nanoseconds, or Discord format like <t:1777217700:F>."
        )
        embed = discord.Embed(
            title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
            description=desc,
            color=constants.FAILED_EMBED_COLOR,
        )
        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(ctx)
        )

        # Determine if we should use respond or followup based on if deferred
        send_method = (
            ctx.followup.send if ctx.interaction.response.is_done() else ctx.respond
        )

        await send_method(
            embed=embed,
            ephemeral=True,
            delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
        )
        return None
