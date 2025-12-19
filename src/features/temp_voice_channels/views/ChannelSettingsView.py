import discord
from typing import Optional
import config.constants as constants
from src.utils.logger import get_cool_logger
from src.utils.database import get_db

logger = get_cool_logger(__name__)


def build_settings_embed(channel: discord.VoiceChannel) -> discord.Embed:
    """Build the settings embed for a temporary voice channel."""
    embed = discord.Embed(
        title="⚙️ Channel Settings",
        description=f"Current settings for **{channel.name}**",
        color=constants.DISCORD_EMBED_COLOR
    )
    
    embed.add_field(
        name="👥 User Limit",
        value=f"{channel.user_limit if channel.user_limit > 0 else 'Unlimited'}",
        inline=True
    )
    embed.add_field(
        name="🎵 Bitrate",
        value=f"{channel.bitrate // 1000} kbps",
        inline=True
    )
    embed.add_field(
        name="🔞 NSFW",
        value="Yes" if channel.nsfw else "No",
        inline=True
    )
    
    if constants.TEMP_VOICE_ENABLE_REGION_SETTING:
        embed.add_field(
            name="🌍 Region",
            value=channel.rtc_region or "Automatic",
            inline=True
        )
    
    embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK)
    return embed


def get_max_bitrate(guild: discord.Guild) -> int:
    """Get the maximum bitrate allowed based on server boost level."""
    # Base bitrate limits by boost tier
    bitrate_limits = {
        0: 96000,   # No boost
        1: 128000,  # Tier 1
        2: 256000,  # Tier 2
        3: 384000,  # Tier 3
    }
    
    tier = guild.premium_tier
    max_bitrate = bitrate_limits.get(tier, 96000)
    
    # Use the configured limit if it's lower
    if constants.TEMP_VOICE_MAX_BITRATE < max_bitrate:
        max_bitrate = constants.TEMP_VOICE_MAX_BITRATE
    
    return max_bitrate


class RenameChannelModal(discord.ui.Modal):
    """Modal for renaming the channel."""

    def __init__(self, channel_id: int):
        super().__init__(title="Rename Channel")
        self.channel_id = channel_id

        self.name_input = discord.ui.InputText(
            label="New Channel Name",
            placeholder="Enter the new channel name",
            max_length=100,
            required=True
        )
        self.add_item(self.name_input)

    async def callback(self, interaction: discord.Interaction):
        """Handle the modal submission."""
        new_name = self.name_input.value.strip()
        
        if not new_name:
            await interaction.response.send_message(
                "❌ Channel name cannot be empty.",
                ephemeral=True
            )
            return
        
        # Get the channel
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            await interaction.response.send_message(
                "❌ Channel not found.",
                ephemeral=True
            )
            return
        
        try:
            await channel.edit(name=new_name)
            
            # Update the control panel message
            db = await get_db()
            channel_data = await db.get_temp_voice_channel(self.channel_id)
            if channel_data and channel_data.get("control_message_id"):
                try:
                    # Try to fetch and update the message
                    async for message in channel.history(limit=50):
                        if message.id == channel_data["control_message_id"]:
                            owner = await interaction.guild.fetch_member(channel_data["owner_id"])
                            from .ControlPanelView import build_control_panel_embed, ControlPanelView
                            embed = build_control_panel_embed(new_name, owner)
                            await message.edit(embed=embed, view=ControlPanelView())
                            break
                except Exception as e:
                    logger.error(f"Failed to update control panel message: {e}")
            
            await interaction.response.send_message(
                f"✅ Channel renamed to **{new_name}**!",
                ephemeral=True
            )
            logger.info(f"User {interaction.user.id} renamed channel {self.channel_id} to '{new_name}'")
        except Exception as e:
            logger.error(f"Failed to rename channel {self.channel_id}: {e}")
            await interaction.response.send_message(
                "❌ Failed to rename the channel.",
                ephemeral=True
            )


