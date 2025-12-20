import discord
from discord import ui
from typing import Optional
import time
from config import constants
from src.utils.database import get_db
from src.utils.logger import get_cool_logger
from src.utils.get_embed_icon import get_embed_icon

logger = get_cool_logger(__name__)


class PermitMentionableSelect(ui.Select):
    """Mentionable select for permitting users or roles to join the channel."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        # Use user_select if roles are disabled, otherwise use mentionable_select
        select_type = discord.ComponentType.user_select if not constants.TEMP_VOICE_PERMIT_ROLES_ENABLED else discord.ComponentType.mentionable_select
        placeholder = "Select users to permit" if not constants.TEMP_VOICE_PERMIT_ROLES_ENABLED else "Select users/roles to permit"
        super().__init__(placeholder=placeholder, min_values=1, max_values=10, select_type=select_type)
        self.channel = channel
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can permit users!", ephemeral=True)
            return

        try:
            storage = await get_db()
            temp_vc = await storage.get_temp_voice_channel(self.channel.id)
            permitted_items = []
            
            for item in self.values:
                if isinstance(item, (discord.Member, discord.User)):
                    # Permit user
                    await self.channel.set_permissions(item, connect=True, view_channel=True)
                    permitted_items.append(item.mention)
                    
                    # Store in database
                    if temp_vc:
                        permitted_users = temp_vc.get("permitted_users", [])
                        if item.id not in permitted_users:
                            permitted_users.append(item.id)
                            await storage.update_temp_voice_channel(self.channel.id, permitted_users=permitted_users)
                            
                elif isinstance(item, discord.Role):
                    # Permit role
                    await self.channel.set_permissions(item, connect=True, view_channel=True)
                    permitted_items.append(item.mention)
                    
                    # Store in database
                    if temp_vc:
                        permitted_roles = temp_vc.get("permitted_roles", [])
                        if item.id not in permitted_roles:
                            permitted_roles.append(item.id)
                            await storage.update_temp_voice_channel(self.channel.id, permitted_roles=permitted_roles)
            
            items_text = ", ".join(permitted_items)
            await interaction.response.send_message(f"✅ Permitted {items_text} to join the channel!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


class RejectMentionableSelect(ui.Select):
    """Mentionable select for rejecting users or roles from joining the channel."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        # Use user_select if roles are disabled, otherwise use mentionable_select
        select_type = discord.ComponentType.user_select if not constants.TEMP_VOICE_REJECT_ROLES_ENABLED else discord.ComponentType.mentionable_select
        placeholder = "Select users to reject" if not constants.TEMP_VOICE_REJECT_ROLES_ENABLED else "Select users/roles to reject"
        super().__init__(placeholder=placeholder, min_values=1, max_values=10, select_type=select_type)
        self.channel = channel
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can reject users!", ephemeral=True)
            return

        try:
            storage = await get_db()
            temp_vc = await storage.get_temp_voice_channel(self.channel.id)
            rejected_items = []
            
            for item in self.values:
                if isinstance(item, (discord.Member, discord.User)):
                    # Reject user
                    await self.channel.set_permissions(item, connect=False, view_channel=False)
                    rejected_items.append(item.mention)
                    
                    # # Disconnect if in channel
                    # if hasattr(item, 'voice') and item.voice and item.voice.channel == self.channel:
                    #     await item.move_to(None)
                    
                    # Store in database
                    if temp_vc:
                        rejected_users = temp_vc.get("rejected_users", [])
                        if item.id not in rejected_users:
                            rejected_users.append(item.id)
                            await storage.update_temp_voice_channel(self.channel.id, rejected_users=rejected_users)
                            
                elif isinstance(item, discord.Role):
                    # Reject role
                    await self.channel.set_permissions(item, connect=False, view_channel=False)
                    rejected_items.append(item.mention)
                    
                    # Store in database
                    if temp_vc:
                        rejected_roles = temp_vc.get("rejected_roles", [])
                        if item.id not in rejected_roles:
                            rejected_roles.append(item.id)
                            await storage.update_temp_voice_channel(self.channel.id, rejected_roles=rejected_roles)
            
            items_text = ", ".join(rejected_items)
            await interaction.response.send_message(f"✅ Rejected {items_text} from the channel!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


class TransferUserSelect(ui.Select):
    """User select for transferring channel ownership."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int, current_owner: discord.Member):
        # Create a filtered list of non-bot members
        super().__init__(
            placeholder="Select a user to transfer ownership to",
            min_values=1,
            max_values=1,
            select_type=discord.ComponentType.user_select
        )
        self.channel = channel
        self.owner_id = owner_id
        self.current_owner = current_owner

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can transfer ownership!", ephemeral=True)
            return

        selected_user = self.values[0]
        
        # Check if selected user is a bot
        if selected_user.bot:
            await interaction.response.send_message("❌ Cannot transfer ownership to a bot!", ephemeral=True)
            return
        
        if selected_user.id == self.owner_id:
            await interaction.response.send_message("❌ You already own this channel!", ephemeral=True)
            return
        
        # Check if selected user is in the voice channel
        if not selected_user.voice or selected_user.voice.channel != self.channel:
            await interaction.response.send_message(f"❌ {selected_user.mention} must be in the voice channel to receive ownership!", ephemeral=True)
            return
        
        try:
            logger.info(f"Starting ownership transfer: channel {self.channel.id}, from {self.owner_id} to {selected_user.id}")
            
            # Update database
            storage = await get_db()
            temp_vc = await storage.get_temp_voice_channel(self.channel.id)
            logger.info(f"Current temp_vc data: {temp_vc}")
            
            await storage.update_temp_voice_channel(self.channel.id, owner_id=selected_user.id)
            logger.info(f"Updated database with new owner_id: {selected_user.id}")
            
            # Verify update
            updated_vc = await storage.get_temp_voice_channel(self.channel.id)
            logger.info(f"Verified temp_vc data after update: {updated_vc}")
            
            # Update channel permissions
            # Remove manage permissions from old owner
            await self.channel.set_permissions(self.current_owner, manage_channels=None)
            logger.info(f"Removed manage permissions from old owner {self.current_owner.id}")
            
            # Grant manage permissions to new owner
            await self.channel.set_permissions(selected_user, manage_channels=True, connect=True, speak=True, view_channel=True)
            logger.info(f"Granted manage permissions to new owner {selected_user.id}")
            
            # Update channel name if it contains old owner's name
            if self.current_owner.display_name in self.channel.name:
                new_name = self.channel.name.replace(self.current_owner.display_name, selected_user.display_name)
                await self.channel.edit(name=new_name)
                logger.info(f"Updated channel name to: {new_name}")
            
            # Update control panel message with new owner
            if temp_vc and temp_vc.get("control_message_id"):
                try:
                    control_message = await self.channel.fetch_message(temp_vc["control_message_id"])
                    # Update embed to mention new owner
                    embed = control_message.embeds[0]
                    embed.description = f"Welcome to your temporary voice channel, {selected_user.mention}!\n\nUse the buttons below to control your channel."
                    await control_message.edit(embed=embed)
                    logger.info(f"Updated control panel message with new owner mention")
                except Exception as e:
                    logger.error(f"Error updating control panel message: {e}")
            
            await interaction.response.send_message(f"✅ Transferred ownership to {selected_user.mention}! They can now use the control panel.\n\nUse the buttons below to control your channel.", ephemeral=True)
            logger.info(f"✅ Channel {self.channel.id} ownership transferred from {self.owner_id} to {selected_user.id}")
        except Exception as e:
            logger.error(f"Error transferring channel ownership: {e}")
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


class InviteUserSelect(ui.Select):
    """User select for inviting users to the channel."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(placeholder="Select a user to invite", min_values=1, max_values=1, select_type=discord.ComponentType.user_select)
        self.channel = channel
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can invite users!", ephemeral=True)
            return

        selected_user = self.values[0]

        # Check if selected user is a bot
        if selected_user.bot:
            await interaction.response.send_message("❌ Cannot invite bots!", ephemeral=True)
            return
        
        if selected_user in self.channel.members:
            await interaction.response.send_message("❌ User is already in the voice channel!", ephemeral=True)
            return

        try:
            # Create invite
            invite = await self.channel.create_invite(max_age=3600, max_uses=1, reason=f"Invited by {interaction.user}")
            
            # Send DM to user
            embed = discord.Embed(
                title="🎙️ Voice Channel Invitation",
                description=f"{interaction.user.mention} has invited you to join their voice channel!",
                color=constants.DISCORD_EMBED_COLOR
            )
            embed.add_field(name="Channel", value=self.channel.mention, inline=False)
            embed.add_field(name="Invite Link", value=invite.url, inline=False)
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(self.channel.guild.me))
            
            try:
                await selected_user.send(embed=embed)
                logger.info(f"User {interaction.user.id} sent invite for channel {self.channel.id} to {selected_user.id}")
                await interaction.response.send_message(f"✅ Sent invitation to {selected_user.mention}!", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message(f"❌ Could not send DM to {selected_user.mention}. They may have DMs disabled.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error sending invite: {e}")
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


class KickUserSelect(ui.Select):
    """User select for kicking users from the channel."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(placeholder="Select a user to kick", min_values=1, max_values=1, select_type=discord.ComponentType.user_select)
        self.channel = channel
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can kick users!", ephemeral=True)
            return

        selected_user = self.values[0]

        # Check if selected user is a bot
        if selected_user.bot:
            await interaction.response.send_message("❌ Cannot kick bots!", ephemeral=True)
            return
        
        # Check if trying to kick themselves
        if selected_user.id == self.owner_id:
            await interaction.response.send_message("❌ You cannot kick yourself!", ephemeral=True)
            return
        
        # Check if user is in the voice channel
        if selected_user not in self.channel.members:
            await interaction.response.send_message(f"❌ {selected_user.mention} is not in the voice channel!", ephemeral=True)
            return

        try:
            # Disconnect user from the channel
            await selected_user.move_to(None)
            logger.info(f"User {interaction.user.id} kicked {selected_user.id} from channel {self.channel.id}")
            await interaction.response.send_message(f"✅ Kicked {selected_user.mention} from the channel!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"❌ Missing permissions to kick {selected_user.mention}.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error kicking user: {e}")
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


class TransferView(ui.View):
    """View for the transfer select."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int, current_owner: discord.Member):
        super().__init__(timeout=300)
        self.add_item(TransferUserSelect(channel, owner_id, current_owner))


class PermitView(ui.View):
    """View for the permit select."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(timeout=300)
        self.add_item(PermitMentionableSelect(channel, owner_id))


class RejectView(ui.View):
    """View for the reject select."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(timeout=300)
        self.add_item(RejectMentionableSelect(channel, owner_id))


class InviteView(ui.View):
    """View for the invite button."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(timeout=300)
        self.add_item(InviteUserSelect(channel, owner_id))


class KickView(ui.View):
    """View for the kick button."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(timeout=300)
        self.add_item(KickUserSelect(channel, owner_id))


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
        await interaction.response.send_message(message, view=PermitView(channel, current_owner_id), ephemeral=True)

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
        await interaction.response.send_message(message, view=RejectView(channel, current_owner_id), ephemeral=True)

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
        await interaction.response.send_message("Select a user to invite:", view=InviteView(channel, current_owner_id), ephemeral=True)

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
        await interaction.response.send_message("Select a user to kick:", view=KickView(channel, current_owner_id), ephemeral=True)

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

        await interaction.response.send_message("Select a user to transfer ownership to:", view=TransferView(channel, current_owner_id, current_owner), ephemeral=True)

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
        from .TempVoiceSettingsView import TempVoiceSettingsView
        
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
