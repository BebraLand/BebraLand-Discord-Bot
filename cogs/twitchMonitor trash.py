import discord
from discord.ext import commands, tasks
import aiohttp
import json
import asyncio
import os
from datetime import datetime

class TwitchMonitorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = {}
        self.twitch_token = None
        self.stream_status = {}  # Track current stream status
        self.stream_details = {}  # Track detailed stream info for comparison
        self.notification_messages = {}  # Track sent notification messages
        self.load_config()
        
    def load_config(self):
        """Load configuration from config.json"""
        try:
            with open('config/config.json', 'r') as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            
    async def get_twitch_token(self):
        """Get OAuth token from Twitch API"""
        try:
            url = "https://id.twitch.tv/oauth2/token"
            params = {
                'client_id': os.getenv('TWITCH_CLIENT_ID'),
                'client_secret': os.getenv('TWITCH_CLIENT_SECRET'),
                'grant_type': 'client_credentials'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.twitch_token = data['access_token']
                        return True
                    else:
                        print(f"Failed to get Twitch token: {response.status}")
                        return False
        except Exception as e:
            print(f"Error getting Twitch token: {e}")
            return False
            
    async def get_user_info(self, username):
        """Get user information from Twitch API"""
        try:
            if not self.twitch_token:
                if not await self.get_twitch_token():
                    return None
                    
            url = f"https://api.twitch.tv/helix/users"
            headers = {
                'Client-ID': self.config.get('TWITCH_CLIENT_ID'),
                'Authorization': f'Bearer {self.twitch_token}'
            }
            params = {'login': username}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data['data']:
                            return data['data'][0]
                    return None
        except Exception as e:
            print(f"Error getting user info for {username}: {e}")
            return None
            
    async def check_stream_status(self, username):
        """Check if a streamer is live and get stream info"""
        try:
            if not self.twitch_token:
                if not await self.get_twitch_token():
                    return None
                    
            url = f"https://api.twitch.tv/helix/streams"
            headers = {
                'Client-ID': self.config.get('TWITCH_CLIENT_ID'),
                'Authorization': f'Bearer {self.twitch_token}'
            }
            params = {'user_login': username}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data['data']:
                            return data['data'][0]  # Return stream info if live
                        return False  # Not live
                    elif response.status == 401:
                        # Token expired, get new one
                        if await self.get_twitch_token():
                            return await self.check_stream_status(username)
                    else:
                        print(f"Error checking stream status: {response.status}")
                        return None
        except Exception as e:
            print(f"Error checking stream for {username}: {e}")
            return None
            
    async def create_stream_embed(self, username, stream_info, user_info=None, last_updated=None):
        """Create embed for stream notification"""
        embed = discord.Embed(
            title=f"🔴 {stream_info.get('user_name', username)} is now LIVE!",
            description=stream_info.get('title', 'Come watch the stream!'),
            color=0x9146FF,  # Twitch purple
            timestamp=datetime.utcnow()
        )
        
        # Set thumbnail to user's profile picture if available
        if user_info and user_info.get('profile_image_url'):
            embed.set_thumbnail(url=user_info['profile_image_url'])
        else:
            embed.set_thumbnail(url="https://static-cdn.jtvnw.net/jtv_user_pictures/8a6381c7-d0c0-4576-b179-38bd5ce1d6af-profile_image-300x300.png")
        
        embed.add_field(name="🎮 Game", value=stream_info.get('game_name', 'Unknown'), inline=True)
        embed.add_field(name="👥 Viewers", value=str(stream_info.get('viewer_count', 0)), inline=True)
        embed.add_field(name="🔗 Watch Now", value=f"https://twitch.tv/{username}", inline=False)
        
        # Add last updated timestamp if provided
        if last_updated:
            embed.set_footer(text=f"Last updated: {last_updated.strftime('%H:%M:%S')}")
        
    async def send_live_notification(self, username, stream_info):
        """Send notification when streamer goes live"""
        try:
            channel_id = self.config.get('TWITCH_NOTIFICATION_CHANNEL')
            role_id = self.config.get('TWITCH_NOTIFICATION_ROLE')
            
            if not channel_id:
                return
                
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return
                
            # Get user info for profile picture
            user_info = await self.get_user_info(username)
            
            # Create embed using helper method
            embed = await self.create_stream_embed(username, stream_info, user_info)
            
            # Send message with role ping
            role_mention = f"<@&{role_id}>" if role_id else ""
            content = f"{role_mention} **{stream_info.get('user_name', username)}** just went live!"
            
            message = await channel.send(content=content, embed=embed)
            
            # Store message for later updates/deletion
            self.notification_messages[username] = message.id
            
            # Store current stream details for comparison
            self.stream_details[username] = {
                'title': stream_info.get('title', ''),
                'game_name': stream_info.get('game_name', ''),
                'viewer_count': stream_info.get('viewer_count', 0),
                'user_info': user_info
            }
            
        except Exception as e:
            print(f"Error sending live notification for {username}: {e}")
            
    async def update_live_notification(self, username, stream_info):
        """Update existing notification when stream details change"""
        try:
            if username not in self.notification_messages:
                return
                
            channel_id = self.config.get('TWITCH_NOTIFICATION_CHANNEL')
            channel = self.bot.get_channel(channel_id)
            
            if not channel:
                return
                
            try:
                message = await channel.fetch_message(self.notification_messages[username])
                
                # Get user info (use cached if available)
                user_info = self.stream_details.get(username, {}).get('user_info')
                if not user_info:
                    user_info = await self.get_user_info(username)
                
                # Create updated embed with timestamp
                embed = await self.create_stream_embed(username, stream_info, user_info, datetime.utcnow())
                
                # Update the message
                await message.edit(embed=embed)
                
                # Update stored details
                self.stream_details[username] = {
                    'title': stream_info.get('title', ''),
                    'game_name': stream_info.get('game_name', ''),
                    'viewer_count': stream_info.get('viewer_count', 0),
                    'user_info': user_info
                }
                
            except discord.NotFound:
                # Message was deleted, remove from tracking
                del self.notification_messages[username]
                if username in self.stream_details:
                    del self.stream_details[username]
            except Exception as e:
                print(f"Error updating message: {e}")
                
        except Exception as e:
            print(f"Error updating live notification for {username}: {e}")
            
    def has_stream_details_changed(self, username, new_stream_info):
        """Check if stream details have changed significantly"""
        if username not in self.stream_details:
            return True
            
        old_details = self.stream_details[username]
        
        # Check for changes in title, game, or significant viewer count changes
        title_changed = old_details.get('title', '') != new_stream_info.get('title', '')
        game_changed = old_details.get('game_name', '') != new_stream_info.get('game_name', '')
        
        # Only update viewer count if change is significant (more than 5% or 10 viewers)
        old_viewers = old_details.get('viewer_count', 0)
        new_viewers = new_stream_info.get('viewer_count', 0)
        viewer_threshold = max(10, old_viewers * 0.05)  # 5% or 10 viewers minimum
        viewer_changed = abs(old_viewers - new_viewers) >= viewer_threshold
        
        return title_changed or game_changed or viewer_changed
            
    async def delete_live_notification(self, username):
        """Delete notification when streamer goes offline"""
        try:
            if username not in self.notification_messages:
                return
                
            channel_id = self.config.get('TWITCH_NOTIFICATION_CHANNEL')
            channel = self.bot.get_channel(channel_id)
            
            if channel:
                try:
                    message = await channel.fetch_message(self.notification_messages[username])
                    await message.delete()
                except discord.NotFound:
                    pass  # Message already deleted
                except Exception as e:
                    print(f"Error deleting message: {e}")
                    
            # Remove from tracking
            del self.notification_messages[username]
            if username in self.stream_details:
                del self.stream_details[username]
            
        except Exception as e:
            print(f"Error deleting notification for {username}: {e}")
    
    @tasks.loop(minutes=2)  # Check every 2 minutes
    async def monitor_streams(self):
        """Monitor all configured Twitch channels"""
        try:
            channels = self.config.get('TWITCH_CHANNELS', [])
            
            for username in channels:
                stream_info = await self.check_stream_status(username)
                
                if stream_info is None:
                    continue  # Skip if we couldn't check status
                    
                current_status = bool(stream_info)  # True if stream_info exists, False otherwise
                previous_status = self.stream_status.get(username, False)
                
                # Stream went live
                if current_status and not previous_status:
                    await self.send_live_notification(username, stream_info)
                    print(f"{username} went live!")
                    
                # Stream went offline
                elif not current_status and previous_status:
                    await self.delete_live_notification(username)
                    print(f"{username} went offline!")
                    
                # Stream is still live - check for updates
                elif current_status and previous_status:
                    if self.has_stream_details_changed(username, stream_info):
                        await self.update_live_notification(username, stream_info)
                        print(f"{username} stream details updated!")
                    
                # Update status
                self.stream_status[username] = current_status
                
        except Exception as e:
            print(f"Error in monitor_streams: {e}")
    
    @monitor_streams.before_loop
    async def before_monitor_streams(self):
        """Wait for bot to be ready before starting monitoring"""
        await self.bot.wait_until_ready()
        
    async def cog_load(self):
        """Start monitoring when cog loads"""
        if not self.monitor_streams.is_running():
            self.monitor_streams.start()
            
    async def cog_unload(self):
        """Stop monitoring when cog unloads"""
        if self.monitor_streams.is_running():
            self.monitor_streams.cancel()

async def setup(bot):
    await bot.add_cog(TwitchMonitorCog(bot))