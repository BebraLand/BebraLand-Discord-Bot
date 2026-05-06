import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import ui

import config.constants as constants
from src.languages import lang_constants
from src.languages.localize import _
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger
from src.utils.news_sender import preview_news, scheduled_send_news_task, send_news
from src.utils.schedule_utils import parse_human_schedule_time
from src.utils.scheduler import scheduler

logger = get_cool_logger(__name__)


def _make_optional_input(**kwargs) -> ui.InputText:
    item = ui.InputText(required=False, **kwargs)
    # Pycord 2.7 serializes required=False as None unless forced here.
    item._underlying.required = False
    return item


class NewsWizardContentModal(ui.Modal):
    def __init__(self, view: "NewsWizardView"):
        super().__init__(title="News content")
        self.wizard_view = view
        limit = getattr(constants, "NEWS_CHARACTER_LIMIT", 2000)
        self.add_item(
            ui.InputText(
                label="English content",
                placeholder="Required. Plain text or embed JSON.",
                style=discord.InputTextStyle.long,
                required=True,
                max_length=limit,
                value=view.news_contents.get("en", "")
                if isinstance(view.news_contents.get("en"), str)
                else "",
            )
        )
        self.add_item(
            _make_optional_input(
                label="Russian content",
                placeholder="Optional. Falls back to English.",
                style=discord.InputTextStyle.long,
                max_length=limit,
                value=view.news_contents.get("ru", "")
                if isinstance(view.news_contents.get("ru"), str)
                else "",
            )
        )
        self.add_item(
            _make_optional_input(
                label="Lithuanian content",
                placeholder="Optional. Falls back to English.",
                style=discord.InputTextStyle.long,
                max_length=limit,
                value=view.news_contents.get("lt", "")
                if isinstance(view.news_contents.get("lt"), str)
                else "",
            )
        )

    async def callback(self, interaction: discord.Interaction):
        import json

        en_val = (self.children[0].value or "").strip()
        ru_val = (self.children[1].value or "").strip()
        lt_val = (self.children[2].value or "").strip()

        self.wizard_view.embed_json = None
        self.wizard_view.news_contents = {}
        self.wizard_view.preview_seen = False

        if en_val.startswith("{") and en_val.endswith("}"):
            try:
                parsed = json.loads(en_val)
                if isinstance(parsed, dict):
                    self.wizard_view.embed_json = parsed
                    desc = parsed.get("description")
                    self.wizard_view.news_contents["en"] = desc if isinstance(desc, str) else ""
            except Exception:
                self.wizard_view.news_contents["en"] = en_val
        else:
            self.wizard_view.news_contents["en"] = en_val

        if ru_val:
            self.wizard_view.news_contents["ru"] = ru_val
        if lt_val:
            self.wizard_view.news_contents["lt"] = lt_val

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
        await interaction.response.edit_message(
            embed=self.wizard_view.build_embed(interaction),
            view=self.wizard_view,
        )


