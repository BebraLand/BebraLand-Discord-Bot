import discord
from discord.ext import commands


class AdminGroup(commands.Cog):
    admin = discord.SlashCommandGroup(
        "admin",
        "Admin related commands",
        default_member_permissions=discord.Permissions(administrator=True),
        contexts={discord.InteractionContextType.guild},
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot


def setup(bot: commands.Bot):
    bot.add_cog(AdminGroup(bot))