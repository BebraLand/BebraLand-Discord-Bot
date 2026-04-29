import discord
from discord.ext import commands
from discord import Option
from src.utils.logger import get_cool_logger
from src.languages import lang_constants as lang_constants
from src.languages.localize import _
from src.utils.database import get_language
from src.utils.auth import require_admin
from src.utils.scheduler import scheduler
from src.utils.normalize_unix import normalize_unix_timestamp
from src.utils.schedule_utils import parse_and_validate_schedule
from datetime import datetime, timezone
import config.constants as constants
from pycord.multicog import subcommand
from src.utils.embeds import get_embed_icon
from src.utils.send.send_language_dropdown import send_language_dropdown


logger = get_cool_logger(__name__)


class adminLanguage(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @subcommand("admin")
    @discord.slash_command(
        name="language_dropdown",
        description="Send a language dropdown message to the current channel",
        description_localizations={
            "ru": "Отправить сообщение с выбором языка",
            "lt": "Siųsti žymėjimo lango pranešimą"
        }
    )
    async def language_dropdown(self, ctx: discord.ApplicationContext,
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

        logger.debug(
            f"{ctx.user.name}({ctx.user.id}) invoked admin language dropdown command with schedule_time={schedule_time} and selected_channel={selected_channel}")

        if not await require_admin(ctx):
            logger.info(
                f"{ctx.user.name}({ctx.user.id}) used admin command without permissions")
            return

        try:
            if not selected_channel:
                selected_channel = ctx.channel

            if schedule_time:
                # Schedule for later with strict Unix timestamp validation and persistence
                schedule_unix = await parse_and_validate_schedule(ctx, schedule_time)
                if not schedule_unix:
                    return
                scheduler.add_job(
                    send_language_dropdown,
                    trigger="date",
                    run_date=datetime.fromtimestamp(schedule_unix, tz=timezone.utc),
                    args=[selected_channel.id],
                    misfire_grace_time=3600
                )

                logger.info(
                    f"{ctx.user.name}({ctx.user.id}) scheduled language dropdown in {selected_channel.name}({selected_channel.id}) at unix {schedule_unix}")

                current_lang = await get_language(ctx.user.id)
                timestamp_tag = f"<t:{schedule_unix}:F>"
                desc = _("language.dropdown_scheduled", current_lang).format(
                    schedule_time=timestamp_tag,
                    relative_time=f"(<t:{schedule_unix}:R>)"
                )
                embed = discord.Embed(
                    title=f"{lang_constants.SUCCESS_EMOJI} {_('common.success', current_lang)}",
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
            else:
                # Immediate send (current behavior preserved)
                await send_language_dropdown(selected_channel.id)

                logger.info(
                    f"{ctx.user.name}({ctx.user.id}) used admin command with language dropdown in {selected_channel.name}({selected_channel.id})")

                await ctx.respond("Language dropdown message sent!", ephemeral=True, delete_after=0)
                
        except discord.errors.NotFound:
            logger.error(
                f"{ctx.user.name}({ctx.user.id}) used admin command with language dropdown, but the channel was not found")
            await ctx.respond(
                "Language dropdown message not found. Please make sure the bot has permissions to send messages in this channel.",
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )

def setup(bot: commands.Bot):
    bot.add_cog(adminLanguage(bot))
