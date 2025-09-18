import discord
from discord.ext import commands
from src.utils.config_manager import load_config
from src.utils.localization import LocalizationManager
import os

localization = LocalizationManager(default_lang="en")

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
        except Exception:
            print(f"Could not send a welcome DM to {member.name}.")

        # Send warning to log channel if local file missing
        if missing_local:
            await self.send_log_warning(missing_local)

    @commands.command(name='testwelcome')
    @commands.has_permissions(administrator=True)
    async def test_welcome(self, ctx, member: discord.Member = None):
        """Test the welcome message - Admin only"""
        if member is None:
            member = ctx.author
        
        embed, file, missing_local = self.create_welcome_embed(member)
        
        try:
            if file:
                await ctx.author.send(embed=embed, file=file)
            else:
                await ctx.author.send(embed=embed)
            await ctx.send(f"✅ Test welcome message sent to your DMs for user: {member.display_name}")
        except discord.Forbidden:
            await ctx.send("❌ I couldn't send you a DM. Please check your privacy settings.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")

        # Send warning to log channel if local file missing
        if missing_local:
            await self.send_log_warning(missing_local)

    async def send_log_warning(self, missing_local):
        """Send warning about missing local image to the configured log channel"""
        config = load_config()
        log_channel_id = config.get("LOG_CHANNEL")
        if log_channel_id:
            log_channel = self.bot.get_channel(log_channel_id)
            if log_channel:
                await log_channel.send(f"⚠️ Warning: local image not found: `{missing_local}`")
            else:
                print(f"Warning: LOG_CHANNEL ID {log_channel_id} not found.")
        else:
            print(f"Warning: local image not found: {missing_local}")

    def create_welcome_embed(self, member):
        """Create the welcome embed with hybrid image support (local or URL)"""
        config = load_config()

        embed_color = int(config.get("DISCORD_EMBED_COLOR", "16"), 16)
        trademark_text = config.get("DISCORD_MESSAGE_TRADEMARK", "")
        image_path = config.get("DISCORD_WELCOME_BANNER", "")

        embed = discord.Embed(
            title=f"Welcome to **{member.guild.name}**, {member.name}!",
            description=(
                "We're super excited to have you here! 🎉\n\n"
                "Check out the channels, introduce yourself, "
                "and have fun!"
            ),
            color=discord.Color(embed_color)
        )

        # Fields
        embed.add_field(
            name="Getting Started",
            value="1️⃣ Read the rules in #rules\n"
                  "2️⃣ Say hi in #introductions\n"
                  "3️⃣ Enjoy your stay! 😎",
            inline=False
        )
        embed.add_field(
            name="Tips",
            value="React to the role messages to get your special roles!\n"
                  "Use /help to see all available commands.",
            inline=False
        )

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
            await ctx.send("❌ You need Administrator permissions to use this command.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Please mention a valid member or leave it blank to test with yourself.")

def setup(bot):
    bot.add_cog(WelcomeMessage(bot))
