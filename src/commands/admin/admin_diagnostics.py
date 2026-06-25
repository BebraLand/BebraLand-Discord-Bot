import discord
from discord.ext import commands
from pycord.multicog import subcommand

import src.languages.lang_constants as lang_constants
from config.config import config as bot_config
from src.utils.auth import require_admin
from src.utils.database import get_db
from src.utils.embeds import get_embed_icon


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
        _check_channel(guild, "Applications review channel", _get_config("modules.applications.review_channel_id")),
        _check_role(guild, "Applications reviewer role", _get_config("modules.applications.reviewer_role_id")),
        _check_role(guild, "Applications verified role", _get_config("modules.applications.verified_role_id")),
        _check_channel(guild, "Tickets category", _get_config("modules.tickets.category_id")),
        _check_channel(guild, "Tickets log channel", _get_config("modules.tickets.log_channel_id")),
        _check_role(guild, "Tickets support role", _get_config("modules.tickets.support_role_id")),
        _check_channel(guild, "Twitch channel", _get_config("modules.twitch.channel_id")),
        _check_role(guild, "Twitch live role", _get_config("modules.twitch.live_role_id")),
        _check_role(guild, "Twitch ping role", _get_config("modules.twitch.ping_role_id")),
        _check_channel(guild, "Temp voice category", _get_config("modules.temp_voice.category_id")),
        _check_channel(guild, "Temp voice lobby", _get_config("modules.temp_voice.lobby_id")),
        _check_channel(guild, "News EN channel", _get_config("modules.news.english_channel_id")),
        _check_channel(guild, "News RU channel", _get_config("modules.news.russian_channel_id")),
        _check_channel(guild, "News LT channel", _get_config("modules.news.lithuanian_channel_id")),
    ]
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
        db_line = await _database_line(ctx.guild.id)
        ok_count = sum(
            line.startswith(lang_constants.SUCCESS_EMOJI)
            for line in config_lines + permission_lines + [db_line]
        )
        total_count = len(config_lines) + len(permission_lines) + 1

        embed = discord.Embed(
            title="Bot diagnostics",
            description=f"{ok_count}/{total_count} checks passed.",
            color=bot_config.embeds.success_color
            if ok_count == total_count
            else bot_config.embeds.warning_color,
        )
        embed.add_field(name="Runtime", value=db_line, inline=False)
        embed.add_field(name="Permissions", value="\n".join(permission_lines), inline=False)
        for index, chunk in enumerate(_chunks(config_lines), 1):
            name = "Config" if index == 1 else f"Config {index}"
            embed.add_field(name=name, value=chunk, inline=False)
        embed.set_footer(text=bot_config.bot.trademark, icon_url=get_embed_icon(ctx))
        await ctx.followup.send(embed=embed, ephemeral=True)


def setup(bot: commands.Bot):
    bot.add_cog(AdminDiagnostics(bot))
