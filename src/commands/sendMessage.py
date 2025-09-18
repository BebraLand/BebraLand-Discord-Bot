import discord
from discord.ext import commands
import json
import asyncio
from datetime import datetime, timedelta
import re
from src.utils.config_manager import load_config
from src.utils.localization import LocalizationManager


class SendMessageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.localization = LocalizationManager()
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
        try:
            # Parse and validate JSON
            parsed_json = json.loads(content)
            
            # Validate required fields
            required_fields = ["title", "description"]
            missing_fields = [field for field in required_fields if field not in parsed_json]
            
            if missing_fields:
                embed = discord.Embed(
                    title="❌ JSON Validation Error",
                    description=f"Missing required fields: {', '.join(missing_fields)}",
                    color=discord.Color.red()
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            # Validate JSON structure (optional fields)
            valid_optional_fields = ["fields", "image", "footer", "color", "thumbnail"]
            
            # Check if fields array has correct structure if present
            if "fields" in parsed_json:
                if not isinstance(parsed_json["fields"], list):
                    embed = discord.Embed(
                        title="❌ JSON Validation Error",
                        description="Fields must be an array",
                        color=discord.Color.red()
                    )
                    await ctx.respond(embed=embed, ephemeral=True)
                    return
                
                for i, field in enumerate(parsed_json["fields"]):
                    if not isinstance(field, dict) or "name" not in field or "value" not in field:
                        embed = discord.Embed(
                            title="❌ JSON Validation Error",
                            description=f"Field {i+1} must have 'name' and 'value' properties",
                            color=discord.Color.red()
                        )
                        await ctx.respond(embed=embed, ephemeral=True)
                        return
            
            # Determine target channel
            target_channel = channel if channel is not None else ctx.channel
            
            # Handle scheduling
            if schedule_time:
                schedule_datetime = self._parse_schedule_time(schedule_time)
                if schedule_datetime is None:
                    embed = discord.Embed(
                        title="❌ Invalid Schedule Time",
                        description="Schedule time format not recognized. Use:\n• '30m' or '30' for minutes\n• '18:30' for time today\n• Unix timestamp",
                        color=discord.Color.red()
                    )
                    await ctx.respond(embed=embed, ephemeral=True)
                    return
                
                if schedule_datetime <= datetime.now():
                    embed = discord.Embed(
                        title="❌ Invalid Schedule Time",
                        description="Schedule time must be in the future",
                        color=discord.Color.red()
                    )
                    await ctx.respond(embed=embed, ephemeral=True)
                    return
                
                # Store scheduled message info
                message_id = f"{ctx.author.id}_{datetime.now().timestamp()}"
                self.scheduled_messages[message_id] = {
                    'content': parsed_json,
                    'channel': target_channel,
                    'author': ctx.author,
                    'scheduled_time': schedule_datetime
                }
                
                # Send confirmation
                embed = discord.Embed(
                    title="⏰ Message Scheduled",
                    description=f"Message will be sent to {target_channel.mention}",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="Scheduled Time",
                    value=f"<t:{int(schedule_datetime.timestamp())}:F>",
                    inline=False
                )
                embed.add_field(
                    name="Preview",
                    value=f"**{parsed_json['title']}**\n{parsed_json['description'][:100]}{'...' if len(parsed_json['description']) > 100 else ''}",
                    inline=False
                )
                await ctx.respond(embed=embed, ephemeral=True)
                
                # Schedule the actual sending
                delay_seconds = (schedule_datetime - datetime.now()).total_seconds()
                await asyncio.sleep(delay_seconds)
                
                # Check if message is still scheduled (not cancelled)
                if message_id in self.scheduled_messages:
                    await self._send_formatted_message(target_channel, parsed_json, ctx.guild, ctx.author)
                    del self.scheduled_messages[message_id]
                
                return
            
            # Send message immediately
            await self._send_formatted_message(target_channel, parsed_json, ctx.guild, ctx.author)
            
            # Send success confirmation
            embed = discord.Embed(
                title="✅ Message Sent Successfully",
                description=f"Message has been sent to {target_channel.mention}",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Preview",
                value=f"**{parsed_json['title']}**\n{parsed_json['description'][:100]}{'...' if len(parsed_json['description']) > 100 else ''}",
                inline=False
            )
            await ctx.respond(embed=embed, ephemeral=True)
            
        except json.JSONDecodeError as e:
            embed = discord.Embed(
                title="❌ JSON Parse Error",
                description=f"Invalid JSON format: {str(e)}",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Error Details",
                value=f"Line {e.lineno}, Column {e.colno}" if hasattr(e, 'lineno') else "Please check your JSON syntax",
                inline=False
            )
            await ctx.respond(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Error",
                description="I don't have permission to send messages in that channel",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Unexpected Error",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)

    async def _send_formatted_message(self, channel, json_data, guild, author):
        """Helper method to send a formatted message based on JSON data."""
        try:
            # Create embed
            embed = discord.Embed(
                title=self._replace_placeholders(json_data.get("title", ""), guild, author),
                description=self._replace_placeholders(json_data.get("description", ""), guild, author)
            )
            
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
                            name=self._replace_placeholders(field["name"], guild, author),
                            value=self._replace_placeholders(field["value"], guild, author),
                            inline=field.get("inline", False)
                        )
            
            # Add image if present
            if "image" in json_data and isinstance(json_data["image"], dict) and "url" in json_data["image"]:
                image_url = self._replace_placeholders(json_data["image"]["url"], guild, author)
                if image_url and self._is_valid_url(image_url):
                    embed.set_image(url=image_url)
            
            # Add thumbnail if present
            if "thumbnail" in json_data and isinstance(json_data["thumbnail"], dict) and "url" in json_data["thumbnail"]:
                thumbnail_url = self._replace_placeholders(json_data["thumbnail"]["url"], guild, author)
                if thumbnail_url and self._is_valid_url(thumbnail_url):
                    embed.set_thumbnail(url=thumbnail_url)
            
            # Add footer if present
            if "footer" in json_data and isinstance(json_data["footer"], dict):
                footer_text = self._replace_placeholders(json_data["footer"].get("text", ""), guild, author)
                footer_icon = None
                if "icon_url" in json_data["footer"]:
                    footer_icon = self._replace_placeholders(json_data["footer"]["icon_url"], guild, author)
                embed.set_footer(text=footer_text, icon_url=footer_icon)
            
            # Send the embed
            await channel.send(embed=embed)
            
        except Exception as e:
            print(f"Error sending formatted message: {e}")
            # Send a simple text message as fallback
            title = json_data.get("title", "Message")
            description = json_data.get("description", "")
            await channel.send(f"**{title}**\n{description}")

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

    @send_message.error
    async def send_message_error(self, ctx: discord.ApplicationContext, error):
        """Handle command errors, especially permission errors."""
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="You need administrator permissions to use this command",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="❌ Command Error",
                description=f"An error occurred: {str(error)}",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(SendMessageCog(bot))