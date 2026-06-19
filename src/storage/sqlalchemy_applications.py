import time
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select, update

from src.utils.logger import get_cool_logger

from .models import Application

logger = get_cool_logger(__name__)


class SQLAlchemyApplicationMixin:
    @staticmethod
    def _application_to_dict(application: Application) -> Dict[str, Any]:
        return {
            "id": application.id,
            "user_id": application.user_id,
            "guild_id": application.guild_id,
            "answers": application.answers or [],
            "status": application.status,
            "review_channel_id": application.review_channel_id,
            "review_message_id": application.review_message_id,
            "created_at": application.created_at,
            "decided_at": application.decided_at,
            "decided_by": application.decided_by,
            "decision_reason": application.decision_reason,
        }

    async def create_application(
        self, user_id: str, guild_id: int, answers: List[Dict[str, Any]]
    ) -> Optional[int]:
        """Create a new pending application and return its ID."""
        try:
            async with self.session_factory() as session:
                application = Application(
                    user_id=user_id,
                    guild_id=guild_id,
                    answers=answers,
                    created_at=time.time(),
                    status="pending",
                )
                session.add(application)
                await session.commit()
                await session.refresh(application)
                return application.id
        except Exception as e:
            logger.error(f"Failed to create application: {e}")
            return None

    async def get_application(self, application_id: int) -> Optional[Dict[str, Any]]:
        """Get an application by ID."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Application).where(Application.id == application_id)
                )
                application = result.scalar_one_or_none()
                return self._application_to_dict(application) if application else None
        except Exception as e:
            logger.error(f"Failed to get application {application_id}: {e}")
            return None

    async def get_pending_application_by_user(
        self, user_id: str, guild_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get a user's pending application for a guild."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Application)
                    .where(
                        Application.user_id == user_id,
                        Application.guild_id == guild_id,
                        Application.status == "pending",
                    )
                    .order_by(Application.created_at.desc())
                )
                application = result.scalars().first()
                return self._application_to_dict(application) if application else None
        except Exception as e:
            logger.error(f"Failed to get pending application for {user_id}: {e}")
            return None

    async def get_latest_application_by_user(
        self, user_id: str, guild_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get a user's latest application for a guild."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Application)
                    .where(
                        Application.user_id == user_id,
                        Application.guild_id == guild_id,
                    )
                    .order_by(Application.created_at.desc())
                )
                application = result.scalars().first()
                return self._application_to_dict(application) if application else None
        except Exception as e:
            logger.error(f"Failed to get latest application for {user_id}: {e}")
            return None

    async def get_application_by_user_status(
        self, user_id: str, guild_id: int, status: str
    ) -> Optional[Dict[str, Any]]:
        """Get a user's latest application with a specific status."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Application)
                    .where(
                        Application.user_id == user_id,
                        Application.guild_id == guild_id,
                        Application.status == status,
                    )
                    .order_by(Application.created_at.desc())
                )
                application = result.scalars().first()
                return self._application_to_dict(application) if application else None
        except Exception as e:
            logger.error(f"Failed to get {status} application for user {user_id}: {e}")
            return None

    async def get_pending_applications(self) -> List[Dict[str, Any]]:
        """Return all pending applications."""
        applications = []
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Application).where(Application.status == "pending")
                )
                for application in result.scalars():
                    applications.append(self._application_to_dict(application))
        except Exception as e:
            logger.error(f"Failed to fetch pending applications: {e}")
        return applications

    async def delete_decided_applications_older_than(self, cutoff_time: float) -> int:
        """Delete rejected/revoked applications decided before cutoff_time."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    delete(Application).where(
                        Application.status.in_(("rejected", "revoked")),
                        Application.decided_at.is_not(None),
                        Application.decided_at < cutoff_time,
                    )
                )
                await session.commit()
                return result.rowcount or 0
        except Exception as e:
            logger.error(f"Failed to clean old decided applications: {e}")
            return 0

    async def update_application_review_message(
        self, application_id: int, review_channel_id: int, review_message_id: int
    ) -> bool:
        """Attach the Discord review message to an application."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    update(Application)
                    .where(Application.id == application_id)
                    .values(
                        review_channel_id=review_channel_id,
                        review_message_id=review_message_id,
                    )
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(
                f"Failed to update review message for application {application_id}: {e}"
            )
            return False

    async def decide_application(
        self,
        application_id: int,
        status: str,
        decided_by: str,
        reason: Optional[str] = None,
    ) -> bool:
        """Mark a pending application as accepted or rejected."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    update(Application)
                    .where(
                        Application.id == application_id,
                        Application.status == "pending",
                    )
                    .values(
                        status=status,
                        decided_at=time.time(),
                        decided_by=decided_by,
                        decision_reason=reason,
                    )
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to decide application {application_id}: {e}")
            return False

    async def update_application_status(
        self,
        application_id: int,
        status: str,
        decided_by: str,
        reason: Optional[str] = None,
    ) -> bool:
        """Update an application status regardless of its current state."""
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    update(Application)
                    .where(Application.id == application_id)
                    .values(
                        status=status,
                        decided_at=time.time(),
                        decided_by=decided_by,
                        decision_reason=reason,
                    )
                )
                await session.commit()
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update application {application_id}: {e}")
            return False

    async def get_application_enabled(self, guild_id: int) -> bool:
        """Get whether applications are enabled for a guild."""
        value = await self._get_guild_setting(guild_id, "applications.enabled", True)
        return bool(value)

    async def set_application_enabled(self, guild_id: int, enabled: bool) -> bool:
        """Set whether applications are enabled for a guild."""
        return await self._set_guild_setting(
            guild_id, "applications.enabled", bool(enabled)
        )
