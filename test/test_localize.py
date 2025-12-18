"""
Unit tests for the localize module.

Run with: pytest test/test_localize.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to path so we can import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.languages.localize import translate, SafeDict, DEFAULT_LOCALE


def test_safe_dict():
    """Test that SafeDict returns the key when value is missing."""
    d = SafeDict({"name": "Alice"})
    assert d["name"] == "Alice"
    assert d["missing"] == "{missing}"


def test_translate_basic():
    """Test basic translation without variables."""
    # Test with English locale
    result = translate("Success", "en")
    assert result == "Success"
    
    # Test with Russian locale
    result = translate("Success", "ru")
    assert result == "Успех"


def test_translate_with_variables():
    """Test translation with variable interpolation."""
    result = translate("Language set to {lang}!", "en", lang="English")
    assert result == "Language set to English!"
    
    result = translate("Language set to {lang}!", "ru", lang="Русский")
    assert result == "Язык установлен: Русский!"


def test_translate_fallback_to_english():
    """Test that missing keys in non-English locales fall back to English."""
    # Create a test scenario where a key exists in English but not in another locale
    # This will use the actual locale files
    # Test with a key that should exist in English
    result = translate("Success", "xx")  # Non-existent locale
    assert result == "Success"  # Should return the key or English fallback


def test_translate_missing_key():
    """Test that missing keys return the key itself."""
    result = translate("NonExistentKey12345", "en")
    assert result == "NonExistentKey12345"


def test_translate_none_locale():
    """Test that None locale defaults to English."""
    result = translate("Success", None)
    assert result == "Success"


def test_translate_missing_variable():
    """Test that missing variables don't cause crashes."""
    # This should not crash even though we don't provide the 'lang' variable
    result = translate("Language set to {lang}!", "en")
    # SafeDict will leave the placeholder as-is
    assert "{lang}" in result


def test_translate_safe_formatting():
    """Test that the formatting is safe and doesn't crash on edge cases."""
    # Test with extra variables
    result = translate("Success", "en", extra="value")
    assert result == "Success"
    
    # Test with empty variables dict
    result = translate("Success", "en")
    assert result == "Success"


def test_locale_files_exist():
    """Test that required locale files exist."""
    base_dir = Path(__file__).parent.parent / "src" / "languages" / "i18n"
    
    assert (base_dir / "en.json").exists(), "en.json must exist"
    assert (base_dir / "ru.json").exists(), "ru.json must exist"
    assert (base_dir / "lt.json").exists(), "lt.json must exist"


def test_locale_files_valid_json():
    """Test that all locale files are valid JSON."""
    base_dir = Path(__file__).parent.parent / "src" / "languages" / "i18n"
    
    for locale_file in base_dir.glob("*.json"):
        with open(locale_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert isinstance(data, dict), f"{locale_file.name} must be a JSON object"


def test_required_keys_in_english():
    """Test that required keys exist in the English locale."""
    base_dir = Path(__file__).parent.parent / "src" / "languages" / "i18n"
    en_file = base_dir / "en.json"
    
    with open(en_file, 'r', encoding='utf-8') as f:
        en_data = json.load(f)
    
    required_keys = [
        "News processing",
        "Mode",
        "Locales captured",
        "English content",
        "Language set to {lang}!",
        "Success",
        "Error",
        "Select your language",
        "Twitch panel sent successfully!",
    ]
    
    for key in required_keys:
        assert key in en_data, f"Required key '{key}' missing from en.json"


if __name__ == "__main__":
    # Allow running tests directly without pytest
    print("Running tests without pytest...")
    try:
        test_safe_dict()
        print("✓ test_safe_dict passed")
        test_translate_basic()
        print("✓ test_translate_basic passed")
        test_translate_with_variables()
        print("✓ test_translate_with_variables passed")
        test_translate_fallback_to_english()
        print("✓ test_translate_fallback_to_english passed")
        test_translate_missing_key()
        print("✓ test_translate_missing_key passed")
        test_translate_none_locale()
        print("✓ test_translate_none_locale passed")
        test_translate_missing_variable()
        print("✓ test_translate_missing_variable passed")
        test_translate_safe_formatting()
        print("✓ test_translate_safe_formatting passed")
        test_locale_files_exist()
        print("✓ test_locale_files_exist passed")
        test_locale_files_valid_json()
        print("✓ test_locale_files_valid_json passed")
        test_required_keys_in_english()
        print("✓ test_required_keys_in_english passed")
        print("\n✓ All tests passed!")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
