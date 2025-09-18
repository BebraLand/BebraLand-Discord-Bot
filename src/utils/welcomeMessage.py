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


    @commands.command(name='testwelcome')
    @commands.has_permissions(administrator=True)
    async def test_welcome(self, ctx, member: discord.Member = None):
        """Test the welcome message - Admin only"""
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
            await ctx.send(localization.get("TESTWELCOME_SENT", member_mention=member.mention))
        except discord.Forbidden:
            await ctx.send(localization.get("TESTWELCOME_NO_DM"))
        except Exception as e:
            await ctx.send(localization.get("TESTWELCOME_ERROR", error_message=str(e)))

        # Send warning to log channel if local file missing
        if missing_local:
            await self.send_log_warning(missing_local)

    async def log_message(self, message_key, **kwargs):
        """Unified logging method for both console and Discord channel"""
        config = load_config()
        log_message = localization.get(message_key, **kwargs)
        
        # Always log to console
        print(log_message)
        
        # Also try to log to Discord channel if configured
        log_channel_id = config.get("LOG_CHANNEL")
        if log_channel_id:
            log_channel = self.bot.get_channel(log_channel_id)
            if log_channel:
                await log_channel.send(log_message)
            else:
                print(f"Warning: LOG_CHANNEL ID {log_channel_id} not found.")

    async def send_log_warning(self, missing_local):
        """Send warning about missing local image to the configured log channel"""
        await self.log_message("LOG_MISSING_IMAGE", path=missing_local)

    def create_welcome_embed(self, member):
        """Create the welcome embed with hybrid image support (local or URL)"""
        config = load_config()

        embed_color = int(config.get("DISCORD_EMBED_COLOR", "16"), 16)
        trademark_text = config.get("DISCORD_MESSAGE_TRADEMARK", "")
        image_path = config.get("DISCORD_WELCOME_BANNER", "")

        # Embed content from localization
        title = localization.get("WELCOME_TITLE", guild_name=member.guild.name, member_name=member.name)
        description = localization.get("WELCOME_DESCRIPTION")
        getting_started = localization.get("WELCOME_GETTING_STARTED")
        tips = localization.get("WELCOME_TIPS")

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color(embed_color)
        )

        # Fields
        embed.add_field(name=localization.get("GettingStarted"), value=getting_started, inline=False)
        embed.add_field(name=localization.get("Tips"), value=tips, inline=False)

        # Footer with bot avatar
        embed.set_footer(
            text=trademark_text,
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )

        # Hybrid image: URL or local file
        file = None
        missing_local = None
        if image_path.startswith("http://") or image_path.startswith("https://"):
            embed.set_image(url=image_path)
        else:
            local_path = os.path.join("src/resources/images", image_path)
            if os.path.isfile(local_path):
                file = discord.File(local_path, filename="welcome_banner.jpg")
                embed.set_image(url="attachment://welcome_banner.jpg")
            else:
                missing_local = local_path

        return embed, file, missing_local

    @test_welcome.error
    async def test_welcome_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(localization.get("MISSING_PERMISSIONS"))
        elif isinstance(error, commands.BadArgument):
            await ctx.send(localization.get("BAD_ARGUMENT"))

def setup(bot):
    bot.add_cog(WelcomeMessage(bot))
