import discord
from discord.ext import commands
from src.utils.config_manager import load_config
import os
from dotenv import load_dotenv

load_dotenv()
config = load_config()
intents = discord.Intents.all()
bot = commands.Bot(
    command_prefix=config.get("DISCORD_PREFIX", "&"),
    intents=intents
)


@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")

    bot.load_extension('src.utils.welcomeMessage')
    bot.load_extension('src.commands.setWelcomeMessage')


@bot.slash_command(name="hello", description="Say hello to the bot")
async def hello(ctx):
    await ctx.respond("Hey!")


bot.run(os.getenv('DISCORD_BOT_TOKEN'))
