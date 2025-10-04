import discord
from src.utils.database import set_language
import config.constants


class LanguageSelector(discord.ui.View):
    @discord.ui.select(
        placeholder="Choose a language!",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="English", emoji="🇬🇧"),
            discord.SelectOption(label="Русский", emoji="🇷🇺"),
            discord.SelectOption(label="Lietuvių", emoji="🇱🇹"),
        ],
    )
    async def select_callback(self, select, interaction):
        lang = select.values[0]
        await set_language(interaction.user.id, lang)
        await interaction.response.send_message(
            f"Language set to **{lang}**!",
            ephemeral=True,
            delete_after=config.constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
        )