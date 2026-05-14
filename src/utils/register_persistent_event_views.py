import time

from src.features.events.service import (
    is_check_in_open,
    refresh_event_message,
    schedule_event_check_in_open,
    schedule_event_reminders,
    schedule_event_start_notification,
)
from src.features.events.view.EventRegistrationView import EventRegistrationView
from src.utils.database import get_db
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


async def register_persistent_event_views(bot):
    db = await get_db()
    events = await db.get_active_events()
    for event in events:
        if event["status"] == "open" and event["starts_at"] <= time.time():
            await db.set_event_status(event["id"], "started")
            event = await db.get_event(event["id"])
            await refresh_event_message(bot, event["id"])
        if event and event["status"] == "open":
            schedule_event_reminders(event)
            schedule_event_check_in_open(event)
            schedule_event_start_notification(event)
        if not event.get("message_id"):
            continue
        try:
            bot.add_view(
                EventRegistrationView(
                    event["id"],
                    disabled=event["status"] != "open",
                    check_in_enabled=event.get("check_in_enabled", False),
                    check_in_open=is_check_in_open(event),
                ),
                message_id=event["message_id"],
            )
        except Exception as e:
            logger.error(f"Failed to register event view #{event['id']}: {e}")
