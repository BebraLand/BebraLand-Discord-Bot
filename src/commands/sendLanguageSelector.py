import discord
from discord.ext import commands
import logging
import sys
import os

# Add the src directory to the path to import utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.config_manager import set_user_language, get_user_language, load_config
from utils.localization import LocalizationManager

class LanguageSelector(discord.ui.View):
	"""Persistent view for language selection dropdown"""
	
	def __init__(self):
		super().__init__(timeout=None)  # Persistent view
		self.localization = LocalizationManager()  # Initialize localization manager
		
	@discord.ui.select(
		placeholder="🌍 Select your language / Pasirinkite kalbą",
		min_values=1,
		max_values=1,
		custom_id="language_selector",
		options=[
			discord.SelectOption(
				label="English",
				value="en",
				description="Set language to English",
				emoji="🇺🇸"
			),
			discord.SelectOption(
				label="Lietuvių",
				value="lt", 
				description="Nustatyti kalbą į lietuvių",
				emoji="🇱🇹"
			)
		]
	)
	async def language_select(self, select: discord.ui.Select, interaction: discord.Interaction):
		"""Handle language selection"""
		try:
			selected_language = select.values[0]
			user_id = interaction.user.id
			
			# Save user's language preference
			set_user_language(user_id, selected_language)
			
			# Get localized response text
			response_text = self.localization.get("LANGUAGE_SELECTOR_SUCCESS", selected_language)
			
			# Create success embed
			embed = discord.Embed(
				title=self.localization.get("LANGUAGE_SELECTOR_UPDATED_TITLE", selected_language),
				description=response_text,
				color=int(load_config().get("DISCORD_EMBED_COLOR", "432F20"), 16)  # Using config color
			)
			embed.add_field(
				name=self.localization.get("LANGUAGE_SELECTOR_SELECTED_FIELD", selected_language),
				value=f"{'🇺🇸 English' if selected_language == 'en' else '🇱🇹 Lietuvių'}",
				inline=False
			)
			
			# Log the language change
			logging.info(f"User {interaction.user.name} ({user_id}) changed language to {selected_language}")
			
			# Respond to the interaction
			await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=10)
			
		except Exception as e:
			logging.error(f"Error in language selection: {e}")
			
			# Error response
			error_embed = discord.Embed(
				title=self.localization.get("LANGUAGE_SELECTOR_ERROR_TITLE", "en"),
				description=self.localization.get("LANGUAGE_SELECTOR_ERROR_DESCRIPTION", "en"),
				color=0xFF0000
			)
			
			try:
				await interaction.response.send_message(embed=error_embed, ephemeral=True)
			except:
				# If response already sent, use followup
				await interaction.followup.send(embed=error_embed, ephemeral=True)

class LanguageSelectorCog(commands.Cog):
	"""Cog for language selector command"""
	
	def __init__(self, bot):
		self.bot = bot
		self.localization = LocalizationManager()  # Initialize localization manager
	
	@commands.Cog.listener()
	async def on_ready(self):
		"""Add persistent view when bot is ready"""
		self.bot.add_view(LanguageSelector())
		logging.info("Language selector persistent view added")
		
	@discord.slash_command(
		name="send_language_selector",
		description="Send language selection message (Admin only)",
		default_member_permissions=discord.Permissions(administrator=True),
		contexts={discord.InteractionContextType.guild}
	)
	async def send_language_selector(self, ctx: discord.ApplicationContext):
		"""Send a persistent language selector message"""
		try:
			# Create the main embed
			embed = discord.Embed(
				title=self.localization.get("LANGUAGE_SELECTOR_TITLE", "en"),
				description=self.localization.get("LANGUAGE_SELECTOR_DESCRIPTION", "en"),
				color=int(load_config().get("DISCORD_EMBED_COLOR", "432F20"), 16) # Using config color
			)
			
			embed.add_field(
				name=self.localization.get("LANGUAGE_SELECTOR_ENGLISH_FIELD", "en"),
				value=self.localization.get("LANGUAGE_SELECTOR_ENGLISH_VALUE", "en"),
				inline=True
			)
			
			embed.add_field(
				name=self.localization.get("LANGUAGE_SELECTOR_LITHUANIAN_FIELD", "en"),
				value=self.localization.get("LANGUAGE_SELECTOR_LITHUANIAN_VALUE", "en"),
				inline=True
			)
			
			embed.set_footer(text=load_config().get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"))
			
			# Create the view with persistent dropdown
			view = LanguageSelector()
			
			# Send the message with the embed and view
			await ctx.respond("Done",ephemeral=True, delete_after=0)
			await ctx.channel.send(embed=embed, view=view)
			
			# Log the command usage
			logging.info(f"Language selector sent by {ctx.author.name} ({ctx.author.id}) in {ctx.guild.name}")
			
		except Exception as e:
			logging.error(f"Error sending language selector: {e}")
			
			# Error response
			error_embed = discord.Embed(
				title=self.localization.get("LANGUAGE_SELECTOR_ERROR_TITLE", "en"),
				description=self.localization.get("LANGUAGE_SELECTOR_SEND_ERROR", "en"),
				color=0xFF0000
			)
			
			try:
				await ctx.respond(embed=error_embed, ephemeral=True)
			except:
				await ctx.followup.send(embed=error_embed, ephemeral=True)

def setup(bot):
	"""Setup function to add the cog to the bot"""
	bot.add_cog(LanguageSelectorCog(bot))
	logging.info("Language selector cog loaded")