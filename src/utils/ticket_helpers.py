"""
Ticket System Helper Functions
Provides utilities for ticket channel management, permissions, and data handling.
"""

import discord
import json
import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

class TicketData:
	"""Class to handle ticket data storage and retrieval"""
	
	def __init__(self, data_file: str = "data/tickets.json"):
		self.data_file = data_file
		self._ensure_data_file()
	
	def _ensure_data_file(self) -> None:
		"""Ensure the data file exists with proper structure"""
		try:
			# Create data directory if it doesn't exist
			os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
			
			# Create file if it doesn't exist
			if not os.path.exists(self.data_file):
				initial_data = {
					"tickets": {},
					"user_tickets": {},
					"closed_tickets": {}
				}
				with open(self.data_file, "w", encoding="utf-8") as f:
					json.dump(initial_data, f, ensure_ascii=False, indent=4)
				logger.info(f"📄 Created new ticket data file: {self.data_file}")
		except Exception as e:
			logger.error(f"❌ Failed to ensure ticket data file: {e}")
	
	def load_data(self) -> Dict[str, Any]:
		"""Load ticket data from file"""
		try:
			with open(self.data_file, "r", encoding="utf-8") as f:
				data = json.load(f)
			
			# Ensure all required keys exist
			if "tickets" not in data:
				data["tickets"] = {}
			if "user_tickets" not in data:
				data["user_tickets"] = {}
			if "closed_tickets" not in data:
				data["closed_tickets"] = {}
			
			logger.debug(f"📖 Loaded ticket data from {self.data_file}")
			return data
		except Exception as e:
			logger.error(f"❌ Failed to load ticket data: {e}")
			return {"tickets": {}, "user_tickets": {}, "closed_tickets": {}}
	
	def save_data(self, data: Dict[str, Any]) -> bool:
		"""Save ticket data to file"""
		try:
			with open(self.data_file, "w", encoding="utf-8") as f:
				json.dump(data, f, ensure_ascii=False, indent=4)
			logger.debug(f"💾 Saved ticket data to {self.data_file}")
			return True
		except Exception as e:
			logger.error(f"❌ Failed to save ticket data: {e}")
			return False
	
	def create_ticket(self, channel_id: int, user_id: int, ticket_type: str, guild_id: int) -> bool:
		"""Create a new ticket record"""
		try:
			data = self.load_data()
			
			# Create ticket record
			ticket_info = {
				"user_id": user_id,
				"ticket_type": ticket_type,
				"guild_id": guild_id,
				"created_at": datetime.now().isoformat(),
				"status": "open",
				"channel_id": channel_id
			}
			
			# Store ticket data
			data["tickets"][str(channel_id)] = ticket_info
			
			# Track user tickets
			user_key = f"{guild_id}_{user_id}"
			if user_key not in data["user_tickets"]:
				data["user_tickets"][user_key] = []
			data["user_tickets"][user_key].append({
				"channel_id": channel_id,
				"ticket_type": ticket_type,
				"status": "open"
			})
			
			success = self.save_data(data)
			if success:
				logger.info(f"🎫 Created ticket record | Channel: {channel_id} | User: {user_id} | Type: {ticket_type}")
			return success
		except Exception as e:
			logger.error(f"❌ Failed to create ticket record: {e}")
			return False
	
	def get_ticket(self, channel_id: int) -> Optional[Dict[str, Any]]:
		"""Get ticket information by channel ID"""
		try:
			data = self.load_data()
			return data["tickets"].get(str(channel_id))
		except Exception as e:
			logger.error(f"❌ Failed to get ticket data: {e}")
			return None
	
	def close_ticket(self, channel_id: int, closed_by: int) -> bool:
		"""Mark a ticket as closed"""
		try:
			data = self.load_data()
			ticket_key = str(channel_id)
			
			if ticket_key in data["tickets"]:
				ticket = data["tickets"][ticket_key]
				ticket["status"] = "closed"
				ticket["closed_at"] = datetime.now().isoformat()
				ticket["closed_by"] = closed_by
				
				# Move to closed tickets
				data["closed_tickets"][ticket_key] = ticket.copy()
				
				# Update user tickets
				user_key = f"{ticket['guild_id']}_{ticket['user_id']}"
				if user_key in data["user_tickets"]:
					for user_ticket in data["user_tickets"][user_key]:
						if user_ticket["channel_id"] == channel_id:
							user_ticket["status"] = "closed"
							break
				
				success = self.save_data(data)
				if success:
					logger.info(f"🔒 Closed ticket | Channel: {channel_id} | Closed by: {closed_by}")
				return success
			return False
		except Exception as e:
			logger.error(f"❌ Failed to close ticket: {e}")
			return False
	
	def delete_ticket(self, channel_id: int) -> bool:
		"""Delete a ticket record completely"""
		try:
			data = self.load_data()
			ticket_key = str(channel_id)
			
			if ticket_key in data["tickets"]:
				ticket = data["tickets"][ticket_key]
				
				# Remove from tickets
				del data["tickets"][ticket_key]
				
				# Remove from closed tickets if exists
				if ticket_key in data["closed_tickets"]:
					del data["closed_tickets"][ticket_key]
				
				# Remove from user tickets
				user_key = f"{ticket['guild_id']}_{ticket['user_id']}"
				if user_key in data["user_tickets"]:
					data["user_tickets"][user_key] = [
						t for t in data["user_tickets"][user_key] 
						if t["channel_id"] != channel_id
					]
					# Clean up empty user entries
					if not data["user_tickets"][user_key]:
						del data["user_tickets"][user_key]
				
				success = self.save_data(data)
				if success:
					logger.info(f"🗑️ Deleted ticket record | Channel: {channel_id}")
				return success
			return False
		except Exception as e:
			logger.error(f"❌ Failed to delete ticket: {e}")
			return False
	
	def has_open_ticket(self, user_id: int, guild_id: int, ticket_type: str = None) -> bool:
		"""Check if user has an open ticket of specified type"""
		try:
			data = self.load_data()
			user_key = f"{guild_id}_{user_id}"
			
			if user_key in data["user_tickets"]:
				for ticket in data["user_tickets"][user_key]:
					if ticket["status"] == "open":
						if ticket_type is None or ticket["ticket_type"] == ticket_type:
							return True
			return False
		except Exception as e:
			logger.error(f"❌ Failed to check user tickets: {e}")
			return False

