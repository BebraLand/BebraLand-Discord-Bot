import discord
from discord.ext import commands, tasks
import aiohttp
import json
import os
from datetime import datetime
from src.utils.config_manager import load_config
from src.utils.localization_helper import LocalizationHelper


class TwitchMonitorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.loc_helper = LocalizationHelper()
        self.twitch_channels = self.config.get("TWITCH_CHANNELS", [])
        self.notification_channel_id = self.config.get("TWITCH_NOTIFICATION_CHANNEL")
        self.notification_role_id = self.config.get("TWITCH_NOTIFICATION_ROLE")
        
        # Store active streams and their message IDs
        self.active_streams = {}  # {channel_name: {"message_id": int, "stream_data": dict}}
        self.stream_data_file = "config/active_streams.json"
        
        # Load existing stream data
        self._load_stream_data()
        
        # Twitch API credentials from environment variables
        self.client_id = os.getenv("TWITCH_CLIENT_ID")
        self.client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        self.access_token = None
        
    def _load_stream_data(self):
        """Load active stream data from file."""
        try:
            if os.path.exists(self.stream_data_file):
                with open(self.stream_data_file, 'r', encoding='utf-8') as f:
                    self.active_streams = json.load(f)
        except Exception as e:
            print(f"Error loading stream data: {e}")
            self.active_streams = {}
    
    def _save_stream_data(self):
        """Save active stream data to file."""
        try:
            os.makedirs(os.path.dirname(self.stream_data_file), exist_ok=True)
            with open(self.stream_data_file, 'w', encoding='utf-8') as f:
                json.dump(self.active_streams, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving stream data: {e}")
    
    async def get_twitch_access_token(self):
        """Get Twitch API access token."""
        if not self.client_id or not self.client_secret:
            print("Twitch API credentials not configured")
            return None
            
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.access_token = data.get("access_token")
                        return self.access_token
                    else:
                        print(f"Failed to get Twitch access token: {response.status}")
                        return None
        except Exception as e:
            print(f"Error getting Twitch access token: {e}")
            return None
    
    async def get_stream_data(self, username):
        """Get stream data for a specific Twitch username."""
        if not self.access_token:
            await self.get_twitch_access_token()
            
        if not self.access_token:
            return None
            
        # First get user ID
        user_url = "https://api.twitch.tv/helix/users"
        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.access_token}"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                # Get user ID
                async with session.get(user_url, headers=headers, params={"login": username}) as response:
                    if response.status != 200:
                        print(f"Failed to get user data for {username}: {response.status}")
                        return None
                    
                    user_data = await response.json()
                    if not user_data.get("data"):
                        print(f"User {username} not found")
                        return None
                    
                    user_id = user_data["data"][0]["id"]
                
                # Get stream data
                stream_url = "https://api.twitch.tv/helix/streams"
                async with session.get(stream_url, headers=headers, params={"user_id": user_id}) as response:
                    if response.status != 200:
                        print(f"Failed to get stream data for {username}: {response.status}")
                        return None
                    
                    stream_data = await response.json()
                    return stream_data.get("data", [])
                    
        except Exception as e:
            print(f"Error getting stream data for {username}: {e}")
            return None
    
    async def send_live_notification(self, channel_name, stream_info):
        """Send live notification to the configured channel."""
        try:
            notification_channel = self.bot.get_channel(self.notification_channel_id)
            if not notification_channel:
                print(f"Notification channel {self.notification_channel_id} not found")
                return None
            
            # Create embed for live notification
            embed = self.loc_helper.create_embed(
                user_id=None,  # System notification, no specific user
                title_key="TWITCH_LIVE_NOTIFICATION_TITLE",
                description_key="TWITCH_LIVE_NOTIFICATION_DESC",
                color=discord.Color.purple(),
                url=f"https://twitch.tv/{channel_name}",
                streamer_name=stream_info['user_name'],
                stream_title=stream_info.get('title', 'No title')
            )
            
            # Add stream details
            embed.add_field(
                name="🎮 Game",
                value=stream_info.get('game_name', 'Unknown'),
                inline=True
            )
            
            embed.add_field(
                name="👥 Viewers",
                value=str(stream_info.get('viewer_count', 0)),
                inline=True
            )
            
            embed.add_field(
                name="🕐 Started",
                value=f"<t:{int(datetime.fromisoformat(stream_info['started_at'].replace('Z', '+00:00')).timestamp())}:R>",
                inline=True
            )
            
            # Add thumbnail if available
            thumbnail_url = stream_info.get('thumbnail_url', '').replace('{width}', '320').replace('{height}', '180')
            if thumbnail_url:
                embed.set_image(url=thumbnail_url)
            
            embed.set_footer(text=self.loc_helper.get_text(None, "TWITCH_LIVE_FOOTER"))
            embed.timestamp = datetime.utcnow()
            
            # Prepare notification content
            role_mention = ""
            if self.notification_role_id:
                role = notification_channel.guild.get_role(self.notification_role_id)
                if role:
                    role_mention = f"{role.mention} "
            
            content = f"{role_mention}**{stream_info['user_name']}** just went live on Twitch!"
            
            # Send the notification
            message = await notification_channel.send(content=content, embed=embed)
            
            # Store the message ID for later deletion
            self.active_streams[channel_name] = {
                "message_id": message.id,
                "stream_data": stream_info,
                "channel_id": notification_channel.id
            }
            self._save_stream_data()
            
            # Update bot activity to show live stream
            await self.update_bot_activity()
            
            print(f"Sent live notification for {channel_name}")
            return message
            
        except Exception as e:
            print(f"Error sending live notification for {channel_name}: {e}")
            return None
    
    async def update_live_notification_if_changed(self, channel_name, new_stream_info):
        """Update live notification if stream details have changed."""
        try:
            if channel_name not in self.active_streams:
                return
                
            stored_data = self.active_streams[channel_name]
            old_stream_info = stored_data.get("stream_data", {})
            
            # Check if important details have changed
            title_changed = old_stream_info.get('title') != new_stream_info.get('title')
            game_changed = old_stream_info.get('game_name') != new_stream_info.get('game_name')
            viewer_count_changed = abs(old_stream_info.get('viewer_count', 0) - new_stream_info.get('viewer_count', 0)) >= 10
            
            if title_changed or game_changed or viewer_count_changed:
                # Get the message to update
                channel_id = stored_data.get("channel_id")
                message_id = stored_data.get("message_id")
                
                if channel_id and message_id:
                    try:
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            message = await channel.fetch_message(message_id)
                            
                            # Create updated embed
                            embed = self.loc_helper.create_embed(
                                user_id=None,  # System notification, no specific user
                                title_key="TWITCH_LIVE_NOTIFICATION_TITLE",
                                description_key="TWITCH_LIVE_NOTIFICATION_DESC",
                                color=discord.Color.purple(),
                                url=f"https://twitch.tv/{channel_name}",
                                streamer_name=new_stream_info['user_name'],
                                stream_title=new_stream_info.get('title', 'No title')
                            )
                            
                            # Add stream details
                            embed.add_field(
                                name="🎮 Game",
                                value=new_stream_info.get('game_name', 'Unknown'),
                                inline=True
                            )
                            
                            embed.add_field(
                                name="👥 Viewers",
                                value=str(new_stream_info.get('viewer_count', 0)),
                                inline=True
                            )
                            
                            embed.add_field(
                                name="🕐 Started",
                                value=f"<t:{int(datetime.fromisoformat(new_stream_info['started_at'].replace('Z', '+00:00')).timestamp())}:R>",
                                inline=True
                            )
                            
                            # Add thumbnail if available
                            thumbnail_url = new_stream_info.get('thumbnail_url', '').replace('{width}', '320').replace('{height}', '180')
                            if thumbnail_url:
                                embed.set_image(url=thumbnail_url)
                            
                            embed.set_footer(text=self.loc_helper.get_text(None, "TWITCH_LIVE_FOOTER_UPDATED"))
                            embed.timestamp = datetime.utcnow()
                            
                            # Update the message
                            await message.edit(embed=embed)
                            
                            # Update stored data
                            self.active_streams[channel_name]["stream_data"] = new_stream_info
                            self._save_stream_data()
                            
                            # Update bot activity with new stream info
                            await self.update_bot_activity()
                            
                            print(f"Updated live notification for {channel_name}")
                            
                    except discord.NotFound:
                        # Message was deleted, remove from active streams
                        del self.active_streams[channel_name]
                        self._save_stream_data()
                    except Exception as e:
                        print(f"Error updating message for {channel_name}: {e}")
                        
        except Exception as e:
            print(f"Error updating live notification for {channel_name}: {e}")
    
    async def update_bot_activity(self):
        """Update bot's Discord activity based on active streams with priority for first channel."""
        try:
            if self.active_streams:
                # Check if priority channel (first in TWITCH_CHANNELS) is live
                priority_channel = None
                priority_stream_data = None
                
                if self.twitch_channels:
                    priority_channel_name = self.twitch_channels[0]  # "auurummm" gets priority
                    if priority_channel_name in self.active_streams:
                        priority_channel = priority_channel_name
                        priority_stream_data = self.active_streams[priority_channel_name].get("stream_data", {})
                
                if priority_channel and priority_stream_data:
                    # Priority channel is live - show it
                    activity_text = f"{priority_stream_data.get('game_name', 'Just Chatting')}"
                    stream_url = f"https://twitch.tv/{priority_channel}"
                else:
                    # Priority channel not live, show first available stream
                    first_stream = next(iter(self.active_streams.values()))
                    stream_data = first_stream.get("stream_data", {})
                    
                    if len(self.active_streams) == 1:
                        # Single stream
                        activity_text = f"{stream_data.get('game_name', 'Just Chatting')}"
                        # Get the channel name from active_streams
                        channel_name = next(iter(self.active_streams.keys()))
                        stream_url = f"https://twitch.tv/{channel_name}"
                    else:
                        # Multiple streams
                        activity_text = f"{len(self.active_streams)} streamers live!"
                        # Use first stream's URL for multiple streams
                        channel_name = next(iter(self.active_streams.keys()))
                        stream_url = f"https://twitch.tv/{channel_name}"
                
                activity = discord.Streaming(
                    name=activity_text,
                    url=stream_url
                )
                await self.bot.change_presence(activity=activity)
                print(f"Updated bot activity: Streaming {activity_text} ({stream_url})")
            else:
                # No active streams - clear activity
                await self.bot.change_presence(activity=None)
                print("Cleared bot activity - no active streams")
                
        except Exception as e:
            print(f"Error updating bot activity: {e}")
    
    async def delete_live_notification(self, channel_name):
        """Delete the live notification when stream ends."""
        try:
            if channel_name not in self.active_streams:
                return
            
            stream_data = self.active_streams[channel_name]
            message_id = stream_data.get("message_id")
            channel_id = stream_data.get("channel_id")
            
            if message_id and channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    try:
                        message = await channel.fetch_message(message_id)
                        await message.delete()
                        print(f"Deleted live notification for {channel_name}")
                    except discord.NotFound:
                        print(f"Message {message_id} not found (already deleted?)")
                    except Exception as e:
                        print(f"Error deleting message {message_id}: {e}")
            
            # Remove from active streams
            del self.active_streams[channel_name]
            self._save_stream_data()
            
            # Update bot activity after stream ends
            await self.update_bot_activity()
            
        except Exception as e:
            print(f"Error deleting live notification for {channel_name}: {e}")
    
    @tasks.loop(minutes=2)  # Check every 2 minutes
    async def check_streams(self):
        """Periodically check stream status for all configured channels."""
        try:
            for channel_name in self.twitch_channels:
                stream_data = await self.get_stream_data(channel_name)
                
                if stream_data and len(stream_data) > 0:
                    # Stream is live
                    stream_info = stream_data[0]
                    
                    if channel_name not in self.active_streams:
                        # New stream started
                        await self.send_live_notification(channel_name, stream_info)
                    else:
                        # Stream is still live - check for updates
                        await self.update_live_notification_if_changed(channel_name, stream_info)
                else:
                    # Stream is not live
                    if channel_name in self.active_streams:
                        # Stream ended
                        await self.delete_live_notification(channel_name)
                        
        except Exception as e:
            print(f"Error in stream check loop: {e}")
    
    @check_streams.before_loop
    async def before_check_streams(self):
        """Wait for bot to be ready before starting the loop."""
        await self.bot.wait_until_ready()
        print("Starting Twitch stream monitoring...")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Start the stream checking loop when bot is ready."""
        if not self.check_streams.is_running():
            self.check_streams.start()
    
    def cog_unload(self):
        """Clean up when cog is unloaded."""
        if self.check_streams.is_running():
            self.check_streams.cancel()
    
    @discord.slash_command(
        name="twitch_status",
        description="Check current Twitch stream status (Admin only)",
        default_member_permissions=discord.Permissions(administrator=True)
    )
    @commands.has_permissions(administrator=True)
    async def twitch_status(self, ctx: discord.ApplicationContext):
        """Manual command to check Twitch stream status."""
        try:
            if not self.twitch_channels:
                embed = self.loc_helper.create_error_embed(
                    user_id=ctx.author.id,
                    title_key="TWITCH_STATUS_NO_CHANNELS_TITLE",
                    description_key="TWITCH_STATUS_NO_CHANNELS_DESC"
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            embed = self.loc_helper.create_embed(
                user_id=ctx.author.id,
                title_key="TWITCH_STATUS_TITLE",
                description_key="TWITCH_STATUS_DESC",
                color=discord.Color.blue()
            )
            
            status_text = ""
            for channel_name in self.twitch_channels:
                stream_data = await self.get_stream_data(channel_name)
                
                if stream_data and len(stream_data) > 0:
                    stream_info = stream_data[0]
                    status_text += f"🔴 **{channel_name}** - LIVE\n"
                    status_text += f"   └ {stream_info.get('title', 'No title')}\n"
                    status_text += f"   └ Playing: {stream_info.get('game_name', 'Unknown')}\n"
                    status_text += f"   └ Viewers: {stream_info.get('viewer_count', 0)}\n\n"
                else:
                    status_text += f"⚫ **{channel_name}** - Offline\n\n"
            
            embed.description = status_text or self.loc_helper.get_text("TWITCH_STATUS_NO_STREAMS", user_id=ctx.author.id)
            
            # Add active notifications info
            if self.active_streams:
                active_text = ""
                for channel, data in self.active_streams.items():
                    active_text += f"📢 {channel} (Message ID: {data['message_id']})\n"
                embed.add_field(
                    name=self.loc_helper.get_text("TWITCH_STATUS_ACTIVE_NOTIFICATIONS", user_id=ctx.author.id),
                    value=active_text,
                    inline=False
                )
            
            await ctx.respond(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = self.loc_helper.create_error_embed(
                user_id=ctx.author.id,
                title_key="TWITCH_STATUS_ERROR_TITLE",
                description_key="TWITCH_STATUS_ERROR_DESC",
                error=str(e)
            )
            await ctx.respond(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(TwitchMonitorCog(bot))