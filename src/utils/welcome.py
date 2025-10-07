import discord
from discord.ext import commands
from src.utils.logger import get_cool_logger
import config.constants as constants
import json
from datetime import datetime

logger = get_cool_logger(__name__)


def create_welcome_embed(member: discord.Member, bot: commands.Bot = None):
    """
    Creates a Discord embed from a JSON template with dynamic placeholder replacement.
    
    Args:
        member: Discord member object
        
    Returns:
        tuple: (embed, error_message, error_file_path)
    """
    try:
        with open("src/languages/messages/welcome_message.json", "r", encoding="utf-8") as f:
            welcome_message = json.load(f)
    except FileNotFoundError:
        logger.error("Error: welcome_message.json not found!")
        return None, None, "src/languages/messages/welcome_message.json"
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing welcome_message.json: {e}")
        return None, None, "src/languages/messages/welcome_message.json"
    
    trademark_text = constants.DISCORD_MESSAGE_TRADEMARK
    override_footer = constants.WELCOME_FORCE_DEFAULT_FOOTER

    # Prepare replacement values
    replacements = {
        "{guild_name}": member.guild.name,
        "{member_name}": member.display_name,
        "{member_mention}": member.mention,
        "{member_avatar}": member.avatar.url if member.avatar else member.default_avatar.url,
        "{bot_avatar}": bot.user.avatar.url if bot and bot.user.avatar else (bot.user.default_avatar.url if bot else ""),
        "{member_count}": str(member.guild.member_count),
        "{trademark}": trademark_text
    }

    # Helper function to recursively replace placeholders
    def replace_placeholders(data):
        """
        Recursively replaces placeholders in strings, dicts, and lists.
        
        Args:
            data: Can be str, dict, list, or any other type
            
        Returns:
            Processed data with placeholders replaced
        """
        if isinstance(data, str):
            # Replace all placeholders in the string
            for placeholder, value in replacements.items():
                if value is not None:
                    data = data.replace(placeholder, str(value))
            return data
        elif isinstance(data, dict):
            # Recursively process dictionary values
            return {key: replace_placeholders(value) for key, value in data.items()}
        elif isinstance(data, list):
            # Recursively process list items
            return [replace_placeholders(item) for item in data]
        else:
            # Return other types unchanged (int, bool, None, etc.)
            return data

    # Process the welcome message data
    processed_data = replace_placeholders(welcome_message)
    
    # Override footer if config requires it
    if override_footer:
        processed_data["footer"] = {
            "text": trademark_text,
            "icon_url": bot.user.avatar.url if bot and bot.user.avatar else (bot.user.default_avatar.url if bot else "")
        }
    
    # Build the Discord embed
    try:
        embed = build_embed_from_data(processed_data)
        return embed, None, None
    except Exception as e:
        logger.error(f"Error creating embed: {e}")
        return None, str(e), None


def build_embed_from_data(data):
    """
    Builds a Discord embed from processed JSON data.
    Adapts to any combination of fields present in the JSON.
    
    Args:
        data: Dictionary containing embed properties
        
    Returns:
        discord.Embed: Constructed Discord embed
    """
    # Handle color: use from JSON if present, otherwise use default
    color = None
    if "color" in data:
        color_value = data["color"]
        if isinstance(color_value, str):
            # Remove # if present and convert hex to int
            color = int(color_value.lstrip('#'), 16)
        elif isinstance(color_value, int):
            color = color_value
    else:
        # Use default color from constants
        try:
            default_color = constants.DISCORD_EMBED_COLOR
            color = int(default_color.lstrip('#'), 16)
        except:
            color = 0x714C35  # Fallback if config not available
    
    # Create base embed - title and description are optional
    # Discord requires at least one of: title, description, or fields
    embed = discord.Embed(color=color)
    
    # Set title if present
    if "title" in data and data["title"]:
        embed.title = data["title"]
    
    # Set description if present
    if "description" in data and data["description"]:
        embed.description = data["description"]
    
    # Set URL if present
    if "url" in data and data["url"]:
        embed.url = data["url"]
    
    # Set author if present
    if "author" in data and data["author"]:
        author = data["author"]
        # Only set author if at least name is present
        if author.get("name"):
            embed.set_author(
                name=author.get("name"),
                url=author.get("url"),
                icon_url=author.get("icon_url")
            )
    
    # Set footer if present
    if "footer" in data and data["footer"]:
        footer = data["footer"]
        # Only set footer if text is present
        if footer.get("text"):
            embed.set_footer(
                text=footer.get("text"),
                icon_url=footer.get("icon_url")
            )
    
    # Set thumbnail if present
    if "thumbnail" in data and data["thumbnail"]:
        thumbnail_url = data["thumbnail"].get("url")
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
    
    # Set image if present
    if "image" in data and data["image"]:
        image_url = data["image"].get("url")
        if image_url:
            embed.set_image(url=image_url)
    
    # Add fields if present
    if "fields" in data and data["fields"]:
        for field in data["fields"]:
            # Only add field if both name and value are present
            if field.get("name") and field.get("value"):
                embed.add_field(
                    name=field.get("name"),
                    value=field.get("value"),
                    inline=field.get("inline", False)
                )
    
    # Set timestamp if present
    if "timestamp" in data and data["timestamp"]:
        timestamp_value = data["timestamp"]
        # Handle both seconds and milliseconds timestamps
        if timestamp_value > 10000000000:  # Likely milliseconds
            timestamp_value = timestamp_value / 1000
        embed.timestamp = datetime.utcfromtimestamp(timestamp_value)
    
    return embed


async def sent_welcome_message(member: discord.Member, bot: commands.Bot = None):
    embed, error_message, _ = create_welcome_embed(member, bot)
    try:
        if embed is not None:
            await member.send(embed=embed)
        else:
            await member.send(error_message or "Welcome to the server!")
        logger.info(f"✅ Sent welcome message to {member.name}({member.id})")
    except discord.Forbidden:
        logger.warning(
            f"⚠️ Can't send DM to {member.name}({member.id}) (forbidden).")
