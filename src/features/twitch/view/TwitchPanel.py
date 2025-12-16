import discord
from pycord.i18n import _
from src.utils.logger import get_cool_logger
import config.constants as constants
from src.utils.get_embed_icon import get_embed_icon
from src.utils.database import get_db

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
        style=discord.ButtonStyle.success,
        emoji="🔔"
    )
    async def subscribe_button_callback(self, button, interaction):
        """Handle subscribe action."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            storage = await get_db()
            user_id = str(interaction.user.id)
            
            # Check if already subscribed
            is_subscribed = await storage.is_subscribed_twitch(user_id)
            
            if is_subscribed:
                embed = discord.Embed(
                    title="Already Subscribed",
                    description="You are already subscribed to Twitch notifications! 🔔",
                    color=constants.TWITCH_EMBED_COLOR
                )
            else:
                # Subscribe the user
                success = await storage.subscribe_twitch(user_id)
                
                if success:
                    embed = discord.Embed(
                        title="Successfully Subscribed! 🔔",
                        description="You will now receive notifications when our streamers go live on Twitch!",
                        color=constants.SUCCESS_EMBED_COLOR
                    )
                    logger.info(f"User {user_id} subscribed to Twitch notifications")
                else:
                    embed = discord.Embed(
                        title="Subscription Failed",
                        description="There was an error subscribing you. Please try again later.",
                        color=constants.FAILED_EMBED_COLOR
                    )
            
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))
            await interaction.followup.send(embed=embed, ephemeral=True, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)
            
        except Exception as e:
            logger.error(f"Error in subscribe button callback: {e}")
            embed = discord.Embed(
                title="Error",
                description="An unexpected error occurred. Please try again later.",
                color=constants.FAILED_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))
            await interaction.followup.send(embed=embed, ephemeral=True)

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
            storage = await get_db()
            user_id = str(interaction.user.id)
            
            # Unsubscribe the user
            success = await storage.unsubscribe_twitch(user_id)
            
            if success:
                embed = discord.Embed(
                    title="Successfully Unsubscribed 🔕",
                    description="You will no longer receive Twitch live notifications.",
                    color=constants.SUCCESS_EMBED_COLOR
                )
                logger.info(f"User {user_id} unsubscribed from Twitch notifications")
            else:
                embed = discord.Embed(
                    title="Not Subscribed",
                    description="You weren't subscribed to Twitch notifications.",
                    color=constants.TWITCH_EMBED_COLOR
                )
            
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))
            await interaction.followup.send(embed=embed, ephemeral=True, delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY)
            
        except Exception as e:
            logger.error(f"Error in unsubscribe button callback: {e}")
            embed = discord.Embed(
                title="Error",
                description="An unexpected error occurred. Please try again later.",
                color=constants.FAILED_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))
            await interaction.followup.send(embed=embed, ephemeral=True)