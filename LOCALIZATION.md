# Localization System

This project uses **gettext** and **Babel** for internationalization (i18n) and localization (l10n).

## Supported Languages

- English (en) - Default language
- Russian (ru) - Русский
- Lithuanian (lt) - Lietuvių

## Directory Structure

```
locales/
├── messages.pot           # Translation template (master file)
├── en/LC_MESSAGES/
│   ├── messages.po        # English translations (source)
│   └── messages.mo        # Compiled English translations
├── ru/LC_MESSAGES/
│   ├── messages.po        # Russian translations
│   └── messages.mo        # Compiled Russian translations
└── lt/LC_MESSAGES/
    ├── messages.po        # Lithuanian translations
    └── messages.mo        # Compiled Lithuanian translations
```

## Using Translations in Code

### Basic Usage

```python
from src.languages.localize import translate

# Translate a message
message = translate("Hello, world!", "ru")  # Returns: "Привет, мир!"
```

### With Variables

```python
from src.languages.localize import translate

# Translate with placeholders
lang = "ru"
user_name = "John"
message = translate("Welcome, {name}!", lang).format(name=user_name)
```

### Get a Translator Function

```python
from src.languages.localize import get_translator

# Get a translator for a specific locale
_ = get_translator("ru")
print(_("Success"))  # Returns: "Успех"
```

### Get Language Display Name

```python
from src.languages.localize import locale_display_name

print(locale_display_name("ru"))  # Returns: "Русский"
```

## Adding New Translations

### 1. Add the English String

Add your English string directly in your Python code using the `translate()` function:

```python
message = translate("This is a new message", locale)
```

### 2. Extract Messages

Extract all translatable strings from the codebase:

```bash
pybabel extract -F babel.cfg -o locales/messages.pot .
```

### 3. Update PO Files

Update all language PO files with the new template:

```bash
pybabel update -i locales/messages.pot -d locales
```

### 4. Edit Translations

Edit the `.po` files manually or use a PO editor like [Poedit](https://poedit.net/):

```
locales/ru/LC_MESSAGES/messages.po
locales/lt/LC_MESSAGES/messages.po
```

Find your new message (msgid) and add the translation (msgstr):

```po
msgid "This is a new message"
msgstr "Это новое сообщение"
```

### 5. Compile MO Files

Compile the PO files to binary MO files:

```bash
pybabel compile -d locales
```

Or using Python:

```python
from babel.messages import mofile, pofile

for lang in ['en', 'ru', 'lt']:
    po_path = f'locales/{lang}/LC_MESSAGES/messages.po'
    mo_path = f'locales/{lang}/LC_MESSAGES/messages.mo'
    with open(po_path, 'rb') as po_file:
        catalog = pofile.read_po(po_file)
    with open(mo_path, 'wb') as mo_file:
        mofile.write_mo(mo_file, catalog)
```

## Adding a New Language

### 1. Initialize the New Language

```bash
pybabel init -i locales/messages.pot -d locales -l es  # For Spanish
```

### 2. Translate the PO File

Edit `locales/es/LC_MESSAGES/messages.po` and add translations.

### 3. Update Code

Add the new language to `src/languages/localize.py` in the `locale_display_name()` function:

```python
def locale_display_name(locale: str) -> str:
    return {
        "en": lang_constants.ENGLISH,
        "ru": lang_constants.RUSSIAN,
        "lt": lang_constants.LITHUANIAN,
        "es": "Español",  # Add new language here
    }.get(locale, locale)
```

### 4. Compile

```bash
pybabel compile -d locales
```

## Tools

### Babel Commands

- **Extract messages**: `pybabel extract -F babel.cfg -o locales/messages.pot .`
- **Initialize new language**: `pybabel init -i locales/messages.pot -d locales -l <lang_code>`
- **Update translations**: `pybabel update -i locales/messages.pot -d locales`
- **Compile translations**: `pybabel compile -d locales`

### PO File Editors

- [Poedit](https://poedit.net/) - Cross-platform PO file editor
- [Lokalize](https://kde.org/applications/office/org.kde.lokalize) - KDE translation tool
- [Gtranslator](https://wiki.gnome.org/Apps/Gtranslator) - GNOME translation editor

## Migration from JSON

This project was migrated from JSON-based translations to gettext/Babel. The old JSON files are kept in `src/languages/i18n/` for reference but are no longer used by the bot.

## Best Practices

1. **Always use English as the msgid**: The English text is the key for translations
2. **Keep placeholders consistent**: Use `{variable}` format for all placeholders
3. **Don't translate in code**: All user-facing strings should go through `translate()`
4. **Context matters**: Add comments in PO files for translators when needed
5. **Test translations**: Always test your translations in the bot before deploying

## Troubleshooting

### Translations Not Showing

1. Make sure MO files are compiled: `pybabel compile -d locales`
2. Check that the locale code matches (e.g., "ru" not "ru_RU")
3. Verify the msgid matches exactly (case-sensitive, including punctuation)

### Missing Translations

If a translation is missing, the system will fallback to English (the msgid).

### Special Characters

PO files use UTF-8 encoding. Make sure your editor is set to UTF-8.

## References

- [GNU gettext documentation](https://www.gnu.org/software/gettext/manual/)
- [Babel documentation](http://babel.pocoo.org/)
- [Python gettext module](https://docs.python.org/3/library/gettext.html)
