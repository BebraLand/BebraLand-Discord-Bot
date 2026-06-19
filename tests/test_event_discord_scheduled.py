import unittest
from datetime import datetime, timezone

from src.features.events.discord_scheduled import (
    build_discord_scheduled_event_url,
    coerce_discord_event_duration_minutes,
    discord_event_end_time,
    normalize_discord_event_location_type,
    resolve_discord_event_location,
)
from src.features.events.service import event_cover_image_data


class DiscordScheduledEventTests(unittest.TestCase):
    def test_normalize_location_type_accepts_discord_names(self):
        self.assertEqual(normalize_discord_event_location_type("voice"), "voice")
        self.assertEqual(normalize_discord_event_location_type("stage"), "stage")
        self.assertEqual(
            normalize_discord_event_location_type("somewhere_else"),
            "external",
        )

    def test_normalize_location_type_uses_external_default(self):
        self.assertEqual(normalize_discord_event_location_type(None), "external")
        self.assertEqual(normalize_discord_event_location_type("weird"), "external")

    def test_duration_has_safe_minimum(self):
        self.assertEqual(coerce_discord_event_duration_minutes(0), 60)
        self.assertEqual(coerce_discord_event_duration_minutes(-20), 60)
        self.assertEqual(coerce_discord_event_duration_minutes(15), 15)

    def test_end_time_adds_duration(self):
        starts_at = datetime(2026, 5, 14, 18, 0, tzinfo=timezone.utc)

        self.assertEqual(
            discord_event_end_time(starts_at, 90),
            datetime(2026, 5, 14, 19, 30, tzinfo=timezone.utc),
        )

    def test_build_discord_scheduled_event_url(self):
        self.assertEqual(
            build_discord_scheduled_event_url(123, 456),
            "https://discord.com/events/123/456",
        )

    def test_resolve_voice_location_requires_voice_channel(self):
        with self.assertRaises(ValueError):
            resolve_discord_event_location("voice")

    def test_resolve_voice_location_uses_voice_channel(self):
        voice_channel = object()

        self.assertIs(
            resolve_discord_event_location("voice", voice_channel=voice_channel),
            voice_channel,
        )

    def test_resolve_external_location_uses_text(self):
        self.assertEqual(
            resolve_discord_event_location(
                "external",
                external_location="BebraLand arena",
            ),
            "BebraLand arena",
        )

    def test_event_cover_image_data_uses_stored_cover_url(self):
        self.assertEqual(
            event_cover_image_data(
                {"cover_image_url": "https://example.com/cover.png"}
            ),
            {"url": "https://example.com/cover.png"},
        )

    def test_event_cover_image_data_ignores_blank_cover_url(self):
        self.assertIsNone(event_cover_image_data({"cover_image_url": "  "}))


if __name__ == "__main__":
    unittest.main()
