import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional

import aiofiles

from .base import LanguageStorage


logger = logging.getLogger(__name__)


class LocalFileStorage(LanguageStorage):
    """Local JSON file storage using aiofiles for non-blocking I/O."""

    def __init__(self, file_path: str = "data/user_languages.json"):
        self.file_path = Path(file_path)
        self.data: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> bool:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

            if self.file_path.exists():
                async with self._lock:
                    async with aiofiles.open(self.file_path, "r", encoding="utf-8") as f:
                        content = await f.read()
                        self.data = json.loads(content) if content else {}
            else:
                self.data = {}
                await self._save()

            logger.info(f"Local storage initialized: {self.file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize local storage: {e}")
            return False

    async def _save(self) -> None:
        async with aiofiles.open(self.file_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(self.data, indent=2, ensure_ascii=False))

    async def get(self, user_id: str) -> Optional[str]:
        async with self._lock:
            return self.data.get(user_id)

    async def set(self, user_id: str, language: str) -> bool:
        try:
            async with self._lock:
                self.data[user_id] = language
                await self._save()
            return True
        except Exception as e:
            logger.error(f"Failed to set language: {e}")
            return False

    async def remove(self, user_id: str) -> bool:
        try:
            async with self._lock:
                if user_id in self.data:
                    del self.data[user_id]
                    await self._save()
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to remove user: {e}")
            return False

    async def close(self) -> None:
        pass