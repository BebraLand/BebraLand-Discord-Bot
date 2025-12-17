import discord
from discord.ext import commands
from discord import Option
from src.utils.logger import get_cool_logger
from src.languages.localize import translate
from src.utils.database import get_language
from src.utils.auth import require_admin
from src.utils.scheduler import get_scheduler
import config.constants as constants
from src.languages import lang_constants as lang_constants
from pycord.multicog import subcommand
from src.views.news_modal import NewsModal
import os
import uuid
from src.utils.news_sender import send_news, preview_news
from src.utils.get_embed_icon import get_embed_icon


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
        preview: bool = Option(
            bool,
            name="preview",
            name_localizations={
                "ru": "предпросмотр",
                "lt": "pranešimo-žiūrėjimas"
            },
            description="Preview news before sending",
            description_localizations={
                "ru": "Предпросмотр новости перед отправкой",
                "lt": "Peržiūrėti pranešimą prieš siuntimą"
            },
            default=False
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
        # Allow sending if either EN content exists or a valid embed JSON was provided
        if not modal.news_contents or not modal.news_contents.get("en"):
            if not embed_json:
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
                    title=f"{lang_constants.ERROR_EMOJI} {translate('Error', current_lang)}",
                    description=desc,
                    color=discord.Color.red(),
                )

                embed.set_footer(
                    text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(ctx))

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
                title=f"{lang_constants.SUCCESS_EMOJI} {translate('Success', current_lang)}",
                description=desc,
                color=discord.Color.green(),
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(ctx))

            await ctx.followup.send(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
            logger.info(f"{ctx.user.name}({ctx.user.id}) scheduled news broadcast at {schedule_time}")
            return

        # Send immediately
        if preview:
            await preview_news(
                self.bot,
                ctx,
                news_contents,
                embed_json,
                image,
                send_image_before_or_after_news,
                send_to_all_users,
                sent_to_all_users_with_role,
                send_to_all_channels,
                send_ghost_ping,
            )
            return

        await send_news(
            self.bot,
            ctx,
            news_contents,
            embed_json,
            image,
            send_image_before_or_after_news,
            send_to_all_users,
            sent_to_all_users_with_role,
            send_to_all_channels,
            send_ghost_ping,
        )


def setup(bot: commands.Bot):
    bot.add_cog(adminSendNews(bot))