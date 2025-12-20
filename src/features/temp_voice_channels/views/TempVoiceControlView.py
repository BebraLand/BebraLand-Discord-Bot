import discord
from discord import ui
from typing import Optional
from src.utils.database import get_db
from src.utils.logger import get_cool_logger
from src.utils.get_embed_icon import get_embed_icon
import config.constants as constants

from .selectors.PermitMentionableSelect import PermitMentionableSelect as PermitView
from .selectors.RejectMentionableSelect import RejectMentionableSelect as RejectView
from .selectors.InviteUserSelect import InviteUserSelect as InviteView
from .selectors.KickUserSelect import KickUserSelect as KickView
from .selectors.TransferUserSelect import TransferUserSelect as TransferView

logger = get_cool_logger(__name__)

class TempVoiceControlView(ui.View):
    """Control panel for temporary voice channels."""
    
    def __init__(self, channel_id: int, owner_id: int):
        super().__init__(timeout=None)  # Persistent view
        self.channel_id = channel_id
        self.owner_id = owner_id
        self.custom_id = f"temp_voice_control:{channel_id}"

    async def _get_channel(self, interaction: discord.Interaction) -> Optional[discord.VoiceChannel]:
        """Get the voice channel."""
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            await interaction.response.send_message("❌ Channel not found!", ephemeral=True)
            return None
        return channel

    async def _get_current_owner_id(self) -> int:
        """Get the current owner ID from the database."""
        try:
            storage = await get_db()
            temp_vc = await storage.get_temp_voice_channel(self.channel_id)
            if temp_vc:
                current_owner = temp_vc.get("owner_id")
                logger.debug(f"Channel {self.channel_id} current owner from DB: {current_owner}")
                return current_owner
            logger.warning(f"Channel {self.channel_id} not found in database, using fallback owner_id: {self.owner_id}")
            return self.owner_id  # Fallback to stored owner_id
        except Exception as e:
            logger.error(f"Error getting current owner ID for channel {self.channel_id}: {e}")
            return self.owner_id

    @ui.button(label="🔒 Lock", style=discord.ButtonStyle.secondary, custom_id="lock")
    async def lock_button(self, button: ui.Button, interaction: discord.Interaction):
        """Lock the channel - DEFAULT_USER_ROLE_ID can see but not connect."""
        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            await interaction.response.send_message("❌ Only the channel owner can lock the channel!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        try:
            # Handle DEFAULT_USER_ROLE_ID (can be int or list)
            default_role_ids = constants.DEFAULT_USER_ROLE_ID if isinstance(constants.DEFAULT_USER_ROLE_ID, list) else [constants.DEFAULT_USER_ROLE_ID]
            for role_id in default_role_ids:
                default_role = interaction.guild.get_role(role_id)
                if default_role:
                    # Get current permissions to preserve view_channel state
                    current_perms = channel.overwrites_for(default_role)
                    view_channel = current_perms.view_channel if current_perms.view_channel is not None else True
                    # Explicitly set all three permissions to prevent Discord from resetting them
                    await channel.set_permissions(default_role, view_channel=view_channel, connect=False, speak=True)
            await interaction.response.send_message("🔒 Channel locked! Users can see but not connect.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

    @ui.button(label="🔓 Unlock", style=discord.ButtonStyle.secondary, custom_id="unlock")
    async def unlock_button(self, button: ui.Button, interaction: discord.Interaction):
        """Unlock the channel - DEFAULT_USER_ROLE_ID can see and connect."""
        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            await interaction.response.send_message("❌ Only the channel owner can unlock the channel!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        try:
            # Handle DEFAULT_USER_ROLE_ID (can be int or list)
            default_role_ids = constants.DEFAULT_USER_ROLE_ID if isinstance(constants.DEFAULT_USER_ROLE_ID, list) else [constants.DEFAULT_USER_ROLE_ID]
            for role_id in default_role_ids:
                default_role = interaction.guild.get_role(role_id)
                if default_role:
                    # Get current permissions to preserve view_channel state
                    current_perms = channel.overwrites_for(default_role)
                    view_channel = current_perms.view_channel if current_perms.view_channel is not None else True
                    # Explicitly set all three permissions to prevent Discord from resetting them
                    await channel.set_permissions(default_role, view_channel=view_channel, connect=True, speak=True)
            await interaction.response.send_message("🔓 Channel unlocked! Users can connect.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

    @ui.button(label="✅ Permit", style=discord.ButtonStyle.success, custom_id="permit")
    async def permit_button(self, button: ui.Button, interaction: discord.Interaction):
        """Permit a user or role to join the channel."""
        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            await interaction.response.send_message("❌ Only the channel owner can permit users!", ephemeral=True)
            return
            
        channel = await self._get_channel(interaction)
        if not channel:
            return

        message = "Select users to permit:" if not constants.TEMP_VOICE_PERMIT_ROLES_ENABLED else "Select users/roles to permit:"
        select = PermitView(channel, current_owner_id)
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message(message, view=view, ephemeral=True)

    @ui.button(label="❌ Reject", style=discord.ButtonStyle.danger, custom_id="reject")
    async def reject_button(self, button: ui.Button, interaction: discord.Interaction):
        """Reject a user or role from joining the channel."""
        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            await interaction.response.send_message("❌ Only the channel owner can reject users!", ephemeral=True)
            return
            
        channel = await self._get_channel(interaction)
        if not channel:
            return

        message = "Select users to reject:" if not constants.TEMP_VOICE_REJECT_ROLES_ENABLED else "Select users/roles to reject:"
        select = RejectView(channel, current_owner_id)
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message(message, view=view, ephemeral=True)

    @ui.button(label="📨 Invite", style=discord.ButtonStyle.primary, custom_id="invite", row=1)
    async def invite_button(self, button: ui.Button, interaction: discord.Interaction):
        """Invite a user to the channel via DM."""
        if not constants.TEMP_VOICE_INVITE_ENABLED:
            await interaction.response.send_message("❌ Invite feature is disabled!", ephemeral=True)
            return

        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            await interaction.response.send_message("❌ Only the channel owner can invite users!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        # Show user select
        select = InviteView(channel, current_owner_id)
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message("Select a user to invite:", view=view, ephemeral=True)

    @ui.button(label="🦵 Kick", style=discord.ButtonStyle.danger, custom_id="kick", row=1)
    async def kick_button(self, button: ui.Button, interaction: discord.Interaction):
        """Kick a user from the channel."""
        if not constants.TEMP_VOICE_KICK_ENABLED:
            await interaction.response.send_message("❌ Kick feature is disabled!", ephemeral=True)
            return

        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            await interaction.response.send_message("❌ Only the channel owner can kick users!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        # Show user select
        select = KickView(channel, current_owner_id)
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message("Select a user to kick:", view=view, ephemeral=True)

    @ui.button(label="👻 Ghost", style=discord.ButtonStyle.secondary, custom_id="ghost", row=1)
    async def ghost_button(self, button: ui.Button, interaction: discord.Interaction):
        """Make the channel invisible."""
        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            await interaction.response.send_message("❌ Only the channel owner can ghost the channel!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        try:
            # Handle DEFAULT_USER_ROLE_ID (can be int or list)
            default_role_ids = constants.DEFAULT_USER_ROLE_ID if isinstance(constants.DEFAULT_USER_ROLE_ID, list) else [constants.DEFAULT_USER_ROLE_ID]
            for role_id in default_role_ids:
                default_role = interaction.guild.get_role(role_id)
                if default_role:
                    # Get current permissions to preserve connect state
                    current_perms = channel.overwrites_for(default_role)
                    connect = current_perms.connect if current_perms.connect is not None else True
                    # Explicitly set all three permissions to prevent Discord from resetting them
                    await channel.set_permissions(default_role, view_channel=False, connect=connect, speak=True)
            await interaction.response.send_message("👻 Channel is now invisible!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

    @ui.button(label="👁️ Unghost", style=discord.ButtonStyle.secondary, custom_id="unghost", row=1)
    async def unghost_button(self, button: ui.Button, interaction: discord.Interaction):
        """Make the channel visible."""
        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            await interaction.response.send_message("❌ Only the channel owner can unghost the channel!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        try:
            # Handle DEFAULT_USER_ROLE_ID (can be int or list)
            default_role_ids = constants.DEFAULT_USER_ROLE_ID if isinstance(constants.DEFAULT_USER_ROLE_ID, list) else [constants.DEFAULT_USER_ROLE_ID]
            for role_id in default_role_ids:
                default_role = interaction.guild.get_role(role_id)
                if default_role:
                    # Get current permissions to preserve connect state
                    current_perms = channel.overwrites_for(default_role)
                    connect = current_perms.connect if current_perms.connect is not None else True
                    # Explicitly set all three permissions to prevent Discord from resetting them
                    await channel.set_permissions(default_role, view_channel=True, connect=connect, speak=True)
            await interaction.response.send_message("👁️ Channel is now visible!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

    @ui.button(label="🔄 Transfer", style=discord.ButtonStyle.secondary, custom_id="transfer", row=1)
    async def transfer_button(self, button: ui.Button, interaction: discord.Interaction):
        """Transfer ownership to another user."""
        channel = await self._get_channel(interaction)
        if not channel:
            return
        
        # Get current owner ID from database
        current_owner_id = await self._get_current_owner_id()
        
        # Get current owner member object
        current_owner = interaction.guild.get_member(current_owner_id)
        if not current_owner:
            await interaction.response.send_message("❌ Current owner not found!", ephemeral=True)
            return

        select = TransferView(channel, current_owner_id, current_owner)
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message("Select a user to transfer ownership to:", view=view, ephemeral=True)

    @ui.button(label="⚙️ Settings", style=discord.ButtonStyle.primary, custom_id="settings", row=2)
    async def settings_button(self, button: ui.Button, interaction: discord.Interaction):
        """Open channel settings."""
        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            await interaction.response.send_message("❌ Only the channel owner can access settings!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        # Import here to avoid circular imports
        from .settings.TempVoiceSettingsView import TempVoiceSettingsView
        
        embed = discord.Embed(
            title="⚙️ Channel Settings",
            description="Configure your voice channel settings below.",
            color=constants.DISCORD_EMBED_COLOR
        )
        embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction.guild.me))
        
        settings_view = TempVoiceSettingsView(self.channel_id, current_owner_id)
        settings_view.update_nsfw_button_style(channel)
        
        await interaction.response.send_message(
            embed=embed,
            view=settings_view,
            ephemeral=True
        )
        logger.info(f"User {interaction.user.id} opened settings for channel {self.channel_id}")
