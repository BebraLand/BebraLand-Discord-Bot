import os
import json
import asyncio
import re
from datetime import datetime
from typing import Dict, Any, Optional, List

import discord
import base64
import io
import config.constants as constants
import src.languages.lang_constants as lang_constants
from src.utils.database import get_language, get_manager

from src.utils.logger import get_cool_logger
from src.views.language_selector import LanguageSelector
from src.views.language_selector import build_language_selector_embed
from src.utils.embeds import build_embed_from_data, build_news_placeholders, replace_placeholders, get_embed_icon


logger = get_cool_logger(__name__)

TASK_LANGUAGE_DROPDOWN = "language_dropdown"
TASK_NEWS_BROADCAST = "news_broadcast"
TASK_TWITCH_PANEL = "twitch_panel"


def normalize_unix_timestamp(value: Any, require_future: bool = True) -> int:
    """
    Normalize Unix timestamp input to seconds.
    Supports:
    - seconds (10-digit)
    - milliseconds (13-digit)
    - microseconds (16-digit)
    - nanoseconds (19-digit)
    - Discord timestamp tag format: <t:1777217700:F>
    """
    raw = str(value).strip()
    if not raw:
        raise ValueError("Invalid time format; expected Unix timestamp")

    # Accept Discord timestamp tag input.
    if raw.startswith("<t:"):
        match = re.match(r"^<t:(\d+)(?::[tTdDfFR])?>$", raw)
        if not match:
            raise ValueError("Invalid time format; expected Unix timestamp")
        raw = match.group(1)

    try:
        timestamp = float(raw)
    except Exception:
        raise ValueError("Invalid time format; expected Unix timestamp")

    abs_ts = abs(timestamp)
    if abs_ts >= 1_000_000_000_000_000_000:
        timestamp = timestamp / 1_000_000_000
    elif abs_ts >= 1_000_000_000_000_000:
        timestamp = timestamp / 1_000_000
    elif abs_ts >= 1_000_000_000_000:
        timestamp = timestamp / 1_000

    normalized = int(timestamp)
    if normalized <= 0:
        raise ValueError("Unix timestamp must be greater than 0")

    if require_future and normalized <= int(datetime.now().timestamp()):
        raise ValueError("Unix timestamp must be in the future")

    return normalized


