import os

import src.languages.lang_constants as lang_constants
from config.config import config as bot_config
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)
enabled_commands = bot_config.get("commands", {})
_COMMAND_FLAGS = {
    "set_lang.py": "set_lang",
    "clear_dm.py": "clear_dm",
    "toggle_invites.py": "toggle_invites",
    "invite_user_context.py": "invite_context_menu",
    "rules.py": "rules",
    "radio.py": "radio",
    "admin.py": "admin",
}


def load_extensions(bot):
    for folder in ["events", "commands"]:
        folder_path = os.path.join("src", folder)
        for filename in os.listdir(folder_path):
            if filename.endswith(".py") and not filename.startswith("__"):
                # Respect command enable/disable flags
                if folder == "commands":
                    # Skip admin.py if an admin package exists; we'll load its submodules below
                    if filename == "admin.py":
                        admin_folder_path = os.path.join(folder_path, "admin")
                        if os.path.isdir(admin_folder_path):
                            continue
                    command_flag = _COMMAND_FLAGS.get(filename)
                    if command_flag and not enabled_commands.get(command_flag, True):
                        logger.info(
                            f"{lang_constants.MUTED_BELL_EMOJI} Skipping src.commands.{filename[:-3]} "
                            f"(disabled by config.commands.{command_flag})"
                        )
                        continue
                    if filename == "invite_user_context.py":
                        if not bot_config.modules.temp_voice.invite_enabled:
                            logger.info(
                                f"{lang_constants.MUTED_BELL_EMOJI} Skipping src.commands.invite_user_context (disabled by config.modules.temp_voice.invite_enabled)"
                            )
                            continue
                module = f"src.{folder}.{filename[:-3]}"
                try:
                    bot.load_extension(module)
                    logger.info(f"{lang_constants.SUCCESS_EMOJI} Loaded {module}")
                except Exception as e:
                    logger.error(
                        f"{lang_constants.ERROR_EMOJI} Failed to load {module}: {e}"
                    )

        # Load admin subfolder commands if ADMIN is enabled
        if folder == "commands" and enabled_commands.get("admin", True):
            admin_folder_path = os.path.join(folder_path, "admin")
            if os.path.isdir(admin_folder_path):
                # Ensure it's a proper package to allow dotted imports
                has_init = os.path.exists(
                    os.path.join(admin_folder_path, "__init__.py")
                )
                if not has_init:
                    logger.error(
                        f"{lang_constants.ERROR_EMOJI} Failed to load src.commands.admin: missing __init__.py in package"
                    )
                    continue
                # Collect admin modules and ensure admin_group loads first
                filenames = [
                    f
                    for f in os.listdir(admin_folder_path)
                    if f.endswith(".py") and not f.startswith("__")
                ]

                # Load the group-defining cog first if present
                if "admin_group.py" in filenames:
                    module = "src.commands.admin.admin_group"
                    try:
                        bot.load_extension(module)
                        logger.info(f"{lang_constants.SUCCESS_EMOJI} Loaded {module}")
                    except Exception as e:
                        logger.error(
                            f"{lang_constants.ERROR_EMOJI} Failed to load {module}: {e}"
                        )
                    filenames.remove("admin_group.py")

                # Load remaining admin cogs
                for filename in filenames:
                    module = f"src.commands.admin.{filename[:-3]}"
                    try:
                        bot.load_extension(module)
                        logger.info(f"{lang_constants.SUCCESS_EMOJI} Loaded {module}")
                    except Exception as e:
                        logger.error(
                            f"{lang_constants.ERROR_EMOJI} Failed to load {module}: {e}"
                        )
