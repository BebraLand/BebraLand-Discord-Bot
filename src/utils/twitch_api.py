"""
Twitch API client for checking stream status.
"""

import os
from typing import Any, Dict, Optional

import aiohttp

from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


class TwitchAPIClient:
    """Client for interacting with Twitch API."""

    def __init__(self):
        self.client_id = os.getenv("TWITCH_CLIENT_ID")
        self.client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        self.access_token: Optional[str] = None
        self.base_url = "https://api.twitch.tv/helix"

    async def get_access_token(self) -> Optional[str]:
        """Get OAuth access token from Twitch."""
        if not self.client_id or not self.client_secret:
            logger.error("Twitch API credentials not configured")
            return None

        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.access_token = data.get("access_token")
                        logger.info("Successfully obtained Twitch access token")
                        return self.access_token
                    else:
                        logger.error(
                            f"Failed to get Twitch access token: {response.status}"
                        )
                        return None
        except Exception as e:
            logger.error(f"Error getting Twitch access token: {e}")
            return None

    async def get_stream_info(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get stream information for a Twitch user.
        Returns None if offline, or a dict with stream info if live.
        """
        if not self.access_token:
            await self.get_access_token()

        if not self.access_token:
            return None

        url = f"{self.base_url}/streams"
        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.access_token}",
        }
        params = {"user_login": username}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 401:
                        # Token expired, get a new one
                        logger.info("Twitch token expired, refreshing...")
                        await self.get_access_token()
                        return await self.get_stream_info(username)

                    if response.status == 200:
                        data = await response.json()
                        streams = data.get("data", [])

                        if streams:
                            stream = streams[0]
                            return {
                                "id": stream.get("id"),
                                "user_name": stream.get("user_name"),
                                "user_login": stream.get("user_login"),
                                "game_name": stream.get("game_name"),
                                "title": stream.get("title"),
                                "viewer_count": stream.get("viewer_count"),
                                "started_at": stream.get("started_at"),
                                "thumbnail_url": stream.get("thumbnail_url"),
                                "is_live": True,
                            }
                        return None  # Stream is offline
                    else:
                        logger.error(
                            f"Failed to get stream info for {username}: {response.status}"
                        )
                        return None
        except Exception as e:
            logger.error(f"Error checking stream status for {username}: {e}")
            return None

    async def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user information from Twitch (profile picture, etc.)."""
        if not self.access_token:
            await self.get_access_token()

        if not self.access_token:
            return None

        url = f"{self.base_url}/users"
        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.access_token}",
        }
        params = {"login": username}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 401:
                        # Token expired, get a new one
                        await self.get_access_token()
                        return await self.get_user_info(username)

                    if response.status == 200:
                        data = await response.json()
                        users = data.get("data", [])

                        if users:
                            user = users[0]
                            return {
                                "id": user.get("id"),
                                "login": user.get("login"),
                                "display_name": user.get("display_name"),
                                "profile_image_url": user.get("profile_image_url"),
                                "offline_image_url": user.get("offline_image_url"),
                                "description": user.get("description"),
                            }
                        return None
                    else:
                        logger.error(
                            f"Failed to get user info for {username}: {response.status}"
                        )
                        return None
        except Exception as e:
            logger.error(f"Error getting user info for {username}: {e}")
            return None


# Global instance
_twitch_client = None


def get_twitch_client() -> TwitchAPIClient:
    """Get the global Twitch API client instance."""
    global _twitch_client
    if _twitch_client is None:
        _twitch_client = TwitchAPIClient()
    return _twitch_client
