from typing import Protocol, Optional, List, Dict, Any


class LanguageStorage(Protocol):
    async def get(self, user_id: str) -> Optional[str]:
        ...

    async def set(self, user_id: str, language: str) -> bool:
        ...

    async def remove(self, user_id: str) -> bool:
        ...

    async def initialize(self) -> bool:
        ...

    async def close(self) -> None:
        ...

    # Scheduler task methods
    async def add_scheduled_task(self, task: Dict[str, Any]) -> Optional[int]:
        """Add a scheduled task and return its ID."""
        ...

    async def remove_scheduled_task(self, task_id: int) -> None:
        """Remove a scheduled task by ID."""
        ...

    async def get_all_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """Get all scheduled tasks."""
        ...

class TicketStorage(Protocol):
    async def create_ticket(self, user_id: str, issue: str) -> Optional[int]:
        ...

    async def get_ticket(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        ...

    async def get_ticket_by_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        ...

    async def ticket_count(self, user_id: str) -> int:
        ...    

    async def close_ticket(self, ticket_id: int) -> bool:
        ...

    async def reopen_ticket(self, ticket_id: int) -> bool:
        ...

    async def update_ticket_channel(self, ticket_id: int, channel_id: int) -> bool:
        ...

    async def delete_ticket(self, ticket_id: int) -> bool:
        ...

    async def initialize(self) -> bool:
        ...

    async def close(self) -> None:
        ...

class TwitchStorage(Protocol):
    async def subscribe_user(self, user_id: str) -> bool:
        """Subscribe a user to Twitch notifications."""
        ...

    async def unsubscribe_user(self, user_id: str) -> bool:
        """Unsubscribe a user from Twitch notifications."""
        ...

    async def is_subscribed(self, user_id: str) -> bool:
        """Check if a user is subscribed to Twitch notifications."""
        ...

    async def get_all_subscribers(self) -> List[str]:
        """Get all subscribed user IDs."""
        ...

    async def get_stream_status(self, discord_user_id: str) -> Optional[Dict[str, Any]]:
        """Get the stream status for a Discord user."""
        ...

    async def update_stream_status(self, discord_user_id: str, twitch_username: str, 
                                   is_live: bool, stream_id: Optional[str] = None,
                                   notification_message_id: Optional[int] = None,
                                   started_at: Optional[float] = None) -> bool:
        """Update or create stream status for a Discord user."""
        ...

    async def delete_stream_status(self, discord_user_id: str) -> bool:
        """Delete stream status for a Discord user."""
        ...

    async def get_all_streamers(self) -> List[Dict[str, Any]]:
        """Get all registered streamers (those who have stream status entries)."""
        ...

    async def initialize(self) -> bool:
        ...

    async def close(self) -> None:
        ...