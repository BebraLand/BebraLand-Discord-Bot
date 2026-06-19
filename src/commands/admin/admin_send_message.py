import asyncio
import json

import discord
from discord import Option
from discord.ext import commands
from pycord.multicog import subcommand

import src.languages.lang_constants as lang_constants
from config.config import config as bot_config
from src.languages.localize import _
from src.utils.auth import require_admin
from src.utils.database import get_language
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger
from src.utils.news_sender import build_news_json_payload

logger = get_cool_logger(__name__)

MAX_JSON_BYTES = 1024 * 1024
JSON_WAIT_TIMEOUT_SECONDS = 300


class AdminSendMessage(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @subcommand("admin")
    @discord.slash_command(
        name="send_message",
        description="Send a Discohook/news JSON message in this channel",
    )
    async def send_message(
        self,
        ctx: discord.ApplicationContext,
        json_file: discord.Attachment = Option(
            discord.Attachment,
            name="json",
            description="Discohook/news JSON file",
            required=False,
            default=None,
        ),
    ) -> None:
        if not await require_admin(ctx):
            logger.info(
                "send_message.denied user_id=%s guild_id=%s",
                ctx.user.id,
                ctx.guild.id if ctx.guild else None,
            )
            return

        await ctx.defer(ephemeral=True)
        user_lang = await get_language(ctx.user.id)
        attachment = json_file
        if attachment is None:
            await ctx.followup.send(
                _("send_message.upload_prompt", user_lang), ephemeral=True
            )
            try:
                message = await self.bot.wait_for(
                    "message",
                    timeout=JSON_WAIT_TIMEOUT_SECONDS,
                    check=lambda message: (
                        message.author.id == ctx.user.id
                        and message.channel.id == ctx.channel.id
                        and bool(message.attachments)
                    ),
                )
            except asyncio.TimeoutError:
                await ctx.followup.send(
                    _("send_message.upload_timeout", user_lang), ephemeral=True
                )
                return
            attachment = message.attachments[0]

        data, error = await self._read_json(attachment, user_lang)
        if error:
            await ctx.followup.send(error, ephemeral=True)
            return

        content, embeds, view = build_news_json_payload(data, get_embed_icon(self.bot))
        if not content and not embeds and not view:
            await ctx.followup.send(
                _("send_message.empty_payload", user_lang), ephemeral=True
            )
            return

        try:
            await ctx.channel.send(
                content=content or None,
                embeds=embeds[:10] or None,
                view=view,
            )
        except discord.HTTPException as error:
            logger.exception(
                "send_message.failed user_id=%s channel_id=%s",
                ctx.user.id,
                ctx.channel.id,
            )
            await ctx.followup.send(
                _("send_message.send_failed", user_lang).format(error=error),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"{lang_constants.SUCCESS_EMOJI} {_('common.success', user_lang)}",
            description=_("send_message.sent", user_lang),
            color=bot_config.embeds.success_color,
        )
        embed.set_footer(text=bot_config.bot.trademark, icon_url=get_embed_icon(ctx))
        await ctx.followup.send(
            embed=embed,
            ephemeral=True,
            delete_after=bot_config.messages.action_confirmation_delete_delay,
        )
        logger.info(
            "send_message.sent user_id=%s guild_id=%s channel_id=%s filename=%s",
            ctx.user.id,
            ctx.guild.id if ctx.guild else None,
            ctx.channel.id,
            attachment.filename,
        )

    async def _read_json(
        self, attachment: discord.Attachment, user_lang: str
    ) -> tuple[dict | None, str | None]:
        filename = attachment.filename or "message.json"
        if not filename.lower().endswith(".json"):
            return None, _("send_message.not_json", user_lang)
        if (attachment.size or 0) > MAX_JSON_BYTES:
            return None, _("send_message.too_large", user_lang)

        try:
            raw = await attachment.read()
        except discord.HTTPException:
            return None, _("send_message.read_failed", user_lang)
        if not raw:
            return None, _("send_message.empty_file", user_lang)
        if len(raw) > MAX_JSON_BYTES:
            return None, _("send_message.too_large", user_lang)

        try:
            data = json.loads(raw.decode("utf-8-sig"))
        except UnicodeDecodeError:
            return None, _("send_message.not_utf8", user_lang)
        except json.JSONDecodeError as error:
            return None, _("send_message.invalid_json", user_lang).format(
                line=error.lineno, column=error.colno
            )
        if not isinstance(data, dict):
            return None, _("send_message.not_object", user_lang)
        return data, None


def setup(bot: commands.Bot):
    bot.add_cog(AdminSendMessage(bot))
