from pycord.multicog import Bot
import discord
import os
from dotenv import load_dotenv
from src.utils.logger import get_cool_logger
from src.languages.localize import setup_i18n
from src.views.language_selector import LanguageSelector
from src.views.ticket_panel import TicketPanel
from src.utils.scheduler import get_scheduler
from src.utils.load_extensions import load_extensions
from src.api.health import HealthAPI
import config.constants as constants
from src.utils.database import get_db
from src.utils.create_ticket import CloseTicketView, TicketControlPanel


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
    # Initialize scheduler and rehydrate tasks to survive restarts
    try:
        scheduler = get_scheduler()
        await scheduler.initialize(bot)
        logger.info("✅ Scheduler initialized and tasks rehydrated")
    except Exception as e:
        logger.error(f"❌ Scheduler initialization failed: {e}")
    # Register persistent ticket views for existing tickets so components work after restarts
    try:
        db = await get_db()
        tickets = await db.get_all_tickets()
        registered = 0
        for t in tickets:
            channel_id = t.get("channel_id")
            if not channel_id:
                continue
            channel = bot.get_channel(channel_id)
            if not channel:
                continue
            try:
                user = channel.guild.get_member(int(t.get("user_id"))) or await bot.fetch_user(int(t.get("user_id")))
            except Exception:
                user = await bot.fetch_user(int(t.get("user_id")))

            if t.get("status") == "open":
                view = CloseTicketView(t.get("id"), user, t.get("issue") or "")
            else:
                view = TicketControlPanel(t.get("id"), user, t.get("issue") or "")

            bot.add_view(view)
            registered += 1

        logger.info(f"Registered persistent views for {registered} ticket(s)")
    except Exception as e:
        logger.error(f"Failed to register persistent ticket views: {e}")

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
