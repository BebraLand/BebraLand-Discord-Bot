import unittest

from src.features.status.core import (
    PresenceCandidate,
    build_event_candidate,
    build_fallback_candidates,
    build_minecraft_candidate,
    build_twitch_candidate,
    pick_presence_candidate,
    truncate_presence_text,
)


class StatusCoreTests(unittest.TestCase):
    def test_pick_presence_candidate_prefers_highest_priority(self):
        event = PresenceCandidate("watching", "Event: Spleef", priority=30)
        minecraft = PresenceCandidate("playing", "Minecraft | 7 online", priority=60)
        twitch = PresenceCandidate(
            "streaming",
            "aurum is live on Twitch",
            priority=100,
            url="https://twitch.tv/aurum",
        )

        self.assertEqual(pick_presence_candidate([event, minecraft, twitch]), twitch)

    def test_pick_presence_candidate_uses_fallback_when_no_live_sources(self):
        fallback = build_fallback_candidates(
            [{"type": "playing", "text": "BebraLand"}]
        )

        self.assertEqual(pick_presence_candidate([], fallback).name, "BebraLand")

    def test_build_minecraft_candidate_formats_online_count(self):
        candidate = build_minecraft_candidate(
            host="mc.bebraland.example",
            online_players=12,
            max_players=50,
        )

        self.assertEqual(candidate.kind, "playing")
        self.assertEqual(candidate.name, "Minecraft | 12/50 online")

    def test_build_twitch_candidate_uses_streaming_url(self):
        candidate = build_twitch_candidate("Aurum")

        self.assertEqual(candidate.kind, "streaming")
        self.assertEqual(candidate.name, "Aurum is live on Twitch")
        self.assertEqual(candidate.url, "https://twitch.tv/Aurum")

    def test_build_event_candidate_prefers_started_event(self):
        candidate = build_event_candidate(
            {"title": "Spleef Night", "status": "started"}
        )

        self.assertEqual(candidate.kind, "watching")
        self.assertEqual(candidate.name, "Event now: Spleef Night")

    def test_truncate_presence_text_keeps_discord_limit(self):
        text = "A" * 200

        self.assertEqual(len(truncate_presence_text(text)), 128)
        self.assertTrue(truncate_presence_text(text).endswith("..."))


if __name__ == "__main__":
    unittest.main()