async def create_ticket_channel(guild: discord.Guild, user: discord.Member, ticket_type: str, category_id: int, config: Dict[str, Any]) -> Optional[discord.TextChannel]:
	"""Create a new ticket channel with proper permissions"""
	try:
		# Log channel creation start
		logger.info(f"🔵 TICKET CHANNEL CREATE START | User: {user.name} ({user.id}) | Guild: {guild.name} ({guild.id}) | Type: {ticket_type}")
		
		# Get category
		category = guild.get_channel(category_id)
		if not category or not isinstance(category, discord.CategoryChannel):
			logger.error(f"❌ TICKET CHANNEL CREATE FAILED | Category not found: {category_id}")
			return None
		
		# Generate channel name
		channel_name = f"ticket-{user.name.lower()}-{ticket_type.lower().replace(' ', '-')}"
		# Ensure channel name is valid (Discord limits)
		channel_name = channel_name[:100]  # Discord channel name limit
		
		# Set up permissions
		overwrites = {
			guild.default_role: discord.PermissionOverwrite(read_messages=False),
			user: discord.PermissionOverwrite(
				read_messages=True,
				send_messages=True,
				read_message_history=True,
				attach_files=True,
				embed_links=True
			),
			guild.me: discord.PermissionOverwrite(
				read_messages=True,
				send_messages=True,
				manage_messages=True,
				read_message_history=True,
				attach_files=True,
				embed_links=True
			)
		}
		
		# Add staff roles permissions
		staff_roles = config.get("TICKET_STAFF_ROLES", [])
		for role_id in staff_roles:
			role = guild.get_role(role_id)
			if role:
				overwrites[role] = discord.PermissionOverwrite(
					read_messages=True,
					send_messages=True,
					manage_messages=True,
					read_message_history=True,
					attach_files=True,
					embed_links=True
				)
		
		# Create the channel
		channel = await guild.create_text_channel(
			name=channel_name,
			category=category,
			overwrites=overwrites,
			reason=f"Ticket created by {user.name} ({user.id})"
		)
		
		logger.info(f"✅ TICKET CHANNEL CREATE SUCCESS | Channel: {channel.name} ({channel.id}) | User: {user.name} | Type: {ticket_type}")
		return channel
		
	except discord.Forbidden:
		logger.error(f"❌ TICKET CHANNEL CREATE FAILED | Missing permissions | Guild: {guild.name}")
		return None
	except Exception as e:
		logger.error(f"❌ TICKET CHANNEL CREATE FAILED | Error: {str(e)} | User: {user.name} | Type: {ticket_type}")
		return None

async def get_member_safely(guild: discord.Guild, user_id: int) -> Optional[discord.Member]:
	"""Safely fetch a member by ID, returning None if not found"""
	try:
		return await guild.fetch_member(user_id)
	except discord.NotFound:
		logger.warning(f"⚠️ Member {user_id} not found in guild {guild.name}")
		return None
	except discord.HTTPException as e:
		logger.error(f"❌ Failed to fetch member {user_id}: {e}")
		return None

