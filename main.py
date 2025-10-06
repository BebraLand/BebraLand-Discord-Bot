import discord
import os
from dotenv import load_dotenv
from src.utils.logger import get_cool_logger
from src.languages.localize import setup_i18n
from src.views.language_selector import LanguageSelector
import config.command as COMMAND_ENABLED

load_dotenv()
logger = get_cool_logger(__name__)

bot = discord.Bot(intents=discord.Intents.all(), prefix=os.getenv("DISCORD_PREFIX"))
i18n, _ = setup_i18n(bot)

@bot.event
async def on_ready():
    logger.info(f"{bot.user} is ready and online!")
    bot.add_view(LanguageSelector())

def load_extensions():
    for folder in ["cogs", "events", "commands"]:
        folder_path = os.path.join("src", folder)
        for filename in os.listdir(folder_path):
            if filename.endswith(".py") and not filename.startswith("__"):
                # Respect command enable/disable flags
                if folder == "commands":
                    if filename == "set_lang.py" and not COMMAND_ENABLED.SET_LANG:
                        logger.info("🔕 Skipping src.commands.set_lang (disabled by config.command)")
                        continue
                    if filename == "clear_dm.py" and not COMMAND_ENABLED.CLEAR_DM:
                        logger.info("🔕 Skipping src.commands.clear_dm (disabled by config.command)")
                        continue
                module = f"src.{folder}.{filename[:-3]}"
                try:
                    bot.load_extension(module)
                    logger.info(f"✅ Loaded {module}")
                except Exception as e:
                    logger.error(f"❌ Failed to load {module}: {e}")

load_extensions()

# Localize all registered commands (names/descriptions/options)
i18n.localize_commands()

@bot.slash_command(name="hello", description="Say hello to the bot")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond("Hey!")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
