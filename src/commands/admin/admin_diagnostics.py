from __future__ import annotations

import json
from pathlib import Path

import discord
from discord.ext import commands
from pycord.multicog import subcommand

import src.languages.lang_constants as lang_constants
from config.config import config as bot_config
from src.utils.auth import require_admin
from src.utils.database import get_db
from src.utils.embeds import build_embeds_from_message_data, get_embed_icon

PROJECT_ROOT = Path(__file__).resolve().parents[3]

CHANNEL_CHECKS = [
    ("Applications review channel", "modules.applications.review_channel_id"),
    ("Tickets category", "modules.tickets.category_id"),
    ("Tickets log channel", "modules.tickets.log_channel_id"),
    ("Twitch channel", "modules.twitch.channel_id"),
    ("Temp voice category", "modules.temp_voice.category_id"),
    ("Temp voice lobby", "modules.temp_voice.lobby_id"),
    ("News EN channel", "modules.news.english_channel_id"),
    ("News RU channel", "modules.news.russian_channel_id"),
    ("News LT channel", "modules.news.lithuanian_channel_id"),
]

ROLE_CHECKS = [
    ("Applications reviewer role", "modules.applications.reviewer_role_id"),
    ("Applications verified role", "modules.applications.verified_role_id"),
    ("Applications pending role", "modules.applications.pending_role_id"),
    ("Applications unverified role", "modules.applications.unverified_role_id"),
    ("Tickets support role", "modules.tickets.support_role_id"),
    ("Twitch live role", "modules.twitch.live_role_id"),
    ("Twitch ping role", "modules.twitch.ping_role_id"),
]

ASSIGNABLE_ROLE_CHECKS = [
    ("Applications verified role", "modules.applications.verified_role_id"),
    ("Applications pending role", "modules.applications.pending_role_id"),
    ("Applications unverified role", "modules.applications.unverified_role_id"),
    ("Twitch live role", "modules.twitch.live_role_id"),
]

JSON_TEMPLATE_PATHS = [
    "config/applications.json",
    "config/tickets.json",
    "src/languages/messages/language.json",
    "src/languages/messages/rules.json",
    "src/languages/messages/twitch.json",
    "src/languages/messages/welcome.json",
    "src/languages/i18n/en.json",
    "src/languages/i18n/ru.json",
    "src/languages/i18n/lt.json",
]


def _get_config(path: str, default=None):
    value = bot_config
    for key in path.split("."):
        value = getattr(value, key, default)
        if value is default:
            return default
    return value


def _configured(value) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, list):
        return bool(value) and all(_configured(item) for item in value)
    return str(value).strip().upper() != "CHANGE_ME"


