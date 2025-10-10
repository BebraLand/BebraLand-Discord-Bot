from ast import Delete
import discord
from discord.ext import commands
import json
import os
import asyncio
from datetime import datetime, timedelta
import re
from src.utils.config_manager import load_config
from src.utils.localization_helper import LocalizationHelper
import logging


class TwitchNotificationView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)  # Persistent view
        self.bot = bot
        self.config = load_config()
        self.loc_helper = LocalizationHelper(bot)
    
    @discord.ui.button(
        label="Subscribe to Twitch Notifications", 
        style=discord.ButtonStyle.green, 
        emoji="🔔",
        custom_id="twitch_subscribe"
    )
    async def subscribe_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Handle subscribe button click."""
        try:
            # Check if user has required role
            required_role_id = self.config.get("TWITCH_NOTIFICATION_ROLE_ID")
            if not required_role_id:
                embed = self.loc_helper.create_error_embed(
                    title_key="TWITCH_CONFIG_ERROR",
                    description_key="TWITCH_CONFIG_ERROR_DESC",
                    user_id=interaction.user.id
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            required_role = interaction.guild.get_role(int(required_role_id))
            if not required_role:
                embed = self.loc_helper.create_error_embed(
                    title_key="TWITCH_ROLE_NOT_FOUND",
                    description_key="TWITCH_ROLE_NOT_FOUND_DESC",
                    user_id=interaction.user.id
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Check if user already has the role
            if required_role in interaction.user.roles:
                embed = self.loc_helper.create_embed(
                    title_key="TWITCH_ALREADY_SUBSCRIBED",
                    description_key="TWITCH_ALREADY_SUBSCRIBED_DESC",
                    user_id=interaction.user.id,
                    color="0099ff"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Add role to user
            await interaction.user.add_roles(required_role)
            
            # Store subscription in tracking file
            await self._add_subscriber(interaction.user.id, interaction.guild.id)
            
            embed = self.loc_helper.create_success_embed(
                title_key="TWITCH_SUBSCRIBED_SUCCESS",
                description_key="TWITCH_SUBSCRIBED_SUCCESS_DESC",
                user_id=interaction.user.id
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            embed = self.loc_helper.create_error_embed(
                title_key="TWITCH_PERMISSION_ERROR",
                description_key="TWITCH_PERMISSION_ERROR_DESC",
                user_id=interaction.user.id
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logging.error(f"Error in subscribe button: {e}")
            embed = self.loc_helper.create_error_embed(
                title_key="TWITCH_ERROR_TITLE",
                description_key="TWITCH_ERROR_DESC",
                user_id=interaction.user.id
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
            required_role_id = self.config.get("TWITCH_NOTIFICATION_ROLE_ID")
            if not required_role_id:
                embed = self.loc_helper.create_error_embed(
                    title_key="TWITCH_CONFIG_ERROR",
                    description_key="TWITCH_CONFIG_ERROR_DESC",
                    user_id=interaction.user.id
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            required_role = interaction.guild.get_role(int(required_role_id))
            if not required_role:
                embed = self.loc_helper.create_error_embed(
                    title_key="TWITCH_ROLE_NOT_FOUND",
                    description_key="TWITCH_ROLE_NOT_FOUND_DESC",
                    user_id=interaction.user.id
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Check if user has the role
            if required_role not in interaction.user.roles:
                embed = self.loc_helper.create_embed(
                    title_key="TWITCH_NOT_SUBSCRIBED",
                    description_key="TWITCH_NOT_SUBSCRIBED_DESC",
                    user_id=interaction.user.id,
                    color="0099ff"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Remove role from user
            await interaction.user.remove_roles(required_role)
            
            # Remove subscription from tracking file
            await self._remove_subscriber(interaction.user.id, interaction.guild.id)
            
            embed = self.loc_helper.create_success_embed(
                title_key="TWITCH_UNSUBSCRIBED_SUCCESS",
                description_key="TWITCH_UNSUBSCRIBED_SUCCESS_DESC",
                user_id=interaction.user.id
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            embed = self.loc_helper.create_error_embed(
                title_key="TWITCH_PERMISSION_ERROR",
                description_key="TWITCH_PERMISSION_ERROR_DESC",
                user_id=interaction.user.id
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logging.error(f"Error in unsubscribe button: {e}")
            embed = self.loc_helper.create_error_embed(
                title_key="TWITCH_ERROR_TITLE",
                description_key="TWITCH_ERROR_DESC",
                user_id=interaction.user.id
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
        self.config = load_config()
        self.loc_helper = LocalizationHelper(bot)
        self.scheduled_messages = {}  # Store scheduled messages
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Add persistent view when bot is ready."""
        if not hasattr(self.bot, '_twitch_view_added'):
            self.bot.add_view(TwitchNotificationView(self.bot))
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
                    embed = self.loc_helper.create_error_embed(
                        title_key="TWITCH_INVALID_SCHEDULE_TIME",
                        description_key="TWITCH_INVALID_SCHEDULE_TIME_DESC",
                        user_id=ctx.author.id
                    )
                    await ctx.respond(embed=embed, ephemeral=True)
                    return
                
                if schedule_datetime <= datetime.now():
                    embed = self.loc_helper.create_error_embed(
                        title_key="TWITCH_INVALID_SCHEDULE_TIME",
                        description_key="TWITCH_SCHEDULE_TIME_FUTURE",
                        user_id=ctx.author.id
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
                embed = self.loc_helper.create_success_embed(
                    title_key="TWITCH_MESSAGE_SCHEDULED",
                    description_key="TWITCH_MESSAGE_SCHEDULED_DESC",
                    user_id=ctx.author.id,
                    channel=target_channel.mention,
                    time=f"<t:{int(schedule_datetime.timestamp())}:F>"
                )
                await ctx.respond(embed=embed, ephemeral=True)
                
                # Schedule the actual sending in the background
                asyncio.create_task(self._schedule_message_task(message_id, target_channel, schedule_datetime))
                
                return
            
            # Send message immediately
            await self._send_twitch_notification_message(target_channel)
            
            # Send success confirmation
            embed_confirm = self.loc_helper.create_success_embed(
                title_key="TWITCH_MESSAGE_SENT",
                description_key="TWITCH_MESSAGE_SENT_DESC",
                user_id=ctx.author.id,
                channel=target_channel.mention
            )
            await ctx.respond(embed=embed_confirm, ephemeral=True, delete_after=120)
            
        except discord.Forbidden:
            embed = self.loc_helper.create_error_embed(
                title_key="TWITCH_PERMISSION_ERROR",
                description_key="TWITCH_CHANNEL_PERMISSION_ERROR",
                user_id=ctx.author.id
            )
            await ctx.respond(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = self.loc_helper.create_error_embed(
                title_key="TWITCH_ERROR_TITLE",
                description_key="TWITCH_ERROR_DESC",
                user_id=ctx.author.id
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
            embed = self.loc_helper.create_error_embed(
                title_key="TWITCH_PERMISSION_DENIED",
                description_key="TWITCH_ADMIN_REQUIRED",
                user_id=ctx.author.id
            )
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            embed = self.loc_helper.create_error_embed(
                title_key="TWITCH_COMMAND_ERROR",
                description_key="TWITCH_COMMAND_ERROR_DESC",
                user_id=ctx.author.id,
                error=str(error)
            )
            await ctx.respond(embed=embed, ephemeral=True)
    
    async def _send_twitch_notification_message(self, target_channel):
        """
        Helper method to send the actual Twitch notification message.
        """
        # Create embed for the notification message
        embed = self.loc_helper.create_embed(
            title_key="TWITCH_SUBSCRIBE_TITLE",
            description_key="TWITCH_SUBSCRIBE_DESC",
            color="9146ff"  # Twitch purple
        )
        # Add localized field for benefits
        self.loc_helper.add_localized_field(
            embed,
            name_key="TWITCH_BENEFITS_TITLE",
            value_key="TWITCH_BENEFITS_DESC",
            inline=False
        )
        
        # Create persistent view with buttons
        view = TwitchNotificationView(self.bot)
        
        # Send the message
        await target_channel.send(embed=embed, view=view)

def setup(bot):
    bot.add_cog(SendTwitchNotificationMessageCog(bot))