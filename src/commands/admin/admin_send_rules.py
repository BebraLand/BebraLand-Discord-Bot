from datetime import datetime, timezone

import discord
from discord import Option
from discord.ext import commands
from pycord.multicog import subcommand

import config.constants as constants
import src.languages.lang_constants as lang_constants
from src.languages.localize import _
from src.utils.auth import require_admin
from src.utils.database import get_language
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger
from src.utils.schedule_utils import parse_and_validate_schedule
from src.utils.scheduler import scheduler
from src.utils.send.send_rules_panel import send_rules_panel

logger = get_cool_logger(__name__)


class AdminSendRules(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @subcommand("admin")
    @discord.slash_command(
        name="rules",
        description="Post the rules panel in a channel",
    )
    async def rules_admin(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel = Option(
            discord.TextChannel,
            name="channel",
            description="Channel to post the rules panel in",
            required=False,
            default=None,
        ),
        schedule_time: str = Option(
            str,
            name="schedule-time",
            name_localizations={"ru": "время-расписания", "lt": "suplanuotas-laikas"},
            description="Schedule time to send rules",
            description_localizations={
                "ru": "Запланированное время отправки правил",
                "lt": "Suplanuotas laikas siųsti taisykles",
            },
            required=False,
            default=None,
        ),
    ):
        await ctx.defer(ephemeral=True)

        if not await require_admin(ctx):
            logger.info(
                f"{ctx.user.name}({ctx.user.id}) used admin rules command without permissions"
            )
            return

        current_lang = await get_language(ctx.user.id)
        target_channel = channel or ctx.channel

        if schedule_time:
            schedule_unix = await parse_and_validate_schedule(ctx, schedule_time)
            if not schedule_unix:
                return

            scheduler.add_job(
                send_rules_panel,
                trigger="date",
                run_date=datetime.fromtimestamp(schedule_unix, tz=timezone.utc),
                args=[target_channel.id],
                misfire_grace_time=3600,
            )

            embed = discord.Embed(
                title=f"{lang_constants.SUCCESS_EMOJI} {_('common.success', current_lang)}",
                description=(
                    f"Rules panel will be sent to {target_channel.mention} "
                    f"at <t:{schedule_unix}:F> (<t:{schedule_unix}:R>)."
                ),
                color=constants.SUCCESS_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(ctx),
            )

            await ctx.followup.send(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
            logger.info(
                f"rules.admin_scheduled user_id={ctx.user.id} "
                f"guild_id={ctx.guild.id if ctx.guild else None} "
                f"channel_id={target_channel.id} unix={schedule_unix}"
            )
            return

        await send_rules_panel(target_channel.id)
        embed = discord.Embed(
            title=f"{lang_constants.SUCCESS_EMOJI} {_('common.success', current_lang)}",
            description=f"Rules panel sent to {target_channel.mention}.",
            color=constants.SUCCESS_EMBED_COLOR,
        )
        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=get_embed_icon(ctx),
        )
        await ctx.followup.send(
            embed=embed,
            ephemeral=True,
            delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
        )
        logger.info(
            f"rules.admin_sent user_id={ctx.user.id} "
            f"guild_id={ctx.guild.id if ctx.guild else None} "
            f"channel_id={target_channel.id}"
        )


def setup(bot: commands.Bot):
    bot.add_cog(AdminSendRules(bot))
