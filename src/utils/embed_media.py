import io
import mimetypes
import re
from urllib.parse import unquote, urlparse

import aiohttp
import discord

from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)

MAX_EMBED_MEDIA_BYTES = 8 * 1024 * 1024


def _is_remote_url(url: str | None) -> bool:
    if not url:
        return False
    return url.startswith(("http://", "https://"))


def _safe_filename(index: int, url: str, content_type: str | None) -> str:
    path_name = unquote(urlparse(url).path.rsplit("/", 1)[-1])
    filename = re.sub(r"[^A-Za-z0-9._-]", "_", path_name).strip("._")
    if not filename:
        extension = mimetypes.guess_extension(content_type or "") or ".png"
        filename = f"embed_media_{index}{extension}"
    if "." not in filename:
        extension = mimetypes.guess_extension(content_type or "") or ".png"
        filename = f"{filename}{extension}"
    return f"{index}_{filename}"


async def _download_media(
    session: aiohttp.ClientSession,
    index: int,
    url: str,
) -> discord.File | None:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
            if response.status != 200:
                logger.warning(f"Embed media download failed ({response.status}): {url}")
                return None

            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                logger.warning(f"Embed media is not an image ({content_type}): {url}")
                return None

            data = await response.read()
            if len(data) > MAX_EMBED_MEDIA_BYTES:
                logger.warning(f"Embed media is too large ({len(data)} bytes): {url}")
                return None

            filename = _safe_filename(index, url, content_type)
            return discord.File(io.BytesIO(data), filename=filename)
    except Exception as error:
        logger.warning(f"Embed media download failed: {url}: {error}")
        return None


async def attach_remote_embed_media(
    embeds: list[discord.Embed],
) -> list[discord.File]:
    """Upload remote embed images as attachments to avoid Discord proxy failures."""
    files: list[discord.File] = []
    media_index = 1

    async with aiohttp.ClientSession() as session:
        for embed in embeds:
            image_url = (embed.to_dict().get("image") or {}).get("url")
            if _is_remote_url(image_url):
                file = await _download_media(session, media_index, image_url)
                if file:
                    embed.set_image(url=f"attachment://{file.filename}")
                    files.append(file)
                    media_index += 1

            thumbnail_url = (embed.to_dict().get("thumbnail") or {}).get("url")
            if _is_remote_url(thumbnail_url):
                file = await _download_media(session, media_index, thumbnail_url)
                if file:
                    embed.set_thumbnail(url=f"attachment://{file.filename}")
                    files.append(file)
                    media_index += 1

    return files
