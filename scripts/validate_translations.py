#!/usr/bin/env python3
"""
Translation validation script for BebraLand Discord Bot.

This script compares all locale JSON files against the canonical English locale (en.json)
and reports missing or extra keys. It can also autofill missing keys with English values
prefixed with [MISSING TRANSLATION].

Usage:
    python scripts/validate_translations.py --report
    python scripts/validate_translations.py --autofill-missing
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def load_locale(locale_path: Path) -> Dict[str, str]:
    """Load a locale JSON file.
    
    Args:
        locale_path: Path to the locale JSON file.
        
    Returns:
        Dictionary of translation keys and values.
    """
    try:
        with open(locale_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, dict):
                print(f"Warning: {locale_path} does not contain a JSON object")
                return {}
            return data
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse {locale_path}: {e}")
        return {}
    except Exception as e:
        print(f"Error: Failed to load {locale_path}: {e}")
        return {}


def save_locale(locale_path: Path, data: Dict[str, str]) -> None:
    """Save a locale JSON file with proper formatting.
    
    Args:
        locale_path: Path to the locale JSON file.
        data: Dictionary of translation keys and values.
    """
    with open(locale_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {locale_path}")


def compare_locales(en_data: Dict[str, str], locale_data: Dict[str, str], locale_name: str) -> Tuple[List[str], List[str]]:
    """Compare a locale against the English baseline.
    
    Args:
        en_data: English locale data.
        locale_data: Target locale data.
        locale_name: Name of the target locale (e.g., 'ru', 'lt').
        
    Returns:
        Tuple of (missing_keys, extra_keys).
    """
    en_keys = set(en_data.keys())
    locale_keys = set(locale_data.keys())
    
    missing_keys = sorted(en_keys - locale_keys)
    extra_keys = sorted(locale_keys - en_keys)
    
    return missing_keys, extra_keys


def report_differences(base_dir: Path) -> bool:
    """Report differences between locales and English.
    
    Args:
        base_dir: Base directory containing i18n folder.
        
    Returns:
        True if all locales are in sync, False otherwise.
    """
    i18n_dir = base_dir / "src" / "languages" / "i18n"
    en_path = i18n_dir / "en.json"
    
    if not en_path.exists():
        print(f"Error: English locale file not found at {en_path}")
        return False
    
    en_data = load_locale(en_path)
    if not en_data:
        print("Error: English locale is empty or invalid")
        return False
    
    print(f"English locale (en.json) has {len(en_data)} keys\n")
    
    all_in_sync = True
    
    for locale_file in sorted(i18n_dir.glob("*.json")):
        if locale_file.name == "en.json":
            continue
            
        locale_name = locale_file.stem
        locale_data = load_locale(locale_file)
        
        missing_keys, extra_keys = compare_locales(en_data, locale_data, locale_name)
        
        print(f"Locale: {locale_name} ({locale_file.name})")
        print(f"  Total keys: {len(locale_data)}")
        
        if missing_keys:
            all_in_sync = False
            print(f"  Missing keys ({len(missing_keys)}):")
            for key in missing_keys:
                print(f"    - {key}")
        else:
            print("  ✓ No missing keys")
        
        if extra_keys:
            all_in_sync = False
            print(f"  Extra keys ({len(extra_keys)}):")
            for key in extra_keys:
                print(f"    + {key}")
        else:
            print("  ✓ No extra keys")
        
        print()
    
    if all_in_sync:
        print("✓ All locales are in sync with English!")
    else:
        print("✗ Some locales have differences")
    
    return all_in_sync


def autofill_missing(base_dir: Path) -> None:
    """Autofill missing keys in locales with English values prefixed with [MISSING TRANSLATION].
    
    Args:
        base_dir: Base directory containing i18n folder.
    """
    i18n_dir = base_dir / "src" / "languages" / "i18n"
    en_path = i18n_dir / "en.json"
    
    if not en_path.exists():
        print(f"Error: English locale file not found at {en_path}")
        return
    
    en_data = load_locale(en_path)
    if not en_data:
        print("Error: English locale is empty or invalid")
        return
    
    print(f"English locale (en.json) has {len(en_data)} keys\n")
    
    for locale_file in sorted(i18n_dir.glob("*.json")):
        if locale_file.name == "en.json":
            continue
            
        locale_name = locale_file.stem
        locale_data = load_locale(locale_file)
        
        missing_keys, _ = compare_locales(en_data, locale_data, locale_name)
        
        if missing_keys:
            print(f"Autofilling {len(missing_keys)} missing keys in {locale_name}:")
            for key in missing_keys:
                locale_data[key] = f"[MISSING TRANSLATION] {en_data[key]}"
                print(f"  + {key}")
            
            # Sort keys to match en.json order
            sorted_data = {k: locale_data[k] for k in sorted(locale_data.keys())}
            save_locale(locale_file, sorted_data)
            print()
        else:
            print(f"No missing keys in {locale_name}, skipping\n")


def main():
    """Main entry point for the validation script."""
    parser = argparse.ArgumentParser(
        description="Validate translation files against the canonical English locale."
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Report missing and extra keys in all locales"
    )
    parser.add_argument(
        "--autofill-missing",
        action="store_true",
        help="Autofill missing keys with English values prefixed with [MISSING TRANSLATION]"
    )
    
    args = parser.parse_args()
    
    if not args.report and not args.autofill_missing:
        parser.print_help()
        sys.exit(1)
    
    # Get the repository root (parent of scripts directory)
    base_dir = Path(__file__).parent.parent
    
    if args.report:
        all_in_sync = report_differences(base_dir)
        sys.exit(0 if all_in_sync else 1)
    
    if args.autofill_missing:
        autofill_missing(base_dir)


if __name__ == "__main__":
    main()
