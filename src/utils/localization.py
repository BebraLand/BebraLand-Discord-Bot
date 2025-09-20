import json
import os
from .config_manager import get_user_language

LANG_DIR = "src/languages"

class LocalizationManager:
    def __init__(self, default_lang="en"):
        self.default_lang = default_lang
        self.languages = {}

    def load_language(self, lang_code=None):
        """Load language JSON file into memory."""
        lang_code = lang_code or self.default_lang
        if lang_code in self.languages:
            return self.languages[lang_code]

        lang_path = os.path.join(LANG_DIR, f"{lang_code}.json")
        if os.path.isfile(lang_path):
            with open(lang_path, "r", encoding="utf-8") as f:
                self.languages[lang_code] = json.load(f)
                return self.languages[lang_code]
        else:
            print(f"⚠️ Language file not found: {lang_path}")
            return {}

    def get(self, key, user_id=None, lang_code=None, **kwargs):
        """Get localized text and format it with optional kwargs.
        
        Args:
            key: The localization key to retrieve
            user_id: Discord user ID to get their preferred language
            lang_code: Override language code (takes priority over user_id)
            **kwargs: Format parameters for the localized string
        """
        # Determine language: explicit lang_code > user preference > default
        if lang_code:
            target_lang = lang_code
        elif user_id:
            target_lang = get_user_language(user_id)
        else:
            target_lang = self.default_lang
            
        lang = self.load_language(target_lang)
        text = lang.get(key, f"[{key}]")
        if kwargs:
            return text.format(**kwargs)
        return text

    def get_user_lang(self, key, user_id, **kwargs):
        """Convenience method to get localized text for a specific user."""
        return self.get(key, user_id=user_id, **kwargs)