def is_staff_member(member: discord.Member, staff_roles: List[int], staff_users: List[int] = None) -> bool:
	"""Check if a member has any of the staff roles or is in the staff users list"""
	try:
		# Check if user is in staff users list
		if staff_users and member.id in staff_users:
			logger.info(f"✅ Staff check: {member.name} ({member.id}) is in TICKET_STAFF_USERS")
			return True
		
		# Check if user has any staff roles
		member_role_ids = [role.id for role in member.roles]
		has_staff_role = any(role_id in member_role_ids for role_id in staff_roles)
		
		if has_staff_role:
			logger.info(f"✅ Staff check: {member.name} ({member.id}) has staff role")
		else:
			logger.info(f"❌ Staff check: {member.name} ({member.id}) - no staff role or user permission")
		
		return has_staff_role
	except Exception as e:
		logger.error(f"❌ Failed to check staff permissions: {e}")
		return False

def is_ticket_channel(channel_id: int, ticket_data: TicketData) -> bool:
	"""Check if a channel is a ticket channel"""
	try:
		ticket = ticket_data.get_ticket(channel_id)
		return ticket is not None
	except Exception as e:
		logger.error(f"❌ Failed to check if channel is ticket: {e}")
		return False

async def send_dm_safely(user: discord.User, embed: discord.Embed) -> bool:
	"""Safely send a DM to a user, handling errors gracefully"""
	try:
		await user.send(embed=embed)
		logger.info(f"📨 DM sent successfully to {user.name} ({user.id})")
		return True
	except discord.Forbidden:
		logger.warning(f"⚠️ Cannot send DM to {user.name} ({user.id}) - DMs disabled")
		return False
	except discord.HTTPException as e:
		logger.error(f"❌ Failed to send DM to {user.name} ({user.id}): {e}")
		return False
	except Exception as e:
		logger.error(f"❌ Unexpected error sending DM to {user.name} ({user.id}): {e}")
		return False

def format_ticket_type_display(ticket_type: str) -> str:
	"""Format ticket type for display with emoji"""
	type_emojis = {
		"bug_report": "🐛 Bug Report",
		"player_report": "⚔️ Player Report", 
		"feature_request": "💡 Feature Request",
		"general_ticket": "📧 General Ticket"
	}
	return type_emojis.get(ticket_type, f"🎫 {ticket_type.replace('_', ' ').title()}")

async def log_ticket_event(guild: discord.Guild, log_channel_id: int, embed: discord.Embed) -> bool:
	"""Log ticket events to the configured log channel"""
	try:
		log_channel = guild.get_channel(log_channel_id)
		if not log_channel or not isinstance(log_channel, discord.TextChannel):
			logger.warning(f"⚠️ Log channel {log_channel_id} not found or not a text channel")
			return False
		
		await log_channel.send(embed=embed)
		logger.info(f"📝 Ticket event logged to {log_channel.name} ({log_channel.id})")
		return True
	except discord.Forbidden:
		logger.error(f"❌ No permission to send to log channel {log_channel_id}")
		return False
	except Exception as e:
		logger.error(f"❌ Failed to log ticket event: {e}")
		return False

def validate_ticket_config(config: Dict[str, Any]) -> Dict[str, Any]:
	"""Validate ticket system configuration and return validation result"""
	issues = []
	
	try:
		# Check if ticket system is enabled
		if not config.get("TICKET_SYSTEM_ENABLED", False):
			issues.append("Ticket system is not enabled in config")
		
		# Check required fields
		required_fields = ["TICKET_LOG_CHANNEL", "TICKET_CATEGORY", "TICKET_STAFF_ROLES", "TICKET_CATEGORIES"]
		for field in required_fields:
			if field not in config:
				issues.append(f"Missing required config field: {field}")
		
		# Validate ticket categories
		categories = config.get("TICKET_CATEGORIES", {})
		if not isinstance(categories, dict) or not categories:
			issues.append("TICKET_CATEGORIES must be a non-empty dictionary")
		else:
			for cat_key, cat_data in categories.items():
				if not isinstance(cat_data, dict):
					issues.append(f"Ticket category '{cat_key}' must be a dictionary")
					continue
				
				required_cat_fields = ["name", "emoji", "description"]
				for field in required_cat_fields:
					if field not in cat_data:
						issues.append(f"Ticket category '{cat_key}' missing field: {field}")
		
		# Validate staff roles
		staff_roles = config.get("TICKET_STAFF_ROLES", [])
		if not isinstance(staff_roles, list):
			issues.append("TICKET_STAFF_ROLES must be a list")
		
		logger.info(f"🔍 Ticket config validation completed | Issues found: {len(issues)}")
		
		# Return validation result in expected format
		if issues:
			return {
				"valid": False,
				"error": "; ".join(issues),
				"issues": issues
			}
		else:
			return {
				"valid": True,
				"error": None,
				"issues": []
			}
		
	except Exception as e:
		logger.error(f"❌ Error validating ticket config: {e}")
		return {
			"valid": False,
			"error": f"Error during validation: {str(e)}",
			"issues": [f"Error during validation: {str(e)}"]
		}