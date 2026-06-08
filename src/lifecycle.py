from __future__ import annotations

import asyncio

from src.features.applications.service import cleanup_old_applications
from src.features.applications.view.ApplicationPanel import ApplicationPanel
from src.features.status.status_monitor import get_status_monitor
from src.features.temp_voice_channels.restore_temp_channels import restore_temp_channels
from src.features.tickets.view.TicketPanel import TicketPanel
from src.features.twitch.twitch_monitor import get_twitch_monitor
from src.features.twitch.view.TwitchPanel import TwitchPanel
from src.utils.logger import get_cool_logger
from src.utils.register_persistent_application_views import (
    register_persistent_application_views,
)
from src.utils.register_persistent_event_views import register_persistent_event_views
from src.utils.register_persistent_ticket_views import register_persistent_ticket_views
from src.utils.scheduler import scheduler
from src.views.language_selector import LanguageSelector

logger = get_cool_logger(__name__)


def _get_startup_lock(bot) -> asyncio.Lock:
    lock = getattr(bot, "_bebraland_startup_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        setattr(bot, "_bebraland_startup_lock", lock)
    return lock


async def bootstrap_bot(bot) -> None:
    """Run one-time startup tasks once per process."""
    lock = _get_startup_lock(bot)
    async with lock:
        if getattr(bot, "_bebraland_startup_complete", False):
            logger.debug("Bot startup already completed; skipping")
            return

        bot.add_view(LanguageSelector())
        bot.add_view(ApplicationPanel())
        bot.add_view(TicketPanel())
        bot.add_view(TwitchPanel())

        if not scheduler.running:
            scheduler.start()

        await register_persistent_ticket_views(bot)
        await register_persistent_application_views(bot)
        await register_persistent_event_views(bot)
        await cleanup_old_applications()

        try:
            await restore_temp_channels(bot)
            logger.info("Temp voice channels restored")
        except Exception as error:
            logger.error(f"Temp voice channels restoration failed: {error}")

        try:
            twitch_monitor = get_twitch_monitor(bot)
            await twitch_monitor.start()
            logger.info("Twitch monitor started")
        except Exception as error:
            logger.error(f"Twitch monitor initialization failed: {error}")

        try:
            status_monitor = get_status_monitor(bot)
            await status_monitor.start()
        except Exception as error:
            logger.error(f"Status monitor initialization failed: {error}")

        setattr(bot, "_bebraland_startup_complete", True)
