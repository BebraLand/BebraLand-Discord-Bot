from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

DISCORD_ACTIVITY_NAME_LIMIT = 128


@dataclass(frozen=True)
class PresenceCandidate:
    kind: str
    name: str
    priority: int = 0
    url: Optional[str] = None


def truncate_presence_text(text: str, limit: int = DISCORD_ACTIVITY_NAME_LIMIT) -> str:
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    if limit <= 3:
        return "." * limit
    return f"{text[: limit - 3].rstrip()}..."


def build_twitch_candidate(
    twitch_username: str, display_name: Optional[str] = None
) -> PresenceCandidate:
    username = str(twitch_username).strip()
    label = str(display_name or username).strip()
    return PresenceCandidate(
        kind="streaming",
        name=truncate_presence_text(f"{label} is live on Twitch"),
        priority=100,
        url=f"https://twitch.tv/{username}",
    )


def build_minecraft_candidate(
    host: str,
    online_players: int,
    max_players: Optional[int] = None,
) -> PresenceCandidate:
    if max_players:
        text = f"Minecraft | {online_players}/{max_players} online"
    else:
        text = f"Minecraft | {online_players} online"
    return PresenceCandidate(
        kind="playing",
        name=truncate_presence_text(text),
        priority=60,
    )


def build_event_candidate(event: Mapping[str, Any]) -> PresenceCandidate:
    title = str(event.get("title") or "BebraLand event").strip()
    status = str(event.get("status") or "open").lower()
    is_started = status == "started"
    return PresenceCandidate(
        kind="watching",
        name=truncate_presence_text(
            f"Event now: {title}" if is_started else f"Event: {title}"
        ),
        priority=80 if is_started else 40,
    )


def build_fallback_candidates(raw_items: Iterable[Any]) -> list[PresenceCandidate]:
    candidates: list[PresenceCandidate] = []
    for item in raw_items:
        if isinstance(item, str):
            kind = "playing"
            text = item
        elif isinstance(item, Mapping):
            kind = str(item.get("type") or item.get("kind") or "playing")
            text = str(item.get("text") or item.get("name") or "").strip()
        else:
            continue
        if text:
            candidates.append(
                PresenceCandidate(
                    kind=kind.lower(),
                    name=truncate_presence_text(text),
                    priority=0,
                )
            )
    return candidates


def pick_presence_candidate(
    candidates: Iterable[PresenceCandidate],
    fallback_candidates: Optional[list[PresenceCandidate]] = None,
    fallback_index: int = 0,
) -> PresenceCandidate:
    valid_candidates = [candidate for candidate in candidates if candidate.name]
    if valid_candidates:
        return max(valid_candidates, key=lambda candidate: candidate.priority)

    if fallback_candidates:
        return fallback_candidates[fallback_index % len(fallback_candidates)]

    return PresenceCandidate("playing", "BebraLand", priority=0)
