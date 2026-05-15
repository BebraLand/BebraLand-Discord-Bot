import pytest

from src.features.status.core import PresenceCandidate
from src.features.status.status_monitor import StatusMonitor


class FakeBot:
    def __init__(self):
        self.activities = []

    async def change_presence(self, *, activity):
        self.activities.append(activity)


@pytest.mark.asyncio
async def test_status_monitor_skips_unchanged_presence(monkeypatch):
    bot = FakeBot()
    monitor = StatusMonitor(bot)

    async def collect_candidates():
        return []

    monkeypatch.setattr(monitor, "_collect_candidates", collect_candidates)
    monkeypatch.setattr(
        monitor,
        "_fallback_candidates",
        lambda: [PresenceCandidate("playing", "BebraLand", priority=0)],
    )

    await monitor.update_once()
    await monitor.update_once()

    assert len(bot.activities) == 1


@pytest.mark.asyncio
async def test_status_monitor_updates_when_presence_changes(monkeypatch):
    bot = FakeBot()
    monitor = StatusMonitor(bot)
    candidates = [
        PresenceCandidate("playing", "BebraLand", priority=0),
        PresenceCandidate("watching", "Event now: Spleef", priority=30),
    ]

    async def collect_candidates():
        candidate = candidates.pop(0)
        return [] if candidate.priority == 0 else [candidate]

    monkeypatch.setattr(monitor, "_collect_candidates", collect_candidates)
    monkeypatch.setattr(
        monitor,
        "_fallback_candidates",
        lambda: [PresenceCandidate("playing", "BebraLand", priority=0)],
    )

    await monitor.update_once()
    await monitor.update_once()

    assert len(bot.activities) == 2
