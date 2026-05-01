import discord
from discord.ext import commands
from discord import Option
from src.utils.logger import get_cool_logger
from src.utils.auth import require_admin
from pycord.multicog import subcommand
from src.languages.localize import _
from src.utils.database import get_language
from src.languages import lang_constants as lang_constants
import config.constants as constants
from src.utils.embeds import get_embed_icon
from src.utils.scheduler import scheduler
from src.utils.schedule_utils import parse_and_validate_schedule
from src.utils.send.send_twitch_panel import send_twitch_panel
from datetime import datetime, timezone


logger = get_cool_logger(__name__)


class sendTwitchPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @subcommand("admin")
    @discord.slash_command(
        name="send_twitch_panel",
        description="Send the Twitch panel to the channel",
        description_localizations={
            "ru": "Отправить панель Twitch в канал",
            "lt": "Siųsti Twitch skydelį į kanalą"
        }

    )
    async def send_twitch_panel(
        self,
        ctx: discord.ApplicationContext,
        schedule_time=Option(str,
                             description="Schedule time as Unix UTC timestamp",
                             required=False,
                             description_localizations={
                                 "ru": "Время планирования в формате Unix UTC timestamp",
                                 "lt": "Planavimo laikas Unix UTC timestamp formatu"
                             }),
        selected_channel=Option(discord.TextChannel,
                                description="Channel to send the message to",
                                required=False,
                                description_localizations={
                                    "ru": "Канал, куда отправить сообщение",
                                    "lt": "Kanalas, į kurį siųsti pranešimą"
                                })):

        await ctx.defer(ephemeral=True)

        if not await require_admin(ctx):
            logger.info(
                f"{ctx.user.name}({ctx.user.id}) used admin command without permissions")
            return

        # Use selected channel or current channel
        target_channel = selected_channel.id if selected_channel else ctx.channel.id

        current_lang = await get_language(ctx.user.id)

        # If scheduling is requested
        if schedule_time:
            schedule_unix = await parse_and_validate_schedule(ctx, schedule_time)
            if not schedule_unix:
                return

            scheduler.add_job(
                send_twitch_panel,
                trigger="date",
                run_date=datetime.fromtimestamp(
                    schedule_unix, tz=timezone.utc),
                args=[target_channel],
                misfire_grace_time=3600
            )
            embed = discord.Embed(
                title=f"{lang_constants.SUCCESS_EMOJI} Scheduled",
                description=f"Twitch panel will be sent to <#{target_channel}> at <t:{schedule_unix}:F> <t:{schedule_unix}:R>.",
                color=constants.SUCCESS_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(ctx))
            await ctx.followup.send(embed=embed, ephemeral=True)

            logger.info(
                f"Admin {ctx.user.name}({ctx.user.id}) scheduled twitch panel for unix {schedule_unix} in channel {target_channel}"
            )
            return

        # Send immediately if not scheduling
        await send_twitch_panel(target_channel)

        # Confirm to admin
        embed = discord.Embed(
            title=f"{lang_constants.SUCCESS_EMOJI} {_('common.success', current_lang)}",
            description=f"Twitch panel sent to <#{target_channel}> successfully!",
            color=constants.SUCCESS_EMBED_COLOR
        )
        await ctx.followup.send(embed=embed, ephemeral=True, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)

        logger.info(
            f"Admin {ctx.user.name}({ctx.user.id}) sent twitch panel to channel {target_channel}"
        )


def setup(bot: commands.Bot):
    bot.add_cog(sendTwitchPanel(bot))
