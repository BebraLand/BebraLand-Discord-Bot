import re
from datetime import datetime, timezone

import discord

from config.config import config as bot_config
from src.features.events.discord_scheduled import (
    cancel_discord_scheduled_event,
    create_discord_scheduled_event,
    discord_scheduled_events_enabled,
    resolve_discord_event_location,
    update_discord_scheduled_event,
)
from src.features.events.service import (
    cancel_event_jobs,
    normalize_event_languages,
    notify_event_cancelled,
    parse_event_reminders,
    refresh_event_message,
    schedule_event_check_in_open,
    schedule_event_reminders,
    schedule_event_start_notification,
    send_event_panel,
)
from src.utils.database import get_db
from src.utils.logger import get_cool_logger
from src.utils.schedule_utils import parse_and_validate_schedule
from src.utils.scheduler import scheduler

logger = get_cool_logger(__name__)


def parse_user_ids(raw_users: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\d{15,25}", raw_users)))


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


async def create_event(
    ctx: discord.ApplicationContext,
    *,
    title: str,
    description: str,
    starts_at: str,
    player_limit: int,
    languages: str,
    selected_channel: discord.TextChannel | None,
    users: str | None,
    schedule_time: str | None,
    reminder_minutes: str | None,
    check_in: bool | None,
    check_in_opens_minutes: int,
    discord_location_type: str | None,
    voice_channel: discord.VoiceChannel | None,
    stage_channel: discord.StageChannel | None,
    external_location: str | None,
    cover_image: discord.Attachment | None,
) -> None:
    schedule_unix = await parse_and_validate_schedule(ctx, starts_at)
    if not schedule_unix:
        return

    message_schedule_unix = None
    if schedule_time:
        message_schedule_unix = await parse_and_validate_schedule(ctx, schedule_time)
        if not message_schedule_unix:
            return

    validation_error = _event_input_error(
        player_limit=player_limit,
        languages=languages,
        check_in_opens_minutes=check_in_opens_minutes,
    )
    if validation_error:
        await send_admin_reply(ctx, validation_error)
        return
    if discord_scheduled_events_enabled():
        try:
            resolve_discord_event_location(
                discord_location_type,
                voice_channel=voice_channel,
                stage_channel=stage_channel,
                external_location=external_location,
            )
        except ValueError as error:
            await send_admin_reply(ctx, str(error))
            return

    event_languages = normalize_event_languages(languages)
    db = await get_db()
    event_id = await db.create_event(
        guild_id=ctx.guild.id,
        title=title,
        description=description,
        starts_at=float(schedule_unix),
        languages=event_languages,
        player_limit=player_limit,
        created_by_id=str(ctx.user.id),
        reminder_minutes=parse_event_reminders(reminder_minutes),
        check_in_enabled=bool(check_in),
        check_in_opens_minutes=check_in_opens_minutes,
        cover_image_url=cover_image.url if cover_image else None,
    )
    if event_id is None:
        await send_admin_reply(ctx, "Could not create event.")
        return

    added_main, added_backup, skipped = await _register_initial_users(
        db,
        event_id,
        users,
        added_by_id=str(ctx.user.id),
    )
    discord_text = ""
    event = await db.get_event(event_id)
    if event:
        try:
            discord_event = await create_discord_scheduled_event(
                ctx.guild,
                event,
                location_type=discord_location_type,
                voice_channel=voice_channel,
                stage_channel=stage_channel,
                external_location=external_location,
                cover_image=cover_image,
            )
        except ValueError as error:
            discord_event = None
            discord_text = f"\nDiscord scheduled event skipped: {error}"
        if discord_event:
            discord_text = f"\nDiscord event: {discord_event.url}"
        elif discord_scheduled_events_enabled() and not discord_text:
            discord_text = "\nDiscord scheduled event was not created."

    channel = selected_channel or ctx.channel
    posted_text = await _post_or_schedule_event_panel(
        channel,
        event_id,
        message_schedule_unix,
    )

    event = await db.get_event(event_id)
    if event:
        schedule_event_reminders(event)
        schedule_event_check_in_open(event)
        schedule_event_start_notification(event)

    user_text = ""
    if users:
        user_text = (
            f"\nRegistered users: main {added_main}, backup {added_backup}, "
            f"skipped {skipped}."
        )
    await send_admin_reply(ctx, posted_text + discord_text + user_text)
    logger.info(f"Admin {ctx.user.id} created event #{event_id} for {ctx.guild.id}")


async def edit_event(
    bot: discord.Client,
    ctx: discord.ApplicationContext,
    *,
    event_id: int,
    title: str | None,
    description: str | None,
    starts_at: str | None,
    player_limit: int | None,
    languages: str | None,
    reminder_minutes: str | None,
    check_in: bool | None,
    check_in_opens_minutes: int | None,
    discord_location_type: str | None,
    voice_channel: discord.VoiceChannel | None,
    stage_channel: discord.StageChannel | None,
    external_location: str | None,
    cover_image: discord.Attachment | None,
) -> None:
    db = await get_db()
    event = await db.get_event(event_id)
    if not event:
        await send_admin_reply(ctx, f"Event #{event_id} not found.")
        return

    starts_at_unix = None
    if starts_at:
        starts_at_unix = await parse_and_validate_schedule(ctx, starts_at)
        if not starts_at_unix:
            return

    event_languages = None
    if languages:
        event_languages = normalize_event_languages(languages)
        if not event_languages:
            await send_admin_reply(ctx, "Choose at least one language: en, ru, lt.")
            return

    validation_error = _event_update_error(
        player_limit=player_limit,
        check_in_opens_minutes=check_in_opens_minutes,
    )
    if validation_error:
        await send_admin_reply(ctx, validation_error)
        return
    if discord_scheduled_events_enabled() and any(
        [discord_location_type, voice_channel, stage_channel, external_location]
    ):
        try:
            resolve_discord_event_location(
                discord_location_type,
                voice_channel=voice_channel,
                stage_channel=stage_channel,
                external_location=external_location,
                default_to_external=False,
            )
        except ValueError as error:
            await send_admin_reply(ctx, str(error))
            return

    discord_only_update = any(
        [
            discord_location_type,
            voice_channel,
            stage_channel,
            external_location,
            cover_image,
        ]
    )
    updated = await db.update_event(
        event_id,
        title=title,
        description=description,
        starts_at=float(starts_at_unix) if starts_at_unix else None,
        languages=event_languages,
        player_limit=player_limit,
        reminder_minutes=(
            parse_event_reminders(reminder_minutes)
            if reminder_minutes is not None
            else None
        ),
        check_in_enabled=check_in,
        check_in_opens_minutes=check_in_opens_minutes,
        cover_image_url=cover_image.url if cover_image else None,
    )
    if not updated and not discord_only_update:
        await send_admin_reply(ctx, f"Event #{event_id} has no changes.")
        return

    event = await db.get_event(event_id)
    discord_synced = False
    if event:
        schedule_event_reminders(event)
        schedule_event_check_in_open(event)
        schedule_event_start_notification(event)
        try:
            discord_synced = await update_discord_scheduled_event(
                ctx.guild,
                event,
                location_type=discord_location_type,
                voice_channel=voice_channel,
                stage_channel=stage_channel,
                external_location=external_location,
                cover_image=cover_image,
            )
        except ValueError as error:
            await send_admin_reply(
                ctx,
                f"Event #{event_id} updated. Discord scheduled event skipped: {error}",
            )
            await refresh_event_message(bot, event_id)
            return
    await refresh_event_message(bot, event_id)
    if discord_only_update and not updated:
        message = (
            f"Event #{event_id} Discord event synced."
            if discord_synced
            else f"Event #{event_id} has no local changes."
        )
    else:
        sync_text = " Discord event synced." if discord_synced else ""
        message = f"Event #{event_id} updated.{sync_text}"
    await send_admin_reply(ctx, message)


async def add_event_users(
    bot: discord.Client,
    ctx: discord.ApplicationContext,
    *,
    event_id: int,
    users: str,
) -> None:
    user_ids = parse_user_ids(users)
    if not user_ids:
        await send_admin_reply(ctx, "No users found. Mention users or paste user IDs.")
        return

    db = await get_db()
    event = await db.get_event(event_id)
    if not event:
        await send_admin_reply(ctx, f"Event #{event_id} not found.")
        return

    added_main, added_backup, skipped = await _register_users(
        db,
        event_id,
        user_ids,
        added_by_id=str(ctx.user.id),
    )
    await refresh_event_message(bot, event_id)
    parts = [
        f"Main: {len(added_main)}",
        f"Backup: {len(added_backup)}",
        f"Skipped: {len(skipped)}",
    ]
    await send_admin_reply(ctx, f"Event #{event_id} updated. " + " | ".join(parts))


async def remove_event_user(
    bot: discord.Client,
    ctx: discord.ApplicationContext,
    *,
    event_id: int,
    user: discord.Member,
) -> None:
    db = await get_db()
    result = await db.remove_event_user(event_id, str(user.id))
    if result is None:
        await send_admin_reply(
            ctx,
            f"{user.mention} is not registered for event #{event_id}.",
        )
        return

    await refresh_event_message(bot, event_id)
    promoted = f" Promoted <@{result}>." if result.isdigit() else ""
    await send_admin_reply(
        ctx,
        f"Removed {user.mention} from event #{event_id}.{promoted}",
    )


async def close_event(
    bot: discord.Client,
    ctx: discord.ApplicationContext,
    *,
    event_id: int,
) -> None:
    db = await get_db()
    if not await db.set_event_status(event_id, "closed"):
        await send_admin_reply(ctx, f"Event #{event_id} not found.")
        return

    cancel_event_jobs(event_id)
    await refresh_event_message(bot, event_id)
    await send_admin_reply(
        ctx,
        f"Event #{event_id} closed at {datetime.now(timezone.utc).isoformat()}.",
    )


async def cancel_event(
    bot: discord.Client,
    ctx: discord.ApplicationContext,
    *,
    event_id: int,
    reason: str | None,
    notify_users: bool,
) -> None:
    db = await get_db()
    event = await db.get_event(event_id)
    if not event:
        await send_admin_reply(ctx, f"Event #{event_id} not found.")
        return

    discord_cancelled = await cancel_discord_scheduled_event(
        ctx.guild,
        event,
        reason=reason,
    )
    if not await db.set_event_status(event_id, "cancelled"):
        await send_admin_reply(ctx, f"Event #{event_id} not found.")
        return

    cancel_event_jobs(event_id)
    await refresh_event_message(bot, event_id)
    if notify_users:
        await notify_event_cancelled(event_id, reason)

    sync_text = " Discord event cancelled." if discord_cancelled else ""
    await send_admin_reply(ctx, f"Event #{event_id} cancelled.{sync_text}")


def _event_input_error(
    *,
    player_limit: int,
    languages: str,
    check_in_opens_minutes: int,
) -> str | None:
    if player_limit < 0:
        return "Player limit must be 0 or higher. Use 0 for unlimited."
    if check_in_opens_minutes < 0:
        return "Check-in open minutes must be 0 or higher."
    if not normalize_event_languages(languages):
        return "Choose at least one language: en, ru, lt."
    return None


def _event_update_error(
    *,
    player_limit: int | None,
    check_in_opens_minutes: int | None,
) -> str | None:
    if player_limit is not None and player_limit < 0:
        return "Player limit must be 0 or higher. Use 0 for unlimited."
    if check_in_opens_minutes is not None and check_in_opens_minutes < 0:
        return "Check-in open minutes must be 0 or higher."
    return None


async def _register_initial_users(
    db,
    event_id: int,
    raw_users: str | None,
    *,
    added_by_id: str,
) -> tuple[int, int, int]:
    if not raw_users:
        return 0, 0, 0
    added_main, added_backup, skipped = await _register_users(
        db,
        event_id,
        parse_user_ids(raw_users),
        added_by_id=added_by_id,
    )
    return len(added_main), len(added_backup), len(skipped)


async def _register_users(
    db,
    event_id: int,
    user_ids: list[str],
    *,
    added_by_id: str,
) -> tuple[list[str], list[str], list[str]]:
    added_main = []
    added_backup = []
    skipped = []
    for user_id in user_ids:
        result = await db.register_event_user(
            event_id,
            user_id,
            added_by_id=added_by_id,
        )
        if result == "main":
            added_main.append(user_id)
        elif result == "backup":
            added_backup.append(user_id)
        else:
            skipped.append(user_id)
    return added_main, added_backup, skipped


async def _post_or_schedule_event_panel(
    channel: discord.TextChannel,
    event_id: int,
    message_schedule_unix: int | None,
) -> str:
    if not message_schedule_unix:
        await send_event_panel(channel.id, event_id)
        return f"Event #{event_id} posted in {channel.mention}."

    scheduler.add_job(
        send_event_panel,
        trigger="date",
        run_date=datetime.fromtimestamp(message_schedule_unix, tz=timezone.utc),
        args=[channel.id, event_id],
        id=f"event_{event_id}_panel",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    return (
        f"Event #{event_id} created. Panel scheduled for "
        f"<t:{int(message_schedule_unix)}:F> (<t:{int(message_schedule_unix)}:R>) "
        f"in {channel.mention}."
    )
