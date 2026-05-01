from src.languages import lang_constants as lang_constants
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


async def send_twitch_panel(target_channel) -> None:
    from src.utils.bot_instance import get_bot

    bot = get_bot()

    channel = bot.get_channel(target_channel)
    if channel is None:
        try:
            channel = await bot.fetch_channel(target_channel)
        except Exception:
            pass

    if channel is None:
        return

    try:
        from src.features.twitch.view.TwitchPanel import (
            TwitchPanel,
            build_twitch_panel_embed,
        )

        embed = build_twitch_panel_embed(bot)
        await channel.send(embed=embed, view=TwitchPanel())
        logger.info(
            f"{lang_constants.SUCCESS_EMOJI} Scheduled Twitch panel sent to channel {channel.id}"
        )
    except Exception as e:
        logger.error(f"Error sending scheduled Twitch panel to {channel.id}: {e}")
