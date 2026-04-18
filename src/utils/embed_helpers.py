"""
Embed Helper Functions
Provides utilities for creating consistent Discord embeds with BebraLand branding.
"""

import discord
from discord.ext import commands
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

def load_config() -> Dict[str, Any]:
	"""Load configuration from config/config.json"""
	try:
		with open("config/config.json", "r", encoding="utf-8") as f:
			config = json.load(f)
		return config
	except Exception as e:
		logger.error(f"❌ Failed to load config: {e}")
		return {}

def create_embed(
	title: str = None,
	description: str = None,
	color: str = None,
	footer_text: str = None,
	footer_icon: str = None,
	thumbnail: str = None,
	image: str = None,
	author_name: str = None,
	author_icon: str = None,
	timestamp: bool = False
) -> discord.Embed:
	"""Create a standardized embed with BebraLand branding"""
	try:
		# Load config for default values
		config = load_config()
		
		# Set default color from config
		if color is None:
			color = config.get("DISCORD_EMBED_COLOR", "714C35")
		
		# Convert hex color to int
		if isinstance(color, str):
			color = int(color, 16) if not color.startswith("0x") else int(color, 0)
		
		# Create embed
		embed = discord.Embed(color=color)
		
		# Set title and description
		if title:
			embed.title = title
		if description:
			embed.description = description
		
		# Set footer with default branding
		if footer_text is None:
			footer_text = config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮")
		
		embed.set_footer(text=footer_text, icon_url=footer_icon)
		
		# Set optional elements
		if thumbnail:
			embed.set_thumbnail(url=thumbnail)
		if image:
			embed.set_image(url=image)
		if author_name:
			embed.set_author(name=author_name, icon_url=author_icon)
		if timestamp:
			embed.timestamp = datetime.utcnow()
		
		logger.debug(f"📝 Created embed | Title: {title} | Color: {hex(color)}")
		return embed
		
	except Exception as e:
		logger.error(f"❌ Failed to create embed: {e}")
		# Return basic embed as fallback
		return discord.Embed(
			title=title or "Error",
			description=description or "An error occurred",
			color=0x714C35
		)

def create_success_embed(
	title: str,
	description: str = None,
	footer_text: str = None,
	bot_avatar: str = None
) -> discord.Embed:
	"""Create a success embed with green color"""
	return create_embed(
		title=title,
		description=description,
		color=0x00FF00,  # Green
		footer_text=footer_text,
		footer_icon=bot_avatar,
		timestamp=True
	)

def create_error_embed(
	title: str,
	description: str = None,
	footer_text: str = None,
	bot_avatar: str = None
) -> discord.Embed:
	"""Create an error embed with red color"""
	return create_embed(
		title=title,
		description=description,
		color=0xFF0000,  # Red
		footer_text=footer_text,
		footer_icon=bot_avatar,
		timestamp=True
	)

def create_info_embed(
	title: str,
	description: str = None,
	footer_text: str = None,
	bot_avatar: str = None
) -> discord.Embed:
	"""Create an info embed with blue color"""
	return create_embed(
		title=title,
		description=description,
		color=0x0099FF,  # Blue
		footer_text=footer_text,
		footer_icon=bot_avatar,
		timestamp=True
	)

def create_warning_embed(
	title: str,
	description: str = None,
	footer_text: str = None,
	bot_avatar: str = None
) -> discord.Embed:
	"""Create a warning embed with yellow color"""
	return create_embed(
		title=title,
		description=description,
		color=0xFFFF00,  # Yellow
		footer_text=footer_text,
		footer_icon=bot_avatar,
		timestamp=True
	)

def create_ticket_embed(
	title: str,
	description: str = None,
	fields: List[Dict[str, Any]] = None,
	color: str = None,
	footer_text: str = None,
	bot_avatar: str = None
) -> discord.Embed:
	"""Create a ticket-specific embed with proper branding"""
	try:
		# Create base embed
		embed = create_embed(
			title=title,
			description=description,
			color=color,
			footer_text=footer_text,
			footer_icon=bot_avatar,
			timestamp=True
		)
		
		# Add fields if provided
		if fields:
			for field in fields:
				embed.add_field(
					name=field.get("name", ""),
					value=field.get("value", ""),
					inline=field.get("inline", True)
				)
		
		logger.debug(f"🎫 Created ticket embed | Title: {title} | Fields: {len(fields) if fields else 0}")
		return embed
		
	except Exception as e:
		logger.error(f"❌ Failed to create ticket embed: {e}")
		return create_error_embed("Embed Error", "Failed to create ticket embed")

def create_ticket_panel_embed(bot_avatar: str = None) -> discord.Embed:
	"""Create the main ticket panel embed"""
	try:
		config = load_config()
		
		embed = create_embed(
			title="🎫 Create Ticket",
			description="Select a category below to create a ticket:",
			footer_text="Ticketing without clutter",
			footer_icon=bot_avatar
		)
		
		logger.debug("🎫 Created ticket panel embed")
		return embed
		
	except Exception as e:
		logger.error(f"❌ Failed to create ticket panel embed: {e}")
		return create_error_embed("Panel Error", "Failed to create ticket panel")

