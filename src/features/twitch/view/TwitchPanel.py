import discord
from pycord.i18n import _
from src.utils.logger import get_cool_logger
import config.constants as constants
from src.utils.get_embed_icon import get_embed_icon

logger = get_cool_logger(__name__)

def build_twitch_panel_embed(ctx: discord.ApplicationContext) -> discord.Embed:
    embed = discord.Embed(
        title="Twitch Notifications",
        description=f"🔔 **Subscribe** to get notified when our streamers go live!\n 🔕 **Unsubscribe** to stop receiving Twitch notifications.\n\nYou can change your preference at any time.",
        color=constants.TWITCH_EMBED_COLOR,
    )

    embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK,
                     icon_url=get_embed_icon(ctx))
    return embed

class TwitchPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        custom_id="subscribe_button",
        label="Subscribe",
        style=discord.ButtonStyle.primary,
        emoji="🔔"
    )
    async def subscribe_button_callback(self, button, interaction):
        # Handle subscribe action
        pass

    @discord.ui.button(
        custom_id="unsubscribe_button",
        label="Unsubscribe",
        style=discord.ButtonStyle.danger,
        emoji="🔕"
    )
    async def unsubscribe_button_callback(self, button, interaction):
        # Handle unsubscribe action
        pass