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
    # Bind shared admin group to this Cog so Discord registers subcommands
    admin_group = admin_group
    
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
        sent_to_all_users_with_role: discord.Role = Option(discord.Role, "Role to send news to", required=False, default=None),
        send_to_all_channels: list[discord.TextChannel] = Option(discord.TextChannel, "Channels to send news to", required=False, default=None),
        send_ghost_ping: bool = Option(description="Send ghost ping", default=False),
        schedule_time: str = Option(str, "Schedule time to send news (format: HH:MM)", required=False, default=None),
    ):
        await ctx.defer(ephemeral=True)

        ctx.respond("WIP")

def setup(bot: commands.Bot):
    bot.add_cog(adminSendNews(bot))
