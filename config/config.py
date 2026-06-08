"""Simple YAML config loader."""

from __future__ import annotations

import os
import sys
from typing import Any

import yaml
from dotenv import load_dotenv


class AttrDict(dict):
    """Dict with dot access for config sections."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as error:
            raise AttributeError(key) from error


class ConfigError(ValueError):
    """Raised when runtime config is invalid."""


def load_config(config_path: str = "config/config.yaml") -> dict:
    """Load configuration from YAML file."""
    load_dotenv()

    try:
        with open(config_path, "r", encoding="utf-8") as file:
            config_data = yaml.safe_load(file)

        if not isinstance(config_data, dict):
            print(f"Error: Config file '{config_path}' is empty or invalid")
            print("Admin must configure config/config.yaml")
            sys.exit(1)

        def replace_env_vars(obj):
            """Recursively replace ${ENV_VAR} with actual values."""
            if isinstance(obj, dict):
                return {key: replace_env_vars(value) for key, value in obj.items()}
            if isinstance(obj, list):
                return [replace_env_vars(item) for item in obj]
            if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
                env_var = obj[2:-1]
                return os.getenv(env_var, obj)
            return obj

        return replace_env_vars(config_data)

    except FileNotFoundError:
        print(f"Error: Config file '{config_path}' not found")
        print("Admin must configure config/config.yaml")
        sys.exit(1)
    except yaml.YAMLError as error:
        print(f"Error parsing config file: {error}")
        sys.exit(1)


def to_attr_dict(obj):
    if isinstance(obj, dict):
        return AttrDict({key: to_attr_dict(value) for key, value in obj.items()})
    if isinstance(obj, list):
        return [to_attr_dict(item) for item in obj]
    return obj


def _get_value(config_data: Any, path: str, default: Any = None) -> Any:
    value = config_data
    for key in path.split("."):
        if value is None:
            return default
        if isinstance(value, dict):
            value = value.get(key, default)
            continue
        value = getattr(value, key, default)
    return value


def _is_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return not stripped or stripped == "CHANGE_ME" or (
            stripped.startswith("${") and stripped.endswith("}")
        )
    return False


def _require_positive_int(errors: list[str], value: Any, path: str) -> None:
    if not isinstance(value, int) or value <= 0:
        errors.append(f"{path} must be a positive integer")


def validate_config(config_data: Any) -> None:
    """Validate runtime config and raise ConfigError with actionable messages."""
    errors: list[str] = []

    bot_section = _get_value(config_data, "bot")
    modules_section = _get_value(config_data, "modules")
    health_section = _get_value(config_data, "health")
    embeds_section = _get_value(config_data, "embeds")

    if not isinstance(bot_section, (dict, AttrDict)):
        errors.append("Missing or invalid config section: bot")
    else:
        token = _get_value(config_data, "bot.token")
        if _is_placeholder(token):
            errors.append(
                "bot.token is not configured. Set DISCORD_BOT_TOKEN or config.bot.token"
            )

        prefix = _get_value(config_data, "bot.prefix", "")
        if not isinstance(prefix, str) or not prefix.strip():
            errors.append("bot.prefix must be a non-empty string")

        default_language = str(_get_value(config_data, "bot.default_language", "en")).lower()
        if default_language not in {"en", "ru", "lt"}:
            errors.append("bot.default_language must be one of: en, ru, lt")

    if not isinstance(modules_section, (dict, AttrDict)):
        errors.append("Missing or invalid config section: modules")
    else:
        status_enabled = bool(_get_value(config_data, "modules.status.enabled", False))
        if status_enabled:
            _require_positive_int(
                errors,
                _get_value(config_data, "modules.status.update_interval_seconds"),
                "modules.status.update_interval_seconds",
            )

        twitch_enabled = bool(_get_value(config_data, "modules.twitch.enabled", False))
        if twitch_enabled:
            _require_positive_int(
                errors,
                _get_value(config_data, "modules.twitch.check_interval_seconds"),
                "modules.twitch.check_interval_seconds",
            )
            streamers = _get_value(config_data, "modules.twitch.streamers", {})
            if not isinstance(streamers, dict):
                errors.append("modules.twitch.streamers must be a mapping")
            elif not streamers:
                errors.append("modules.twitch.streamers cannot be empty when Twitch is enabled")

        tickets_max = _get_value(config_data, "modules.tickets.max_per_user")
        if tickets_max is not None:
            _require_positive_int(errors, tickets_max, "modules.tickets.max_per_user")

        temp_delete_empty_after = _get_value(
            config_data, "modules.temp_voice.delete_empty_after_seconds"
        )
        if temp_delete_empty_after is not None:
            if not isinstance(temp_delete_empty_after, int) or temp_delete_empty_after < 0:
                errors.append(
                    "modules.temp_voice.delete_empty_after_seconds must be a non-negative integer"
                )

        news_limit = _get_value(config_data, "modules.news.character_limit")
        if news_limit is not None:
            _require_positive_int(errors, news_limit, "modules.news.character_limit")

    if not isinstance(health_section, (dict, AttrDict)):
        errors.append("Missing or invalid config section: health")
    elif bool(_get_value(config_data, "health.enabled", False)):
        port = _get_value(config_data, "health.port")
        if not isinstance(port, int) or not (1 <= port <= 65535):
            errors.append("health.port must be between 1 and 65535")

    if not isinstance(embeds_section, (dict, AttrDict)):
        errors.append("Missing or invalid config section: embeds")

    if errors:
        raise ConfigError("Invalid runtime config:\n- " + "\n- ".join(errors))


config = to_attr_dict(load_config(os.getenv("BOT_CONFIG_PATH", "config/config.yaml")))
