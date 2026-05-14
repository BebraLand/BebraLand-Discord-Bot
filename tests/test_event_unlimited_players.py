import unittest

from src.features.events.service import format_player_capacity
from src.storage.sqlalchemy_events import event_registration_status


class EventUnlimitedPlayersTests(unittest.TestCase):
    def test_zero_player_limit_formats_as_unlimited(self):
        self.assertEqual(format_player_capacity(7, 0), "7/unlimited")

    def test_positive_player_limit_formats_as_capacity(self):
        self.assertEqual(format_player_capacity(2, 5), "2/5")

    def test_zero_player_limit_keeps_everyone_main(self):
        self.assertEqual(event_registration_status(0, 0), "main")
        self.assertEqual(event_registration_status(50, 0), "main")

    def test_positive_player_limit_uses_backup_after_capacity(self):
        self.assertEqual(event_registration_status(1, 2), "main")
        self.assertEqual(event_registration_status(2, 2), "backup")


if __name__ == "__main__":
    unittest.main()
