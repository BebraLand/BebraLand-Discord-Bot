from src.utils.database import get_db
from src.features.tickets.view.CloseTicketView import CloseTicketView
from src.features.tickets.view.TicketControlPanel import TicketControlPanel
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


async def register_persistent_ticket_views(bot):
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
                view = TicketControlPanel(
                    t.get("id"), user, t.get("issue") or "")

            bot.add_view(view)
            registered += 1

        logger.info(f"Registered persistent views for {registered} ticket(s)")
    except Exception as e:
        logger.error(f"Failed to register persistent ticket views: {e}")
