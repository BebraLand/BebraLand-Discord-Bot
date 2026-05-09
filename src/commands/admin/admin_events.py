import re
from datetime import datetime, timezone

import discord
from discord import Option
from discord.ext import commands
from pycord.multicog import subcommand

from config.config import config as bot_config
from src.features.events.service import (
    normalize_event_languages,
    refresh_event_message,
    send_event_panel,
)
from src.utils.auth import require_admin
from src.utils.database import get_db
from src.utils.logger import get_cool_logger
from src.utils.schedule_utils import parse_and_validate_schedule
from src.utils.scheduler import scheduler

logger = get_cool_logger(__name__)


def parse_user_ids(raw_users: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\d{15,25}", raw_users)))


class EventsAdmin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @subcommand("admin")
    @discord.slash_command(
        name="event_create",
        description="Create and post an event registration panel",
    )
    async def event_create(
        self,
        ctx: discord.ApplicationContext,
        title=Option(str, description="Event title", required=True),
        description=Option(str, description="Event description", required=True),
        starts_at=Option(
            str,
            description="Event time: today 19:00, tomorrow 16:00, in 2h, or Unix",
            required=True,
        ),
        player_limit=Option(int, description="Main player limit", required=True),
        languages=Option(
            str,
            description="Comma-separated languages: en,ru,lt",
            required=True,
        ),
        selected_channel=Option(
            discord.TextChannel,
            description="Channel to post the event in",
            required=False,
        ),
        users=Option(
            str,
            description="Optional mentions or user IDs to register instantly",
            required=False,
        ),
        schedule_time=Option(
            str,
            description="Schedule panel message: today 12:00, in 30m, or Unix",
            required=False,
        ),
    ):
        await ctx.defer(ephemeral=True)
        if not await require_admin(ctx):
            return

        schedule_unix = await parse_and_validate_schedule(ctx, starts_at)
        if not schedule_unix:
            return

        message_schedule_unix = None
        if schedule_time:
            message_schedule_unix = await parse_and_validate_schedule(
                ctx, schedule_time
            )
            if not message_schedule_unix:
                return

        if player_limit < 1:
            await ctx.followup.send(
                "Player limit must be at least 1.",
                ephemeral=True,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
            return

        event_languages = normalize_event_languages(languages)
        if not event_languages:
            await ctx.followup.send(
                "Choose at least one language: en, ru, lt.",
                ephemeral=True,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
            return

        db = await get_db()
        event_id = await db.create_event(
            guild_id=ctx.guild.id,
            title=title,
            description=description,
            starts_at=float(schedule_unix),
            languages=event_languages,
            player_limit=player_limit,
            created_by_id=str(ctx.user.id),
        )
        if event_id is None:
            await ctx.followup.send(
                "Could not create event.",
                ephemeral=True,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
            return

        added_main = 0
        added_backup = 0
        skipped = 0
        if users:
            for user_id in parse_user_ids(users):
                result = await db.register_event_user(
                    event_id,
                    user_id,
                    added_by_id=str(ctx.user.id),
                )
                if result == "main":
                    added_main += 1
                elif result == "backup":
                    added_backup += 1
                else:
                    skipped += 1

        channel = selected_channel or ctx.channel
        if message_schedule_unix:
            scheduler.add_job(
                send_event_panel,
                trigger="date",
                run_date=datetime.fromtimestamp(
                    message_schedule_unix,
                    tz=timezone.utc,
                ),
                args=[channel.id, event_id],
                misfire_grace_time=3600,
            )
            posted_text = (
                f"Event #{event_id} created. Panel scheduled for "
                f"<t:{int(message_schedule_unix)}:F> (<t:{int(message_schedule_unix)}:R>) "
                f"in {channel.mention}."
            )
        else:
            await send_event_panel(channel.id, event_id)
            posted_text = f"Event #{event_id} posted in {channel.mention}."

        user_text = ""
        if users:
            user_text = (
                f"\nRegistered users: main {added_main}, backup {added_backup}, "
                f"skipped {skipped}."
            )

        await ctx.followup.send(
            posted_text + user_text,
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )
        logger.info(
            f"Admin {ctx.user.id} created event #{event_id} for {ctx.guild.id}"
        )

    @subcommand("admin")
    @discord.slash_command(
        name="event_add_users",
        description="Instantly register users for an event",
    )
    async def event_add_users(
        self,
        ctx: discord.ApplicationContext,
        event_id=Option(int, description="Event ID", required=True),
        users=Option(
            str,
            description="Mentions or user IDs separated by spaces",
            required=True,
        ),
    ):
        await ctx.defer(ephemeral=True)
        if not await require_admin(ctx):
            return

        user_ids = parse_user_ids(users)
        if not user_ids:
            await ctx.followup.send(
                "No users found. Mention users or paste user IDs.",
                ephemeral=True,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
            return

        db = await get_db()
        event = await db.get_event(event_id)
        if not event:
            await ctx.followup.send(
                f"Event #{event_id} not found.",
                ephemeral=True,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
            return

        added_main = []
        added_backup = []
        skipped = []
        for user_id in user_ids:
            result = await db.register_event_user(
                event_id,
                user_id,
                added_by_id=str(ctx.user.id),
            )
            if result == "main":
                added_main.append(user_id)
            elif result == "backup":
                added_backup.append(user_id)
            else:
                skipped.append(user_id)

        await refresh_event_message(self.bot, event_id)
        parts = [
            f"Main: {len(added_main)}",
            f"Backup: {len(added_backup)}",
            f"Skipped: {len(skipped)}",
        ]
        await ctx.followup.send(
            f"Event #{event_id} updated. " + " | ".join(parts),
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )

    @subcommand("admin")
    @discord.slash_command(
        name="event_remove_user",
        description="Remove a user from an event",
    )
    async def event_remove_user(
        self,
        ctx: discord.ApplicationContext,
        event_id=Option(int, description="Event ID", required=True),
        user=Option(discord.Member, description="User to remove", required=True),
    ):
        await ctx.defer(ephemeral=True)
        if not await require_admin(ctx):
            return

        db = await get_db()
        result = await db.remove_event_user(event_id, str(user.id))
        if result is None:
            await ctx.followup.send(
                f"{user.mention} is not registered for event #{event_id}.",
                ephemeral=True,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
            return

        await refresh_event_message(self.bot, event_id)
        promoted = f" Promoted <@{result}>." if result.isdigit() else ""
        await ctx.followup.send(
            f"Removed {user.mention} from event #{event_id}.{promoted}",
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )

    @subcommand("admin")
    @discord.slash_command(
        name="event_close",
        description="Close event registration",
    )
    async def event_close(
        self,
        ctx: discord.ApplicationContext,
        event_id=Option(int, description="Event ID", required=True),
    ):
        await ctx.defer(ephemeral=True)
        if not await require_admin(ctx):
            return

        db = await get_db()
        if not await db.set_event_status(event_id, "closed"):
            await ctx.followup.send(
                f"Event #{event_id} not found.",
                ephemeral=True,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
            return

        await refresh_event_message(self.bot, event_id)
        await ctx.followup.send(
            f"Event #{event_id} closed at {datetime.now(timezone.utc).isoformat()}.",
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )


def setup(bot: commands.Bot):
    bot.add_cog(EventsAdmin(bot))
