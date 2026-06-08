import unittest

from config.config import ConfigError, to_attr_dict, validate_config


class ConfigValidationTests(unittest.TestCase):
    def test_validate_config_accepts_minimal_valid_config(self):
        config = to_attr_dict(
            {
                "bot": {
                    "token": "test-token",
                    "default_language": "en",
                    "prefix": "!",
                },
                "health": {"enabled": False, "port": 8085},
                "embeds": {},
                "modules": {
                    "status": {"enabled": False, "update_interval_seconds": 90},
                    "twitch": {
                        "enabled": False,
                        "check_interval_seconds": 30,
                        "streamers": {},
                    },
                    "tickets": {"max_per_user": 3},
                    "temp_voice": {"delete_empty_after_seconds": 5},
                    "news": {"character_limit": 2000},
                    "applications": {},
                },
            }
        )

        validate_config(config)

    def test_validate_config_rejects_placeholder_token(self):
        config = to_attr_dict(
            {
                "bot": {
                    "token": "${DISCORD_BOT_TOKEN}",
                    "default_language": "en",
                    "prefix": "!",
                },
                "health": {"enabled": False, "port": 8085},
                "embeds": {},
                "modules": {},
            }
        )

        with self.assertRaises(ConfigError):
            validate_config(config)


if __name__ == "__main__":
    unittest.main()
