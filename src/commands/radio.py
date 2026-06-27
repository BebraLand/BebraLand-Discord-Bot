import asyncio
import json
import os
from pathlib import Path
from typing import Any

import aiohttp
import discord
from discord.ext import commands

from config.config import config as bot_config
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)

API_URL = "https://radio.auuruum.me/api/nowplaying/bebralandfm"
STREAM_URL = "https://radio.auuruum.me/listen/bebralandfm/radio.mp3"
PLAYER_URL = "https://radio.auuruum.me/public/bebralandfm"
WEBSITE_URL = "https://bebraland.auuruum.me/"
MESSAGE_STATE_PATH = Path("data/radio_nowplaying_message.json")
RADIO_COLOR = 0x714C35


def _get(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _text(value: Any, fallback: str) -> str:
    return value if isinstance(value, str) and value.strip() else fallback


def _song_label(song: dict[str, Any] | None) -> str:
    song = song if isinstance(song, dict) else {}
    artist = _text(song.get("artist"), "Unknown artist")
    title = _text(song.get("title"), "Unknown title")
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


def _history(data: dict[str, Any], limit: int) -> list[str]:
    history = data.get("song_history")
    if not isinstance(history, list):
        return []

    labels = []
    for item in history[:limit]:
        if isinstance(item, dict):
            labels.append(_song_label(item.get("song")))
    return labels


def _add_footer(embed: discord.Embed, ctx_or_bot: Any) -> None:
    embed.set_footer(text=bot_config.bot.trademark, icon_url=get_embed_icon(ctx_or_bot))


def _radio_embed(data: dict[str, Any], ctx_or_bot: Any) -> discord.Embed:
    station = data.get("station") if isinstance(data.get("station"), dict) else {}
    listeners = _get(data, "listeners", "current")
    live = data.get("live") if isinstance(data.get("live"), dict) else {}
    song = _get(data, "now_playing", "song")
    song = song if isinstance(song, dict) else {}

    title = _text(station.get("name"), "BebraLand FM")
    description = _text(station.get("description"), "Community radio for BebraLand")
    embed = discord.Embed(
        title=f"Radio: {title}",
        description=description,
        color=RADIO_COLOR,
        url=WEBSITE_URL,
    )

    album = _text(song.get("album"), "No album information")
    live_text = "Yes" if live.get("is_live") else "No"
    streamer = _text(live.get("streamer_name"), "")
    if streamer:
        live_text = f"{live_text} ({streamer})"

    embed.add_field(name="Now playing", value=f"{_song_label(song)}\nAlbum: {album}", inline=False)
    embed.add_field(name="Listeners", value=str(listeners or 0), inline=True)
    embed.add_field(name="Live", value=live_text, inline=True)
    embed.add_field(
        name="Links",
        value=f"[Listen]({station.get('listen_url') or STREAM_URL}) | [Player]({station.get('public_player_url') or PLAYER_URL})",
        inline=False,
    )

    recent = _history(data, 3)
    if recent:
        embed.add_field(
            name="Recently played",
            value="\n".join(f"{index}. {label}" for index, label in enumerate(recent, 1)),
            inline=False,
        )

    art = _text(song.get("art"), "")
    if art:
        embed.set_thumbnail(url=art)
    _add_footer(embed, ctx_or_bot)
    return embed


def _nowplaying_embed(data: dict[str, Any], ctx_or_bot: Any) -> discord.Embed:
    song = _get(data, "now_playing", "song")
    song = song if isinstance(song, dict) else {}
    listeners = _get(data, "listeners", "current")

    embed = discord.Embed(
        title="Now playing on BebraLand FM",
        description=_song_label(song),
        color=RADIO_COLOR,
        url=PLAYER_URL,
    )
    embed.add_field(name="Album", value=_text(song.get("album"), "No album information"), inline=False)
    embed.add_field(name="Listeners", value=str(listeners or 0), inline=True)
    embed.add_field(name="Listen", value=f"[Open stream]({STREAM_URL})", inline=True)

    art = _text(song.get("art"), "")
    if art:
        embed.set_thumbnail(url=art)
    _add_footer(embed, ctx_or_bot)
    return embed


def _history_embed(data: dict[str, Any], ctx_or_bot: Any) -> discord.Embed:
    recent = _history(data, 5)
    description = (
        "\n".join(f"{index}. {label}" for index, label in enumerate(recent, 1))
        if recent
        else "No recent tracks yet."
    )
    embed = discord.Embed(
        title="BebraLand FM history",
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
        if self.channel_id and not self._task_started:
            self._task_started = True
            asyncio.create_task(self._nowplaying_loop())

    @commands.slash_command(name="radio", description="Show the BebraLand FM radio card")
    async def radio(self, ctx: discord.ApplicationContext):
        await self._reply(ctx, _radio_embed, ephemeral=True)

    @commands.slash_command(name="nowplaying", description="Show the current BebraLand FM song")
    async def nowplaying(self, ctx: discord.ApplicationContext):
        await self._reply(ctx, _nowplaying_embed)

    @commands.slash_command(name="radiohistory", description="Show recent BebraLand FM tracks")
    async def radiohistory(self, ctx: discord.ApplicationContext):
        await self._reply(ctx, _history_embed, ephemeral=True)

    async def _reply(self, ctx: discord.ApplicationContext, builder, ephemeral: bool = False):
        await ctx.defer(ephemeral=ephemeral)
        try:
            data = await _fetch_nowplaying()
        except Exception as error:
            logger.error(f"AzuraCast fetch failed: {error}")
            await ctx.followup.send(
                "BebraLand FM is unavailable right now. Please try again soon.",
                ephemeral=ephemeral,
            )
            return

        await ctx.followup.send(embed=builder(data, ctx), ephemeral=ephemeral)

    async def _nowplaying_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self._sync_nowplaying_message()
            except Exception as error:
                logger.error(f"Radio now-playing update failed: {error}")
            await asyncio.sleep(60)

    async def _sync_nowplaying_message(self):
        channel = self.bot.get_channel(self.channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(self.channel_id)
        if not hasattr(channel, "send"):
            logger.error(f"Radio channel {self.channel_id} is not a text channel")
            return

        data = await _fetch_nowplaying()
        embed = _nowplaying_embed(data, self.bot)
        message_id = self._read_message_id()

        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(embed=embed)
                return
            except discord.NotFound:
                pass

        message = await channel.send(embed=embed)
        self._write_message_id(message.id)

    @staticmethod
    def _read_message_id() -> int | None:
        try:
            data = json.loads(MESSAGE_STATE_PATH.read_text(encoding="utf-8"))
            return int(data["message_id"])
        except Exception:
            return None

    @staticmethod
    def _write_message_id(message_id: int) -> None:
        MESSAGE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        MESSAGE_STATE_PATH.write_text(
            json.dumps({"message_id": message_id}, indent=2),
            encoding="utf-8",
        )


def setup(bot: commands.Bot):
    bot.add_cog(Radio(bot))
