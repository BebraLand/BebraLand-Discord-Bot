import json

import discord
from discord.ext import commands

import config.constants as constants
from src.languages import lang_constants as lang_constants
from src.utils.logger import get_cool_logger
from src.utils.welcome import sent_welcome_message

logger = get_cool_logger(__name__)


class on_member_join(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        with open(
            "src/languages/messages/welcome_message.json", "r", encoding="utf-8"
        ) as f:
            self.messages = json.load(f)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        logger.info(
            f"{member.name}({member.id}) Joined {member.guild.name}({member.guild.id})"
        )
        if not constants.USER_WELCOME_ENABLED:
            logger.info(
                f"{lang_constants.MUTED_BELL_EMOJI} Skipping src.events.on_member_join (disabled by config.constants)"
            )
            return

        await sent_welcome_message(member, self.bot)


def setup(bot: commands.Bot):
    bot.add_cog(on_member_join(bot))
