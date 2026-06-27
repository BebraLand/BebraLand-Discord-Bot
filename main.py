import discord
from pycord.multicog import Bot

import src.languages.lang_constants as lang_constants
from config.config import config as bot_config
from src.api.health import HealthAPI
from src.features.applications.service import cleanup_old_applications
from src.features.applications.view.ApplicationPanel import ApplicationPanel
from src.features.status.status_monitor import get_status_monitor
from src.features.temp_voice_channels.restore_temp_channels import restore_temp_channels
from src.features.tickets.view.TicketPanel import TicketPanel
from src.features.twitch.twitch_monitor import get_twitch_monitor
from src.features.twitch.view.TwitchPanel import TwitchPanel
from src.languages.localize import setup_i18n
from src.utils.bot_instance import set_bot
from src.utils.load_extensions import load_extensions
from src.utils.logger import get_cool_logger
from src.utils.register_persistent_application_views import (
    register_persistent_application_views,
)
from src.utils.register_persistent_event_views import register_persistent_event_views
from src.utils.register_persistent_ticket_views import register_persistent_ticket_views
from src.utils.scheduler import scheduler
from src.views.language_selector import LanguageSelector

logger = get_cool_logger(__name__)

bot = Bot(intents=discord.Intents.all(), prefix=bot_config.bot.prefix)
set_bot(bot)
i18n, _ = setup_i18n(bot)
_guild_commands_synced = False


@bot.event
async def on_ready():
    global _guild_commands_synced

    logger.info(f"{bot.user} is ready and online!")
    if not _guild_commands_synced:
        guild_ids = [guild.id for guild in bot.guilds]
        if guild_ids:
            try:
                await bot.sync_commands(guild_ids=guild_ids, force=True)
                _guild_commands_synced = True
                logger.info(f"Synced slash commands for guilds: {guild_ids}")
            except Exception as e:
                logger.error(f"Failed to sync guild slash commands: {e}")

    bot.add_view(LanguageSelector())
    bot.add_view(ApplicationPanel())
    bot.add_view(TicketPanel())
    bot.add_view(TwitchPanel())

    if not scheduler.running:
        scheduler.start()

    # Register persistent ticket views for existing tickets so components work after restarts
    await register_persistent_ticket_views(bot)
    await register_persistent_application_views(bot)
    await register_persistent_event_views(bot)
    await cleanup_old_applications()

    # Restore temp voice channels and their control panels
    try:
        await restore_temp_channels(bot)
        logger.info(f"{lang_constants.SUCCESS_EMOJI} Temp voice channels restored")
    except Exception as e:
        logger.error(
            f"{lang_constants.ERROR_EMOJI} Temp voice channels restoration failed: {e}"
        )

    # Start Twitch live monitor
    try:
        twitch_monitor = get_twitch_monitor(bot)
        await twitch_monitor.start()
        logger.info(f"{lang_constants.SUCCESS_EMOJI} Twitch monitor started")
    except Exception as e:
        logger.error(
            f"{lang_constants.ERROR_EMOJI} Twitch monitor initialization failed: {e}"
        )

    # Start dynamic Discord presence monitor
    try:
        status_monitor = get_status_monitor(bot)
        await status_monitor.start()
    except Exception as e:
        logger.error(
            f"{lang_constants.ERROR_EMOJI} Status monitor initialization failed: {e}"
        )


load_extensions(bot)

# Localize all registered commands (names/descriptions/options)
i18n.localize_commands()

# Initialize and start health API server if enabled
if bot_config.health.enabled:
    health_api = HealthAPI(bot, port=bot_config.health.port)
    health_api.start()


if __name__ == "__main__":
    bot.run(bot_config.bot.token)
