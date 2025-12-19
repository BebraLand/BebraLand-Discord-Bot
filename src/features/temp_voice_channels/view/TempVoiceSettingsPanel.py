"""
Settings panel view for temporary voice channels.
Provides name, user limit, bitrate, region, and NSFW settings.
"""
import discord
from typing import Optional
from src.utils.logger import get_cool_logger
from src.utils.database import get_db
from src.utils.get_embed_icon import get_embed_icon
import config.constants as constants
from src.languages import lang_constants as lang_constants

logger = get_cool_logger(__name__)

# Conversion factor for bitrate (kbps to bps)
BITRATE_CONVERSION_FACTOR = 1000


class ChannelNameModal(discord.ui.Modal):
    """Modal for changing channel name."""
    
    def __init__(self, channel_id: int, owner_id: int):
        super().__init__(title="Change Channel Name")
        self.channel_id = channel_id
        self.owner_id = owner_id
        
        self.name_input = discord.ui.InputText(
            label="Channel Name",
            placeholder="Enter new channel name",
            max_length=100,
            required=True
        )
        self.add_item(self.name_input)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Only the channel owner can use this!",
                ephemeral=True
            )
            return
        
        new_name = self.name_input.value
        
        try:
            channel = interaction.guild.get_channel(self.channel_id)
            if not channel or not isinstance(channel, discord.VoiceChannel):
                await interaction.response.send_message(
                    f"{lang_constants.ERROR_EMOJI} Channel not found!",
                    ephemeral=True
                )
                return
            
            await channel.edit(name=new_name)
            
            embed = discord.Embed(
                title=f"{lang_constants.SUCCESS_EMOJI} Channel Name Updated",
                description=f"Channel name changed to: **{new_name}**",
                color=constants.SUCCESS_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(f"Channel {self.channel_id} renamed to '{new_name}'")
            
        except discord.Forbidden:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Missing permissions to edit channel!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error changing channel name: {e}")
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Failed to change channel name.",
                ephemeral=True
            )


class UserLimitModal(discord.ui.Modal):
    """Modal for changing user limit."""
    
    def __init__(self, channel_id: int, owner_id: int):
        super().__init__(title="Change User Limit")
        self.channel_id = channel_id
        self.owner_id = owner_id
        
        self.limit_input = discord.ui.InputText(
            label="User Limit (0 = unlimited)",
            placeholder=f"Enter number (0-{constants.TEMP_VOICE_MAX_USER_LIMIT})",
            max_length=2,
            required=True
        )
        self.add_item(self.limit_input)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Only the channel owner can use this!",
                ephemeral=True
            )
            return
        
        try:
            limit = int(self.limit_input.value)
            
            if limit < 0 or limit > constants.TEMP_VOICE_MAX_USER_LIMIT:
                await interaction.response.send_message(
                    f"{lang_constants.ERROR_EMOJI} User limit must be between 0 and {constants.TEMP_VOICE_MAX_USER_LIMIT}!",
                    ephemeral=True
                )
                return
            
            channel = interaction.guild.get_channel(self.channel_id)
            if not channel or not isinstance(channel, discord.VoiceChannel):
                await interaction.response.send_message(
                    f"{lang_constants.ERROR_EMOJI} Channel not found!",
                    ephemeral=True
                )
                return
            
            await channel.edit(user_limit=limit)
            
            limit_text = "unlimited" if limit == 0 else str(limit)
            embed = discord.Embed(
                title=f"{lang_constants.SUCCESS_EMOJI} User Limit Updated",
                description=f"User limit set to: **{limit_text}**",
                color=constants.SUCCESS_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(f"Channel {self.channel_id} user limit set to {limit}")
            
        except ValueError:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Please enter a valid number!",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Missing permissions to edit channel!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error changing user limit: {e}")
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Failed to change user limit.",
                ephemeral=True
            )


