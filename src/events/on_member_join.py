import discord
from discord.ext import commands
from src.utils.logger import get_cool_logger
import json

logger = get_cool_logger("on_member_join.py")

class on_member_join(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        with open("src/language/messages/welcome_message.json", "r", encoding="utf-8") as f:
            self.messages = json.load(f)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        message = self.messages.get("en", "Welcome to the server!")
        try:
            await member.send(message)
            logger.info(f"✅ Sent welcome message to {member.name}")
        except discord.Forbidden:
            logger.warning(f"⚠️ Can't send DM to {member.name} (forbidden).")

def setup(bot: commands.Bot):
    bot.add_cog(on_member_join(bot))
