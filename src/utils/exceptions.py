"""Custom exception classes for the Discord bot.

This module defines custom exceptions that extend Discord.py's built-in exceptions
to provide more specific error handling and better user experience.
"""

import discord
from discord.ext import commands
import logging
from typing import Optional, Any, Dict, List, Union
from datetime import datetime


class BotError(Exception):
	"""Base exception class for all bot-related errors.
	
	Attributes:
		user_message: User-friendly error message
		log_message: Detailed message for logging
		error_code: Unique error code for tracking
		user_id: ID of the user who triggered the error
		guild_id: ID of the guild where error occurred
	"""
	
	def __init__(
		self,
		message: str,
		user_message: Optional[str] = None,
		log_message: Optional[str] = None,
		error_code: Optional[str] = None,
		user_id: Optional[int] = None,
		guild_id: Optional[int] = None
	):
		super().__init__(message)
		self.user_message = user_message or message
		self.log_message = log_message or message
		self.error_code = error_code
		self.user_id = user_id
		self.guild_id = guild_id


class ValidationError(BotError):
	"""Raised when user input validation fails.
	
	Used for invalid parameters, malformed data, or constraint violations.
	"""
	pass


class PermissionError(BotError):
	"""Raised when user lacks required permissions.
	
	Extends Discord.py's MissingPermissions with additional context.
	"""
	
	def __init__(
		self,
		message: str,
		missing_permissions: Optional[list] = None,
		**kwargs
	):
		super().__init__(message, **kwargs)
		self.missing_permissions = missing_permissions or []


class BotPermissionError(BotError):
	"""Raised when bot lacks required permissions.
	
	Used when the bot cannot perform an action due to missing permissions.
	"""
	
	def __init__(
		self,
		message: str,
		missing_permissions: Optional[list] = None,
		**kwargs
	):
		super().__init__(message, **kwargs)
		self.missing_permissions = missing_permissions or []


class ConfigurationError(BotError):
	"""Raised when there's an issue with bot configuration.
	
	Used for missing config values, invalid settings, or setup issues.
	"""
	pass


class DatabaseError(BotError):
	"""Raised when database operations fail.
	
	Used for connection issues, query failures, or data integrity problems.
	"""
	
	def __init__(
		self,
		message: str,
		operation: Optional[str] = None,
		table: Optional[str] = None,
		**kwargs
	):
		super().__init__(message, **kwargs)
		self.operation = operation
		self.table = table


class APIError(BotError):
	"""Raised when external API calls fail.
	
	Used for third-party service failures, rate limits, or network issues.
	"""
	
	def __init__(
		self,
		message: str,
		api_name: Optional[str] = None,
		status_code: Optional[int] = None,
		response_data: Optional[Any] = None,
		**kwargs
	):
		super().__init__(message, **kwargs)
		self.api_name = api_name
		self.status_code = status_code
		self.response_data = response_data


class RateLimitError(BotError):
	"""Raised when rate limits are exceeded.
	
	Used for both Discord API rate limits and custom bot rate limits.
	"""
	
	def __init__(
		self,
		message: str,
		retry_after: Optional[float] = None,
		limit_type: Optional[str] = None,
		**kwargs
	):
		super().__init__(message, **kwargs)
		self.retry_after = retry_after
		self.limit_type = limit_type


class CooldownError(BotError):
	"""Raised when command is on cooldown.
	
	Extends Discord.py's CommandOnCooldown with additional context.
	"""
	
	def __init__(
		self,
		message: str,
		retry_after: Optional[float] = None,
		cooldown_type: Optional[str] = None,
		**kwargs
	):
		super().__init__(message, **kwargs)
		self.retry_after = retry_after
		self.cooldown_type = cooldown_type


class LocalizationError(BotError):
	"""Raised when localization operations fail.
	
	Used for missing translation keys or language loading issues.
	"""
	
	def __init__(
		self,
		message: str,
		lang_code: Optional[str] = None,
		missing_key: Optional[str] = None,
		**kwargs
	):
		super().__init__(message, **kwargs)
		self.lang_code = lang_code
		self.missing_key = missing_key


