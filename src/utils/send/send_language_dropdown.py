

from src.utils.logger import get_cool_logger
from src.languages import lang_constants as lang_constants
from src.views.language_selector import build_language_selector_embed, LanguageSelector


logger = get_cool_logger(__name__)


async def send_language_dropdown(channel_id: int) -> None:
    from src.utils.bot_instance import get_bot
    bot = get_bot()
    
    if not bot:
        logger.error("Bot instance is not initialized yet.")
        return
        
    channel = bot.get_channel(channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception as e:
            logger.error(f"Failed to fetch channel {channel_id} for language dropdown: {e}")
            return
            
    embed = build_language_selector_embed(bot)
    await channel.send(embed=embed, view=LanguageSelector())
    logger.info(
        f"{lang_constants.SUCCESS_EMOJI} Scheduled language dropdown sent to channel {channel.id}")