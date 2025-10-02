import logging
import sys
from typing import Optional

# ANSI color codes for a vibrant console experience
COLORS = {
    "DEBUG": "\033[94m",     # Blue
    "INFO": "\033[92m",      # Green
    "WARNING": "\033[93m",   # Yellow
    "ERROR": "\033[91m",     # Red
    "CRITICAL": "\033[95m",  # Magenta
    "RESET": "\033[0m"
}

class CoolFormatter(logging.Formatter):
    """Custom formatter to inject color and emoji flair."""
    def format(self, record: logging.LogRecord) -> str:
        log_color = COLORS.get(record.levelname, COLORS["RESET"])
        emoji = {
            "DEBUG": "🔍",
            "INFO": "✨",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "CRITICAL": "💀"
        }.get(record.levelname, "📝")
        record.levelname = f"{log_color}{emoji} {record.levelname}{COLORS['RESET']}"
        return super().format(record)

def get_cool_logger(name: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """Return a pre-configured, stylish console logger."""
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        return logger  # Already set up

    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        CoolFormatter(
            fmt="%(asctime)s | %(levelname)-10s | %(name)s | %(message)s",
            datefmt="%H:%M:%S"
        )
    )
    logger.addHandler(handler)
    logger.propagate = False
    return logger
