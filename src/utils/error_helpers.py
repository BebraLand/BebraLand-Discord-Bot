"""Error logging utilities for the Discord bot.

This module provides comprehensive error logging functionality with context-rich
logging, structured error reporting, and integration with the bot's localization system.
"""

import logging
import traceback
import time
import sys
from typing import Optional, Dict, Any, Union, List
from datetime import datetime
import discord
from discord.ext import commands

from .exceptions import BotError, map_discord_exception
from .config_manager import load_config

# Set up logger
logger = logging.getLogger(__name__)
config = load_config()


class ErrorLogger:
	"""Centralized error logging utility with rich context and formatting."""
	
	def __init__(self, bot: Optional[discord.Bot] = None):
		self.bot = bot
		self.config = config
		self.error_counts = {}  # Track error frequency
		self.last_errors = {}   # Track recent errors to prevent spam
	
	def log_command_start(
		self,
		ctx: Union[discord.ApplicationContext, commands.Context],
		command_name: str,
		params: Optional[Dict[str, Any]] = None
	) -> float:
		"""Log command execution start with full context.
		
		Args:
			ctx: Discord context object
			command_name: Name of the command being executed
			params: Command parameters/options
			
		Returns:
			Timestamp for duration calculation
		"""
		start_time = time.time()
		
		# Extract user and guild information
		user_info = self._get_user_info(ctx)
		guild_info = self._get_guild_info(ctx)
		
		logger.info(
			f"🔵 COMMAND START | User: {user_info['name']} ({user_info['id']}) | "
			f"Guild: {guild_info['name']} ({guild_info['id']}) | Command: /{command_name}"
		)
		
		# Log parameters if provided
		if params:
			logger.info(f"📝 COMMAND PARAMS | {params}")
		
		return start_time
	
	def log_command_success(
		self,
		ctx: Union[discord.ApplicationContext, commands.Context],
		command_name: str,
		start_time: float,
		additional_info: Optional[str] = None
	):
		"""Log successful command execution.
		
		Args:
			ctx: Discord context object
			command_name: Name of the executed command
			start_time: Start timestamp from log_command_start
			additional_info: Optional additional information to log
		"""
		duration = round((time.time() - start_time) * 1000, 2)
		user_info = self._get_user_info(ctx)
		
		success_msg = (
			f"✅ COMMAND SUCCESS | User: {user_info['name']} | "
			f"Command: /{command_name} | Duration: {duration}ms"
		)
		
		if additional_info:
			success_msg += f" | {additional_info}"
		
		logger.info(success_msg)
	
	def log_command_error(
		self,
		ctx: Union[discord.ApplicationContext, commands.Context],
		command_name: str,
		error: Exception,
		start_time: Optional[float] = None,
		include_traceback: bool = True
	) -> str:
		"""Log command execution error with full context.
		
		Args:
			ctx: Discord context object
			command_name: Name of the failed command
			error: The exception that occurred
			start_time: Start timestamp for duration calculation
			include_traceback: Whether to include full traceback
			
		Returns:
			Error ID for tracking
		"""
		error_id = self._generate_error_id()
		duration_info = ""
		
		if start_time:
			duration = round((time.time() - start_time) * 1000, 2)
			duration_info = f" | Duration: {duration}ms"
		
		user_info = self._get_user_info(ctx)
		guild_info = self._get_guild_info(ctx)
		
		# Log basic error information
		logger.error(
			f"❌ COMMAND FAILED | User: {user_info['name']} ({user_info['id']}) | "
			f"Guild: {guild_info['name']} ({guild_info['id']}) | "
			f"Command: /{command_name}{duration_info} | "
			f"Error: {str(error)} | Error ID: {error_id}"
		)
		
		# Log detailed error context
		self._log_error_context(ctx, error, error_id)
		
		# Log traceback if requested
		if include_traceback:
			logger.error(f"🔍 ERROR TRACEBACK [{error_id}]:", exc_info=True)
		
		# Update error tracking
		self._update_error_tracking(error, error_id)
		
		return error_id
	
	def log_event_error(
		self,
		event_name: str,
		error: Exception,
		context: Optional[Dict[str, Any]] = None,
		include_traceback: bool = True
	) -> str:
		"""Log errors that occur in event handlers.
		
		Args:
			event_name: Name of the event where error occurred
			error: The exception that occurred
			context: Additional context information
			include_traceback: Whether to include full traceback
			
		Returns:
			Error ID for tracking
		"""
		error_id = self._generate_error_id()
		
		context_str = ""
		if context:
			context_str = f" | Context: {context}"
		
		logger.error(
			f"❌ EVENT ERROR | Event: {event_name} | "
			f"Error: {str(error)} | Error ID: {error_id}{context_str}"
		)
		
		if include_traceback:
			logger.error(f"🔍 ERROR TRACEBACK [{error_id}]:", exc_info=True)
		
		self._update_error_tracking(error, error_id)
		return error_id
	
	def log_api_error(
		self,
		api_name: str,
		endpoint: str,
		error: Exception,
		status_code: Optional[int] = None,
		response_data: Optional[Any] = None,
		user_id: Optional[int] = None
	) -> str:
		"""Log external API errors.
		
		Args:
			api_name: Name of the API service
			endpoint: API endpoint that failed
			error: The exception that occurred
			status_code: HTTP status code if available
			response_data: Response data if available
			user_id: User who triggered the API call
			
		Returns:
			Error ID for tracking
		"""
		error_id = self._generate_error_id()
		
		user_info = f" | User: {user_id}" if user_id else ""
		status_info = f" | Status: {status_code}" if status_code else ""
		
		logger.error(
			f"🌐 API ERROR | Service: {api_name} | Endpoint: {endpoint} | "
			f"Error: {str(error)} | Error ID: {error_id}{status_info}{user_info}"
		)
		
		if response_data:
			logger.error(f"📄 API RESPONSE [{error_id}]: {response_data}")
		
		self._update_error_tracking(error, error_id)
		return error_id
	
	def log_database_error(
		self,
		operation: str,
		table: str,
		error: Exception,
		user_id: Optional[int] = None,
		query: Optional[str] = None
	) -> str:
		"""Log database operation errors.
		
		Args:
			operation: Type of database operation (SELECT, INSERT, etc.)
			table: Database table involved
			error: The exception that occurred
			user_id: User who triggered the operation
			query: SQL query if available (sanitized)
			
		Returns:
			Error ID for tracking
		"""
		error_id = self._generate_error_id()
		
		user_info = f" | User: {user_id}" if user_id else ""
		
		logger.error(
			f"🗄️ DB ERROR | Operation: {operation} | Table: {table} | "
			f"Error: {str(error)} | Error ID: {error_id}{user_info}"
		)
		
		if query:
			# Log sanitized query (remove sensitive data)
			sanitized_query = self._sanitize_query(query)
			logger.error(f"📝 DB QUERY [{error_id}]: {sanitized_query}")
		
		self._update_error_tracking(error, error_id)
		return error_id
	
	def log_rate_limit(
		self,
		limit_type: str,
		user_id: Optional[int] = None,
		guild_id: Optional[int] = None,
		retry_after: Optional[float] = None,
		bucket: Optional[str] = None
	):
		"""Log rate limit events.
		
		Args:
			limit_type: Type of rate limit (discord, custom, etc.)
			user_id: User who hit the rate limit
			guild_id: Guild where rate limit occurred
			retry_after: Seconds until rate limit resets
			bucket: Rate limit bucket identifier
		"""
		user_info = f" | User: {user_id}" if user_id else ""
		guild_info = f" | Guild: {guild_id}" if guild_id else ""
		retry_info = f" | Retry After: {retry_after}s" if retry_after else ""
		bucket_info = f" | Bucket: {bucket}" if bucket else ""
		
		logger.warning(
			f"⚠️ RATE LIMIT | Type: {limit_type}{user_info}{guild_info}{retry_info}{bucket_info}"
		)
	
	def get_error_stats(self) -> Dict[str, Any]:
		"""Get error statistics for monitoring.
		
		Returns:
			Dictionary containing error statistics
		"""
		total_errors = sum(self.error_counts.values())
		
		return {
			"total_errors": total_errors,
			"error_types": dict(self.error_counts),
			"most_common_error": max(self.error_counts.items(), key=lambda x: x[1]) if self.error_counts else None,
			"recent_errors": len(self.last_errors),
			"timestamp": datetime.utcnow().isoformat()
		}
	
	def _get_user_info(self, ctx: Union[discord.ApplicationContext, commands.Context]) -> Dict[str, Any]:
		"""Extract user information from context."""
		if hasattr(ctx, 'user') and ctx.user:
			user = ctx.user
		elif hasattr(ctx, 'author') and ctx.author:
			user = ctx.author
		else:
			return {"name": "Unknown", "id": "N/A"}
		
		return {
			"name": user.name,
			"id": user.id,
			"display_name": getattr(user, 'display_name', user.name),
			"bot": getattr(user, 'bot', False)
		}
	
	def _get_guild_info(self, ctx: Union[discord.ApplicationContext, commands.Context]) -> Dict[str, Any]:
		"""Extract guild information from context."""
		if hasattr(ctx, 'guild') and ctx.guild:
			return {
				"name": ctx.guild.name,
				"id": ctx.guild.id,
				"member_count": getattr(ctx.guild, 'member_count', 'Unknown')
			}
		else:
			return {"name": "DM", "id": "N/A"}
	
	def _log_error_context(
		self,
		ctx: Union[discord.ApplicationContext, commands.Context],
		error: Exception,
		error_id: str
	):
		"""Log additional error context information."""
		context_info = {
			"error_type": type(error).__name__,
			"error_module": getattr(error, '__module__', 'unknown'),
			"python_version": sys.version.split()[0],
			"discord_py_version": discord.__version__
		}
		
		# Add bot-specific context
		if self.bot:
			context_info.update({
				"bot_latency": round(self.bot.latency * 1000, 2),
				"guild_count": len(self.bot.guilds),
				"user_count": len(self.bot.users)
			})
		
		# Add channel context if available
		if hasattr(ctx, 'channel') and ctx.channel:
			context_info["channel_type"] = type(ctx.channel).__name__
			context_info["channel_id"] = ctx.channel.id
		
		logger.error(f"🔍 ERROR CONTEXT [{error_id}]: {context_info}")
	
	def _generate_error_id(self) -> str:
		"""Generate unique error ID for tracking."""
		timestamp = int(time.time() * 1000)  # Millisecond precision
		return f"ERR_{timestamp}"
	
	def _update_error_tracking(self, error: Exception, error_id: str):
		"""Update error frequency tracking."""
		error_type = type(error).__name__
		self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
		self.last_errors[error_id] = {
			"type": error_type,
			"message": str(error),
			"timestamp": datetime.utcnow().isoformat()
		}
		
		# Keep only last 100 errors to prevent memory issues
		if len(self.last_errors) > 100:
			oldest_key = min(self.last_errors.keys())
			del self.last_errors[oldest_key]
	
	def _sanitize_query(self, query: str) -> str:
		"""Sanitize SQL query for logging (remove sensitive data)."""
		# Basic sanitization - remove potential sensitive values
		sensitive_patterns = [
			r"'[^']*'",  # String literals
			r'"[^"]*"',  # Double-quoted strings
			r'\b\d{10,}\b',  # Long numbers (potential IDs/tokens)
		]
		
		sanitized = query
		for pattern in sensitive_patterns:
			import re
			sanitized = re.sub(pattern, "'***'", sanitized)
		
		return sanitized[:500]  # Limit length


