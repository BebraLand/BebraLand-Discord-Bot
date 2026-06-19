import asyncio
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import ui

from config.config import config as bot_config
from src.languages import lang_constants
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger
from src.utils.news_sender import preview_news, scheduled_send_news_task, send_news
from src.utils.schedule_utils import parse_human_schedule_time
from src.utils.scheduler import scheduler

logger = get_cool_logger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_IMAGE_BYTES = 25 * 1024 * 1024
JSON_EXTENSIONS = {".json"}
MAX_JSON_BYTES = 1024 * 1024

NEWS_LOCALES = ("en", "ru", "lt")


def _locale_from_json_filename(filename: str | None) -> Optional[str]:
    """Return locale encoded as a standalone token in a JSON filename."""
    stem, extension = os.path.splitext(filename or "")
    if extension.lower() not in JSON_EXTENSIONS:
        return None

    matches = [
        locale
        for locale in NEWS_LOCALES
        if re.search(rf"(?:^|[^a-z]){locale}(?:$|[^a-z])", stem.lower())
    ]
    return matches[0] if len(matches) == 1 else None


def _modal_value(value) -> str:
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2)
    if isinstance(value, str):
        return value
    return ""


def _make_optional_input(**kwargs) -> ui.InputText:
    item = ui.InputText(required=False, **kwargs)
    # Pycord 2.7 serializes required=False as None unless forced here.
    item._underlying.required = False
    return item


class NewsWizardImage:
    def __init__(self, filename: str, data: bytes):
        self.filename = filename
        self._data = data

    async def read(self) -> bytes:
        return self._data


class NewsWizardContentModal(ui.Modal):
    def __init__(self, view: "NewsWizardView"):
        super().__init__(title="News content")
        self.wizard_view = view
        limit = bot_config.modules.news.character_limit
        self.add_item(
            ui.InputText(
                label="English content",
                placeholder="Required. Plain text or embed JSON.",
                style=discord.InputTextStyle.long,
                required=True,
                max_length=limit,
                value=_modal_value(view.news_contents.get("en")),
            )
        )
        self.add_item(
            _make_optional_input(
                label="Russian content",
                placeholder="Optional. Falls back to English.",
                style=discord.InputTextStyle.long,
                max_length=limit,
                value=_modal_value(view.news_contents.get("ru")),
            )
        )
        self.add_item(
            _make_optional_input(
                label="Lithuanian content",
                placeholder="Optional. Falls back to English.",
                style=discord.InputTextStyle.long,
                max_length=limit,
                value=_modal_value(view.news_contents.get("lt")),
            )
        )

    async def callback(self, interaction: discord.Interaction):
        en_val = (self.children[0].value or "").strip()
        ru_val = (self.children[1].value or "").strip()
        lt_val = (self.children[2].value or "").strip()

        self.wizard_view.embed_json = None
        self.wizard_view.news_contents = {}
        self.wizard_view.preview_seen = False

        def store_locale(locale: str, value: str) -> None:
            if not value:
                return
            if value.startswith("{") and value.endswith("}"):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, dict):
                        self.wizard_view.news_contents[locale] = parsed
                        return
                except Exception:
                    pass
            self.wizard_view.news_contents[locale] = value

        store_locale("en", en_val)
        store_locale("ru", ru_val)
        store_locale("lt", lt_val)

        en_content = self.wizard_view.news_contents.get("en")
        if isinstance(en_content, dict):
            self.wizard_view.embed_json = en_content
        elif en_val.startswith("{") and en_val.endswith("}"):
            try:
                parsed = json.loads(en_val)
                if isinstance(parsed, dict):
                    self.wizard_view.embed_json = parsed
            except Exception:
                pass

        self.wizard_view._log_action("content_saved")
        await interaction.response.edit_message(
            embed=self.wizard_view.build_embed(interaction),
            view=self.wizard_view,
        )


