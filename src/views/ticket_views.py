"""
Ticket System Views
Contains all Discord UI views for ticket management including creation, closing, and staff controls.
"""

import discord
import json
import logging
import time
import asyncio
from typing import Dict, Any, Optional

# Import helper functions
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ticket_helpers import (
	TicketData, create_ticket_channel, get_member_safely, is_staff_member,
	is_ticket_channel, send_dm_safely, format_ticket_type_display, log_ticket_event
)
from utils.embed_helpers import (
	create_ticket_welcome_embed, create_ticket_closed_embed, create_ticket_log_embed,
	create_dm_notification_embed, create_success_embed, create_error_embed
)

# Set up logging
logger = logging.getLogger(__name__)

def load_config() -> Dict[str, Any]:
	"""Load configuration from config.json"""
	try:
		with open("config.json", "r", encoding="utf-8") as f:
			return json.load(f)
	except Exception as e:
		logger.error(f"❌ Failed to load config: {e}")
		return {}

def load_localization(lang: str = "en") -> Dict[str, str]:
	"""Load localization strings with fallback"""
	try:
		# Try to load requested language
		try:
			with open(f"src/languages/{lang}.json", "r", encoding="utf-8") as f:
				return json.load(f)
		except FileNotFoundError:
			# Fallback to English
			with open("src/languages/en.json", "r", encoding="utf-8") as f:
				return json.load(f)
	except Exception as e:
		logger.error(f"❌ Failed to load localization: {e}")
		return {}

class TicketCreationHandler:
	"""Handles ticket creation logic"""
	
	def __init__(self, config: Dict[str, Any], localization: Dict[str, str]):
		self.config = config
		self.localization = localization
		self.ticket_data = TicketData()
	
	async def create_ticket(self, interaction: discord.Interaction, ticket_type: str):
		"""Create a new ticket channel"""
		try:
			# Defer the response to give us more time
			await interaction.response.defer(ephemeral=True)
			
			# Validate guild context
			if not interaction.guild:
				await interaction.followup.send(
					embed=create_error_embed(
						title=self.localization.get("TICKET_ERROR_NOT_IN_GUILD", "❌ Guild Only"),
						description="This command can only be used in a server.",
						bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
					),
					ephemeral=True
				)
				return
			
			# Check if user already has an open ticket of this type
			if self.ticket_data.has_open_ticket(interaction.user.id, interaction.guild.id, ticket_type):
				await interaction.followup.send(
					embed=create_error_embed(
						title=self.localization.get("TICKET_ERROR_ALREADY_EXISTS", "❌ Ticket Exists"),
						description="You already have an open ticket of this type.",
						bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
					),
					ephemeral=True
				)
				return
			
			# Get ticket category from config
			ticket_categories = self.config.get("TICKET_CATEGORIES", {})
			if ticket_type not in ticket_categories:
				await interaction.followup.send(
					embed=create_error_embed(
						title="❌ Invalid Category",
						description="The selected ticket category is not valid.",
						bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
					),
					ephemeral=True
				)
				return
			
			# Create the ticket channel
			category_id = self.config.get("TICKET_CATEGORY")
			channel = await create_ticket_channel(
				interaction.guild,
				interaction.user,
				ticket_type,
				category_id,
				self.config
			)
			
			if not channel:
				await interaction.followup.send(
					embed=create_error_embed(
						title=self.localization.get("TICKET_ERROR_CHANNEL_CREATE", "❌ Channel Creation Failed"),
						description="Failed to create ticket channel. Please check bot permissions.",
						bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
					),
					ephemeral=True
				)
				return
			
			# Store ticket data
			success = self.ticket_data.create_ticket(
				channel.id,
				interaction.user.id,
				ticket_type,
				interaction.guild.id
			)
			
			if not success:
				logger.warning(f"⚠️ Failed to store ticket data for channel {channel.id}")
			
			# Send welcome message to ticket channel
			welcome_embed = create_ticket_welcome_embed(
				interaction.user,
				ticket_type,
				bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
			)
			
			# Create close button view
			close_view = TicketCloseView(self.config, self.localization)
			
			await channel.send(
				content=f"{interaction.user.mention}",
				embed=welcome_embed,
				view=close_view
			)
			
			# Send success message to user
			await interaction.followup.send(
				embed=create_success_embed(
					title=self.localization.get("TICKET_CREATED_TITLE", "🎫 Ticket Created"),
					description=f"Your ticket has been created: {channel.mention}",
					bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
				),
				ephemeral=True
			)
			
			# Log ticket creation
			log_channel_id = self.config.get("TICKET_LOG_CHANNEL")
			if log_channel_id:
				log_embed = create_ticket_log_embed(
					"created",
					interaction.user,
					ticket_type,
					channel.mention,
					bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
				)
				
				await log_ticket_event(interaction.guild, log_channel_id, log_embed)
			
			# Send DM notification
			dm_embed = create_dm_notification_embed(
				"created",
				interaction.guild.name,
				ticket_type,
				channel.mention,
				bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
			)
			
			await send_dm_safely(interaction.user, dm_embed)
			
			logger.info(f"🎫 Ticket created successfully | Channel: {channel.name} ({channel.id}) | User: {interaction.user.name} | Type: {ticket_type}")
			
		except Exception as e:
			logger.error(f"❌ Failed to create ticket: {e}")
			logger.error(f"🔍 ERROR TRACEBACK:", exc_info=True)
			
			try:
				await interaction.followup.send(
					embed=create_error_embed(
						title=self.localization.get("TICKET_ERROR_CHANNEL_CREATE", "❌ Creation Failed"),
						description=f"An error occurred: {str(e)}",
						bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
					),
					ephemeral=True
				)
			except:
				pass  # Ignore if we can't send error message

