"""
Control panel view for temporary voice channels.
Provides lock/unlock, permit/reject, invite, ghost/unghost, and transfer ownership buttons.
"""
import discord
from typing import Optional
from src.utils.logger import get_cool_logger
from src.utils.database import get_db
from src.utils.get_embed_icon import get_embed_icon
import config.constants as constants
from src.languages import lang_constants as lang_constants

logger = get_cool_logger(__name__)


class UserSelectView(discord.ui.View):
    """View for selecting users to permit/reject/invite."""
    
    def __init__(self, action: str, channel_id: int, owner_id: int):
        super().__init__(timeout=60)
        self.action = action
        self.channel_id = channel_id
        self.owner_id = owner_id
        self.selected_user = None


class PermitUserSelect(discord.ui.UserSelect):
    """User select for permitting users."""
    
    def __init__(self, channel_id: int, owner_id: int):
        super().__init__(
            placeholder="Select a user to permit",
            min_values=1,
            max_values=1,
            custom_id=f"permit_user_select_{channel_id}"
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
        
        selected_user = self.values[0]
        
        try:
            db = await get_db()
            channel_data = await db.get_temp_voice_channel(self.channel_id)
            
            if not channel_data:
                await interaction.response.send_message(
                    f"{lang_constants.ERROR_EMOJI} Channel data not found!",
                    ephemeral=True
                )
                return
            
            # Add user to permitted list and remove from rejected if present
            permitted = channel_data["permitted_users"]
            rejected = channel_data["rejected_users"]
            
            user_id_str = str(selected_user.id)
            if user_id_str not in permitted:
                permitted.append(user_id_str)
            if user_id_str in rejected:
                rejected.remove(user_id_str)
            
            await db.update_temp_voice_channel_permissions(
                self.channel_id,
                permitted_users=permitted,
                rejected_users=rejected
            )
            
            # Update channel permissions
            channel = interaction.guild.get_channel(self.channel_id)
            if channel and isinstance(channel, discord.VoiceChannel):
                await channel.set_permissions(
                    selected_user,
                    view_channel=True,
                    connect=True
                )
            
            embed = discord.Embed(
                title=f"{lang_constants.SUCCESS_EMOJI} User Permitted",
                description=f"{selected_user.mention} can now join your voice channel!",
                color=constants.SUCCESS_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(f"User {selected_user.id} permitted to channel {self.channel_id}")
            
        except Exception as e:
            logger.error(f"Error permitting user: {e}")
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Failed to permit user.",
                ephemeral=True
            )


class RejectUserSelect(discord.ui.UserSelect):
    """User select for rejecting users."""
    
    def __init__(self, channel_id: int, owner_id: int):
        super().__init__(
            placeholder="Select a user to reject",
            min_values=1,
            max_values=1,
            custom_id=f"reject_user_select_{channel_id}"
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
        
        selected_user = self.values[0]
        
        try:
            db = await get_db()
            channel_data = await db.get_temp_voice_channel(self.channel_id)
            
            if not channel_data:
                await interaction.response.send_message(
                    f"{lang_constants.ERROR_EMOJI} Channel data not found!",
                    ephemeral=True
                )
                return
            
            # Add user to rejected list and remove from permitted if present
            permitted = channel_data["permitted_users"]
            rejected = channel_data["rejected_users"]
            
            user_id_str = str(selected_user.id)
            if user_id_str not in rejected:
                rejected.append(user_id_str)
            if user_id_str in permitted:
                permitted.remove(user_id_str)
            
            await db.update_temp_voice_channel_permissions(
                self.channel_id,
                permitted_users=permitted,
                rejected_users=rejected
            )
            
            # Update channel permissions and kick if in channel
            channel = interaction.guild.get_channel(self.channel_id)
            if channel and isinstance(channel, discord.VoiceChannel):
                await channel.set_permissions(
                    selected_user,
                    view_channel=False,
                    connect=False
                )
                
                # Disconnect user if they're in the channel
                if selected_user in channel.members:
                    await selected_user.move_to(None, reason="Rejected from temp voice channel")
            
            embed = discord.Embed(
                title=f"{lang_constants.SUCCESS_EMOJI} User Rejected",
                description=f"{selected_user.mention} has been blocked from your voice channel!",
                color=constants.SUCCESS_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(f"User {selected_user.id} rejected from channel {self.channel_id}")
            
        except Exception as e:
            logger.error(f"Error rejecting user: {e}")
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Failed to reject user.",
                ephemeral=True
            )


class InviteUserSelect(discord.ui.UserSelect):
    """User select for inviting users."""
    
    def __init__(self, channel_id: int, owner_id: int):
        super().__init__(
            placeholder="Select a user to invite",
            min_values=1,
            max_values=1,
            custom_id=f"invite_user_select_{channel_id}"
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
        
        selected_user = self.values[0]
        
        try:
            channel = interaction.guild.get_channel(self.channel_id)
            if not channel:
                await interaction.response.send_message(
                    f"{lang_constants.ERROR_EMOJI} Channel not found!",
                    ephemeral=True
                )
                return
            
            # Send DM to invited user
            try:
                invite_embed = discord.Embed(
                    title="🎙️ Voice Channel Invitation",
                    description=f"{interaction.user.mention} invited you to join their voice channel: **{channel.name}**\n\nClick the channel to join!",
                    color=constants.DISCORD_EMBED_COLOR
                )
                invite_embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK)
                await selected_user.send(embed=invite_embed)
                
                embed = discord.Embed(
                    title=f"{lang_constants.SUCCESS_EMOJI} Invitation Sent",
                    description=f"Sent an invitation to {selected_user.mention}!",
                    color=constants.SUCCESS_EMBED_COLOR
                )
                embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
                logger.info(f"Invitation sent to {selected_user.id} for channel {self.channel_id}")
                
            except discord.Forbidden:
                await interaction.response.send_message(
                    f"{lang_constants.ERROR_EMOJI} Could not send DM to {selected_user.mention}. They may have DMs disabled.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error inviting user: {e}")
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Failed to invite user.",
                ephemeral=True
            )


class TransferOwnershipSelect(discord.ui.UserSelect):
    """User select for transferring ownership."""
    
    def __init__(self, channel_id: int, owner_id: int):
        super().__init__(
            placeholder="Select a user to transfer ownership",
            min_values=1,
            max_values=1,
            custom_id=f"transfer_owner_select_{channel_id}"
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
        
        selected_user = self.values[0]
        
        if selected_user.bot:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Cannot transfer ownership to a bot!",
                ephemeral=True
            )
            return
        
        if selected_user.id == self.owner_id:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} You are already the owner!",
                ephemeral=True
            )
            return
        
        try:
            from src.features.temp_voice_channels.channel_manager import transfer_ownership
            
            channel = interaction.guild.get_channel(self.channel_id)
            if not channel or not isinstance(channel, discord.VoiceChannel):
                await interaction.response.send_message(
                    f"{lang_constants.ERROR_EMOJI} Channel not found!",
                    ephemeral=True
                )
                return
            
            await transfer_ownership(channel, selected_user, str(self.owner_id))
            
            # Update the control panel message
            db = await get_db()
            channel_data = await db.get_temp_voice_channel(self.channel_id)
            
            if channel_data and channel_data.get("control_message_id"):
                try:
                    control_msg = await channel.fetch_message(channel_data["control_message_id"])
                    new_view = TempVoiceControlPanel(self.channel_id, selected_user.id)
                    await control_msg.edit(view=new_view)
                except:
                    pass
            
            embed = discord.Embed(
                title=f"{lang_constants.SUCCESS_EMOJI} Ownership Transferred",
                description=f"Channel ownership transferred to {selected_user.mention}!",
                color=constants.SUCCESS_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(f"Ownership of channel {self.channel_id} transferred to {selected_user.id}")
            
        except Exception as e:
            logger.error(f"Error transferring ownership: {e}")
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Failed to transfer ownership.",
                ephemeral=True
            )