class ChannelSettingsView(discord.ui.View):
    """Settings view for temporary voice channels."""

    def __init__(self, channel_id: int):
        super().__init__(timeout=300)  # 5 minute timeout for settings view
        self.channel_id = channel_id

    @discord.ui.button(label="Rename", emoji="✏️", style=discord.ButtonStyle.secondary)
    async def rename_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Rename the channel."""
        modal = RenameChannelModal(self.channel_id)
        await interaction.response.send_modal(modal)

    @discord.ui.select(
        placeholder="Set User Limit",
        options=[
            discord.SelectOption(label="No Limit", value="0", emoji="♾️"),
            discord.SelectOption(label="1 User", value="1"),
            discord.SelectOption(label="2 Users", value="2"),
            discord.SelectOption(label="3 Users", value="3"),
            discord.SelectOption(label="4 Users", value="4"),
            discord.SelectOption(label="5 Users", value="5"),
            discord.SelectOption(label="10 Users", value="10"),
            discord.SelectOption(label="15 Users", value="15"),
            discord.SelectOption(label="25 Users", value="25"),
            discord.SelectOption(label="50 Users", value="50"),
            discord.SelectOption(label="99 Users", value="99"),
        ]
    )
    async def user_limit_select(self, select: discord.ui.Select, interaction: discord.Interaction):
        """Set the user limit for the channel."""
        limit = int(select.values[0])
        
        # Get the channel
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            await interaction.response.send_message(
                "❌ Channel not found.",
                ephemeral=True
            )
            return
        
        try:
            await channel.edit(user_limit=limit)
            
            limit_text = "Unlimited" if limit == 0 else f"{limit} users"
            await interaction.response.send_message(
                f"✅ User limit set to **{limit_text}**!",
                ephemeral=True
            )
            logger.info(f"User {interaction.user.id} set user limit to {limit} for channel {self.channel_id}")
        except Exception as e:
            logger.error(f"Failed to set user limit for channel {self.channel_id}: {e}")
            await interaction.response.send_message(
                "❌ Failed to set user limit.",
                ephemeral=True
            )

    @discord.ui.select(
        placeholder="Set Bitrate",
        options=[
            discord.SelectOption(label="64 kbps", value="64000"),
            discord.SelectOption(label="96 kbps", value="96000"),
            discord.SelectOption(label="128 kbps", value="128000"),
            discord.SelectOption(label="256 kbps", value="256000"),
            discord.SelectOption(label="384 kbps", value="384000"),
        ]
    )
    async def bitrate_select(self, select: discord.ui.Select, interaction: discord.Interaction):
        """Set the bitrate for the channel."""
        bitrate = int(select.values[0])
        
        # Get the channel
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            await interaction.response.send_message(
                "❌ Channel not found.",
                ephemeral=True
            )
            return
        
        # Check if the server supports this bitrate
        max_bitrate = get_max_bitrate(interaction.guild)
        if bitrate > max_bitrate:
            await interaction.response.send_message(
                f"❌ Your server only supports up to {max_bitrate // 1000} kbps. Upgrade server boost level for higher bitrates!",
                ephemeral=True
            )
            return
        
        try:
            await channel.edit(bitrate=bitrate)
            
            await interaction.response.send_message(
                f"✅ Bitrate set to **{bitrate // 1000} kbps**!",
                ephemeral=True
            )
            logger.info(f"User {interaction.user.id} set bitrate to {bitrate} for channel {self.channel_id}")
        except Exception as e:
            logger.error(f"Failed to set bitrate for channel {self.channel_id}: {e}")
            await interaction.response.send_message(
                "❌ Failed to set bitrate.",
                ephemeral=True
            )

    @discord.ui.button(label="Toggle NSFW", emoji="🔞", style=discord.ButtonStyle.danger, row=2)
    async def nsfw_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Toggle NSFW status for the channel."""
        # Get the channel
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            await interaction.response.send_message(
                "❌ Channel not found.",
                ephemeral=True
            )
            return
        
        try:
            new_nsfw = not channel.nsfw
            await channel.edit(nsfw=new_nsfw)
            
            status = "enabled" if new_nsfw else "disabled"
            await interaction.response.send_message(
                f"{'🔞' if new_nsfw else '✅'} NSFW mode **{status}**!",
                ephemeral=True
            )
            logger.info(f"User {interaction.user.id} set NSFW to {new_nsfw} for channel {self.channel_id}")
        except Exception as e:
            logger.error(f"Failed to toggle NSFW for channel {self.channel_id}: {e}")
            await interaction.response.send_message(
                "❌ Failed to toggle NSFW.",
                ephemeral=True
            )
