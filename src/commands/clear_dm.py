import discord
from discord.ext import commands
from src.utils.logger import get_cool_logger
from src.languages.localize import translate
from src.utils.database import get_language
import config.constants as constants


logger = get_cool_logger(__name__)


class clear_dm(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(name="clear_dm",
                            description="Clear the bot's DM",
                            description_localizations={
                                "ru": "Очистить DM с ботом",
                                "lt": "Išvalyti DM su botu"
                            },)
    async def clear_dm(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)

        current_lang = await get_language(ctx.user.id)
        dm_channel = await ctx.user.create_dm()

        deleted_count = 0
        try:
            async for message in dm_channel.history(limit=constants.CLEAR_COMMAND_LIMIT):
                if message.author.id == ctx.bot.user.id:
                    try:
                        await message.delete()
                        deleted_count += 1
                    except discord.HTTPException:
                        # Ignore messages that can't be deleted (permissions/age/etc.)
                        pass
        except Exception as e:
            logger.exception("Failed to clear DM messages", exc_info=e)

        if deleted_count > 0:
            description_text = translate(
                "Removed {count} messages previously sent by the bot in your DMs.",
                current_lang,
            ).format(count=deleted_count)
        else:
            description_text = translate("No messages previously sent by the bot in your DMs.", current_lang)

        embed = discord.Embed(
            title=f"✅ {translate('Success', current_lang)}",
            description=description_text,
            color=discord.Color.green(),
        )
        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=ctx.bot.user.display_avatar.url,
        )

        await ctx.followup.send(
            embed=embed,
            ephemeral=True,
            delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
        )
        logger.info(
            f"{ctx.user.name}({ctx.user.id}) cleared the bot's DM; deleted={deleted_count}"
        )


def setup(bot: commands.Bot):
    bot.add_cog(clear_dm(bot))