# Global error logger instance
error_logger = ErrorLogger()


def setup_error_logger(bot: discord.Bot):
	"""Initialize the error logger with bot instance.
	
	Args:
		bot: Discord bot instance
	"""
	global error_logger
	error_logger = ErrorLogger(bot)
	return error_logger


def get_error_logger() -> ErrorLogger:
	"""Get the global error logger instance.
	
	Returns:
		Global ErrorLogger instance
	"""
	return error_logger


def handle_discord_exception(exc: Exception) -> BotError:
	"""Handle and map Discord.py exceptions to custom exceptions.
	
	Args:
		exc: Discord.py exception
		
	Returns:
		Mapped custom exception
	"""
	return map_discord_exception(exc)


def log_performance_warning(operation: str, duration: float, threshold: float = 1000.0):
	"""Log performance warnings for slow operations.
	
	Args:
		operation: Name of the operation
		duration: Duration in milliseconds
		threshold: Warning threshold in milliseconds
	"""
	if duration > threshold:
		logger.warning(
			f"⚠️ PERFORMANCE WARNING | Operation: {operation} | "
			f"Duration: {duration}ms | Threshold: {threshold}ms"
		)


def log_memory_usage():
	"""Log current memory usage for monitoring."""
	try:
		import psutil
		process = psutil.Process()
		memory_info = process.memory_info()
		memory_mb = memory_info.rss / 1024 / 1024
		
		logger.info(f"📊 MEMORY USAGE | RAM: {memory_mb:.1f}MB")
	except ImportError:
		logger.debug("psutil not available for memory monitoring")
	except Exception as e:
		logger.error(f"Failed to get memory usage: {e}")


