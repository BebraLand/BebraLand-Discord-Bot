import json
import os
from typing import Tuple, Dict
from pycord.i18n import I18n, _
import src.languages.lang_constants as lang_constants


# In-memory map of locale_code -> translations
LOCALES: Dict[str, dict] = {}


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
                        data = json.load(f)
                        locales[locale_code] = data
                        LOCALES[locale_code] = data
                except Exception:
                    # Skip malformed locale file
                    pass

    # Initialize I18n; prefer user's locale when available
    i18n = I18n(bot, consider_user_locale=True, **locales)
    return i18n, _


def translate(key: str, locale: str) -> str:
    """Return translated string for given key and locale, fallback to key."""
    try:
        locale_map = LOCALES.get(locale)
        if locale_map:
            return locale_map.get(key, key)
    except Exception:
        pass
    return key


def locale_display_name(locale: str) -> str:
    """Map a locale code to a human-readable name using lang_constants."""
    return {
        "en": lang_constants.ENGLISH,
        "ru": lang_constants.RUSSIAN,
        "lt": lang_constants.LITHUANIAN,
    }.get(locale, locale)