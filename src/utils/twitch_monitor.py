"""
Twitch live stream monitoring service.
Checks streamers periodically and handles notifications, roles, and messages.
"""
import asyncio
import discord
from typing import Optional
from datetime import datetime
import config.constants as constants
from src.utils.logger import get_cool_logger
from src.utils.database import get_db
from src.utils.twitch_api import get_twitch_client
from src.utils.get_embed_icon import get_embed_icon

logger = get_cool_logger(__name__)


class TwitchMonitor:
    """Monitor Twitch streams and send notifications."""

    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.is_running = False
        self.check_interval = constants.TWITCH_CHECK_INTERVAL_SECONDS

    async def start(self):
        """Start the Twitch monitoring loop."""
        if self.is_running:
            logger.warning("Twitch monitor is already running")
            return

        self.is_running = True
        logger.info("🎮 Starting Twitch stream monitor...")
        
        # Run the monitor loop
        asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """Stop the Twitch monitoring loop."""
        self.is_running = False
        logger.info("Twitch monitor stopped")

    async def _monitor_loop(self):
        """Main monitoring loop."""
        await self.bot.wait_until_ready()
        
        while self.is_running:
            try:
                await self._check_all_streamers()
            except Exception as e:
                logger.error(f"Error in Twitch monitor loop: {e}")
            
            # Wait before next check
            await asyncio.sleep(self.check_interval)

    async def _check_all_streamers(self):
        """Check all configured streamers."""
        storage = await get_db()
        twitch_client = get_twitch_client()

        for twitch_username, discord_user_id in constants.TWITCH_STREAMERS.items():
            try:
                # Get current stream info from Twitch API
                stream_info = await twitch_client.get_stream_info(twitch_username)
                
                # Get stored state from database
                stored_state = await storage.get_stream_state(twitch_username)
                
                # Determine if stream state changed
                is_live = stream_info is not None
                was_live = stored_state and stored_state.get("is_live", False)

                if is_live and not was_live:
                    # Stream just went live
                    await self._handle_stream_start(twitch_username, discord_user_id, stream_info)
                elif not is_live and was_live:
                    # Stream just went offline
                    await self._handle_stream_end(twitch_username, discord_user_id, stored_state)
                elif is_live and was_live:
                    # Stream is still live, update state
                    await storage.update_stream_state(
                        twitch_username=twitch_username,
                        is_live=True,
                        stream_id=stream_info.get("id"),
                        started_at=stream_info.get("started_at")
                    )

            except Exception as e:
                logger.error(f"Error checking stream for {twitch_username}: {e}")

    async def _handle_stream_start(self, twitch_username: str, discord_user_id: str, stream_info: dict):
        """Handle when a stream goes live."""
        try:
            logger.info(f"🔴 {twitch_username} went live!")
            
            storage = await get_db()
            
            # Get the guild (use the first guild the bot is in)
            if not self.bot.guilds:
                logger.error("Bot is not in any guilds")
                return
            
            guild = self.bot.guilds[0]  # Use first guild
            
            # Give the streamer the live role
            try:
                member = await guild.fetch_member(int(discord_user_id))
                live_role = guild.get_role(constants.TWITCH_LIVE_ROLE_ID)
                
                if live_role and member:
                    await member.add_roles(live_role)
                    logger.info(f"Added live role to {member.name}")
            except Exception as e:
                logger.error(f"Error adding live role: {e}")

            # Send notification to the channel
            channel = self.bot.get_channel(constants.TWITCH_CHANNEL_ID)
            if not channel:
                logger.error(f"Twitch channel {constants.TWITCH_CHANNEL_ID} not found")
                return

            # Build the embed
            embed = await self._build_live_embed(twitch_username, stream_info)
            
            # Build mention string - just mention the ping role
            mention_text = ""
            ping_role = guild.get_role(constants.TWITCH_PING_ROLE_ID)
            if ping_role:
                mention_text = ping_role.mention
            
            # Send the message
            message = await channel.send(content=mention_text, embed=embed)
            
            # Store the state with message ID
            await storage.update_stream_state(
                twitch_username=twitch_username,
                is_live=True,
                stream_id=stream_info.get("id"),
                notification_message_id=message.id,
                started_at=stream_info.get("started_at")
            )
            
            logger.info(f"Sent live notification for {twitch_username} (message ID: {message.id})")

        except Exception as e:
            logger.error(f"Error handling stream start for {twitch_username}: {e}")

    async def _handle_stream_end(self, twitch_username: str, discord_user_id: str, stored_state: dict):
        """Handle when a stream goes offline."""
        try:
            logger.info(f"⚫ {twitch_username} went offline")
            
            storage = await get_db()
            
            # Get the guild (use the first guild the bot is in)
            if not self.bot.guilds:
                logger.error("Bot is not in any guilds")
                return
            
            guild = self.bot.guilds[0]  # Use first guild
            
            # Remove the live role
            try:
                member = await guild.fetch_member(int(discord_user_id))
                live_role = guild.get_role(constants.TWITCH_LIVE_ROLE_ID)
                
                if live_role and member and live_role in member.roles:
                    await member.remove_roles(live_role)
                    logger.info(f"Removed live role from {member.name}")
            except Exception as e:
                logger.error(f"Error removing live role: {e}")

            # Delete the notification message
            message_id = stored_state.get("notification_message_id")
            if message_id:
                try:
                    channel = self.bot.get_channel(constants.TWITCH_CHANNEL_ID)
                    if channel:
                        message = await channel.fetch_message(message_id)
                        await message.delete()
                        logger.info(f"Deleted notification message {message_id}")
                except discord.NotFound:
                    logger.warning(f"Notification message {message_id} not found (already deleted?)")
                except Exception as e:
                    logger.error(f"Error deleting notification message: {e}")

            # Update state to offline
            await storage.update_stream_state(
                twitch_username=twitch_username,
                is_live=False,
                stream_id=None,
                notification_message_id=None,
                started_at=None
            )

        except Exception as e:
            logger.error(f"Error handling stream end for {twitch_username}: {e}")

    async def _build_live_embed(self, twitch_username: str, stream_info: dict) -> discord.Embed:
        """Build a beautiful embed for the live notification."""
        twitch_client = get_twitch_client()
        
        # Get user info for profile picture
        user_info = await twitch_client.get_user_info(twitch_username)
        
        title = stream_info.get("title", "Live on Twitch!")
        game = stream_info.get("game_name", "Just Chatting")
        viewers = stream_info.get("viewer_count", 0)
        
        embed = discord.Embed(
            title=f"🔴 {stream_info.get('user_name', twitch_username)} is now LIVE!",
            description=f"**{title}**",
            color=constants.TWITCH_EMBED_COLOR,
            url=f"https://twitch.tv/{twitch_username}"
        )
        
        embed.add_field(name="🎮 Playing", value=game, inline=True)
        embed.add_field(name="👁️ Viewers", value=str(viewers), inline=True)
        
        # Add thumbnail from stream
        thumbnail_url = stream_info.get("thumbnail_url", "")
        if thumbnail_url:
            # Replace template variables with actual dimensions
            thumbnail_url = thumbnail_url.replace("{width}", "1920").replace("{height}", "1080")
            embed.set_image(url=thumbnail_url)
        
        # Add profile picture
        if user_info:
            profile_pic = user_info.get("profile_image_url")
            if profile_pic:
                embed.set_thumbnail(url=profile_pic)
        
        # Add watch now button-like field
        embed.add_field(
            name="📺 Watch Now",
            value=f"[Click here to watch](https://twitch.tv/{twitch_username})",
            inline=False
        )
        
        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=get_embed_icon(self.bot)
        )
        
        # Add timestamp
        started_at = stream_info.get("started_at")
        if started_at:
            try:
                timestamp = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                embed.timestamp = timestamp
            except:
                pass
        
        return embed


# Global instance
_twitch_monitor: Optional[TwitchMonitor] = None


def get_twitch_monitor(bot: discord.Bot) -> TwitchMonitor:
    """Get the global Twitch monitor instance."""
    global _twitch_monitor
    if _twitch_monitor is None:
        _twitch_monitor = TwitchMonitor(bot)
    return _twitch_monitor