async def handle_command_error(
	ctx: Union[discord.ApplicationContext, commands.Context],
	error: Exception,
	command_name: Optional[str] = None,
	start_time: Optional[float] = None
) -> Optional[str]:
	"""Handle command errors with logging and user-friendly responses.
	
	This function provides centralized error handling for Discord commands,
	including comprehensive logging and appropriate user responses.
	
	Args:
		ctx: Discord context object
		error: The exception that occurred
		command_name: Name of the command (auto-detected if not provided)
		start_time: Start timestamp for duration calculation
		
	Returns:
		Error ID for tracking, or None if error was handled silently
	"""
	global error_logger
	
	# Auto-detect command name if not provided
	if not command_name:
		if hasattr(ctx, 'command') and ctx.command:
			command_name = ctx.command.name
		elif hasattr(ctx, 'interaction') and ctx.interaction and hasattr(ctx.interaction, 'data'):
			command_name = ctx.interaction.data.get('name', 'unknown')
		else:
			command_name = 'unknown'
	
	# Log the error with full context
	error_id = error_logger.log_command_error(
		ctx=ctx,
		command_name=command_name,
		error=error,
		start_time=start_time,
		include_traceback=True
	)
	
	# Handle different types of errors
	try:
		# Check if it's a Discord.py specific error
		if isinstance(error, discord.errors.NotFound):
			# Resource not found - usually safe to ignore or give generic message
			await _send_error_response(
				ctx,
				"❌ The requested resource could not be found.",
				error_id
			)
			return error_id
		
		elif isinstance(error, discord.errors.Forbidden):
			# Permission denied
			await _send_error_response(
				ctx,
				"❌ I don't have permission to perform this action.",
				error_id
			)
			return error_id
		
		elif isinstance(error, discord.errors.HTTPException):
			# General HTTP error
			await _send_error_response(
				ctx,
				"❌ A Discord API error occurred. Please try again later.",
				error_id
			)
			return error_id
		
		elif isinstance(error, commands.MissingPermissions):
			# User lacks permissions
			await _send_error_response(
				ctx,
				"❌ You don't have permission to use this command.",
				error_id
			)
			return error_id
		
		elif isinstance(error, commands.BotMissingPermissions):
			# Bot lacks permissions
			await _send_error_response(
				ctx,
				"❌ I don't have the required permissions to execute this command.",
				error_id
			)
			return error_id
		
		elif isinstance(error, commands.CommandOnCooldown):
			# Command on cooldown
			retry_after = round(error.retry_after, 1)
			await _send_error_response(
				ctx,
				f"⏰ This command is on cooldown. Try again in {retry_after} seconds.",
				error_id
			)
			return error_id
		
		elif isinstance(error, commands.MissingRequiredArgument):
			# Missing required argument
			await _send_error_response(
				ctx,
				f"❌ Missing required argument: `{error.param.name}`",
				error_id
			)
			return error_id
		
		elif isinstance(error, commands.BadArgument):
			# Invalid argument
			await _send_error_response(
				ctx,
				"❌ Invalid argument provided. Please check your input and try again.",
				error_id
			)
			return error_id
		
		elif isinstance(error, commands.CommandNotFound):
			# Command not found - usually ignore silently
			return None
		
		else:
			# Generic/unexpected error
			await _send_error_response(
				ctx,
				f"❌ An unexpected error occurred. Error ID: `{error_id}`",
				error_id
			)
			return error_id
		
	except Exception as response_error:
		# Error occurred while trying to send error response
		logger.error(
			f"Failed to send error response for {error_id}: {response_error}",
			exc_info=True
		)
		return error_id


