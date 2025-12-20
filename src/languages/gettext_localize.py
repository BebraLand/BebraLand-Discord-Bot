import gettext
import os
from typing import Dict, Callable
from functools import lru_cache
import src.languages.lang_constants as lang_constants


# Directory containing locale files
LOCALE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'locales')

# Cache for translation functions per locale
_translations_cache: Dict[str, gettext.GNUTranslations] = {}


@lru_cache(maxsize=10)
def get_translation(locale: str) -> gettext.GNUTranslations:
    """Get or create a translation object for the given locale.
    
    Args:
        locale: Language code (e.g., 'en', 'ru', 'lt')
    
    Returns:
        GNUTranslations object for the locale
    """
    if locale not in _translations_cache:
        try:
            translation = gettext.translation(
                'messages',
                localedir=LOCALE_DIR,
                languages=[locale],
                fallback=True
            )
            _translations_cache[locale] = translation
        except Exception as e:
            # Fallback to NullTranslations if locale not found
            _translations_cache[locale] = gettext.NullTranslations()
    
    return _translations_cache[locale]


def translate(message: str, locale: str) -> str:
    """Translate a message to the specified locale.
    
    Args:
        message: The message to translate (English text)
        locale: Language code (e.g., 'en', 'ru', 'lt')
    
    Returns:
        Translated message
    """
    try:
        translation = get_translation(locale)
        return translation.gettext(message)
    except Exception:
        # Return original message if translation fails
        return message


def locale_display_name(locale: str) -> str:
    """Map a locale code to a human-readable name using lang_constants.
    
    Args:
        locale: Language code (e.g., 'en', 'ru', 'lt')
    
    Returns:
        Human-readable language name
    """
    return {
        "en": lang_constants.ENGLISH,
        "ru": lang_constants.RUSSIAN,
        "lt": lang_constants.LITHUANIAN,
    }.get(locale, locale)


def get_translator(locale: str) -> Callable[[str], str]:
    """Get a translation function for a specific locale.
    
    This is useful when you need to translate multiple strings
    in the same locale without passing the locale each time.
    
    Args:
        locale: Language code (e.g., 'en', 'ru', 'lt')
    
    Returns:
        Translation function that takes a message and returns translated text
    
    Example:
        >>> _ = get_translator('ru')
        >>> _('Hello')
        'Привет'
    """
    translation = get_translation(locale)
    return translation.gettext


# For compatibility with pycord.i18n (if needed)
def setup_i18n(bot):
    """Initialize gettext-based i18n.
    
    This function provides compatibility with the old setup_i18n interface.
    
    Args:
        bot: Discord bot instance
    
    Returns:
        Tuple of (None, translate function)
    """
    # Return a simple translate function that uses English by default
    def _(message: str) -> str:
        return message
    
    return None, _
