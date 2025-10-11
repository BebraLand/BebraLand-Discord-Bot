from pycord.multicog import Bot
import discord
import os
from dotenv import load_dotenv
from src.utils.logger import get_cool_logger
from src.languages.localize import setup_i18n
from src.views.language_selector import LanguageSelector
from src.utils.scheduler import get_scheduler
from src.utils.load_extensions import load_extensions
from src.api.health import HealthAPI
import config.constants as constants


load_dotenv()
logger = get_cool_logger(__name__)

bot = Bot(intents=discord.Intents.all(),
                  prefix=os.getenv("DISCORD_PREFIX"))
i18n, _ = setup_i18n(bot)


@bot.event
async def on_ready():
    logger.info(f"{bot.user} is ready and online!")
    bot.add_view(LanguageSelector())
    # Initialize scheduler and rehydrate tasks to survive restarts
    try:
        scheduler = get_scheduler()
        await scheduler.initialize(bot)
        logger.info("✅ Scheduler initialized and tasks rehydrated")
    except Exception as e:
        logger.error(f"❌ Scheduler initialization failed: {e}")

load_extensions(bot)

# Localize all registered commands (names/descriptions/options)
i18n.localize_commands()

# Initialize and start health API server if enabled
if constants.HEALTH_API_ENABLED:
    health_api = HealthAPI(bot, port=constants.HEALTH_API_PORT)
    health_api.start()


@bot.slash_command(name="hello", description="Say hello to the bot")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond("Hey!")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
