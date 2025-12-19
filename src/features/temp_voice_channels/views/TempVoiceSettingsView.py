import discord
from discord import ui
from typing import Optional
from config import constants


class NameModal(ui.Modal, title="Change Channel Name"):
    """Modal to change the channel name."""
    name = discord.ui.InputText(
        label="Channel Name",
        placeholder="Enter new channel name",
        required=True,
        max_length=100,
        min_length=1
    )

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__()
        self.channel = channel
        self.owner_id = owner_id
        self.name.default = channel.name

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can change the name!", ephemeral=True)
            return

        try:
            await self.channel.edit(name=self.name.value)
            await interaction.response.send_message(f"✅ Channel name changed to: **{self.name.value}**", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


class LimitModal(ui.Modal, title="Change User Limit"):
    """Modal to change the user limit."""
    limit = discord.ui.InputText(
        label="User Limit (0 for unlimited)",
        placeholder="Enter user limit (0-99)",
        required=True,
        max_length=2
    )

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__()
        self.channel = channel
        self.owner_id = owner_id
        self.limit.default = str(channel.user_limit)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can change the limit!", ephemeral=True)
            return

        try:
            limit_value = int(self.limit.value)
            if limit_value < 0 or limit_value > constants.TEMP_VOICE_MAX_LIMIT:
                await interaction.response.send_message(f"❌ Limit must be between 0 and {constants.TEMP_VOICE_MAX_LIMIT}!", ephemeral=True)
                return

            await self.channel.edit(user_limit=limit_value)
            limit_text = "unlimited" if limit_value == 0 else str(limit_value)
            await interaction.response.send_message(f"✅ User limit set to: **{limit_text}**", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid limit value!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


class BitrateModal(ui.Modal, title="Change Bitrate"):
    """Modal to change the bitrate."""
    bitrate = discord.ui.InputText(
        label="Bitrate (in kbps)",
        placeholder=f"Enter bitrate ({constants.TEMP_VOICE_MIN_BITRATE // 1000}-{constants.TEMP_VOICE_MAX_BITRATE // 1000} kbps)",
        required=True,
        max_length=3
    )

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__()
        self.channel = channel
        self.owner_id = owner_id
        self.bitrate.default = str(channel.bitrate // 1000)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can change the bitrate!", ephemeral=True)
            return

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

            await self.channel.edit(bitrate=bitrate_bps)
            await interaction.response.send_message(f"✅ Bitrate set to: **{bitrate_kbps} kbps**", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid bitrate value!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


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
    async def name_button(self, interaction: discord.Interaction, button: ui.Button):
        """Change channel name."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can change settings!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        await interaction.response.send_modal(NameModal(channel, self.owner_id))

    @ui.button(label="👥 Limit", style=discord.ButtonStyle.secondary, row=0)
    async def limit_button(self, interaction: discord.Interaction, button: ui.Button):
        """Change user limit."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can change settings!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        await interaction.response.send_modal(LimitModal(channel, self.owner_id))

    @ui.button(label="🎵 Bitrate", style=discord.ButtonStyle.secondary, row=0)
    async def bitrate_button(self, interaction: discord.Interaction, button: ui.Button):
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
    async def region_button(self, interaction: discord.Interaction, button: ui.Button):
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
    async def nsfw_button(self, interaction: discord.Interaction, button: ui.Button):
        """Toggle NSFW status."""
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
            await interaction.response.send_message(f"✅ NSFW status **{status}**!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
