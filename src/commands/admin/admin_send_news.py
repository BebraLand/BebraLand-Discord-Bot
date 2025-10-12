import discord
from discord.ext import commands
from discord import Option
from src.utils.logger import get_cool_logger
from src.languages.localize import translate
from src.utils.database import get_language
from src.utils.auth import require_admin
from src.utils.scheduler import get_scheduler
import config.constants as constants
from pycord.multicog import subcommand
from datetime import datetime, time
import asyncio
import io
import os
import uuid
import json
from src.utils.embed_builder import build_embed_from_template, build_embed_from_data, replace_placeholders


logger = get_cool_logger(__name__)


class adminSendNews(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @subcommand("admin")
    @discord.slash_command(
        name="send_news",
        description="Send news to all users or channels",
        description_localizations={
            "ru": "Отправить новость всем пользователям или каналам",
            "lt": "Išsiųsti pranešimą visiems naudotojams arba kanalams"
        }
    )
    async def send_news_admin(
        self,
        ctx: discord.ApplicationContext,
        image: discord.Attachment = Option(
            discord.Attachment,
            name="image",
            name_localizations={
                "ru": "изображение",
                "lt": "vaizdas"
            },
            description="Image to send",
            description_localizations={
                "ru": "Изображение для отправки",
                "lt": "Vaizdas siųsti"
            },
            required=False
        ),
        send_image_before_or_after_news: str = Option(
            str,
            name="image-position",
            name_localizations={
                "ru": "позиция-изображения",
                "lt": "vaizdo-pozicija"
            },
            description="Send image before or after news",
            description_localizations={
                "ru": "Отправить изображение до или после новости",
                "lt": "Siųsti vaizdą prieš ar po pranešimo"
            },
            choices=["Before", "After"],
            default="Before"
        ),
        send_to_all_users: bool = Option(
            bool,
            name="send-to-all-users",
            name_localizations={
                "ru": "отправить-всем-пользователям",
                "lt": "siųsti-visiems-naudotojams"
            },
            description="Send news to all users",
            description_localizations={
                "ru": "Отправить новость всем пользователям",
                "lt": "Siųsti pranešimą visiems naudotojams"
            },
            default=True
        ),
        sent_to_all_users_with_role: discord.Role = Option(
            discord.Role,
            name="send-to-all-users-with-role",
            name_localizations={
                "ru": "отправить-пользователям-с-ролью",
                "lt": "siųsti-naudotojams-su-role"
            },
            description="Role to send news to (overrides send-to-all-users)",
            description_localizations={
                "ru": "Роль для отправки новостей (перезаписывает отправить-всем-пользователям)",
                "lt": "Rolė siųsti pranešimus (pakeičia siųsti-visiems-naudotojams)"
            },
            required=False,
            default=None
        ),
        send_to_all_channels: bool = Option(
            bool,
            name="send-to-all-channels",
            name_localizations={
                "ru": "отправить-во-все-каналы",
                "lt": "siųsti-visiems-kanalams"
            },
            description="Send news to all channels",
            description_localizations={
                "ru": "Отправить новость во все каналы",
                "lt": "Siųsti pranešimą visiems kanalams"
            },
            default=True
        ),
        send_ghost_ping: bool = Option(
            bool,
            name="send-ghost-ping",
            name_localizations={
                "ru": "отправить-призрачный-пинг",
                "lt": "siųsti-vaiduoklinį-pingą"
            },
            description="Send ghost ping",
            description_localizations={
                "ru": "Отправить призрачный пинг",
                "lt": "Siųsti vaiduoklinį pingą"
            },
            default=True
        ),
        schedule_time: str = Option(
            str,
            name="schedule-time",
            name_localizations={
                "ru": "время-расписания",
                "lt": "suplanuotas-laikas"
            },
            description="Schedule time to send news (format: HH:MM)",
            description_localizations={
                "ru": "Запланированное время отправки новости (формат: ЧЧ:ММ)",
                "lt": "Suplanuotas laikas siųsti pranešimą (formatas: HH:MM)"
            },
            required=False,
            default=None
        ),
    ):
        if not await require_admin(ctx):
            logger.info(
                f"{ctx.user.name}({ctx.user.id}) used admin command without permissions")
            return

        user_lang = await get_language(ctx.user.id)

        # Create a modal to get the news content (EN required, RU/LT optional)
        modal = NewsModal(
            title=translate("News Content", user_lang),
            user_lang=user_lang
        )
        await ctx.send_modal(modal)
        
        # Wait for modal submission
        await modal.wait()

        # Accept either multilingual plain text or a raw JSON embed pasted in EN field
        embed_json = getattr(modal, "embed_json", None)
        if not modal.news_contents or not modal.news_contents.get("en"):
            return
        news_contents = modal.news_contents

        # Validate schedule time if provided
        if schedule_time:
            try:
                scheduler = get_scheduler()
                payload = {
                    "news_contents": news_contents,
                    "embed_json": embed_json,
                    "send_to_all_users": send_to_all_users,
                    "role_id": sent_to_all_users_with_role.id if sent_to_all_users_with_role else None,
                    "send_to_all_channels": send_to_all_channels,
                    "send_ghost_ping": send_ghost_ping,
                    "image_position": send_image_before_or_after_news,
                }
                # Encode image for scheduled send if provided
                if image:
                    try:
                        image_bytes = await image.read()
                        if image_bytes:
                            os.makedirs("data/scheduled_files", exist_ok=True)
                            unique_name = f"{uuid.uuid4()}_{image.filename}"
                            image_path = os.path.join("data", "scheduled_files", unique_name)
                            with open(image_path, "wb") as f:
                                f.write(image_bytes)
                            payload["image_path"] = image_path
                            payload["image_filename"] = image.filename
                    except Exception:
                        # If image cannot be saved, proceed without image
                        pass
                await scheduler.schedule_news_broadcast(ctx.guild.id, schedule_time, payload)
            except ValueError:
                current_lang = await get_language(ctx.user.id)
                desc = translate(
                    "Invalid time format. Please use HH:MM (00-23:00-59).", current_lang)
                embed = discord.Embed(
                    title=f"❌ {translate('Error', current_lang)}",
                    description=desc,
                    color=discord.Color.red(),
                )

                embed.set_footer(
                    text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=ctx.bot.user.avatar.url)

                await ctx.respond(
                    embed=embed,
                    ephemeral=True,
                    delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
                )
                return

            current_lang = await get_language(ctx.user.id)
            desc = translate("News scheduled for {schedule_time}.", current_lang).format(
                schedule_time=schedule_time
            )
            embed = discord.Embed(
                title=f"✅ {translate('Success', current_lang)}",
                description=desc,
                color=discord.Color.green(),
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=ctx.bot.user.avatar.url)

            await ctx.followup.send(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
            logger.info(f"{ctx.user.name}({ctx.user.id}) scheduled news broadcast at {schedule_time}")
            return

        # Send immediately
        await self._send_news_task(
            ctx,
            news_contents,
            embed_json,
            image,
            send_image_before_or_after_news,
            send_to_all_users,
            sent_to_all_users_with_role,
            send_to_all_channels,
            send_ghost_ping
        )

    async def _send_news_task(
        self,
        ctx: discord.ApplicationContext,
        news_contents: dict,
        embed_json: dict,
        image: discord.Attachment,
        send_image_before_or_after_news: str,
        send_to_all_users: bool,
        sent_to_all_users_with_role: discord.Role,
        send_to_all_channels: bool,
        send_ghost_ping: bool
    ):
        """Execute the news sending task"""
        user_lang = await get_language(ctx.user.id)
        # Helper to choose content for a locale, falling back to English
        def _content_for(locale: str) -> str:
            if isinstance(news_contents, dict):
                return news_contents.get(locale) or news_contents.get("en") or ""
            return str(news_contents)
        
        # Prepare embed template (for default case) and bot avatar
        try:
            with open("src/languages/messages/news_message.json", "r", encoding="utf-8") as f:
                news_template = json.load(f)
        except Exception:
            news_template = None

        bot_user = getattr(ctx.bot, "user", None)
        bot_avatar = ""
        if bot_user:
            if bot_user.avatar:
                bot_avatar = bot_user.avatar.url
            else:
                bot_avatar = bot_user.default_avatar.url

        # Read image once if provided
        image_bytes = None
        image_filename = None
        if image:
            try:
                image_bytes = await image.read()
                image_filename = image.filename
            except Exception as e:
                logger.error(f"Failed to download image: {e}")
                image_bytes = None
                image_filename = None

        from typing import Optional
        def _build_embed(content_text: str, include_image: bool) -> Optional[discord.Embed]:
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
            # If raw embed JSON was provided in the modal, use it preferentially
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
            # Otherwise, fall back to the default template file
            if not news_template:
                return None
            try:
                return build_embed_from_template(
                    template=news_template,
                    replacements=replacements,
                    default_footer=getattr(constants, "NEWS_DEFAULT_FOOTER", False),
                )
            except Exception:
                return None

        success_count = 0
        fail_count = 0

        # Send to configured language-specific channels
        failed_channels = []
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
                        failed_channels.append((channel_id, str(e)))
                        fail_count += 1
                        continue
                try:
                    # Build embed and send, respecting image position
                    include_image_in_embed = send_image_before_or_after_news != "After"
                    embed = _build_embed(_content_for(locale), include_image_in_embed)

                    if embed:
                        if include_image_in_embed and image_bytes:
                            await channel.send(
                                embed=embed,
                                file=discord.File(fp=io.BytesIO(image_bytes), filename=image_filename)
                            )
                        else:
                            await channel.send(embed=embed)
                            if send_image_before_or_after_news == "After" and image_bytes:
                                await channel.send(
                                    file=discord.File(fp=io.BytesIO(image_bytes), filename=image_filename)
                                )
                    else:
                        # Fallback to plain text
                        if image_bytes and send_image_before_or_after_news == "Before":
                            await channel.send(
                                file=discord.File(fp=io.BytesIO(image_bytes), filename=image_filename)
                            )
                        await channel.send(_content_for(locale))
                        if image_bytes and send_image_before_or_after_news == "After":
                            await channel.send(
                                file=discord.File(fp=io.BytesIO(image_bytes), filename=image_filename)
                            )

                    # Send ghost ping after content (English channel only)
                    if send_ghost_ping and locale == "en":
                        ping_msg = await channel.send("@everyone")
                        await ping_msg.delete()

                    success_count += 1
                    await asyncio.sleep(1)  # Rate limit protection
                except Exception as e:
                    logger.error(f"Failed to send news to channel {channel.id}: {e}")
                    failed_channels.append((channel.id, str(e)))
                    fail_count += 1

        # Send to users (DMs)
        failed_users = []
        if send_to_all_users or sent_to_all_users_with_role:
            members = []
            if sent_to_all_users_with_role:
                # Role in the current guild only
                role = discord.utils.get(ctx.guild.roles, id=sent_to_all_users_with_role.id)
                if role:
                    members.extend(role.members)
            else:
                # All members in the current guild
                members.extend(ctx.guild.members)

            # Remove duplicates and bots
            unique_members = {m.id: m for m in members if not m.bot}

            for member in unique_members.values():
                try:
                    # Build embed and send via DM, respecting image position
                    include_image_in_embed = send_image_before_or_after_news != "After"
                    member_lang = await get_language(member.id)
                    embed = _build_embed(_content_for(member_lang), include_image_in_embed)

                    if embed:
                        if include_image_in_embed and image_bytes:
                            await member.send(
                                embed=embed,
                                file=discord.File(fp=io.BytesIO(image_bytes), filename=image_filename)
                            )
                        else:
                            await member.send(embed=embed)
                            if send_image_before_or_after_news == "After" and image_bytes:
                                await member.send(
                                    file=discord.File(fp=io.BytesIO(image_bytes), filename=image_filename)
                                )
                    else:
                        # Fallback to plain text
                        if image_bytes and send_image_before_or_after_news == "Before":
                            await member.send(
                                file=discord.File(fp=io.BytesIO(image_bytes), filename=image_filename)
                            )
                        await member.send(_content_for(member_lang))
                        if image_bytes and send_image_before_or_after_news == "After":
                            await member.send(
                                file=discord.File(fp=io.BytesIO(image_bytes), filename=image_filename)
                            )

                    success_count += 1
                    await asyncio.sleep(1)  # Rate limit protection
                except discord.Forbidden:
                    logger.debug(f"Cannot send DM to {member.name}({member.id})")
                    failed_users.append((member.id, "Forbidden"))
                    fail_count += 1
                except Exception as e:
                    logger.error(f"Failed to send news to user {member.id}: {e}")
                    failed_users.append((member.id, str(e)))
                    fail_count += 1

        # Send summary
        summary = translate("news_sent_summary", user_lang).format(
            success=success_count,
            failed=fail_count
        )
        
        try:
            # If there are failures, include brief details (limited to 20 each)
            if fail_count > 0:
                ch_details = "\n".join([f"• Channel {cid}: {err}" for cid, err in failed_channels[:20]]) if failed_channels else ""
                user_details = "\n".join([f"• User {uid}: {err}" for uid, err in failed_users[:20]]) if failed_users else ""
                details = "\n\nFailed channels:\n" + ch_details if ch_details else ""
                details += "\n\nFailed users:\n" + user_details if user_details else ""
                summary = summary + details
            await ctx.followup.send(summary, ephemeral=True)
        except:
            # If context is no longer valid, log instead
            logger.info(f"News sent: {success_count} successful, {fail_count} failed")

        logger.info(f"News broadcast completed by {ctx.user.name}({ctx.user.id}): {success_count} sent, {fail_count} failed")


class NewsModal(discord.ui.Modal):
    def __init__(self, title: str, user_lang: str):
        super().__init__(title=title)
        self.news_contents = {}
        self.embed_json = None
        self.user_lang = user_lang
        # English (required)
        self.add_item(
            discord.ui.InputText(
                label="English content",
                placeholder="Enter the news text in English (required)",
                style=discord.InputTextStyle.long,
                required=True,
                max_length=4000,
            )
        )
        # Russian (optional)
        self.add_item(
            discord.ui.InputText(
                label="Русский текст",
                placeholder="Введите текст новости на русском (необязательно)",
                style=discord.InputTextStyle.long,
                required=False,
                max_length=4000,
            )
        )
        # Lithuanian (optional)
        self.add_item(
            discord.ui.InputText(
                label="Turinys lietuvių kalba",
                placeholder="Įrašykite naujienų tekstą lietuviškai (nebūtina)",
                style=discord.InputTextStyle.long,
                required=False,
                max_length=4000,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        # Collect values from inputs in order: EN, RU, LT
        try:
            en_val = (self.children[0].value or "").strip()
            ru_val = (self.children[1].value or "").strip()
            lt_val = (self.children[2].value or "").strip()
        except Exception:
            en_val = ""
            ru_val = ""
            lt_val = ""

        # If EN looks like a JSON object, try to parse it as an embed definition
        try:
            trimmed = en_val.strip()
            if trimmed.startswith("{") and trimmed.endswith("}"):
                parsed = json.loads(trimmed)
                if isinstance(parsed, dict):
                    self.embed_json = parsed
        except Exception:
            self.embed_json = None

        if self.embed_json:
            # Use description from embed JSON as EN content fallback, if present
            desc_text = ""
            try:
                if isinstance(self.embed_json.get("description"), str):
                    desc_text = self.embed_json.get("description")
            except Exception:
                desc_text = ""
            self.news_contents["en"] = desc_text
            if ru_val:
                self.news_contents["ru"] = ru_val
            if lt_val:
                self.news_contents["lt"] = lt_val
        else:
            if en_val:
                self.news_contents["en"] = en_val
            if ru_val:
                self.news_contents["ru"] = ru_val
            if lt_val:
                self.news_contents["lt"] = lt_val

        await interaction.response.send_message(
            translate("news_processing", self.user_lang),
            ephemeral=True,
        )
        self.stop()


def setup(bot: commands.Bot):
    bot.add_cog(adminSendNews(bot))