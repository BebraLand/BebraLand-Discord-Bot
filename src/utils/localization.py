import json
import os

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

    def get(self, key, lang_code=None, **kwargs):
        """Get localized text and format it with optional kwargs."""
        lang = self.load_language(lang_code)
        text = lang.get(key, f"[{key}]")
        if kwargs:
            return text.format(**kwargs)
        return text
