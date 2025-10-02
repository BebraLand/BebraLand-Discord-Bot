import discord
from discord.ext import commands
from src.utils.logger import get_cool_logger
from src.utils.welcome import sent_welcome_message
import json

logger = get_cool_logger("on_member_join.py")

class on_member_join(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        with open("src/languages/messages/welcome_message.json", "r", encoding="utf-8") as f:
            self.messages = json.load(f)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        logger.info(f"{member.name}({member.id}) Joined {member.guild.name}({member.guild.id})")
        await sent_welcome_message(member, self.bot)

def setup(bot: commands.Bot):
    bot.add_cog(on_member_join(bot))
