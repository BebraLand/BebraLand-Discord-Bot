"""Error embed creation helpers for the Discord bot.

This module provides utilities for creating user-friendly error embeds with
localization support, consistent styling, and proper error context.
"""

import discord
from typing import Optional, Dict, Any, Union, List
from datetime import datetime

from .exceptions import (
	BotError, PermissionError, BotPermissionError, ValidationError,
	CooldownError, RateLimitError, APIError, DatabaseError,
	ConfigurationError, LocalizationError, UserNotFoundError,
	ChannelNotFoundError, GuildNotFoundError, FileOperationError,
	CommandExecutionError, MaintenanceError
)
from .localization_helper import LocalizationHelper
from .config_manager import load_config

# Initialize dependencies
config = load_config()
loc_helper = LocalizationHelper()


class ErrorEmbedBuilder:
	"""Builder class for creating error embeds with consistent styling."""
	
	def __init__(self, bot: Optional[discord.Bot] = None):
		self.bot = bot
		self.config = config
		self.loc_helper = loc_helper
	
		# Error type to color mapping
		self.error_colors = {
			"error": 0xFF0000,      # Red
			"warning": 0xFFA500,    # Orange
			"permission": 0xFF6B6B, # Light red
			"cooldown": 0xFFD700,   # Gold
			"validation": 0xFF8C00, # Dark orange
			"api": 0xFF4500,        # Orange red
			"database": 0xDC143C,   # Crimson
			"maintenance": 0x808080 # Gray
		}
	
	def create_error_embed(
		self,
		error: Exception,
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		error_id: Optional[str] = None,
		include_support_info: bool = True
	) -> discord.Embed:
		"""Create an error embed based on exception type.
		
		Args:
			error: The exception that occurred
			user_id: Discord user ID for localization
			lang_code: Override language code
			error_id: Unique error ID for tracking
			include_support_info: Whether to include support information
			
		Returns:
			Formatted Discord embed
		"""
		# Determine error type and get appropriate handler
		if isinstance(error, BotError):
			return self._create_bot_error_embed(error, user_id, lang_code, error_id, include_support_info)
		else:
			return self._create_generic_error_embed(error, user_id, lang_code, error_id, include_support_info)
	
	def create_permission_error_embed(
		self,
		missing_permissions: List[str],
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		is_bot_permission: bool = False
	) -> discord.Embed:
		"""Create a permission error embed.
		
		Args:
			missing_permissions: List of missing permission names
			user_id: Discord user ID for localization
			lang_code: Override language code
			is_bot_permission: Whether it's a bot permission error
			
		Returns:
			Formatted Discord embed
		"""
		if is_bot_permission:
			title_key = "errors.bot_missing_permissions.title"
			desc_key = "errors.bot_missing_permissions.description"
		else:
			title_key = "errors.user_missing_permissions.title"
			desc_key = "errors.user_missing_permissions.description"
		
		# Format permissions list
		permissions_text = self._format_permissions_list(missing_permissions, user_id, lang_code)
		
		embed = discord.Embed(
			title=self.loc_helper.get_text(title_key, user_id=user_id, lang_code=lang_code),
			description=self.loc_helper.get_text(
				desc_key,
				user_id=user_id,
				lang_code=lang_code,
				permissions=permissions_text
			),
			color=self.error_colors["permission"]
		)
		
		self._add_standard_footer(embed, user_id, lang_code)
		return embed
	
	def create_cooldown_error_embed(
		self,
		retry_after: float,
		cooldown_type: Optional[str] = None,
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None
	) -> discord.Embed:
		"""Create a cooldown error embed.
		
		Args:
			retry_after: Seconds until cooldown expires
			cooldown_type: Type of cooldown (user, guild, etc.)
			user_id: Discord user ID for localization
			lang_code: Override language code
			
		Returns:
			Formatted Discord embed
		"""
		# Format time remaining
		time_text = self._format_duration(retry_after, user_id, lang_code)
		
		embed = discord.Embed(
			title=self.loc_helper.get_text("errors.cooldown.title", user_id=user_id, lang_code=lang_code),
			description=self.loc_helper.get_text(
				"errors.cooldown.description",
				user_id=user_id,
				lang_code=lang_code,
				time_remaining=time_text
			),
			color=self.error_colors["cooldown"]
		)
		
		if cooldown_type:
			embed.add_field(
				name=self.loc_helper.get_text("errors.cooldown.type_field", user_id=user_id, lang_code=lang_code),
				value=cooldown_type.title(),
				inline=True
			)
		
		self._add_standard_footer(embed, user_id, lang_code)
		return embed
	
	def create_validation_error_embed(
		self,
		validation_errors: Union[str, List[str]],
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None
	) -> discord.Embed:
		"""Create a validation error embed.
		
		Args:
			validation_errors: Error message(s) or list of errors
			user_id: Discord user ID for localization
			lang_code: Override language code
			
		Returns:
			Formatted Discord embed
		"""
		if isinstance(validation_errors, str):
			error_text = validation_errors
		else:
			error_text = "\n".join(f"• {error}" for error in validation_errors)
		
		embed = discord.Embed(
			title=self.loc_helper.get_text("errors.validation.title", user_id=user_id, lang_code=lang_code),
			description=self.loc_helper.get_text(
				"errors.validation.description",
				user_id=user_id,
				lang_code=lang_code,
				errors=error_text
			),
			color=self.error_colors["validation"]
		)
		
		self._add_standard_footer(embed, user_id, lang_code)
		return embed
	
	def create_api_error_embed(
		self,
		api_name: str,
		status_code: Optional[int] = None,
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		retry_suggestion: bool = True
	) -> discord.Embed:
		"""Create an API error embed.
		
		Args:
			api_name: Name of the API service
			status_code: HTTP status code if available
			user_id: Discord user ID for localization
			lang_code: Override language code
			retry_suggestion: Whether to suggest retrying
			
		Returns:
			Formatted Discord embed
		"""
		embed = discord.Embed(
			title=self.loc_helper.get_text("errors.api.title", user_id=user_id, lang_code=lang_code),
			description=self.loc_helper.get_text(
				"errors.api.description",
				user_id=user_id,
				lang_code=lang_code,
				api_name=api_name
			),
			color=self.error_colors["api"]
		)
		
		if status_code:
			embed.add_field(
				name=self.loc_helper.get_text("errors.api.status_field", user_id=user_id, lang_code=lang_code),
				value=str(status_code),
				inline=True
			)
		
		if retry_suggestion:
			embed.add_field(
				name=self.loc_helper.get_text("errors.api.suggestion_field", user_id=user_id, lang_code=lang_code),
				value=self.loc_helper.get_text("errors.api.retry_suggestion", user_id=user_id, lang_code=lang_code),
				inline=False
			)
		
		self._add_standard_footer(embed, user_id, lang_code)
		return embed
	
	def create_maintenance_embed(
		self,
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None,
		estimated_duration: Optional[str] = None
	) -> discord.Embed:
		"""Create a maintenance mode embed.
		
		Args:
			user_id: Discord user ID for localization
			lang_code: Override language code
			estimated_duration: Estimated maintenance duration
			
		Returns:
			Formatted Discord embed
		"""
		embed = discord.Embed(
			title=self.loc_helper.get_text("errors.maintenance.title", user_id=user_id, lang_code=lang_code),
			description=self.loc_helper.get_text("errors.maintenance.description", user_id=user_id, lang_code=lang_code),
			color=self.error_colors["maintenance"]
		)
		
		if estimated_duration:
			embed.add_field(
				name=self.loc_helper.get_text("errors.maintenance.duration_field", user_id=user_id, lang_code=lang_code),
				value=estimated_duration,
				inline=True
			)
		
		self._add_standard_footer(embed, user_id, lang_code)
		return embed
	
	def create_not_found_embed(
		self,
		resource_type: str,
		search_term: Optional[str] = None,
		user_id: Optional[int] = None,
		lang_code: Optional[str] = None
	) -> discord.Embed:
		"""Create a 'not found' error embed.
		
		Args:
			resource_type: Type of resource (user, channel, guild, etc.)
			search_term: What was being searched for
			user_id: Discord user ID for localization
			lang_code: Override language code
			
		Returns:
			Formatted Discord embed
		"""
		embed = discord.Embed(
			title=self.loc_helper.get_text(
				f"errors.not_found.{resource_type}.title",
				user_id=user_id,
				lang_code=lang_code
			),
			description=self.loc_helper.get_text(
				f"errors.not_found.{resource_type}.description",
				user_id=user_id,
				lang_code=lang_code,
				search_term=search_term or "N/A"
			),
			color=self.error_colors["error"]
		)
		
		self._add_standard_footer(embed, user_id, lang_code)
		return embed
	
	def _create_bot_error_embed(
		self,
		error: BotError,
		user_id: Optional[int],
		lang_code: Optional[str],
		error_id: Optional[str],
		include_support_info: bool
	) -> discord.Embed:
		"""Create embed for custom bot errors."""
		# Map error types to embed creation methods
		if isinstance(error, PermissionError):
			return self.create_permission_error_embed(
				error.missing_permissions, user_id, lang_code, False
			)
		elif isinstance(error, BotPermissionError):
			return self.create_permission_error_embed(
				error.missing_permissions, user_id, lang_code, True
			)
		elif isinstance(error, CooldownError):
			return self.create_cooldown_error_embed(
				error.retry_after or 0, error.cooldown_type, user_id, lang_code
			)
		elif isinstance(error, ValidationError):
			return self.create_validation_error_embed(
				error.user_message, user_id, lang_code
			)
		elif isinstance(error, APIError):
			return self.create_api_error_embed(
				error.api_name or "Unknown API", error.status_code, user_id, lang_code
			)
		elif isinstance(error, MaintenanceError):
			return self.create_maintenance_embed(user_id, lang_code)
		elif isinstance(error, (UserNotFoundError, ChannelNotFoundError, GuildNotFoundError)):
			resource_type = type(error).__name__.replace("NotFoundError", "").lower()
			return self.create_not_found_embed(
				resource_type, str(error.search_term) if hasattr(error, 'search_term') else None,
				user_id, lang_code
			)
		else:
			# Generic bot error
			return self._create_generic_bot_error_embed(error, user_id, lang_code, error_id, include_support_info)
	
	def _create_generic_error_embed(
		self,
		error: Exception,
		user_id: Optional[int],
		lang_code: Optional[str],
		error_id: Optional[str],
		include_support_info: bool
	) -> discord.Embed:
		"""Create embed for generic Python exceptions."""
		embed = discord.Embed(
			title=self.loc_helper.get_text("errors.generic.title", user_id=user_id, lang_code=lang_code),
			description=self.loc_helper.get_text("errors.generic.description", user_id=user_id, lang_code=lang_code),
			color=self.error_colors["error"]
		)
		
		if error_id and include_support_info:
			embed.add_field(
				name=self.loc_helper.get_text("errors.generic.error_id_field", user_id=user_id, lang_code=lang_code),
				value=f"`{error_id}`",
				inline=True
			)
		
		self._add_standard_footer(embed, user_id, lang_code)
		if include_support_info:
			self._add_support_info(embed, user_id, lang_code)
		
		return embed
	
	def _create_generic_bot_error_embed(
		self,
		error: BotError,
		user_id: Optional[int],
		lang_code: Optional[str],
		error_id: Optional[str],
		include_support_info: bool
	) -> discord.Embed:
		"""Create embed for generic bot errors."""
		embed = discord.Embed(
			title=self.loc_helper.get_text("errors.bot.title", user_id=user_id, lang_code=lang_code),
			description=error.user_message,
			color=self.error_colors["error"]
		)
		
		if error.error_code:
			embed.add_field(
				name=self.loc_helper.get_text("errors.bot.error_code_field", user_id=user_id, lang_code=lang_code),
				value=f"`{error.error_code}`",
				inline=True
			)
		
		if error_id and include_support_info:
			embed.add_field(
				name=self.loc_helper.get_text("errors.bot.error_id_field", user_id=user_id, lang_code=lang_code),
				value=f"`{error_id}`",
				inline=True
			)
		
		self._add_standard_footer(embed, user_id, lang_code)
		if include_support_info:
			self._add_support_info(embed, user_id, lang_code)
		
		return embed
	
	def _add_standard_footer(self, embed: discord.Embed, user_id: Optional[int], lang_code: Optional[str]):
		"""Add standard footer to embed."""
		footer_text = self.config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand Bot")
		
		if self.bot and self.bot.user:
			embed.set_footer(text=footer_text, icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
		else:
			embed.set_footer(text=footer_text)
	
	def _add_support_info(self, embed: discord.Embed, user_id: Optional[int], lang_code: Optional[str]):
		"""Add support information to embed."""
		support_text = self.loc_helper.get_text("errors.support_info", user_id=user_id, lang_code=lang_code)
		
		# Add support info as a field if it doesn't make the embed too long
		if len(embed) + len(support_text) < 5900:  # Leave some buffer
			embed.add_field(
				name=self.loc_helper.get_text("errors.support_field", user_id=user_id, lang_code=lang_code),
				value=support_text,
				inline=False
			)
	
	def _format_permissions_list(self, permissions: List[str], user_id: Optional[int], lang_code: Optional[str]) -> str:
		"""Format permissions list for display."""
		if not permissions:
			return self.loc_helper.get_text("errors.permissions.none", user_id=user_id, lang_code=lang_code)
		
		# Translate permission names if possible
		translated_perms = []
		for perm in permissions:
			translated = self.loc_helper.get_text(
				f"permissions.{perm.lower()}",
				user_id=user_id,
				lang_code=lang_code
			)
			# If translation not found, use original permission name
			if translated.startswith("Missing translation"):
				translated_perms.append(perm.replace("_", " ").title())
			else:
				translated_perms.append(translated)
		
		return "\n".join(f"• {perm}" for perm in translated_perms)
	
	def _format_duration(self, seconds: float, user_id: Optional[int], lang_code: Optional[str]) -> str:
		"""Format duration for display."""
		if seconds < 60:
			return self.loc_helper.get_text(
				"time.seconds",
				user_id=user_id,
				lang_code=lang_code,
				count=int(seconds)
			)
		elif seconds < 3600:
			minutes = int(seconds // 60)
			return self.loc_helper.get_text(
				"time.minutes",
				user_id=user_id,
				lang_code=lang_code,
				count=minutes
			)
		else:
			hours = int(seconds // 3600)
			return self.loc_helper.get_text(
				"time.hours",
				user_id=user_id,
				lang_code=lang_code,
				count=hours
			)


# Global embed builder instance
embed_builder = ErrorEmbedBuilder()


def setup_embed_builder(bot: discord.Bot) -> ErrorEmbedBuilder:
	"""Initialize the embed builder with bot instance.
	
	Args:
		bot: Discord bot instance
		
	Returns:
		Configured ErrorEmbedBuilder instance
	"""
	global embed_builder
	embed_builder = ErrorEmbedBuilder(bot)
	return embed_builder


def setup_error_embed_builder(bot: discord.Bot) -> ErrorEmbedBuilder:
	"""Initialize the error embed builder with bot instance.
	
	This is an alias for setup_embed_builder for backward compatibility.
	
	Args:
		bot: Discord bot instance
		
	Returns:
		Configured ErrorEmbedBuilder instance
	"""
	return setup_embed_builder(bot)


def get_embed_builder() -> ErrorEmbedBuilder:
	"""Get the global embed builder instance.
	
	Returns:
		Global ErrorEmbedBuilder instance
	"""
	return embed_builder


# Convenience functions for quick embed creation
def create_error_embed(
	error: Exception,
	user_id: Optional[int] = None,
	lang_code: Optional[str] = None,
	error_id: Optional[str] = None
) -> discord.Embed:
	"""Quick function to create an error embed.
	
	Args:
		error: The exception that occurred
		user_id: Discord user ID for localization
		lang_code: Override language code
		error_id: Unique error ID for tracking
		
	Returns:
		Formatted Discord embed
	"""
	return embed_builder.create_error_embed(error, user_id, lang_code, error_id)


def create_permission_error_embed(
	missing_permissions: List[str],
	user_id: Optional[int] = None,
	lang_code: Optional[str] = None,
	is_bot_permission: bool = False
) -> discord.Embed:
	"""Quick function to create a permission error embed.
	
	Args:
		missing_permissions: List of missing permission names
		user_id: Discord user ID for localization
		lang_code: Override language code
		is_bot_permission: Whether it's a bot permission error
		
	Returns:
		Formatted Discord embed
	"""
	return embed_builder.create_permission_error_embed(
		missing_permissions, user_id, lang_code, is_bot_permission
	)


def create_cooldown_error_embed(
	retry_after: float,
	cooldown_type: Optional[str] = None,
	user_id: Optional[int] = None,
	lang_code: Optional[str] = None
) -> discord.Embed:
	"""Quick function to create a cooldown error embed.
	
	Args:
		retry_after: Seconds until cooldown expires
		cooldown_type: Type of cooldown (user, guild, etc.)
		user_id: Discord user ID for localization
		lang_code: Override language code
		
	Returns:
		Formatted Discord embed
	"""
	return embed_builder.create_cooldown_error_embed(
		retry_after, cooldown_type, user_id, lang_code
	)