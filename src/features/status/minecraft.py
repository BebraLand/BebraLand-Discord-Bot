from __future__ import annotations

from typing import Any, Optional

from mcstatus import JavaServer


def _serialize_status_response(status: Any) -> dict[str, Any]:
    players = getattr(status, "players", None)
    version = getattr(status, "version", None)
    return {
        "players": {
            "online": getattr(players, "online", 0) or 0,
            "max": getattr(players, "max", None),
        },
        "version": {
            "name": getattr(version, "name", None),
            "protocol": getattr(version, "protocol", None),
        },
        "latency": getattr(status, "latency", None),
        "motd": getattr(status, "description", None),
    }


async def query_minecraft_status(
    host: str,
    port: int = 25565,
    timeout: float = 5.0,
) -> Optional[dict[str, Any]]:
    """Query Minecraft Java server status through mcstatus."""
    try:
        server = await JavaServer.async_lookup(f"{host}:{port}", timeout=timeout)
        status = await server.async_status(tries=1)
        return _serialize_status_response(status)
    except Exception:
        return None
