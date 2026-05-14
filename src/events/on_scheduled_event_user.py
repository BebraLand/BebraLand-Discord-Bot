import discord
from discord.ext import commands

from src.features.events.discord_scheduled import discord_event_user_sync_enabled
from src.features.events.service import refresh_event_message
from src.utils.database import get_db
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


class OnScheduledEventUser(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_scheduled_event_user_add(
        self,
        payload: discord.RawScheduledEventSubscription,
    ) -> None:
        if not discord_event_user_sync_enabled():
            return

        db = await get_db()
        event = await db.get_event_by_discord_event_id(payload.event_id)
        if not event or event.get("status") != "open":
            return

        result = await db.register_event_user(
            event["id"],
            str(payload.user_id),
            added_by_id="discord_scheduled_event",
        )
        if result in {"main", "backup"}:
            await refresh_event_message(self.bot, event["id"])
            logger.info(
                f"Synced Discord scheduled event signup user={payload.user_id} "
                f"event={event['id']} status={result}"
            )

    @commands.Cog.listener()
    async def on_raw_scheduled_event_user_remove(
        self,
        payload: discord.RawScheduledEventSubscription,
    ) -> None:
        if not discord_event_user_sync_enabled():
            return

        db = await get_db()
        event = await db.get_event_by_discord_event_id(payload.event_id)
        if not event or event.get("status") != "open":
            return

        result = await db.unregister_event_user(event["id"], str(payload.user_id))
        if result:
            await refresh_event_message(self.bot, event["id"])
            logger.info(
                f"Synced Discord scheduled event removal user={payload.user_id} "
                f"event={event['id']} result={result}"
            )


def setup(bot: commands.Bot):
    bot.add_cog(OnScheduledEventUser(bot))