class BitrateModal(discord.ui.Modal):
    """Modal for changing bitrate."""
    
    def __init__(self, channel_id: int, owner_id: int):
        super().__init__(title="Change Bitrate")
        self.channel_id = channel_id
        self.owner_id = owner_id
        
        self.bitrate_input = discord.ui.InputText(
            label="Bitrate (kbps)",
            placeholder=f"Enter bitrate (8-{constants.TEMP_VOICE_MAX_BITRATE // BITRATE_CONVERSION_FACTOR})",
            max_length=3,
            required=True
        )
        self.add_item(self.bitrate_input)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Only the channel owner can use this!",
                ephemeral=True
            )
            return
        
        try:
            bitrate_kbps = int(self.bitrate_input.value)
            bitrate = bitrate_kbps * BITRATE_CONVERSION_FACTOR  # Convert to bps
            
            max_bitrate = min(constants.TEMP_VOICE_MAX_BITRATE, interaction.guild.bitrate_limit)
            
            if bitrate < 8000 or bitrate > max_bitrate:
                await interaction.response.send_message(
                    f"{lang_constants.ERROR_EMOJI} Bitrate must be between 8 and {max_bitrate // BITRATE_CONVERSION_FACTOR} kbps!",
                    ephemeral=True
                )
                return
            
            channel = interaction.guild.get_channel(self.channel_id)
            if not channel or not isinstance(channel, discord.VoiceChannel):
                await interaction.response.send_message(
                    f"{lang_constants.ERROR_EMOJI} Channel not found!",
                    ephemeral=True
                )
                return
            
            await channel.edit(bitrate=bitrate)
            
            embed = discord.Embed(
                title=f"{lang_constants.SUCCESS_EMOJI} Bitrate Updated",
                description=f"Bitrate set to: **{bitrate_kbps} kbps**",
                color=constants.SUCCESS_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(f"Channel {self.channel_id} bitrate set to {bitrate}")
            
        except ValueError:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Please enter a valid number!",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Missing permissions to edit channel!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error changing bitrate: {e}")
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Failed to change bitrate.",
                ephemeral=True
            )


class RegionSelect(discord.ui.Select):
    """Select menu for changing voice region."""
    
    def __init__(self, channel_id: int, owner_id: int):
        options = [
            discord.SelectOption(label="Automatic", value="auto", description="Let Discord choose the best region"),
            discord.SelectOption(label="US West", value="us-west", emoji="🇺🇸"),
            discord.SelectOption(label="US East", value="us-east", emoji="🇺🇸"),
            discord.SelectOption(label="US Central", value="us-central", emoji="🇺🇸"),
            discord.SelectOption(label="US South", value="us-south", emoji="🇺🇸"),
            discord.SelectOption(label="Europe", value="europe", emoji="🇪🇺"),
            discord.SelectOption(label="Russia", value="russia", emoji="🇷🇺"),
            discord.SelectOption(label="Singapore", value="singapore", emoji="🇸🇬"),
            discord.SelectOption(label="Japan", value="japan", emoji="🇯🇵"),
            discord.SelectOption(label="Brazil", value="brazil", emoji="🇧🇷"),
            discord.SelectOption(label="Hong Kong", value="hongkong", emoji="🇭🇰"),
            discord.SelectOption(label="Sydney", value="sydney", emoji="🇦🇺"),
            discord.SelectOption(label="South Africa", value="southafrica", emoji="🇿🇦"),
            discord.SelectOption(label="India", value="india", emoji="🇮🇳"),
        ]
        
        super().__init__(
            placeholder="Select a voice region",
            options=options,
            custom_id=f"region_select_{channel_id}"
        )
        self.channel_id = channel_id
        self.owner_id = owner_id
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Only the channel owner can use this!",
                ephemeral=True
            )
            return
        
        region_value = self.values[0]
        rtc_region = None if region_value == "auto" else region_value
        
        try:
            channel = interaction.guild.get_channel(self.channel_id)
            if not channel or not isinstance(channel, discord.VoiceChannel):
                await interaction.response.send_message(
                    f"{lang_constants.ERROR_EMOJI} Channel not found!",
                    ephemeral=True
                )
                return
            
            await channel.edit(rtc_region=rtc_region)
            
            region_text = "Automatic" if rtc_region is None else region_value.title()
            embed = discord.Embed(
                title=f"{lang_constants.SUCCESS_EMOJI} Region Updated",
                description=f"Voice region set to: **{region_text}**",
                color=constants.SUCCESS_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(f"Channel {self.channel_id} region set to {region_text}")
            
        except discord.Forbidden:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Missing permissions to edit channel!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error changing region: {e}")
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Failed to change region.",
                ephemeral=True
            )


