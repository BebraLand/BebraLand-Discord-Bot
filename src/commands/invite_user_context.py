import discord
from discord.ext import commands
from src.utils.logger import get_cool_logger
from src.languages.localize import _
from src.utils.database import get_language
import config.constants as constants
from src.languages import lang_constants as lang_constants
from src.utils.embeds import get_embed_icon
from src.features.temp_voice_channels.invite_user import invite_user_to_channel


logger = get_cool_logger(__name__)


class invite_user_context(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.user_command(
        name="Invite to Voice Channel",
        name_localizations={
            "ru": "Пригласить в голосовой канал",
            "lt": "Pakviesti į balso kanalą",
        },
    )
    async def invite_to_voice(
        self, ctx: discord.ApplicationContext, user: discord.User
    ):
        await ctx.defer(ephemeral=True)

        current_lang = await get_language(ctx.user.id)

        # Check if the user is in a voice channel
        if not ctx.user.voice or not ctx.user.voice.channel:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
                description=_("temp_voice.errors.not_in_voice_channel", current_lang),
                color=constants.FAILED_EMBED_COLOR,
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
            return

        voice_channel = ctx.user.voice.channel

        # Use shared invite function
        success, embed = await invite_user_to_channel(
            inviter=ctx.user,
            target_user=user,
            voice_channel=voice_channel,
            inviter_lang=current_lang,
        )

        await ctx.followup.send(
            embed=embed,
            ephemeral=True,
            delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
        )

        logger.info(
            f"{ctx.user.name}({ctx.user.id}) invited {user.name}({user.id}) to channel {voice_channel.id}"
        )


def setup(bot: commands.Bot):
    bot.add_cog(invite_user_context(bot))
