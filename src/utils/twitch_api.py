"""
Twitch API integration for checking stream status.
"""
import aiohttp
import time
from typing import Optional, Dict, Any
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


class TwitchAPI:
    """Twitch API client for checking stream status."""
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token: Optional[str] = None
        self.token_expires_at: float = 0
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def _ensure_session(self):
        """Ensure aiohttp session is created."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    async def _get_access_token(self) -> bool:
        """Get OAuth access token from Twitch."""
        try:
            await self._ensure_session()
            
            url = "https://id.twitch.tv/oauth2/token"
            params = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials"
            }
            
            async with self.session.post(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    self.access_token = data["access_token"]
                    expires_in = data.get("expires_in", 3600)
                    self.token_expires_at = time.time() + expires_in - 60  # Refresh 1 min early
                    logger.info("✅ Twitch access token obtained")
                    return True
                else:
                    logger.error(f"❌ Failed to get Twitch access token: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"❌ Error getting Twitch access token: {e}")
            return False
    
    async def _ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token."""
        if not self.access_token or time.time() >= self.token_expires_at:
            return await self._get_access_token()
        return True
    
    async def get_stream_info(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get stream information for a Twitch user.
        
        Args:
            username: Twitch username
            
        Returns:
            Dict with stream info if live, None if offline or error
        """
        try:
            if not await self._ensure_valid_token():
                return None
            
            await self._ensure_session()
            
            # First get user ID from username
            user_url = "https://api.twitch.tv/helix/users"
            headers = {
                "Client-ID": self.client_id,
                "Authorization": f"Bearer {self.access_token}"
            }
            params = {"login": username.lower()}
            
            async with self.session.get(user_url, headers=headers, params=params) as response:
                if response.status != 200:
                    logger.error(f"❌ Failed to get user info for {username}: {response.status}")
                    return None
                
                user_data = await response.json()
                if not user_data.get("data"):
                    logger.warning(f"⚠️ User {username} not found on Twitch")
                    return None
                
                user_id = user_data["data"][0]["id"]
            
            # Now check if user is streaming
            stream_url = "https://api.twitch.tv/helix/streams"
            params = {"user_id": user_id}
            
            async with self.session.get(stream_url, headers=headers, params=params) as response:
                if response.status != 200:
                    logger.error(f"❌ Failed to get stream info for {username}: {response.status}")
                    return None
                
                stream_data = await response.json()
                
                if stream_data.get("data") and len(stream_data["data"]) > 0:
                    # User is live
                    stream = stream_data["data"][0]
                    return {
                        "is_live": True,
                        "stream_id": stream["id"],
                        "user_id": stream["user_id"],
                        "user_login": stream["user_login"],
                        "user_name": stream["user_name"],
                        "game_id": stream["game_id"],
                        "game_name": stream["game_name"],
                        "title": stream["title"],
                        "viewer_count": stream["viewer_count"],
                        "started_at": stream["started_at"],
                        "thumbnail_url": stream["thumbnail_url"],
                        "profile_image_url": user_data["data"][0].get("profile_image_url", "")
                    }
                else:
                    # User is offline
                    return {
                        "is_live": False,
                        "user_login": username.lower(),
                        "user_name": user_data["data"][0]["display_name"],
                        "profile_image_url": user_data["data"][0].get("profile_image_url", "")
                    }
                    
        except Exception as e:
            logger.error(f"❌ Error checking stream status for {username}: {e}")
            return None
    
    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("Twitch API session closed")