class TicketCloseView(discord.ui.View):
	"""View with close button for tickets"""
	
	def __init__(self, config: Dict[str, Any], localization: Dict[str, str]):
		super().__init__(timeout=None)  # Persistent view
		self.config = config
		self.localization = localization
		self.ticket_data = TicketData()
	
	@discord.ui.button(
		label="🔒 Close",
		style=discord.ButtonStyle.danger,
		custom_id="ticket_close_button"
	)
	async def close_ticket_button(self, button: discord.ui.Button, interaction: discord.Interaction):
		"""Handle close ticket button click"""
		start_time = time.time()
		
		# Log button interaction start
		logger.info(f"🔵 TICKET CLOSE BUTTON START | User: {interaction.user.name} ({interaction.user.id}) | Channel: {interaction.channel.name if interaction.channel else 'Unknown'} ({interaction.channel.id if interaction.channel else 'N/A'})")
		
		try:
			# Check if this is a ticket channel
			if not is_ticket_channel(interaction.channel.id, self.ticket_data):
				await interaction.response.send_message(
					embed=create_error_embed(
						title=self.localization.get("TICKET_ERROR_NOT_TICKET_CHANNEL", "❌ Not a Ticket"),
						description="This is not a ticket channel.",
						bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
					),
					ephemeral=True
				)
				return
			
			# Get ticket data
			ticket = self.ticket_data.get_ticket(interaction.channel.id)
			if not ticket:
				await interaction.response.send_message(
					embed=create_error_embed(
						title="❌ Ticket Not Found",
						description="Could not find ticket data.",
						bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
					),
					ephemeral=True
				)
				return
			
			# Check if ticket is already closed
			if ticket.get("status") == "closed":
				await interaction.response.send_message(
					embed=create_error_embed(
						title=self.localization.get("TICKET_ERROR_ALREADY_CLOSED", "❌ Already Closed"),
						description="This ticket is already closed.",
						bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
					),
					ephemeral=True
				)
				return
			
			# Check permissions (ticket creator or staff)
			is_creator = ticket["user_id"] == interaction.user.id
			is_staff = is_staff_member(
				interaction.user, 
				self.config.get("TICKET_STAFF_ROLES", []),
				self.config.get("TICKET_STAFF_USERS", [])
			)
			
			if not (is_creator or is_staff):
				await interaction.response.send_message(
					embed=create_error_embed(
						title=self.localization.get("TICKET_ERROR_STAFF_ONLY", "❌ Staff Only"),
						description="Only the ticket creator or staff can close this ticket.",
						bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
					),
					ephemeral=True
				)
				return
			
			# Show confirmation dialog
			confirmation_view = TicketCloseConfirmationView(
				self.config, self.localization, ticket, interaction.user
			)
			
			await interaction.response.send_message(
				self.localization.get("TICKET_CLOSE_CONFIRMATION", "Are you sure you would like to close this ticket?"),
				view=confirmation_view,
				ephemeral=True
			)
			
			# Log button interaction success
			duration = round((time.time() - start_time) * 1000, 2)
			logger.info(f"✅ TICKET CLOSE BUTTON SUCCESS | User: {interaction.user.name} | Duration: {duration}ms")
			
		except Exception as e:
			# Log error with full details
			duration = round((time.time() - start_time) * 1000, 2)
			logger.error(f"❌ TICKET CLOSE BUTTON FAILED | User: {interaction.user.name} | Duration: {duration}ms | Error: {str(e)}")
			logger.error(f"🔍 ERROR TRACEBACK:", exc_info=True)
			
			try:
				await interaction.response.send_message(
					embed=create_error_embed(
						title="❌ Error",
						description=f"An error occurred: {str(e)}",
						bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
					),
					ephemeral=True
				)
			except:
				pass  # Ignore if we can't send error message

