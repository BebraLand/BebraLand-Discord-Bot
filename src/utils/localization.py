import json
import os
import logging
from typing import Dict, Optional, Set
from .config_manager import get_user_language

LANG_DIR = "src/languages"

# Set up logging for localization
logger = logging.getLogger(__name__)

# Track missing keys to avoid spam logging
_missing_keys_cache: Set[str] = set()

class LocalizationManager:
    def __init__(self, default_lang="en"):
        self.default_lang = default_lang
        self.languages = {}
        self.supported_languages = {"en", "lt", "ru"}
        self.fallback_chain = ["en"]  # Fallback order
        
    def get_supported_languages(self) -> Set[str]:
        """Get set of supported language codes."""
        return self.supported_languages.copy()
        
    def is_language_supported(self, lang_code: str) -> bool:
        """Check if a language code is supported."""
        return lang_code in self.supported_languages

    def load_language(self, lang_code: Optional[str] = None) -> Dict[str, str]:
        """Load language JSON file into memory with enhanced error handling.
        
        Args:
            lang_code: Language code to load (defaults to default_lang)
            
        Returns:
            Dictionary containing localization keys and values
        """
        lang_code = lang_code or self.default_lang
        
        # Validate language code
        if not self.is_language_supported(lang_code):
            logger.warning(f"Unsupported language code '{lang_code}', falling back to '{self.default_lang}'")
            lang_code = self.default_lang
            
        # Return cached language if already loaded
        if lang_code in self.languages:
            return self.languages[lang_code]

        lang_path = os.path.join(LANG_DIR, f"{lang_code}.json")
        
        if not os.path.isfile(lang_path):
            logger.error(f"Language file not found: {lang_path}")
            # If it's not the default language, try to load default as fallback
            if lang_code != self.default_lang:
                logger.info(f"Attempting to load default language '{self.default_lang}' as fallback")
                return self.load_language(self.default_lang)
            return {}
            
        try:
            with open(lang_path, "r", encoding="utf-8") as f:
                language_data = json.load(f)
                
            # Validate that it's a dictionary
            if not isinstance(language_data, dict):
                logger.error(f"Invalid language file format in {lang_path}: expected dictionary, got {type(language_data)}")
                return {}
                
            self.languages[lang_code] = language_data
            logger.info(f"Successfully loaded language file: {lang_code} ({len(language_data)} keys)")
            return self.languages[lang_code]
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON in language file {lang_path}: {e}")
        except UnicodeDecodeError as e:
            logger.error(f"Encoding error in language file {lang_path}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading language file {lang_path}: {e}")
            
        # Return empty dict on any error
        return {}

    def _log_missing_key(self, key: str, lang_code: str, user_id: Optional[int] = None) -> None:
        """Log missing translation key with spam prevention.
        
        Args:
            key: The missing localization key
            lang_code: The language code where the key is missing
            user_id: Optional user ID for context
        """
        cache_key = f"{key}:{lang_code}"
        if cache_key not in _missing_keys_cache:
            _missing_keys_cache.add(cache_key)
            context = f" (user: {user_id})" if user_id else ""
            logger.warning(f"Missing translation key '{key}' for language '{lang_code}'{context}")
    
    def get(self, key: str, user_id: Optional[int] = None, lang_code: Optional[str] = None, **kwargs) -> str:
        """Get localized text with comprehensive fallback handling and formatting.
        
        Args:
            key: The localization key to retrieve
            user_id: Discord user ID to get their preferred language
            lang_code: Override language code (takes priority over user_id)
            **kwargs: Format parameters for the localized string
            
        Returns:
            Localized and formatted text, or a placeholder if key is missing
        """
        if not key:
            logger.error("Empty or None key provided to localization")
            return "[INVALID KEY]"
            
        # Determine target language: explicit lang_code > user preference > default
        if lang_code:
            target_lang = lang_code
        elif user_id:
            try:
                target_lang = get_user_language(user_id)
            except Exception as e:
                logger.error(f"Error getting user language for {user_id}: {e}")
                target_lang = self.default_lang
        else:
            target_lang = self.default_lang
            
        # Validate target language
        if not self.is_language_supported(target_lang):
            logger.warning(f"Unsupported target language '{target_lang}', using default '{self.default_lang}'")
            target_lang = self.default_lang
            
        text = None
        languages_tried = []
        
        # Try target language first
        try:
            lang_data = self.load_language(target_lang)
            text = lang_data.get(key)
            languages_tried.append(target_lang)
            
            if text is not None:
                logger.debug(f"Found key '{key}' in target language '{target_lang}'")
            else:
                self._log_missing_key(key, target_lang, user_id)
        except Exception as e:
            logger.error(f"Error loading target language '{target_lang}': {e}")
            
        # Try fallback languages if key not found
        if text is None:
            for fallback_lang in self.fallback_chain:
                if fallback_lang == target_lang:
                    continue  # Already tried
                    
                try:
                    fallback_data = self.load_language(fallback_lang)
                    text = fallback_data.get(key)
                    languages_tried.append(fallback_lang)
                    
                    if text is not None:
                        logger.info(f"Found key '{key}' in fallback language '{fallback_lang}' (target was '{target_lang}')")
                        break
                    else:
                        self._log_missing_key(key, fallback_lang, user_id)
                except Exception as e:
                    logger.error(f"Error loading fallback language '{fallback_lang}': {e}")
                    
        # If still not found, return placeholder
        if text is None:
            logger.error(f"Key '{key}' not found in any language (tried: {', '.join(languages_tried)})")
            return f"[MISSING: {key}]"
            
        # Format text with kwargs if provided
        if kwargs and text and isinstance(text, str):
            try:
                formatted_text = text.format(**kwargs)
                logger.debug(f"Successfully formatted key '{key}' with {len(kwargs)} parameters")
                return formatted_text
            except KeyError as e:
                logger.error(f"Missing format parameter for key '{key}': {e}. Available params: {list(kwargs.keys())}")
                return text
            except ValueError as e:
                logger.error(f"Invalid format string for key '{key}': {e}")
                return text
            except Exception as e:
                logger.error(f"Unexpected error formatting text for key '{key}': {e}")
                return text
                
        return text if isinstance(text, str) else str(text)

    def get_user_lang(self, key, user_id, **kwargs):
        """Convenience method to get localized text for a specific user.
        
        Args:
            key: The localization key to retrieve
            user_id: Discord user ID to get their preferred language
            **kwargs: Format parameters for the localized string
        """
        return self.get(key, user_id=user_id, **kwargs)
    
    def get_missing_keys_stats(self) -> Dict[str, int]:
        """Get statistics about missing translation keys.
        
        Returns:
            Dictionary with language codes as keys and missing key counts as values
        """
        stats = {}
        for cache_key in _missing_keys_cache:
            if ':' in cache_key:
                key, lang_code = cache_key.rsplit(':', 1)
                stats[lang_code] = stats.get(lang_code, 0) + 1
        return stats
    
    def clear_missing_keys_cache(self) -> int:
        """Clear the missing keys cache and return the number of entries cleared.
        
        Returns:
            Number of cache entries that were cleared
        """
        count = len(_missing_keys_cache)
        _missing_keys_cache.clear()
        logger.info(f"Cleared {count} missing key cache entries")
        return count
    
    def validate_language_completeness(self, reference_lang: str = "en") -> Dict[str, Dict[str, any]]:
        """Validate completeness of all languages against a reference language.
        
        Args:
            reference_lang: Language to use as reference (default: English)
            
        Returns:
            Dictionary with validation results for each language
        """
        results = {}
        
        try:
            reference_data = self.load_language(reference_lang)
            reference_keys = set(reference_data.keys())
            
            for lang_code in self.supported_languages:
                if lang_code == reference_lang:
                    continue
                    
                try:
                    lang_data = self.load_language(lang_code)
                    lang_keys = set(lang_data.keys())
                    
                    missing_keys = reference_keys - lang_keys
                    extra_keys = lang_keys - reference_keys
                    
                    results[lang_code] = {
                        'total_keys': len(lang_keys),
                        'missing_keys': list(missing_keys),
                        'missing_count': len(missing_keys),
                        'extra_keys': list(extra_keys),
                        'extra_count': len(extra_keys),
                        'completeness_percent': round((len(lang_keys & reference_keys) / len(reference_keys)) * 100, 2) if reference_keys else 100
                    }
                    
                except Exception as e:
                    results[lang_code] = {
                        'error': str(e),
                        'total_keys': 0,
                        'missing_keys': list(reference_keys),
                        'missing_count': len(reference_keys),
                        'extra_keys': [],
                        'extra_count': 0,
                        'completeness_percent': 0
                    }
                    
        except Exception as e:
            logger.error(f"Error loading reference language '{reference_lang}': {e}")
            return {}
            
        return results
