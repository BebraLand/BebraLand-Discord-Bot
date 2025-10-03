import discord
import os
from dotenv import load_dotenv
from src.utils.logger import get_cool_logger

load_dotenv()
logger = get_cool_logger("main.py")

bot = discord.Bot(intents=discord.Intents.all(), prefix=os.getenv("DISCORD_PREFIX"))

@bot.event
async def on_ready():
    logger.info(f"{bot.user} is ready and online!")

def load_extensions():
    for folder in ["cogs", "events", "commands"]:
        folder_path = os.path.join("src", folder)
        for filename in os.listdir(folder_path):
            if filename.endswith(".py") and not filename.startswith("__"):
                module = f"src.{folder}.{filename[:-3]}"
                try:
                    bot.load_extension(module)
                    logger.info(f"✅ Loaded {module}")
                except Exception as e:
                    logger.error(f"❌ Failed to load {module}: {e}")

load_extensions()

@bot.slash_command(name="hello", description="Say hello to the bot")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond("Hey!")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
