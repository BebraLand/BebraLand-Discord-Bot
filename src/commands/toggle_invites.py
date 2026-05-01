import discord
from discord.ext import commands
from src.utils.logger import get_cool_logger
from src.languages.localize import _
from src.utils.database import get_language, get_db
import config.constants as constants
from src.languages import lang_constants as lang_constants
from src.utils.embeds import get_embed_icon


logger = get_cool_logger(__name__)


class toggle_invites(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(
        name="toggle_invites",
        description="Toggle whether you can receive voice channel invites",
        description_localizations={
            "ru": "Переключить возможность получать приглашения в голосовые каналы",
            "lt": "Perjungti galimybę gauti kvietimus į balso kanalus",
        },
    )
    async def toggle_invites(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)

        current_lang = await get_language(ctx.user.id)

        # Toggle the invite preference
        db = await get_db()
        invites_blocked = await db.toggle_invite_preference(ctx.user.id)

        if invites_blocked:
            # User just disabled invites
            description_text = _("temp_voice.toggle_invites.disabled", current_lang)
            title = f"{lang_constants.ERROR_EMOJI} {_('temp_voice.toggle_invites.invites_disabled', current_lang)}"
            color = constants.FAILED_EMBED_COLOR
        else:
            # User just enabled invites
            description_text = _("temp_voice.toggle_invites.enabled", current_lang)
            title = f"{lang_constants.SUCCESS_EMOJI} {_('temp_voice.toggle_invites.invites_enabled', current_lang)}"
            color = constants.SUCCESS_EMBED_COLOR

        embed = discord.Embed(
            title=title,
            description=description_text,
            color=color,
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
            f"{ctx.user.name}({ctx.user.id}) toggled invite preference to blocked={invites_blocked}"
        )


def setup(bot: commands.Bot):
    bot.add_cog(toggle_invites(bot))
