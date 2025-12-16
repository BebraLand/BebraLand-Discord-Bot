import discord
from pycord.i18n import _
from src.utils.logger import get_cool_logger
import config.constants as constants
from src.utils.get_embed_icon import get_embed_icon
from src.storage.factory import get_storage

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
        """Handle subscribe action."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            storage = get_storage()
            user_id = str(interaction.user.id)
            
            # Check if already subscribed
            if await storage.is_subscribed(user_id):
                await interaction.followup.send(
                    "🔔 You are already subscribed to Twitch notifications!",
                    ephemeral=True
                )
                return
            
            # Subscribe the user
            success = await storage.subscribe_user(user_id)
            
            if success:
                await interaction.followup.send(
                    "✅ You have successfully subscribed to Twitch notifications! You'll be notified when streamers go live.",
                    ephemeral=True
                )
                logger.info(f"User {interaction.user} ({user_id}) subscribed to Twitch notifications")
            else:
                await interaction.followup.send(
                    "❌ Failed to subscribe. Please try again later.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error subscribing user {interaction.user.id}: {e}")
            await interaction.followup.send(
                "❌ An error occurred. Please try again later.",
                ephemeral=True
            )

    @discord.ui.button(
        custom_id="unsubscribe_button",
        label="Unsubscribe",
        style=discord.ButtonStyle.danger,
        emoji="🔕"
    )
    async def unsubscribe_button_callback(self, button, interaction):
        """Handle unsubscribe action."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            storage = get_storage()
            user_id = str(interaction.user.id)
            
            # Unsubscribe the user
            success = await storage.unsubscribe_user(user_id)
            
            if success:
                await interaction.followup.send(
                    "✅ You have successfully unsubscribed from Twitch notifications.",
                    ephemeral=True
                )
                logger.info(f"User {interaction.user} ({user_id}) unsubscribed from Twitch notifications")
            else:
                await interaction.followup.send(
                    "⚠️ You are not currently subscribed to Twitch notifications.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Error unsubscribing user {interaction.user.id}: {e}")
            await interaction.followup.send(
                "❌ An error occurred. Please try again later.",
                ephemeral=True
            )
