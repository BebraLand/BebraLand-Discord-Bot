import discord
import json
import config.constants as constants
from src.languages.localize import translate
from src.utils.get_embed_icon import get_embed_icon

class NewsModal(discord.ui.Modal):
    def __init__(self, title: str, user_lang: str):
        super().__init__(title=title)
        self.news_contents = {}
        self.embed_json = None
        self.user_lang = user_lang
        # English (required)
        self.add_item(
            discord.ui.InputText(
                label=translate("English content", user_lang),
                placeholder=translate("Enter the news text in English (required)", user_lang),
                style=discord.InputTextStyle.long,
                required=True,
                max_length=getattr(constants, "NEWS_CHARACTER_LIMIT", 2000),
            )
        )
        # Russian (optional)
        self.add_item(
            discord.ui.InputText(
                label=translate("Russian content", user_lang),
                placeholder=translate("Enter the news text in Russian (optional)", user_lang),
                style=discord.InputTextStyle.long,
                required=False,
                max_length=getattr(constants, "NEWS_CHARACTER_LIMIT", 2000),
            )
        )
        # Lithuanian (optional)
        self.add_item(
            discord.ui.InputText(
                label=translate("Lithuanian content", user_lang),
                placeholder=translate("Enter the news text in Lithuanian (optional)", user_lang),
                style=discord.InputTextStyle.long,
                required=False,
                max_length=getattr(constants, "NEWS_CHARACTER_LIMIT", 2000),
            )
        )

    async def callback(self, interaction: discord.Interaction):
        # Collect values from inputs in order: EN, RU, LT
        try:
            en_val = (self.children[0].value or "").strip()
            ru_val = (self.children[1].value or "").strip()
            lt_val = (self.children[2].value or "").strip()
        except Exception:
            en_val = ""
            ru_val = ""
            lt_val = ""

        # If EN looks like a JSON object, try to parse it as an embed definition
        try:
            trimmed = en_val.strip()
            if trimmed.startswith("{") and trimmed.endswith("}"):
                parsed = json.loads(trimmed)
                if isinstance(parsed, dict):
                    self.embed_json = parsed
        except Exception:
            self.embed_json = None

        # If EN provided an embed JSON, use its description as EN fallback text
        if self.embed_json:
            desc_text = ""
            try:
                if isinstance(self.embed_json.get("description"), str):
                    desc_text = self.embed_json.get("description")
            except Exception:
                desc_text = ""
            self.news_contents["en"] = desc_text
        else:
            if en_val:
                self.news_contents["en"] = en_val

        # Parse RU and LT inputs as JSON if they look like JSON objects; otherwise
        # store as plain text. This ensures scheduled payload preserves dicts
        # rather than JSON strings.
        try:
            if ru_val and ru_val.strip().startswith("{") and ru_val.strip().endswith("}"):
                parsed_ru = json.loads(ru_val.strip())
                if isinstance(parsed_ru, dict):
                    self.news_contents["ru"] = parsed_ru
                else:
                    self.news_contents["ru"] = ru_val
            else:
                if ru_val:
                    self.news_contents["ru"] = ru_val
        except Exception:
            self.news_contents["ru"] = ru_val

        try:
            if lt_val and lt_val.strip().startswith("{") and lt_val.strip().endswith("}"):
                parsed_lt = json.loads(lt_val.strip())
                if isinstance(parsed_lt, dict):
                    self.news_contents["lt"] = parsed_lt
                else:
                    self.news_contents["lt"] = lt_val
            else:
                if lt_val:
                    self.news_contents["lt"] = lt_val
        except Exception:
            self.news_contents["lt"] = lt_val
        # Send a richer status embed instead of plain text
        try:
            bot_user = getattr(interaction.client, "user", None)
            bot_avatar = ""
            if bot_user:
                bot_avatar = bot_user.avatar.url if bot_user.avatar else bot_user.default_avatar.url

            locales = [loc for loc in ("en", "ru", "lt") if self.news_contents.get(loc)]
            mode = "JSON embed" if isinstance(self.embed_json, dict) else "Plain text"

            embed = discord.Embed(color=constants.DISCORD_EMBED_COLOR)
            embed.title = translate("News processing", self.user_lang)
            embed.description = (
                translate("Preparing your news for delivery...", self.user_lang) + "\n" +
                translate("We'll send it shortly and report a summary.", self.user_lang)
            embed.add_field(name=translate("Mode", self.user_lang), value=mode, inline=True)
            embed.add_field(
                name=translate("Locales captured", self.user_lang),
                value=", ".join(locales) if locales else "None",
                inline=True,
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=getattr(constants, "ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY", 0),
            )
        except Exception:
            # Fallback to previous behavior if embed fails
            await interaction.response.send_message(
                translate("News processing", self.user_lang),
                ephemeral=True,
            )
        self.stop()