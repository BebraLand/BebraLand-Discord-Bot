from typing import Protocol, Optional


class LanguageStorage(Protocol):
    async def get(self, user_id: str) -> Optional[str]:
        ...

    async def set(self, user_id: str, language: str) -> bool:
        ...