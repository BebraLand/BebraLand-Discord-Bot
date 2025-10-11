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
        await ctx.defer(ephemeral=True)

        if not await require_admin(ctx):
            logger.info(
                f"{ctx.user.name}({ctx.user.id}) used admin command without permissions")
            return

        # Get user language for response messages
        user_lang = await get_language(ctx.author.id)
        
        # You can use translate() for dynamic messages
        wip_message = translate("admin.send_news.wip", user_lang)
        
        await ctx.respond(wip_message, ephemeral=True)


def setup(bot: commands.Bot):
    bot.add_cog(adminSendNews(bot))