def create_ticket_welcome_embed(user: discord.Member, ticket_type: str, bot_avatar: str = None) -> discord.Embed:
	"""Create welcome embed for new tickets"""
	try:
		from .ticket_helpers import format_ticket_type_display
		
		embed = create_embed(
			title="🎫 Welcome",
			description="Support will be with you shortly.\nTo close this press the close button",
			footer_text="Ticketing without clutter",
			footer_icon=bot_avatar
		)
		
		# Add ticket info field
		embed.add_field(
			name="📋 Ticket Information",
			value=f"**Type:** {format_ticket_type_display(ticket_type)}\n**Created by:** {user.mention}",
			inline=False
		)
		
		logger.debug(f"🎫 Created ticket welcome embed | User: {user.name} | Type: {ticket_type}")
		return embed
		
	except Exception as e:
		logger.error(f"❌ Failed to create ticket welcome embed: {e}")
		return create_error_embed("Welcome Error", "Failed to create welcome message")

def create_ticket_closed_embed(user: discord.Member, ticket_type: str, channel_name: str, closed_by: discord.Member, bot_avatar: str = None) -> discord.Embed:
	"""Create embed for closed tickets"""
	try:
		from .ticket_helpers import format_ticket_type_display
		
		embed = create_embed(
			title="🔒 Ticket Closed",
			description="This ticket has been closed.",
			color=0xFF6B6B,  # Light red
			footer_text="Ticketing without clutter",
			footer_icon=bot_avatar,
			timestamp=True
		)
		
		# Add ticket details
		embed.add_field(name="📋 Closed by", value=closed_by.mention, inline=True)
		embed.add_field(name="🏷️ Channel", value=channel_name, inline=True)
		embed.add_field(name="📝 Type", value=format_ticket_type_display(ticket_type), inline=True)
		
		logger.debug(f"🔒 Created ticket closed embed | User: {user.name} | Closed by: {closed_by.name}")
		return embed
		
	except Exception as e:
		logger.error(f"❌ Failed to create ticket closed embed: {e}")
		return create_error_embed("Close Error", "Failed to create close message")

def create_ticket_log_embed(
	event_type: str,
	user: discord.Member,
	ticket_type: str,
	channel_mention: str,
	additional_info: Dict[str, Any] = None,
	bot_avatar: str = None
) -> discord.Embed:
	"""Create embed for ticket logging"""
	try:
		from .ticket_helpers import format_ticket_type_display
		
		# Set title and color based on event type
		event_config = {
			"created": {"title": "🎫 New Ticket Created", "color": 0x00FF00},
			"closed": {"title": "🔒 Ticket Closed", "color": 0xFF6B6B},
			"deleted": {"title": "🗑️ Ticket Deleted", "color": 0xFF0000},
			"reopened": {"title": "🔓 Ticket Reopened", "color": 0x00FF00}
		}
		
		config = event_config.get(event_type, {"title": "🎫 Ticket Event", "color": 0x714C35})
		
		embed = create_embed(
			title=config["title"],
			description=f"A ticket has been {event_type}!",
			color=config["color"],
			footer_icon=bot_avatar,
			timestamp=True
		)
		
		# Add standard fields
		embed.add_field(name="👤 User", value=user.mention, inline=True)
		embed.add_field(name="🏷️ Channel", value=channel_mention, inline=True)
		embed.add_field(name="📝 Type", value=format_ticket_type_display(ticket_type), inline=True)
		
		# Add additional info if provided
		if additional_info:
			for key, value in additional_info.items():
				embed.add_field(name=key, value=value, inline=True)
		
		logger.debug(f"📝 Created ticket log embed | Event: {event_type} | User: {user.name}")
		return embed
		
	except Exception as e:
		logger.error(f"❌ Failed to create ticket log embed: {e}")
		return create_error_embed("Log Error", "Failed to create log message")

def create_dm_notification_embed(
	event_type: str,
	guild_name: str,
	ticket_type: str,
	channel_mention: str = None,
	staff_name: str = None,
	bot_avatar: str = None
) -> discord.Embed:
	"""Create embed for DM notifications"""
	try:
		from .ticket_helpers import format_ticket_type_display
		
		if event_type == "created":
			embed = create_embed(
				title="🎫 Ticket Created",
				description=f"Your ticket has been created in {guild_name}!",
				color=0x00FF00,
				footer_icon=bot_avatar,
				timestamp=True
			)
			
			if channel_mention:
				embed.add_field(name="🏷️ Channel", value=channel_mention, inline=False)
			embed.add_field(name="📝 Type", value=format_ticket_type_display(ticket_type), inline=False)
			
		elif event_type == "closed":
			embed = create_embed(
				title="🔒 Ticket Closed",
				description=f"Your ticket has been closed in {guild_name}.",
				color=0xFF6B6B,
				footer_icon=bot_avatar,
				timestamp=True
			)
			
			if staff_name:
				embed.add_field(name="👤 Closed by", value=staff_name, inline=False)
			embed.add_field(name="📝 Type", value=format_ticket_type_display(ticket_type), inline=False)
		
		logger.debug(f"📨 Created DM notification embed | Event: {event_type} | Guild: {guild_name}")
		return embed
		
	except Exception as e:
		logger.error(f"❌ Failed to create DM notification embed: {e}")
		return create_error_embed("DM Error", "Failed to create notification")

def setup_error_embed_builder(bot: commands.Bot) -> None:
	"""Setup error embed builder for the bot (compatibility function)"""
	try:
		# Attach embed helper functions to bot for global access
		bot.create_embed = create_embed
		bot.create_error_embed = create_error_embed
		bot.create_success_embed = create_success_embed
		bot.create_info_embed = create_info_embed
		bot.create_warning_embed = create_warning_embed
		
		logger.info("✅ Error embed builder setup completed")
		
	except Exception as e:
		logger.error(f"❌ Failed to setup error embed builder: {e}")