class Scheduler:
    """
    Simple persistent scheduler for one-off tasks.
    - Validates Unix timestamp format strictly
    - Persists tasks to database (uses same backend as language storage) to survive bot restarts
    - Schedules execution using asyncio
    """

    def __init__(self) -> None:
        self.bot: Optional[discord.Bot] = None
        self.storage = None  # Will be set from language manager
        self._scheduled_handles: Dict[int, asyncio.Task] = {}  # Key is now task ID

    async def initialize(self, bot: discord.Bot) -> None:
        """Attach bot instance, get storage from language manager, migrate if needed, and rehydrate tasks."""
        self.bot = bot
        
        # Get storage from the language manager (shares same DB connection)
        manager = await get_manager()
        self.storage = manager.storage

        # Check for migration from old JSON file
        json_path = "data/scheduled_tasks.json"
        if os.path.exists(json_path):
            await self._migrate_from_json(json_path)

        await self._rehydrate()

    async def _migrate_from_json(self, json_path: str) -> None:
        """Migrate tasks from JSON to DB and rename JSON file."""
        logger.info(f"Migrating tasks from {json_path} to database...")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            count = 0
            for task in data:
                # Insert into DB
                await self._add_task_to_db(task)
                count += 1
            
            # Rename file to indicate backup
            os.rename(json_path, json_path + ".bak")
            logger.info(f"Successfully migrated {count} tasks. Renamed {json_path} to {json_path}.bak")
        except Exception as e:
            logger.error(f"Failed to migrate tasks from JSON: {e}")

    async def schedule_language_dropdown(self, guild_id: int, channel_id: int, run_at_unix: Any) -> None:
        """Schedule sending the language dropdown message to the channel at Unix timestamp."""
        await self._schedule_one_off_task(
            task_type=TASK_LANGUAGE_DROPDOWN,
            guild_id=guild_id,
            run_at_unix=run_at_unix,
            channel_id=channel_id,
            payload={},
        )

    async def schedule_news_broadcast(self, guild_id: int, run_at_unix: Any, payload: Dict[str, Any]) -> None:
        """Schedule sending a multilingual news broadcast at Unix timestamp."""
        await self._schedule_one_off_task(
            task_type=TASK_NEWS_BROADCAST,
            guild_id=guild_id,
            run_at_unix=run_at_unix,
            payload=payload or {},
        )

    async def schedule_twitch_panel(self, guild_id: int, run_at_unix: Any, payload: Dict[str, Any]) -> None:
        """Schedule sending the Twitch panel at Unix timestamp."""
        await self._schedule_one_off_task(
            task_type=TASK_TWITCH_PANEL,
            guild_id=guild_id,
            run_at_unix=run_at_unix,
            payload=payload or {},
        )

    async def _schedule_one_off_task(
        self,
        task_type: str,
        guild_id: int,
        run_at_unix: Any,
        payload: Optional[Dict[str, Any]] = None,
        channel_id: Optional[int] = None,
    ) -> None:
        run_at = self._parse_unix_timestamp(run_at_unix)
        task = {
            "type": task_type,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "time": str(run_at),
            "run_at": run_at,
            "payload": payload or {},
        }

        task_id = await self._add_task_to_db(task)
        if task_id:
            task["id"] = task_id
            await self._schedule_task(task)

    def _parse_unix_timestamp(self, value: Any) -> float:
        try:
            return float(normalize_unix_timestamp(value, require_future=True))
        except Exception:
            raise ValueError("Invalid time format; expected Unix timestamp")

    async def _rehydrate(self) -> None:
        """Load tasks from DB and schedule or execute immediately if missed."""
        tasks = await self._get_all_tasks_from_db()
        now_ts = datetime.now().timestamp()
        
        for task in tasks:
            try:
                if float(task.get("run_at", 0)) <= now_ts:
                    # Missed due to downtime; execute immediately
                    await self._execute_task(task)
                    await self._remove_task_from_db(task.get("id"))
                else:
                    await self._schedule_task(task)
            except Exception as e:
                logger.error(f"Failed to rehydrate task {task}: {e}")

    async def _schedule_task(self, task: Dict[str, Any]) -> None:
        run_at = datetime.fromtimestamp(float(task["run_at"]))
        delay = (run_at - datetime.now()).total_seconds()
        if delay < 0:
            delay = 0
        
        task_id = task.get("id")
        if task_id is None:
            logger.error(f"Cannot schedule task without ID: {task}")
            return

        # Cancel existing if any (shouldn't happen with new ID logic but good safety)
        if task_id in self._scheduled_handles:
            self._scheduled_handles[task_id].cancel()

        self._scheduled_handles[task_id] = asyncio.create_task(self._delayed_execute(task, delay))

    async def _delayed_execute(self, task: Dict[str, Any], delay: float) -> None:
        task_id = task.get("id")
        try:
            await asyncio.sleep(delay)
            await self._execute_task(task)
            await self._remove_task_from_db(task_id)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Scheduled task failed: {e}")
        finally:
            current_handle = self._scheduled_handles.get(task_id)
            if current_handle is asyncio.current_task():
                self._scheduled_handles.pop(task_id, None)

    async def _execute_task(self, task: Dict[str, Any]) -> None:
        if not self.bot:
            logger.error("Bot is not initialized for scheduler execution.")
            return

        task_type = task.get("type")
        if task_type == TASK_LANGUAGE_DROPDOWN:
            await self._execute_language_dropdown_task(task)
        elif task_type == TASK_NEWS_BROADCAST:
            await self._execute_news_broadcast_task(task)
        elif task_type == TASK_TWITCH_PANEL:
            await self._execute_twitch_panel_task(task)
        else:
            logger.warning(f"Unknown scheduled task type: {task_type}")

    async def _get_channel(self, channel_id: int) -> Optional[discord.abc.GuildChannel]:
        if not self.bot:
            return None
        channel = self.bot.get_channel(channel_id)
        if channel is not None:
            return channel
        try:
            return await self.bot.fetch_channel(channel_id)
        except Exception as e:
            logger.error(f"Failed to fetch channel {channel_id}: {e}")
            return None

    async def _execute_language_dropdown_task(self, task: Dict[str, Any]) -> None:
        channel_id = int(task["channel_id"])
        channel = await self._get_channel(channel_id)
        if channel is None:
            return
        try:
            class _FakeCtx:
                def __init__(self, bot: discord.Bot):
                    self.bot = bot

            embed = build_language_selector_embed(_FakeCtx(self.bot))
            await channel.send(embed=embed, view=LanguageSelector())
            logger.info(f"{lang_constants.SUCCESS_EMOJI} Scheduled language dropdown sent to channel {channel_id}")
        except Exception as e:
            logger.error(f"Error sending scheduled language dropdown to {channel_id}: {e}")

    def _normalize_locale(self, locale: str) -> str:
        try:
            return str(locale).split('-')[0].split('_')[0].lower()
        except Exception:
            return str(locale).lower() if locale else ""

    def _news_content_for(self, payload: Dict[str, Any], locale: str) -> str:
        contents = payload.get("news_contents", {})
        if not isinstance(contents, dict):
            return str(contents)

        locale_short = self._normalize_locale(locale)
        val = contents.get(locale) or contents.get(locale_short) or contents.get("en") or ""
        if isinstance(val, dict):
            try:
                return val.get("description") or ""
            except Exception:
                return ""
        return str(val)

    def _news_embed_source_for_locale(self, payload: Dict[str, Any], locale: str) -> Optional[Dict[str, Any]]:
        contents = payload.get("news_contents", {})
        if not isinstance(contents, dict) or not locale:
            return None

        candidate = contents.get(locale) or contents.get(self._normalize_locale(locale))
        if isinstance(candidate, str):
            trimmed = candidate.strip()
            if trimmed.startswith("{") and trimmed.endswith("}"):
                try:
                    parsed_candidate = json.loads(trimmed)
                    if isinstance(parsed_candidate, dict):
                        candidate = parsed_candidate
                except Exception:
                    return None
        if isinstance(candidate, dict):
            return candidate
        return None

    def _build_news_embed(self, payload: Dict[str, Any], content_text: str, locale: str = None) -> Optional[discord.Embed]:
        if not self.bot:
            return None

        bot_user = getattr(self.bot, "user", None)
        bot_avatar = ""
        if bot_user:
            if bot_user.avatar:
                bot_avatar = bot_user.avatar.url
            else:
                bot_avatar = bot_user.default_avatar.url

        image_filename = payload.get("image_filename")
        image_url = f"attachment://{image_filename}" if image_filename else ""
        replacements = build_news_placeholders(content_text, bot_avatar, image_url)

        locale_embed = self._news_embed_source_for_locale(payload, locale)
        embed_json = payload.get("embed_json")
        embed_source = locale_embed if locale_embed is not None else (embed_json if isinstance(embed_json, dict) else None)

        if embed_source and isinstance(embed_source, dict):
            try:
                processed = replace_placeholders(embed_source, replacements)
                if getattr(constants, "NEWS_DEFAULT_FOOTER", False):
                    processed["footer"] = {
                        "text": constants.DISCORD_MESSAGE_TRADEMARK,
                        "icon_url": get_embed_icon(self.bot),
                    }
                return build_embed_from_data(processed)
            except Exception:
                return None

        try:
            default_data = {
                "description": content_text,
            }
            if image_url:
                default_data["image"] = {"url": image_url}
            if getattr(constants, "NEWS_DEFAULT_FOOTER", False):
                default_data["footer"] = {
                    "text": constants.DISCORD_MESSAGE_TRADEMARK,
                    "icon_url": get_embed_icon(self.bot),
                }
            return build_embed_from_data(default_data)
        except Exception:
            return None

    def _make_news_image_file(self, payload: Dict[str, Any]) -> Optional[discord.File]:
        image_b64 = payload.get("image_b64")
        image_filename = payload.get("image_filename")
        image_path = payload.get("image_path")

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

    async def _send_news_message(
        self,
        target: Any,
        payload: Dict[str, Any],
        locale: str,
    ) -> None:
        image_position = str(payload.get("image_position") or "Before")
        content = self._news_content_for(payload, locale)
        embed = self._build_news_embed(payload, content, locale=locale)
        image_file = self._make_news_image_file(payload)

        if embed:
            if image_file and image_position == "Before":
                await target.send(file=image_file)
            await target.send(embed=embed)
            if image_file and image_position == "After":
                await target.send(file=image_file)
        else:
            if image_file and image_position == "Before":
                await target.send(file=image_file)
            await target.send(content)
            if image_file and image_position == "After":
                await target.send(file=image_file)

    async def _execute_news_broadcast_task(self, task: Dict[str, Any]) -> None:
        if not self.bot:
            return

        payload = task.get("payload", {})
        guild_id = int(task.get("guild_id", 0) or 0)
        guild = self.bot.get_guild(guild_id)

        send_to_all_channels = bool(payload.get("send_to_all_channels", True))
        send_to_all_users = bool(payload.get("send_to_all_users", True))
        role_id = payload.get("role_id")
        send_ghost_ping = bool(payload.get("send_ghost_ping", True))

        success_count = 0
        fail_count = 0

        if send_to_all_channels:
            channels_to_send = [
                (getattr(constants, "NEWS_ENGLISH_CHANNEL_ID", None), "en"),
                (getattr(constants, "NEWS_RUSSIAN_CHANNEL_ID", None), "ru"),
                (getattr(constants, "NEWS_LITHUANIAN_CHANNEL_ID", None), "lt"),
            ]
            for channel_id, locale in channels_to_send:
                if not channel_id:
                    continue

                channel = await self._get_channel(int(channel_id))
                if channel is None:
                    fail_count += 1
                    continue

                try:
                    await self._send_news_message(channel, payload, locale)
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
                    await self._send_news_message(member, payload, member_lang)
                    success_count += 1
                    await asyncio.sleep(1)
                except discord.Forbidden:
                    fail_count += 1
                except Exception as e:
                    logger.error(f"Failed to send scheduled news to user {member.id}: {e}")
                    fail_count += 1

        logger.info(
            f"{lang_constants.SUCCESS_EMOJI} Scheduled news broadcast executed for guild {guild_id}: {success_count} sent, {fail_count} failed"
        )

        image_path = payload.get("image_path")
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass

    async def _execute_twitch_panel_task(self, task: Dict[str, Any]) -> None:
        payload = task.get("payload", {})
        channel_id = int(payload.get("channel_id", 0))

        if not channel_id:
            logger.error("Scheduled twitch_panel task has no channel_id")
            return

        channel = await self._get_channel(channel_id)
        if channel is None:
            return

        try:
            from src.features.twitch.view.TwitchPanel import build_twitch_panel_embed, TwitchPanel

            class _FakeCtx:
                def __init__(self, bot: discord.Bot):
                    self.bot = bot

            embed = build_twitch_panel_embed(_FakeCtx(self.bot))
            await channel.send(embed=embed, view=TwitchPanel())
            logger.info(f"{lang_constants.SUCCESS_EMOJI} Scheduled Twitch panel sent to channel {channel_id}")
        except Exception as e:
            logger.error(f"Error sending scheduled Twitch panel to {channel_id}: {e}")

    # --- Database Helpers ---

    async def _add_task_to_db(self, task: Dict[str, Any]) -> Optional[int]:
        """Insert task into DB and return its new ID."""
        if not self.storage:
            logger.error("Storage not initialized")
            return None
        return await self.storage.add_scheduled_task(task)

    async def _remove_task_from_db(self, task_id: int) -> None:
        """Remove task from DB by ID."""
        if not self.storage:
            logger.error("Storage not initialized")
            return
        await self.storage.remove_scheduled_task(task_id)

    async def _get_all_tasks_from_db(self) -> List[Dict[str, Any]]:
        """Retrieve all tasks from DB."""
        if not self.storage:
            logger.error("Storage not initialized")
            return []
        return await self.storage.get_all_scheduled_tasks()


# Singleton accessor
_scheduler: Optional[Scheduler] = None


def get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler