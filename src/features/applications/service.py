import json

import discord

from config.config import config as bot_config
from src.features.applications.config import (
    REASON_MAX,
    get_application_config_value,
)
from src.languages import lang_constants
from src.languages.localize import _
from src.utils.bot_instance import get_bot
from src.utils.database import get_db, get_language
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


def _status_color(status: str) -> int:
    if status == "accepted":
        return bot_config.embeds.success_color
    if status in {"rejected", "revoked"}:
        return bot_config.embeds.failed_color
    return bot_config.embeds.info_color


def _format_answer_value(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return "No answer"
    if len(value) > 1024:
        return value[:1021] + "..."
    return value


def _normalize_answers(answers) -> list[dict]:
    if isinstance(answers, list):
        return [answer for answer in answers if isinstance(answer, dict)]
    if isinstance(answers, str):
        try:
            parsed = json.loads(answers)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [answer for answer in parsed if isinstance(answer, dict)]
    return []


def build_application_review_embed(
    application: dict,
    guild: discord.Guild,
    user: discord.abc.User,
) -> discord.Embed:
    status = application.get("status", "pending")
    embed = discord.Embed(
        title=f"Application #{application['id']} - {status.title()}",
        description=(
            f"**User:** {user.mention} (`{user.id}`)\n"
            f"**Created:** <t:{int(application['created_at'])}:F>"
        ),
        color=_status_color(status),
    )

    member = guild.get_member(int(application["user_id"]))
    if member:
        embed.add_field(
            name="Discord Info",
            value=(
                f"**Joined:** <t:{int(member.joined_at.timestamp())}:R>\n"
                f"**Account:** <t:{int(member.created_at.timestamp())}:R>"
            ),
            inline=False,
        )

    for answer in _normalize_answers(application.get("answers", [])):
        question = str(answer.get("question", "Question"))[:256]
        value = _format_answer_value(str(answer.get("value", "")))
        embed.add_field(name=question, value=value, inline=False)

    if status in {"accepted", "rejected"}:
        decided_by = application.get("decided_by") or "Unknown"
        reason = application.get("decision_reason") or "No reason provided."
        embed.add_field(
            name="Decision",
            value=(
                f"**By:** <@{decided_by}>\n"
                f"**At:** <t:{int(application['decided_at'])}:F>\n"
                f"**Reason:** {reason[:REASON_MAX]}"
            ),
            inline=False,
        )

    embed.set_footer(text=bot_config.bot.trademark, icon_url=get_embed_icon(guild.me))
    return embed


def build_application_panel_embed(ctx: discord.abc.User | None = None) -> discord.Embed:
    from src.features.applications.config import load_application_form_config

    data = load_application_form_config()
    panel = data["panel"]
    embed = discord.Embed(
        title=panel["title"],
        description=panel["description"],
        color=bot_config.embeds.default_color,
    )
    embed.set_footer(text=bot_config.bot.trademark, icon_url=get_embed_icon(ctx))
    return embed


def build_application_client_embed(
    title_key: str,
    description_key: str,
    locale: str,
    color: int,
    ctx=None,
    **format_values,
) -> discord.Embed:
    title = _(title_key, locale)
    description = _(description_key, locale).format(**format_values)
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text=bot_config.bot.trademark, icon_url=get_embed_icon(ctx))
    return embed


async def send_application_review(
    guild: discord.Guild,
    user: discord.Member,
    application_id: int,
) -> bool:
    review_channel_id = get_application_config_value("review_channel_id")
    if not review_channel_id:
        logger.error("Application review_channel_id is not configured")
        return False

    channel = guild.get_channel(int(review_channel_id))
    if not channel:
        channel = await guild.fetch_channel(int(review_channel_id))
    if not channel:
        logger.error(f"Application review channel {review_channel_id} not found")
        return False

    db = await get_db()
    application = await db.get_application(application_id)
    if not application:
        return False

    from src.features.applications.view.ApplicationReviewView import (
        ApplicationReviewView,
    )

    embed = build_application_review_embed(application, guild, user)
    message = await channel.send(embed=embed, view=ApplicationReviewView(application_id))
    await db.update_application_review_message(application_id, channel.id, message.id)
    logger.info(
        f"Application #{application_id} review message sent to channel {channel.id} as message {message.id}"
    )
    return True


