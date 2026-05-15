from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any, Optional

import discord

from config.config import config as bot_config
from src.features.status.core import (
    PresenceCandidate,
    build_event_candidate,
    build_fallback_candidates,
    build_minecraft_candidate,
    build_twitch_candidate,
    pick_presence_candidate,
    truncate_presence_text,
)
from src.features.status.minecraft import query_minecraft_status
from src.utils.database import get_db
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


def _get_config_value(root: Any, path: str, default: Any = None) -> Any:
    value = root
    for key in path.split("."):
        if value is None:
            return default
        value = getattr(value, key, default)
    return value


def status_feature_enabled() -> bool:
    return bool(_get_config_value(bot_config, "modules.status.enabled", False))


class StatusMonitor:
    """Rotates Discord presence from Minecraft, Twitch, events, and fallback data."""

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self._task: Optional[asyncio.Task] = None
        self._fallback_index = 0
        self._last_presence_key: Optional[tuple[str, str, Optional[str]]] = None

    async def start(self) -> None:
        if not status_feature_enabled():
            logger.info("Status monitor skipped: disabled in config")
            return
        if self._task and not self._task.done():
            logger.warning("Status monitor is already running")
            return
        self._task = asyncio.create_task(self._loop())
        logger.info("Status monitor started")

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        logger.info("Status monitor stopped")

    async def _loop(self) -> None:
        interval = max(
            15,
            int(_get_config_value(bot_config, "modules.status.update_interval_seconds", 90)),
        )
        while not self.bot.is_closed():
            try:
                await self.update_once()
            except Exception as error:
                logger.error(f"Status monitor update failed: {error}")
            await asyncio.sleep(interval)

    async def update_once(self) -> None:
        candidates = await self._collect_candidates()
        fallback = self._fallback_candidates()
        candidate = pick_presence_candidate(candidates, fallback, self._fallback_index)
        if candidate.priority == 0:
            self._fallback_index += 1

        presence_key = (candidate.kind, candidate.name, candidate.url)
        if presence_key == self._last_presence_key:
            logger.debug(
                f"Discord presence unchanged: {candidate.kind} {candidate.name}"
            )
            return

        await self.bot.change_presence(activity=self._to_discord_activity(candidate))
        self._last_presence_key = presence_key
        logger.info(f"Discord presence updated: {candidate.kind} {candidate.name}")

    async def _collect_candidates(self) -> list[PresenceCandidate]:
        candidates: list[PresenceCandidate] = []

        twitch_candidate = await self._twitch_candidate()
        if twitch_candidate:
            candidates.append(twitch_candidate)

        event_candidate = await self._event_candidate()
        if event_candidate:
            candidates.append(event_candidate)

        minecraft_candidate = await self._minecraft_candidate()
        if minecraft_candidate:
            candidates.append(minecraft_candidate)

        return candidates

    async def _twitch_candidate(self) -> Optional[PresenceCandidate]:
        if not bool(_get_config_value(bot_config, "modules.status.twitch.enabled", True)):
            return None

        streamers = _get_config_value(bot_config, "modules.twitch.streamers", {}) or {}
        configured_usernames = list(streamers.keys())
        if not configured_usernames:
            return None

        now = time.time()
        check_interval = int(
            _get_config_value(bot_config, "modules.twitch.check_interval_seconds", 30)
        )
        max_age = int(
            _get_config_value(
                bot_config,
                "modules.status.twitch.live_max_age_seconds",
                max(check_interval * 4, 300),
            )
        )

        db = await get_db()
        states = await db.get_all_stream_states()
        live_by_username = {
            str(state.get("twitch_username")): state
            for state in states
            if state.get("is_live")
            and now - float(state.get("last_checked") or 0) <= max_age
        }
        for username in configured_usernames:
            if username in live_by_username:
                return build_twitch_candidate(username)
        return None

    async def _event_candidate(self) -> Optional[PresenceCandidate]:
        if not bool(_get_config_value(bot_config, "modules.status.events.enabled", True)):
            return None

        now = time.time()
        upcoming_window = (
            float(
                _get_config_value(
                    bot_config, "modules.status.events.upcoming_window_hours", 24
                )
            )
            * 60
            * 60
        )
        db = await get_db()
        events = await db.get_active_events()
        visible_events = []
        for event in events:
            status = str(event.get("status") or "").lower()
            starts_at = float(event.get("starts_at") or 0)
            if status == "started" or (
                status == "open" and now <= starts_at <= now + upcoming_window
            ):
                visible_events.append(event)

        if not visible_events:
            return None

        visible_events.sort(
            key=lambda event: (
                0 if str(event.get("status")).lower() == "started" else 1,
                float(event.get("starts_at") or 0),
            )
        )
        return build_event_candidate(visible_events[0])

    async def _minecraft_candidate(self) -> Optional[PresenceCandidate]:
        if not bool(
            _get_config_value(bot_config, "modules.status.minecraft.enabled", True)
        ):
            return None

        host = str(_get_config_value(bot_config, "modules.status.minecraft.host", "")).strip()
        if not host:
            return None
        port = int(_get_config_value(bot_config, "modules.status.minecraft.port", 25565))
        timeout = float(
            _get_config_value(bot_config, "modules.status.minecraft.timeout_seconds", 5)
        )
        status = await query_minecraft_status(host, port=port, timeout=timeout)
        if not status:
            if bool(
                _get_config_value(
                    bot_config, "modules.status.minecraft.show_when_offline", False
                )
            ):
                return PresenceCandidate(
                    "watching", "Minecraft server offline", priority=20
                )
            return None

        players = status.get("players") or {}
        online_players = int(players.get("online") or 0)
        max_players = players.get("max")
        return build_minecraft_candidate(
            host=host,
            online_players=online_players,
            max_players=int(max_players) if max_players is not None else None,
        )

    def _fallback_candidates(self) -> list[PresenceCandidate]:
        raw_fallbacks = _get_config_value(bot_config, "modules.status.fallback", None)
        if raw_fallbacks is None:
            raw_fallbacks = [{"type": "playing", "text": "BebraLand"}]
        return build_fallback_candidates(raw_fallbacks)

    def _to_discord_activity(self, candidate: PresenceCandidate) -> discord.BaseActivity:
        kind = candidate.kind.lower()
        name = truncate_presence_text(candidate.name)

        if kind == "streaming" and candidate.url:
            return discord.Streaming(name=name, url=candidate.url)
        if kind == "watching":
            return discord.Activity(type=discord.ActivityType.watching, name=name)
        if kind == "listening":
            return discord.Activity(type=discord.ActivityType.listening, name=name)
        if kind == "competing":
            return discord.Activity(type=discord.ActivityType.competing, name=name)
        return discord.Game(name=name)


_status_monitor: Optional[StatusMonitor] = None


def get_status_monitor(bot: discord.Bot) -> StatusMonitor:
    global _status_monitor
    if _status_monitor is None:
        _status_monitor = StatusMonitor(bot)
    return _status_monitor
