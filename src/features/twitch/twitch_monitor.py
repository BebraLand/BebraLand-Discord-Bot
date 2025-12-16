"""
Twitch stream monitor - checks streams periodically and manages notifications.
"""
import asyncio
import discord
from typing import Optional, Dict
from datetime import datetime
from src.utils.logger import get_cool_logger
from src.utils.twitch_api import TwitchAPI
from src.storage.factory import get_storage
import config.constants as constants

logger = get_cool_logger(__name__)


class TwitchMonitor:
    """Monitors Twitch streams and manages Discord notifications."""
    
    def __init__(self, bot: discord.Bot, client_id: str, client_secret: str):
        self.bot = bot
        self.twitch_api = TwitchAPI(client_id, client_secret)
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start the monitor loop."""
        if self.is_running:
            logger.warning("Twitch monitor is already running")
            return
        
        self.is_running = True
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info("✅ Twitch monitor started")
    
    async def stop(self):
        """Stop the monitor loop."""
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        await self.twitch_api.close()
        logger.info("Twitch monitor stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        await self.bot.wait_until_ready()
        
        while self.is_running:
            try:
                await self._check_all_streams()
            except Exception as e:
                logger.error(f"❌ Error in Twitch monitor loop: {e}")
            
            # Wait before next check (default: 60 seconds)
            await asyncio.sleep(constants.TWITCH_CHECK_INTERVAL)
    
    async def _check_all_streams(self):
        """Check all registered streamers' status."""
        storage = get_storage()
        
        # Get all registered streamers from DB
        streamers = await storage.get_all_streamers()
        
        for streamer in streamers:
            try:
                await self._check_stream(
                    discord_user_id=streamer["discord_user_id"],
                    twitch_username=streamer["twitch_username"],
                    stored_status=streamer
                )
            except Exception as e:
                logger.error(f"❌ Error checking stream for {streamer['twitch_username']}: {e}")
    
    async def _check_stream(self, discord_user_id: str, twitch_username: str, stored_status: Dict):
        """Check a single stream's status and update accordingly."""
        storage = get_storage()
        
        # Get current stream info from Twitch API
        stream_info = await self.twitch_api.get_stream_info(twitch_username)
        
        if not stream_info:
            logger.warning(f"⚠️ Could not get stream info for {twitch_username}")
            return
        
        is_currently_live = stream_info["is_live"]
        was_live = stored_status["is_live"]
        
        # Stream just went live
        if is_currently_live and not was_live:
            await self._handle_stream_start(discord_user_id, twitch_username, stream_info, stored_status)
        
        # Stream just ended
        elif not is_currently_live and was_live:
            await self._handle_stream_end(discord_user_id, twitch_username, stored_status)
    
    async def _handle_stream_start(self, discord_user_id: str, twitch_username: str, 
                                   stream_info: Dict, stored_status: Dict):
        """Handle when a stream goes live."""
        logger.info(f"🔴 {twitch_username} went live!")
        
        storage = get_storage()
        guild = self.bot.get_guild(constants.GUILD_ID)
        
        if not guild:
            logger.error(f"❌ Guild {constants.GUILD_ID} not found")
            return
        
        # Get the Discord member
        member = guild.get_member(int(discord_user_id))
        if not member:
            logger.warning(f"⚠️ Member {discord_user_id} not found in guild")
        else:
            # Add live role
            live_role = guild.get_role(constants.TWITCH_LIVE_ROLE_ID)
            if live_role:
                try:
                    await member.add_roles(live_role, reason=f"{twitch_username} is now live on Twitch")
                    logger.info(f"✅ Added live role to {member}")
                except Exception as e:
                    logger.error(f"❌ Failed to add live role to {member}: {e}")
        
        # Send notification to channel
        channel = guild.get_channel(constants.TWITCH_CHANNEL_ID)
        if not channel:
            logger.error(f"❌ Channel {constants.TWITCH_CHANNEL_ID} not found")
            return
        
        # Build beautiful embed
        embed = self._build_live_embed(stream_info)
        
        # Get ping role
        ping_content = ""
        if constants.TWITCH_PING_ROLE_ID:
            ping_role = guild.get_role(constants.TWITCH_PING_ROLE_ID)
            if ping_role:
                ping_content = ping_role.mention
        
        try:
            # Send message
            message = await channel.send(content=ping_content, embed=embed)
            
            # Store message ID and stream status in DB
            started_at = datetime.fromisoformat(stream_info["started_at"].replace('Z', '+00:00')).timestamp()
            await storage.update_stream_status(
                discord_user_id=discord_user_id,
                twitch_username=twitch_username,
                is_live=True,
                stream_id=stream_info["stream_id"],
                notification_message_id=message.id,
                started_at=started_at
            )
            
            logger.info(f"✅ Sent live notification for {twitch_username} (message ID: {message.id})")
        except Exception as e:
            logger.error(f"❌ Failed to send live notification: {e}")
    
    async def _handle_stream_end(self, discord_user_id: str, twitch_username: str, stored_status: Dict):
        """Handle when a stream goes offline."""
        logger.info(f"⚫ {twitch_username} went offline")
        
        storage = get_storage()
        guild = self.bot.get_guild(constants.GUILD_ID)
        
        if not guild:
            logger.error(f"❌ Guild {constants.GUILD_ID} not found")
            return
        
        # Get the Discord member
        member = guild.get_member(int(discord_user_id))
        if member:
            # Remove live role
            live_role = guild.get_role(constants.TWITCH_LIVE_ROLE_ID)
            if live_role and live_role in member.roles:
                try:
                    await member.remove_roles(live_role, reason=f"{twitch_username} is no longer live on Twitch")
                    logger.info(f"✅ Removed live role from {member}")
                except Exception as e:
                    logger.error(f"❌ Failed to remove live role from {member}: {e}")
        
        # Delete the notification message
        if stored_status.get("notification_message_id"):
            channel = guild.get_channel(constants.TWITCH_CHANNEL_ID)
            if channel:
                try:
                    message = await channel.fetch_message(stored_status["notification_message_id"])
                    await message.delete()
                    logger.info(f"✅ Deleted live notification message {stored_status['notification_message_id']}")
                except discord.NotFound:
                    logger.warning(f"⚠️ Notification message {stored_status['notification_message_id']} not found")
                except Exception as e:
                    logger.error(f"❌ Failed to delete notification message: {e}")
        
        # Update DB status
        await storage.update_stream_status(
            discord_user_id=discord_user_id,
            twitch_username=twitch_username,
            is_live=False,
            stream_id=None,
            notification_message_id=None,
            started_at=None
        )
    
    def _build_live_embed(self, stream_info: Dict) -> discord.Embed:
        """Build a beautiful embed for live notification."""
        embed = discord.Embed(
            title=f"🔴 {stream_info['user_name']} is now LIVE!",
            description=stream_info.get("title", "No title"),
            color=constants.TWITCH_EMBED_COLOR,
            url=f"https://twitch.tv/{stream_info['user_login']}"
        )
        
        # Add game/category
        if stream_info.get("game_name"):
            embed.add_field(
                name="🎮 Playing",
                value=stream_info["game_name"],
                inline=True
            )
        
        # Add viewer count
        embed.add_field(
            name="👥 Viewers",
            value=str(stream_info.get("viewer_count", 0)),
            inline=True
        )
        
        # Add thumbnail
        if stream_info.get("thumbnail_url"):
            # Replace placeholders in thumbnail URL
            thumbnail_url = stream_info["thumbnail_url"].replace("{width}", "1920").replace("{height}", "1080")
            # Add timestamp to prevent caching
            thumbnail_url += f"?t={int(datetime.now().timestamp())}"
            embed.set_image(url=thumbnail_url)
        
        # Add streamer profile image
        if stream_info.get("profile_image_url"):
            embed.set_thumbnail(url=stream_info["profile_image_url"])
        
        # Add footer
        embed.set_footer(
            text=f"Watch at twitch.tv/{stream_info['user_login']} • {constants.DISCORD_MESSAGE_TRADEMARK}",
            icon_url="https://static.twitchcdn.net/assets/favicon-32-e29e246c157142c94346.png"
        )
        
        embed.timestamp = datetime.now()
        
        return embed


# Global instance
_twitch_monitor: Optional[TwitchMonitor] = None


def get_twitch_monitor() -> Optional[TwitchMonitor]:
    """Get the global Twitch monitor instance."""
    return _twitch_monitor


async def start_twitch_monitor(bot: discord.Bot, client_id: str, client_secret: str):
    """Initialize and start the Twitch monitor."""
    global _twitch_monitor
    
    if not client_id or not client_secret:
        logger.warning("⚠️ Twitch API credentials not configured, monitor not started")
        return
    
    _twitch_monitor = TwitchMonitor(bot, client_id, client_secret)
    await _twitch_monitor.start()


async def stop_twitch_monitor():
    """Stop the Twitch monitor."""
    global _twitch_monitor
    
    if _twitch_monitor:
        await _twitch_monitor.stop()
        _twitch_monitor = None
