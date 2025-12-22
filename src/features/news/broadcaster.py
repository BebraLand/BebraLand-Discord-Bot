"""Core news broadcasting logic - DRY implementation."""
import io
import os
import asyncio
from typing import Optional, Union
from datetime import datetime

import discord

import config.constants as constants
from src.utils.logger import get_cool_logger
from src.utils.database import get_language
from src.utils.embed_builder import build_embed_from_data, replace_placeholders
from src.utils.get_embed_icon import get_embed_icon
from .models import NewsContent, BroadcastConfig, BroadcastResult


logger = get_cool_logger(__name__)


class NewsBroadcaster:
    """
    Centralized news broadcasting logic.
    Handles all embed building and message sending to avoid code duplication.
    """
    
    def __init__(
        self,
        bot: discord.Bot,
        guild_id: int,
        content: NewsContent,
        config: BroadcastConfig,
        image_data: Optional[bytes] = None,
        image_filename: Optional[str] = None,
        image_path: Optional[str] = None,
        ctx_for_footer: Optional[Union[discord.ApplicationContext, discord.Bot]] = None
    ):
        """
        Initialize broadcaster.
        
        Args:
            bot: Discord bot instance
            guild_id: Guild ID for the broadcast
            content: NewsContent with multilingual text
            config: BroadcastConfig with send options
            image_data: Optional image bytes
            image_filename: Optional image filename
            image_path: Optional path to image file (for scheduled broadcasts)
            ctx_for_footer: Context or bot for embed footer icon
        """
        self.bot = bot
        self.guild_id = guild_id
        self.content = content
        self.config = config
        self.image_data = image_data
        self.image_filename = image_filename
        self.image_path = image_path
        self.ctx_for_footer = ctx_for_footer or bot
        
        # Bot avatar for replacements
        self.bot_avatar = self._get_bot_avatar()
    
    def _get_bot_avatar(self) -> str:
        """Get bot avatar URL."""
        bot_user = getattr(self.bot, "user", None)
        if bot_user:
            if bot_user.avatar:
                return bot_user.avatar.url
            return bot_user.default_avatar.url
        return ""
    
    def _build_embed(self, locale: str, include_image_url: bool = False) -> Optional[discord.Embed]:
        """
        Build embed for a specific locale.
        
        Args:
            locale: Language code (en, ru, lt)
            include_image_url: Whether to include attachment:// URL in embed
        
        Returns:
            Discord embed or None if build fails
        """
        content_text = self.content.get_for_locale(locale)
        image_url = f"attachment://{self.image_filename}" if include_image_url and self.image_filename else ""
        
        replacements = {
            "{content}": content_text,
            "content": content_text,
            "{bot_avatar}": self.bot_avatar,
            "bot_avatar": self.bot_avatar,
            "{image_url}": image_url,
            "image_url": image_url,
        }
        
        # Check for locale-specific embed JSON first
        embed_json = self.content.get_embed_for_locale(locale)
        
        if embed_json and isinstance(embed_json, dict):
            try:
                processed = replace_placeholders(embed_json, replacements)
                if getattr(constants, "NEWS_DEFAULT_FOOTER", False):
                    processed["footer"] = {
                        "text": constants.DISCORD_MESSAGE_TRADEMARK,
                        "icon_url": get_embed_icon(self.ctx_for_footer),
                    }
                return build_embed_from_data(processed)
            except Exception as e:
                logger.error(f"Failed to build embed from JSON: {e}")
                return None
        
        # Build default embed
        try:
            default_data = {"description": content_text}
            if image_url:
                default_data["image"] = {"url": image_url}
            if getattr(constants, "NEWS_DEFAULT_FOOTER", False):
                default_data["footer"] = {
                    "text": constants.DISCORD_MESSAGE_TRADEMARK,
                    "icon_url": get_embed_icon(self.ctx_for_footer),
                }
            return build_embed_from_data(default_data)
        except Exception as e:
            logger.error(f"Failed to build default embed: {e}")
            return None
    
    def _make_image_file(self) -> Optional[discord.File]:
        """Create a Discord File object from image data."""
        # Prefer disk file for scheduled broadcasts
        if self.image_path and os.path.exists(self.image_path):
            try:
                with open(self.image_path, "rb") as f:
                    img_bytes = f.read()
                return discord.File(
                    fp=io.BytesIO(img_bytes),
                    filename=self.image_filename or os.path.basename(self.image_path)
                )
            except Exception as e:
                logger.error(f"Failed to read image from path: {e}")
        
        # Use in-memory image data
        if self.image_data and self.image_filename:
            try:
                return discord.File(
                    fp=io.BytesIO(self.image_data),
                    filename=self.image_filename
                )
            except Exception as e:
                logger.error(f"Failed to create image file: {e}")
        
        return None
    
    async def _send_message_with_embed(
        self,
        destination: Union[discord.TextChannel, discord.Member],
        locale: str
    ) -> bool:
        """
        Send a message with embed to a channel or user.
        
        Args:
            destination: Channel or member to send to
            locale: Language code for content
        
        Returns:
            True if successful, False otherwise
        """
        try:
            embed = self._build_embed(locale, include_image_url=False)
            content_text = self.content.get_for_locale(locale)
            
            # Send image before if configured
            if self.config.image_position == "Before":
                image_file = self._make_image_file()
                if image_file:
                    await destination.send(file=image_file)
            
            # Send embed or fallback to plain text
            if embed:
                await destination.send(embed=embed)
            else:
                await destination.send(content_text)
            
            # Send image after if configured
            if self.config.image_position == "After":
                image_file = self._make_image_file()
                if image_file:
                    await destination.send(file=image_file)
            
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {destination}: {e}")
            return False
    
    async def broadcast_to_channels(self) -> BroadcastResult:
        """
        Broadcast news to configured language-specific channels.
        
        Returns:
            BroadcastResult with statistics
        """
        result = BroadcastResult(start_time=datetime.utcnow())
        
        if not self.config.send_to_channels:
            result.end_time = datetime.utcnow()
            return result
        
        channels_to_send = [
            (getattr(constants, "NEWS_ENGLISH_CHANNEL_ID", None), "en"),
            (getattr(constants, "NEWS_RUSSIAN_CHANNEL_ID", None), "ru"),
            (getattr(constants, "NEWS_LITHUANIAN_CHANNEL_ID", None), "lt"),
        ]
        
        for channel_id, locale in channels_to_send:
            if not channel_id:
                continue
            
            channel = self.bot.get_channel(int(channel_id))
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(int(channel_id))
                except Exception as e:
                    logger.error(f"Failed to fetch channel {channel_id}: {e}")
                    result.failed_channels.append((channel_id, str(e)))
                    result.fail_count += 1
                    continue
            
            try:
                success = await self._send_message_with_embed(channel, locale)
                
                if success:
                    # Send ghost ping if configured (English channel only)
                    if self.config.send_ghost_ping and locale == "en":
                        try:
                            ping_msg = await channel.send("@everyone")
                            await ping_msg.delete()
                        except Exception as e:
                            logger.debug(f"Ghost ping failed: {e}")
                    
                    result.success_count += 1
                    try:
                        result.sent_channels.append(
                            f"<#{channel.id}> ({getattr(channel, 'name', 'channel')}, {locale})"
                        )
                    except Exception:
                        result.sent_channels.append(f"<#{channel.id}> ({locale})")
                else:
                    result.fail_count += 1
                    result.failed_channels.append((channel.id, "Send failed"))
                
                await asyncio.sleep(1)  # Rate limit protection
            except Exception as e:
                logger.error(f"Failed to send news to channel {channel.id}: {e}")
                result.failed_channels.append((channel.id, str(e)))
                result.fail_count += 1
        
        result.end_time = datetime.utcnow()
        return result
    
    async def broadcast_to_users(self) -> BroadcastResult:
        """
        Broadcast news to users via DM.
        
        Returns:
            BroadcastResult with statistics
        """
        result = BroadcastResult(start_time=datetime.utcnow())
        
        if not self.config.send_to_users:
            result.end_time = datetime.utcnow()
            return result
        
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            logger.error(f"Guild {self.guild_id} not found")
            result.end_time = datetime.utcnow()
            return result
        
        # Collect members to send to
        members = []
        if self.config.role_id:
            role = discord.utils.get(guild.roles, id=self.config.role_id)
            if role:
                members.extend(role.members)
        else:
            members.extend(guild.members)
        
        # Remove duplicates and bots
        unique_members = {m.id: m for m in members if not m.bot}
        
        for member in unique_members.values():
            try:
                member_lang = await get_language(member.id)
                success = await self._send_message_with_embed(member, member_lang)
                
                if success:
                    result.success_count += 1
                    try:
                        result.sent_users.append(
                            f"<@{member.id}> ({getattr(member, 'name', 'user')})"
                        )
                    except Exception:
                        result.sent_users.append(f"<@{member.id}>")
                else:
                    result.fail_count += 1
                    result.failed_users.append((member.id, "Send failed"))
                
                await asyncio.sleep(1)  # Rate limit protection
            except discord.Forbidden:
                logger.debug(f"Cannot send DM to {member.name}({member.id})")
                result.failed_users.append((member.id, "Forbidden"))
                result.fail_count += 1
            except Exception as e:
                logger.error(f"Failed to send news to user {member.id}: {e}")
                result.failed_users.append((member.id, str(e)))
                result.fail_count += 1
        
        result.end_time = datetime.utcnow()
        return result
    
    async def broadcast(self) -> BroadcastResult:
        """
        Execute full broadcast to both channels and users.
        
        Returns:
            Combined BroadcastResult
        """
        start_time = datetime.utcnow()
        
        # Broadcast to channels
        channel_result = await self.broadcast_to_channels()
        
        # Broadcast to users
        user_result = await self.broadcast_to_users()
        
        # Combine results
        combined_result = BroadcastResult(
            success_count=channel_result.success_count + user_result.success_count,
            fail_count=channel_result.fail_count + user_result.fail_count,
            sent_channels=channel_result.sent_channels,
            sent_users=user_result.sent_users,
            failed_channels=channel_result.failed_channels,
            failed_users=user_result.failed_users,
            start_time=start_time,
            end_time=datetime.utcnow()
        )
        
        logger.info(
            f"News broadcast completed: {combined_result.success_count} sent, "
            f"{combined_result.fail_count} failed in {combined_result.duration_seconds:.2f}s"
        )
        
        return combined_result
