from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.utils.db_config import get_scheduler_database_url

scheduler = AsyncIOScheduler(
    jobstores={"default": SQLAlchemyJobStore(url=get_scheduler_database_url())}
)
