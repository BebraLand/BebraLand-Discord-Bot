"""Localization module using gettext and Babel.

This module provides translation functionality using gettext/Babel
instead of JSON-based translations.
"""

import gettext
import os
from pathlib import Path
from typing import Tuple, Callable
from functools import lru_cache
import src.languages.lang_constants as lang_constants


# Directory containing locale files
LOCALE_DIR = str(Path(__file__).parent.parent.parent / 'locales')


@lru_cache(maxsize=10)
def get_translation(locale: str) -> gettext.GNUTranslations:
    """Get or create a translation object for the given locale.
    
    Args:
        locale: Language code (e.g., 'en', 'ru', 'lt')
    
    Returns:
        GNUTranslations object for the locale
    """
    try:
        translation = gettext.translation(
            'messages',
            localedir=LOCALE_DIR,
            languages=[locale],
            fallback=True
        )
        return translation
    except Exception:
        # Fallback to NullTranslations if locale not found
        return gettext.NullTranslations()


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


def setup_i18n(bot) -> Tuple[None, Callable]:
    """Initialize gettext-based i18n.
    
    This function provides compatibility with the old pycord.i18n interface.
    With gettext, we don't need a special I18n object, so we return None.
    
    Args:
        bot: Discord bot instance
    
    Returns:
        Tuple of (None, identity function)
    """
    # Return a simple identity function for the _ placeholder
    def _(message: str) -> str:
        return message
    
    return None, _