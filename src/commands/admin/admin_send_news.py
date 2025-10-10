import discord
from discord.ext import commands
from discord import Option
from src.utils.logger import get_cool_logger
from src.languages.localize import translate
from src.utils.database import get_language
from src.utils.auth import require_admin
from src.utils.scheduler import get_scheduler
import config.constants as constants
from src.utils.clear_dm_messages import clear_dm_messages, clear_all_dm_messages
from src.commands.admin import admin_group


logger = get_cool_logger(__name__)


class adminSendNews(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @admin_group.command(name="send_news",
                         description="Send news to all users or channels",
                         description_localizations={
                             "ru": "Отправить новость всем пользователям или каналам",
                             "lt": "Išsiųsti pranešimą visiems naudotojams arba kanalams"
                         }
                         )
    async def send_news_admin(
        self,
        ctx: discord.ApplicationContext,
        image: discord.Attachment = Option(discord.Attachment, "Image to send", required=True),
        send_image_before_or_after_news: str = Option(str, "Send image before or after news", choices=["before", "after"], default="before"),
        send_to_all_users: bool = Option(bool, "Send news to all users", default=True),
        send_to_all_channels: bool = Option(bool, "Send news to all channels", default=True),
        schedule_time: str = Option(str, "Schedule time to send news (format: HH:MM)", required=False, default=None),
    ):
        await ctx.defer(ephemeral=True)

        ctx.respond("WIP")

def setup(bot: commands.Bot):
    bot.add_cog(adminSendNews(bot))
