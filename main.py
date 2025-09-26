import discord
from discord.ext import commands
from src.utils.config_manager import load_config
from src.utils.exceptions import map_discord_exception
from src.utils.error_helpers import setup_error_logger, handle_command_error
from src.utils.embed_helpers import setup_error_embed_builder
from src.utils.localization_helper import LocalizationHelper
from src.utils.localization import LocalizationManager
import os
import logging
from dotenv import load_dotenv

load_dotenv()
config = load_config()
intents = discord.Intents.all()
bot = commands.Bot(
    command_prefix=config.get("DISCORD_PREFIX", "&"),
    intents=intents
)

# Attach shared objects to bot for global access in cogs
bot.config = config  # make config accessible as bot.config
bot.localization = LocalizationManager()  # provide a LocalizationManager instance for cogs expecting bot.localization

# Setup error handling components
logger = setup_error_logger(bot)
localization = LocalizationHelper()
setup_error_embed_builder(bot)


@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")
    print(f"🏰 Bot is in {len(bot.guilds)} guilds:")
    for guild in bot.guilds:
        print(f"  - {guild.name} ({guild.id}) with {guild.member_count} members")
    
    print(f"📱 Bot has {len(bot.private_channels)} private channels cached:")
    for channel in bot.private_channels:
        if isinstance(channel, discord.DMChannel):
            print(f"  - DM with {channel.recipient} ({channel.recipient.id})")
        else:
            print(f"  - {type(channel).__name__}: {channel}")
    
    print(f"👤 Bot user: {bot.user} ({bot.user.id})")

@bot.event
async def on_message(message):
    """Log all messages for debugging"""
    if isinstance(message.channel, discord.DMChannel):
        print(f"📩 DM received from {message.author} ({message.author.id}): {message.content[:50]}...")
    elif isinstance(message.channel, discord.TextChannel):
        print(f"💬 Guild message in #{message.channel.name} from {message.author}: {message.content[:50]}...")
    
    # Process commands
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    """Log when members join"""
    print(f"👋 Member joined {member.guild.name}: {member} ({member.id})")

@bot.event
async def on_member_remove(member):
    """Log when members leave"""
    print(f"👋 Member left {member.guild.name}: {member} ({member.id})")

@bot.event
async def on_guild_join(guild):
    """Log when bot joins a guild"""
    print(f"🏰 Bot joined guild: {guild.name} ({guild.id}) with {guild.member_count} members")

@bot.event
async def on_guild_remove(guild):
    """Log when bot leaves a guild"""
    print(f"🏰 Bot left guild: {guild.name} ({guild.id})")


@bot.event
async def on_application_command_error(ctx: discord.ApplicationContext, error: discord.DiscordException):
    """Global error handler for application commands (slash commands)"""
    await handle_command_error(ctx, error)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    """Global error handler for text commands"""
    await handle_command_error(ctx, error)


# Load extensions before running the bot
bot.load_extension('src.utils.welcomeMessage')
bot.load_extension('src.commands.setWelcomeMessage')
bot.load_extension('src.commands.sendMessage')
bot.load_extension('src.commands.sendNews')
bot.load_extension('src.commands.sendTwitchNotificationMessage')
bot.load_extension('src.commands.sendLanguageSelector')
bot.load_extension('src.commands.twitchMonitor')
bot.load_extension('src.commands.clearDMadmin')
bot.load_extension('src.commands.tempVoice')

if config.get("CLEAR_DM_COMMAND_ENABLED", False):
    bot.load_extension('src.commands.clearDM')


@bot.slash_command(name="hello", description="Say hello to the bot")
async def hello(ctx):
    print(f"👋 Hello command used by {ctx.author} in {ctx.guild.name if ctx.guild else 'DM'}")
    await ctx.respond("Hey!")


@bot.slash_command(name="sync", description="Sync application commands (admin only)", default_member_permissions=discord.Permissions(administrator=True), contexts={discord.InteractionContextType.guild})
async def sync(ctx):
    if ctx.author.id != 568834033430036525:  # your Discord ID
        return await ctx.respond("You are not allowed to use this.", ephemeral=True)
    print(f"🔄 Sync command used by {ctx.author}")
    await ctx.respond("Working", ephemeral=True)
    await bot.sync_commands()
    await ctx.send("✅ Commands synced!")


bot.run(os.getenv('DISCORD_BOT_TOKEN'))
