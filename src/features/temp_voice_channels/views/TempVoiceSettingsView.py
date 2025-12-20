import discord
from discord import ui
from typing import Optional
import traceback
from config import constants
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


class NameModal(ui.Modal):
    """Modal to change the channel name."""

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(title="Change Channel Name")
        self.channel = channel
        self.owner_id = owner_id
        
        self.name = ui.InputText(
            label="Channel Name",
            placeholder="Enter new channel name",
            required=True,
            max_length=100,
            min_length=1,
            value=channel.name
        )
        self.add_item(self.name)

    async def on_submit(self, interaction: discord.Interaction):
        logger.info(f"User {interaction.user.id} submitted name change modal for channel {self.channel.id}")
        try:
            logger.info(f"User {interaction.user.id} changing channel {self.channel.id} name to '{self.name.value}'")
            await self.channel.edit(name=self.name.value)
            await interaction.response.send_message(f"✅ Channel name changed to: **{self.name.value}**", ephemeral=True)
        except Exception as e:
            logger.error(f"Error changing channel name: {e}")
            logger.error(traceback.format_exc())
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
            except:
                pass

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Modal error for user {interaction.user.id}: {error}")
        logger.error(traceback.format_exc())
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ An error occurred: {str(error)}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ An error occurred: {str(error)}", ephemeral=True)
        except:
            pass


