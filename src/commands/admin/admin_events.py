import discord
from discord import Option
from discord.ext import commands
from pycord.multicog import subcommand

from src.features.events.admin_service import (
    add_event_users,
    cancel_event,
    close_event,
    create_event,
    edit_event,
    list_events,
    remove_event_user,
)
from src.utils.auth import require_admin


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
        player_limit=Option(
            int,
            description="Main player limit; 0 means unlimited",
            min_value=0,
            required=True,
        ),
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
        reminder_minutes=Option(
            str,
            description="Optional DM reminders, comma-separated minutes: 60,10,0",
            required=False,
        ),
        check_in=Option(
            bool,
            description="Enable Check in button",
            required=False,
        ),
        check_in_opens_minutes=Option(
            int,
            description="Minutes before event when check-in opens",
            required=False,
            default=60,
        ),
        discord_location_type=Option(
            str,
            description="Native Discord event location",
            choices=["external", "voice", "stage"],
            required=False,
        ),
        voice_channel=Option(
            discord.VoiceChannel,
            description="Voice channel for native Discord event",
            required=False,
        ),
        stage_channel=Option(
            discord.StageChannel,
            description="Stage channel for native Discord event",
            required=False,
        ),
        external_location=Option(
            str,
            description="External/native event location text",
            required=False,
        ),
        cover_image=Option(
            discord.Attachment,
            description="Cover image for native Discord event",
            required=False,
        ),
    ):
        await ctx.defer(ephemeral=True)
        if not await require_admin(ctx):
            return

        await create_event(
            ctx,
            title=title,
            description=description,
            player_limit=player_limit,
            starts_at=starts_at,
            languages=languages,
            selected_channel=selected_channel,
            users=users,
            schedule_time=schedule_time,
            reminder_minutes=reminder_minutes,
            check_in=check_in,
            check_in_opens_minutes=check_in_opens_minutes,
            discord_location_type=discord_location_type,
            voice_channel=voice_channel,
            stage_channel=stage_channel,
            external_location=external_location,
            cover_image=cover_image,
        )

    @subcommand("admin")
    @discord.slash_command(
        name="event_edit",
        description="Edit an event registration panel",
    )
    async def event_edit(
        self,
        ctx: discord.ApplicationContext,
        event_id=Option(int, description="Event ID", required=True),
        title=Option(str, description="New event title", required=False),
        description=Option(str, description="New event description", required=False),
        starts_at=Option(
            str,
            description="New event time: 19:00, today 19:00, in 2h, or Unix",
            required=False,
        ),
        player_limit=Option(
            int,
            description="New main player limit; 0 means unlimited",
            min_value=0,
            required=False,
        ),
        languages=Option(
            str,
            description="New comma-separated languages: en,ru,lt",
            required=False,
        ),
        reminder_minutes=Option(
            str,
            description="Replace DM reminders: 60,10,0 or none",
            required=False,
        ),
        check_in=Option(
            bool,
            description="Enable or disable Check in button",
            required=False,
        ),
        check_in_opens_minutes=Option(
            int,
            description="Minutes before event when check-in opens",
            required=False,
        ),
        discord_location_type=Option(
            str,
            description="Update native Discord event location",
            choices=["external", "voice", "stage"],
            required=False,
        ),
        voice_channel=Option(
            discord.VoiceChannel,
            description="New native Discord voice channel",
            required=False,
        ),
        stage_channel=Option(
            discord.StageChannel,
            description="New native Discord stage channel",
            required=False,
        ),
        external_location=Option(
            str,
            description="New native Discord external location text",
            required=False,
        ),
        cover_image=Option(
            discord.Attachment,
            description="New cover image for native Discord event",
            required=False,
        ),
    ):
        await ctx.defer(ephemeral=True)
        if not await require_admin(ctx):
            return

        await edit_event(
            self.bot,
            ctx,
            event_id=event_id,
            title=title,
            description=description,
            player_limit=player_limit,
            starts_at=starts_at,
            languages=languages,
            reminder_minutes=reminder_minutes,
            check_in=check_in,
            check_in_opens_minutes=check_in_opens_minutes,
            discord_location_type=discord_location_type,
            voice_channel=voice_channel,
            stage_channel=stage_channel,
            external_location=external_location,
            cover_image=cover_image,
        )

    @subcommand("admin")
    @discord.slash_command(
        name="event_list",
        description="List server events",
    )
    async def event_list(
        self,
        ctx: discord.ApplicationContext,
        status=Option(
            str,
            description="Filter events",
            choices=["active", "all", "open", "started", "closed", "cancelled"],
            required=False,
            default="active",
        ),
        limit=Option(
            int,
            description="How many events to show",
            min_value=1,
            max_value=25,
            required=False,
            default=10,
        ),
    ):
        await ctx.defer(ephemeral=True)
        if not await require_admin(ctx):
            return

        await list_events(ctx, status=status, limit=limit)

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

        await add_event_users(self.bot, ctx, event_id=event_id, users=users)

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

        await remove_event_user(self.bot, ctx, event_id=event_id, user=user)

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

        await close_event(self.bot, ctx, event_id=event_id)

    @subcommand("admin")
    @discord.slash_command(
        name="event_cancel",
        description="Cancel an event and notify registered users",
    )
    async def event_cancel(
        self,
        ctx: discord.ApplicationContext,
        event_id=Option(int, description="Event ID", required=True),
        reason=Option(str, description="Optional cancellation reason", required=False),
        notify_users=Option(
            bool,
            description="DM registered users",
            required=False,
            default=True,
        ),
    ):
        await ctx.defer(ephemeral=True)
        if not await require_admin(ctx):
            return

        await cancel_event(
            self.bot,
            ctx,
            event_id=event_id,
            reason=reason,
            notify_users=notify_users,
        )


def setup(bot: commands.Bot):
    bot.add_cog(EventsAdmin(bot))
