from __future__ import annotations

from pathlib import Path

import config.command as COMMAND_ENABLED
import src.languages.lang_constants as lang_constants
from config.config import config as bot_config
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)

BASE_PATH = Path("src")


def _load_extension(bot, module: str) -> None:
    try:
        bot.load_extension(module)
        logger.info(f"{lang_constants.SUCCESS_EMOJI} Loaded {module}")
    except Exception as error:
        logger.error(f"{lang_constants.ERROR_EMOJI} Failed to load {module}: {error}")


def _iter_python_files(folder_path: Path):
    return sorted(
        file for file in folder_path.iterdir() if file.suffix == ".py" and not file.name.startswith("__")
    )


def _command_skip_reason(filename: str) -> str | None:
    if filename == "set_lang.py" and not COMMAND_ENABLED.SET_LANG:
        return "disabled by config.command"
    if filename == "clear_dm.py" and not COMMAND_ENABLED.CLEAR_DM:
        return "disabled by config.command"
    if filename == "rules.py" and not COMMAND_ENABLED.RULES_COMMAND:
        return "disabled by config.command"
    if filename == "toggle_invites.py" and not COMMAND_ENABLED.TOGGLE_INVITES:
        return "disabled by config.command"
    if filename == "invite_user_context.py":
        if not bot_config.modules.temp_voice.invite_enabled:
            return "disabled by config.modules.temp_voice.invite_enabled"
        if not COMMAND_ENABLED.INVITE_CONTEXT_MENU:
            return "disabled by config.command"
    if filename == "admin.py" and not COMMAND_ENABLED.ADMIN:
        return "disabled by config.command"
    return None


def _load_admin_extensions(bot, admin_folder_path: Path) -> None:
    if not (admin_folder_path / "__init__.py").exists():
        logger.error(
            f"{lang_constants.ERROR_EMOJI} Failed to load src.commands.admin: missing __init__.py in package"
        )
        return

    filenames = [file.name for file in _iter_python_files(admin_folder_path)]

    if "admin_group.py" in filenames:
        _load_extension(bot, "src.commands.admin.admin_group")
        filenames.remove("admin_group.py")

    for filename in filenames:
        _load_extension(bot, f"src.commands.admin.{filename[:-3]}")


def load_extensions(bot):
    for folder in ("events", "commands"):
        folder_path = BASE_PATH / folder
        for file in _iter_python_files(folder_path):
            if folder == "commands" and file.name == "admin.py" and (folder_path / "admin").is_dir():
                continue

            if folder == "commands":
                skip_reason = _command_skip_reason(file.name)
                if skip_reason:
                    logger.info(
                        f"{lang_constants.MUTED_BELL_EMOJI} Skipping src.{folder}.{file.stem} ({skip_reason})"
                    )
                    continue

            _load_extension(bot, f"src.{folder}.{file.stem}")

        if folder == "commands" and COMMAND_ENABLED.ADMIN:
            admin_folder_path = folder_path / "admin"
            if admin_folder_path.is_dir():
                _load_admin_extensions(bot, admin_folder_path)
