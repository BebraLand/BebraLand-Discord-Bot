from src.languages import lang_constants as lang_constants
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


async def send_rules_panel(target_channel: int) -> None:
    from src.utils.bot_instance import get_bot
    from src.views.rules_panel import RulesView, build_rules_embed

    bot = get_bot()
    if bot is None:
        logger.error("Bot instance not available for send_rules_panel")
        return

    channel = bot.get_channel(target_channel)
    if channel is None:
        try:
            channel = await bot.fetch_channel(target_channel)
        except Exception:
            pass

    if channel is None:
        logger.error(f"Rules panel target channel not found: {target_channel}")
        return

    try:
        await channel.send(embed=build_rules_embed(bot), view=RulesView(bot))
        logger.info(
            f"{lang_constants.SUCCESS_EMOJI} Scheduled rules panel sent to channel {channel.id}"
        )
    except Exception as e:
        logger.error(f"Error sending rules panel to {channel.id}: {e}")