def _int_id(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _check_channel(guild: discord.Guild, label: str, value) -> str:
    if not _configured(value):
        return f"{lang_constants.ERROR_EMOJI} {label}: not configured"
    channel_id = _int_id(value)
    if channel_id is None:
        return f"{lang_constants.ERROR_EMOJI} {label}: invalid id `{value}`"
    channel = guild.get_channel(channel_id)
    if channel is None:
        return f"{lang_constants.ERROR_EMOJI} {label}: missing <#{channel_id}>"
    return f"{lang_constants.SUCCESS_EMOJI} {label}: {channel.mention}"


def _check_role(guild: discord.Guild, label: str, value) -> str:
    if not _configured(value):
        return f"{lang_constants.ERROR_EMOJI} {label}: not configured"
    role_id = _int_id(value)
    if role_id is None:
        return f"{lang_constants.ERROR_EMOJI} {label}: invalid id `{value}`"
    role = guild.get_role(role_id)
    if role is None:
        return f"{lang_constants.ERROR_EMOJI} {label}: missing `{role_id}`"
    return f"{lang_constants.SUCCESS_EMOJI} {label}: {role.mention}"


def _check_roles(guild: discord.Guild, label: str, values) -> list[str]:
    if not isinstance(values, list):
        values = [values]
    return [_check_role(guild, f"{label} #{index}", value) for index, value in enumerate(values, 1)]


def _resolve_channel(guild: discord.Guild, value) -> discord.abc.GuildChannel | None:
    channel_id = _int_id(value)
    if channel_id is None:
        return None
    return guild.get_channel(channel_id)


def _resolve_role(guild: discord.Guild, value) -> discord.Role | None:
    role_id = _int_id(value)
    if role_id is None:
        return None
    return guild.get_role(role_id)


def _permission_state(permissions, names: list[str]) -> str:
    missing = [name for name in names if not getattr(permissions, name, False)]
    if not missing:
        return f"{lang_constants.SUCCESS_EMOJI} ok"
    readable = ", ".join(name.replace("_", " ").title() for name in missing)
    return f"{lang_constants.ERROR_EMOJI} missing {readable}"


def _channel_required_permissions(channel: discord.abc.GuildChannel) -> list[str]:
    if isinstance(channel, discord.CategoryChannel):
        return ["view_channel", "manage_channels"]
    if isinstance(channel, discord.VoiceChannel):
        return ["view_channel", "connect", "manage_channels"]
    return ["view_channel", "send_messages", "embed_links", "read_message_history"]


def _channel_permission_lines(guild: discord.Guild) -> list[str]:
    bot_member = guild.me
    if bot_member is None:
        return [f"{lang_constants.ERROR_EMOJI} Bot member not found in guild"]

    lines = []
    for label, path in CHANNEL_CHECKS:
        value = _get_config(path)
        if not _configured(value):
            continue
        channel = _resolve_channel(guild, value)
        if channel is None:
            continue
        permissions = channel.permissions_for(bot_member)
        required = _channel_required_permissions(channel)
        lines.append(f"{_permission_state(permissions, required)} {label}")
    return lines or [f"{lang_constants.SUCCESS_EMOJI} No configured channels to check"]


def _role_hierarchy_lines(guild: discord.Guild) -> list[str]:
    bot_member = guild.me
    if bot_member is None:
        return [f"{lang_constants.ERROR_EMOJI} Bot member not found in guild"]

    lines = []
    if not bot_member.guild_permissions.manage_roles:
        lines.append(f"{lang_constants.ERROR_EMOJI} Bot is missing Manage Roles")

    role_checks = list(ASSIGNABLE_ROLE_CHECKS)
    role_checks.extend(
        ("Temp voice default role", value)
        for value in _get_config("modules.temp_voice.default_user_role_ids", [])
    )

    for label, path_or_value in role_checks:
        value = (
            _get_config(path_or_value)
            if isinstance(path_or_value, str) and path_or_value.startswith("modules.")
            else path_or_value
        )
        if not _configured(value):
            continue
        role = _resolve_role(guild, value)
        if role is None:
            continue
        if role >= bot_member.top_role:
            lines.append(
                f"{lang_constants.ERROR_EMOJI} {label}: {role.mention} is above/equal "
                f"bot top role {bot_member.top_role.mention}"
            )
        else:
            lines.append(f"{lang_constants.SUCCESS_EMOJI} {label}: manageable")

    return lines or [f"{lang_constants.SUCCESS_EMOJI} No assignable roles configured"]


def _validate_applications_json(data: object) -> list[str]:
    errors = []
    if not isinstance(data, dict):
        return ["root must be an object"]
    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        errors.append("questions must be a non-empty list")
    else:
        for index, question in enumerate(questions, 1):
            if not isinstance(question, dict):
                errors.append(f"question #{index} must be an object")
                continue
            if not question.get("question"):
                errors.append(f"question #{index} is missing question text")
            if question.get("type") in {"dropdown", "select", "choice", "button", "buttons"}:
                if not isinstance(question.get("options"), list) or not question["options"]:
                    errors.append(f"question #{index} requires options")
    panel_source = data.get("panel") if isinstance(data.get("panel"), dict) else data
    if not build_embeds_from_message_data(panel_source, default_color=None):
        if not (data.get("title") or data.get("description") or data.get("panel")):
            errors.append("panel has no usable embed/title/description")
    return errors


def _validate_tickets_json(data: object) -> list[str]:
    errors = []
    if not isinstance(data, dict):
        return ["root must be an object"]
    categories = data.get("ticketCategories")
    if not isinstance(categories, list) or not categories:
        return ["ticketCategories must be a non-empty list"]
    for index, category in enumerate(categories, 1):
        if not isinstance(category, dict):
            errors.append(f"category #{index} must be an object")
            continue
        for key in ("name", "description", "emoji"):
            if not category.get(key):
                errors.append(f"category #{index} is missing {key}")
        forms = category.get("forms", [])
        if forms is not None and not isinstance(forms, list):
            errors.append(f"category #{index} forms must be a list")
    return errors


def _json_template_lines() -> list[str]:
    lines = []
    for relative_path in JSON_TEMPLATE_PATHS:
        path = PROJECT_ROOT / relative_path
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            errors = []
            if relative_path == "config/applications.json":
                errors = _validate_applications_json(data)
            elif relative_path == "config/tickets.json":
                errors = _validate_tickets_json(data)
            elif "/messages/" in relative_path.replace("\\", "/"):
                if not isinstance(data, dict):
                    errors = ["root must be an object"]
                elif not build_embeds_from_message_data(data, default_color=None):
                    errors = ["no usable embed data found"]
            if errors:
                lines.append(
                    f"{lang_constants.ERROR_EMOJI} {relative_path}: {errors[0]}"
                )
            else:
                lines.append(f"{lang_constants.SUCCESS_EMOJI} {relative_path}: valid")
        except FileNotFoundError:
            lines.append(f"{lang_constants.ERROR_EMOJI} {relative_path}: missing")
        except json.JSONDecodeError as error:
            lines.append(
                f"{lang_constants.ERROR_EMOJI} {relative_path}: JSON line "
                f"{error.lineno}: {error.msg}"
            )
        except Exception as error:
            lines.append(
                f"{lang_constants.ERROR_EMOJI} {relative_path}: "
                f"{type(error).__name__}: {error}"
            )
    return lines


def _configured_id_paths(value, prefix: str = "") -> list[str]:
    if not isinstance(value, dict):
        return []

    paths = []
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if (str(key).endswith("_id") or str(key).endswith("_ids")) and _configured(item):
            paths.append(path)
        paths.extend(_configured_id_paths(item, path))
    return paths


def _disabled_module_lines() -> list[str]:
    modules = _get_config("modules", {})
    lines = []
    if not isinstance(modules, dict):
        return [f"{lang_constants.ERROR_EMOJI} modules config is invalid"]

    def scan(section, path: str):
        if not isinstance(section, dict):
            return
        if section.get("enabled") is False:
            configured_ids = _configured_id_paths(section)
            if configured_ids:
                lines.append(
                    f"{lang_constants.ERROR_EMOJI} {path}: disabled but has "
                    f"configured IDs ({', '.join(configured_ids[:3])})"
                )
        for key, item in section.items():
            if isinstance(item, dict):
                scan(item, f"{path}.{key}")

    scan(modules, "modules")
    return lines or [f"{lang_constants.SUCCESS_EMOJI} No disabled modules with configured IDs"]


def _chunks(lines: list[str], max_len: int = 1000) -> list[str]:
    chunks = []
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > max_len:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


async def _database_line(guild_id: int) -> str:
    try:
        db = await get_db()
        await db.get_application_enabled(guild_id)
        return f"{lang_constants.SUCCESS_EMOJI} Database: reachable"
    except Exception as error:
        return f"{lang_constants.ERROR_EMOJI} Database: {type(error).__name__}: {error}"


def _permission_lines(guild: discord.Guild) -> list[str]:
    permissions = guild.me.guild_permissions if guild.me else None
    checks = {
        "Send Messages": "send_messages",
        "Embed Links": "embed_links",
        "Manage Roles": "manage_roles",
        "Manage Channels": "manage_channels",
        "Manage Messages": "manage_messages",
        "Read Message History": "read_message_history",
    }
    if permissions is None:
        return [f"{lang_constants.ERROR_EMOJI} Bot member not found in guild"]
    return [
        f"{lang_constants.SUCCESS_EMOJI if getattr(permissions, attr, False) else lang_constants.ERROR_EMOJI} {label}"
        for label, attr in checks.items()
    ]


def _config_lines(guild: discord.Guild) -> list[str]:
    lines = [
        _check_channel(guild, label, _get_config(path))
        for label, path in CHANNEL_CHECKS
    ]
    lines.extend(_check_role(guild, label, _get_config(path)) for label, path in ROLE_CHECKS)
    lines.extend(_check_roles(guild, "Temp voice default role", _get_config("modules.temp_voice.default_user_role_ids", [])))
    return lines


class AdminDiagnostics(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @subcommand("admin")
    @discord.slash_command(
        name="diagnostics",
        description="Check bot config, permissions, and database access",
    )
    async def diagnostics(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        if not await require_admin(ctx):
            return

        config_lines = _config_lines(ctx.guild)
        permission_lines = _permission_lines(ctx.guild)
        channel_permission_lines = _channel_permission_lines(ctx.guild)
        role_hierarchy_lines = _role_hierarchy_lines(ctx.guild)
        json_template_lines = _json_template_lines()
        disabled_module_lines = _disabled_module_lines()
        db_line = await _database_line(ctx.guild.id)
        check_lines = (
            config_lines
            + permission_lines
            + channel_permission_lines
            + role_hierarchy_lines
            + json_template_lines
            + disabled_module_lines
            + [db_line]
        )
        ok_count = sum(
            line.startswith(lang_constants.SUCCESS_EMOJI)
            for line in check_lines
        )
        total_count = len(check_lines)

        embed = discord.Embed(
            title="Bot diagnostics",
            description=f"{ok_count}/{total_count} checks passed.",
            color=bot_config.embeds.success_color
            if ok_count == total_count
            else bot_config.embeds.warning_color,
        )
        embed.add_field(name="Runtime", value=db_line, inline=False)
        embed.add_field(name="Permissions", value="\n".join(permission_lines), inline=False)
        for index, chunk in enumerate(_chunks(channel_permission_lines), 1):
            name = "Channel Permissions" if index == 1 else f"Channel Permissions {index}"
            embed.add_field(name=name, value=chunk, inline=False)
        for index, chunk in enumerate(_chunks(role_hierarchy_lines), 1):
            name = "Role Hierarchy" if index == 1 else f"Role Hierarchy {index}"
            embed.add_field(name=name, value=chunk, inline=False)
        for index, chunk in enumerate(_chunks(json_template_lines), 1):
            name = "JSON Templates" if index == 1 else f"JSON Templates {index}"
            embed.add_field(name=name, value=chunk, inline=False)
        for index, chunk in enumerate(_chunks(disabled_module_lines), 1):
            name = "Disabled Modules" if index == 1 else f"Disabled Modules {index}"
            embed.add_field(name=name, value=chunk, inline=False)
        for index, chunk in enumerate(_chunks(config_lines), 1):
            name = "Config" if index == 1 else f"Config {index}"
            embed.add_field(name=name, value=chunk, inline=False)
        embed.set_footer(text=bot_config.bot.trademark, icon_url=get_embed_icon(ctx))
        await ctx.followup.send(embed=embed, ephemeral=True)


def setup(bot: commands.Bot):
    bot.add_cog(AdminDiagnostics(bot))
