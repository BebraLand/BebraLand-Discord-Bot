import discord
from discord.ext import commands
from src.utils.config_manager import load_config
import os
from dotenv import load_dotenv

load_dotenv()
config = load_config()
intents = discord.Intents.all()
bot = commands.Bot(
    command_prefix=config.get("DISCORD_PREFIX", "&"),
    intents=intents
)


@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")


# Load extensions before running the bot
bot.load_extension('src.utils.welcomeMessage')
bot.load_extension('src.commands.setWelcomeMessage')
bot.load_extension('src.commands.clearDMadmin')

if config.get("CLEAR_DM_COMMAND_ENABLED", False):
    bot.load_extension('src.commands.clearDM')


@bot.slash_command(name="hello", description="Say hello to the bot")
async def hello(ctx):
    await ctx.respond("Hey!")


@bot.slash_command(name="sync", description="Sync application commands (admin only)", default_member_permissions=discord.Permissions(administrator=True), contexts={discord.InteractionContextType.guild})
async def sync(ctx):
    if ctx.author.id != 568834033430036525:  # your Discord ID
        return await ctx.respond("You are not allowed to use this.", ephemeral=True)
    await ctx.respond("Working", ephemeral=True)
    await bot.sync_commands()
    await ctx.send("✅ Commands synced!")


bot.run(os.getenv('DISCORD_BOT_TOKEN'))