class UserNotFoundError(BotError):
	"""Raised when a user cannot be found.
	
	Used when user lookup operations fail.
	"""
	
	def __init__(
		self,
		message: str,
		search_term: Optional[Union[str, int]] = None,
		**kwargs
	):
		super().__init__(message, **kwargs)
		self.search_term = search_term


class ChannelNotFoundError(BotError):
	"""Raised when a channel cannot be found.
	
	Used when channel lookup operations fail.
	"""
	
	def __init__(
		self,
		message: str,
		search_term: Optional[Union[str, int]] = None,
		**kwargs
	):
		super().__init__(message, **kwargs)
		self.search_term = search_term


class GuildNotFoundError(BotError):
	"""Raised when a guild cannot be found.
	
	Used when guild lookup operations fail.
	"""
	
	def __init__(
		self,
		message: str,
		search_term: Optional[Union[str, int]] = None,
		**kwargs
	):
		super().__init__(message, **kwargs)
		self.search_term = search_term


class FileOperationError(BotError):
	"""Raised when file operations fail.
	
	Used for file reading, writing, or processing errors.
	"""
	
	def __init__(
		self,
		message: str,
		file_path: Optional[str] = None,
		operation: Optional[str] = None,
		**kwargs
	):
		super().__init__(message, **kwargs)
		self.file_path = file_path
		self.operation = operation


class CommandExecutionError(BotError):
	"""Raised when command execution fails unexpectedly.
	
	Used as a wrapper for unexpected errors during command processing.
	"""
	
	def __init__(
		self,
		message: str,
		command_name: Optional[str] = None,
		original_error: Optional[Exception] = None,
		**kwargs
	):
		super().__init__(message, **kwargs)
		self.command_name = command_name
		self.original_error = original_error


class MaintenanceError(BotError):
	"""Raised when bot is in maintenance mode.
	
	Used to prevent command execution during maintenance.
	"""
	pass


# Exception mapping dictionary for automatic conversion
EXCEPTION_MAPPING = {
	# Permission-related errors
	commands.MissingPermissions: PermissionError,
	commands.BotMissingPermissions: PermissionError,
	commands.MissingRole: PermissionError,
	commands.MissingAnyRole: PermissionError,
	
	# Command-related errors
	commands.CommandNotFound: ValidationError,
	commands.MissingRequiredArgument: ValidationError,
	commands.BadArgument: ValidationError,
	commands.ArgumentParsingError: ValidationError,
	commands.TooManyArguments: ValidationError,
	
	# Cooldown and rate limiting
	commands.CommandOnCooldown: CooldownError,
	commands.MaxConcurrencyReached: RateLimitError,
	
	# API and network errors
	discord.HTTPException: APIError,
	discord.Forbidden: PermissionError,
	discord.NotFound: ValidationError,
	discord.DiscordServerError: APIError,
	
	# General errors
	commands.CommandError: BotError,
}


def map_discord_exception(discord_error: Exception) -> BotError:
	"""
	Map Discord.py exceptions to custom bot exceptions.
	
	Args:
		discord_error: The original Discord.py exception
		
	Returns:
		BotError: Mapped custom exception
	"""
	exception_type = type(discord_error)
	
	# Check if we have a direct mapping
	if exception_type in EXCEPTION_MAPPING:
		custom_exception_class = EXCEPTION_MAPPING[exception_type]
		
		# Create the custom exception with original error details
		if hasattr(discord_error, 'args') and discord_error.args:
			message = str(discord_error.args[0])
		else:
			message = str(discord_error)
		
		return custom_exception_class(
			message,
			user_message=message,
			error_code=f"DISCORD_{exception_type.__name__.upper()}",
			log_message=f"Discord.py error: {message}"
		)
	
	# Default to generic BotError for unmapped exceptions
	return BotError(
		"An unexpected error occurred. Please try again.",
		user_message="An unexpected error occurred. Please try again.",
		error_code=f"UNMAPPED_{exception_type.__name__.upper()}",
		log_message=f"Unmapped Discord.py exception: {discord_error}"
	)