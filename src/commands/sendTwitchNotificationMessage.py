from ast import Delete
import discord
from discord.ext import commands
import json
import os
import asyncio
from datetime import datetime, timedelta
import re
from src.utils.config_manager import load_config


class TwitchNotificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view
    
    @discord.ui.button(
        label="Subscribe to Twitch Notifications", 
        style=discord.ButtonStyle.green, 
        emoji="🔔",
        custom_id="twitch_subscribe"
    )
    async def subscribe_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Handle subscribe button click."""
        try:
            config = load_config()
            role_id = config.get("TWITCH_NOTIFICATION_ROLE")
            
            if not role_id:
                embed = discord.Embed(
                    title="❌ Configuration Error",
                    description="Twitch notification role is not configured.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            role = interaction.guild.get_role(int(role_id))
            if not role:
                embed = discord.Embed(
                    title="❌ Role Not Found",
                    description="The Twitch notification role could not be found.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Check if user already has the role
            if role in interaction.user.roles:
                embed = discord.Embed(
                    title="ℹ️ Already Subscribed",
                    description="You are already subscribed to Twitch notifications!",
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30)
                return
            
            # Add role to user
            await interaction.user.add_roles(role)
            
            # Store subscription in tracking file
            await self._add_subscriber(interaction.user.id, interaction.guild.id)
            
            embed = discord.Embed(
                title="✅ Subscribed Successfully",
                description=f"You have been subscribed to Twitch notifications! You now have the {role.mention} role.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Error",
                description="I don't have permission to assign roles. Please contact an administrator.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(
        label="Unsubscribe from Twitch Notifications", 
        style=discord.ButtonStyle.red, 
        emoji="🔕",
        custom_id="twitch_unsubscribe"
    )
    async def unsubscribe_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Handle unsubscribe button click."""
        try:
            config = load_config()
            role_id = config.get("TWITCH_NOTIFICATION_ROLE")
            
            if not role_id:
                embed = discord.Embed(
                    title="❌ Configuration Error",
                    description="Twitch notification role is not configured.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            role = interaction.guild.get_role(int(role_id))
            if not role:
                embed = discord.Embed(
                    title="❌ Role Not Found",
                    description="The Twitch notification role could not be found.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Check if user has the role
            if role not in interaction.user.roles:
                embed = discord.Embed(
                    title="ℹ️ Not Subscribed",
                    description="You are not currently subscribed to Twitch notifications.",
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30)
                return
            
            # Remove role from user
            await interaction.user.remove_roles(role)
            
            # Remove subscription from tracking file
            await self._remove_subscriber(interaction.user.id, interaction.guild.id)
            
            embed = discord.Embed(
                title="✅ Unsubscribed Successfully",
                description=f"You have been unsubscribed from Twitch notifications. The {role.name} role has been removed.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=30)
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Error",
                description="I don't have permission to remove roles. Please contact an administrator.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _add_subscriber(self, user_id: int, guild_id: int):
        """Add user to subscription tracking file."""
        try:
            file_path = "config/twitch_subscribers.json"
            
            # Create file if it doesn't exist
            if not os.path.exists(file_path):
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                data = {}
            else:
                with open(file_path, 'r') as f:
                    data = json.load(f)
            
            # Initialize guild data if not exists
            guild_key = str(guild_id)
            if guild_key not in data:
                data[guild_key] = []
            
            # Add user if not already in list
            if user_id not in data[guild_key]:
                data[guild_key].append(user_id)
            
            # Save updated data
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"Error adding subscriber: {e}")
    
    async def _remove_subscriber(self, user_id: int, guild_id: int):
        """Remove user from subscription tracking file."""
        try:
            file_path = "config/twitch_subscribers.json"
            
            if not os.path.exists(file_path):
                return
            
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            guild_key = str(guild_id)
            if guild_key in data and user_id in data[guild_key]:
                data[guild_key].remove(user_id)
            
            # Save updated data
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"Error removing subscriber: {e}")


class SendTwitchNotificationMessageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scheduled_messages = {}  # Store scheduled messages
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Add persistent view when bot is ready."""
        if not hasattr(self.bot, '_twitch_view_added'):
            self.bot.add_view(TwitchNotificationView())
            self.bot._twitch_view_added = True
    
    @discord.slash_command(
        name="send_twitch_notification_message",
        description="Send Twitch notification subscription message (Admin only)",
        default_member_permissions=discord.Permissions(administrator=True),
        contexts={discord.InteractionContextType.guild}
    )
    @commands.has_permissions(administrator=True)
    async def send_twitch_notification_message(
        self, 
        ctx: discord.ApplicationContext,
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
        Admin-only command to send Twitch notification subscription message with persistent buttons.
        Supports message scheduling.
        """
        try:
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
                    'channel': target_channel,
                    'author': ctx.author,
                    'scheduled_time': schedule_datetime
                }
                
                # Send confirmation
                embed = discord.Embed(
                    title="⏰ Twitch Notification Message Scheduled",
                    description=f"Twitch notification message will be sent to {target_channel.mention}",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="Scheduled Time",
                    value=f"<t:{int(schedule_datetime.timestamp())}:F>",
                    inline=False
                )
                await ctx.respond(embed=embed, ephemeral=True)
                
                # Schedule the actual sending in the background
                asyncio.create_task(self._schedule_message_task(message_id, target_channel, schedule_datetime))
                
                return
            
            # Send message immediately
            await self._send_twitch_notification_message(target_channel)
            
            # Send success confirmation
            embed_confirm = discord.Embed(
                title="✅ Twitch Notification Message Sent",
                description=f"The Twitch notification subscription message has been sent to {target_channel.mention}",
                color=discord.Color.green()
            )
            await ctx.respond(embed=embed_confirm, ephemeral=True, delete_after=120)
            
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
    
    async def _schedule_message_task(self, message_id, target_channel, schedule_datetime):
        """Background task to handle scheduled message sending."""
        try:
            # Calculate delay and wait
            delay_seconds = (schedule_datetime - datetime.now()).total_seconds()
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
            
            # Check if message is still scheduled (not cancelled)
            if message_id in self.scheduled_messages:
                await self._send_twitch_notification_message(target_channel)
                del self.scheduled_messages[message_id]
                
        except Exception as e:
            # Clean up on error
            if message_id in self.scheduled_messages:
                del self.scheduled_messages[message_id]
            print(f"Error in scheduled message task: {e}")
    
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
    
    @send_twitch_notification_message.error
    async def send_twitch_notification_message_error(self, ctx: discord.ApplicationContext, error):
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
    
    async def _send_twitch_notification_message(self, target_channel):
        """
        Helper method to send the actual Twitch notification message.
        """
        # Create embed with specified content and color
        embed = discord.Embed(
            title="Twitch Notifications",
            description="🔔 **Subscribe** to get notified when our streamers go live!\n🔕 **Unsubscribe** to stop receiving Twitch notifications.\n\nYou can change your preference at any time.",
            color=discord.Color(int("975BB3", 16))  # Convert hex color to int
        )
        
        # Create persistent view with buttons
        view = TwitchNotificationView()
        
        # Send the message
        await target_channel.send(embed=embed, view=view)

def setup(bot):
    bot.add_cog(SendTwitchNotificationMessageCog(bot))