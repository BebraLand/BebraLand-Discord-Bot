import discord
from discord import ui
from typing import Optional
import time
from config import constants
from src.utils.database import get_db


class PermitMentionableSelect(ui.MentionableSelect):
    """Mentionable select for permitting users or roles to join the channel."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(placeholder="Select users/roles to permit", min_values=1, max_values=10)
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


class RejectMentionableSelect(ui.MentionableSelect):
    """Mentionable select for rejecting users or roles from joining the channel."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(placeholder="Select users/roles to reject", min_values=1, max_values=10)
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
                    
                    # Disconnect if in channel
                    if hasattr(item, 'voice') and item.voice and item.voice.channel == self.channel:
                        await item.move_to(None)
                    
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


class TransferModal(ui.Modal):
    """Modal to transfer channel ownership to another user."""
    user_id = discord.ui.InputText(
        label="User ID",
        placeholder="Enter user ID to transfer ownership to",
        required=True,
        max_length=20
    )

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(title="Transfer Ownership")
        self.channel = channel
        self.owner_id = owner_id

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can transfer ownership!", ephemeral=True)
            return

        try:
            new_owner_id = int(self.user_id.value.strip())
            new_owner = interaction.guild.get_member(new_owner_id)
            
            if not new_owner:
                await interaction.response.send_message("❌ User not found!", ephemeral=True)
                return
            
            if new_owner.id == self.owner_id:
                await interaction.response.send_message("❌ You already own this channel!", ephemeral=True)
                return
            
            # Update database
            storage = await get_db()
            await storage.update_temp_voice_channel(self.channel.id, owner_id=new_owner_id)
            
            # Update channel name if it contains old owner's name
            if interaction.user.display_name in self.channel.name:
                new_name = self.channel.name.replace(interaction.user.display_name, new_owner.display_name)
                await self.channel.edit(name=new_name)
            
            await interaction.response.send_message(f"✅ Transferred ownership to {new_owner.mention}!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid user ID format!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


class InviteUserSelect(ui.UserSelect):
    """User select for inviting users to the channel."""
    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(placeholder="Select a user to invite", min_values=1, max_values=1)
        self.channel = channel
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can invite users!", ephemeral=True)
            return

        selected_user = self.values[0]
        
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
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=constants.DISCORD_EMBED_FOOTER_ICON)
            
            try:
                await selected_user.send(embed=embed)
                await interaction.response.send_message(f"✅ Sent invitation to {selected_user.mention}!", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message(f"❌ Could not send DM to {selected_user.mention}. They may have DMs disabled.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


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

    @ui.button(label="🔒 Lock", style=discord.ButtonStyle.secondary, custom_id="lock")
    async def lock_button(self, interaction: discord.Interaction, button: ui.Button):
        """Lock the channel - DEFAULT_USER_ROLE_ID can see but not connect."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can lock the channel!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        try:
            default_role = interaction.guild.get_role(constants.DEFAULT_USER_ROLE_ID)
            if default_role:
                await channel.set_permissions(default_role, connect=False, view_channel=True)
            await interaction.response.send_message("🔒 Channel locked! Users can see but not connect.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

    @ui.button(label="🔓 Unlock", style=discord.ButtonStyle.secondary, custom_id="unlock")
    async def unlock_button(self, interaction: discord.Interaction, button: ui.Button):
        """Unlock the channel - DEFAULT_USER_ROLE_ID can see and connect."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can unlock the channel!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        try:
            default_role = interaction.guild.get_role(constants.DEFAULT_USER_ROLE_ID)
            if default_role:
                await channel.set_permissions(default_role, connect=True, view_channel=True)
            await interaction.response.send_message("🔓 Channel unlocked! Users can connect.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

    @ui.button(label="✅ Permit", style=discord.ButtonStyle.success, custom_id="permit")
    async def permit_button(self, interaction: discord.Interaction, button: ui.Button):
        """Permit a user or role to join the channel."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can permit users!", ephemeral=True)
            return
            
        channel = await self._get_channel(interaction)
        if not channel:
            return

        await interaction.response.send_message("Select users/roles to permit:", view=PermitView(channel, self.owner_id), ephemeral=True)

    @ui.button(label="❌ Reject", style=discord.ButtonStyle.danger, custom_id="reject")
    async def reject_button(self, interaction: discord.Interaction, button: ui.Button):
        """Reject a user or role from joining the channel."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can reject users!", ephemeral=True)
            return
            
        channel = await self._get_channel(interaction)
        if not channel:
            return

        await interaction.response.send_message("Select users/roles to reject:", view=RejectView(channel, self.owner_id), ephemeral=True)

    @ui.button(label="📨 Invite", style=discord.ButtonStyle.primary, custom_id="invite", row=1)
    async def invite_button(self, interaction: discord.Interaction, button: ui.Button):
        """Invite a user to the channel via DM."""
        if not constants.TEMP_VOICE_INVITE_ENABLED:
            await interaction.response.send_message("❌ Invite feature is disabled!", ephemeral=True)
            return

        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can invite users!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        # Show user select
        await interaction.response.send_message("Select a user to invite:", view=InviteView(channel, self.owner_id), ephemeral=True)

    @ui.button(label="👻 Ghost", style=discord.ButtonStyle.secondary, custom_id="ghost", row=1)
    async def ghost_button(self, interaction: discord.Interaction, button: ui.Button):
        """Make the channel invisible."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can ghost the channel!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        try:
            default_role = interaction.guild.get_role(constants.DEFAULT_USER_ROLE_ID)
            if default_role:
                await channel.set_permissions(default_role, view_channel=False)
            await interaction.response.send_message("👻 Channel is now invisible!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

    @ui.button(label="👁️ Unghost", style=discord.ButtonStyle.secondary, custom_id="unghost", row=1)
    async def unghost_button(self, interaction: discord.Interaction, button: ui.Button):
        """Make the channel visible."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Only the channel owner can unghost the channel!", ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        try:
            default_role = interaction.guild.get_role(constants.DEFAULT_USER_ROLE_ID)
            if default_role:
                await channel.set_permissions(default_role, view_channel=True, connect=True)
            await interaction.response.send_message("👁️ Channel is now visible!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

    @ui.button(label="🔄 Transfer", style=discord.ButtonStyle.secondary, custom_id="transfer", row=1)
    async def transfer_button(self, interaction: discord.Interaction, button: ui.Button):
        """Transfer ownership to another user."""
        channel = await self._get_channel(interaction)
        if not channel:
            return

        await interaction.response.send_modal(TransferModal(channel, self.owner_id))

    @ui.button(label="⚙️ Settings", style=discord.ButtonStyle.primary, custom_id="settings", row=2)
    async def settings_button(self, interaction: discord.Interaction, button: ui.Button):
        """Open channel settings."""
        if interaction.user.id != self.owner_id:
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
        embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=constants.DISCORD_EMBED_FOOTER_ICON)
        
        await interaction.response.send_message(
            embed=embed,
            view=TempVoiceSettingsView(self.channel_id, self.owner_id),
            ephemeral=True
        )
