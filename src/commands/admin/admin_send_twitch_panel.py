import discord
from discord.ext import commands
from discord import Option
from src.utils.logger import get_cool_logger
from src.utils.auth import require_admin
from pycord.multicog import subcommand
from src.features.twitch.view.TwitchPanel import build_twitch_panel_embed
from src.features.twitch.view.TwitchPanel import TwitchPanel


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

        await ctx.delete()

        await ctx.send(embed=build_twitch_panel_embed(ctx), view=TwitchPanel())

        logger.info(
            f"Admin {ctx.user.name}({ctx.user.id}) sent twitch panel"
        )


def setup(bot: commands.Bot):
    bot.add_cog(sendTwitchPanel(bot))
