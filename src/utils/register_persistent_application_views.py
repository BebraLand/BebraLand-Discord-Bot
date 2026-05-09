from src.features.applications.view.ApplicationReviewView import ApplicationReviewView
from src.utils.database import get_db
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


async def register_persistent_application_views(bot):
    try:
        db = await get_db()
        applications = await db.get_pending_applications()
        registered = 0
        for application in applications:
            bot.add_view(ApplicationReviewView(application["id"]))
            registered += 1

        logger.info(f"Registered persistent views for {registered} application(s)")
    except Exception as e:
        logger.error(f"Failed to register persistent application views: {e}")
