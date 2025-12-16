from pycord.multicog import Bot
import discord
import os
from dotenv import load_dotenv
from src.utils.logger import get_cool_logger
from src.languages.localize import setup_i18n
from src.views.language_selector import LanguageSelector
from src.features.tickets.view.TicketPanel import TicketPanel
from src.utils.scheduler import get_scheduler
from src.utils.load_extensions import load_extensions
from src.utils.register_persistent_ticket_views import register_persistent_ticket_views
from src.features.twitch.view.TwitchPanel import TwitchPanel
from src.features.twitch.twitch_monitor import start_twitch_monitor
from src.storage.factory import get_storage
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
    bot.add_view(TicketPanel())
    bot.add_view(TwitchPanel())
    
    # Initialize scheduler and rehydrate tasks to survive restarts
    try:
        scheduler = get_scheduler()
        await scheduler.initialize(bot)
        logger.info("✅ Scheduler initialized and tasks rehydrated")
    except Exception as e:
        logger.error(f"❌ Scheduler initialization failed: {e}")
    
    # Register persistent ticket views for existing tickets so components work after restarts
    await register_persistent_ticket_views(bot)
    
    # Initialize Twitch streamers in database
    await initialize_twitch_streamers()
    
    # Start Twitch monitor
    try:
        client_id = os.getenv("TWITCH_CLIENT_ID")
        client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        
        if client_id and client_secret:
            await start_twitch_monitor(bot, client_id, client_secret)
        else:
            logger.warning("⚠️ Twitch credentials not found in .env or constants.py - Twitch monitor not started")
    except Exception as e:
        logger.error(f"❌ Twitch monitor initialization failed: {e}")


async def initialize_twitch_streamers():
    """Initialize Twitch streamers in database from constants."""
    try:
        storage = get_storage()
        
        for discord_user_id, twitch_username in constants.TWITCH_STREAMERS.items():
            # Check if streamer already exists in DB
            status = await storage.get_stream_status(str(discord_user_id))
            
            if not status:
                # Create initial entry for this streamer
                await storage.update_stream_status(
                    discord_user_id=str(discord_user_id),
                    twitch_username=twitch_username,
                    is_live=False,
                    stream_id=None,
                    notification_message_id=None,
                    started_at=None
                )
                logger.info(f"✅ Initialized Twitch streamer: {twitch_username} ({discord_user_id})")
            else:
                # Update username if it changed
                if status["twitch_username"] != twitch_username:
                    await storage.update_stream_status(
                        discord_user_id=str(discord_user_id),
                        twitch_username=twitch_username,
                        is_live=status["is_live"],
                        stream_id=status.get("stream_id"),
                        notification_message_id=status.get("notification_message_id"),
                        started_at=status.get("started_at")
                    )
                    logger.info(f"✅ Updated Twitch username for {discord_user_id}: {status['twitch_username']} -> {twitch_username}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Twitch streamers: {e}")

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


@bot.slash_command(name="clear", description="Delete a number of messages from this channel")
async def clear(ctx, amount: int):
    await ctx.response.defer(ephemeral=True)

    deleted = await ctx.channel.purge(limit=amount)

    await ctx.followup.send(f"✅ Deleted {len(deleted)} messages.", ephemeral=True, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)


bot.run(os.getenv("DISCORD_BOT_TOKEN"))