async def _send_error_response(
	ctx: Union[discord.ApplicationContext, commands.Context],
	message: str,
	error_id: str
):
	"""Send error response to user safely.
	
	Args:
		ctx: Discord context object
		message: Error message to send
		error_id: Error ID for tracking
	"""
	try:
		# Try to respond with an embed if possible
		embed = discord.Embed(
			title="Error",
			description=message,
			color=discord.Color.red()
		)
		
		# Add footer with error ID for support
		embed.set_footer(text=f"Error ID: {error_id}")
		
		# Try to respond or send based on context type
		if hasattr(ctx, 'respond') and not ctx.response.is_done():
			# Application command that hasn't been responded to
			await ctx.respond(embed=embed, ephemeral=True)
		elif hasattr(ctx, 'followup'):
			# Application command that has been responded to
			await ctx.followup.send(embed=embed, ephemeral=True)
		elif hasattr(ctx, 'send'):
			# Regular message context
			await ctx.send(embed=embed)
		else:
			# Fallback - try to send to channel
			if hasattr(ctx, 'channel') and ctx.channel:
				await ctx.channel.send(embed=embed)
		
	except discord.errors.NotFound:
		# Channel/interaction not found - log but don't raise
		logger.warning(f"Could not send error response for {error_id}: Channel/interaction not found")
	except discord.errors.Forbidden:
		# No permission to send - log but don't raise
		logger.warning(f"Could not send error response for {error_id}: Missing permissions")
	except Exception as e:
		# Any other error - log but don't raise to prevent error loops
		logger.error(f"Failed to send error response for {error_id}: {e}", exc_info=True)