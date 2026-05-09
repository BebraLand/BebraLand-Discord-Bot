from typing import Any, Dict, List, Optional, Protocol


class LanguageStorage(Protocol):
    async def get(self, user_id: str) -> Optional[str]: ...

    async def set(self, user_id: str, language: str) -> bool: ...

    async def remove(self, user_id: str) -> bool: ...

    async def initialize(self) -> bool: ...

    async def close(self) -> None: ...


class TicketStorage(Protocol):
    async def create_ticket(self, user_id: str, issue: str) -> Optional[int]: ...

    async def get_ticket(self, ticket_id: int) -> Optional[Dict[str, Any]]: ...

    async def get_ticket_by_channel(
        self, channel_id: int
    ) -> Optional[Dict[str, Any]]: ...

    async def ticket_count(self, user_id: str) -> int: ...

    async def close_ticket(self, ticket_id: int) -> bool: ...

    async def reopen_ticket(self, ticket_id: int) -> bool: ...

    async def update_ticket_channel(self, ticket_id: int, channel_id: int) -> bool: ...

    async def delete_ticket(self, ticket_id: int) -> bool: ...

    async def initialize(self) -> bool: ...

    async def close(self) -> None: ...


class ApplicationStorage(Protocol):
    async def create_application(
        self, user_id: str, guild_id: int, answers: List[Dict[str, Any]]
    ) -> Optional[int]: ...

    async def get_application(
        self, application_id: int
    ) -> Optional[Dict[str, Any]]: ...

    async def get_pending_application_by_user(
        self, user_id: str, guild_id: int
    ) -> Optional[Dict[str, Any]]: ...

    async def get_latest_application_by_user(
        self, user_id: str, guild_id: int
    ) -> Optional[Dict[str, Any]]: ...

    async def get_application_by_user_status(
        self, user_id: str, guild_id: int, status: str
    ) -> Optional[Dict[str, Any]]: ...

    async def get_pending_applications(self) -> List[Dict[str, Any]]: ...

    async def delete_decided_applications_older_than(self, cutoff_time: float) -> int: ...

    async def update_application_review_message(
        self, application_id: int, review_channel_id: int, review_message_id: int
    ) -> bool: ...

    async def decide_application(
        self,
        application_id: int,
        status: str,
        decided_by: str,
        reason: Optional[str] = None,
    ) -> bool: ...

    async def update_application_status(
        self,
        application_id: int,
        status: str,
        decided_by: str,
        reason: Optional[str] = None,
    ) -> bool: ...

    async def get_application_enabled(self, guild_id: int) -> bool: ...

    async def set_application_enabled(self, guild_id: int, enabled: bool) -> bool: ...

    async def initialize(self) -> bool: ...

    async def close(self) -> None: ...


class EventStorage(Protocol):
    async def create_event(
        self,
        guild_id: int,
        title: str,
        description: str,
        starts_at: float,
        languages: List[str],
        player_limit: int,
        created_by_id: str,
    ) -> Optional[int]: ...

    async def get_event(self, event_id: int) -> Optional[Dict[str, Any]]: ...

    async def get_open_events(self) -> List[Dict[str, Any]]: ...

    async def update_event_message(
        self, event_id: int, channel_id: int, message_id: int
    ) -> bool: ...

    async def set_event_status(self, event_id: int, status: str) -> bool: ...

    async def register_event_user(
        self,
        event_id: int,
        user_id: str,
        added_by_id: Optional[str] = None,
    ) -> Optional[str]: ...

    async def unregister_event_user(self, event_id: int, user_id: str) -> Optional[str]: ...

    async def remove_event_user(self, event_id: int, user_id: str) -> Optional[str]: ...

    async def get_event_registrations(
        self, event_id: int
    ) -> List[Dict[str, Any]]: ...

    async def close(self) -> None: ...


class TempVoiceChannelStorage(Protocol):
    async def create_temp_voice_channel(
        self,
        channel_id: int,
        owner_id: int,
        guild_id: int,
        control_message_id: Optional[int],
        created_at: float,
    ) -> bool: ...

    async def get_temp_voice_channel(
        self, channel_id: int
    ) -> Optional[Dict[str, Any]]: ...

    async def get_all_temp_voice_channels(
        self, guild_id: int
    ) -> List[Dict[str, Any]]: ...

    async def update_temp_voice_channel(
        self,
        channel_id: int,
        owner_id: Optional[int] = None,
        control_message_id: Optional[int] = None,
        permitted_users: Optional[List[int]] = None,
        permitted_roles: Optional[List[int]] = None,
        rejected_users: Optional[List[int]] = None,
        rejected_roles: Optional[List[int]] = None,
    ) -> bool: ...

    async def delete_temp_voice_channel(self, channel_id: int) -> bool: ...

    async def initialize(self) -> bool: ...

    async def close(self) -> None: ...