class NewsWizardRoleSelectView(ui.View):
    def __init__(self, wizard_view: "NewsWizardView"):
        super().__init__(timeout=120)
        select = ui.RoleSelect(
            placeholder="Choose role target",
            min_values=1,
            max_values=1,
            row=0,
        )

        async def callback(interaction: discord.Interaction):
            role = select.values[0] if select.values else None
            if not role:
                await interaction.response.send_message(
                    f"{lang_constants.ERROR_EMOJI} Role not found.",
                    ephemeral=True,
                )
                return

            wizard_view.send_to_all_users = False
            wizard_view.role = role
            wizard_view.preview_seen = False
            await interaction.response.edit_message(
                embed=wizard_view.build_embed(interaction),
                view=wizard_view,
            )

        select.callback = callback
        self.add_item(select)


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
        self.role: Optional[discord.Role] = None
        self.send_ghost_ping = True
        self.image_position = "Before"
        self.schedule_text: Optional[str] = None
        self.schedule_unix: Optional[int] = None
        self.preview_seen = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            f"{lang_constants.ERROR_EMOJI} This news wizard belongs to another admin.",
            ephemeral=True,
        )
        return False

    def build_embed(self, source) -> discord.Embed:
        content_locales = [key.upper() for key in ("en", "ru", "lt") if self.news_contents.get(key)]
        targets = []
        if self.send_to_all_channels:
            targets.append("news channels")
        if self.send_to_all_users:
            targets.append("all users")
        if self.role:
            targets.append(f"role {self.role.mention}")

        embed = discord.Embed(
            title="News wizard",
            description="Set content, targets, preview, then send.",
            color=constants.INFO_EMBED_COLOR,
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
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=get_embed_icon(source),
        )
        return embed

    def _has_content(self) -> bool:
        return bool(self.news_contents.get("en") or self.embed_json)

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
        try:
            await interaction.edit_original_response(
                embed=self.build_embed(interaction),
                view=self,
            )
            return
        except (discord.NotFound, discord.HTTPException):
            pass

        await interaction.followup.send(
            embed=self.build_embed(interaction),
            view=self,
            ephemeral=True,
        )

    @ui.button(label="Content", style=discord.ButtonStyle.primary, row=0)
    async def content_button(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(NewsWizardContentModal(self))

    @ui.button(label="Channels", style=discord.ButtonStyle.secondary, row=0)
    async def channels_button(self, button: ui.Button, interaction: discord.Interaction):
        self.send_to_all_channels = not self.send_to_all_channels
        self.preview_seen = False
        await interaction.response.edit_message(embed=self.build_embed(interaction), view=self)

    @ui.button(label="Users", style=discord.ButtonStyle.secondary, row=0)
    async def users_button(self, button: ui.Button, interaction: discord.Interaction):
        self.send_to_all_users = not self.send_to_all_users
        self.preview_seen = False
        if self.send_to_all_users:
            self.role = None
        await interaction.response.edit_message(embed=self.build_embed(interaction), view=self)

    @ui.button(label="Role", style=discord.ButtonStyle.secondary, row=0)
    async def role_button(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Choose role to receive news DMs.",
            view=NewsWizardRoleSelectView(self),
            ephemeral=True,
        )

    @ui.button(label="Ghost ping", style=discord.ButtonStyle.secondary, row=1)
    async def ghost_button(self, button: ui.Button, interaction: discord.Interaction):
        self.send_ghost_ping = not self.send_ghost_ping
        self.preview_seen = False
        await interaction.response.edit_message(embed=self.build_embed(interaction), view=self)

    @ui.button(label="Image before/after", style=discord.ButtonStyle.secondary, row=1)
    async def image_position_button(
        self, button: ui.Button, interaction: discord.Interaction
    ):
        self.image_position = "After" if self.image_position == "Before" else "Before"
        self.preview_seen = False
        await interaction.response.edit_message(embed=self.build_embed(interaction), view=self)

    @ui.button(label="Add image", style=discord.ButtonStyle.secondary, row=1)
    async def add_image_button(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
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

        self.image = message.attachments[0]
        self.preview_seen = False
        await interaction.followup.send(
            f"{lang_constants.SUCCESS_EMOJI} Image added: `{self.image.filename}`",
            ephemeral=True,
        )
        await self._refresh_panel(interaction)

    @ui.button(label="Remove image", style=discord.ButtonStyle.secondary, row=3)
    async def remove_image_button(
        self, button: ui.Button, interaction: discord.Interaction
    ):
        self.image = None
        self.preview_seen = False
        await interaction.response.edit_message(embed=self.build_embed(interaction), view=self)

    @ui.button(label="Clear role", style=discord.ButtonStyle.secondary, row=3)
    async def clear_role_button(
        self, button: ui.Button, interaction: discord.Interaction
    ):
        self.role = None
        self.preview_seen = False
        await interaction.response.edit_message(embed=self.build_embed(interaction), view=self)

    @ui.button(label="Schedule", style=discord.ButtonStyle.secondary, row=1)
    async def schedule_button(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(NewsWizardScheduleModal(self))

    @ui.button(label="Clear schedule", style=discord.ButtonStyle.secondary, row=1)
    async def clear_schedule_button(
        self, button: ui.Button, interaction: discord.Interaction
    ):
        self.schedule_text = None
        self.schedule_unix = None
        self.preview_seen = False
        await interaction.response.edit_message(embed=self.build_embed(interaction), view=self)

    @ui.button(label="Preview", style=discord.ButtonStyle.primary, row=2)
    async def preview_button(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self._has_content():
            await self._send_error(interaction, "Add news content first.")
            return
        self.preview_seen = True
        await preview_news(
            self.bot,
            self.ctx,
            self.news_contents,
            self.embed_json,
            self.image,
            self.image_position,
            self.send_to_all_users,
            self.role,
            self.send_to_all_channels,
            self.send_ghost_ping,
        )

    @ui.button(label="Send", style=discord.ButtonStyle.success, row=2)
    async def send_button(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not self._has_content():
            await self._send_error(interaction, "Add news content first.")
            return
        if not (self.send_to_all_channels or self.send_to_all_users or self.role):
            await self._send_error(interaction, "Choose at least one target.")
            return
        if not self.preview_seen:
            await self._send_error(interaction, "Preview news before sending.")
            return

        if self.schedule_unix:
            payload = {
                "news_contents": self.news_contents,
                "embed_json": self.embed_json,
                "send_to_all_users": self.send_to_all_users,
                "role_id": self.role.id if self.role else None,
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
            return

        await send_news(
            self.bot,
            self.ctx,
            self.news_contents,
            self.embed_json,
            self.image,
            self.image_position,
            self.send_to_all_users,
            self.role,
            self.send_to_all_channels,
            self.send_ghost_ping,
        )

    @ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel_button(self, button: ui.Button, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=self.build_embed(interaction), view=self)
