import discord
from typing import Optional
import config.constants as constants
from src.utils.logger import get_cool_logger
from src.utils.database import get_db

logger = get_cool_logger(__name__)


def build_control_panel_embed(channel_name: str, owner: discord.Member) -> discord.Embed:
    """Build the control panel embed for a temporary voice channel."""
    embed = discord.Embed(
        title=f"🎙️ {channel_name}",
        description=f"**Owner:** {owner.mention}\n\nUse the buttons below to manage your temporary voice channel.",
        color=constants.DISCORD_EMBED_COLOR
    )
    embed.add_field(
        name="🔒 Lock/Unlock",
        value="Control who can join your channel",
        inline=True
    )
    embed.add_field(
        name="👥 Permit/Reject",
        value="Manage user access",
        inline=True
    )
    embed.add_field(
        name="👻 Ghost/Unghost",
        value="Hide/show your channel",
        inline=True
    )
    if constants.TEMP_VOICE_ENABLE_INVITE_BUTTON:
        embed.add_field(
            name="📨 Invite",
            value="Send invite to a user",
            inline=True
        )
    embed.add_field(
        name="👑 Transfer",
        value="Transfer ownership",
        inline=True
    )
    if constants.TEMP_VOICE_ENABLE_SETTINGS_VIEW:
        embed.add_field(
            name="⚙️ Settings",
            value="Channel settings",
            inline=True
        )
    embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK)
    return embed


