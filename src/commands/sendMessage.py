import discord
from discord.ext import commands
import json
import asyncio
from datetime import datetime, timedelta
import re
from src.utils.config_manager import load_config
from src.utils.localization import LocalizationManager
from src.utils.localization_helper import LocalizationHelper


class SendMessageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.localization = LocalizationManager()
        self.loc_helper = LocalizationHelper(bot)
        self.scheduled_messages = {}  # Store scheduled messages

    @discord.slash_command(
        name="send_message",
        description="Send a custom message with JSON formatting (Admin only)",
        default_member_permissions=discord.Permissions(administrator=True),
        contexts={discord.InteractionContextType.guild}
    )
    @commands.has_permissions(administrator=True)
    async def send_message(
        self, 
        ctx: discord.ApplicationContext,
        content: discord.Option(
            str,
            description="JSON content for the message",
            required=True
        ),
        channel: discord.Option(
            discord.TextChannel,
            description="Channel to send the message to (defaults to current channel)",
            required=False,
            default=None
        ),
        schedule_time: discord.Option(
            str,
            description="Schedule time: '30m' (30 min), '18:30' (today at 18:30), or Unix timestamp",
            required=False,
            default=None
        )
    ):
        """
        Admin-only command to send custom messages with JSON formatting.
        Supports channel selection and message scheduling.
        """
        print(f"[SEND_MESSAGE] Command initiated by {ctx.author.name} in guild '{ctx.guild.name}'")
        print(f"[SEND_MESSAGE] Raw JSON content received: {content}")
        
        try:
            # Parse and validate JSON
            print("[SEND_MESSAGE] Parsing JSON content...")
            parsed_json = json.loads(content)
            print(f"[SEND_MESSAGE] JSON parsed successfully: {parsed_json}")
            
            # Validate required fields - need at least title OR description
            if not parsed_json.get('title') and not parsed_json.get('description'):
                print(f"[SEND_MESSAGE] ❌ Validation failed - need at least title or description")
                embed = self.loc_helper.create_error_embed(
                    title_key="SEND_MESSAGE_JSON_VALIDATION_ERROR",
                    description_key="SEND_MESSAGE_NEED_TITLE_OR_DESC",
                    user_id=ctx.author.id
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            print(f"[SEND_MESSAGE] ✅ Content validation passed")
            
            # Validate JSON structure (optional fields)
            valid_optional_fields = ["title", "fields", "image", "footer", "color", "thumbnail"]
            print(f"[SEND_MESSAGE] Checking optional fields structure...")
            
            # Check if fields array has correct structure if present
            if "fields" in parsed_json:
                print(f"[SEND_MESSAGE] Validating fields array with {len(parsed_json['fields'])} items...")
                if not isinstance(parsed_json["fields"], list):
                    print("[SEND_MESSAGE] ❌ Fields validation failed - not an array")
                    embed = self.loc_helper.create_error_embed(
                        title_key="SEND_MESSAGE_JSON_VALIDATION_ERROR",
                        description_key="SEND_MESSAGE_FIELDS_MUST_BE_ARRAY",
                        user_id=ctx.author.id
                    )
                    await ctx.respond(embed=embed, ephemeral=True)
                    return
                
                for i, field in enumerate(parsed_json["fields"]):
                    if not isinstance(field, dict) or "name" not in field or "value" not in field:
                        print(f"[SEND_MESSAGE] ❌ Field {i+1} validation failed - missing name/value")
                        embed = self.loc_helper.create_error_embed(
                            title_key="SEND_MESSAGE_JSON_VALIDATION_ERROR",
                            description_key="SEND_MESSAGE_FIELD_MISSING_NAME_VALUE",
                            user_id=ctx.author.id,
                            field_num=i+1
                        )
                        await ctx.respond(embed=embed, ephemeral=True)
                        return
                print("[SEND_MESSAGE] ✅ Fields array validation passed")
            
            # Determine target channel
            target_channel = channel if channel is not None else ctx.channel
            print(f"[SEND_MESSAGE] Target channel: #{target_channel.name} (ID: {target_channel.id})")
            
            # Handle scheduling
            if schedule_time:
                print(f"[SEND_MESSAGE] Processing schedule time: {schedule_time}")
                schedule_datetime = self._parse_schedule_time(schedule_time)
                if schedule_datetime is None:
                    print("[SEND_MESSAGE] ❌ Invalid schedule time format")
                    embed = self.loc_helper.create_error_embed(
                    title_key="SEND_MESSAGE_INVALID_SCHEDULE_TIME",
                    description_key="SEND_MESSAGE_SCHEDULE_FORMAT_ERROR",
                    user_id=ctx.author.id
                )
                    await ctx.respond(embed=embed, ephemeral=True)
                    return
                
                if schedule_datetime <= datetime.now():
                    print("[SEND_MESSAGE] ❌ Schedule time is in the past")
                    embed = self.loc_helper.create_error_embed(
                    title_key="SEND_MESSAGE_INVALID_SCHEDULE_TIME",
                    description_key="SEND_MESSAGE_SCHEDULE_PAST_ERROR",
                    user_id=ctx.author.id
                )
                    await ctx.respond(embed=embed, ephemeral=True)
                    return
                
                print(f"[SEND_MESSAGE] ✅ Message scheduled for: {schedule_datetime}")
                
                # Store scheduled message info
                message_id = f"{ctx.author.id}_{datetime.now().timestamp()}"
                self.scheduled_messages[message_id] = {
                    'content': parsed_json,
                    'channel': target_channel,
                    'author': ctx.author,
                    'scheduled_time': schedule_datetime
                }
                
                # Schedule the message
                delay = (schedule_datetime - datetime.now()).total_seconds()
                asyncio.create_task(self._send_scheduled_message(message_id, delay))
                
                embed = self.loc_helper.create_info_embed(
                    title_key="SEND_MESSAGE_SCHEDULED",
                    description_key="SEND_MESSAGE_SCHEDULED_DESC",
                    user_id=ctx.author.id,
                    channel=target_channel.mention,
                    time=schedule_datetime.strftime('%Y-%m-%d %H:%M:%S')
                )
                await ctx.respond(embed=embed, ephemeral=True)
                
                # Log the scheduling
                await self._log_message_delivery(ctx.guild, ctx.author, target_channel, parsed_json, True, scheduled=True)
                return
            
            print("[SEND_MESSAGE] Sending message immediately...")
            # Send message immediately
            success = await self._send_formatted_message(target_channel, parsed_json, ctx.guild, ctx.author)
            
            if success:
                print(f"[SEND_MESSAGE] ✅ Message sent successfully to #{target_channel.name}")
                embed = self.loc_helper.create_success_embed(
                    title_key="SEND_MESSAGE_SENT",
                    description_key="SEND_MESSAGE_SENT_DESC",
                    user_id=ctx.author.id,
                    channel=target_channel.mention
                )
                await ctx.respond(embed=embed, ephemeral=True)
                
                # Log successful delivery
                await self._log_message_delivery(ctx.guild, ctx.author, target_channel, parsed_json, True)
            else:
                print(f"[SEND_MESSAGE] ❌ Failed to send message to #{target_channel.name}")
                embed = self.loc_helper.create_error_embed(
                    title_key="SEND_MESSAGE_FAILED",
                    description_key="SEND_MESSAGE_FAILED_DESC",
                    user_id=ctx.author.id,
                    error=str(e)
                )
                await ctx.respond(embed=embed, ephemeral=True)
                
                # Log failed delivery
                await self._log_message_delivery(ctx.guild, ctx.author, target_channel, parsed_json, False, "Permission or channel error")
                
        except json.JSONDecodeError as e:
            print(f"[SEND_MESSAGE] ❌ JSON parsing error: {e}")
            embed = self.loc_helper.create_error_embed(
                title_key="SEND_MESSAGE_JSON_PARSE_ERROR",
                description_key="SEND_MESSAGE_JSON_PARSE_ERROR_DESC",
                user_id=ctx.author.id,
                error=str(e)
            )
            await ctx.respond(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"[SEND_MESSAGE] ❌ Unexpected error: {e}")
            embed = self.loc_helper.create_error_embed(
                title_key="SEND_MESSAGE_ERROR",
                description_key="SEND_MESSAGE_ERROR_DESC",
                user_id=ctx.author.id,
                error=str(e)
            )
            await ctx.respond(embed=embed, ephemeral=True)

    async def _send_formatted_message(self, channel, json_data, guild, author, scheduled=False):
        """Helper method to send a formatted message based on JSON data."""
        print(f"[SEND_MESSAGE] Creating formatted message for channel #{channel.name}")
        print(f"[SEND_MESSAGE] Message data: title='{json_data.get('title', 'No title')}', description length={len(json_data.get('description', ''))}")
        
        success = False
        error_msg = None
        
        try:
            # Create embed
            print("[SEND_MESSAGE] Building embed...")
            title = self._replace_placeholders(json_data.get("title", ""), guild, author)
            description = self._replace_placeholders(json_data.get("description", ""), guild, author)
            
            # Create embed with only non-empty fields
            if title and description:
                embed = discord.Embed(title=title, description=description)
            elif title:
                embed = discord.Embed(title=title)
            elif description:
                embed = discord.Embed(description=description)
            else:
                # This shouldn't happen due to validation, but just in case
                embed = discord.Embed(title="Message")
            
            # Set color - use config fallback if not provided in JSON
            if "color" in json_data:
                print(f"[SEND_MESSAGE] Setting custom color: {json_data['color']}")
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
                    print("[SEND_MESSAGE] ⚠️ Invalid color format, using fallback")
                    # Fallback to config color if JSON color is invalid
                    config = load_config()
                    fallback_color = config.get("DISCORD_EMBED_COLOR", "432F20")
                    embed.color = discord.Color(int(fallback_color, 16))
            else:
                print("[SEND_MESSAGE] Using default color from config")
                # Use color from config.json when no color in JSON
                config = load_config()
                fallback_color = config.get("DISCORD_EMBED_COLOR", "432F20")
                embed.color = discord.Color(int(fallback_color, 16))
            
            # Add fields if present
            if "fields" in json_data and isinstance(json_data["fields"], list):
                print(f"[SEND_MESSAGE] Adding {len(json_data['fields'])} fields to embed")
                for i, field in enumerate(json_data["fields"]):
                    if isinstance(field, dict) and "name" in field and "value" in field:
                        embed.add_field(
                            name=self._replace_placeholders(field["name"], guild, author),
                            value=self._replace_placeholders(field["value"], guild, author),
                            inline=field.get("inline", False)
                        )
                        print(f"[SEND_MESSAGE] Added field {i+1}: '{field['name']}'")
            
            # Add image if present
            if "image" in json_data and isinstance(json_data["image"], dict) and "url" in json_data["image"]:
                image_url = self._replace_placeholders(json_data["image"]["url"], guild, author)
                if image_url and self._is_valid_url(image_url):
                    embed.set_image(url=image_url)
                    print(f"[SEND_MESSAGE] Added image: {image_url}")
                else:
                    print(f"[SEND_MESSAGE] ⚠️ Invalid image URL: {image_url}")
            
            # Add thumbnail if present
            if "thumbnail" in json_data and isinstance(json_data["thumbnail"], dict) and "url" in json_data["thumbnail"]:
                thumbnail_url = self._replace_placeholders(json_data["thumbnail"]["url"], guild, author)
                if thumbnail_url and self._is_valid_url(thumbnail_url):
                    embed.set_thumbnail(url=thumbnail_url)
                    print(f"[SEND_MESSAGE] Added thumbnail: {thumbnail_url}")
                else:
                    print(f"[SEND_MESSAGE] ⚠️ Invalid thumbnail URL: {thumbnail_url}")
            
            # Add footer if present
            if "footer" in json_data and isinstance(json_data["footer"], dict):
                footer_text = self._replace_placeholders(json_data["footer"].get("text", ""), guild, author)
                footer_icon = None
                if "icon_url" in json_data["footer"]:
                    footer_icon = self._replace_placeholders(json_data["footer"]["icon_url"], guild, author)
                embed.set_footer(text=footer_text, icon_url=footer_icon)
                print(f"[SEND_MESSAGE] Added footer: '{footer_text}'")
            
            # Send the embed
            print(f"[SEND_MESSAGE] Sending embed to #{channel.name}...")
            await channel.send(embed=embed)
            success = True
            print(f"[SEND_MESSAGE] ✅ Embed sent successfully!")
            
        except Exception as e:
            error_msg = str(e)
            print(f"[SEND_MESSAGE] ❌ Error sending embed: {e}")
            print(f"[SEND_MESSAGE] Attempting fallback to text message...")
            try:
                # Send a simple text message as fallback
                title = json_data.get("title", "Message")
                description = json_data.get("description", "")
                fallback_content = f"**{title}**\n{description}" if title else description
                await channel.send(fallback_content)
                success = True
                error_msg = f"Embed failed, sent as text: {str(e)}"
                print(f"[SEND_MESSAGE] ✅ Fallback text message sent successfully")
            except Exception as fallback_error:
                error_msg = f"Complete failure: {str(fallback_error)}"
                print(f"[SEND_MESSAGE] ❌ Fallback also failed: {fallback_error}")
        
        # Log the delivery attempt
        await self._log_message_delivery(guild, author, channel, json_data, success, error_msg, scheduled)
        return success

    async def _send_scheduled_message(self, message_id, delay):
        """Handle sending a scheduled message after the specified delay."""
        print(f"[SEND_MESSAGE] Scheduled message {message_id} will be sent in {delay} seconds")
        await asyncio.sleep(delay)
        
        # Check if message is still scheduled (not cancelled)
        if message_id in self.scheduled_messages:
            message_info = self.scheduled_messages[message_id]
            print(f"[SEND_MESSAGE] Sending scheduled message {message_id} to #{message_info['channel'].name}")
            
            success = await self._send_formatted_message(
                message_info['channel'], 
                message_info['content'], 
                message_info['channel'].guild, 
                message_info['author'], 
                scheduled=True
            )
            
            if success:
                print(f"[SEND_MESSAGE] ✅ Scheduled message {message_id} sent successfully")
            else:
                print(f"[SEND_MESSAGE] ❌ Scheduled message {message_id} failed to send")
            
            # Clean up the scheduled message
            del self.scheduled_messages[message_id]
        else:
            print(f"[SEND_MESSAGE] Scheduled message {message_id} was cancelled or already sent")

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

    def _replace_placeholders(self, text, guild, author):
        """Replace placeholders in text with actual values."""
        if not isinstance(text, str):
            return text
            
        # Load config to get trademark
        config = load_config()
        trademark_text = config.get("DISCORD_MESSAGE_TRADEMARK", "")
            
        replacements = {
            "{guild_name}": guild.name if guild else "Unknown Guild",
            "{member_name}": author.display_name if author else "Unknown Member",
            "{member_mention}": author.mention if author else "@Unknown",
            "{bot_avatar}": self.bot.user.display_avatar.url if self.bot.user else "",
            "{trademark}": trademark_text
        }
        
        for placeholder, value in replacements.items():
            text = text.replace(placeholder, str(value))
        
        return text

    async def _log_message_delivery(self, guild, author, channel, json_data, success, error_msg=None, scheduled=False):
        """Log message delivery to the configured LOG_CHANNEL."""
        try:
            config = load_config()
            log_channel_id = config.get("LOG_CHANNEL")
            
            if not log_channel_id:
                return  # No log channel configured
            
            log_channel = self.bot.get_channel(int(log_channel_id))
            if not log_channel:
                return  # Log channel not found
            
            # Create log embed
            embed = discord.Embed(
                title="📨 Message Delivery Log",
                description=f"{'Scheduled' if scheduled else 'Immediate'} message delivery completed",
                color=discord.Color.green() if success else discord.Color.red(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="Server",
                value=guild.name,
                inline=True
            )
            
            embed.add_field(
                name="Sender",
                value=f"{author.display_name} ({author.mention})",
                inline=True
            )
            
            embed.add_field(
                name="Target Channel",
                value=f"#{channel.name} ({channel.mention})",
                inline=True
            )
            
            embed.add_field(
                name="Message Type",
                value="Scheduled" if scheduled else "Immediate",
                inline=True
            )
            
            embed.add_field(
                name="Status",
                value="✅ Success" if success else "❌ Failed",
                inline=True
            )
            
            if not success and error_msg:
                embed.add_field(
                    name="Error",
                    value=error_msg[:1024],  # Discord field limit
                    inline=False
                )
            
            # Add message preview
            title = json_data.get("title", "No title")
            description = json_data.get("description", "No description")
            preview = f"**{title}**\n{description[:200]}{'...' if len(description) > 200 else ''}"
            
            embed.add_field(
                name="Message Preview",
                value=preview,
                inline=False
            )
            
            embed.set_footer(text=f"Message ID: {author.id}_{int(datetime.now().timestamp())}")
            
            await log_channel.send(embed=embed)
            
        except Exception as e:
            print(f"Error logging message delivery: {e}")

    @send_message.error
    async def send_message_error(self, ctx: discord.ApplicationContext, error):
        """Handle command errors, especially permission errors."""
        if isinstance(error, commands.MissingPermissions):
            embed = self.loc_helper.create_error_embed(
                title_key="SEND_MESSAGE_PERMISSION_DENIED",
                description_key="SEND_MESSAGE_PERMISSION_DENIED_DESC",
                user_id=ctx.author.id
            )
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            embed = self.loc_helper.create_error_embed(
                title_key="SEND_MESSAGE_COMMAND_ERROR",
                description_key="SEND_MESSAGE_COMMAND_ERROR_DESC",
                user_id=ctx.author.id,
                error=str(error)
            )
            await ctx.respond(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(SendMessageCog(bot))