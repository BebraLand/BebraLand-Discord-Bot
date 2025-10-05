import json
import os
from typing import Tuple
from pycord.i18n import I18n, _


def setup_i18n(bot) -> Tuple[I18n, callable]:
    """Initialize pycord-i18n with available locale files.

    Looks for translation JSON files in `src/languages/i18n/` and
    registers them with I18n using their filename (without extension)
    as the locale code (e.g., `ru.json` -> `ru`).
    """
    base_dir = os.path.join("src", "languages", "i18n")
    locales = {}

    if os.path.isdir(base_dir):
        for filename in os.listdir(base_dir):
            if filename.endswith(".json"):
                locale_code = filename[:-5]  # strip .json
                file_path = os.path.join(base_dir, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        locales[locale_code] = json.load(f)
                except Exception:
                    # Skip malformed locale file
                    pass

    # Initialize I18n; prefer user's locale when available
    i18n = I18n(bot, consider_user_locale=True, **locales)
    return i18n, _