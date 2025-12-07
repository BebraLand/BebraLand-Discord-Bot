import discord
from discord.ext import commands
from discord import Option
from src.utils.logger import get_cool_logger
from src.utils.auth import require_admin
import config.constants as constants
from pycord.multicog import subcommand
from src.views.ticket_panel import build_ticket_panel_embed


logger = get_cool_logger(__name__)


class sendTicketPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    
    @subcommand("admin")
    @discord.slash_command(
        name="send_ticket_panel",
        description="Send the ticket panel to the channel",
        description_localizations={
            "ru": "Отправить панель тикетов в канал",
            "lt": "Siųsti bilietų skydelį į kanalą"
        }
    )
    async def send_ticket_panel(
        self,
        ctx: discord.ApplicationContext,
    ):
        await ctx.defer(ephemeral=True)

        if not await require_admin(ctx):
            logger.info(
                f"{ctx.user.name}({ctx.user.id}) used admin command without permissions")
            return

        await ctx.delete()

        await ctx.send(embed=build_ticket_panel_embed(ctx))

        logger.info(
            f"Admin {ctx.user.name}({ctx.user.id}) sent ticket panel"
        )


def setup(bot: commands.Bot):
    bot.add_cog(sendTicketPanel(bot))