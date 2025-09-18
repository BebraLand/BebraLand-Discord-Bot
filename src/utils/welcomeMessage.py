import discord
from discord.ext import commands
from src.utils.config_manager import load_config
from src.utils.localization import LocalizationManager
import os

localization = LocalizationManager(default_lang="en")  # Load default language

class WelcomeMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        embed, file, missing_local = self.create_welcome_embed(member)
        
        try:
            if file:
                await member.send(embed=embed, file=file)
            else:
                await member.send(embed=embed)
            
            # Log successful welcome message
            await self.log_message("LOG_WELCOME_SENT", 
                                 member_mention=member.mention,
                                 member_name=member.display_name, 
                                 member_id=member.id, 
                                 guild_name=member.guild.name)
        except Exception as e:
            # Log failed welcome message
            await self.log_message("LOG_WELCOME_FAILED", 
                                 member_name=member.display_name, 
                                 member_id=member.id, 
                                 error=str(e))
            
            warning_msg = localization.get("TESTWELCOME_NO_DM") + f" ({member.name})"
            print(f"Could not send a welcome DM to {member.name}.")
            
            # Send to LOG_CHANNEL
            config = load_config()
            log_channel_id = config.get("LOG_CHANNEL")
            if log_channel_id:
                log_channel = self.bot.get_channel(log_channel_id)
                if log_channel:
                    await log_channel.send(warning_msg)

        # Send warning to log channel if local file missing
        if missing_local:
            await self.send_log_warning(missing_local)


    @discord.slash_command(
        name='testwelcome',
        description="Test the welcome message - Admin only",
        default_member_permissions=discord.Permissions(administrator=True)
    )
    async def test_welcome(self, ctx, member: discord.Member = None):
        """Test the welcome message - Admin only"""
        # Check if command is used in a guild
        if ctx.guild is None:
            await ctx.respond(localization.get("TESTWELCOME_DM_ONLY"), ephemeral=True, delete_after=20)
            return
            
        if member is None:
            member = ctx.author
        
        # Log test welcome execution
        await self.log_message("LOG_TEST_WELCOME", 
                             admin_mention=ctx.author.mention, 
                             member_mention=member.mention)
        
        embed, file, missing_local = self.create_welcome_embed(member)
        
        try:
            if file:
                await member.send(embed=embed, file=file)
            else:
                await member.send(embed=embed)
            await ctx.respond(localization.get("TESTWELCOME_SENT", member_mention=member.mention), ephemeral=True, delete_after=60)
        except discord.Forbidden:
            await ctx.respond(localization.get("TESTWELCOME_NO_DM"), ephemeral=True)
        except Exception as e:
            await ctx.respond(localization.get("TESTWELCOME_ERROR", error_message=str(e)), ephemeral=True)

        # Send warning to log channel if local file missing
        if missing_local:
            await self.send_log_warning(missing_local)

    async def log_message(self, message_key, **kwargs):
        """Unified logging method for both console and Discord channel"""
        config = load_config()
        
        # Create console-friendly version by replacing mentions with display names
        console_kwargs = kwargs.copy()
        for key, value in console_kwargs.items():
            if key.endswith('_mention') and hasattr(value, 'startswith') and value.startswith('<@'):
                # Extract user ID from mention and get display name
                user_id = value.strip('<@!>')
                try:
                    user = self.bot.get_user(int(user_id))
                    if user:
                        console_kwargs[key] = user.display_name
                    else:
                        console_kwargs[key] = f"User({user_id})"
                except (ValueError, AttributeError):
                    console_kwargs[key] = value
        
        # Log to console with display names
        console_message = localization.get(message_key, **console_kwargs)
        print(console_message)
        
        # Log to Discord channel with mentions (original format)
        log_channel_id = config.get("LOG_CHANNEL")
        if log_channel_id:
            log_channel = self.bot.get_channel(log_channel_id)
            if log_channel:
                discord_message = localization.get(message_key, **kwargs)
                await log_channel.send(discord_message)
            else:
                print(f"Warning: LOG_CHANNEL ID {log_channel_id} not found.")

    async def send_log_warning(self, missing_local):
        """Send warning about missing local image to the configured log channel"""
        await self.log_message("LOG_MISSING_IMAGE", path=missing_local)

    def create_welcome_embed(self, member):
        """Create the welcome embed using JSON configuration"""
        import json
        
        # Load welcome message configuration from JSON
        try:
            with open("src/languages/welcome_message.json", "r", encoding="utf-8") as f:
                welcome_config = json.load(f)
        except FileNotFoundError:
            print("Error: welcome_message.json not found!")
            return None, None, "src/languages/welcome_message.json"
        except json.JSONDecodeError as e:
            print(f"Error parsing welcome_message.json: {e}")
            return None, None, "src/languages/welcome_message.json"

        # Load config for trademark and other settings
        config = load_config()
        trademark_text = config.get("DISCORD_MESSAGE_TRADEMARK", "")

        # Prepare replacement values
        replacements = {
            "{guild_name}": member.guild.name,
            "{member_name}": member.display_name,
            "{member_mention}": member.mention,
            "{member_avatar}": member.avatar.url if member.avatar else member.default_avatar.url,
            "{bot_avatar}": self.bot.user.avatar.url if self.bot.user.avatar else None,
            "{member_count}": str(member.guild.member_count),
            "{trademark}": trademark_text
        }

        # Helper function to replace placeholders in strings
        def replace_placeholders(text):
            if isinstance(text, str):
                for placeholder, value in replacements.items():
                    if value is not None:
                        text = text.replace(placeholder, str(value))
            return text

        # Create embed with basic properties
        embed_kwargs = {}
        
        # Handle title
        if welcome_config.get("title"):
            embed_kwargs["title"] = replace_placeholders(welcome_config["title"])
        
        # Handle description
        if welcome_config.get("description"):
            embed_kwargs["description"] = replace_placeholders(welcome_config["description"])
        
        # Handle URL
        if welcome_config.get("url"):
            embed_kwargs["url"] = replace_placeholders(welcome_config["url"])
        
        # Handle color - use config fallback if not specified in welcome_message.json
        color_value = welcome_config.get("color")
        if color_value:
            # Color specified in welcome_message.json
            if isinstance(color_value, str) and color_value.startswith("#"):
                embed_kwargs["color"] = discord.Color(int(color_value[1:], 16))
            elif isinstance(color_value, int):
                embed_kwargs["color"] = discord.Color(color_value)
            else:
                embed_kwargs["color"] = discord.Color(0x00b0f4)  # Default blue
        else:
            # Use fallback color from config.json
            fallback_color = config.get("DISCORD_EMBED_COLOR", "00b0f4")
            if isinstance(fallback_color, str):
                # Remove # if present and convert to int
                fallback_color = fallback_color.lstrip("#")
                embed_kwargs["color"] = discord.Color(int(fallback_color, 16))
            else:
                embed_kwargs["color"] = discord.Color(0x00b0f4)  # Default blue
        
        # Handle timestamp
        if welcome_config.get("timestamp"):
            embed_kwargs["timestamp"] = discord.utils.utcnow()

        # Create the embed
        embed = discord.Embed(**embed_kwargs)

        # Handle author
        author_config = welcome_config.get("author")
        if author_config and author_config.get("name"):
            author_kwargs = {"name": replace_placeholders(author_config["name"])}
            if author_config.get("url"):
                author_kwargs["url"] = replace_placeholders(author_config["url"])
            if author_config.get("icon_url"):
                author_kwargs["icon_url"] = replace_placeholders(author_config["icon_url"])
            embed.set_author(**author_kwargs)

        # Handle fields
        fields = welcome_config.get("fields", [])
        for field in fields:
            if field.get("name") and field.get("value"):
                embed.add_field(
                    name=replace_placeholders(field["name"]),
                    value=replace_placeholders(field["value"]),
                    inline=field.get("inline", False)
                )

        # Handle thumbnail
        thumbnail_config = welcome_config.get("thumbnail")
        if thumbnail_config and thumbnail_config.get("url"):
            thumbnail_url = replace_placeholders(thumbnail_config["url"])
            if thumbnail_url and thumbnail_url != "None":
                embed.set_thumbnail(url=thumbnail_url)

        # Handle footer
        footer_config = welcome_config.get("footer")
        if footer_config and footer_config.get("text"):
            footer_kwargs = {"text": replace_placeholders(footer_config["text"])}
            if footer_config.get("icon_url"):
                icon_url = replace_placeholders(footer_config["icon_url"])
                if icon_url and icon_url != "None":
                    footer_kwargs["icon_url"] = icon_url
            embed.set_footer(**footer_kwargs)

        # Handle image (hybrid: URL or local file)
        file = None
        missing_local = None
        image_config = welcome_config.get("image")
        if image_config and image_config.get("url"):
            image_path = replace_placeholders(image_config["url"])
            if image_path.startswith("http://") or image_path.startswith("https://"):
                embed.set_image(url=image_path)
            else:
                # Use absolute path for file checking
                local_path = os.path.join(os.getcwd(), "src", "resources", "images", image_path)
                print(f"Looking for image at: {local_path}")  # Debug print
                if os.path.isfile(local_path):
                    # Get file extension for proper attachment name
                    file_ext = os.path.splitext(image_path)[1] or ".png"
                    attachment_name = f"welcome_banner{file_ext}"
                    file = discord.File(local_path, filename=attachment_name)
                    embed.set_image(url=f"attachment://{attachment_name}")
                    print(f"Image file found and attached: {attachment_name}")  # Debug print
                else:
                    missing_local = local_path
                    print(f"Image file not found at: {local_path}")  # Debug print

        return embed, file, missing_local

    @test_welcome.error
    async def test_welcome_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(localization.get("MISSING_PERMISSIONS"))
        elif isinstance(error, commands.BadArgument):
            await ctx.send(localization.get("BAD_ARGUMENT"))

def setup(bot):
    bot.add_cog(WelcomeMessage(bot))
