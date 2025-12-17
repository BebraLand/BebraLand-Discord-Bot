import discord
from discord.ext import commands
from discord import Option
from src.utils.logger import get_cool_logger
from src.utils.auth import require_admin
from src.utils.scheduler import get_scheduler
from pycord.multicog import subcommand
from src.features.twitch.view.TwitchPanel import build_twitch_panel_embed
from src.features.twitch.view.TwitchPanel import TwitchPanel
from src.languages import lang_constants as lang_constants
import config.constants as constants
from src.utils.get_embed_icon import get_embed_icon


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
                             description="Schedule time in HH:MM format",
                             required=False,
                             description_localizations={
                                 "ru": "Время планирования в формате HH:MM",
                                 "lt": "Planavimo laikas HH:MM formatu"
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
        target_channel = selected_channel or ctx.channel

        # If scheduling is requested
        if schedule_time:
            try:
                scheduler = get_scheduler()
                payload = {
                    "channel_id": target_channel.id,
                }
                await scheduler.schedule_twitch_panel(ctx.guild.id, schedule_time, payload)
                
                embed = discord.Embed(
                    title=f"{lang_constants.SUCCESS_EMOJI} Scheduled",
                    description=f"Twitch panel will be sent to {target_channel.mention} at {schedule_time}.",
                    color=constants.SUCCESS_EMBED_COLOR,
                )
                embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(ctx))
                await ctx.followup.send(embed=embed, ephemeral=True)
                
                logger.info(
                    f"Admin {ctx.user.name}({ctx.user.id}) scheduled twitch panel for {schedule_time} in {target_channel.name}"
                )
                return
                
            except ValueError as e:
                embed = discord.Embed(
                    title=f"{lang_constants.ERROR_EMOJI} Error",
                    description=f"Invalid time format. Please use HH:MM (00-23:00-59).\n{str(e)}",
                    color=constants.FAILED_EMBED_COLOR,
                )
                embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(ctx))
                await ctx.followup.send(embed=embed, ephemeral=True, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)
                return

        # Send immediately if not scheduling
        await target_channel.send(embed=build_twitch_panel_embed(ctx), view=TwitchPanel())

        # Confirm to admin
        await ctx.followup.send(f"{lang_constants.SUCCESS_EMOJI} Twitch panel sent successfully!", ephemeral=True)

        logger.info(
            f"Admin {ctx.user.name}({ctx.user.id}) sent twitch panel to {target_channel.name}"
        )


def setup(bot: commands.Bot):
    bot.add_cog(sendTwitchPanel(bot))
