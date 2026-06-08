import discord
from pycord.multicog import Bot

from config.config import config as bot_config
from config.config import validate_config
from src.api.health import HealthAPI
from src.languages.localize import setup_i18n
from src.lifecycle import bootstrap_bot
from src.utils.bot_instance import set_bot
from src.utils.load_extensions import load_extensions
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)

validate_config(bot_config)

bot = Bot(intents=discord.Intents.all(), prefix=bot_config.bot.prefix)
set_bot(bot)
i18n, _ = setup_i18n(bot)


@bot.event
async def on_ready():
    logger.info(f"{bot.user} is ready and online!")
    await bootstrap_bot(bot)


load_extensions(bot)

# Localize all registered commands (names/descriptions/options)
i18n.localize_commands()

# Initialize and start health API server if enabled
if bot_config.health.enabled:
    health_api = HealthAPI(bot, port=bot_config.health.port)
    health_api.start()


if __name__ == "__main__":
    bot.run(bot_config.bot.token)
