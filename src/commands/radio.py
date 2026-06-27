import asyncio
import os
from typing import Any

import aiohttp
import discord
from discord.ext import commands

from config.config import config as bot_config
from src.languages.localize import _
from src.utils.database import get_db, get_language
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)

API_URL = "https://radio.auuruum.me/api/nowplaying/bebralandfm"
STREAM_URL = "https://radio.auuruum.me/listen/bebralandfm/radio.mp3"
PLAYER_URL = "https://radio.auuruum.me/public/bebralandfm"
WEBSITE_URL = "https://bebraland.auuruum.me/"
RADIO_COLOR = 0x714C35


def _get(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _text(value: Any, fallback: str) -> str:
    return value if isinstance(value, str) and value.strip() else fallback


def _song_label(song: dict[str, Any] | None, locale: str) -> str:
    song = song if isinstance(song, dict) else {}
    artist = _text(song.get("artist"), _("radio.unknown_artist", locale))
    title = _text(song.get("title"), _("radio.unknown_title", locale))
    return f"{artist} - {title}"


async def _fetch_nowplaying() -> dict[str, Any]:
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(API_URL) as response:
            response.raise_for_status()
            data = await response.json(content_type=None)
            if not isinstance(data, dict):
                raise ValueError("AzuraCast returned non-object JSON")
            return data


def _history(data: dict[str, Any], limit: int, locale: str) -> list[str]:
    history = data.get("song_history")
    if not isinstance(history, list):
        return []

    labels = []
    for item in history[:limit]:
        if isinstance(item, dict):
            labels.append(_song_label(item.get("song"), locale))
    return labels


def _add_footer(embed: discord.Embed, ctx_or_bot: Any) -> None:
    embed.set_footer(text=bot_config.bot.trademark, icon_url=get_embed_icon(ctx_or_bot))


async def _read_message_states() -> list[dict[str, int]]:
    db = await get_db()
    return await db.get_all_radio_panel_states()


async def _write_message_state(
    guild_id: int, channel_id: int, message_id: int
) -> bool:
    db = await get_db()
    return await db.add_radio_panel_state(guild_id, channel_id, message_id)


async def _replace_message_state(
    guild_id: int, channel_id: int, message_id: int, old_message_id: int | None = None
) -> bool:
    db = await get_db()
    return await db.replace_radio_panel_state(
        guild_id, channel_id, message_id, old_message_id=old_message_id
    )


async def _remove_message_state(guild_id: int, message_id: int) -> bool:
    db = await get_db()
    return await db.remove_radio_panel_state(guild_id, message_id)


def _radio_embed(data: dict[str, Any], ctx_or_bot: Any, locale: str) -> discord.Embed:
    station = data.get("station") if isinstance(data.get("station"), dict) else {}
    listeners = _get(data, "listeners", "current")
    live = data.get("live") if isinstance(data.get("live"), dict) else {}
    song = _get(data, "now_playing", "song")
    song = song if isinstance(song, dict) else {}

    title = _text(station.get("name"), "BebraLand FM")
    description = _text(station.get("description"), _("radio.station_description", locale))
    embed = discord.Embed(
        title=_("radio.card_title", locale).format(station=title),
        description=description,
        color=RADIO_COLOR,
        url=WEBSITE_URL,
    )

    album = _text(song.get("album"), _("radio.no_album", locale))
    live_text = _("radio.yes", locale) if live.get("is_live") else _("radio.no", locale)
    streamer = _text(live.get("streamer_name"), "")
    if streamer:
        live_text = f"{live_text} ({streamer})"

    embed.add_field(
        name=_("radio.now_playing", locale),
        value=f"{_song_label(song, locale)}\n{_('radio.album', locale)}: {album}",
        inline=False,
    )
    embed.add_field(name=_("radio.listeners", locale), value=str(listeners or 0), inline=True)
    embed.add_field(name=_("radio.live", locale), value=live_text, inline=True)
    embed.add_field(
        name=_("radio.links", locale),
        value=f"[{_('radio.listen', locale)}]({station.get('listen_url') or STREAM_URL}) | [{_('radio.player', locale)}]({station.get('public_player_url') or PLAYER_URL})",
        inline=False,
    )

    recent = _history(data, 3, locale)
    if recent:
        embed.add_field(
            name=_("radio.recently_played", locale),
            value="\n".join(f"{index}. {label}" for index, label in enumerate(recent, 1)),
            inline=False,
        )

    art = _text(song.get("art"), "")
    if art:
        embed.set_thumbnail(url=art)
    _add_footer(embed, ctx_or_bot)
    return embed


def _nowplaying_embed(data: dict[str, Any], ctx_or_bot: Any, locale: str) -> discord.Embed:
    song = _get(data, "now_playing", "song")
    song = song if isinstance(song, dict) else {}
    listeners = _get(data, "listeners", "current")

    embed = discord.Embed(
        title=_("radio.nowplaying_title", locale),
        description=_song_label(song, locale),
        color=RADIO_COLOR,
        url=PLAYER_URL,
    )
    embed.add_field(
        name=_("radio.album", locale),
        value=_text(song.get("album"), _("radio.no_album", locale)),
        inline=False,
    )
    embed.add_field(name=_("radio.listeners", locale), value=str(listeners or 0), inline=True)
    embed.add_field(
        name=_("radio.listen", locale),
        value=f"[{_('radio.open_stream', locale)}]({STREAM_URL})",
        inline=True,
    )

    art = _text(song.get("art"), "")
    if art:
        embed.set_thumbnail(url=art)
    _add_footer(embed, ctx_or_bot)
    return embed


def _history_embed(data: dict[str, Any], ctx_or_bot: Any, locale: str) -> discord.Embed:
    recent = _history(data, 5, locale)
    description = (
        "\n".join(f"{index}. {label}" for index, label in enumerate(recent, 1))
        if recent
        else _("radio.no_recent_tracks", locale)
    )
    embed = discord.Embed(
        title=_("radio.history_title", locale),
        description=description,
        color=RADIO_COLOR,
        url=PLAYER_URL,
    )
    _add_footer(embed, ctx_or_bot)
    return embed


class Radio(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.channel_id = self._load_channel_id()
        self._task_started = False

    @staticmethod
    def _load_channel_id() -> int | None:
        value = os.getenv("RADIO_NOWPLAYING_CHANNEL_ID")
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            logger.error("RADIO_NOWPLAYING_CHANNEL_ID must be a Discord channel ID")
            return None

    @commands.Cog.listener()
    async def on_ready(self):
        if not self._task_started and (
            self.channel_id or await _read_message_states()
        ):
            self._task_started = True
            asyncio.create_task(self._nowplaying_loop())

    @commands.slash_command(name="radio", description="Show the BebraLand FM radio card")
    async def radio(self, ctx: discord.ApplicationContext):
        await self._reply(ctx, _radio_embed, ephemeral=True)

    @commands.slash_command(name="radiohistory", description="Show recent BebraLand FM tracks")
    async def radiohistory(self, ctx: discord.ApplicationContext):
        await self._reply(ctx, _history_embed, ephemeral=True)

    async def _reply(self, ctx: discord.ApplicationContext, builder, ephemeral: bool = False):
        await ctx.defer(ephemeral=ephemeral)
        locale = await get_language(ctx.user.id)
        try:
            data = await _fetch_nowplaying()
        except Exception as error:
            logger.error(f"AzuraCast fetch failed: {error}")
            await ctx.followup.send(
                _("radio.unavailable", locale),
                ephemeral=ephemeral,
            )
            return

        await ctx.followup.send(embed=builder(data, ctx, locale), ephemeral=ephemeral)

    async def _nowplaying_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self._sync_nowplaying_message()
            except Exception as error:
                logger.error(f"Radio now-playing update failed: {error}")
            await asyncio.sleep(60)

    async def _sync_nowplaying_message(self):
        states = await _read_message_states()
        if self.channel_id and not any(
            state.get("channel_id") == self.channel_id for state in states
        ):
            states.append({"channel_id": self.channel_id})
        for state in states:
            await self._sync_nowplaying_state(state)

    async def _sync_nowplaying_state(self, state: dict[str, int]):
        channel_id = state.get("channel_id")
        if not channel_id:
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(channel_id)
        if not hasattr(channel, "send"):
            logger.error(f"Radio channel {channel_id} is not a text channel")
            return

        data = await _fetch_nowplaying()
        embed = _radio_embed(data, self.bot, bot_config.bot.default_language)
        message_id = state.get("message_id")

        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(embed=embed)
                return
            except discord.NotFound:
                guild_id = state.get("guild_id")
                if guild_id:
                    await _remove_message_state(guild_id, message_id)
                return

        message = await channel.send(embed=embed)
        guild = getattr(channel, "guild", None)
        if guild:
            await _replace_message_state(guild.id, channel.id, message.id, message_id)


def setup(bot: commands.Bot):
    bot.add_cog(Radio(bot))
