import unittest

from src.features.events.admin_service import (
    clamp_event_list_limit,
    format_event_list_line,
    normalize_event_list_status,
)


class EventAdminListTests(unittest.TestCase):
    def test_normalize_event_list_status_defaults_to_active(self):
        self.assertEqual(normalize_event_list_status(None), "active")
        self.assertEqual(normalize_event_list_status("weird"), "active")

    def test_normalize_event_list_status_accepts_filters(self):
        self.assertEqual(normalize_event_list_status("all"), "all")
        self.assertEqual(normalize_event_list_status("open"), "open")
        self.assertEqual(normalize_event_list_status("cancelled"), "cancelled")

    def test_clamp_event_list_limit(self):
        self.assertEqual(clamp_event_list_limit(None), 10)
        self.assertEqual(clamp_event_list_limit(0), 1)
        self.assertEqual(clamp_event_list_limit(30), 25)

    def test_format_event_list_line_includes_core_details_and_links(self):
        line = format_event_list_line(
            {
                "id": 9,
                "guild_id": 123,
                "channel_id": 456,
                "message_id": 789,
                "discord_event_id": 111,
                "title": "Opening",
                "status": "open",
                "starts_at": 1777217700,
                "player_limit": 0,
            },
            main_count=4,
            backup_count=0,
        )

        self.assertIn("`#9`", line)
        self.assertIn("**Opening**", line)
        self.assertIn("`open`", line)
        self.assertIn("4/unlimited players", line)
        self.assertIn("[panel]", line)
        self.assertIn("[native]", line)


if __name__ == "__main__":
    unittest.main()
