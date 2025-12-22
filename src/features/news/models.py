"""Data models for news broadcasting."""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class NewsContent:
    """Represents multilingual news content."""
    en: str
    ru: Optional[str] = None
    lt: Optional[str] = None
    embed_json: Optional[Dict[str, Any]] = None
    
    def get_for_locale(self, locale: str) -> str:
        """Get content for a specific locale, falling back to English."""
        if not locale:
            return self.en
        
        # Normalize locale: accept 'ru', 'ru_RU', 'ru-RU', etc.
        try:
            locale_short = str(locale).split('-')[0].split('_')[0].lower()
        except Exception:
            locale_short = str(locale).lower()
        
        # Check if the locale content is a dict (embed JSON)
        content = getattr(self, locale_short, None) or self.en
        if isinstance(content, dict):
            # Extract description from embed dict
            return content.get("description", "")
        return str(content) if content else self.en
    
    def get_embed_for_locale(self, locale: str) -> Optional[Dict[str, Any]]:
        """Get locale-specific embed JSON if it exists."""
        if not locale:
            return self.embed_json
        
        try:
            locale_short = str(locale).split('-')[0].split('_')[0].lower()
        except Exception:
            locale_short = str(locale).lower()
        
        # Check if locale content is a dict (embed)
        content = getattr(self, locale_short, None)
        if isinstance(content, dict):
            return content
        
        return self.embed_json
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NewsContent":
        """Create NewsContent from a dictionary (e.g., from modal or scheduler)."""
        return cls(
            en=data.get("en", ""),
            ru=data.get("ru"),
            lt=data.get("lt"),
            embed_json=data.get("embed_json")
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {"en": self.en}
        if self.ru:
            result["ru"] = self.ru
        if self.lt:
            result["lt"] = self.lt
        if self.embed_json:
            result["embed_json"] = self.embed_json
        return result


@dataclass
class BroadcastConfig:
    """Configuration for a news broadcast."""
    send_to_channels: bool = True
    send_to_users: bool = True
    role_id: Optional[int] = None
    send_ghost_ping: bool = True
    image_position: str = "Before"  # "Before" or "After"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BroadcastConfig":
        """Create BroadcastConfig from a dictionary."""
        return cls(
            send_to_channels=data.get("send_to_all_channels", True),
            send_to_users=data.get("send_to_all_users", True),
            role_id=data.get("role_id"),
            send_ghost_ping=data.get("send_ghost_ping", True),
            image_position=data.get("image_position", "Before")
        )


@dataclass
class BroadcastResult:
    """Result of a news broadcast operation."""
    success_count: int = 0
    fail_count: int = 0
    sent_channels: List[str] = field(default_factory=list)
    sent_users: List[str] = field(default_factory=list)
    failed_channels: List[tuple] = field(default_factory=list)
    failed_users: List[tuple] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    @property
    def total_attempted(self) -> int:
        """Total number of send attempts."""
        return self.success_count + self.fail_count
