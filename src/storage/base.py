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