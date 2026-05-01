import discord
from discord.ext import commands
from discord import Option
from config import constants
from src.utils.logger import get_cool_logger
from src.utils.auth import require_admin
from pycord.multicog import subcommand
from src.languages import lang_constants as lang_constants
from src.utils.scheduler import scheduler
from src.utils.schedule_utils import parse_and_validate_schedule
from datetime import datetime, timezone
from src.utils.database import get_language
from src.languages.localize import _
from src.utils.send.send_ticket_panel_message import send_ticket_panel_message

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
            "lt": "Siųsti bilietų skydelį į kanalą",
        },
    )
    async def send_ticket_panel(
        self,
        ctx: discord.ApplicationContext,
        schedule_time=Option(
            str,
            description="Schedule time as Unix UTC timestamp",
            required=False,
            description_localizations={
                "ru": "Время планирования в формате Unix UTC timestamp",
                "lt": "Planavimo laikas Unix UTC timestamp formatu",
            },
        ),
        selected_channel=Option(
            discord.TextChannel,
            description="Channel to send the message to",
            required=False,
            description_localizations={
                "ru": "Канал, куда отправить сообщение",
                "lt": "Kanalas, į kurį siųsti pranešimą",
            },
        ),
    ):

        await ctx.defer(ephemeral=True)

        current_lang = await get_language(ctx.user.id)

        if not await require_admin(ctx):
            logger.info(
                f"{ctx.user.name}({ctx.user.id}) used admin command without permissions"
            )
            return

        try:
            if schedule_time:
                schedule_unix = await parse_and_validate_schedule(ctx, schedule_time)
                if not schedule_unix:
                    return

                scheduler.add_job(
                    send_ticket_panel_message,
                    trigger="date",
                    run_date=datetime.fromtimestamp(schedule_unix, tz=timezone.utc),
                    args=[selected_channel.id if selected_channel else ctx.channel.id],
                    misfire_grace_time=3600,
                )

                embed = discord.Embed(
                    title=f"{lang_constants.SUCCESS_EMOJI} {_('common.success', current_lang)}",
                    description=f"{_('tickets.ticket_panel_scheduled', current_lang).format(timestamp=f'<t:{int(schedule_unix)}:F>', relative_time=f'<t:{int(schedule_unix)}:R>')}",
                    color=discord.Color.green(),
                )

                await ctx.followup.send(
                    embed=embed,
                    ephemeral=True,
                    delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
                )

                logger.info(f"Admin {ctx.user.name}({ctx.user.id}) sent ticket panel")
            else:
                await send_ticket_panel_message(
                    selected_channel.id if selected_channel else ctx.channel.id
                )

                embed = discord.Embed(
                    title=f"{lang_constants.SUCCESS_EMOJI} {_('common.success', current_lang)}",
                    color=discord.Color.green(),
                )

                await ctx.followup.send(
                    embed=embed,
                    ephemeral=True,
                    delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
                )

                logger.info(f"Admin {ctx.user.name}({ctx.user.id}) sent ticket panel")
        except discord.errors.NotFound:
            logger.error(
                f"{ctx.user.name}({ctx.user.id}) used admin command to send ticket panel, but the channel was not found"
            )
            await ctx.followup.send(
                f"{lang_constants.ERROR_EMOJI} Channel not found.",
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
        except Exception as e:
            logger.error(f"Error in send_ticket_panel: {e}")
            await ctx.followup.send(
                f"{lang_constants.ERROR_EMOJI} An error occurred: {e}",
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )


def setup(bot: commands.Bot):
    bot.add_cog(sendTicketPanel(bot))