class NewsWizardScheduleModal(ui.Modal):
    def __init__(self, view: "NewsWizardView"):
        super().__init__(title="Schedule news")
        self.wizard_view = view
        self.add_item(
            ui.InputText(
                label="Send time",
                placeholder="now, in 30m, in 2h, today 20:00, tomorrow 18:30",
                required=True,
                max_length=80,
                value=view.schedule_text or "",
            )
        )

    async def callback(self, interaction: discord.Interaction):
        schedule_text = (self.children[0].value or "").strip()
        try:
            schedule_unix = parse_human_schedule_time(schedule_text)
        except ValueError as e:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} {e}",
                ephemeral=True,
            )
            return

        self.wizard_view.schedule_text = schedule_text
        self.wizard_view.schedule_unix = schedule_unix
        self.wizard_view.preview_seen = False
        self.wizard_view._log_action("schedule_set", schedule_text=schedule_text)
        await interaction.response.edit_message(
            embed=self.wizard_view.build_embed(interaction),
            view=self.wizard_view,
        )


class NewsWizardView(ui.View):
    def __init__(
        self,
        bot: discord.Bot,
        ctx: discord.ApplicationContext,
        user_lang: str,
        image: Optional[discord.Attachment] = None,
    ):
        super().__init__(timeout=900)
        self.bot = bot
        self.ctx = ctx
        self.owner_id = ctx.user.id
        self.user_lang = user_lang
        self.image = image
        self.news_contents: dict = {}
        self.embed_json: Optional[dict] = None
        self.send_to_all_users = False
        self.send_to_all_channels = True
        self.roles: list[discord.Role] = []
        self.send_ghost_ping = True
        self.image_position = "Before"
        self.schedule_text: Optional[str] = None
        self.schedule_unix: Optional[int] = None
        self.preview_seen = False
        self.completed = False
        self.panel_message: Optional[discord.Message] = None
        self.role_select_open = False

        self.role_select = ui.RoleSelect(
            placeholder="Click Role, then choose role target",
            min_values=1,
            max_values=5,
            row=4,
        )
        self.role_select.callback = self._role_select_callback
        self.add_item(self.role_select)

    async def _role_select_callback(self, interaction: discord.Interaction):
        self._remember_panel(interaction)
        roles = list(self.role_select.values or [])
        if not roles:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Role not found.",
                ephemeral=True,
            )
            return

        self.send_to_all_users = False
        self.roles = roles[:5]
        self.role_select_open = False
        self.preview_seen = False
        self._log_action(
            "roles_selected",
            role_ids=",".join(str(role.id) for role in self.roles),
        )
        await interaction.response.edit_message(
            embed=self.build_embed(interaction),
            view=self,
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            f"{lang_constants.ERROR_EMOJI} This news wizard belongs to another admin.",
            ephemeral=True,
        )
        return False

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    def _remember_panel(self, interaction: discord.Interaction) -> None:
        if interaction.message:
            self.panel_message = interaction.message

    def _targets_summary(self) -> str:
        targets = []
        if self.send_to_all_channels:
            targets.append("channels")
        if self.send_to_all_users:
            targets.append("all_users")
        if self.roles:
            targets.append("roles=" + ",".join(str(role.id) for role in self.roles))
        return ";".join(targets) if targets else "none"

    def _log_action(self, action: str, **extra) -> None:
        details = {
            "user_id": self.owner_id,
            "guild_id": getattr(self.ctx.guild, "id", None),
            "targets": self._targets_summary(),
            "locales": ",".join(self.news_contents.keys()) or "none",
            "has_embed_json": bool(self.embed_json),
            "has_image": bool(self.image),
            "image_position": self.image_position,
            "ghost_ping": self.send_ghost_ping,
            "schedule_unix": self.schedule_unix,
            "preview_seen": self.preview_seen,
        }
        details.update(extra)
        logger.info(
            "news_wizard.%s %s",
            action,
            " ".join(f"{key}={value}" for key, value in details.items()),
        )

    def _sync_button_state(self) -> None:
        if self.completed:
            for item in self.children:
                item.disabled = True
            return

        has_content = self._has_content()
        has_target = bool(
            self.send_to_all_channels or self.send_to_all_users or self.roles
        )

        for item in self.children:
            if item is self.role_select:
                item.disabled = not self.role_select_open
                if self.roles:
                    role_names = ", ".join(role.name for role in self.roles[:3])
                    if len(self.roles) > 3:
                        role_names += f" +{len(self.roles) - 3}"
                    item.placeholder = f"Selected roles: {role_names}"
                elif self.role_select_open:
                    item.placeholder = "Choose role target"
                else:
                    item.placeholder = "Click Role, then choose role target"
                continue

            if not isinstance(item, ui.Button):
                continue
            if item.label == "Channels":
                item.style = (
                    discord.ButtonStyle.success
                    if self.send_to_all_channels
                    else discord.ButtonStyle.secondary
                )
            elif item.label == "Users":
                item.style = (
                    discord.ButtonStyle.success
                    if self.send_to_all_users
                    else discord.ButtonStyle.secondary
                )
            elif item.label == "Role":
                item.style = (
                    discord.ButtonStyle.success
                    if self.roles
                    else discord.ButtonStyle.secondary
                )
            elif item.label == "Ghost ping":
                item.style = (
                    discord.ButtonStyle.success
                    if self.send_ghost_ping
                    else discord.ButtonStyle.secondary
                )
            elif item.label == "Preview":
                item.disabled = not (has_content and has_target)
            elif item.label == "Send":
                item.disabled = not (has_content and has_target and self.preview_seen)
            elif item.label == "Remove image":
                item.disabled = self.image is None
            elif item.label == "Clear role":
                item.disabled = not self.roles
            elif item.label == "Clear schedule":
                item.disabled = self.schedule_unix is None

    def build_embed(self, source) -> discord.Embed:
        self._sync_button_state()
        content_locales = [
            key.upper() for key in ("en", "ru", "lt") if self.news_contents.get(key)
        ]
        targets = []
        if self.send_to_all_channels:
            targets.append("news channels")
        if self.send_to_all_users:
            targets.append("all users")
        if self.roles:
            targets.append("roles " + ", ".join(role.mention for role in self.roles))

        embed = discord.Embed(
            title="News wizard",
            description=(
                "Set content and targets, preview, then send."
                if not self.completed
                else "This wizard is complete."
            ),
            color=bot_config.embeds.info_color,
        )
        embed.add_field(
            name="Content",
            value=", ".join(content_locales) if content_locales else "Missing",
            inline=True,
        )
        embed.add_field(
            name="Targets",
            value=", ".join(targets) if targets else "None",
            inline=True,
        )
        embed.add_field(
            name="Image",
            value=(
                f"{self.image.filename} ({self.image_position})"
                if self.image
                else "None"
            ),
            inline=True,
        )
        embed.add_field(
            name="Preview",
            value="Ready to send" if self.preview_seen else "Required before send",
            inline=True,
        )
        embed.add_field(
            name="Ghost ping",
            value=str(self.send_ghost_ping),
            inline=True,
        )
        embed.add_field(
            name="Schedule",
            value=f"<t:{self.schedule_unix}:F> (<t:{self.schedule_unix}:R>)"
            if self.schedule_unix
            else "Now",
            inline=True,
        )
        embed.set_footer(
            text=bot_config.bot.trademark,
            icon_url=get_embed_icon(source),
        )
        return embed

    def _has_content(self) -> bool:
        return bool(self.news_contents.get("en") or self.embed_json)

    async def _set_content_from_json_attachment(
        self,
        attachment: discord.Attachment,
        locale: str = "en",
        replace_existing: bool = True,
    ) -> Optional[str]:
        filename = attachment.filename or "news.json"
        lower_name = filename.lower()
        if not any(lower_name.endswith(ext) for ext in JSON_EXTENSIONS):
            return f"{locale.upper()} attachment must be a .json file."

        size = getattr(attachment, "size", 0) or 0
        if size > MAX_JSON_BYTES:
            return f"{locale.upper()} JSON file is too large. Max size is 1 MB."

        try:
            raw = await attachment.read()
        except Exception as e:
            logger.error(f"Failed to read news wizard JSON: {e}")
            return f"Could not read {locale.upper()} JSON attachment."

        if not raw:
            return f"{locale.upper()} JSON attachment was empty."
        if len(raw) > MAX_JSON_BYTES:
            return f"{locale.upper()} JSON file is too large. Max size is 1 MB."

        try:
            parsed = json.loads(raw.decode("utf-8-sig"))
        except UnicodeDecodeError:
            return f"{locale.upper()} JSON file must be UTF-8 encoded."
        except json.JSONDecodeError as e:
            return f"Invalid {locale.upper()} JSON: {e.msg} at line {e.lineno}, column {e.colno}."

        if not isinstance(parsed, dict):
            return f"{locale.upper()} JSON root must be an object."

        if replace_existing:
            self.news_contents = {}
            self.embed_json = None
        self.news_contents[locale] = parsed
        if locale == "en":
            self.embed_json = parsed
        self.preview_seen = False
        return None

    async def _set_image_from_attachment(
        self, attachment: discord.Attachment
    ) -> Optional[str]:
        filename = attachment.filename or "news-image"
        lower_name = filename.lower()
        content_type = (getattr(attachment, "content_type", "") or "").lower()
        looks_like_image = content_type.startswith("image/") or any(
            lower_name.endswith(ext) for ext in IMAGE_EXTENSIONS
        )
        if not looks_like_image:
            return "Attachment must be an image file."

        size = getattr(attachment, "size", 0) or 0
        if size > MAX_IMAGE_BYTES:
            return "Image is too large. Max size is 25 MB."

        try:
            image_bytes = await attachment.read()
        except Exception as e:
            logger.error(f"Failed to read news wizard image: {e}")
            return "Could not read image attachment."

        if not image_bytes:
            return "Image attachment was empty."
        if len(image_bytes) > MAX_IMAGE_BYTES:
            return "Image is too large. Max size is 25 MB."

        self.image = NewsWizardImage(filename, image_bytes)
        self.preview_seen = False
        return None

    async def _save_scheduled_image(self, payload: dict) -> None:
        if not self.image:
            return
        try:
            image_bytes = await self.image.read()
            if not image_bytes:
                return
            os.makedirs("data/scheduled_files", exist_ok=True)
            unique_name = f"{uuid.uuid4()}_{self.image.filename}"
            image_path = os.path.join("data", "scheduled_files", unique_name)
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            payload["image_path"] = image_path
            payload["image_filename"] = self.image.filename
        except Exception as e:
            logger.error(f"Failed to save scheduled news image: {e}")

    async def _send_error(self, interaction: discord.Interaction, message: str):
        await interaction.followup.send(
            f"{lang_constants.ERROR_EMOJI} {message}",
            ephemeral=True,
        )

    async def _refresh_panel(self, interaction: discord.Interaction):
        panel_id = getattr(self.panel_message, "id", None)
        if self.panel_message:
            try:
                await self.panel_message.edit(
                    embed=self.build_embed(interaction),
                    view=self,
                )
                self._log_action(
                    "panel_refreshed", method="panel_message", message_id=panel_id
                )
                return
            except (discord.NotFound, discord.HTTPException) as e:
                logger.warning(
                    "news_wizard.panel_refresh_failed method=panel_message "
                    "user_id=%s guild_id=%s message_id=%s error_type=%s status=%s code=%s text=%s",
                    self.owner_id,
                    getattr(self.ctx.guild, "id", None),
                    panel_id,
                    type(e).__name__,
                    getattr(e, "status", None),
                    getattr(e, "code", None),
                    getattr(e, "text", str(e)),
                )
                self.panel_message = None

        try:
            await interaction.edit_original_response(
                embed=self.build_embed(interaction),
                view=self,
            )
            self._log_action("panel_refreshed", method="interaction_original")
            return
        except (discord.NotFound, discord.HTTPException) as e:
            logger.warning(
                "news_wizard.panel_refresh_failed method=interaction_original "
                "user_id=%s guild_id=%s interaction_id=%s error_type=%s status=%s code=%s text=%s",
                self.owner_id,
                getattr(self.ctx.guild, "id", None),
                getattr(interaction, "id", None),
                type(e).__name__,
                getattr(e, "status", None),
                getattr(e, "code", None),
                getattr(e, "text", str(e)),
            )

        await interaction.followup.send(
            f"{lang_constants.ERROR_EMOJI} News panel expired. Run `/admin news` again.",
            ephemeral=True,
        )
        self._log_action("panel_refresh_gave_up")

    @ui.button(label="Content", style=discord.ButtonStyle.primary, row=0)
    async def content_button(self, button: ui.Button, interaction: discord.Interaction):
        self._remember_panel(interaction)
        await interaction.response.send_modal(NewsWizardContentModal(self))

    @ui.button(label="Channels", style=discord.ButtonStyle.secondary, row=0)
    async def channels_button(
        self, button: ui.Button, interaction: discord.Interaction
    ):
        self._remember_panel(interaction)
        self.send_to_all_channels = not self.send_to_all_channels
        self.preview_seen = False
        self._log_action("channels_toggled")
        await interaction.response.edit_message(
            embed=self.build_embed(interaction), view=self
        )

    @ui.button(label="Users", style=discord.ButtonStyle.secondary, row=0)
    async def users_button(self, button: ui.Button, interaction: discord.Interaction):
        self._remember_panel(interaction)
        self.send_to_all_users = not self.send_to_all_users
        self.preview_seen = False
        if self.send_to_all_users:
            self.roles = []
            self.role_select_open = False
        self._log_action("users_toggled")
        await interaction.response.edit_message(
            embed=self.build_embed(interaction), view=self
        )

    @ui.button(label="Role", style=discord.ButtonStyle.secondary, row=0)
    async def role_button(self, button: ui.Button, interaction: discord.Interaction):
        self._remember_panel(interaction)
        if self.roles:
            self.roles = []
            self.role_select_open = False
            self.preview_seen = False
            self._log_action("roles_cleared")
            await interaction.response.edit_message(
                embed=self.build_embed(interaction),
                view=self,
            )
            return

        self.role_select_open = not self.role_select_open
        self._log_action("role_select_toggled", open=self.role_select_open)
        await interaction.response.edit_message(
            embed=self.build_embed(interaction),
            view=self,
        )

    @ui.button(label="Ghost ping", style=discord.ButtonStyle.secondary, row=1)
    async def ghost_button(self, button: ui.Button, interaction: discord.Interaction):
        self._remember_panel(interaction)
        self.send_ghost_ping = not self.send_ghost_ping
        self.preview_seen = False
        self._log_action("ghost_ping_toggled")
        await interaction.response.edit_message(
            embed=self.build_embed(interaction), view=self
        )

    @ui.button(label="Image before/after", style=discord.ButtonStyle.secondary, row=1)
    async def image_position_button(
        self, button: ui.Button, interaction: discord.Interaction
    ):
        self._remember_panel(interaction)
        self.image_position = "After" if self.image_position == "Before" else "Before"
        self.preview_seen = False
        self._log_action("image_position_toggled")
        await interaction.response.edit_message(
            embed=self.build_embed(interaction), view=self
        )

    @ui.button(label="Add image", style=discord.ButtonStyle.secondary, row=1)
    async def add_image_button(
        self, button: ui.Button, interaction: discord.Interaction
    ):
        self._remember_panel(interaction)
        await interaction.response.defer(ephemeral=True)
        self._log_action("image_upload_prompt")
        await interaction.followup.send(
            "Upload image in this channel within 2 minutes. I will use first attachment.",
            ephemeral=True,
        )

        def check(message: discord.Message) -> bool:
            return (
                message.author.id == self.owner_id
                and message.channel.id == interaction.channel_id
                and bool(message.attachments)
            )

        try:
            message = await self.bot.wait_for("message", check=check, timeout=120)
        except asyncio.TimeoutError:
            await interaction.followup.send(
                f"{lang_constants.ERROR_EMOJI} Image upload timed out.",
                ephemeral=True,
            )
            return

        error = await self._set_image_from_attachment(message.attachments[0])
        if error:
            await interaction.followup.send(
                f"{lang_constants.ERROR_EMOJI} {error}",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"{lang_constants.SUCCESS_EMOJI} Image added: `{self.image.filename}`",
            ephemeral=True,
        )
        self._log_action("image_added", filename=self.image.filename)
        await self._refresh_panel(interaction)

    @ui.button(label="Upload JSON", style=discord.ButtonStyle.secondary, row=3)
    async def upload_json_button(
        self, button: ui.Button, interaction: discord.Interaction
    ):
        self._remember_panel(interaction)
        await interaction.response.defer(ephemeral=True)
        self._log_action("json_upload_prompt")
        await interaction.followup.send(
            "Upload .json file(s) in this channel within 2 minutes. "
            "Name files with EN, RU, or LT (for example: en.json, ru.json, lt.json).",
            ephemeral=True,
        )

        def check(message: discord.Message) -> bool:
            return (
                message.author.id == self.owner_id
                and message.channel.id == interaction.channel_id
                and bool(message.attachments)
            )

        try:
            message = await self.bot.wait_for("message", check=check, timeout=120)
        except asyncio.TimeoutError:
            await interaction.followup.send(
                f"{lang_constants.ERROR_EMOJI} JSON upload timed out.",
                ephemeral=True,
            )
            return

        attachments_by_locale = {}
        for attachment in message.attachments[:3]:
            locale = _locale_from_json_filename(attachment.filename)
            if not locale:
                await interaction.followup.send(
                    f"{lang_constants.ERROR_EMOJI} Could not determine language from "
                    f"`{attachment.filename or 'news.json'}`. Name it with EN, RU, or LT.",
                    ephemeral=True,
                )
                return
            if locale in attachments_by_locale:
                await interaction.followup.send(
                    f"{lang_constants.ERROR_EMOJI} More than one {locale.upper()} JSON file uploaded.",
                    ephemeral=True,
                )
                return
            attachments_by_locale[locale] = attachment

        loaded = []
        for locale in NEWS_LOCALES:
            attachment = attachments_by_locale.get(locale)
            if not attachment:
                continue
            error = await self._set_content_from_json_attachment(
                attachment,
                locale=locale,
                replace_existing=not loaded,
            )
            if error:
                await interaction.followup.send(
                    f"{lang_constants.ERROR_EMOJI} {error}",
                    ephemeral=True,
                )
                return
            loaded.append(locale.upper())

        uploaded_message_deleted = True
        try:
            await message.delete()
        except discord.HTTPException as e:
            uploaded_message_deleted = False
            logger.warning("news_wizard.json_upload_delete_failed error=%s", e)

        deletion_note = (
            " Uploaded message deleted."
            if uploaded_message_deleted
            else " Could not delete uploaded message; check bot Manage Messages permission."
        )
        await interaction.followup.send(
            f"{lang_constants.SUCCESS_EMOJI} JSON added for: {', '.join(loaded)}"
            f"{deletion_note}",
            ephemeral=True,
        )
        self._log_action(
            "json_added",
            filenames=",".join(
                a.filename or "news.json" for a in message.attachments[:3]
            ),
        )
        await self._refresh_panel(interaction)

    @ui.button(label="Remove image", style=discord.ButtonStyle.secondary, row=3)
    async def remove_image_button(
        self, button: ui.Button, interaction: discord.Interaction
    ):
        self._remember_panel(interaction)
        self.image = None
        self.preview_seen = False
        self._log_action("image_removed")
        await interaction.response.edit_message(
            embed=self.build_embed(interaction), view=self
        )

    @ui.button(label="Clear role", style=discord.ButtonStyle.secondary, row=3)
    async def clear_role_button(
        self, button: ui.Button, interaction: discord.Interaction
    ):
        self._remember_panel(interaction)
        self.roles = []
        self.role_select_open = False
        self.preview_seen = False
        self._log_action("roles_cleared")
        await interaction.response.edit_message(
            embed=self.build_embed(interaction), view=self
        )

    @ui.button(label="Schedule", style=discord.ButtonStyle.secondary, row=1)
    async def schedule_button(
        self, button: ui.Button, interaction: discord.Interaction
    ):
        self._remember_panel(interaction)
        await interaction.response.send_modal(NewsWizardScheduleModal(self))

    @ui.button(label="Clear schedule", style=discord.ButtonStyle.secondary, row=1)
    async def clear_schedule_button(
        self, button: ui.Button, interaction: discord.Interaction
    ):
        self._remember_panel(interaction)
        self.schedule_text = None
        self.schedule_unix = None
        self.preview_seen = False
        self._log_action("schedule_cleared")
        await interaction.response.edit_message(
            embed=self.build_embed(interaction), view=self
        )

    @ui.button(label="Preview", style=discord.ButtonStyle.primary, row=2)
    async def preview_button(self, button: ui.Button, interaction: discord.Interaction):
        self._remember_panel(interaction)
        await interaction.response.defer(ephemeral=True)
        if not self._has_content():
            self._log_action("preview_blocked", reason="missing_content")
            await self._send_error(interaction, "Add news content first.")
            return
        self.preview_seen = True
        self._log_action("preview_started")
        await preview_news(
            self.bot,
            self.ctx,
            self.news_contents,
            self.embed_json,
            self.image,
            self.image_position,
            self.send_to_all_users,
            self.roles,
            self.send_to_all_channels,
            self.send_ghost_ping,
        )
        self._log_action("preview_completed")
        await self._refresh_panel(interaction)

    @ui.button(label="Send", style=discord.ButtonStyle.success, row=2)
    async def send_button(self, button: ui.Button, interaction: discord.Interaction):
        self._remember_panel(interaction)
        await interaction.response.defer(ephemeral=True)
        if not self._has_content():
            self._log_action("send_blocked", reason="missing_content")
            await self._send_error(interaction, "Add news content first.")
            return
        if not (self.send_to_all_channels or self.send_to_all_users or self.roles):
            self._log_action("send_blocked", reason="missing_target")
            await self._send_error(interaction, "Choose at least one target.")
            return
        if not self.preview_seen:
            self._log_action("send_blocked", reason="missing_preview")
            await self._send_error(interaction, "Preview news before sending.")
            return

        if self.schedule_unix:
            self._log_action("schedule_submit_started")
            payload = {
                "news_contents": self.news_contents,
                "embed_json": self.embed_json,
                "send_to_all_users": self.send_to_all_users,
                "role_ids": [role.id for role in self.roles],
                "send_to_all_channels": self.send_to_all_channels,
                "send_ghost_ping": self.send_ghost_ping,
                "image_position": self.image_position,
            }
            await self._save_scheduled_image(payload)
            scheduler.add_job(
                scheduled_send_news_task,
                trigger="date",
                run_date=datetime.fromtimestamp(self.schedule_unix, tz=timezone.utc),
                args=[self.ctx.user.id, self.ctx.guild.id, payload],
                misfire_grace_time=3600,
            )
            await interaction.followup.send(
                f"{lang_constants.SUCCESS_EMOJI} News scheduled for <t:{self.schedule_unix}:F> (<t:{self.schedule_unix}:R>).",
                ephemeral=True,
            )
            self._log_action("schedule_submit_completed")
            self.completed = True
            for item in self.children:
                item.disabled = True
            await self._refresh_panel(interaction)
            return

        self._log_action("send_started")
        await send_news(
            self.bot,
            self.ctx,
            self.news_contents,
            self.embed_json,
            self.image,
            self.image_position,
            self.send_to_all_users,
            self.roles,
            self.send_to_all_channels,
            self.send_ghost_ping,
        )
        self._log_action("send_completed")
        self.completed = True
        for item in self.children:
            item.disabled = True
        await self._refresh_panel(interaction)

    @ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel_button(self, button: ui.Button, interaction: discord.Interaction):
        self._remember_panel(interaction)
        self.completed = True
        self._log_action("cancelled")
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            embed=self.build_embed(interaction), view=self
        )
