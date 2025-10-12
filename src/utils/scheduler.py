import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

import discord
import base64
import io
import os
import config.constants as constants
from src.utils.database import get_language

from src.utils.logger import get_cool_logger
from src.views.language_selector import LanguageSelector
from src.views.language_selector import build_language_selector_embed 
from src.utils.embed_builder import build_embed_from_template, build_embed_from_data, replace_placeholders


logger = get_cool_logger(__name__)


class Scheduler:
    """
    Simple persistent scheduler for one-off tasks.
    - Validates HH:MM format strictly
    - Persists tasks to disk to survive bot restarts
    - Schedules execution using asyncio
    """

    def __init__(self, storage_path: str = "data/scheduled_tasks.json") -> None:
        self.storage_path = storage_path
        self.bot: Optional[discord.Bot] = None
        self._scheduled_handles: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        # Ensure storage file exists
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    async def initialize(self, bot: discord.Bot) -> None:
        """Attach bot instance and rehydrate scheduled tasks from disk."""
        self.bot = bot
        await self._rehydrate()

    async def schedule_language_dropdown(self, guild_id: int, channel_id: int, time_str: str) -> None:
        """Schedule sending the language dropdown message to the channel at HH:MM local time."""
        hm = self._parse_hhmm(time_str)
        if hm is None:
            raise ValueError("Invalid time format; expected HH:MM")
        hour, minute = hm
        run_at = self._compute_next_run(hour, minute).timestamp()
        task = {
            "type": "language_dropdown",
            "guild_id": guild_id,
            "channel_id": channel_id,
            "time": f"{hour:02d}:{minute:02d}",
            "run_at": run_at,
        }
        async with self._lock:
            data = await self._load()
            data.append(task)
            await self._save(data)
        await self._schedule_task(task)

    async def schedule_news_broadcast(self, guild_id: int, time_str: str, payload: Dict[str, Any]) -> None:
        """Schedule sending a multilingual news broadcast at HH:MM local time.

        Payload keys:
        - news_contents: dict of locale -> text (expects 'en' at minimum)
        - embed_json: optional dict for a full embed definition (placeholders supported)
        - send_to_all_users: bool
        - role_id: Optional[int]
        - send_to_all_channels: bool
        - send_ghost_ping: bool
        - image_path: optional path to stored image file
        - image_filename: original image filename
        - image_position: 'Before' or 'After'
        """
        hm = self._parse_hhmm(time_str)
        if hm is None:
            raise ValueError("Invalid time format; expected HH:MM")
        hour, minute = hm
        run_at = self._compute_next_run(hour, minute).timestamp()
        task = {
            "type": "news_broadcast",
            "guild_id": guild_id,
            "time": f"{hour:02d}:{minute:02d}",
            "run_at": run_at,
            "payload": payload or {},
        }
        async with self._lock:
            data = await self._load()
            data.append(task)
            await self._save(data)
        await self._schedule_task(task)

    def _parse_hhmm(self, time_str: str) -> Optional[tuple]:
        try:
            parts = time_str.strip().split(":")
            if len(parts) != 2:
                return None
            hour = int(parts[0])
            minute = int(parts[1])
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return hour, minute
            return None
        except Exception:
            return None

    def _compute_next_run(self, hour: int, minute: int) -> datetime:
        now = datetime.now()
        run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if run <= now:
            run += timedelta(days=1)
        return run

    async def _rehydrate(self) -> None:
        """Load tasks from disk and schedule or execute immediately if missed."""
        async with self._lock:
            data = await self._load()
        now_ts = datetime.now().timestamp()
        for task in data:
            try:
                if float(task.get("run_at", 0)) <= now_ts:
                    # Missed due to downtime; execute immediately
                    await self._execute_task(task)
                    await self._remove_task(task)
                else:
                    await self._schedule_task(task)
            except Exception as e:
                logger.error(f"Failed to rehydrate task {task}: {e}")

    async def _schedule_task(self, task: Dict[str, Any]) -> None:
        run_at = datetime.fromtimestamp(float(task["run_at"]))
        delay = (run_at - datetime.now()).total_seconds()
        if delay < 0:
            delay = 0
        key = self._task_key(task)
        self._scheduled_handles[key] = asyncio.create_task(self._delayed_execute(task, delay))

    async def _delayed_execute(self, task: Dict[str, Any], delay: float) -> None:
        try:
            await asyncio.sleep(delay)
            await self._execute_task(task)
            await self._remove_task(task)
        except Exception as e:
            logger.error(f"Scheduled task failed: {e}")

    async def _execute_task(self, task: Dict[str, Any]) -> None:
        if not self.bot:
            logger.error("Bot is not initialized for scheduler execution.")
            return

        if task.get("type") == "language_dropdown":
            channel_id = int(task["channel_id"])
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception as e:
                    logger.error(f"Failed to fetch channel {channel_id}: {e}")
                    return
            try:
                # Build embed using existing helper by providing a minimal ctx-like object
                class _FakeCtx:
                    def __init__(self, bot: discord.Bot):
                        self.bot = bot
                embed = build_language_selector_embed(_FakeCtx(self.bot))

                await channel.send(embed=embed, view=LanguageSelector())
                logger.info(f"✅ Scheduled language dropdown sent to channel {channel_id}")
            except Exception as e:
                logger.error(f"Error sending scheduled language dropdown to {channel_id}: {e}")
        elif task.get("type") == "news_broadcast":
            payload = task.get("payload", {})
            guild_id = int(task.get("guild_id", 0) or 0)
            guild = self.bot.get_guild(guild_id)
            image_b64 = payload.get("image_b64")
            image_filename = payload.get("image_filename")
            image_path = payload.get("image_path")
            image_position = str(payload.get("image_position") or "Before")
            embed_json = payload.get("embed_json")

            # Helper to choose content for a locale, falling back to English
            def _content_for(locale: str) -> str:
                contents = payload.get("news_contents", {})
                if isinstance(contents, dict):
                    return contents.get(locale) or contents.get("en") or ""
                return str(contents)

            # Helper to build an embed from raw JSON or default structure
            def _build_embed(content_text: str, include_image: bool) -> discord.Embed:
                # Prepare common replacements
                bot_user = getattr(self.bot, "user", None)
                bot_avatar = ""
                if bot_user:
                    if bot_user.avatar:
                        bot_avatar = bot_user.avatar.url
                    else:
                        bot_avatar = bot_user.default_avatar.url

                image_url = ""
                if include_image and image_filename:
                    image_url = f"attachment://{image_filename}"

                replacements = {
                    "{content}": content_text,
                    "content": content_text,
                    "{bot_avatar}": bot_avatar,
                    "bot_avatar": bot_avatar,
                    "{image_url}": image_url,
                    "image_url": image_url,
                }

                # Prefer explicit embed JSON from payload
                if embed_json and isinstance(embed_json, dict):
                    try:
                        processed = replace_placeholders(embed_json, replacements)
                        if getattr(constants, "NEWS_DEFAULT_FOOTER", False):
                            processed["footer"] = {
                                "text": constants.DISCORD_MESSAGE_TRADEMARK,
                                "icon_url": bot_avatar,
                            }
                        return build_embed_from_data(processed)
                    except Exception:
                        return None

                # Fallback: build a simple default embed
                try:
                    default_data = {
                        "description": content_text,
                    }
                    if image_url:
                        default_data["image"] = {"url": image_url}
                    if getattr(constants, "NEWS_DEFAULT_FOOTER", False):
                        default_data["footer"] = {
                            "text": constants.DISCORD_MESSAGE_TRADEMARK,
                            "icon_url": bot_avatar,
                        }
                    return build_embed_from_data(default_data)
                except Exception:
                    return None

            def _make_image_file():
                # Prefer disk file for storage efficiency; fallback to b64
                if image_path and os.path.exists(image_path):
                    try:
                        with open(image_path, "rb") as f:
                            img_bytes = f.read()
                        return discord.File(fp=io.BytesIO(img_bytes), filename=image_filename or os.path.basename(image_path))
                    except Exception:
                        pass
                if image_b64 and image_filename:
                    try:
                        img_bytes = base64.b64decode(image_b64)
                        return discord.File(fp=io.BytesIO(img_bytes), filename=image_filename)
                    except Exception:
                        return None
                return None

            send_to_all_channels = bool(payload.get("send_to_all_channels", True))
            send_to_all_users = bool(payload.get("send_to_all_users", True))
            role_id = payload.get("role_id")
            send_ghost_ping = bool(payload.get("send_ghost_ping", True))

            success_count = 0
            fail_count = 0

            # Send to configured language-specific channels
            if send_to_all_channels:
                channels_to_send = [
                    (getattr(constants, "NEWS_ENGLISH_CHANNEL_ID", None), "en"),
                    (getattr(constants, "NEWS_RUSSIAN_CHANNEL_ID", None), "ru"),
                    (getattr(constants, "NEWS_LITHUANIAN_CHANNEL_ID", None), "lt"),
                ]
                for channel_id, locale in channels_to_send:
                    if not channel_id:
                        continue
                    channel = self.bot.get_channel(int(channel_id))
                    if channel is None:
                        try:
                            channel = await self.bot.fetch_channel(int(channel_id))
                        except Exception as e:
                            logger.error(f"Failed to fetch channel {channel_id}: {e}")
                            fail_count += 1
                            continue
                    try:
                        # Build embed and send; image is always a separate message
                        embed = _build_embed(_content_for(locale), include_image=False)
                        image_file = _make_image_file()

                        if embed:
                            # Send image separately before the embed if requested
                            if image_file and image_position == "Before":
                                await channel.send(file=image_file)
                            await channel.send(embed=embed)
                            # Or send image after the embed if requested
                            if image_file and image_position == "After":
                                await channel.send(file=image_file)
                        else:
                            # Fallback to plain text if embed fails
                            if image_file and image_position == "Before":
                                await channel.send(file=image_file)
                            await channel.send(_content_for(locale))
                            if image_file and image_position == "After":
                                await channel.send(file=image_file)
                        if send_ghost_ping and locale == "en":
                            ping_msg = await channel.send("@everyone")
                            try:
                                await ping_msg.delete()
                            except Exception:
                                pass
                        success_count += 1
                        await asyncio.sleep(1)
                    except Exception as e:
                        logger.error(f"Failed to send scheduled news to channel {channel.id}: {e}")
                        fail_count += 1

            # Send to users (DMs)
            if send_to_all_users and guild:
                members = []
                if role_id:
                    role = discord.utils.get(guild.roles, id=int(role_id))
                    if role:
                        members.extend(role.members)
                else:
                    members.extend(guild.members)

                unique_members = {m.id: m for m in members if not m.bot}
                for member in unique_members.values():
                    try:
                        member_lang = await get_language(member.id)
                        # Build embed and send via DM; image is always a separate message
                        embed = _build_embed(_content_for(member_lang), include_image=False)
                        image_file = _make_image_file()

                        if embed:
                            # Send image separately before the embed if requested
                            if image_file and image_position == "Before":
                                await member.send(file=image_file)
                            await member.send(embed=embed)
                            # Or send image after the embed if requested
                            if image_file and image_position == "After":
                                await member.send(file=image_file)
                        else:
                            # Fallback to plain text
                            if image_file and image_position == "Before":
                                await member.send(file=image_file)
                            await member.send(_content_for(member_lang))
                            if image_file and image_position == "After":
                                await member.send(file=image_file)
                        success_count += 1
                        await asyncio.sleep(1)
                    except discord.Forbidden:
                        fail_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send scheduled news to user {member.id}: {e}")
                        fail_count += 1

            logger.info(
                f"✅ Scheduled news broadcast executed for guild {guild_id}: {success_count} sent, {fail_count} failed"
            )

            # Cleanup stored image file after use
            if image_path and os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception:
                    pass

    async def _remove_task(self, task: Dict[str, Any]) -> None:
        key = self._task_key(task)
        handle = self._scheduled_handles.pop(key, None)
        if handle and not handle.done():
            handle.cancel()
        async with self._lock:
            data = await self._load()
            data = [t for t in data if self._task_key(t) != key]
            await self._save(data)

    def _task_key(self, task: Dict[str, Any]) -> str:
        # Use channel_id when available (e.g., language_dropdown), otherwise guild_id for broader tasks
        target_id = task.get('channel_id') or task.get('guild_id') or 'global'
        return f"{task.get('type')}:{target_id}:{task.get('run_at')}"

    async def _load(self) -> List[Dict[str, Any]]:
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    async def _save(self, data: List[Dict[str, Any]]) -> None:
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# Singleton accessor
_scheduler: Optional[Scheduler] = None


def get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler