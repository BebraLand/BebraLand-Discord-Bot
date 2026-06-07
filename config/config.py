"""Simple YAML config loader."""

import os
import sys

import yaml
from dotenv import load_dotenv


class AttrDict(dict):
    """Dict with dot access for config sections."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as error:
            raise AttributeError(key) from error


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


config = to_attr_dict(load_config(os.getenv("BOT_CONFIG_PATH", "config/config.yaml")))
