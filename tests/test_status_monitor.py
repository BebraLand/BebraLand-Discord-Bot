import unittest

from src.features.status.core import PresenceCandidate
from src.features.status.status_monitor import StatusMonitor


class FakeBot:
    def __init__(self):
        self.presence_updates = []

    async def change_presence(self, *, activity):
        self.presence_updates.append(activity)


class StatusMonitorTests(unittest.IsolatedAsyncioTestCase):
    async def test_update_once_skips_unchanged_presence(self):
        bot = FakeBot()
        monitor = StatusMonitor(bot)

        async def collect_candidates():
            return [PresenceCandidate("playing", "BebraLand", priority=60)]

        monitor._collect_candidates = collect_candidates
        monitor._fallback_candidates = lambda: []

        await monitor.update_once()
        await monitor.update_once()

        self.assertEqual(len(bot.presence_updates), 1)


if __name__ == "__main__":
    unittest.main()
