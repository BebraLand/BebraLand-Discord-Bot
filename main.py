from pycord.multicog import Bot
import discord
import os
from dotenv import load_dotenv
from src.utils.logger import get_cool_logger
from src.languages.localize import setup_i18n
from src.views.language_selector import LanguageSelector
from src.features.tickets.view.TicketPanel import TicketPanel
from src.features.twitch.view.TwitchPanel import TwitchPanel
from src.utils.scheduler import get_scheduler
from src.utils.load_extensions import load_extensions
from src.utils.register_persistent_ticket_views import register_persistent_ticket_views
from src.features.twitch.twitch_monitor import get_twitch_monitor
from src.features.temp_voice_channels.restore_temp_channels import restore_temp_channels
from src.api.health import HealthAPI
import config.constants as constants
import src.languages.lang_constants as lang_constants


load_dotenv()
logger = get_cool_logger(__name__)

bot = Bot(intents=discord.Intents.all(),
          prefix=os.getenv("DISCORD_PREFIX"))

# Initialize gettext-based i18n (no longer uses pycord.i18n)
_, _ = setup_i18n(bot)


@bot.event
async def on_ready():
    logger.info(f"{bot.user} is ready and online!")
    bot.add_view(LanguageSelector())
    bot.add_view(TicketPanel())
    bot.add_view(TwitchPanel())
    
    # Initialize scheduler and rehydrate tasks to survive restarts
    try:
        scheduler = get_scheduler()
        await scheduler.initialize(bot)
        logger.info(f"{lang_constants.SUCCESS_EMOJI} Scheduler initialized and tasks rehydrated")
    except Exception as e:
        logger.error(f"{lang_constants.ERROR_EMOJI} Scheduler initialization failed: {e}")
    
    # Register persistent ticket views for existing tickets so components work after restarts
    await register_persistent_ticket_views(bot)
    
    # Restore temp voice channels and their control panels
    try:
        await restore_temp_channels(bot)
        logger.info(f"{lang_constants.SUCCESS_EMOJI} Temp voice channels restored")
    except Exception as e:
        logger.error(f"{lang_constants.ERROR_EMOJI} Temp voice channels restoration failed: {e}")
    
    # Start Twitch live monitor
    try:
        twitch_monitor = get_twitch_monitor(bot)
        await twitch_monitor.start()
        logger.info(f"{lang_constants.SUCCESS_EMOJI} Twitch monitor started")
    except Exception as e:
        logger.error(f"{lang_constants.ERROR_EMOJI} Twitch monitor initialization failed: {e}")

load_extensions(bot)

# Note: With gettext, command localization is handled differently
# No need for i18n.localize_commands() as we're using standard gettext

# Initialize and start health API server if enabled
if constants.HEALTH_API_ENABLED:
    health_api = HealthAPI(bot, port=constants.HEALTH_API_PORT)
    health_api.start()


@bot.slash_command(name="hello", description="Say hello to the bot")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond("Hey!")


@bot.slash_command(name="clear", description="Delete a number of messages from this channel")
async def clear(ctx, amount: int):
    await ctx.response.defer(ephemeral=True)

    deleted = await ctx.channel.purge(limit=amount)

    await ctx.followup.send(f"{lang_constants.SUCCESS_EMOJI} Deleted {len(deleted)} messages.", ephemeral=True, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)


bot.run(os.getenv("DISCORD_BOT_TOKEN"))
