import discord

import config.constants as constants
from src.languages import lang_constants as lang_constants
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


def build_twitch_panel_embed(ctx: discord.ApplicationContext = None) -> discord.Embed:
    embed = discord.Embed(
        title="Twitch Notifications",
        description=f"{lang_constants.BELL_EMOJI} **Subscribe** to get notified when our streamers go live!\n {lang_constants.MUTED_BELL_EMOJI} **Unsubscribe** to stop receiving Twitch notifications.\n\nYou can change your preference at any time.",
        color=constants.TWITCH_EMBED_COLOR,
    )

    embed.set_footer(
        text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(ctx)
    )
    return embed


class TwitchPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        custom_id="subscribe_button",
        label="Subscribe",
        style=discord.ButtonStyle.success,
        emoji=lang_constants.BELL_EMOJI,
    )
    async def subscribe_button_callback(self, button, interaction):
        """Handle subscribe action - gives user the ping role."""
        await interaction.response.defer(ephemeral=True)

        try:
            # Get the ping role
            ping_role = interaction.guild.get_role(constants.TWITCH_PING_ROLE_ID)

            if not ping_role:
                embed = discord.Embed(
                    title="Configuration Error",
                    description="The Twitch notification role is not configured properly. Please contact an administrator.",
                    color=constants.FAILED_EMBED_COLOR,
                )
                embed.set_footer(
                    text=constants.DISCORD_MESSAGE_TRADEMARK,
                    icon_url=get_embed_icon(interaction),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Check if user already has the role
            if ping_role in interaction.user.roles:
                embed = discord.Embed(
                    title="Already Subscribed",
                    description=f"You are already subscribed to Twitch notifications! {lang_constants.BELL_EMOJI}",
                    color=constants.TWITCH_EMBED_COLOR,
                )
            else:
                # Give the user the ping role
                await interaction.user.add_roles(ping_role)
                embed = discord.Embed(
                    title=f"Successfully Subscribed! {lang_constants.BELL_EMOJI}",
                    description="You will now receive notifications when our streamers go live on Twitch!",
                    color=constants.SUCCESS_EMBED_COLOR,
                )
                logger.info(
                    f"User {interaction.user.name} ({interaction.user.id}) subscribed to Twitch notifications"
                )

            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction),
            )
            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )

        except discord.Forbidden:
            logger.error(
                f"Missing permissions to manage roles for user {interaction.user.id}"
            )
            embed = discord.Embed(
                title="Permission Error",
                description="I don't have permission to manage roles. Please contact an administrator.",
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in subscribe button callback: {e}")
            embed = discord.Embed(
                title="Error",
                description="An unexpected error occurred. Please try again later.",
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(
        custom_id="unsubscribe_button",
        label="Unsubscribe",
        style=discord.ButtonStyle.danger,
        emoji=lang_constants.MUTED_BELL_EMOJI,
    )
    async def unsubscribe_button_callback(self, button, interaction):
        """Handle unsubscribe action - removes the ping role from user."""
        await interaction.response.defer(ephemeral=True)

        try:
            # Get the ping role
            ping_role = interaction.guild.get_role(constants.TWITCH_PING_ROLE_ID)

            if not ping_role:
                embed = discord.Embed(
                    title="Configuration Error",
                    description="The Twitch notification role is not configured properly. Please contact an administrator.",
                    color=constants.FAILED_EMBED_COLOR,
                )
                embed.set_footer(
                    text=constants.DISCORD_MESSAGE_TRADEMARK,
                    icon_url=get_embed_icon(interaction),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Check if user has the role
            if ping_role not in interaction.user.roles:
                embed = discord.Embed(
                    title="Not Subscribed",
                    description="You weren't subscribed to Twitch notifications.",
                    color=constants.TWITCH_EMBED_COLOR,
                )
            else:
                # Remove the ping role from user
                await interaction.user.remove_roles(ping_role)
                embed = discord.Embed(
                    title=f"Successfully Unsubscribed {lang_constants.MUTED_BELL_EMOJI}",
                    description="You will no longer receive Twitch live notifications.",
                    color=constants.SUCCESS_EMBED_COLOR,
                )
                logger.info(
                    f"User {interaction.user.name} ({interaction.user.id}) unsubscribed from Twitch notifications"
                )

            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction),
            )
            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )

        except discord.Forbidden:
            logger.error(
                f"Missing permissions to manage roles for user {interaction.user.id}"
            )
            embed = discord.Embed(
                title="Permission Error",
                description="I don't have permission to manage roles. Please contact an administrator.",
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in unsubscribe button callback: {e}")
            embed = discord.Embed(
                title="Error",
                description="An unexpected error occurred. Please try again later.",
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