class LimitModal(ui.Modal):
    """Modal to change the user limit."""

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(title="Change User Limit")
        self.channel = channel
        self.owner_id = owner_id
        
        self.limit = ui.InputText(
            label="User Limit (0 for unlimited)",
            placeholder="Enter user limit (0-99)",
            required=True,
            max_length=2,
            value=str(channel.user_limit)
        )
        self.add_item(self.limit)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit_value = int(self.limit.value)
            if limit_value < 0 or limit_value > constants.TEMP_VOICE_MAX_LIMIT:
                await interaction.response.send_message(f"❌ Limit must be between 0 and {constants.TEMP_VOICE_MAX_LIMIT}!", ephemeral=True)
                return

            logger.info(f"User {interaction.user.id} changing channel {self.channel.id} limit to {limit_value}")
            await self.channel.edit(user_limit=limit_value)
            limit_text = "unlimited" if limit_value == 0 else str(limit_value)
            await interaction.response.send_message(f"✅ User limit set to: **{limit_text}**", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid limit value!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error changing channel limit: {e}")
            logger.error(traceback.format_exc())
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
            except:
                pass

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Limit modal error for user {interaction.user.id}: {error}")
        logger.error(traceback.format_exc())
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ An error occurred: {str(error)}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ An error occurred: {str(error)}", ephemeral=True)
        except:
            pass


class BitrateModal(ui.Modal):
    """Modal to change the bitrate."""

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(title="Change Bitrate")
        self.channel = channel
        self.owner_id = owner_id
        
        self.bitrate = ui.InputText(
            label="Bitrate (in kbps)",
            placeholder=f"Enter bitrate ({constants.TEMP_VOICE_MIN_BITRATE // 1000}-{constants.TEMP_VOICE_MAX_BITRATE // 1000} kbps)",
            required=True,
            max_length=3,
            value=str(channel.bitrate // 1000)
        )
        self.add_item(self.bitrate)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bitrate_kbps = int(self.bitrate.value)
            bitrate_bps = bitrate_kbps * 1000

            # Get max bitrate based on server boost level
            guild = interaction.guild
            max_bitrate = constants.TEMP_VOICE_MAX_BITRATE
            
            if guild.premium_tier >= 3:
                max_bitrate = 384000
            elif guild.premium_tier == 2:
                max_bitrate = 256000
            elif guild.premium_tier == 1:
                max_bitrate = 128000

            if bitrate_bps < constants.TEMP_VOICE_MIN_BITRATE or bitrate_bps > max_bitrate:
                await interaction.response.send_message(
                    f"❌ Bitrate must be between {constants.TEMP_VOICE_MIN_BITRATE // 1000} and {max_bitrate // 1000} kbps!",
                    ephemeral=True
                )
                return

            logger.info(f"User {interaction.user.id} changing channel {self.channel.id} bitrate to {bitrate_kbps} kbps")
            await self.channel.edit(bitrate=bitrate_bps)
            await interaction.response.send_message(f"✅ Bitrate set to: **{bitrate_kbps} kbps**", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid bitrate value!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error changing channel bitrate: {e}")
            logger.error(traceback.format_exc())
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
            except:
                pass

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Bitrate modal error for user {interaction.user.id}: {error}")
        logger.error(traceback.format_exc())
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ An error occurred: {str(error)}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ An error occurred: {str(error)}", ephemeral=True)
        except:
            pass


class RegionSelect(ui.Select):
    """Select menu for region."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        self.channel = channel
        self.owner_id = owner_id
        
        options = [
            discord.SelectOption(label="Automatic", value="auto", description="Let Discord choose the best region", emoji="🌐"),
            discord.SelectOption(label="US West", value="us-west", description="US West Coast", emoji="🇺🇸"),
            discord.SelectOption(label="US East", value="us-east", description="US East Coast", emoji="🇺🇸"),
            discord.SelectOption(label="US Central", value="us-central", description="US Central", emoji="🇺🇸"),
            discord.SelectOption(label="US South", value="us-south", description="US South", emoji="🇺🇸"),
            discord.SelectOption(label="Europe", value="europe", description="Europe", emoji="🇪🇺"),
            discord.SelectOption(label="Singapore", value="singapore", description="Singapore", emoji="🇸🇬"),
            discord.SelectOption(label="Russia", value="russia", description="Russia", emoji="🇷🇺"),
            discord.SelectOption(label="Japan", value="japan", description="Japan", emoji="🇯🇵"),
            discord.SelectOption(label="Brazil", value="brazil", description="Brazil", emoji="🇧🇷"),
            discord.SelectOption(label="Hong Kong", value="hongkong", description="Hong Kong", emoji="🇭🇰"),
            discord.SelectOption(label="Sydney", value="sydney", description="Sydney", emoji="🇦🇺"),
            discord.SelectOption(label="South Africa", value="southafrica", description="South Africa", emoji="🇿🇦"),
            discord.SelectOption(label="India", value="india", description="India", emoji="🇮🇳"),
        ]
        
        super().__init__(placeholder="Select a region", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can change the region!", ephemeral=True)
            return

        try:
            region_value = None if self.values[0] == "auto" else self.values[0]
            await self.channel.edit(rtc_region=region_value)
            region_name = "Automatic" if region_value is None else self.values[0]
            await interaction.response.send_message(f"✅ Region set to: **{region_name}**", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


class RegionView(ui.View):
    """View for region selection."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(timeout=300)
        self.add_item(RegionSelect(channel, owner_id))


class TempVoiceSettingsView(ui.View):
    """Settings panel for temporary voice channels."""
    
    def __init__(self, channel_id: int, owner_id: int):
        super().__init__(timeout=300)
        self.channel_id = channel_id
        self.owner_id = owner_id

    async def _get_channel(self, interaction: discord.Interaction) -> Optional[discord.VoiceChannel]:
        """Get the voice channel."""
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            await interaction.response.send_message("❌ Channel not found!", ephemeral=True)
            return None
        return channel

    @ui.button(label="✏️ Name", style=discord.ButtonStyle.secondary, row=0)
    async def name_button(self, button: ui.Button, interaction: discord.Interaction):
        """Change channel name."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can change settings!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        logger.info(f"User {interaction.user.id} is changing name for channel {channel.id}")
        await interaction.response.send_modal(NameModal(channel, self.owner_id))

    @ui.button(label="👥 Limit", style=discord.ButtonStyle.secondary, row=0)
    async def limit_button(self, button: ui.Button, interaction: discord.Interaction):
        """Change user limit."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can change settings!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        await interaction.response.send_modal(LimitModal(channel, self.owner_id))

    @ui.button(label="🎵 Bitrate", style=discord.ButtonStyle.secondary, row=0)
    async def bitrate_button(self, button: ui.Button, interaction: discord.Interaction):
        """Change bitrate."""
        if not constants.TEMP_VOICE_BITRATE_SETTINGS_ENABLED:
            await interaction.response.send_message("❌ Bitrate settings are disabled!", ephemeral=True)
            return

        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can change settings!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        await interaction.response.send_modal(BitrateModal(channel, self.owner_id))

    @ui.button(label="🌍 Region", style=discord.ButtonStyle.secondary, row=1)
    async def region_button(self, button: ui.Button, interaction: discord.Interaction):
        """Change region."""
        if not constants.TEMP_VOICE_REGION_SETTINGS_ENABLED:
            await interaction.response.send_message("❌ Region settings are disabled!", ephemeral=True)
            return

        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can change settings!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        await interaction.response.send_message("Select a region:", view=RegionView(channel, self.owner_id), ephemeral=True)

    @ui.button(label="🔞 NSFW", style=discord.ButtonStyle.danger, row=1)
    async def nsfw_button(self, button: ui.Button, interaction: discord.Interaction):
        """Toggle NSFW status."""
        if not constants.TEMP_VOICE_NSFW_SETTINGS_ENABLED:
            await interaction.response.send_message("❌ NSFW settings are disabled!", ephemeral=True)
            return
            
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can change settings!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        try:
            new_nsfw = not channel.nsfw
            await channel.edit(nsfw=new_nsfw)
            status = "enabled" if new_nsfw else "disabled"
            emoji = "🔴" if new_nsfw else "⚪"
            await interaction.response.send_message(f"{emoji} NSFW status **{status}**!", ephemeral=True)
            logger.info(f"User {interaction.user.id} toggled NSFW for channel {channel.id} to {new_nsfw}")
        except Exception as e:
            logger.error(f"Error toggling NSFW: {e}")
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
