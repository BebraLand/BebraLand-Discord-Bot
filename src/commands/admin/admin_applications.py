import discord
from discord import Option
from discord.ext import commands
from pycord.multicog import subcommand

from src.features.applications.admin_service import (
    revoke_application_status,
    send_application_panel,
    send_applications_status,
    set_applications_enabled,
)
from src.utils.auth import require_admin


class ApplicationsAdmin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @subcommand("admin")
    @discord.slash_command(
        name="send_application_panel",
        description="Send the application panel to a channel",
    )
    async def send_application_panel(
        self,
        ctx: discord.ApplicationContext,
        schedule_time=Option(
            str,
            description="Schedule time as Unix UTC timestamp",
            required=False,
        ),
        selected_channel=Option(
            discord.TextChannel,
            description="Channel to send the application panel to",
            required=False,
        ),
    ):
        await ctx.defer(ephemeral=True)
        if not await require_admin(ctx):
            return

        await send_application_panel(
            ctx,
            schedule_time=schedule_time,
            selected_channel=selected_channel,
        )

    @subcommand("admin")
    @discord.slash_command(
        name="applications_enable",
        description="Open applications for this server",
    )
    async def applications_enable(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        if not await require_admin(ctx):
            return

        await set_applications_enabled(ctx, enabled=True)

    @subcommand("admin")
    @discord.slash_command(
        name="applications_disable",
        description="Close applications for this server",
    )
    async def applications_disable(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        if not await require_admin(ctx):
            return

        await set_applications_enabled(ctx, enabled=False)

    @subcommand("admin")
    @discord.slash_command(
        name="applications_status",
        description="Show application system status",
    )
    async def applications_status(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        if not await require_admin(ctx):
            return

        await send_applications_status(ctx)

    @subcommand("admin")
    @discord.slash_command(
        name="application_revoke",
        description="Remove a user's accepted application status",
    )
    async def application_revoke(
        self,
        ctx: discord.ApplicationContext,
        user=Option(
            discord.Member,
            description="User whose application status should be removed",
            required=True,
        ),
        reason=Option(
            str,
            description="Reason shown in the database and DM",
            required=False,
        ),
    ):
        await ctx.defer(ephemeral=True)
        if not await require_admin(ctx):
            return
        await revoke_application_status(ctx, user=user, reason=reason)


def setup(bot: commands.Bot):
    bot.add_cog(ApplicationsAdmin(bot))
