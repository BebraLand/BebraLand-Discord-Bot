from datetime import datetime, timezone

import discord

from config.config import config as bot_config
from src.features.applications.config import get_application_config_value
from src.features.applications.service import (
    apply_application_roles,
    get_guild_member,
    notify_application_decision,
)
from src.utils.database import get_db
from src.utils.logger import get_cool_logger
from src.utils.schedule_utils import parse_and_validate_schedule
from src.utils.scheduler import scheduler
from src.utils.send.send_application_panel_message import send_application_panel_message

logger = get_cool_logger(__name__)


async def send_admin_reply(
    ctx: discord.ApplicationContext,
    content: str | None = None,
    *,
    embed: discord.Embed | None = None,
) -> None:
    await ctx.followup.send(
        content,
        embed=embed,
        ephemeral=True,
        delete_after=bot_config.messages.action_confirmation_delete_delay,
    )


async def send_application_panel(
    ctx: discord.ApplicationContext,
    *,
    schedule_time: str | None,
    selected_channel: discord.TextChannel | None,
) -> None:
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

        await send_admin_reply(
            ctx,
            "Application panel scheduled for "
            f"<t:{int(schedule_unix)}:F> (<t:{int(schedule_unix)}:R>).",
        )
        logger.info(f"Admin {ctx.user.id} scheduled application panel to {channel_id}")
        return

    await send_application_panel_message(channel_id)
    await send_admin_reply(ctx, "Application panel sent.")
    logger.info(f"Admin {ctx.user.id} sent application panel to {channel_id}")


async def set_applications_enabled(
    ctx: discord.ApplicationContext,
    *,
    enabled: bool,
) -> None:
    db = await get_db()
    await db.set_application_enabled(ctx.guild.id, enabled)
    state_text = "open" if enabled else "closed"
    await send_admin_reply(ctx, f"Applications are now {state_text}.")
    logger.info(
        f"Admin {ctx.user.id} {'enabled' if enabled else 'disabled'} "
        f"applications in {ctx.guild.id}"
    )


async def send_applications_status(ctx: discord.ApplicationContext) -> None:
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


async def revoke_application_status(
    ctx: discord.ApplicationContext,
    *,
    user: discord.Member,
    reason: str | None,
) -> None:
    if user.bot:
        await send_admin_reply(ctx, "Cannot revoke application status for bots.")
        logger.info(f"Admin {ctx.user.id} tried to revoke bot user {user.id}; ignored")
        return

    db = await get_db()
    target_application = await _find_revocation_target(db, str(user.id), ctx.guild.id)
    db_updated = False
    if target_application:
        db_updated = await db.update_application_status(
            target_application["id"],
            "revoked",
            str(ctx.user.id),
            reason,
        )

    member = await get_guild_member(ctx.guild, user.id)
    if member:
        role_ok, role_error = await apply_application_roles(member, "revoked")
    else:
        role_ok = False
        role_error = "Could not find the user as a server member."
    await notify_application_decision(user, "revoked", reason)

    embed = discord.Embed(
        title="Application Status Revoked",
        description=_build_revocation_description(
            user,
            target_application,
            db_updated=db_updated,
            role_ok=role_ok,
            role_error=role_error,
        ),
        color=bot_config.embeds.info_color,
    )
    await send_admin_reply(ctx, embed=embed)
    _log_revocation(ctx, user, target_application, db_updated)


async def _find_revocation_target(db, user_id: str, guild_id: int) -> dict | None:
    accepted = await db.get_application_by_user_status(user_id, guild_id, "accepted")
    pending = await db.get_application_by_user_status(user_id, guild_id, "pending")
    return accepted or pending


def _build_revocation_description(
    user: discord.Member,
    target_application: dict | None,
    *,
    db_updated: bool,
    role_ok: bool,
    role_error: str,
) -> str:
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
    return description


def _log_revocation(
    ctx: discord.ApplicationContext,
    user: discord.Member,
    target_application: dict | None,
    db_updated: bool,
) -> None:
    if target_application:
        logger.info(
            f"Admin {ctx.user.id} revoked application #{target_application['id']} "
            f"({target_application['status']}) for {user.id}; db_updated={db_updated}"
        )
        return
    logger.info(
        f"Admin {ctx.user.id} reset roles for {user.id}; "
        "no accepted/pending application found"
    )
