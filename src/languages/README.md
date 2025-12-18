# Localization System

This directory contains the localization infrastructure for the BebraLand Discord Bot.

## Directory Structure

```
src/languages/
├── i18n/                    # Translation files
│   ├── en.json             # English (canonical/default)
│   ├── ru.json             # Russian
│   └── lt.json             # Lithuanian
├── lang_constants.py        # Non-translatable constants (flags, emojis)
├── localize.py             # Translation API and locale loading
└── README.md               # This file
```

## Translation Files

All translation files are stored as JSON in the `i18n/` directory. The `en.json` file is the canonical source of truth for all translation keys.

### File Format

Each locale file is a JSON object mapping translation keys to localized strings:

```json
{
  "Language set to {lang}!": "Language set to {lang}!",
  "Success": "Success",
  "Error": "Error"
}
```

### Variable Interpolation

Translation strings support variable interpolation using Python's `str.format()` syntax:

```python
translate("Language set to {lang}!", locale="en", lang="English")
# Returns: "Language set to English!"
```

Variables are interpolated safely using a `SafeDict` to prevent crashes from missing variables.

## Adding a New Locale

1. Create a new JSON file in `i18n/` with the locale code as the filename (e.g., `de.json` for German)
2. Copy the structure from `en.json`
3. Translate all values while keeping the keys in English
4. Add the locale to `locale_display_name()` in `localize.py` if needed
5. Run the validation script to ensure completeness

## Using the Translation API

### translate()

The main translation function with automatic fallback to English:

```python
from src.languages.localize import translate

# Basic usage
translated = translate("Success", locale="ru")

# With variable interpolation
msg = translate("Language set to {lang}!", locale="en", lang="English")

# Automatic fallback to English if key missing
msg = translate("New key", locale="ru")  # Falls back to English
```

### locale_display_name()

Get a human-readable name for a locale code:

```python
from src.languages.localize import locale_display_name

name = locale_display_name("ru")  # Returns: "Русский"
```

## Validation Script

The `scripts/validate_translations.py` script helps maintain translation consistency.

### Check for Missing Keys

```bash
python scripts/validate_translations.py --report
```

This reports:
- Missing keys (exist in `en.json` but not in other locales)
- Extra keys (exist in other locales but not in `en.json`)

### Auto-fill Missing Keys

```bash
python scripts/validate_translations.py --autofill-missing
```

This automatically adds missing keys to locale files with the English value prefixed by `[MISSING TRANSLATION]`.

## Workflow

### Adding New Translatable Strings

1. Add the English key and value to `src/languages/i18n/en.json`
2. Update your code to use `translate("Your key here", user_lang)`
3. Run `python scripts/validate_translations.py --autofill-missing` to add placeholders to other locales
4. Replace the `[MISSING TRANSLATION]` placeholders with actual translations
5. Run `python scripts/validate_translations.py --report` to verify

### Best Practices

- Always add new keys to `en.json` first
- Use descriptive, unique keys that capture the meaning
- Include context in the key if the same English text has different meanings
- Keep variable names short but meaningful: `{lang}`, `{count}`, `{user}`
- Run the validator before committing changes
- Keep slash command `description_localizations` metadata unchanged (pycord-i18n handles that)

## Constants vs. Translations

**lang_constants.py** contains only non-translatable constants:
- Emoji symbols (flags, status icons, etc.)
- Language display names for backwards compatibility (use `locale_display_name()` for runtime)

**i18n/*.json** files contain all user-facing translatable text.

## Optional: Babel/ICU Integration

For advanced features like pluralization, you can integrate `Babel` or ICU:

```bash
pip install babel
```

Then use Babel's message formatting in your translation values:

```json
{
  "items_count": "{count, plural, one {1 item} other {# items}}"
}
```

Update the `translate()` function to use Babel's `format_message()` for interpolation instead of `str.format_map()`.

## Testing

See `test/test_localize.py` for unit tests of the translation system.

Run tests with:
```bash
pytest test/test_localize.py -v
```