class TicketCloseConfirmationView(discord.ui.View):
	"""Confirmation dialog for closing tickets"""
	
	def __init__(self, config: Dict[str, Any], localization: Dict[str, str], ticket: Dict[str, Any], closer: discord.Member):
		super().__init__(timeout=None)  # Persistent view
		self.config = config
		self.localization = localization
		self.ticket = ticket
		self.closer = closer
		self.ticket_data = TicketData()
	
	@discord.ui.button(
		label="Close",
		style=discord.ButtonStyle.danger,
		custom_id="ticket_close_confirm"
	)
	async def confirm_close(self, button: discord.ui.Button, interaction: discord.Interaction):
		"""Confirm ticket closure"""
		start_time = time.time()
		
		# Log confirmation start
		logger.info(f"🔵 TICKET CLOSE CONFIRM START | User: {interaction.user.name} ({interaction.user.id}) | Channel: {interaction.channel.name if interaction.channel else 'Unknown'}")
		
		try:
			await interaction.response.defer(ephemeral=True)
			
			# Close the ticket in data
			success = self.ticket_data.close_ticket(interaction.channel.id, self.closer.id)
			if not success:
				logger.warning(f"⚠️ Failed to update ticket data for channel {interaction.channel.id}")
			
			# Get ticket creator
			ticket_creator = await get_member_safely(interaction.guild, self.ticket["user_id"])
			
			# Create closed embed
			closed_embed = create_ticket_closed_embed(
				ticket_creator or interaction.user,
				self.ticket["ticket_type"],
				interaction.channel.name,
				self.closer,
				bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
			)
			
			# Create staff controls view
			staff_view = TicketStaffControlsView(self.config, self.localization, self.ticket)
			
			# Send closed message to channel
			await interaction.channel.send(embed=closed_embed, view=staff_view)
			
			# Update channel permissions (make read-only for creator)
			if ticket_creator:
				try:
					await interaction.channel.set_permissions(
						ticket_creator,
						read_messages=True,
						send_messages=False,
						read_message_history=True
					)
				except discord.Forbidden:
					logger.warning(f"⚠️ Could not update permissions for {ticket_creator.name} in {interaction.channel.name}")
			
			# Log ticket closure
			log_channel_id = self.config.get("TICKET_LOG_CHANNEL")
			if log_channel_id:
				log_embed = create_ticket_log_embed(
					"closed",
					ticket_creator or interaction.user,
					self.ticket["ticket_type"],
					interaction.channel.mention,
					additional_info={"👤 Closed by": self.closer.mention},
					bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
				)
				
				await log_ticket_event(interaction.guild, log_channel_id, log_embed)
			
			# Send DM notification to ticket creator
			if ticket_creator:
				dm_embed = create_dm_notification_embed(
					"closed",
					interaction.guild.name,
					self.ticket["ticket_type"],
					staff_name=self.closer.display_name,
					bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
				)
				
				await send_dm_safely(ticket_creator, dm_embed)
			
			# Delete the confirmation message
			try:
				await interaction.delete_original_response()
				logger.info(f"🗑️ CONFIRMATION MESSAGE DELETED | User: {interaction.user.name}")
			except discord.NotFound:
				logger.warning(f"⚠️ Confirmation message already deleted | User: {interaction.user.name}")
			except Exception as delete_error:
				logger.error(f"❌ Failed to delete confirmation message | Error: {str(delete_error)}")
			
			# Send confirmation to closer
			await interaction.followup.send(
				embed=create_success_embed(
					title="✅ Ticket Closed",
					description="The ticket has been successfully closed.",
					bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
				),
				ephemeral=True
			)
			
			# Log successful completion
			duration = round((time.time() - start_time) * 1000, 2)
			logger.info(f"✅ TICKET CLOSE CONFIRM SUCCESS | User: {interaction.user.name} | Duration: {duration}ms")
			
		except Exception as e:
			# Log error with full details
			duration = round((time.time() - start_time) * 1000, 2)
			logger.error(f"❌ TICKET CLOSE CONFIRM FAILED | User: {interaction.user.name} | Duration: {duration}ms | Error: {str(e)}")
			logger.error(f"🔍 ERROR TRACEBACK:", exc_info=True)
			
			try:
				await interaction.followup.send(
					embed=create_error_embed(
						title="❌ Close Failed",
						description=f"Failed to close ticket: {str(e)}",
						bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
					),
					ephemeral=True
				)
			except:
				pass  # Ignore if we can't send error message
	
	@discord.ui.button(
		label="Cancel",
		style=discord.ButtonStyle.secondary,
		custom_id="ticket_close_cancel"
	)
	async def cancel_close(self, button: discord.ui.Button, interaction: discord.Interaction):
		"""Cancel ticket closure"""
		try:
			# Delete the confirmation message
			await interaction.response.defer()
			await interaction.delete_original_response()
			
			logger.info(f"ℹ️ Ticket close cancelled by {interaction.user.name} - confirmation message deleted")
		except Exception as e:
			# If we can't delete the message, just send a cancellation response
			logger.warning(f"⚠️ Could not delete confirmation message: {e}")
			await interaction.response.send_message(
				embed=create_success_embed(
					title="❌ Cancelled",
					description="Ticket closure has been cancelled.",
					bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
				),
				ephemeral=True
			)

