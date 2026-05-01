import discord
from discord import ui

import config.constants as constants
from src.features.temp_voice_channels.invite_user import invite_user_to_channel
from src.utils.database import get_language


class InviteUserSelect(ui.Select):
    """User select for inviting users to the channel."""

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(
            placeholder="Select a user to invite",
            min_values=1,
            max_values=1,
            select_type=discord.ComponentType.user_select,
        )
        self.channel = channel
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            return

        selected_user = self.values[0]
        current_lang = await get_language(interaction.user.id)

        # Use shared invite function
        success, embed = await invite_user_to_channel(
            inviter=interaction.user,
            target_user=selected_user,
            voice_channel=self.channel,
            inviter_lang=current_lang,
        )

        await interaction.response.edit_message(
            content=None,
            embed=embed,
            view=None,
            delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
        )