async def apply_application_roles(
    member: discord.Member, status: str
) -> tuple[bool, str]:
    verified_role_id = get_application_config_value(
        "verified_role_id", 1501965355663233054
    )
    pending_role_id = get_application_config_value(
        "pending_role_id", 1501965434180862122
    )
    unverified_role_id = get_application_config_value(
        "unverified_role_id", 1501965564070068404
    )

    verified_role = member.guild.get_role(int(verified_role_id))
    pending_role = member.guild.get_role(int(pending_role_id))
    unverified_role = member.guild.get_role(int(unverified_role_id))

    missing_roles = []
    if not verified_role:
        missing_roles.append(f"verified_role_id={verified_role_id}")
    if not pending_role:
        missing_roles.append(f"pending_role_id={pending_role_id}")
    if not unverified_role:
        missing_roles.append(f"unverified_role_id={unverified_role_id}")
    if missing_roles:
        logger.warning(
            f"Application role update for {member.id} has missing roles: {', '.join(missing_roles)}"
        )

    try:
        if status == "pending":
            if pending_role:
                await member.add_roles(pending_role, reason="Application submitted")
                logger.info(
                    f"Added pending role {pending_role.id} to user {member.id}"
                )
            if unverified_role:
                await member.remove_roles(unverified_role, reason="Application submitted")
                logger.info(
                    f"Removed unverified role {unverified_role.id} from user {member.id}"
                )
        elif status == "accepted":
            if verified_role:
                await member.add_roles(verified_role, reason="Application accepted")
                logger.info(
                    f"Added verified role {verified_role.id} to user {member.id}"
                )
            roles_to_remove = [role for role in [pending_role, unverified_role] if role]
            if roles_to_remove:
                await member.remove_roles(
                    *roles_to_remove, reason="Application accepted"
                )
                logger.info(
                    "Removed application gate roles "
                    f"{','.join(str(role.id) for role in roles_to_remove)} from user {member.id}"
                )
        elif status == "rejected":
            if unverified_role:
                await member.add_roles(unverified_role, reason="Application rejected")
                logger.info(
                    f"Added unverified role {unverified_role.id} to user {member.id}"
                )
            if pending_role:
                await member.remove_roles(pending_role, reason="Application rejected")
                logger.info(
                    f"Removed pending role {pending_role.id} from user {member.id}"
                )
        elif status == "revoked":
            if unverified_role:
                await member.add_roles(
                    unverified_role, reason="Application status revoked"
                )
                logger.info(
                    f"Added unverified role {unverified_role.id} to user {member.id}"
                )
            roles_to_remove = [role for role in [verified_role, pending_role] if role]
            if roles_to_remove:
                await member.remove_roles(
                    *roles_to_remove, reason="Application status revoked"
                )
                logger.info(
                    "Removed application status roles "
                    f"{','.join(str(role.id) for role in roles_to_remove)} from user {member.id}"
                )
        return True, ""
    except discord.Forbidden:
        logger.error(
            f"Forbidden while updating application roles for {member.id}. "
            "Check Manage Roles permission and bot role hierarchy."
        )
        return False, "I do not have permission to manage one of the application roles."
    except Exception as error:
        logger.error(f"Failed to update application roles for {member.id}: {error}")
        return False, str(error)


async def get_guild_member(
    guild: discord.Guild, user_id: int
) -> discord.Member | None:
    member = guild.get_member(user_id)
    if member:
        return member
    try:
        member = await guild.fetch_member(user_id)
        logger.info(f"Fetched guild member {user_id} for application role update")
        return member
    except discord.NotFound:
        logger.warning(f"Application user {user_id} is no longer in guild {guild.id}")
        return None
    except Exception as error:
        logger.error(f"Failed to fetch guild member {user_id}: {error}")
        return None


async def notify_application_decision(
    user: discord.abc.User, status: str, reason: str | None
) -> None:
    if not get_application_config_value("dm_on_decision", True):
        return

    locale = await get_language(user.id)
    title_key = (
        "applications.decision.accepted_title"
        if status == "accepted"
        else "applications.decision.revoked_title"
        if status == "revoked"
        else "applications.decision.rejected_title"
    )
    description_key = (
        "applications.decision.accepted_description"
        if status == "accepted"
        else "applications.decision.revoked_description"
        if status == "revoked"
        else "applications.decision.rejected_description"
    )
    embed = build_application_client_embed(
        title_key,
        description_key,
        locale,
        _status_color(status),
        get_bot(),
    )
    if reason:
        embed.add_field(
            name=f"{lang_constants.INFO_EMOJI} {_('applications.reason', locale)}",
            value=reason[:REASON_MAX],
            inline=False,
        )
    try:
        await user.send(embed=embed)
    except Exception:
        logger.info(f"Could not DM application decision to user {user.id}")
