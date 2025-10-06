import discord
from discord.ext import commands
from src.utils.logger import get_cool_logger
from src.utils.auth import require_admin
import config.constants as constants


logger = get_cool_logger(__name__)


class admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(name="admin",
                            default_member_permissions=discord.Permissions(administrator=True),
                            contexts={discord.InteractionContextType.guild},
                            description="Admin commands",
                            description_localizations={
                                "ru": "Административные команды",
                                "lt": "Administracijos komandos"
                            },)
    async def admin(self, ctx: discord.ApplicationContext):
        if not await require_admin(ctx):
            logger.info(f"{ctx.user.name}({ctx.user.id}) used admin command without permissions")
            return

        await ctx.defer()
        logger.info(f"{ctx.user.name}({ctx.user.id}) used admin command")
        await ctx.respond("Admin command used!", ephemeral=True, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)


def setup(bot: commands.Bot):
    bot.add_cog(admin(bot))
