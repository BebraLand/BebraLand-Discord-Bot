"""
Unit tests for the validate_translations script.

Run with: pytest test/test_validate_translations.py -v
"""

import json
import sys
import tempfile
from pathlib import Path

# Add parent directory to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.validate_translations import (
    load_locale,
    compare_locales,
    report_differences,
    autofill_missing,
)


def create_test_locales(tmp_dir: Path):
    """Create a temporary locale structure for testing."""
    i18n_dir = tmp_dir / "src" / "languages" / "i18n"
    i18n_dir.mkdir(parents=True)
    
    # Create en.json with baseline keys
    en_data = {
        "key1": "Value 1",
        "key2": "Value 2",
        "key3": "Value with {var}",
    }
    with open(i18n_dir / "en.json", 'w', encoding='utf-8') as f:
        json.dump(en_data, f, indent=2)
    
    # Create ru.json with one missing key and one extra key
    ru_data = {
        "key1": "Значение 1",
        "key2": "Значение 2",
        # key3 is missing
        "extra_key": "Extra value",
    }
    with open(i18n_dir / "ru.json", 'w', encoding='utf-8') as f:
        json.dump(ru_data, f, indent=2, ensure_ascii=False)
    
    return i18n_dir


def test_load_locale():
    """Test loading a locale file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        locale_file = tmp_path / "test.json"
        
        # Create a test locale file
        test_data = {"key": "value"}
        with open(locale_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)
        
        # Load it
        loaded = load_locale(locale_file)
        assert loaded == test_data


def test_load_invalid_locale():
    """Test loading an invalid locale file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        locale_file = tmp_path / "invalid.json"
        
        # Create an invalid JSON file
        with open(locale_file, 'w') as f:
            f.write("{ invalid json")
        
        # Should return empty dict
        loaded = load_locale(locale_file)
        assert loaded == {}


def test_compare_locales():
    """Test comparing two locales."""
    en_data = {"key1": "val1", "key2": "val2", "key3": "val3"}
    ru_data = {"key1": "val1_ru", "key2": "val2_ru", "extra": "extra_val"}
    
    missing, extra = compare_locales(en_data, ru_data, "ru")
    
    assert missing == ["key3"]
    assert extra == ["extra"]


def test_compare_identical_locales():
    """Test comparing identical locales."""
    en_data = {"key1": "val1", "key2": "val2"}
    ru_data = {"key1": "val1_ru", "key2": "val2_ru"}
    
    missing, extra = compare_locales(en_data, ru_data, "ru")
    
    assert missing == []
    assert extra == []


def test_report_differences():
    """Test reporting differences between locales."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        create_test_locales(tmp_path)
        
        # This should return False because there are differences
        result = report_differences(tmp_path)
        assert result == False


def test_autofill_missing():
    """Test autofilling missing keys."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        i18n_dir = create_test_locales(tmp_path)
        
        # Autofill missing keys
        autofill_missing(tmp_path)
        
        # Check that key3 was added to ru.json
        ru_file = i18n_dir / "ru.json"
        with open(ru_file, 'r', encoding='utf-8') as f:
            ru_data = json.load(f)
        
        assert "key3" in ru_data
        assert ru_data["key3"] == "[MISSING TRANSLATION] Value with {var}"


def test_real_locales_structure():
    """Test that the actual project locale structure is valid."""
    base_dir = Path(__file__).parent.parent
    i18n_dir = base_dir / "src" / "languages" / "i18n"
    
    # Check that the directory exists
    assert i18n_dir.exists(), "i18n directory should exist"
    
    # Check that en.json exists
    en_file = i18n_dir / "en.json"
    assert en_file.exists(), "en.json should exist"
    
    # Load and validate en.json
    en_data = load_locale(en_file)
    assert len(en_data) > 0, "en.json should not be empty"
    
    # Check that all values are strings
    for key, value in en_data.items():
        assert isinstance(key, str), f"Key {key} should be a string"
        assert isinstance(value, str), f"Value for key {key} should be a string"


if __name__ == "__main__":
    # Allow running tests directly without pytest
    print("Running tests without pytest...")
    try:
        test_load_locale()
        print("✓ test_load_locale passed")
        test_load_invalid_locale()
        print("✓ test_load_invalid_locale passed")
        test_compare_locales()
        print("✓ test_compare_locales passed")
        test_compare_identical_locales()
        print("✓ test_compare_identical_locales passed")
        test_report_differences()
        print("✓ test_report_differences passed")
        test_autofill_missing()
        print("✓ test_autofill_missing passed")
        test_real_locales_structure()
        print("✓ test_real_locales_structure passed")
        print("\n✓ All tests passed!")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
