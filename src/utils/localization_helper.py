import discord
import logging
from typing import Optional, Dict, Any, List, Union
from .localization import LocalizationManager
from .config_manager import load_config

# Set up logging
logger = logging.getLogger(__name__)

# Initialize localization manager
loc_manager = LocalizationManager()

class LocalizationHelper:
	"""Comprehensive localization utility with helper methods for Discord bot."""
	
	def __init__(self, bot: Optional[discord.Bot] = None):
		self.bot = bot
		self.config = load_config()
		self.loc_manager = loc_manager
	
	def get_text(self, key: str, user_id: Optional[int] = None, lang_code: Optional[str] = None, **kwargs) -> str:
		"""Get localized text with fallback handling.
		
		Args:
			key: The localization key to retrieve
			user_id: Discord user ID to get their preferred language
			lang_code: Override language code (takes priority over user_id)
			**kwargs: Format parameters for the localized string
		"""
		return self.loc_manager.get(key, user_id=user_id, lang_code=lang_code, **kwargs)
	
	def create_embed(
		self,
		title_key: Optional[str] = None,
		description_key: Optional[str] = None,
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		color: Optional[str] = None,
		embed_type: str = "default",
		**format_kwargs
	) -> discord.Embed:
		"""Create a localized embed with consistent styling.
		
		Args:
			title_key: Localization key for embed title
			description_key: Localization key for embed description
			user_id: Discord user ID for language preference
			lang_code: Override language code
			color: Custom color (hex string without #)
			embed_type: Type of embed (default, success, error, warning)
			**format_kwargs: Format parameters for localized strings
		"""
		# Set embed color using localized color system
		if color:
			if isinstance(color, str):
				# Use the embed_type parameter or color string to get appropriate color
				embed_type_for_color = color if color in ["success", "error", "warning", "info", "default"] else embed_type
				embed = discord.Embed(color=self.get_localized_embed_color(embed_type_for_color, user_id, lang_code))
			elif isinstance(color, int):
				embed = discord.Embed(color=color)
			else:
				# Fallback to default color
				embed = discord.Embed(color=self.get_localized_embed_color("default", user_id, lang_code))
		else:
			embed = discord.Embed(color=self.get_localized_embed_color(embed_type, user_id, lang_code))
		
		# Set title if provided
		if title_key:
			title = self.get_text(title_key, user_id=user_id, lang_code=lang_code, **format_kwargs)
			embed.title = title
		
		# Set description if provided
		if description_key:
			description = self.get_text(description_key, user_id=user_id, lang_code=lang_code, **format_kwargs)
			embed.description = description
		
		# Add localized footer with bot avatar
		self.set_localized_footer(embed, user_id=user_id, lang_code=lang_code)
		
		return embed
	
	def create_success_embed(
		self,
		title_key: str,
		description_key: str,
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		**format_kwargs
	) -> discord.Embed:
		"""Create a success embed with green color."""
		return self.create_embed(
			title_key=title_key,
			description_key=description_key,
			user_id=user_id,
			lang_code=lang_code,
			embed_type="success",
			**format_kwargs
		)
	
	def create_error_embed(
		self,
		title_key: str,
		description_key: str,
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		**format_kwargs
	) -> discord.Embed:
		"""Create an error embed with red color."""
		return self.create_embed(
			title_key=title_key,
			description_key=description_key,
			user_id=user_id,
			lang_code=lang_code,
			embed_type="error",
			**format_kwargs
		)
	
	def create_warning_embed(
		self,
		title_key: str,
		description_key: str,
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		**format_kwargs
	) -> discord.Embed:
		"""Create a warning embed with orange color."""
		return self.create_embed(
			title_key=title_key,
			description_key=description_key,
			user_id=user_id,
			lang_code=lang_code,
			embed_type="warning",
			**format_kwargs
		)
	
	def add_localized_field(
		self,
		embed: discord.Embed,
		name_key: str,
		value_key: str,
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		inline: bool = False,
		**format_kwargs
	) -> discord.Embed:
		"""Add a localized field to an existing embed.
		
		Args:
			embed: The embed to add the field to
			name_key: Localization key for field name
			value_key: Localization key for field value
			user_id: Discord user ID for language preference
			lang_code: Override language code
			inline: Whether the field should be inline
			**format_kwargs: Format parameters for localized strings
		"""
		name = self.get_text(name_key, user_id=user_id, lang_code=lang_code, **format_kwargs)
		value = self.get_text(value_key, user_id=user_id, lang_code=lang_code, **format_kwargs)
		embed.add_field(name=name, value=value, inline=inline)
		return embed
	
	def get_error_message(
		self,
		error_key: str,
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		**format_kwargs
	) -> str:
		"""Get a localized error message with consistent formatting.
		
		Args:
			error_key: Localization key for the error message
			user_id: Discord user ID for language preference
			lang_code: Override language code
			**format_kwargs: Format parameters for localized strings
		"""
		error_msg = self.get_text(error_key, user_id=user_id, lang_code=lang_code, **format_kwargs)
		logger.error(f"Error message sent to user {user_id}: {error_msg}")
		return error_msg
	
	def log_missing_translation(self, key: str, lang_code: str, user_id: Optional[int] = None):
		"""Log missing translation keys for debugging.
		
		Args:
			key: The missing localization key
			lang_code: The language code where the key is missing
			user_id: Optional user ID for context
		"""
		context = f" (user: {user_id})" if user_id else ""
		logger.warning(f"Missing translation key '{key}' for language '{lang_code}'{context}")
	
	def get_available_languages(self) -> Dict[str, str]:
		"""Get a dictionary of available languages with their display names.
		
		Returns:
			Dict mapping language codes to display names
		"""
		return {
			"en": "English",
			"lt": "Lietuvių",
			"ru": "Русский"
		}
	
	def validate_language_code(self, lang_code: str) -> bool:
		"""Validate if a language code is supported.
		
		Args:
			lang_code: The language code to validate
			
		Returns:
			True if the language is supported, False otherwise
		"""
		return lang_code in self.get_available_languages()
	
	def create_info_embed(
		self,
		title_key: str,
		description_key: str,
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		**format_kwargs
	) -> discord.Embed:
		"""Create an info embed with default color."""
		return self.create_embed(
			title_key=title_key,
			description_key=description_key,
			user_id=user_id,
			lang_code=lang_code,
			embed_type="default",
			**format_kwargs
		)
	
	def create_localized_footer(
		self,
		footer_key: Optional[str] = None,
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		**format_kwargs
	) -> str:
		"""Create a localized footer text.
		
		Args:
			footer_key: Localization key for footer text (optional)
			user_id: Discord user ID for language preference
			lang_code: Override language code
			**format_kwargs: Format parameters for localized strings
			
		Returns:
			Localized footer text or default trademark
		"""
		if footer_key:
			return self.get_text(footer_key, user_id=user_id, lang_code=lang_code, **format_kwargs)
		return self.config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮")
	
	def set_localized_footer(
		self,
		embed: discord.Embed,
		footer_key: Optional[str] = None,
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		**format_kwargs
	) -> discord.Embed:
		"""Set a localized footer on an existing embed.
		
		Args:
			embed: The embed to set the footer on
			footer_key: Localization key for footer text (optional)
			user_id: Discord user ID for language preference
			lang_code: Override language code
			**format_kwargs: Format parameters for localized strings
		"""
		footer_text = self.create_localized_footer(footer_key, user_id, lang_code, **format_kwargs)
		
		if self.bot and self.bot.user:
			embed.set_footer(text=footer_text, icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
		else:
			embed.set_footer(text=footer_text)
		
		return embed
	
	def get_localized_choice_list(
		self,
		choices: List[str],
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		**format_kwargs
	) -> List[str]:
		"""Get a list of localized choices.
		
		Args:
			choices: List of localization keys
			user_id: Discord user ID for language preference
			lang_code: Override language code
			**format_kwargs: Format parameters for localized strings
			
		Returns:
			List of localized choice strings
		"""
		return [self.get_text(choice, user_id=user_id, lang_code=lang_code, **format_kwargs) for choice in choices]
	
	def format_user_mention(
		self,
		message_key: str,
		user: Union[discord.User, discord.Member],
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		**format_kwargs
	) -> str:
		"""Format a localized message with user mention.
		
		Args:
			message_key: Localization key for the message
			user: Discord user or member to mention
			user_id: Discord user ID for language preference (defaults to mentioned user)
			lang_code: Override language code
			**format_kwargs: Additional format parameters
			
		Returns:
			Localized message with user mention
		"""
		target_user_id = user_id or user.id
		format_kwargs.update({
			'user_mention': user.mention,
			'user_name': user.display_name,
			'user_id': user.id
		})
		
		return self.get_text(message_key, user_id=target_user_id, lang_code=lang_code, **format_kwargs)
	
	def create_paginated_embed_list(
		self,
		items: List[Any],
		title_key: str,
		description_key: Optional[str] = None,
		items_per_page: int = 10,
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		embed_type: str = "default",
		**format_kwargs
	) -> List[discord.Embed]:
		"""Create a list of paginated embeds for large datasets.
		
		Args:
			items: List of items to paginate
			title_key: Localization key for embed title
			description_key: Localization key for embed description (optional)
			items_per_page: Number of items per page
			user_id: Discord user ID for language preference
			lang_code: Override language code
			embed_type: Type of embed (default, success, error, warning)
			**format_kwargs: Format parameters for localized strings
			
		Returns:
			List of paginated embeds
		"""
		embeds = []
		total_pages = (len(items) + items_per_page - 1) // items_per_page
		
		for page in range(total_pages):
			start_idx = page * items_per_page
			end_idx = min(start_idx + items_per_page, len(items))
			page_items = items[start_idx:end_idx]
			
			# Add pagination info to format kwargs
			page_format_kwargs = format_kwargs.copy()
			page_format_kwargs.update({
				'current_page': page + 1,
				'total_pages': total_pages,
				'items_count': len(items),
				'page_items_count': len(page_items)
			})
			
			embed = self.create_embed(
				title_key=title_key,
				description_key=description_key,
				user_id=user_id,
				lang_code=lang_code,
				embed_type=embed_type,
				**page_format_kwargs
			)
			
			embeds.append(embed)
		
		return embeds
	
	def get_language_display_name(
		self,
		lang_code: str,
		display_in_lang: Optional[str] = None,
		user_id: Optional[int] = None
	) -> str:
		"""Get the display name of a language, optionally in another language.
		
		Args:
			lang_code: The language code to get the display name for
			display_in_lang: Language to display the name in (optional)
			user_id: User ID for language preference if display_in_lang not provided
			
		Returns:
			Display name of the language
		"""
		# Try to get localized language names
		lang_key = f"LANGUAGE_NAME_{lang_code.upper()}"
		
		try:
			return self.get_text(lang_key, user_id=user_id, lang_code=display_in_lang)
		except:
			# Fallback to hardcoded names
			lang_names = {
				"en": "English",
				"lt": "Lietuvių",
				"ru": "Русский"
			}
			return lang_names.get(lang_code, lang_code.upper())
	
	def create_command_help_embed(
		self,
		command_name: str,
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		**format_kwargs
	) -> discord.Embed:
		"""Create a standardized help embed for commands.
		
		Args:
			command_name: Name of the command
			user_id: Discord user ID for language preference
			lang_code: Override language code
			**format_kwargs: Additional format parameters
			
		Returns:
			Localized help embed
		"""
		title_key = f"{command_name.upper()}_COMMAND_HELP_TITLE"
		description_key = f"{command_name.upper()}_COMMAND_HELP_DESC"
		
		format_kwargs.update({'command_name': command_name})
		
		return self.create_info_embed(
			title_key=title_key,
			description_key=description_key,
			user_id=user_id,
			lang_code=lang_code,
			**format_kwargs
		)
	
	def get_localized_embed_color(self, embed_type: str = "default", user_id: Optional[int] = None, lang_code: Optional[str] = None) -> int:
		"""Get embed color with potential localization support.
		
		Args:
			embed_type: Type of embed (success, error, warning, info, default)
			user_id: Discord user ID for language preference
			lang_code: Override language code
			
		Returns:
			Color value as integer
		"""
		color_map = {
			"success": 0x00FF00,  # Green
			"error": 0xFF0000,    # Red
			"warning": 0xFFFF00,  # Yellow
			"info": 0x0099FF,     # Blue
			"default": int(self.config.get("DISCORD_EMBED_COLOR", "714C35"), 16)
		}
		
		# Future: Could add language-specific color preferences here
		# For now, return standard colors
		return color_map.get(embed_type, color_map["default"])
	
	def create_localized_embed_with_fields(
		self,
		title_key: str,
		description_key: Optional[str] = None,
		fields: Optional[List[Dict[str, Any]]] = None,
		embed_type: str = "default",
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		**format_kwargs
	) -> discord.Embed:
		"""Create a comprehensive localized embed with multiple fields.
		
		Args:
			title_key: Localization key for embed title
			description_key: Localization key for embed description (optional)
			fields: List of field dictionaries with 'name_key', 'value_key', and optional 'inline'
			embed_type: Type of embed for color selection
			user_id: Discord user ID for language preference
			lang_code: Override language code
			**format_kwargs: Format parameters for localized strings
			
		Returns:
			Localized Discord embed with fields
		"""
		# Create base embed
		embed = self.create_embed(
			title_key=title_key,
			description_key=description_key,
			embed_type=embed_type,
			user_id=user_id,
			lang_code=lang_code,
			**format_kwargs
		)
		
		# Add localized fields if provided
		if fields:
			for field in fields:
				name_key = field.get('name_key')
				value_key = field.get('value_key')
				inline = field.get('inline', False)
				
				if name_key and value_key:
					self.add_localized_field(
						embed=embed,
						name_key=name_key,
						value_key=value_key,
						user_id=user_id,
						lang_code=lang_code,
						inline=inline,
						**format_kwargs
					)
		
		return embed
	
	def get_localization_stats(self) -> Dict[str, Any]:
		"""Get comprehensive localization statistics.
		
		Returns:
			Dictionary with localization statistics
		"""
		stats = {
			'supported_languages': list(self.get_available_languages().keys()),
			'missing_keys_by_language': self.loc_manager.get_missing_keys_stats(),
			'language_completeness': self.loc_manager.validate_language_completeness()
		}
		
		return stats
	
	def log_localization_usage(
		self,
		key: str,
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		context: str = "unknown"
	) -> None:
		"""Log localization key usage for analytics.
		
		Args:
			key: The localization key used
			user_id: Discord user ID
			lang_code: Language code used
			context: Context where the key was used (command, event, etc.)
		"""
		logger.debug(f"Localization usage - Key: {key}, User: {user_id}, Lang: {lang_code}, Context: {context}")

# Global instance for easy access
localization_helper = LocalizationHelper()

# Convenience functions for backward compatibility and easy access
def get_localized_text(key: str, user_id: Optional[int] = None, lang_code: Optional[str] = None, **kwargs) -> str:
	"""Get localized text using the global helper instance."""
	return localization_helper.get_text(key, user_id=user_id, lang_code=lang_code, **kwargs)

def create_localized_embed(
	title_key: Optional[str] = None,
	description_key: Optional[str] = None,
	user_id: Optional[int] = None,
	lang_code: Optional[str] = None,
	color: Optional[str] = None,
	embed_type: str = "default",
	**format_kwargs
) -> discord.Embed:
	"""Create a localized embed using the global helper instance."""
	return localization_helper.create_embed(
		title_key=title_key,
		description_key=description_key,
		user_id=user_id,
		lang_code=lang_code,
		color=color,
		embed_type=embed_type,
		**format_kwargs
	)

def create_success_embed(title_key: str, description_key: str, user_id: Optional[int] = None, lang_code: Optional[str] = None, **kwargs) -> discord.Embed:
	"""Create a success embed using the global helper instance."""
	return localization_helper.create_success_embed(title_key, description_key, user_id, lang_code, **kwargs)

def create_error_embed(title_key: str, description_key: str, user_id: Optional[int] = None, lang_code: Optional[str] = None, **kwargs) -> discord.Embed:
	"""Create an error embed using the global helper instance."""
	return localization_helper.create_error_embed(title_key, description_key, user_id, lang_code, **kwargs)

def create_warning_embed(title_key: str, description_key: str, user_id: Optional[int] = None, lang_code: Optional[str] = None, **kwargs) -> discord.Embed:
	"""Create a warning embed using the global helper instance."""
	return localization_helper.create_warning_embed(title_key, description_key, user_id, lang_code, **kwargs)

def create_info_embed(title_key: str, description_key: str, user_id: Optional[int] = None, lang_code: Optional[str] = None, **kwargs) -> discord.Embed:
	"""Create an info embed using the global helper instance."""
	return localization_helper.create_info_embed(title_key, description_key, user_id, lang_code, **kwargs)

def get_error_message(error_key: str, user_id: Optional[int] = None, lang_code: Optional[str] = None, **kwargs) -> str:
	"""Get a localized error message using the global helper instance."""
	return localization_helper.get_error_message(error_key, user_id, lang_code, **kwargs)

def format_user_mention(message_key: str, user: Union[discord.User, discord.Member], user_id: Optional[int] = None, lang_code: Optional[str] = None, **kwargs) -> str:
	"""Format a localized message with user mention using the global helper instance."""
	return localization_helper.format_user_mention(message_key, user, user_id, lang_code, **kwargs)

def get_localization_stats() -> Dict[str, Any]:
	"""Get comprehensive localization statistics using the global helper instance."""
	return localization_helper.get_localization_stats()

def validate_language_code(lang_code: str) -> bool:
	"""Validate if a language code is supported using the global helper instance."""
	return localization_helper.validate_language_code(lang_code)

def get_available_languages() -> Dict[str, str]:
	"""Get available languages using the global helper instance."""
	return localization_helper.get_available_languages()