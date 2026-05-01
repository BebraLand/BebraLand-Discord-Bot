from .BitrateModal import BitrateModal
from .LimitModal import LimitModal
from .NameModal import NameModal
from .RegionSelect import RegionSelect
import discord
from discord import ui
from typing import Optional
from config import constants
from src.utils.logger import get_cool_logger
import src.languages.lang_constants as lang_constants

logger = get_cool_logger(__name__)


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

        # Always add Name and Limit buttons
        name_btn = ui.Button(
            label=f"{lang_constants.PENCIL_EMOJI} Name",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        name_btn.callback = self.name_button_callback
        self.add_item(name_btn)

        limit_btn = ui.Button(
            label=f"{lang_constants.PEOPLE_EMOJI} Limit",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        limit_btn.callback = self.limit_button_callback
        self.add_item(limit_btn)

        # Conditionally add Bitrate button
        if constants.TEMP_VOICE_BITRATE_SETTINGS_ENABLED:
            bitrate_btn = ui.Button(
                label=f"{lang_constants.MUSIC_EMOJI} Bitrate",
                style=discord.ButtonStyle.secondary,
                row=0,
            )
            bitrate_btn.callback = self.bitrate_button_callback
            self.add_item(bitrate_btn)

        # Conditionally add Region button
        if constants.TEMP_VOICE_REGION_SETTINGS_ENABLED:
            region_btn = ui.Button(
                label=f"{lang_constants.GLOBE_EMOJI} Region",
                style=discord.ButtonStyle.secondary,
                row=1,
            )
            region_btn.callback = self.region_button_callback
            self.add_item(region_btn)

        # Conditionally add NSFW button
        if constants.TEMP_VOICE_NSFW_SETTINGS_ENABLED:
            nsfw_btn = ui.Button(
                label=f"{lang_constants.NSFW_EMOJI} NSFW",
                style=discord.ButtonStyle.danger,
                row=1,
            )
            nsfw_btn.callback = self.nsfw_button_callback
            self.add_item(nsfw_btn)

    def update_nsfw_button_style(self, channel: discord.VoiceChannel):
        """Update the NSFW button style based on the channel's current state."""
        # Find the NSFW button in the view's children
        for item in self.children:
            if (
                isinstance(item, ui.Button)
                and item.label == f"{lang_constants.NSFW_EMOJI} NSFW"
            ):
                item.style = (
                    discord.ButtonStyle.success
                    if channel.nsfw
                    else discord.ButtonStyle.danger
                )
                break

    async def _get_channel(
        self, interaction: discord.Interaction
    ) -> Optional[discord.VoiceChannel]:
        """Get the voice channel."""
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Channel not found!", ephemeral=True
            )
            return None
        return channel

    async def name_button_callback(self, interaction: discord.Interaction):
        """Change channel name."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Only the channel owner can change settings!",
                ephemeral=True,
            )
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        logger.info(
            f"User {interaction.user.id} is changing name for channel {channel.id}"
        )
        await interaction.response.send_modal(NameModal(channel, self.owner_id))

    async def limit_button_callback(self, interaction: discord.Interaction):
        """Change user limit."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Only the channel owner can change settings!",
                ephemeral=True,
            )
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        await interaction.response.send_modal(LimitModal(channel, self.owner_id))

    async def bitrate_button_callback(self, interaction: discord.Interaction):
        """Change bitrate."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Only the channel owner can change settings!",
                ephemeral=True,
            )
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        await interaction.response.send_modal(BitrateModal(channel, self.owner_id))

    async def region_button_callback(self, interaction: discord.Interaction):
        """Change region."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Only the channel owner can change settings!",
                ephemeral=True,
            )
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        await interaction.response.send_message(
            "Select a region:", view=RegionView(channel, self.owner_id), ephemeral=True
        )

    async def nsfw_button_callback(self, interaction: discord.Interaction):
        """Toggle NSFW status."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Only the channel owner can change settings!",
                ephemeral=True,
            )
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        try:
            new_nsfw = not channel.nsfw
            await channel.edit(nsfw=new_nsfw)

            # Update button style based on NSFW state
            # Find the button and update its style
            for item in self.children:
                if (
                    isinstance(item, ui.Button)
                    and item.label == f"{lang_constants.NSFW_EMOJI} NSFW"
                ):
                    item.style = (
                        discord.ButtonStyle.success
                        if new_nsfw
                        else discord.ButtonStyle.danger
                    )
                    break

            await interaction.response.edit_message(view=self)
            logger.info(
                f"User {interaction.user.id} toggled NSFW for channel {channel.id} to {new_nsfw}"
            )
        except Exception as e:
            logger.error(f"Error toggling NSFW: {e}")
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", ephemeral=True
            )