class TempVoiceControlPanel(discord.ui.View):
    """Main control panel for temporary voice channels."""
    
    def __init__(self, channel_id: int, owner_id: int):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.owner_id = owner_id
        
        # Set custom IDs for persistence
        self.lock_button.custom_id = f"temp_voice_lock_{channel_id}"
        self.unlock_button.custom_id = f"temp_voice_unlock_{channel_id}"
        self.permit_button.custom_id = f"temp_voice_permit_{channel_id}"
        self.reject_button.custom_id = f"temp_voice_reject_{channel_id}"
        self.ghost_button.custom_id = f"temp_voice_ghost_{channel_id}"
        self.unghost_button.custom_id = f"temp_voice_unghost_{channel_id}"
        self.transfer_button.custom_id = f"temp_voice_transfer_{channel_id}"
        
        # Conditionally add invite button
        if constants.TEMP_VOICE_INVITE_ENABLED:
            self.invite_button.custom_id = f"temp_voice_invite_{channel_id}"
        else:
            self.remove_item(self.invite_button)
    
    async def _check_owner(self, interaction: discord.Interaction) -> bool:
        """Check if the user is the channel owner."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Only the channel owner can use this!",
                ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="Lock", style=discord.ButtonStyle.secondary, emoji="🔒", row=0)
    async def lock_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        
        try:
            db = await get_db()
            await db.update_temp_voice_channel_permissions(self.channel_id, is_locked=True)
            
            channel = interaction.guild.get_channel(self.channel_id)
            if channel and isinstance(channel, discord.VoiceChannel):
                default_role = interaction.guild.get_role(constants.DEFAULT_USER_ROLE_ID)
                if default_role:
                    await channel.set_permissions(default_role, view_channel=True, connect=False)
            
            embed = discord.Embed(
                title="🔒 Channel Locked",
                description="Your channel is now locked. Only permitted users can join.",
                color=constants.SUCCESS_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(f"Channel {self.channel_id} locked by owner {self.owner_id}")
            
        except Exception as e:
            logger.error(f"Error locking channel: {e}")
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Failed to lock channel.",
                ephemeral=True
            )
    
    @discord.ui.button(label="Unlock", style=discord.ButtonStyle.secondary, emoji="🔓", row=0)
    async def unlock_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        
        try:
            db = await get_db()
            await db.update_temp_voice_channel_permissions(self.channel_id, is_locked=False)
            
            channel = interaction.guild.get_channel(self.channel_id)
            if channel and isinstance(channel, discord.VoiceChannel):
                default_role = interaction.guild.get_role(constants.DEFAULT_USER_ROLE_ID)
                if default_role:
                    await channel.set_permissions(default_role, view_channel=True, connect=True)
            
            embed = discord.Embed(
                title="🔓 Channel Unlocked",
                description="Your channel is now unlocked. Everyone can join again.",
                color=constants.SUCCESS_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(f"Channel {self.channel_id} unlocked by owner {self.owner_id}")
            
        except Exception as e:
            logger.error(f"Error unlocking channel: {e}")
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Failed to unlock channel.",
                ephemeral=True
            )
    
    @discord.ui.button(label="Permit", style=discord.ButtonStyle.success, emoji="✅", row=0)
    async def permit_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        
        # Send ephemeral message with user select
        view = discord.ui.View(timeout=60)
        view.add_item(PermitUserSelect(self.channel_id, self.owner_id))
        
        await interaction.response.send_message(
            "Select a user to permit:",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, emoji="❌", row=0)
    async def reject_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        
        # Send ephemeral message with user select
        view = discord.ui.View(timeout=60)
        view.add_item(RejectUserSelect(self.channel_id, self.owner_id))
        
        await interaction.response.send_message(
            "Select a user to reject:",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="Invite", style=discord.ButtonStyle.primary, emoji="📧", row=1)
    async def invite_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        
        # Send ephemeral message with user select
        view = discord.ui.View(timeout=60)
        view.add_item(InviteUserSelect(self.channel_id, self.owner_id))
        
        await interaction.response.send_message(
            "Select a user to invite:",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="Ghost", style=discord.ButtonStyle.secondary, emoji="👻", row=1)
    async def ghost_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        
        try:
            db = await get_db()
            await db.update_temp_voice_channel_permissions(self.channel_id, is_ghost=True)
            
            channel = interaction.guild.get_channel(self.channel_id)
            if channel and isinstance(channel, discord.VoiceChannel):
                default_role = interaction.guild.get_role(constants.DEFAULT_USER_ROLE_ID)
                if default_role:
                    await channel.set_permissions(default_role, view_channel=False, connect=False)
            
            embed = discord.Embed(
                title="👻 Channel Hidden",
                description="Your channel is now invisible to others.",
                color=constants.SUCCESS_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(f"Channel {self.channel_id} ghosted by owner {self.owner_id}")
            
        except Exception as e:
            logger.error(f"Error ghosting channel: {e}")
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Failed to ghost channel.",
                ephemeral=True
            )
    
    @discord.ui.button(label="Unghost", style=discord.ButtonStyle.secondary, emoji="👁️", row=1)
    async def unghost_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        
        try:
            db = await get_db()
            channel_data = await db.get_temp_voice_channel(self.channel_id)
            await db.update_temp_voice_channel_permissions(self.channel_id, is_ghost=False)
            
            channel = interaction.guild.get_channel(self.channel_id)
            if channel and isinstance(channel, discord.VoiceChannel):
                default_role = interaction.guild.get_role(constants.DEFAULT_USER_ROLE_ID)
                if default_role:
                    # Restore based on lock status
                    if channel_data and channel_data.get("is_locked"):
                        await channel.set_permissions(default_role, view_channel=True, connect=False)
                    else:
                        await channel.set_permissions(default_role, view_channel=True, connect=True)
            
            embed = discord.Embed(
                title="👁️ Channel Visible",
                description="Your channel is now visible to others.",
                color=constants.SUCCESS_EMBED_COLOR
            )
            embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK, icon_url=get_embed_icon(interaction))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(f"Channel {self.channel_id} unghosted by owner {self.owner_id}")
            
        except Exception as e:
            logger.error(f"Error unghosting channel: {e}")
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Failed to unghost channel.",
                ephemeral=True
            )
    
    @discord.ui.button(label="Transfer", style=discord.ButtonStyle.secondary, emoji="👑", row=1)
    async def transfer_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self._check_owner(interaction):
            return
        
        # Send ephemeral message with user select
        view = discord.ui.View(timeout=60)
        view.add_item(TransferOwnershipSelect(self.channel_id, self.owner_id))
        
        await interaction.response.send_message(
            "Select a user to transfer ownership:",
            view=view,
            ephemeral=True
        )


def build_control_panel_embed(owner: discord.Member, channel: discord.VoiceChannel) -> discord.Embed:
    """Build the embed for the control panel."""
    description_parts = [
        f"**Owner:** {owner.mention}\n**Channel:** {channel.mention}\n",
        "🔒 **Lock** - Prevent new users from joining",
        "🔓 **Unlock** - Allow users to join again",
        "✅ **Permit** - Allow specific users to join",
        "❌ **Reject** - Block specific users",
    ]
    
    if constants.TEMP_VOICE_INVITE_ENABLED:
        description_parts.append("📧 **Invite** - Send DM invite to a user")
    
    description_parts.extend([
        "👻 **Ghost** - Hide your channel",
        "👁️ **Unghost** - Make your channel visible",
        "👑 **Transfer** - Transfer ownership"
    ])
    
    embed = discord.Embed(
        title="🎙️ Voice Channel Control Panel",
        description="\n".join(description_parts),
        color=constants.DISCORD_EMBED_COLOR
    )
    embed.set_footer(text=constants.DISCORD_MESSAGE_TRADEMARK)
    return embed
