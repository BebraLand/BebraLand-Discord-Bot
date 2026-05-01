import re
from datetime import datetime
from typing import Any


def normalize_unix_timestamp(value: Any, require_future: bool = True) -> int:
    """
    Normalize Unix timestamp input to seconds.
    Supports:
    - seconds (10-digit)
    - milliseconds (13-digit)
    - microseconds (16-digit)
    - nanoseconds (19-digit)
    - Discord timestamp tag format: <t:1777217700:F>
    """
    raw = str(value).strip()
    if not raw:
        raise ValueError("Invalid time format; expected Unix timestamp")

    # Accept Discord timestamp tag input.
    if raw.startswith("<t:"):
        match = re.match(r"^<t:(\d+)(?::[tTdDfFR])?>$", raw)
        if not match:
            raise ValueError("Invalid time format; expected Unix timestamp")
        raw = match.group(1)

    try:
        timestamp = float(raw)
    except Exception:
        raise ValueError("Invalid time format; expected Unix timestamp")

    abs_ts = abs(timestamp)
    if abs_ts >= 1_000_000_000_000_000_000:
        timestamp = timestamp / 1_000_000_000
    elif abs_ts >= 1_000_000_000_000_000:
        timestamp = timestamp / 1_000_000
    elif abs_ts >= 1_000_000_000_000:
        timestamp = timestamp / 1_000

    normalized = int(timestamp)
    if normalized <= 0:
        raise ValueError("Unix timestamp must be greater than 0")

    if require_future and normalized <= int(datetime.now().timestamp()):
        raise ValueError("Unix timestamp must be in the future")

    return normalized
