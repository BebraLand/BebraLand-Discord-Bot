import json
import logging
import os

CONFIG_FILE = "config/config.json"
USER_LANGUAGES_FILE = "config/users_language.json"

def load_config():
	with open(CONFIG_FILE, "r", encoding="utf-8") as f:
		return json.load(f)

def save_config(new_data: dict):
	with open(CONFIG_FILE, "w", encoding="utf-8") as f:
		json.dump(new_data, f, indent=4, ensure_ascii=False)

def load_user_languages():
	"""Load user language preferences from users_language.json"""
	try:
		if os.path.exists(USER_LANGUAGES_FILE):
			with open(USER_LANGUAGES_FILE, "r", encoding="utf-8") as f:
				return json.load(f)
		else:
			# Create empty file if it doesn't exist
			return {}
	except Exception as e:
		logging.error(f"Error loading user languages: {e}")
		return {}

def save_user_languages(user_languages: dict):
	"""Save user language preferences to users_language.json"""
	try:
		# Ensure config directory exists
		os.makedirs(os.path.dirname(USER_LANGUAGES_FILE), exist_ok=True)
		
		with open(USER_LANGUAGES_FILE, "w", encoding="utf-8") as f:
			json.dump(user_languages, f, indent=4, ensure_ascii=False)
	except Exception as e:
		logging.error(f"Error saving user languages: {e}")
		raise

def get_user_language(user_id: int) -> str:
	"""Get user's preferred language, defaults to 'en' if not set"""
	try:
		user_languages = load_user_languages()
		return user_languages.get(str(user_id), "en")
	except Exception as e:
		logging.error(f"Error getting user language for {user_id}: {e}")
		return "en"

def set_user_language(user_id: int, language: str):
	"""Set user's preferred language. If language is 'en' (default), remove user from storage to save space."""
	try:
		user_languages = load_user_languages()
		
		if language == "en":
			# Remove user from storage if they select English (default language)
			if str(user_id) in user_languages:
				del user_languages[str(user_id)]
				logging.info(f"Removed user {user_id} from language storage (using default 'en')")
			else:
				logging.info(f"User {user_id} selected default language 'en' (no storage needed)")
		else:
			# Set the user's language preference for non-default languages
			user_languages[str(user_id)] = language
			logging.info(f"Set language '{language}' for user {user_id}")
		
		# Save the updated user languages
		save_user_languages(user_languages)
		
	except Exception as e:
		logging.error(f"Error setting user language for {user_id}: {e}")
		raise