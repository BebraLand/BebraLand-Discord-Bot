import discord
from src.utils.database import set_language
import src.languages.lang_constants as lang_constants
import config.constants as constants


def build_language_selector_embed(ctx: discord.ApplicationContext) -> discord.Embed:
    embed = discord.Embed(
      title=":earth_africa:Language Selection / Выбор языка / Kalbos pasirinkimas",
      description=(
        f"**{lang_constants.ENGLISH}**: Please select your preferred language from the dropdown below. "
        "This will be used for all bot interactions.\n\n"
        f"**{lang_constants.RUSSIAN}**: Пожалуйста, выберите предпочитаемый язык из выпадающего списка ниже. "
        "Он будет использоваться для всех взаимодействий с ботом.\n\n"
        f"**{lang_constants.LITHUANIAN}**: Prašome pasirinkti pageidaujamą kalbą iš žemiau esančio sąrašo. "
        "Ji bus naudojama visoms bot sąveikoms."
      ),
      color=constants.DISCORD_EMBED_COLOR,
    )

    embed.add_field(name=lang_constants.US_FLAG + " " + lang_constants.ENGLISH, value="Select for English interface", inline=True)
    embed.add_field(name=lang_constants.RU_FLAG + " " + lang_constants.RUSSIAN, value="Выберите для русского интерфейса", inline=True)
    embed.add_field(name=lang_constants.LT_FLAG + " " + lang_constants.LITHUANIAN, value="Pasirinkite lietuvių kalbai", inline=True)

    embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=ctx.bot.user.display_avatar.url)
    return embed

def build_selected_language_embed(interaction: discord.Interaction, lang: str) -> discord.Embed:
    embed = discord.Embed(
      title=f"Language set to **{lang}**!",
      color=constants.DISCORD_EMBED_COLOR,
    )
    
    embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=interaction.client.user.display_avatar.url)
    return embed

class LanguageSelector(discord.ui.View):
    @discord.ui.select(
        placeholder="Select your language / Выберите язык / Pasirinkite kalbą",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label=lang_constants.ENGLISH, emoji=lang_constants.US_FLAG, description="Set language to English"),
            discord.SelectOption(label=lang_constants.RUSSIAN, emoji=lang_constants.RU_FLAG, description="Установить язык на русский"),
            discord.SelectOption(label=lang_constants.LITHUANIAN, emoji=lang_constants.LT_FLAG, description="Nustatyti kalba į lietuvių"),
        ],
    )
    async def select_callback(self, select, interaction):
        lang = select.values[0]
        await set_language(interaction.user.id, lang)
        await interaction.response.send_message(
            ephemeral=True,
            delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            embed=build_selected_language_embed(interaction, lang)
        )