class TicketStaffControlsView(discord.ui.View):
	"""Staff controls for closed tickets"""
	
	def __init__(self, config: Dict[str, Any], localization: Dict[str, str], ticket: Dict[str, Any]):
		super().__init__(timeout=None)  # Persistent view
		self.config = config
		self.localization = localization
		self.ticket = ticket
		self.ticket_data = TicketData()
	
	@discord.ui.button(
		label="📄 Transcript",
		style=discord.ButtonStyle.secondary,
		custom_id="ticket_transcript"
	)
	async def create_transcript(self, button: discord.ui.Button, interaction: discord.Interaction):
		"""Create ticket transcript"""
		start_time = time.time()
		
		# Log transcript start
		logger.info(f"🔵 TICKET TRANSCRIPT START | User: {interaction.user.name} ({interaction.user.id}) | Channel: {interaction.channel.name if interaction.channel else 'Unknown'}")
		
		try:
			# Check staff permissions
			if not is_staff_member(
				interaction.user, 
				self.config.get("TICKET_STAFF_ROLES", []),
				self.config.get("TICKET_STAFF_USERS", [])
			):
				await interaction.response.send_message(
					embed=create_error_embed(
						title=self.localization.get("TICKET_ERROR_STAFF_ONLY", "❌ Staff Only"),
						description="Only staff members can create transcripts.",
						bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
					),
					ephemeral=True
				)
				return
			
			await interaction.response.defer(ephemeral=True)
			
			# Create simple transcript (message history)
			messages = []
			async for message in interaction.channel.history(limit=None, oldest_first=True):
				timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
				content = message.content or "[No text content]"
				
				# Handle embeds
				if message.embeds:
					for embed in message.embeds:
						if embed.title:
							content += f"\n[Embed: {embed.title}]"
						if embed.description:
							content += f"\n{embed.description}"
				
				# Handle attachments
				if message.attachments:
					for attachment in message.attachments:
						content += f"\n[Attachment: {attachment.filename}]"
				
				messages.append(f"[{timestamp}] {message.author.display_name}: {content}")
			
			# Create transcript file
			transcript_content = f"Ticket Transcript - {interaction.channel.name}\n"
			transcript_content += f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
			transcript_content += f"Ticket Type: {format_ticket_type_display(self.ticket['ticket_type'])}\n"
			transcript_content += "=" * 50 + "\n\n"
			transcript_content += "\n".join(messages)
			
			# Create file using BytesIO
			import io
			transcript_bytes = io.BytesIO(transcript_content.encode('utf-8'))
			transcript_file = discord.File(
				fp=transcript_bytes,
				filename=f"transcript-{interaction.channel.name}.txt"
			)
			
			await interaction.followup.send(
				embed=create_success_embed(
					title=self.localization.get("TICKET_SUCCESS_TRANSCRIPT", "✅ Transcript Created"),
					description="Ticket transcript has been generated.",
					bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
				),
				file=transcript_file,
				ephemeral=True
			)
			
			# Log successful completion
			duration = round((time.time() - start_time) * 1000, 2)
			logger.info(f"✅ TICKET TRANSCRIPT SUCCESS | User: {interaction.user.name} | Duration: {duration}ms")
			
		except Exception as e:
			# Log error with full details
			duration = round((time.time() - start_time) * 1000, 2)
			logger.error(f"❌ TICKET TRANSCRIPT FAILED | User: {interaction.user.name} | Duration: {duration}ms | Error: {str(e)}")
			logger.error(f"🔍 ERROR TRACEBACK:", exc_info=True)
			
			try:
				await interaction.followup.send(
					embed=create_error_embed(
						title=self.localization.get("TICKET_ERROR_TRANSCRIPT_FAILED", "❌ Transcript Failed"),
						description=f"Failed to create transcript: {str(e)}",
						bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
					),
					ephemeral=True
				)
			except:
				pass  # Ignore if we can't send error message
	
	@discord.ui.button(
		label="🔓 Open",
		style=discord.ButtonStyle.success,
		custom_id="ticket_reopen"
	)
	async def reopen_ticket(self, button: discord.ui.Button, interaction: discord.Interaction):
		"""Reopen closed ticket"""
		start_time = time.time()
		
		# Log reopen start
		logger.info(f"🔵 TICKET REOPEN START | User: {interaction.user.name} ({interaction.user.id}) | Channel: {interaction.channel.name if interaction.channel else 'Unknown'}")
		
		try:
			# Check staff permissions
			if not is_staff_member(
				interaction.user, 
				self.config.get("TICKET_STAFF_ROLES", []),
				self.config.get("TICKET_STAFF_USERS", [])
			):
				await interaction.response.send_message(
					embed=create_error_embed(
						title=self.localization.get("TICKET_ERROR_STAFF_REOPEN", "❌ Staff Only"),
						description=self.localization.get("TICKET_ERROR_STAFF_REOPEN", "Only staff members can reopen tickets."),
						bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
					),
					ephemeral=True
				)
				return
			
			await interaction.response.defer(ephemeral=True)
			
			# Update ticket status
			ticket_data = self.ticket_data.load_data()
			ticket_key = str(interaction.channel.id)
			
			if ticket_key in ticket_data["tickets"]:
				ticket_data["tickets"][ticket_key]["status"] = "open"
				self.ticket_data.save_data(ticket_data)
			
			# Get ticket creator
			ticket_creator = await get_member_safely(interaction.guild, self.ticket["user_id"])
			
			# Restore creator permissions
			if ticket_creator:
				try:
					await interaction.channel.set_permissions(
						ticket_creator,
						read_messages=True,
						send_messages=True,
						read_message_history=True,
						attach_files=True,
						embed_links=True
					)
				except discord.Forbidden:
					logger.warning(f"⚠️ Could not restore permissions for {ticket_creator.name} in {interaction.channel.name}")
			
			# Send reopened message
			reopened_embed = create_success_embed(
				title="🔓 Ticket Reopened",
				description=f"This ticket has been reopened by {interaction.user.mention}.",
				bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
			)
			
			# Create new close view
			close_view = TicketCloseView(self.config, self.localization)
			
			await interaction.channel.send(embed=reopened_embed, view=close_view)
			
			# Send DM notification to ticket creator
			if ticket_creator:
				dm_embed = create_dm_notification_embed(
					"reopened",
					interaction.guild.name,
					self.ticket["ticket_type"],
					staff_name=interaction.user.display_name,
					bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
				)
				
				await send_dm_safely(ticket_creator, dm_embed)
				logger.info(f"📩 DM NOTIFICATION SENT | User: {ticket_creator.name} | Event: ticket_reopened")
			
			# Log ticket reopening
			log_channel_id = self.config.get("TICKET_LOG_CHANNEL")
			if log_channel_id:
				log_embed = create_ticket_log_embed(
					"reopened",
					ticket_creator or interaction.user,
					self.ticket["ticket_type"],
					interaction.channel.mention,
					additional_info={"👤 Reopened by": interaction.user.mention},
					bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
				)
				
				await log_ticket_event(interaction.guild, log_channel_id, log_embed)
			
			await interaction.followup.send(
				embed=create_success_embed(
					title=self.localization.get("TICKET_SUCCESS_REOPENED", "✅ Ticket Reopened"),
					description="The ticket has been successfully reopened.",
					bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
				),
				ephemeral=True
			)
			
			# Log successful completion
			duration = round((time.time() - start_time) * 1000, 2)
			logger.info(f"✅ TICKET REOPEN SUCCESS | User: {interaction.user.name} | Duration: {duration}ms")
			
		except Exception as e:
			# Log error with full details
			duration = round((time.time() - start_time) * 1000, 2)
			logger.error(f"❌ TICKET REOPEN FAILED | User: {interaction.user.name} | Duration: {duration}ms | Error: {str(e)}")
			logger.error(f"🔍 ERROR TRACEBACK:", exc_info=True)
			
			try:
				await interaction.followup.send(
					embed=create_error_embed(
						title=self.localization.get("TICKET_ERROR_REOPEN_FAILED", "❌ Reopen Failed"),
						description=f"Failed to reopen ticket: {str(e)}",
						bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
					),
					ephemeral=True
				)
			except:
				pass  # Ignore if we can't send error message
	
	@discord.ui.button(
		label="🗑️ Delete",
		style=discord.ButtonStyle.danger,
		custom_id="ticket_delete"
	)
	async def delete_ticket(self, button: discord.ui.Button, interaction: discord.Interaction):
		"""Delete ticket channel"""
		start_time = time.time()
		
		# Log delete start
		logger.info(f"🔵 TICKET DELETE START | User: {interaction.user.name} ({interaction.user.id}) | Channel: {interaction.channel.name if interaction.channel else 'Unknown'}")
		
		try:
			# Check staff permissions
			if not is_staff_member(
				interaction.user, 
				self.config.get("TICKET_STAFF_ROLES", []),
				self.config.get("TICKET_STAFF_USERS", [])
			):
				await interaction.response.send_message(
					embed=create_error_embed(
						title=self.localization.get("TICKET_ERROR_STAFF_ONLY", "❌ Staff Only"),
						description="Only staff members can delete tickets.",
						bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
					),
					ephemeral=True
				)
				return
			
			await interaction.response.send_message(
				embed=create_success_embed(
					title=self.localization.get("TICKET_SUCCESS_DELETED", "✅ Deleting Ticket"),
					description="This ticket will be deleted in 5 seconds...",
					bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
				),
				ephemeral=True
			)
			
			# Get ticket creator for logging
			ticket_creator = await get_member_safely(interaction.guild, self.ticket["user_id"])
			
			# Log ticket deletion
			log_channel_id = self.config.get("TICKET_LOG_CHANNEL")
			if log_channel_id:
				log_embed = create_ticket_log_embed(
					"deleted",
					ticket_creator or interaction.user,
					self.ticket["ticket_type"],
					f"#{interaction.channel.name}",
					additional_info={"👤 Deleted by": interaction.user.mention},
					bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
				)
				
				await log_ticket_event(interaction.guild, log_channel_id, log_embed)
			
			# Delete ticket data
			self.ticket_data.delete_ticket(interaction.channel.id)
			
			# Wait 5 seconds then delete channel
			await asyncio.sleep(5)
			await interaction.channel.delete(reason=f"Ticket deleted by {interaction.user.name}")
			
			# Log successful completion
			duration = round((time.time() - start_time) * 1000, 2)
			logger.info(f"✅ TICKET DELETE SUCCESS | User: {interaction.user.name} | Duration: {duration}ms")
			
		except Exception as e:
			# Log error with full details
			duration = round((time.time() - start_time) * 1000, 2)
			logger.error(f"❌ TICKET DELETE FAILED | User: {interaction.user.name} | Duration: {duration}ms | Error: {str(e)}")
			logger.error(f"🔍 ERROR TRACEBACK:", exc_info=True)
			
			try:
				await interaction.followup.send(
					embed=create_error_embed(
						title=self.localization.get("TICKET_ERROR_DELETE_FAILED", "❌ Delete Failed"),
						description=f"Failed to delete ticket: {str(e)}",
						bot_avatar=interaction.client.user.avatar.url if interaction.client.user.avatar else None
					),
					ephemeral=True
				)
			except:
				pass  # Ignore if we can't send error message