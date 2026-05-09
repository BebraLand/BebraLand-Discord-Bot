from datetime import datetime, timezone

import discord
from discord import Option
from discord.ext import commands
from pycord.multicog import subcommand

from config.config import config as bot_config
from src.features.applications.config import get_application_config_value
from src.features.applications.service import (
    apply_application_roles,
    get_guild_member,
    notify_application_decision,
)
from src.utils.auth import require_admin
from src.utils.database import get_db
from src.utils.logger import get_cool_logger
from src.utils.schedule_utils import parse_and_validate_schedule
from src.utils.scheduler import scheduler
from src.utils.send.send_application_panel_message import send_application_panel_message

logger = get_cool_logger(__name__)


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

        channel_id = selected_channel.id if selected_channel else ctx.channel.id
        if schedule_time:
            schedule_unix = await parse_and_validate_schedule(ctx, schedule_time)
            if not schedule_unix:
                return

            scheduler.add_job(
                send_application_panel_message,
                trigger="date",
                run_date=datetime.fromtimestamp(schedule_unix, tz=timezone.utc),
                args=[channel_id],
                misfire_grace_time=3600,
            )

            await ctx.followup.send(
                f"Application panel scheduled for <t:{int(schedule_unix)}:F> (<t:{int(schedule_unix)}:R>).",
                ephemeral=True,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
            logger.info(
                f"Admin {ctx.user.id} scheduled application panel to {channel_id}"
            )
            return

        await send_application_panel_message(channel_id)
        await ctx.followup.send(
            "Application panel sent.",
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )
        logger.info(f"Admin {ctx.user.id} sent application panel to {channel_id}")

    @subcommand("admin")
    @discord.slash_command(
        name="applications_enable",
        description="Open applications for this server",
    )
    async def applications_enable(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        if not await require_admin(ctx):
            return

        db = await get_db()
        await db.set_application_enabled(ctx.guild.id, True)
        await ctx.followup.send(
            "Applications are now open.",
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )
        logger.info(f"Admin {ctx.user.id} enabled applications in {ctx.guild.id}")

    @subcommand("admin")
    @discord.slash_command(
        name="applications_disable",
        description="Close applications for this server",
    )
    async def applications_disable(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        if not await require_admin(ctx):
            return

        db = await get_db()
        await db.set_application_enabled(ctx.guild.id, False)
        await ctx.followup.send(
            "Applications are now closed.",
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )
        logger.info(f"Admin {ctx.user.id} disabled applications in {ctx.guild.id}")

    @subcommand("admin")
    @discord.slash_command(
        name="applications_status",
        description="Show application system status",
    )
    async def applications_status(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        if not await require_admin(ctx):
            return

        db = await get_db()
        enabled = await db.get_application_enabled(ctx.guild.id)
        review_channel_id = get_application_config_value("review_channel_id")
        reviewer_role_id = get_application_config_value("reviewer_role_id")

        embed = discord.Embed(
            title="Application Status",
            color=(
                bot_config.embeds.success_color
                if enabled
                else bot_config.embeds.failed_color
            ),
        )
        embed.add_field(
            name="State",
            value="Open" if enabled else "Closed",
            inline=False,
        )
        embed.add_field(
            name="Review Channel",
            value=f"<#{review_channel_id}>" if review_channel_id else "Not configured",
            inline=True,
        )
        embed.add_field(
            name="Reviewer Role",
            value=f"<@&{reviewer_role_id}>" if reviewer_role_id else "Admin list only",
            inline=True,
        )
        await ctx.followup.send(embed=embed, ephemeral=True)

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
        if user.bot:
            await ctx.followup.send(
                "Cannot revoke application status for bots.",
                ephemeral=True,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )
            logger.info(
                f"Admin {ctx.user.id} tried to revoke bot user {user.id}; ignored"
            )
            return

        db = await get_db()
        accepted = await db.get_application_by_user_status(
            str(user.id), ctx.guild.id, "accepted"
        )
        pending = await db.get_application_by_user_status(
            str(user.id), ctx.guild.id, "pending"
        )
        target_application = accepted or pending

        db_updated = False
        if target_application:
            db_updated = await db.update_application_status(
                target_application["id"], "revoked", str(ctx.user.id), reason
            )

        member = await get_guild_member(ctx.guild, user.id)
        if member:
            role_ok, role_error = await apply_application_roles(member, "revoked")
        else:
            role_ok = False
            role_error = "Could not find the user as a server member."
        await notify_application_decision(user, "revoked", reason)

        description = f"Application status removed for {user.mention}."
        if target_application:
            description += (
                f"\nApplication #{target_application['id']} changed from "
                f"`{target_application['status']}` to `revoked`."
            )
        if target_application and not db_updated:
            description += "\nDatabase status was not changed."
        if not target_application:
            description += "\nNo application record was found; roles were reset only."
        if not role_ok:
            description += f"\nRole update warning: {role_error}"

        embed = discord.Embed(
            title="Application Status Revoked",
            description=description,
            color=bot_config.embeds.info_color,
        )
        await ctx.followup.send(
            embed=embed,
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )
        if target_application:
            logger.info(
                f"Admin {ctx.user.id} revoked application #{target_application['id']} "
                f"({target_application['status']}) for {user.id}; db_updated={db_updated}"
            )
        else:
            logger.info(
                f"Admin {ctx.user.id} reset roles for {user.id}; no accepted/pending application found"
            )


def setup(bot: commands.Bot):
    bot.add_cog(ApplicationsAdmin(bot))
