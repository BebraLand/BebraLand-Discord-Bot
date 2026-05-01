import json
import os
from typing import Dict, Tuple

from pycord.i18n import I18n
from pycord.i18n import _ as pycord_translate

import src.languages.lang_constants as lang_constants
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)

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
    return i18n, pycord_translate


def _(key: str, locale: str) -> str:
    """Return translated string for given nested key path and locale.

    Supports nested keys using dot notation (e.g., 'common.info', 'language.set').
    Falls back to DEFAULT_LANGUAGE if translation is not found in requested locale.
    Finally falls back to the key itself if not found in any locale.

    Args:
        key: Dot-separated path to the translation (e.g., 'common.error')
        locale: Locale code (e.g., 'en', 'ru', 'lt')

    Returns:
        Translated string, fallback translation, or the key itself if not found
    """
    from config.constants import DEFAULT_LANGUAGE

    def get_translation(lang: str) -> tuple[bool, str]:
        """Try to get translation for a specific language.

        Returns:
            Tuple of (found: bool, value: str)
        """
        try:
            locale_map = LOCALES.get(lang)
            if not locale_map:
                return False, key

            # Split the key by dots to traverse nested structure
            keys = key.split(".")
            value = locale_map

            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return False, key

            if isinstance(value, str):
                return True, value
            return False, key
        except Exception:
            return False, key

    # Try requested locale first
    found, translation = get_translation(locale)
    if found:
        return translation

    # Fall back to DEFAULT_LANGUAGE if different from requested locale
    if locale != DEFAULT_LANGUAGE:
        found, translation = get_translation(DEFAULT_LANGUAGE)
        if found:
            logger.warning(
                f"Translation key '{key}' not found for locale '{locale}', using DEFAULT_LANGUAGE '{DEFAULT_LANGUAGE}'"
            )
            return translation

    # Final fallback: return the key itself
    logger.warning(
        f"Translation key '{key}' not found in any locale (requested: '{locale}')"
    )
    return key


# Keep translate() as an alias for backward compatibility
def translate(key: str, locale: str) -> str:
    """Legacy alias for _() function. Use _() instead."""
    return _(key, locale)


def locale_display_name(locale: str) -> str:
    """Map a locale code to a human-readable name using lang_constants."""
    return {
        "en": lang_constants.ENGLISH,
        "ru": lang_constants.RUSSIAN,
        "lt": lang_constants.LITHUANIAN,
    }.get(locale, locale)