class ControlPanelView(discord.ui.View):
    """Control panel view for temporary voice channels."""

    def __init__(self):
        super().__init__(timeout=None)
        
        # Remove buttons based on feature flags using remove_item
        items_to_remove = []
        
        if not constants.TEMP_VOICE_ENABLE_INVITE_BUTTON:
            # Find and remove invite button
            for item in self.children:
                if hasattr(item, 'custom_id') and item.custom_id == "temp_voice_invite":
                    items_to_remove.append(item)
        
        if not constants.TEMP_VOICE_ENABLE_SETTINGS_VIEW:
            # Find and remove settings button
            for item in self.children:
                if hasattr(item, 'custom_id') and item.custom_id == "temp_voice_settings":
                    items_to_remove.append(item)
        
        # Remove all marked items
        for item in items_to_remove:
            self.remove_item(item)

    async def check_ownership(self, interaction: discord.Interaction, channel_id: int) -> bool:
        """Check if the user is the owner of the channel."""
        db = await get_db()
        channel_data = await db.get_temp_voice_channel(channel_id)
        
        if not channel_data:
            await interaction.response.send_message(
                "❌ This channel is not registered in the system.",
                ephemeral=True
            )
            return False
        
        if channel_data["owner_id"] != interaction.user.id:
            await interaction.response.send_message(
                "❌ Only the channel owner can use this button.",
                ephemeral=True
            )
            return False
        
        return True

    @discord.ui.button(label="Lock", emoji="🔒", style=discord.ButtonStyle.secondary, custom_id="temp_voice_lock")
    async def lock_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Lock the channel so default role can see but not connect."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You must be in the voice channel to use this.",
                ephemeral=True
            )
            return
        
        channel = interaction.user.voice.channel
        
        if not await self.check_ownership(interaction, channel.id):
            return
        
        try:
            # Get the default role
            default_role = interaction.guild.get_role(constants.DEFAULT_USER_ROLE_ID)
            if not default_role:
                await interaction.response.send_message(
                    "❌ Default role not found.",
                    ephemeral=True
                )
                return
            
            # Set permissions: can view but cannot connect
            await channel.set_permissions(
                default_role,
                view_channel=True,
                connect=False
            )
            
            await interaction.response.send_message(
                "🔒 Channel locked! Users can see it but cannot join unless permitted.",
                ephemeral=True
            )
            logger.info(f"User {interaction.user.id} locked channel {channel.id}")
        except Exception as e:
            logger.error(f"Failed to lock channel {channel.id}: {e}")
            await interaction.response.send_message(
                "❌ Failed to lock the channel.",
                ephemeral=True
            )

    @discord.ui.button(label="Unlock", emoji="🔓", style=discord.ButtonStyle.secondary, custom_id="temp_voice_unlock")
    async def unlock_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Unlock the channel so default role can see and connect."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You must be in the voice channel to use this.",
                ephemeral=True
            )
            return
        
        channel = interaction.user.voice.channel
        
        if not await self.check_ownership(interaction, channel.id):
            return
        
        try:
            # Get the default role
            default_role = interaction.guild.get_role(constants.DEFAULT_USER_ROLE_ID)
            if not default_role:
                await interaction.response.send_message(
                    "❌ Default role not found.",
                    ephemeral=True
                )
                return
            
            # Set permissions: can view and connect
            await channel.set_permissions(
                default_role,
                view_channel=True,
                connect=True
            )
            
            await interaction.response.send_message(
                "🔓 Channel unlocked! Users can now join.",
                ephemeral=True
            )
            logger.info(f"User {interaction.user.id} unlocked channel {channel.id}")
        except Exception as e:
            logger.error(f"Failed to unlock channel {channel.id}: {e}")
            await interaction.response.send_message(
                "❌ Failed to unlock the channel.",
                ephemeral=True
            )

    @discord.ui.button(label="Permit", emoji="✅", style=discord.ButtonStyle.success, custom_id="temp_voice_permit")
    async def permit_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Permit a user to join the locked channel."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You must be in the voice channel to use this.",
                ephemeral=True
            )
            return
        
        channel = interaction.user.voice.channel
        
        if not await self.check_ownership(interaction, channel.id):
            return
        
        # Import here to avoid circular imports
        from .PermitUserModal import PermitUserModal
        
        modal = PermitUserModal(channel.id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Reject", emoji="❌", style=discord.ButtonStyle.danger, custom_id="temp_voice_reject")
    async def reject_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Reject a user from joining the channel."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You must be in the voice channel to use this.",
                ephemeral=True
            )
            return
        
        channel = interaction.user.voice.channel
        
        if not await self.check_ownership(interaction, channel.id):
            return
        
        # Import here to avoid circular imports
        from .RejectUserModal import RejectUserModal
        
        modal = RejectUserModal(channel.id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Ghost", emoji="👻", style=discord.ButtonStyle.secondary, custom_id="temp_voice_ghost", row=1)
    async def ghost_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Make the channel invisible to the default role."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You must be in the voice channel to use this.",
                ephemeral=True
            )
            return
        
        channel = interaction.user.voice.channel
        
        if not await self.check_ownership(interaction, channel.id):
            return
        
        try:
            # Get the default role
            default_role = interaction.guild.get_role(constants.DEFAULT_USER_ROLE_ID)
            if not default_role:
                await interaction.response.send_message(
                    "❌ Default role not found.",
                    ephemeral=True
                )
                return
            
            # Set permissions: cannot view channel
            await channel.set_permissions(
                default_role,
                view_channel=False
            )
            
            await interaction.response.send_message(
                "👻 Channel is now invisible!",
                ephemeral=True
            )
            logger.info(f"User {interaction.user.id} ghosted channel {channel.id}")
        except Exception as e:
            logger.error(f"Failed to ghost channel {channel.id}: {e}")
            await interaction.response.send_message(
                "❌ Failed to ghost the channel.",
                ephemeral=True
            )

    @discord.ui.button(label="Unghost", emoji="👁️", style=discord.ButtonStyle.secondary, custom_id="temp_voice_unghost", row=1)
    async def unghost_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Make the channel visible to the default role."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You must be in the voice channel to use this.",
                ephemeral=True
            )
            return
        
        channel = interaction.user.voice.channel
        
        if not await self.check_ownership(interaction, channel.id):
            return
        
        try:
            # Get the default role
            default_role = interaction.guild.get_role(constants.DEFAULT_USER_ROLE_ID)
            if not default_role:
                await interaction.response.send_message(
                    "❌ Default role not found.",
                    ephemeral=True
                )
                return
            
            # Set permissions: can view and connect
            await channel.set_permissions(
                default_role,
                view_channel=True,
                connect=True
            )
            
            await interaction.response.send_message(
                "👁️ Channel is now visible!",
                ephemeral=True
            )
            logger.info(f"User {interaction.user.id} unghosted channel {channel.id}")
        except Exception as e:
            logger.error(f"Failed to unghost channel {channel.id}: {e}")
            await interaction.response.send_message(
                "❌ Failed to unghost the channel.",
                ephemeral=True
            )

    @discord.ui.button(label="Invite", emoji="📨", style=discord.ButtonStyle.primary, custom_id="temp_voice_invite", row=1)
    async def invite_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Send an invite to a user via DM."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You must be in the voice channel to use this.",
                ephemeral=True
            )
            return
        
        channel = interaction.user.voice.channel
        
        if not await self.check_ownership(interaction, channel.id):
            return
        
        # Import here to avoid circular imports
        from .InviteUserModal import InviteUserModal
        
        modal = InviteUserModal(channel.id, channel.name)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Transfer", emoji="👑", style=discord.ButtonStyle.secondary, custom_id="temp_voice_transfer", row=1)
    async def transfer_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Transfer ownership of the channel."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You must be in the voice channel to use this.",
                ephemeral=True
            )
            return
        
        channel = interaction.user.voice.channel
        
        if not await self.check_ownership(interaction, channel.id):
            return
        
        # Import here to avoid circular imports
        from .TransferOwnershipModal import TransferOwnershipModal
        
        modal = TransferOwnershipModal(channel.id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Settings", emoji="⚙️", style=discord.ButtonStyle.secondary, custom_id="temp_voice_settings", row=1)
    async def settings_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Open channel settings view."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You must be in the voice channel to use this.",
                ephemeral=True
            )
            return
        
        channel = interaction.user.voice.channel
        
        if not await self.check_ownership(interaction, channel.id):
            return
        
        # Import here to avoid circular imports
        from .ChannelSettingsView import ChannelSettingsView, build_settings_embed
        
        embed = build_settings_embed(channel)
        await interaction.response.send_message(
            embed=embed,
            view=ChannelSettingsView(channel.id),
            ephemeral=True
        )
