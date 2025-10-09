import discord
from discord.ext import commands
from discord import Option
from src.utils.logger import get_cool_logger
from src.views.language_selector import LanguageSelector, build_language_selector_embed
from src.languages.localize import translate
from src.utils.database import get_language
from src.utils.auth import require_admin
from src.utils.scheduler import get_scheduler
import config.constants as constants
from src.commands.admin import admin_group


logger = get_cool_logger(__name__)


class adminLanguage(commands.Cog):
    # Bind shared admin group to this Cog so Discord registers subcommands
    admin_group = admin_group

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @admin_group.command(name="language_dropdown",
                         description="Send a language dropdown message to the current channel",
                         description_localizations={
                             "ru": "Отправить сообщение с выбором языка",
                             "lt": "Siųsti žymėjimo lango pranešimą"
                         }
                         )
    async def language_dropdown(self, ctx: discord.ApplicationContext,
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

        try:
            if not selected_channel:
                selected_channel = ctx.channel

            if schedule_time:
                # Schedule for later with strict HH:MM validation and persistence
                try:
                    scheduler = get_scheduler()
                    await scheduler.schedule_language_dropdown(ctx.guild.id, selected_channel.id, schedule_time)
                except ValueError:
                    current_lang = await get_language(ctx.user.id)
                    desc = translate(
                        "Invalid time format. Please use HH:MM (00-23:00-59).", current_lang)
                    embed = discord.Embed(
                        title=f"❌ {translate('Error', current_lang)}",
                        description=desc,
                        color=discord.Color.red(),
                    )

                    embed.set_footer(
                        text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=ctx.bot.user.avatar.url)

                    await ctx.respond(
                        embed=embed,
                        ephemeral=True,
                        delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
                    )
                    return

                logger.info(
                    f"{ctx.user.name}({ctx.user.id}) scheduled language dropdown in {selected_channel.name}({selected_channel.id}) at {schedule_time}")

                current_lang = await get_language(ctx.user.id)
                desc = translate("Language dropdown scheduled for {schedule_time}.", current_lang).format(
                    schedule_time=schedule_time
                )
                embed = discord.Embed(
                    title=f"✅ {translate('Success', current_lang)}",
                    description=desc,
                    color=discord.Color.green(),
                )

                embed.set_footer(
                    text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=ctx.bot.user.avatar.url)

                await ctx.followup.send(
                    embed=embed,
                    ephemeral=True,
                    delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
                )
            else:
                # Immediate send (current behavior preserved)
                await selected_channel.send(embed=build_language_selector_embed(ctx), view=LanguageSelector())

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
