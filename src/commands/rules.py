import discord
from discord.ext import commands

from src.utils.logger import get_cool_logger
from src.views.rules_panel import RulesView, build_rules_embed

logger = get_cool_logger(__name__)


class Rules(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(
        name="rules",
        description="Show the BebraLand rules link and quick summary",
    )
    async def rules(
        self,
        ctx: discord.ApplicationContext,
    ):
        logger.info(
            f"rules.command user_id={ctx.user.id} "
            f"guild_id={ctx.guild.id if ctx.guild else None}"
        )
        await ctx.respond(
            embed=build_rules_embed(ctx),
            view=RulesView(ctx),
            ephemeral=True,
        )


def setup(bot: commands.Bot):
    bot.add_cog(Rules(bot))
