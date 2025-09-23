import discord
from discord.ext import commands
import json
import logging
import asyncio
import time
from datetime import datetime, timedelta
import re
from typing import Optional, Dict, Any, List
from src.utils.config_manager import load_config, get_user_language
from src.utils.localization import LocalizationManager
from src.utils.localization_helper import LocalizationHelper

# Enhanced with detailed console logging for news delivery tracking:
# - Shows when news delivery starts with basic statistics
# - Real-time logging for each user being sent a message (success/failure)
# - Logging for scheduled news delivery process
# - Progress tracking with [NEWS] prefix for easy identification

# Set up logging
logger = logging.getLogger(__name__)

class NewsModal(discord.ui.Modal):
	"""Modal for collecting multi-language news content."""
	
	def __init__(self, schedule_time: Optional[str] = None):
		super().__init__(title="📰 Send News to All Members")
		self.schedule_time = schedule_time
		
		# English content input (required)
		self.english_input = discord.ui.InputText(
			label="English Content (Required)",
			placeholder="Enter news content in English (JSON format)...",
			style=discord.InputTextStyle.long,
			max_length=4000,
			required=True
		)
		self.add_item(self.english_input)
		
		# Lithuanian content input (optional)
		self.lithuanian_input = discord.ui.InputText(
			label="Lithuanian Content (Optional)",
			placeholder="Enter news content in Lithuanian (JSON format)...",
			style=discord.InputTextStyle.long,
			max_length=4000,
			required=False
		)
		self.add_item(self.lithuanian_input)
		
		# Russian content input (optional)
		self.russian_input = discord.ui.InputText(
			label="Russian Content (Optional)",
			placeholder="Enter news content in Russian (JSON format)...",
			style=discord.InputTextStyle.long,
			max_length=4000,
			required=False
		)
		self.add_item(self.russian_input)
	
	async def callback(self, interaction: discord.Interaction):
		"""Handle modal submission."""
		start_time = datetime.now()
		logger.info(f"🔵 MODAL SUBMIT START | User: {interaction.user.name} ({interaction.user.id}) | Guild: {interaction.guild.name if interaction.guild else 'DM'} ({interaction.guild.id if interaction.guild else 'N/A'}) | Modal: NewsModal")
		
		try:
			# Collect and validate inputs
			multi_lang_content = {}
			
			# Process English content (required)
			if self.english_input.value:
				try:
					english_data = json.loads(self.english_input.value)
					multi_lang_content['en'] = english_data
					logger.info(f"📝 ENGLISH CONTENT | Valid JSON with {len(english_data)} keys")
				except json.JSONDecodeError as e:
					logger.error(f"❌ INVALID ENGLISH JSON | Error: {str(e)}")
					await interaction.response.send_message(
						"❌ **Error**: Invalid JSON format in English content. Please check your syntax.",
						ephemeral=True
					)
					return
			
			# Process Lithuanian content (optional)
			if self.lithuanian_input.value and self.lithuanian_input.value.strip():
				try:
					lithuanian_data = json.loads(self.lithuanian_input.value)
					multi_lang_content['lt'] = lithuanian_data
					logger.info(f"📝 LITHUANIAN CONTENT | Valid JSON with {len(lithuanian_data)} keys")
				except json.JSONDecodeError as e:
					logger.error(f"❌ INVALID LITHUANIAN JSON | Error: {str(e)}")
					await interaction.response.send_message(
						"❌ **Error**: Invalid JSON format in Lithuanian content. Please check your syntax.",
						ephemeral=True
					)
					return
			
			# Process Russian content (optional)
			if self.russian_input.value and self.russian_input.value.strip():
				try:
					russian_data = json.loads(self.russian_input.value)
					multi_lang_content['ru'] = russian_data
					logger.info(f"📝 RUSSIAN CONTENT | Valid JSON with {len(russian_data)} keys")
				except json.JSONDecodeError as e:
					logger.error(f"❌ INVALID RUSSIAN JSON | Error: {str(e)}")
					await interaction.response.send_message(
						"❌ **Error**: Invalid JSON format in Russian content. Please check your syntax.",
						ephemeral=True
					)
					return
			
			# Validate that we have at least English content
			if 'en' not in multi_lang_content:
				logger.error(f"❌ NO ENGLISH CONTENT | User provided no valid English content")
				await interaction.response.send_message(
					"❌ **Error**: English content is required and must be valid JSON.",
					ephemeral=True
				)
				return
			
			# Create SendNewsCog instance and process the news
			cog = SendNewsCog(interaction.client)
			await cog._process_multi_language_news(
				interaction, 
				multi_lang_content, 
				self.schedule_time
			)
			
			duration = (datetime.now() - start_time).total_seconds() * 1000
			logger.info(f"✅ MODAL SUBMIT SUCCESS | User: {interaction.user.name} | Duration: {duration:.2f}ms")
			
		except Exception as e:
			duration = (datetime.now() - start_time).total_seconds() * 1000
			logger.error(f"❌ MODAL SUBMIT FAILED | User: {interaction.user.name} | Duration: {duration:.2f}ms | Error: {str(e)}")
			logger.error(f"🔍 ERROR TRACEBACK:", exc_info=True)
			
			try:
				if not interaction.response.is_done():
					await interaction.response.send_message(
						"❌ **Error**: An unexpected error occurred while processing your news. Please try again.",
						ephemeral=True
					)
			except:
				pass


class SendNewsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.localization = LocalizationManager()
        self.loc_helper = LocalizationHelper()
        self.scheduled_news = {}  # Store scheduled news messages

    @discord.slash_command(
        name="send_news",
        description="Send news message to all guild members via DM (Admin only)",
        default_member_permissions=discord.Permissions(administrator=True),
        contexts={discord.InteractionContextType.guild}
    )
    @commands.has_permissions(administrator=True)
    async def send_news(
        self, 
        ctx: discord.ApplicationContext,
        schedule_time: discord.Option(
            str,
            description="Schedule time: '30m' (30 min), '18:30' (today at 18:30), or Unix timestamp",
            required=False,
            default=None
        )
    ):
        """
        Admin-only command to send news messages to all guild members via DM using multi-language modal.
        Supports message scheduling. Always excludes bots from receiving news.
        """
        print(f"[NEWS] Command initiated by {ctx.author.name} in guild '{ctx.guild.name}'")
        
        try:
            # Create and send modal
            modal = NewsModal(schedule_time=schedule_time)
            await ctx.send_modal(modal)
            
            print(f"[NEWS] Modal sent to {ctx.author.name}")
            
        except Exception as e:
            print(f"[NEWS] ❌ Error sending modal: {str(e)}")
            embed = self.loc_helper.create_error_embed(
                user_id=ctx.author.id,
                title_key="SEND_NEWS_MODAL_ERROR",
                description_key="SEND_NEWS_MODAL_ERROR_DESC",
                error=str(e)
            )
            await ctx.respond(embed=embed, ephemeral=True)
            raise
    
    async def _process_multi_language_news(self, interaction, multi_lang_content, schedule_time=None):
        """
        Process multi-language news content from modal submission.
        
        Args:
            interaction: Discord interaction from modal submission
            multi_lang_content: Dictionary with language codes as keys and news content as values
            schedule_time: Optional scheduling parameter
        """
        start_time = time.time()
        logger.info(f"🔵 PROCESSING MULTI-LANG NEWS | User: {interaction.user.name} | Languages: {list(multi_lang_content.keys())}")
        
        try:
            # Use English content for validation (required)
            parsed_json = multi_lang_content['en']
            logger.info(f"📄 VALIDATING ENGLISH CONTENT | Keys: {list(parsed_json.keys())}")
            
            # Validate required fields - need at least title OR description
            if not parsed_json.get('title') and not parsed_json.get('description'):
                print(f"[NEWS] ❌ Validation failed - need at least title or description")
                embed = self.loc_helper.create_error_embed(
                    user_id=ctx.author.id,
                    title_key="SEND_NEWS_JSON_VALIDATION_ERROR",
                    description_key="SEND_NEWS_JSON_VALIDATION_ERROR_DESC"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            print(f"[NEWS] ✅ Content validation passed")
            
            # Validate JSON structure (optional fields)
            valid_optional_fields = ["title", "fields", "image", "footer", "color", "thumbnail"]
            print(f"[NEWS] Checking optional fields structure...")
            
            # Check if fields array has correct structure if present
            if "fields" in parsed_json:
                print(f"[NEWS] Validating fields array with {len(parsed_json['fields'])} items...")
                if not isinstance(parsed_json["fields"], list):
                    print("[NEWS] ❌ Fields validation failed - not an array")
                    embed = self.loc_helper.create_error_embed(
                        user_id=ctx.author.id,
                        title_key="SEND_NEWS_JSON_VALIDATION_ERROR",
                        description_key="SEND_NEWS_FIELDS_ARRAY_ERROR"
                    )
                    await ctx.respond(embed=embed, ephemeral=True)
                    return
                
                for i, field in enumerate(parsed_json["fields"]):
                    if not isinstance(field, dict) or "name" not in field or "value" not in field:
                        print(f"[NEWS] ❌ Field {i+1} validation failed - missing name/value")
                        embed = self.loc_helper.create_error_embed(
                            user_id=ctx.author.id,
                            title_key="SEND_NEWS_JSON_VALIDATION_ERROR",
                            description_key="SEND_NEWS_FIELD_VALIDATION_ERROR",
                            field_number=i+1
                        )
                        await ctx.respond(embed=embed, ephemeral=True)
                        return
                print("[NEWS] ✅ Fields array validation passed")
            
            # Get guild members count for confirmation (excluding bots by default)
            guild_members = [member for member in interaction.guild.members if not member.bot]
            member_count = len(guild_members)
            print(f"[NEWS] Found {member_count} non-bot members to send news to")
            
            if member_count == 0:
                print("[NEWS] ❌ No recipients found")
                embed = self.loc_helper.create_error_embed(
                    user_id=interaction.user.id,
                    title_key="SEND_NEWS_NO_RECIPIENTS",
                    description_key="SEND_NEWS_NO_RECIPIENTS_DESC"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Handle scheduling
            if schedule_time:
                schedule_datetime = self._parse_schedule_time(schedule_time)
                if schedule_datetime is None:
                    embed = self.loc_helper.create_error_embed(
                        user_id=interaction.user.id,
                        title_key="SEND_NEWS_INVALID_SCHEDULE_TIME",
                        description_key="SEND_NEWS_SCHEDULE_FORMAT_ERROR"
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                
                if schedule_datetime <= datetime.now():
                    embed = self.loc_helper.create_error_embed(
                        user_id=interaction.user.id,
                        title_key="SEND_NEWS_INVALID_SCHEDULE_TIME",
                        description_key="SEND_NEWS_SCHEDULE_PAST_ERROR"
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                
                # Store scheduled news info
                news_id = f"{interaction.user.id}_{datetime.now().timestamp()}"
                self.scheduled_news[news_id] = {
                    'content': parsed_json,
                    'guild': interaction.guild,
                    'author': interaction.user,
                    'scheduled_time': schedule_datetime
                }
                
                print(f"[NEWS] News scheduled for delivery at {schedule_datetime}")
                print(f"[NEWS] Schedule ID: {news_id}")
                print(f"[NEWS] Scheduled by: {interaction.user.display_name} ({interaction.user.id})")
                print(f"[NEWS] Target: {member_count} members in {interaction.guild.name}")
                
                # Send confirmation
                embed = self.loc_helper.create_embed(
                    title_key="SEND_NEWS_SCHEDULED",
                    description_key="SEND_NEWS_SCHEDULED_DESC",
                    user_id=interaction.user.id,
                    color="blue",
                    member_count=member_count
                )
                embed.add_field(
                    name="Scheduled Time",
                    value=f"<t:{int(schedule_datetime.timestamp())}:F>",
                    inline=False
                )
                embed.add_field(
                    name="Preview",
                    value=f"**{parsed_json.get('title', 'No title')}**\n{parsed_json.get('description', 'No description')[:100]}{'...' if len(parsed_json.get('description', '')) > 100 else ''}",
                    inline=False
                )
                embed.add_field(
                    name="Recipients",
                    value=f"{member_count} members (excluding bots)",
                    inline=False
                )
                await ctx.respond(embed=embed, ephemeral=True)
                
                # Schedule the actual sending
                delay_seconds = (schedule_datetime - datetime.now()).total_seconds()
                print(f"[NEWS] Waiting {delay_seconds:.0f} seconds until scheduled delivery...")
                await asyncio.sleep(delay_seconds)
                
                # Check if news is still scheduled (not cancelled)
                if news_id in self.scheduled_news:
                    print(f"[NEWS] Executing scheduled news delivery (ID: {news_id})")
                    print(f"[NEWS] Starting scheduled delivery to {interaction.guild.name}...")
                    success_count, failed_count, failed_users = await self._send_news_to_all_members(interaction.guild, multi_lang_content, interaction.user)
                    # Log scheduled news delivery results
                    await self._log_news_delivery(interaction.guild, interaction.user, success_count, failed_count, failed_users, scheduled=True)
                    del self.scheduled_news[news_id]
                    print(f"[NEWS] Scheduled delivery completed and removed from queue (ID: {news_id})")
                else:
                    print(f"[NEWS] Scheduled news was cancelled or already executed (ID: {news_id})")
                
                return
            
            # Send confirmation before sending news
            embed = self.loc_helper.create_embed(
                title_key="SEND_NEWS_SENDING",
                description_key="SEND_NEWS_SENDING_DESC",
                user_id=interaction.user.id,
                color="blue",
                member_count=member_count
            )
            embed.add_field(
                name="Preview",
                value=f"**{parsed_json.get('title', 'No title')}**\n{parsed_json.get('description', 'No description')[:100]}{'...' if len(parsed_json.get('description', '')) > 100 else ''}",
                inline=False
            )
            embed.add_field(
                name="Recipients",
                value=f"{member_count} members (excluding bots)",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=60)
            
            # Send news to all members with multi-language support
            print(f"[NEWS] Starting multi-language news delivery to {member_count} members...")
            print(f"[NEWS] Initiated by: {interaction.user.display_name} ({interaction.user.id})")
            print(f"[NEWS] Guild: {interaction.guild.name} ({interaction.guild.id})")
            print(f"[NEWS] Available languages: {list(multi_lang_content.keys())}")
            success_count, failed_count, failed_users = await self._send_news_to_all_members(interaction.guild, multi_lang_content, interaction.user)
            
            # Send final status report
            status_embed = self.loc_helper.create_embed(
                title_key="SEND_NEWS_DELIVERY_COMPLETE",
                description_key="SEND_NEWS_DELIVERY_FINISHED",
                user_id=interaction.user.id,
                color="green" if failed_count == 0 else "orange"
            )
            status_embed.add_field(
                name=self.loc_helper.get_text("SEND_NEWS_DELIVERY_STATISTICS", user_id=interaction.user.id),
                value=f"✅ Successfully sent: **{success_count}**\n❌ Failed to send: **{failed_count}**",
                inline=False
            )
            
            if failed_count > 0:
                # Show failed users with reasons
                failed_list = []
                for failed_user in failed_users[:10]:  # Limit to first 10 to avoid embed limits
                    failed_list.append(f"• {failed_user['member'].display_name} - {failed_user['reason']}")
                
                if len(failed_users) > 10:
                    failed_list.append(f"• ... and {len(failed_users) - 10} more")
                
                status_embed.add_field(
                    name="Failed Recipients",
                    value="\n".join(failed_list) if failed_list else "No specific failures recorded",
                    inline=False
                )
            
            # Log delivery results to LOG_CHANNEL
            await self._log_news_delivery(interaction.guild, interaction.user, success_count, failed_count, failed_users, scheduled=False)
            
            await interaction.followup.send(embed=status_embed, ephemeral=True, delete_after=120)
            
        except json.JSONDecodeError as e:
            embed = self.loc_helper.create_error_embed(
                title_key="SEND_NEWS_JSON_PARSE_ERROR",
                description_key="SEND_NEWS_JSON_PARSE_ERROR_DESC",
                user_id=interaction.user.id,
                error=str(e)
            )
            embed.add_field(
                name=self.loc_helper.get_text("SEND_NEWS_ERROR_DETAILS", user_id=interaction.user.id),
                value=f"Line {e.lineno}, Column {e.colno}" if hasattr(e, 'lineno') else self.loc_helper.get_text("SEND_NEWS_CHECK_JSON_SYNTAX", user_id=interaction.user.id),
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=120)
            
        except Exception as e:
            embed = self.loc_helper.create_error_embed(
                user_id=interaction.user.id,
                title_key="SEND_NEWS_UNEXPECTED_ERROR",
                description_key="SEND_NEWS_UNEXPECTED_ERROR_DESC",
                error=str(e)
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _send_news_to_all_members(self, guild, multi_lang_content, author):
        """Send news message to all guild members via DM in their preferred language.
        
        Args:
            guild: Discord guild object
            multi_lang_content: Dictionary with language codes as keys and JSON content as values
            author: User who initiated the news sending
        """
        success_count = 0
        failed_count = 0
        failed_users = []  # Track failed users and reasons
        
        # Get all members (excluding bots by default)
        members = [member for member in guild.members if not member.bot]
        total_members = len(members)
        
        print(f"[NEWS] Processing {total_members} members for multi-language DM delivery...")
        print(f"[NEWS] Available languages: {list(multi_lang_content.keys())}")
        
        for i, member in enumerate(members, 1):
            print(f"[NEWS] [{i}/{total_members}] Sending to: {member.display_name}({member.id})")
            
            try:
                # Get user's preferred language
                user_lang = get_user_language(member.id)
                print(f"[NEWS] User {member.display_name} preferred language: {user_lang}")
                
                # Select appropriate content based on user's language preference
                if user_lang in multi_lang_content:
                    selected_content = multi_lang_content[user_lang]
                    print(f"[NEWS] Using {user_lang} content for {member.display_name}")
                else:
                    # Fallback to English if user's preferred language is not available
                    selected_content = multi_lang_content['en']
                    print(f"[NEWS] Fallback to English content for {member.display_name} (preferred: {user_lang})")
                
                # Create and send the formatted message with recipient-specific placeholders
                embed = await self._create_formatted_embed(selected_content, guild, author, member)
                await member.send(embed=embed)
                success_count += 1
                print(f"[NEWS] ✅ Successfully sent to {member.display_name} in {user_lang if user_lang in multi_lang_content else 'en'}")
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)
                
            except discord.Forbidden:
                # Member has DMs disabled or blocked the bot
                failed_count += 1
                failed_users.append({
                    'member': member,
                    'reason': 'DMs disabled or bot blocked'
                })
                print(f"[NEWS] ❌ Failed to send to {member.display_name}: DMs disabled or bot blocked")
            except discord.HTTPException as e:
                # Other Discord API errors
                failed_count += 1
                failed_users.append({
                    'member': member,
                    'reason': f'Discord API error: {str(e)}'
                })
                print(f"[NEWS] ❌ Failed to send to {member.display_name}: Discord API error - {str(e)}")
            except Exception as e:
                # Unexpected errors
                print(f"[NEWS] ❌ Failed to send to {member.display_name}: Unexpected error - {str(e)}")
                failed_count += 1
                failed_users.append({
                    'member': member,
                    'reason': f'Unexpected error: {str(e)}'
                })
        
        print(f"[NEWS] Delivery completed! ✅ Success: {success_count}, ❌ Failed: {failed_count}")
        return success_count, failed_count, failed_users

    async def _create_formatted_embed(self, json_data, guild, author, recipient=None):
        """Create a formatted embed from JSON data."""
        title = self._replace_placeholders(json_data.get("title", ""), guild, author, recipient)
        description = self._replace_placeholders(json_data.get("description", ""), guild, author, recipient)
        
        # Create embed with only non-empty fields
        if title and description:
            embed = discord.Embed(title=title, description=description)
        elif title:
            embed = discord.Embed(title=title)
        elif description:
            embed = discord.Embed(description=description)
        else:
            # This shouldn't happen due to validation, but just in case
            embed = discord.Embed(title="News")
        
        # Set color - use config fallback if not provided in JSON
        if "color" in json_data:
            try:
                if isinstance(json_data["color"], str):
                    if json_data["color"].startswith("#"):
                        # Remove # and convert hex to int
                        color_hex = json_data["color"][1:]
                        embed.color = discord.Color(int(color_hex, 16))
                    else:
                        # Add # if missing and convert hex to int
                        embed.color = discord.Color(int(json_data["color"], 16))
                elif isinstance(json_data["color"], int):
                    embed.color = discord.Color(json_data["color"])
            except (ValueError, TypeError):
                # Fallback to config color if JSON color is invalid
                config = load_config()
                fallback_color = config.get("DISCORD_EMBED_COLOR", "432F20")
                embed.color = discord.Color(int(fallback_color, 16))
        else:
            # Use color from config.json when no color in JSON
            config = load_config()
            fallback_color = config.get("DISCORD_EMBED_COLOR", "432F20")
            embed.color = discord.Color(int(fallback_color, 16))
        
        # Add fields if present
        if "fields" in json_data and isinstance(json_data["fields"], list):
            for field in json_data["fields"]:
                if isinstance(field, dict) and "name" in field and "value" in field:
                    embed.add_field(
                        name=self._replace_placeholders(field["name"], guild, author, recipient),
                        value=self._replace_placeholders(field["value"], guild, author, recipient),
                        inline=field.get("inline", False)
                    )
        
        # Add image if present
        if "image" in json_data and isinstance(json_data["image"], dict) and "url" in json_data["image"]:
            image_url = self._replace_placeholders(json_data["image"]["url"], guild, author, recipient)
            if image_url and self._is_valid_url(image_url):
                embed.set_image(url=image_url)
        
        # Add thumbnail if present
        if "thumbnail" in json_data and isinstance(json_data["thumbnail"], dict) and "url" in json_data["thumbnail"]:
            thumbnail_url = self._replace_placeholders(json_data["thumbnail"]["url"], guild, author, recipient)
            if thumbnail_url and self._is_valid_url(thumbnail_url):
                embed.set_thumbnail(url=thumbnail_url)
        
        # Add footer if present
        if "footer" in json_data and isinstance(json_data["footer"], dict):
            footer_text = self._replace_placeholders(json_data["footer"].get("text", ""), guild, author, recipient)
            footer_icon = None
            if "icon_url" in json_data["footer"]:
                footer_icon = self._replace_placeholders(json_data["footer"]["icon_url"], guild, author, recipient)
            embed.set_footer(text=footer_text, icon_url=footer_icon)
        
        return embed

    def _parse_schedule_time(self, time_str):
        """Parse various time formats and return a datetime object."""
        try:
            time_str = time_str.strip()
            
            # Unix timestamp
            if time_str.isdigit() and len(time_str) >= 10:
                timestamp = int(time_str)
                return datetime.fromtimestamp(timestamp)
            
            # Minutes format (30m, 30, etc.)
            minutes_match = re.match(r'^(\d+)m?$', time_str)
            if minutes_match:
                minutes = int(minutes_match.group(1))
                if minutes > 0:
                    return datetime.now() + timedelta(minutes=minutes)
            
            # Time format (18:30, 9:15, etc.)
            time_match = re.match(r'^(\d{1,2}):(\d{2})$', time_str)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    now = datetime.now()
                    target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
                    # If the time has already passed today, schedule for tomorrow
                    if target_time <= now:
                        target_time += timedelta(days=1)
                    
                    return target_time
            
            return None
            
        except (ValueError, OverflowError):
             return None

    def _is_valid_url(self, url):
        """Check if a URL is valid and well-formed."""
        if not url or not isinstance(url, str):
            return False
        
        # Check if it's a valid HTTP/HTTPS URL
        if url.startswith(('http://', 'https://')):
            return True
        
        # Check if it's a Discord attachment URL
        if url.startswith('attachment://'):
            return True
        
        # If it's just a filename without protocol, it's not a valid URL for Discord embeds
        return False

    def _replace_placeholders(self, text, guild, author, recipient=None):
        """Replace placeholders in text with actual values."""
        if not isinstance(text, str):
            return text
            
        # Load config to get trademark
        config = load_config()
        trademark_text = config.get("DISCORD_MESSAGE_TRADEMARK", "")
        
        # Use recipient for recipient-specific placeholders, fallback to author
        target_member = recipient if recipient else author
            
        replacements = {
            "{guild_name}": guild.name if guild else "Unknown Guild",
            "{member_name}": author.display_name if author else "Unknown Member",
            "{member_mention}": author.mention if author else "@Unknown",
            "{member_avatar}": author.display_avatar.url if author and author.display_avatar else (author.default_avatar.url if author else ""),
            "{recipient_name}": target_member.display_name if target_member else "Unknown Member",
            "{recipient_mention}": target_member.mention if target_member else "@Unknown",
            "{recipient_avatar}": target_member.display_avatar.url if target_member and target_member.display_avatar else (target_member.default_avatar.url if target_member else ""),
            "{bot_avatar}": self.bot.user.display_avatar.url if self.bot.user else "",
            "{member_count}": str(guild.member_count) if guild else "0",
            "{trademark}": trademark_text
        }
        
        for placeholder, value in replacements.items():
            text = text.replace(placeholder, str(value))
        
        return text

    async def _log_news_delivery(self, guild, author, success_count, failed_count, failed_users, scheduled=False):
        """Log news delivery results to the configured LOG_CHANNEL."""
        try:
            config = load_config()
            log_channel_id = config.get("LOG_CHANNEL")
            
            if not log_channel_id:
                return  # No log channel configured
            
            log_channel = self.bot.get_channel(log_channel_id)
            if not log_channel:
                return  # Log channel not found
            
            # Create log embed - Force English for LOG_CHANNEL
            embed = self.loc_helper.create_info_embed(
                user_id=author.id,
                lang_code="en",  # Force English for LOG_CHANNEL messages
                title_key="NEWS_DELIVERY_REPORT",
                description_key="NEWS_DELIVERY_COMPLETED",
                delivery_type="Scheduled" if scheduled else "Immediate"
            )
            embed.color = discord.Color.green() if failed_count == 0 else discord.Color.orange()
            embed.timestamp = datetime.now()
            
            embed.add_field(
                name="Guild",
                value=guild.name,
                inline=True
            )
            
            embed.add_field(
                name="Sent by",
                value=author.mention,
                inline=True
            )
            
            embed.add_field(
                name="Delivery Type",
                value="Scheduled" if scheduled else "Immediate",
                inline=True
            )
            
            embed.add_field(
                name="Statistics",
                value=f"✅ Success: **{success_count}**\n❌ Failed: **{failed_count}**\n📊 Total: **{success_count + failed_count}**",
                inline=False
            )
            
            if failed_count > 0:
                # Show failed users (limit to avoid embed limits)
                failed_list = []
                for failed_user in failed_users[:15]:  # Show up to 15 failed users
                    failed_list.append(f"• {failed_user['member'].display_name} ({failed_user['member'].id}) - {failed_user['reason']}")
                
                if len(failed_users) > 15:
                    failed_list.append(f"• ... and {len(failed_users) - 15} more users")
                
                embed.add_field(
                    name="Failed Recipients",
                    value="\n".join(failed_list) if failed_list else "No failures recorded",
                    inline=False
                )
            
            embed.set_footer(text=f"Guild ID: {guild.id} | Author ID: {author.id}")
            
            await log_channel.send(embed=embed)
            
        except Exception as e:
            print(f"Error logging news delivery: {e}")

    @send_news.error
    async def send_news_error(self, ctx, error):
        """Handle command errors"""
        if isinstance(error, commands.MissingPermissions):
            embed = self.loc_helper.create_error_embed(
                user_id=ctx.author.id,
                title_key="PERMISSION_DENIED",
                description_key="PERMISSION_DENIED_DESC"
            )
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            print(f"[NEWS] ❌ Command error: {error}")
            embed = self.loc_helper.create_error_embed(
                user_id=ctx.author.id,
                title_key="SEND_NEWS_COMMAND_ERROR",
                description_key="SEND_NEWS_COMMAND_ERROR_DESC"
            )
            await ctx.respond(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(SendNewsCog(bot))