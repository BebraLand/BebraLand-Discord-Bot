import json
import os
import logging
from typing import Tuple, Dict, Any, Optional
from pycord.i18n import I18n, _
import src.languages.lang_constants as lang_constants


# Set up logger for localization module
logger = logging.getLogger(__name__)

# In-memory cache of locale_code -> translations
_LOCALES_CACHE: Dict[str, Dict[str, str]] = {}

# Default locale for fallback
DEFAULT_LOCALE = "en"


class SafeDict(dict):
    """Dictionary subclass that returns the key if a value is missing.
    
    This prevents KeyError exceptions during string formatting and returns
    the placeholder key instead, making it safer for user-provided input.
    """
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def setup_i18n(bot) -> Tuple[I18n, callable]:
    """Initialize pycord-i18n with available locale files.

    Looks for translation JSON files in `src/languages/i18n/` and
    registers them with I18n using their filename (without extension)
    as the locale code (e.g., `ru.json` -> `ru`, `en.json` -> `en`).
    
    Also populates the internal locale cache for the translate() function.

    Args:
        bot: The Discord bot instance to initialize i18n for.

    Returns:
        Tuple of (I18n instance, translation function)
    """
    base_dir = os.path.join("src", "languages", "i18n")
    locales = {}

    if os.path.isdir(base_dir):
        for filename in sorted(os.listdir(base_dir)):
            if filename.endswith(".json"):
                locale_code = filename[:-5]  # strip .json
                file_path = os.path.join(base_dir, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if not isinstance(data, dict):
                            logger.warning(
                                f"Locale file {file_path} does not contain a JSON object, skipping"
                            )
                            continue
                        locales[locale_code] = data
                        _LOCALES_CACHE[locale_code] = data
                        logger.info(f"Loaded locale '{locale_code}' from {file_path}")
                except json.JSONDecodeError as e:
                    logger.error(
                        f"Failed to parse locale file {file_path}: {e}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to load locale file {file_path}: {e}"
                    )
    else:
        logger.warning(f"Locale directory {base_dir} does not exist")

    # Ensure default locale is loaded
    if DEFAULT_LOCALE not in _LOCALES_CACHE:
        logger.warning(
            f"Default locale '{DEFAULT_LOCALE}' not found in loaded locales. "
            f"Fallback behavior may not work as expected."
        )

    # Initialize I18n; prefer user's locale when available
    i18n = I18n(bot, consider_user_locale=True, **locales)
    return i18n, _


def translate(key: str, locale: Optional[str] = None, **vars) -> str:
    """Translate a key to the specified locale with safe variable interpolation.

    This function looks up the translation key in the requested locale. If the key
    is not found, it falls back to the default locale (English). If still not found,
    it returns the key itself.

    Variable interpolation is done using str.format_map() with a SafeDict to prevent
    KeyError exceptions. Missing variables in the format string will be left as-is.

    Args:
        key: The translation key to look up.
        locale: The locale code (e.g., 'en', 'ru', 'lt'). If None, uses DEFAULT_LOCALE.
        **vars: Named variables to interpolate into the translated string.

    Returns:
        The translated and interpolated string.

    Examples:
        >>> translate("Language set to {lang}!", "en", lang="English")
        "Language set to English!"
        
        >>> translate("Your language is already {lang}.", "ru", lang="Русский")
        "Ваш язык уже установлен: Русский!"
        
        >>> translate("Missing key", "en")
        "Missing key"
    """
    if locale is None:
        locale = DEFAULT_LOCALE

    translated_value = None

    # Try requested locale first
    try:
        locale_map = _LOCALES_CACHE.get(locale)
        if locale_map:
            translated_value = locale_map.get(key)
    except Exception as e:
        logger.warning(f"Error accessing locale '{locale}': {e}")

    # Fallback to default locale if key not found
    if translated_value is None and locale != DEFAULT_LOCALE:
        try:
            default_map = _LOCALES_CACHE.get(DEFAULT_LOCALE)
            if default_map:
                translated_value = default_map.get(key)
                if translated_value is not None:
                    logger.debug(
                        f"Key '{key}' not found in locale '{locale}', using default locale '{DEFAULT_LOCALE}'"
                    )
        except Exception as e:
            logger.warning(f"Error accessing default locale '{DEFAULT_LOCALE}': {e}")

    # Final fallback to the key itself
    if translated_value is None:
        logger.debug(f"Key '{key}' not found in any locale, returning key as-is")
        translated_value = key

    # Perform safe variable interpolation if variables were provided
    if vars:
        try:
            translated_value = translated_value.format_map(SafeDict(vars))
        except Exception as e:
            logger.warning(
                f"Error interpolating variables into translated string for key '{key}': {e}"
            )

    return translated_value


def locale_display_name(locale: str) -> str:
    """Map a locale code to a human-readable language name.
    
    Uses lang_constants for the display names to maintain consistency
    with language flags and emojis.

    Args:
        locale: The locale code (e.g., 'en', 'ru', 'lt').

    Returns:
        Human-readable language name, or the locale code if not recognized.
    """
    return {
        "en": lang_constants.ENGLISH,
        "ru": lang_constants.RUSSIAN,
        "lt": lang_constants.LITHUANIAN,
    }.get(locale, locale)