class TempVoiceSettingsPanel(discord.ui.View):
    """Settings panel for temporary voice channels."""
    
    def __init__(self, channel_id: int, owner_id: int):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.owner_id = owner_id
        
        # Set custom IDs for persistence
        self.name_button.custom_id = f"temp_voice_name_{channel_id}"
        self.limit_button.custom_id = f"temp_voice_limit_{channel_id}"
        self.bitrate_button.custom_id = f"temp_voice_bitrate_{channel_id}"
        self.nsfw_button.custom_id = f"temp_voice_nsfw_{channel_id}"
        
        # Conditionally add region button
        if constants.TEMP_VOICE_REGION_ENABLED:
            self.region_button.custom_id = f"temp_voice_region_{channel_id}"
        else:
            self.remove_item(self.region_button)
    
    async def _check_owner(self, interaction: discord.Interaction) -> bool:
        """Check if the user is the channel owner."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Only the channel owner can use this!",
                ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="Name", style=discord.ButtonStyle.secondary, emoji="✏️", row=0)
    async def name_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        
        modal = ChannelNameModal(self.channel_id, self.owner_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="User Limit", style=discord.ButtonStyle.secondary, emoji="👥", row=0)
    async def limit_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        
        modal = UserLimitModal(self.channel_id, self.owner_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Bitrate", style=discord.ButtonStyle.secondary, emoji="🎵", row=0)
    async def bitrate_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        
        modal = BitrateModal(self.channel_id, self.owner_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Region", style=discord.ButtonStyle.secondary, emoji="🌍", row=1)
    async def region_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        
        # Send ephemeral message with region select
        view = discord.ui.View(timeout=60)
        view.add_item(RegionSelect(self.channel_id, self.owner_id))
        
        await interaction.response.send_message(
            "Select a voice region:",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="Toggle NSFW", style=discord.ButtonStyle.secondary, emoji="🔞", row=1)
    async def nsfw_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        
        try:
            channel = interaction.guild.get_channel(self.channel_id)
            if not channel or not isinstance(channel, discord.VoiceChannel):
                await interaction.response.send_message(
                    f"{lang_constants.ERROR_EMOJI} Channel not found!",
                    ephemeral=True
                )
                return
            
            new_nsfw = not channel.nsfw
            await channel.edit(nsfw=new_nsfw)
            
            status = "enabled" if new_nsfw else "disabled"
            embed = discord.Embed(
                title=f"{lang_constants.SUCCESS_EMOJI} NSFW {status.title()}",
                description=f"Channel NSFW mode is now **{status}**.",
                color=constants.SUCCESS_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(f"Channel {self.channel_id} NSFW set to {new_nsfw}")
            
        except discord.Forbidden:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Missing permissions to edit channel!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error toggling NSFW: {e}")
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Failed to toggle NSFW.",
                ephemeral=True
            )


def build_settings_panel_embed(owner: discord.Member, channel: discord.VoiceChannel) -> discord.Embed:
    """Build the embed for the settings panel."""
    description_parts = [
        f"**Owner:** {owner.mention}\n**Channel:** {channel.mention}\n",
        "✏️ **Name** - Change channel name",
        "👥 **User Limit** - Set max users (0 = unlimited)",
        "🎵 **Bitrate** - Adjust audio quality",
    ]
    
    if constants.TEMP_VOICE_REGION_ENABLED:
        description_parts.append("🌍 **Region** - Select voice region")
    
    description_parts.append("🔞 **Toggle NSFW** - Enable/disable NSFW mode")
    
    embed = discord.Embed(
        title="⚙️ Voice Channel Settings",
        description="\n".join(description_parts),
        color=constants.DISCORD_EMBED_COLOR
    )
    embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK)
    return embed
