import os

import config.command as COMMAND_ENABLED
import config.constants as constants
import src.languages.lang_constants as lang_constants
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


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
                    if filename == "set_lang.py" and not COMMAND_ENABLED.SET_LANG:
                        logger.info(
                            f"{lang_constants.MUTED_BELL_EMOJI} Skipping src.commands.set_lang (disabled by config.command)"
                        )
                        continue
                    if filename == "clear_dm.py" and not COMMAND_ENABLED.CLEAR_DM:
                        logger.info(
                            f"{lang_constants.MUTED_BELL_EMOJI} Skipping src.commands.clear_dm (disabled by config.command)"
                        )
                        continue
                    if (
                        filename == "toggle_invites.py"
                        and not COMMAND_ENABLED.TOGGLE_INVITES
                    ):
                        logger.info(
                            f"{lang_constants.MUTED_BELL_EMOJI} Skipping src.commands.toggle_invites (disabled by config.command)"
                        )
                        continue
                    if filename == "invite_user_context.py":
                        if not constants.TEMP_VOICE_INVITE_ENABLED:
                            logger.info(
                                f"{lang_constants.MUTED_BELL_EMOJI} Skipping src.commands.invite_user_context (disabled by config.constants.TEMP_VOICE_INVITE_ENABLED)"
                            )
                            continue
                        if not COMMAND_ENABLED.INVITE_CONTEXT_MENU:
                            logger.info(
                                f"{lang_constants.MUTED_BELL_EMOJI} Skipping src.commands.invite_user_context (disabled by config.command)"
                            )
                            continue
                    if filename == "admin.py" and not COMMAND_ENABLED.ADMIN:
                        logger.info(
                            f"{lang_constants.MUTED_BELL_EMOJI} Skipping src.commands.admin (disabled by config.command)"
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
        if folder == "commands" and COMMAND_ENABLED.ADMIN:
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
