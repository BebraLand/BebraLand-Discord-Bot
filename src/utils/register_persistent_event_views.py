from src.features.events.view.EventRegistrationView import EventRegistrationView
from src.utils.database import get_db
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


async def register_persistent_event_views(bot):
    db = await get_db()
    events = await db.get_open_events()
    for event in events:
        if not event.get("message_id"):
            continue
        try:
            bot.add_view(
                EventRegistrationView(event["id"]),
                message_id=event["message_id"],
            )
        except Exception as e:
            logger.error(f"Failed to register event view #{event['id']}: {e}")
