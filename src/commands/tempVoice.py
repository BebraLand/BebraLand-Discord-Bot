import discord
from discord.ext import commands, tasks
import json
import asyncio
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, Set, Optional, List
from src.utils.config_manager import load_config
from src.utils.localization import LocalizationManager
from src.utils.localization_helper import LocalizationHelper, create_success_embed
from src.utils.discord_helpers import create_permission_overwrites, apply_privacy_overwrites

# Set up logger
logger = logging.getLogger(__name__)


@dataclass
class TempChannelData:
    """Data structure for temporary voice channels"""
    channel_id: int
    owner_id: int
    guild_id: int
    channel_name: str
    user_limit: int = 0
    is_private: bool = False
    region: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    trusted_users: Set[int] = field(default_factory=set)
    blocked_users: Set[int] = field(default_factory=set)


@dataclass
class GuildTempVoiceConfig:
    """Guild-specific TempVoice configuration"""
    guild_id: int
    creator_channels: List[int] = field(default_factory=list)
    temp_category_id: Optional[int] = None
    enabled: bool = True
    required_role: Optional[int] = None
    max_channels_per_user: int = 3
    auto_delete_delay: int = 0
    default_everyone_permissions: Dict[str, bool] = field(default_factory=lambda: {"view_channel": True, "connect": True})
    allowed_roles: List[int] = field(default_factory=list)


class ChannelNameModal(discord.ui.Modal):
    """Modal for changing channel name"""
    def __init__(self, cog, channel_data: TempChannelData):
        super().__init__(title="Change Channel Name")
        self.cog = cog
        self.channel_data = channel_data
        
        self.name_input = discord.ui.InputText(
            label="Channel Name",
            placeholder="Enter new channel name...",
            value=channel_data.channel_name,
            max_length=100
        )
        self.add_item(self.name_input)
    
    async def callback(self, interaction: discord.Interaction):
        new_name = self.name_input.value.strip()
        if not new_name:
            try:
                await interaction.response.send_message(
                    self.cog.loc_helper.get_text("TEMPVOICE_INVALID_NAME", interaction.user.id),
                    ephemeral=True
                )
            except discord.errors.NotFound:
                try:
                    await interaction.followup.send(
                        self.cog.loc_helper.get_text("TEMPVOICE_INVALID_NAME", interaction.user.id),
                        ephemeral=True
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] Failed to send invalid name message")
            return
        
        try:
            channel = interaction.guild.get_channel(self.channel_data.channel_id)
            if channel:
                await channel.edit(name=new_name)
                self.channel_data.channel_name = new_name
                
                # Create success embed with green color
                success_embed = discord.Embed(
                    title="✅ Success",
                    description=self.cog.loc_helper.get_text("TEMPVOICE_NAME_CHANGED", interaction.user.id, name=new_name),
                    color=0x00FF00  # Green color for success
                )
                
                # Add bot branding footer
                config = load_config()
                success_embed.set_footer(
                    text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                    icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
                )
                
                try:
                    # Send a separate success message instead of editing the original interface
                    await interaction.response.send_message(
                        embed=success_embed,
                        ephemeral=True,
                        delete_after=30  # Auto-delete after 30 seconds
                    )
                except discord.errors.NotFound:
                    try:
                        await interaction.followup.send(
                            embed=success_embed,
                            ephemeral=True,
                            delete_after=30
                        )
                    except discord.errors.NotFound:
                        print(f"[TEMPVOICE] ❌ Failed to send name change success message")
                        return
                
                print(f"[TEMPVOICE] ✅ NAME CHANGE SUCCESS | User: {interaction.user.name} | New Name: {new_name}")
            else:
                try:
                    await interaction.response.send_message(
                        self.cog.loc_helper.get_text("TEMPVOICE_CHANNEL_NOT_FOUND", interaction.user.id),
                        ephemeral=True
                    )
                except discord.errors.NotFound:
                    try:
                        await interaction.followup.send(
                            self.cog.loc_helper.get_text("TEMPVOICE_CHANNEL_NOT_FOUND", interaction.user.id),
                            ephemeral=True
                        )
                    except discord.errors.NotFound:
                        print(f"[TEMPVOICE] Failed to send channel not found message")
        except Exception as e:
            try:
                await interaction.response.send_message(
                    self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error=str(e)),
                    ephemeral=True
                )
            except discord.errors.NotFound:
                try:
                    await interaction.followup.send(
                        self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error=str(e)),
                        ephemeral=True
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] Failed to send error message: {e}")


class PrivacyDropdownView(discord.ui.View):
    """Dropdown view for privacy options"""
    def __init__(self, cog, channel_data: TempChannelData):
        super().__init__(timeout=300)
        self.cog = cog
        self.channel_data = channel_data
        
        # Add the dropdown select menu
        self.add_item(PrivacySelect(cog, channel_data))


class PrivacySelect(discord.ui.Select):
    """Select menu for privacy options"""
    def __init__(self, cog, channel_data: TempChannelData):
        self.cog = cog
        self.channel_data = channel_data
        
        options = [
            discord.SelectOption(
                label="Lock",
                description="Only trusted users can join your voice channel",
                emoji="🔒",
                value="lock"
            ),
            discord.SelectOption(
                label="Unlock",
                description="Everyone can join your voice channel",
                emoji="🔓",
                value="unlock"
            ),
            discord.SelectOption(
                label="Invisible",
                description="Only trusted users can view your voice channel",
                emoji="👁️‍🗨️",
                value="invisible"
            ),
            discord.SelectOption(
                label="Visible",
                description="Everyone can view your voice channel",
                emoji="👁️",
                value="visible"
            ),
            discord.SelectOption(
                label="Close Chat",
                description="Only trusted users can text in your chat",
                emoji="💬",
                value="close_chat"
            ),
            discord.SelectOption(
                label="Open Chat",
                description="Everyone can text in your chat",
                emoji="💭",
                value="open_chat"
            )
        ]
        
        super().__init__(
            placeholder="Choose a privacy option...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle privacy option selection"""
        try:
            channel = interaction.guild.get_channel(self.channel_data.channel_id)
            if not channel:
                # Create error embed
                error_embed = self.cog.loc_helper.create_error_embed(
                    title_key="tempvoice_error_title",
                    description_key="TEMPVOICE_CHANNEL_NOT_FOUND",
                    user_id=interaction.user.id
                )
                
                try:
                    # Send a separate ephemeral error message instead of editing the original interface
                    await interaction.response.send_message(
                        embed=error_embed,
                        ephemeral=True,
                        delete_after=30  # Auto-delete after 30 seconds
                    )
                except discord.errors.NotFound:
                    try:
                        await interaction.followup.send(
                            embed=error_embed,
                            ephemeral=True,
                            delete_after=30
                        )
                    except discord.errors.NotFound:
                        print(f"[TEMPVOICE] ❌ Failed to send channel not found error message")
                
                print(f"[TEMPVOICE] ❌ PRIVACY CHANGE FAILED | Channel not found | Channel ID: {self.channel_data.channel_id}")
                return
            
            option = self.values[0]
            
            # Get guild config for allowed roles
            config = load_config()
            guild_config = self.cog._get_guild_config(interaction.guild.id, config)
            allowed_roles = guild_config.get("TEMPVOICE_ALLOWED_ROLES", [])
            
            # DEBUG: Log guild config and allowed roles
            print(f"[TEMPVOICE DEBUG] 🔧 CONFIG LOADED | Guild: {interaction.guild.name} ({interaction.guild.id})")
            print(f"[TEMPVOICE DEBUG] 🔧 ALLOWED_ROLES: {allowed_roles}")
            print(f"[TEMPVOICE DEBUG] 🔧 GUILD_CONFIG: {guild_config}")
            
            # Get channel owner
            owner = interaction.guild.get_member(self.channel_data.owner_id)
            if not owner:
                # Create error embed
                error_embed = self.cog.loc_helper.create_error_embed(
                    title_key="tempvoice_error_title",
                    description_key="TEMPVOICE_ERROR",
                    user_id=interaction.user.id,
                    error="Channel owner not found. Cannot modify permissions."
                )
                
                try:
                    # Edit the original message instead of sending new one
                    await interaction.response.edit_message(
                        embed=error_embed,
                        view=None,  # Remove the dropdown
                        delete_after=30  # Auto-delete after 30 seconds
                    )
                except discord.errors.NotFound:
                    try:
                        await interaction.edit_original_response(
                            embed=error_embed,
                            view=None,
                            delete_after=30
                        )
                    except discord.errors.NotFound:
                        print(f"[TEMPVOICE] ❌ Failed to edit message with owner not found error")
                
                print(f"[TEMPVOICE] ❌ PRIVACY CHANGE FAILED | Owner not found | Owner ID: {self.channel_data.owner_id}")
                return
            
            # DEBUG: Log current permissions BEFORE changes
            print(f"[TEMPVOICE DEBUG] 🔒 BEFORE PRIVACY CHANGE | Action: {option}")
            print(f"[TEMPVOICE DEBUG] 🔒 Channel: {channel.name} ({channel.id})")
            print(f"[TEMPVOICE DEBUG] 🔒 Owner: {owner.name} ({owner.id})")
            print(f"[TEMPVOICE DEBUG] 🔒 Trusted Users: {self.channel_data.trusted_users}")
            
            # Log current @everyone permissions
            everyone_perms = channel.overwrites_for(interaction.guild.default_role)
            print(f"[TEMPVOICE DEBUG] 🔒 BEFORE @everyone perms: view_channel={everyone_perms.view_channel}, connect={everyone_perms.connect}")
            
            # Log current owner permissions
            owner_perms = channel.overwrites_for(owner)
            print(f"[TEMPVOICE DEBUG] 🔒 BEFORE Owner perms: view_channel={owner_perms.view_channel}, connect={owner_perms.connect}")
            
            # Log current allowed roles permissions
            for role_id in allowed_roles:
                role = interaction.guild.get_role(role_id)
                if role:
                    role_perms = channel.overwrites_for(role)
                    print(f"[TEMPVOICE DEBUG] 🔒 BEFORE Role {role.name} ({role_id}) perms: view_channel={role_perms.view_channel}, connect={role_perms.connect}")
                else:
                    print(f"[TEMPVOICE DEBUG] 🔒 BEFORE Role {role_id} not found in guild")
            
            # Apply privacy settings using the helper function
            from src.utils.discord_helpers import apply_privacy_overwrites
            
            base_overwrites = channel.overwrites.copy()
            new_overwrites = apply_privacy_overwrites(
                base_overwrites=base_overwrites,
                privacy_action=option,
                guild=interaction.guild,
                allowed_roles=allowed_roles,
                owner=owner,
                trusted_users=self.channel_data.trusted_users
            )
            
            # DEBUG: Log NEW permissions AFTER changes
            print(f"[TEMPVOICE DEBUG] 🔒 AFTER PRIVACY CHANGE | New overwrites count: {len(new_overwrites)}")
            
            # Log new @everyone permissions
            if interaction.guild.default_role in new_overwrites:
                new_everyone_perms = new_overwrites[interaction.guild.default_role]
                print(f"[TEMPVOICE DEBUG] 🔒 AFTER @everyone perms: view_channel={new_everyone_perms.view_channel}, connect={new_everyone_perms.connect}")
            else:
                print(f"[TEMPVOICE DEBUG] 🔒 AFTER @everyone perms: NO OVERWRITE (inherits from category)")
            
            # Log new owner permissions
            if owner in new_overwrites:
                new_owner_perms = new_overwrites[owner]
                print(f"[TEMPVOICE DEBUG] 🔒 AFTER Owner perms: view_channel={new_owner_perms.view_channel}, connect={new_owner_perms.connect}")
            else:
                print(f"[TEMPVOICE DEBUG] 🔒 AFTER Owner perms: NO OVERWRITE (inherits from category)")
            
            # Log new allowed roles permissions
            for role_id in allowed_roles:
                role = interaction.guild.get_role(role_id)
                if role and role in new_overwrites:
                    new_role_perms = new_overwrites[role]
                    print(f"[TEMPVOICE DEBUG] 🔒 AFTER Role {role.name} ({role_id}) perms: view_channel={new_role_perms.view_channel}, connect={new_role_perms.connect}")
                elif role:
                    print(f"[TEMPVOICE DEBUG] 🔒 AFTER Role {role.name} ({role_id}) perms: NO OVERWRITE (inherits from category)")
                else:
                    print(f"[TEMPVOICE DEBUG] 🔒 AFTER Role {role_id} not found in guild")
            
            # Update privacy state
            if option in ["lock", "invisible"]:
                self.channel_data.is_private = True
            elif option in ["unlock", "visible"]:
                self.channel_data.is_private = False
            
            # Set action text for confirmation
            action_texts = {
                "lock": "locked - only trusted users and allowed roles can join",
                "unlock": "unlocked - everyone can join",
                "invisible": "made invisible - only trusted users and allowed roles can view",
                "visible": "made visible - everyone can view",
                "close_chat": "chat closed - only trusted users can text",
                "open_chat": "chat opened - everyone can text"
            }
            action_text = action_texts.get(option, "updated")
            
            # Update channel permissions
            await channel.edit(overwrites=new_overwrites)
            
            # Create success embed
            embed = discord.Embed(
                title="Privacy Updated",
                description=f"Your channel has been **{action_text}**.",
                color=0x00ff00
            )
            
            config = load_config()
            embed.set_footer(
                text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
            )
            
            try:
                # Send a separate ephemeral success message instead of editing the original interface
                await interaction.response.send_message(
                    embed=embed,
                    ephemeral=True,
                    delete_after=30  # Auto-delete after 30 seconds
                )
            except discord.errors.NotFound:
                try:
                    await interaction.followup.send(
                        embed=embed,
                        ephemeral=True,
                        delete_after=30
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] ❌ Failed to send privacy success message")
            
            # Log the privacy change
            print(f"[TEMPVOICE] 🔒 PRIVACY CHANGED | User: {interaction.user.name} ({interaction.user.id}) | Channel: {channel.name} ({channel.id}) | Action: {option} | Guild: {interaction.guild.name}")
            
        except Exception as e:
            # Create error embed
            error_embed = self.cog.loc_helper.create_error_embed(
                title_key="tempvoice_error_title",
                description_key="TEMPVOICE_ERROR",
                user_id=interaction.user.id,
                error=str(e)
            )
            
            try:
                # Send a separate ephemeral error message instead of editing the original interface
                await interaction.response.send_message(
                    embed=error_embed,
                    ephemeral=True,
                    delete_after=30  # Auto-delete after 30 seconds
                )
            except discord.errors.NotFound:
                try:
                    await interaction.followup.send(
                        embed=error_embed,
                        ephemeral=True,
                        delete_after=30
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] ❌ Failed to send privacy error message")
            
            print(f"[TEMPVOICE] ❌ PRIVACY ERROR | User: {interaction.user.name} | Error: {str(e)}")


class UserLimitModal(discord.ui.Modal):
    """Modal for setting user limit"""
    def __init__(self, cog, channel_data: TempChannelData):
        super().__init__(title="Set User Limit")
        self.cog = cog
        self.channel_data = channel_data
        
        self.limit_input = discord.ui.InputText(
            label="User Limit (0 = unlimited)",
            placeholder="Enter number (0-99)...",
            value=str(channel_data.user_limit),
            max_length=2
        )
        self.add_item(self.limit_input)
    
    async def callback(self, interaction: discord.Interaction):
        try:
            limit = int(self.limit_input.value)
            if limit < 0 or limit > 99:
                # Create error embed with red color
                error_embed = discord.Embed(
                    title="❌ Error",
                    description=self.cog.loc_helper.get_text("TEMPVOICE_INVALID_LIMIT", interaction.user.id),
                    color=0xFF0000  # Red color for error
                )
                
                # Add bot branding footer
                config = load_config()
                error_embed.set_footer(
                    text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                    icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
                )
                
                try:
                    await interaction.response.send_message(
                        embed=error_embed,
                        ephemeral=True
                    )
                except discord.errors.NotFound:
                    try:
                        await interaction.followup.send(
                            embed=error_embed,
                            ephemeral=True
                        )
                    except discord.errors.NotFound:
                        print(f"[TEMPVOICE] Failed to send invalid limit message")
                return
            
            channel = interaction.guild.get_channel(self.channel_data.channel_id)
            if channel:
                await channel.edit(user_limit=limit)
                self.channel_data.user_limit = limit
                
                # Create success embed with green color
                limit_text = "unlimited" if limit == 0 else str(limit)
                success_embed = discord.Embed(
                    title="✅ Success",
                    description=self.cog.loc_helper.get_text("TEMPVOICE_LIMIT_SET", interaction.user.id, limit=limit_text),
                    color=0x00FF00  # Green color for success
                )
                
                # Add bot branding footer
                config = load_config()
                success_embed.set_footer(
                    text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                    icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
                )
                
                try:
                    # Send separate ephemeral success message (don't edit main interface)
                    await interaction.response.send_message(
                        embed=success_embed,
                        ephemeral=True,
                        delete_after=30  # Auto-delete after 30 seconds
                    )
                except discord.errors.NotFound:
                    try:
                        await interaction.followup.send(
                            embed=success_embed,
                            ephemeral=True,
                            delete_after=30
                        )
                    except discord.errors.NotFound:
                        print(f"[TEMPVOICE] ❌ Failed to send limit change success message")
                        return
                
                print(f"[TEMPVOICE] ✅ LIMIT CHANGE SUCCESS | User: {interaction.user.name} | New Limit: {limit_text}")
            else:
                try:
                    await interaction.response.send_message(
                        self.cog.loc_helper.get_text("TEMPVOICE_CHANNEL_NOT_FOUND", interaction.user.id),
                        ephemeral=True
                    )
                except discord.errors.NotFound:
                    try:
                        await interaction.followup.send(
                            self.cog.loc_helper.get_text("TEMPVOICE_CHANNEL_NOT_FOUND", interaction.user.id),
                            ephemeral=True
                        )
                    except discord.errors.NotFound:
                        print(f"[TEMPVOICE] Failed to send channel not found message")
        except ValueError:
            # Create error embed with red color
            error_embed = discord.Embed(
                title="❌ Error",
                description=self.cog.loc_helper.get_text("TEMPVOICE_INVALID_LIMIT", interaction.user.id),
                color=0xFF0000  # Red color for error
            )
            
            # Add bot branding footer
            config = load_config()
            error_embed.set_footer(
                text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
            )
            
            try:
                await interaction.response.send_message(
                    embed=error_embed,
                    ephemeral=True
                )
            except discord.errors.NotFound:
                try:
                    await interaction.followup.send(
                        embed=error_embed,
                        ephemeral=True
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] Failed to send invalid limit message")
        except Exception as e:
            try:
                await interaction.response.send_message(
                    self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error=str(e)),
                    ephemeral=True
                )
            except discord.errors.NotFound:
                try:
                    await interaction.followup.send(
                        self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error=str(e)),
                        ephemeral=True
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] Failed to send error message: {e}")


class UserActionSelectView(discord.ui.View):
    """View containing user select dropdown for user actions (trust, untrust, kick, block, unblock)"""
    
    def __init__(self, cog, channel_data: TempChannelData, action: str):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.cog = cog
        self.channel_data = channel_data
        self.action = action
        
        # Add the user select dropdown
        self.add_item(UserActionSelect(cog, channel_data, action))
    
    async def on_timeout(self):
        """Called when the view times out."""
        # Disable all items when timeout occurs
        for item in self.children:
            item.disabled = True


class UserActionSelect(discord.ui.Select):
    """User select dropdown for user actions"""
    
    def __init__(self, cog, channel_data: TempChannelData, action: str):
        self.cog = cog
        self.channel_data = channel_data
        self.action = action
        
        # Set placeholder based on action
        action_emojis = {
            "trust": "✅",
            "untrust": "❌", 
            "kick": "👢",
            "block": "🚫",
            "unblock": "✅"
        }
        
        placeholder = f"{action_emojis.get(action, '👤')} Select user to {action}"
        
        super().__init__(
            select_type=discord.ComponentType.user_select,
            placeholder=placeholder,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle user selection for actions"""
        user = self.values[0]  # Get selected user
        
        # Log the action attempt
        print(f"[TEMPVOICE] 🔵 USER ACTION START | User: {interaction.user.name} ({interaction.user.id}) | Action: {self.action} | Target: {user.name} ({user.id}) | Channel: {self.channel_data.channel_id}")
        
        # Check if trying to action the owner (for kick/block)
        if user.id == self.channel_data.owner_id and self.action in ['kick', 'block']:
            try:
                await interaction.response.send_message(
                    self.cog.loc_helper.get_text("TEMPVOICE_CANNOT_ACTION_OWNER", interaction.user.id),
                    ephemeral=True
                )
            except discord.errors.NotFound:
                try:
                    await interaction.followup.send(
                        self.cog.loc_helper.get_text("TEMPVOICE_CANNOT_ACTION_OWNER", interaction.user.id),
                        ephemeral=True
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] ❌ Failed to send cannot action owner message")
            print(f"[TEMPVOICE] ❌ USER ACTION FAILED | Cannot {self.action} owner | Target: {user.name}")
            return
        
        try:
            channel = interaction.guild.get_channel(self.channel_data.channel_id)
            if not channel:
                try:
                    await interaction.response.send_message(
                        self.cog.loc_helper.get_text("TEMPVOICE_CHANNEL_NOT_FOUND", interaction.user.id),
                        ephemeral=True
                    )
                except discord.errors.NotFound:
                    try:
                        await interaction.followup.send(
                            self.cog.loc_helper.get_text("TEMPVOICE_CHANNEL_NOT_FOUND", interaction.user.id),
                            ephemeral=True
                        )
                    except discord.errors.NotFound:
                        print(f"[TEMPVOICE] ❌ Failed to send channel not found message")
                print(f"[TEMPVOICE] ❌ USER ACTION FAILED | Channel not found | Channel ID: {self.channel_data.channel_id}")
                return
            
            # Perform the user action
            result = await self.cog._handle_user_action(channel, user, self.action, self.channel_data)
            
            if result is True:
                # Create success embed for the action
                action_key = f"TEMPVOICE_{self.action.upper()}_SUCCESS"
                
                # Create success embed with green color
                config = load_config()
                success_embed = discord.Embed(
                    title="✅ Success",
                    description=self.cog.loc_helper.get_text(action_key, interaction.user.id, user=user.mention),
                    color=0x00FF00  # Green color for success
                )
                
                # Add bot branding footer
                success_embed.set_footer(
                    text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                    icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
                )
                
                try:
                    # Edit the dropdown message to show success embed
                    await interaction.response.edit_message(
                        embed=success_embed,
                        view=None,  # Remove the dropdown
                        delete_after=30  # Auto-delete after 30 seconds
                    )
                except discord.errors.NotFound:
                    try:
                        await interaction.edit_original_response(
                            embed=success_embed,
                            view=None,
                            delete_after=30
                        )
                    except discord.errors.NotFound:
                        print(f"[TEMPVOICE] ❌ Failed to edit message with success embed")
                
                print(f"[TEMPVOICE] ✅ USER ACTION SUCCESS | Action: {self.action} | Target: {user.name} | Channel: {channel.name}")
            elif isinstance(result, str):
                # Handle specific error messages (like TEMPVOICE_USER_NOT_IN_CHANNEL)
                # Create error embed
                error_embed = self.cog.loc_helper.create_error_embed(
                    title_key="tempvoice_error_title",
                    description_key=result,
                    user_id=interaction.user.id,
                    user=user.mention
                )
                
                try:
                    # Edit the original message instead of sending new one
                    await interaction.response.edit_message(
                        embed=error_embed,
                        view=None,  # Remove the dropdown
                        delete_after=30  # Auto-delete after 30 seconds
                    )
                except discord.errors.NotFound:
                    try:
                        await interaction.edit_original_response(
                            embed=error_embed,
                            view=None,
                            delete_after=30
                        )
                    except discord.errors.NotFound:
                        print(f"[TEMPVOICE] ❌ Failed to edit message with error embed")
                
                print(f"[TEMPVOICE] ❌ USER ACTION FAILED | Action: {self.action} | Target: {user.name} | Reason: {result}")
            else:
                # Handle generic failure (result is False)
                # Create error embed
                error_embed = self.cog.loc_helper.create_error_embed(
                    title_key="tempvoice_error_title",
                    description_key="TEMPVOICE_ACTION_FAILED",
                    user_id=interaction.user.id
                )
                
                try:
                    # Edit the original message instead of sending new one
                    await interaction.response.edit_message(
                        embed=error_embed,
                        view=None,  # Remove the dropdown
                        delete_after=30  # Auto-delete after 30 seconds
                    )
                except discord.errors.NotFound:
                    try:
                        await interaction.edit_original_response(
                            embed=error_embed,
                            view=None,
                            delete_after=30
                        )
                    except discord.errors.NotFound:
                        print(f"[TEMPVOICE] ❌ Failed to edit message with error embed")
                
                print(f"[TEMPVOICE] ❌ USER ACTION FAILED | Action: {self.action} | Target: {user.name} | Reason: Action handler returned False")
        except Exception as e:
            # Create error embed for exceptions
            error_embed = self.cog.loc_helper.create_error_embed(
                title_key="tempvoice_error_title",
                description_key="TEMPVOICE_ERROR",
                user_id=interaction.user.id,
                error=str(e)
            )
            
            try:
                # Edit the original message instead of sending new one
                await interaction.response.edit_message(
                    embed=error_embed,
                    view=None,  # Remove the dropdown
                    delete_after=30  # Auto-delete after 30 seconds
                )
            except discord.errors.NotFound:
                try:
                    await interaction.edit_original_response(
                        embed=error_embed,
                        view=None,
                        delete_after=30
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] ❌ Failed to edit message with error embed: {e}")
            
            print(f"[TEMPVOICE] ❌ USER ACTION ERROR | Action: {self.action} | Target: {user.name} | Error: {str(e)}")


class TransferOwnershipSelectView(discord.ui.View):
    """View containing user select dropdown for ownership transfer"""
    
    def __init__(self, cog, channel_data: TempChannelData):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.cog = cog
        self.channel_data = channel_data
        
        # Add the user select dropdown
        self.add_item(TransferOwnershipSelect(cog, channel_data))
    
    async def on_timeout(self):
        """Called when the view times out."""
        # Disable all items when timeout occurs
        for item in self.children:
            item.disabled = True


class TransferOwnershipSelect(discord.ui.Select):
    """User select dropdown for ownership transfer"""
    
    def __init__(self, cog, channel_data: TempChannelData):
        self.cog = cog
        self.channel_data = channel_data
        
        super().__init__(
            select_type=discord.ComponentType.user_select,
            placeholder="🔄 Select new channel owner",
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle user selection for ownership transfer"""
        user = self.values[0]  # Get selected user
        
        # Log the transfer attempt
        print(f"[TEMPVOICE] 🔵 OWNERSHIP TRANSFER START | User: {interaction.user.name} ({interaction.user.id}) | New Owner: {user.name} ({user.id}) | Channel: {self.channel_data.channel_id}")
        
        # Check if user is already the owner
        if user.id == self.channel_data.owner_id:
            # Create error embed
            error_embed = self.cog.loc_helper.create_error_embed(
                title_key="tempvoice_error_title",
                description_key="TEMPVOICE_ALREADY_OWNER",
                user_id=interaction.user.id
            )
            
            try:
                # Edit the original message instead of sending new one
                await interaction.response.edit_message(
                    embed=error_embed,
                    view=None,  # Remove the dropdown
                    delete_after=30  # Auto-delete after 30 seconds
                )
            except discord.errors.NotFound:
                try:
                    await interaction.edit_original_response(
                        embed=error_embed,
                        view=None,
                        delete_after=30
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] ❌ Failed to edit message with already owner error")
            
            print(f"[TEMPVOICE] ❌ OWNERSHIP TRANSFER FAILED | User is already owner | User: {user.name}")
            return
        
        # Check if the target user is in the voice channel
        channel = interaction.guild.get_channel(self.channel_data.channel_id)
        if not channel:
            # Create error embed
            error_embed = self.cog.loc_helper.create_error_embed(
                title_key="tempvoice_error_title",
                description_key="TEMPVOICE_CHANNEL_NOT_FOUND",
                user_id=interaction.user.id
            )
            
            try:
                await interaction.response.edit_message(
                    embed=error_embed,
                    view=None,
                    delete_after=30
                )
            except discord.errors.NotFound:
                try:
                    await interaction.edit_original_response(
                        embed=error_embed,
                        view=None,
                        delete_after=30
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] ❌ Failed to edit message with channel not found error")
            
            print(f"[TEMPVOICE] ❌ OWNERSHIP TRANSFER FAILED | Channel not found | Channel ID: {self.channel_data.channel_id}")
            return
        
        # Check if the target user is in the voice channel
        if user not in channel.members:
            # Create error embed
            error_embed = self.cog.loc_helper.create_error_embed(
                title_key="tempvoice_error_title",
                description_key="TEMPVOICE_USER_NOT_IN_CHANNEL",
                user_id=interaction.user.id
            )
            
            try:
                await interaction.response.edit_message(
                    embed=error_embed,
                    view=None,
                    delete_after=30
                )
            except discord.errors.NotFound:
                try:
                    await interaction.edit_original_response(
                        embed=error_embed,
                        view=None,
                        delete_after=30
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] ❌ Failed to edit message with user not in channel error")
            
            print(f"[TEMPVOICE] ❌ OWNERSHIP TRANSFER FAILED | User not in channel | User: {user.name}")
            return
        
        try:
            # Update the channel data with new owner
            old_owner_id = self.channel_data.owner_id
            self.channel_data.owner_id = user.id
            
            # Channel data is automatically updated in memory (self.cog.active_channels)
            # No need to save to file as temp channels are stored in memory
            
            # Update channel permissions for new owner
            await self.cog._update_channel_permissions(channel, user, self.channel_data)
            
            # Create success embed
            config = load_config()
            embed_color = 0x00ff00  # Green color for success
            
            success_embed = discord.Embed(
                title="🔄 Ownership Transferred Successfully",
                description=f"✅ Channel ownership has been transferred to <@{user.id}>!",
                color=embed_color
            )
            
            success_embed.set_footer(
                text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
            )
            
            try:
                await interaction.response.edit_message(
                    embed=success_embed,
                    view=None,
                    delete_after=30
                )
            except discord.errors.NotFound:
                try:
                    await interaction.edit_original_response(
                        embed=success_embed,
                        view=None,
                        delete_after=30
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] ❌ Failed to edit message with transfer success")
            
            print(f"[TEMPVOICE] ✅ OWNERSHIP TRANSFER SUCCESS | Old Owner: {interaction.user.name} ({old_owner_id}) | New Owner: {user.name} ({user.id}) | Channel: {channel.name}")
            
        except Exception as e:
            # Create error embed
            error_embed = self.cog.loc_helper.create_error_embed(
                title_key="tempvoice_error_title",
                description_key="TEMPVOICE_TRANSFER_FAILED",
                user_id=interaction.user.id
            )
            
            try:
                await interaction.response.edit_message(
                    embed=error_embed,
                    view=None,
                    delete_after=30
                )
            except discord.errors.NotFound:
                try:
                    await interaction.edit_original_response(
                        embed=error_embed,
                        view=None,
                        delete_after=30
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] ❌ Failed to edit message with transfer error")
            
            print(f"[TEMPVOICE] ❌ OWNERSHIP TRANSFER FAILED | Error: {str(e)} | User: {interaction.user.name} | Target: {user.name}")
            logger.error(f"[TEMPVOICE] 🔍 TRANSFER ERROR TRACEBACK:", exc_info=True)


class InviteUserSelectView(discord.ui.View):
    """View containing user select dropdown for inviting users via DM"""
    
    def __init__(self, cog, channel_data: TempChannelData):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.cog = cog
        self.channel_data = channel_data
        
        # Add the user select dropdown
        self.add_item(InviteUserSelect(cog, channel_data))
    
    async def on_timeout(self):
        """Called when the view times out."""
        # Disable all items when timeout occurs
        for item in self.children:
            item.disabled = True


class InviteUserSelect(discord.ui.Select):
    """User select dropdown for inviting users via DM"""
    
    def __init__(self, cog, channel_data: TempChannelData):
        self.cog = cog
        self.channel_data = channel_data
        
        super().__init__(
            select_type=discord.ComponentType.user_select,
            placeholder="📧 Select users to invite to your voice channel",
            min_values=1,
            max_values=5  # Allow selecting up to 5 users at once
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle user selection for DM invites"""
        selected_users = self.values  # Get all selected users
        
        # Log the invite attempt
        user_names = [user.name for user in selected_users]
        print(f"[TEMPVOICE] 📧 DM INVITE START | User: {interaction.user.name} ({interaction.user.id}) | Targets: {', '.join(user_names)} | Channel: {self.channel_data.channel_id}")
        
        try:
            channel = interaction.guild.get_channel(self.channel_data.channel_id)
            if not channel:
                # Create error embed
                error_embed = self.cog.loc_helper.create_error_embed(
                    title_key="tempvoice_error_title",
                    description_key="TEMPVOICE_CHANNEL_NOT_FOUND",
                    user_id=interaction.user.id
                )
                
                try:
                    # Edit the original message instead of sending new one
                    await interaction.response.edit_message(
                        embed=error_embed,
                        view=None,  # Remove the dropdown
                        delete_after=30  # Auto-delete after 30 seconds
                    )
                except discord.errors.NotFound:
                    try:
                        await interaction.edit_original_response(
                            embed=error_embed,
                            view=None,
                            delete_after=30
                        )
                    except discord.errors.NotFound:
                        print(f"[TEMPVOICE] ❌ Failed to edit message with channel not found error")
                
                print(f"[TEMPVOICE] ❌ DM INVITE FAILED | Channel not found | Channel ID: {self.channel_data.channel_id}")
                return
            
            # Create invite link
            invite = await channel.create_invite(max_age=18000, max_uses=10, reason="TempVoice DM invite")
            
            successful_invites = []
            failed_invites = []
            
            # Keep track of successful user objects for mentions
            successful_user_objects = []
            
            # Send DM invites to selected users
            for user in selected_users:
                try:
                    # Skip if user is a bot
                    if user.bot:
                        failed_invites.append(f"{user.display_name} (bot)")
                        continue
                    
                    # Skip if user is already in the channel
                    if user in channel.members:
                        failed_invites.append(f"{user.display_name} (already in channel)")
                        continue
                    
                    # Create DM embed
                    config = load_config()
                    embed_color = int(config.get("DISCORD_EMBED_COLOR", "714C35"), 16)
                    
                    dm_embed = discord.Embed(
                        title=self.cog.loc_helper.get_text("TEMPVOICE_DM_INVITE_TITLE", user.id),
                        description=self.cog.loc_helper.get_text("TEMPVOICE_DM_INVITE_DESC", user.id, user=interaction.user.display_name, channel=f"<#{channel.id}>", guild=interaction.guild.name),
                        color=embed_color
                    )
                    
                    dm_embed.add_field(
                        name=self.cog.loc_helper.get_text("TEMPVOICE_DM_INVITE_JOIN_FIELD", user.id),
                        value=self.cog.loc_helper.get_text("TEMPVOICE_DM_INVITE_JOIN_VALUE", user.id, invite_url=invite.url),
                        inline=False
                    )
                    
                    dm_embed.set_footer(
                        text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                        icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
                    )
                    
                    # Send DM
                    await user.send(embed=dm_embed)
                    successful_invites.append(user.display_name)
                    successful_user_objects.append(user)  # Keep user object for mentions
                    
                    # Log successful DM invite
                    print(f"[TEMPVOICE] 📧 DM INVITE SENT | From: {interaction.user.name} | To: {user.name} | Channel: {channel.name}")
                    
                except discord.Forbidden:
                    failed_invites.append(f"{user.display_name} (DMs disabled)")
                except Exception as e:
                    failed_invites.append(f"{user.display_name} (error: {str(e)[:50]})")
            
            # Create response message with user mentions and channel mention
            response_parts = []
            
            if successful_invites:
                # Create user mentions for successful invites
                user_mentions = [f"<@{user.id}>" for user in successful_user_objects]
                response_parts.append(f"✅ **Invites sent to:** {', '.join(user_mentions)} for channel <#{channel.id}>")
            
            if failed_invites:
                response_parts.append(f"❌ **Failed to invite:** {', '.join(failed_invites)}")
            
            if not response_parts:
                response_parts.append("❌ No invites were sent.")
            
            # Create response embed
            config = load_config()
            embed_color = int(config.get("DISCORD_EMBED_COLOR", "714C35"), 16)
            
            if successful_invites and not failed_invites:
                # All invites successful - green color
                embed_color = 0x00ff00
                embed_title = "📧 Invites Sent Successfully"
                # Use user mentions and channel mention in embed description
                user_mentions = [f"<@{user.id}>" for user in successful_user_objects]
                embed_description = f"✅ **Invites sent to:** {', '.join(user_mentions)} for channel <#{channel.id}>"
            elif failed_invites and not successful_invites:
                # All invites failed - red color
                embed_color = 0xff0000
                embed_title = "📧 Invite Failed"
                embed_description = f"❌ **Failed to invite:** {', '.join(failed_invites)}"
            elif successful_invites and failed_invites:
                # Mixed results - orange color
                embed_color = 0xffa500
                embed_title = "📧 Invite Results"
                user_mentions = [f"<@{user.id}>" for user in successful_user_objects]
                embed_description = f"✅ **Invites sent to:** {', '.join(user_mentions)} for channel <#{channel.id}>\n\n❌ **Failed to invite:** {', '.join(failed_invites)}"
            else:
                # No invites sent - red color
                embed_color = 0xff0000
                embed_title = "📧 No Invites Sent"
                embed_description = "❌ No invites were sent."
            
            response_embed = discord.Embed(
                title=embed_title,
                description=embed_description,
                color=embed_color
            )
            
            response_embed.set_footer(
                text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
            )
            
            try:
                # Edit the original message instead of sending new one
                await interaction.response.edit_message(
                    embed=response_embed,
                    view=None,  # Remove the dropdown
                    delete_after=30  # Auto-delete after 30 seconds
                )
            except discord.errors.NotFound:
                try:
                    await interaction.edit_original_response(
                        embed=response_embed,
                        view=None,
                        delete_after=30
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] ❌ Failed to edit message with invite summary")
            
            # Log invite summary
            print(f"[TEMPVOICE] 📧 INVITE SUMMARY | User: {interaction.user.name} | Successful: {len(successful_invites)} | Failed: {len(failed_invites)}")
            
        except Exception as e:
            # Create error embed
            error_embed = self.cog.loc_helper.create_error_embed(
                title_key="tempvoice_error_title",
                description_key="TEMPVOICE_ERROR",
                user_id=interaction.user.id,
                error=str(e)
            )
            
            try:
                # Edit the original message instead of sending new one
                await interaction.response.edit_message(
                    embed=error_embed,
                    view=None,  # Remove the dropdown
                    delete_after=30  # Auto-delete after 30 seconds
                )
            except discord.errors.NotFound:
                try:
                    await interaction.edit_original_response(
                        embed=error_embed,
                        view=None,
                        delete_after=30
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] ❌ Failed to edit message with error: {e}")
            
            print(f"[TEMPVOICE] ❌ DM INVITE ERROR | User: {interaction.user.name} | Error: {str(e)}")








class PrivacyDropdownView(discord.ui.View):
    """View containing the privacy dropdown menu."""
    
    def __init__(self, cog, channel_data: TempChannelData):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.cog = cog
        self.channel_data = channel_data
        
        # Add the privacy dropdown
        self.add_item(PrivacySelect(cog, channel_data))
    
    async def on_timeout(self):
        """Called when the view times out."""
        # Disable all items when timeout occurs
        for item in self.children:
            item.disabled = True


class RegionDropdownView(discord.ui.View):
    """View containing the region dropdown menu."""
    
    def __init__(self, cog, channel_data: TempChannelData):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.cog = cog
        self.channel_data = channel_data
        
        # Add the region dropdown
        self.add_item(RegionSelect(cog, channel_data))
    
    async def on_timeout(self):
        """Called when the view times out."""
        # Disable all items when timeout occurs
        for item in self.children:
            item.disabled = True


class RegionSelect(discord.ui.Select):
    """Dropdown select for voice channel regions."""
    
    def __init__(self, cog, channel_data: TempChannelData):
        self.cog = cog
        self.channel_data = channel_data
        
        # Define Discord voice regions (only valid API values)
        options = [
            discord.SelectOption(
                label="Automatic",
                description="Let Discord choose the best region",
                emoji="🌐",
                value="auto"
            ),
            discord.SelectOption(
                label="US West",
                description="United States West Coast",
                emoji="🇺🇸",
                value="us-west"
            ),
            discord.SelectOption(
                label="US East",
                description="United States East Coast",
                emoji="🇺🇸",
                value="us-east"
            ),
            discord.SelectOption(
                label="US Central",
                description="United States Central",
                emoji="🇺🇸",
                value="us-central"
            ),
            discord.SelectOption(
                label="US South",
                description="United States South",
                emoji="🇺🇸",
                value="us-south"
            ),
            discord.SelectOption(
                label="Rotterdam",
                description="Europe (Rotterdam)",
                emoji="🇳🇱",
                value="rotterdam"
            ),
            discord.SelectOption(
                label="Singapore",
                description="Asia Pacific (Singapore)",
                emoji="🇸🇬",
                value="singapore"
            ),
            discord.SelectOption(
                label="Sydney",
                description="Australia (Sydney)",
                emoji="🇦🇺",
                value="sydney"
            ),
            discord.SelectOption(
                label="Japan",
                description="Asia Pacific (Japan)",
                emoji="🇯🇵",
                value="japan"
            ),
            discord.SelectOption(
                label="Hong Kong",
                description="Asia Pacific (Hong Kong)",
                emoji="🇭🇰",
                value="hongkong"
            ),
            discord.SelectOption(
                label="Brazil",
                description="South America (Brazil)",
                emoji="🇧🇷",
                value="brazil"
            ),
            discord.SelectOption(
                label="India",
                description="Asia Pacific (India)",
                emoji="🇮🇳",
                value="india"
            ),
            discord.SelectOption(
                label="South Korea",
                description="Asia Pacific (South Korea)",
                emoji="🇰🇷",
                value="south-korea"
            ),
            discord.SelectOption(
                label="South Africa",
                description="Africa (South Africa)",
                emoji="🇿🇦",
                value="southafrica"
            )
        ]
        
        super().__init__(
            placeholder="Choose a voice region...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle region selection."""
        try:
            channel = interaction.guild.get_channel(self.channel_data.channel_id)
            if not channel:
                # Create error embed
                error_embed = self.cog.loc_helper.create_error_embed(
                    title_key="tempvoice_error_title",
                    description_key="TEMPVOICE_CHANNEL_NOT_FOUND",
                    user_id=interaction.user.id
                )
                
                try:
                    # Edit the original message instead of sending new one
                    await interaction.response.edit_message(
                        embed=error_embed,
                        view=None,  # Remove the dropdown
                        delete_after=30  # Auto-delete after 30 seconds
                    )
                except discord.errors.NotFound:
                    try:
                        await interaction.edit_original_response(
                            embed=error_embed,
                            view=None,
                            delete_after=30
                        )
                    except discord.errors.NotFound:
                        print(f"[TEMPVOICE] ❌ Failed to edit message with channel not found error")
                
                print(f"[TEMPVOICE] ❌ REGION CHANGE FAILED | Channel not found | Channel ID: {self.channel_data.channel_id}")
                return
            
            selected_region = self.values[0]
            region_name = next(option.label for option in self.options if option.value == selected_region)
            
            # Log region change attempt
            print(f"[TEMPVOICE] 🌍 REGION CHANGE | User: {interaction.user.name} ({interaction.user.id}) | Channel: {channel.name} ({channel.id}) | From: {channel.rtc_region or 'auto'} | To: {selected_region}")
            
            # Apply region change
            if selected_region == "auto":
                await channel.edit(rtc_region=None)
            else:
                await channel.edit(rtc_region=selected_region)
            
            # Send success message using localization
            success_message = self.cog.loc_helper.get_text("TEMPVOICE_REGION_CHANGED", interaction.user.id, region=region_name)
            
            config = load_config()
            
            embed = discord.Embed(
                title="🌍 Region Changed Successfully",
                description=success_message,
                color=0x00FF00  # Green color for success
            )
            
            embed.set_footer(
                text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
            )
            
            try:
                # Edit the original dropdown message with success embed
                await interaction.response.edit_message(
                    embed=embed,
                    view=None,  # Remove the dropdown
                    delete_after=30  # Auto-delete after 30 seconds
                )
            except discord.errors.NotFound:
                try:
                    await interaction.edit_original_response(
                        embed=embed,
                        view=None,
                        delete_after=30
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] ❌ Failed to edit message with region success")
            
            # Log successful region change
            print(f"[TEMPVOICE] ✅ REGION CHANGED | User: {interaction.user.name} | Channel: {channel.name} | New Region: {selected_region}")
            
        except discord.Forbidden:
            # Create error embed
            error_embed = self.cog.loc_helper.create_error_embed(
                title_key="tempvoice_error_title",
                description_key="TEMPVOICE_NO_PERMISSION",
                user_id=interaction.user.id
            )
            
            try:
                # Edit the original dropdown message with error embed
                await interaction.response.edit_message(
                    embed=error_embed,
                    view=None,  # Remove the dropdown
                    delete_after=30  # Auto-delete after 30 seconds
                )
            except discord.errors.NotFound:
                try:
                    await interaction.edit_original_response(
                        embed=error_embed,
                        view=None,
                        delete_after=30
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] ❌ Failed to edit message with permission error")
            
            print(f"[TEMPVOICE] ❌ REGION CHANGE FORBIDDEN | User: {interaction.user.name} | Channel: {self.channel_data.channel_id}")
            
        except Exception as e:
            # Create error embed
            error_embed = self.cog.loc_helper.create_error_embed(
                title_key="tempvoice_error_title",
                description_key="TEMPVOICE_REGION_CHANGE_FAILED",
                user_id=interaction.user.id,
                error=str(e)
            )
            
            try:
                # Edit the original dropdown message with error embed
                await interaction.response.edit_message(
                    embed=error_embed,
                    view=None,  # Remove the dropdown
                    delete_after=30  # Auto-delete after 30 seconds
                )
            except discord.errors.NotFound:
                try:
                    await interaction.edit_original_response(
                        embed=error_embed,
                        view=None,
                        delete_after=30
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] ❌ Failed to edit message with region change error")
            
            print(f"[TEMPVOICE] ❌ REGION CHANGE ERROR | User: {interaction.user.name} | Error: {str(e)}")


class PrivacySelect(discord.ui.Select):
    """Dropdown select for privacy options."""
    
    def __init__(self, cog, channel_data: TempChannelData):
        self.cog = cog
        self.channel_data = channel_data
        
        # Define privacy options
        options = [
            discord.SelectOption(
                label="Lock",
                description="Only trusted users can join your voice channel",
                emoji="🔒",
                value="lock"
            ),
            discord.SelectOption(
                label="Unlock",
                description="Everyone can join your voice channel",
                emoji="🔓",
                value="unlock"
            ),
            discord.SelectOption(
                label="Invisible",
                description="Only trusted users can see your voice channel",
                emoji="🙈",
                value="invisible"
            ),
            discord.SelectOption(
                label="Visible",
                description="Everyone can see your voice channel",
                emoji="👁️",
                value="visible"
            ),
            discord.SelectOption(
                label="Close Chat",
                description="Only trusted users can text in your channel",
                emoji="💬",
                value="close_chat"
            ),
            discord.SelectOption(
                label="Open Chat",
                description="Everyone can text in your channel",
                emoji="💭",
                value="open_chat"
            )
        ]
        
        super().__init__(
            placeholder="Choose a privacy option...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle privacy option selection."""
        try:
            channel = interaction.guild.get_channel(self.channel_data.channel_id)
            if not channel:
                # Create error embed
                error_embed = self.cog.loc_helper.create_error_embed(
                    title_key="tempvoice_error_title",
                    description_key="TEMPVOICE_CHANNEL_NOT_FOUND",
                    user_id=interaction.user.id
                )
                
                try:
                    # Edit the original message instead of sending new one
                    await interaction.response.edit_message(
                        embed=error_embed,
                        view=None,  # Remove the dropdown
                        delete_after=30  # Auto-delete after 30 seconds
                    )
                except discord.errors.NotFound:
                    try:
                        await interaction.edit_original_response(
                            embed=error_embed,
                            view=None,
                            delete_after=30
                        )
                    except discord.errors.NotFound:
                        print(f"[TEMPVOICE] ❌ Failed to edit message with channel not found error")
                return
            
            selected_option = self.values[0]
            
            # Get guild config for base permissions
            guild_config = self.cog._get_guild_config(interaction.guild.id)
            
            # Get fresh channel data from active_channels to ensure we have latest trusted_users
            fresh_channel_data = self.cog.active_channels.get(self.channel_data.channel_id)
            if not fresh_channel_data:
                # Create error embed
                error_embed = self.cog.loc_helper.create_error_embed(
                    title_key="tempvoice_error_title",
                    description_key="TEMPVOICE_CHANNEL_NOT_FOUND",
                    user_id=interaction.user.id
                )
                
                try:
                    # Edit the original message instead of sending new one
                    await interaction.response.edit_message(
                        embed=error_embed,
                        view=None,  # Remove the dropdown
                        delete_after=30  # Auto-delete after 30 seconds
                    )
                except discord.errors.NotFound:
                    try:
                        await interaction.edit_original_response(
                            embed=error_embed,
                            view=None,
                            delete_after=30
                        )
                    except discord.errors.NotFound:
                        print(f"[TEMPVOICE] ❌ Failed to edit message with channel data not found error")
                return
            
            # Get trusted users and owner for permission checks (using fresh data)
            trusted_users = list(fresh_channel_data.trusted_users)  # Convert set to list
            owner_id = fresh_channel_data.owner_id
            owner = interaction.guild.get_member(owner_id)
            
            # Apply privacy settings using helper function
            overwrites = apply_privacy_overwrites(
                base_overwrites=channel.overwrites,
                privacy_action=selected_option,
                guild=interaction.guild,
                allowed_roles=guild_config.allowed_roles,
                owner=owner,
                trusted_users=trusted_users
            )
            
            # Apply the permission changes
            await channel.edit(overwrites=overwrites)
            
            # Create confirmation embed
            config = load_config()
            embed_color = int(config.get("DISCORD_EMBED_COLOR", "714C35"), 16)
            
            embed = discord.Embed(
                title="✅ Privacy Updated",
                description=f"Successfully applied **{selected_option.replace('_', ' ').title()}** to your channel!",
                color=embed_color
            )
            
            embed.set_footer(
                text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
            )
            
            try:
                # Send a separate ephemeral success message instead of editing the original interface
                await interaction.response.send_message(
                    embed=embed,
                    ephemeral=True,
                    delete_after=30  # Auto-delete after 30 seconds
                )
            except discord.errors.NotFound:
                try:
                    await interaction.followup.send(
                        embed=embed,
                        ephemeral=True,
                        delete_after=30
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] ❌ Failed to send privacy success message")
            
            # Log the privacy change
            print(f"[TEMPVOICE] 🔒 PRIVACY CHANGED | User: {interaction.user.name} ({interaction.user.id}) | Channel: {channel.name} ({channel.id}) | Option: {selected_option} | Guild: {interaction.guild.name}")
            
        except Exception as e:
            # Create error embed
            error_embed = self.cog.loc_helper.create_error_embed(
                title_key="tempvoice_error_title",
                description_key="TEMPVOICE_ERROR",
                user_id=interaction.user.id,
                error=str(e)
            )
            
            try:
                # Edit the original message instead of sending new one
                await interaction.response.edit_message(
                    embed=error_embed,
                    view=None,  # Remove the dropdown
                    delete_after=30  # Auto-delete after 30 seconds
                )
            except discord.errors.NotFound:
                try:
                    await interaction.edit_original_response(
                        embed=error_embed,
                        view=None,
                        delete_after=30
                    )
                except discord.errors.NotFound:
                    print(f"[TEMPVOICE] ❌ Failed to edit message with privacy error")
            
            print(f"[TEMPVOICE] ❌ PRIVACY DROPDOWN ERROR | User: {interaction.user.name} | Option: {selected_option} | Error: {str(e)}")


class TempVoiceControlPanel(discord.ui.View):
    """Main control panel for temporary voice channels"""
    def __init__(self, cog, channel_data: TempChannelData):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_data = channel_data
    
    def _can_manage_channel(self, user_id: int) -> bool:
        """Check if user can manage the channel"""
        return (user_id == self.channel_data.owner_id or 
                user_id in self.channel_data.trusted_users)
    
    async def _safe_interaction_response(self, interaction: discord.Interaction, message: str, ephemeral: bool = True, edit: bool = False, embed: discord.Embed = None, view: discord.ui.View = None, delete_after: int = None):
        """Safely send interaction response with proper error handling"""
        try:
            if edit:
                if embed and view:
                    await interaction.response.edit_message(embed=embed, view=view, delete_after=delete_after)
                elif embed:
                    await interaction.response.edit_message(embed=embed, view=view, delete_after=delete_after)
                else:
                    await interaction.response.edit_message(content=message, delete_after=delete_after)
            else:
                if embed:
                    await interaction.response.send_message(embed=embed, ephemeral=ephemeral, delete_after=delete_after)
                else:
                    await interaction.response.send_message(message, ephemeral=ephemeral, delete_after=delete_after)
        except discord.errors.NotFound:
            # Interaction expired, try followup
            try:
                if edit:
                    if embed and view:
                        await interaction.edit_original_response(embed=embed, view=view, delete_after=delete_after)
                    elif embed:
                        await interaction.edit_original_response(embed=embed, view=view, delete_after=delete_after)
                    else:
                        await interaction.edit_original_response(content=message, delete_after=delete_after)
                else:
                    if embed:
                        await interaction.followup.send(embed=embed, ephemeral=ephemeral, delete_after=delete_after)
                    else:
                        await interaction.followup.send(message, ephemeral=ephemeral, delete_after=delete_after)
            except discord.errors.NotFound:
                # Both methods failed, log the error
                print(f"[TEMPVOICE] Failed to send interaction response: {message}")
        except Exception as e:
            print(f"[TEMPVOICE] Error in interaction response: {e}")
    
    @discord.ui.button(label="NAME", emoji="🏷️", style=discord.ButtonStyle.secondary, row=0)
    async def name_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not self._can_manage_channel(interaction.user.id):
            # Create permission error embed
            error_embed = self.cog.loc_helper.create_error_embed(
                title_key="tempvoice_error_title",
                description_key="TEMPVOICE_NO_PERMISSION",
                user_id=interaction.user.id
            )
            await self._safe_interaction_response(
                interaction,
                "",
                embed=error_embed,
                ephemeral=True,
                delete_after=10
            )
            return
        
        try:
            modal = ChannelNameModal(self.cog, self.channel_data)
            await interaction.response.send_modal(modal)
        except discord.errors.NotFound:
            await self._safe_interaction_response(
                interaction,
                self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error="Interaction expired")
            )
        except Exception as e:
            await self._safe_interaction_response(
                interaction,
                self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error=str(e))
            )
    
    @discord.ui.button(label="LIMIT", emoji="👥", style=discord.ButtonStyle.secondary, row=0)
    async def limit_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not self._can_manage_channel(interaction.user.id):
            # Create permission error embed
            error_embed = self.cog.loc_helper.create_error_embed(
                title_key="tempvoice_error_title",
                description_key="TEMPVOICE_NO_PERMISSION",
                user_id=interaction.user.id
            )
            await self._safe_interaction_response(
                interaction,
                "",
                embed=error_embed,
                ephemeral=True,
                delete_after=10
            )
            return
        
        try:
            modal = UserLimitModal(self.cog, self.channel_data)
            await interaction.response.send_modal(modal)
        except discord.errors.NotFound:
            await self._safe_interaction_response(
                interaction,
                self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error="Interaction expired")
            )
        except Exception as e:
            await self._safe_interaction_response(
                interaction,
                self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error=str(e))
            )
    
    @discord.ui.button(label="PRIVACY", emoji="🔒", style=discord.ButtonStyle.secondary, row=0)
    async def privacy_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not self._can_manage_channel(interaction.user.id):
            # Create permission error embed
            error_embed = self.cog.loc_helper.create_error_embed(
                title_key="tempvoice_error_title",
                description_key="TEMPVOICE_NO_PERMISSION",
                user_id=interaction.user.id
            )
            await self._safe_interaction_response(
                interaction,
                "",
                embed=error_embed,
                ephemeral=True,
                delete_after=10
            )
            return
        
        try:
            channel = interaction.guild.get_channel(self.channel_data.channel_id)
            if not channel:
                await self._safe_interaction_response(
                    interaction,
                    self.cog.loc_helper.get_text("TEMPVOICE_CHANNEL_NOT_FOUND", interaction.user.id)
                )
                return
            
            # Create privacy dropdown view
            privacy_view = PrivacyDropdownView(self.cog, self.channel_data)
            
            # Create embed for privacy options
            config = load_config()
            embed_color = int(config.get("DISCORD_EMBED_COLOR", "714C35"), 16)
            
            embed = discord.Embed(
                title="🔒 Privacy Settings",
                description="Choose how you want to control access to your temporary voice channel:",
                color=embed_color
            )
            
            embed.add_field(
                name="🔒 Lock/Unlock",
                value="Control who can **join** your voice channel",
                inline=True
            )
            embed.add_field(
                name="👁️ Invisible/Visible",
                value="Control who can **see** your voice channel",
                inline=True
            )
            embed.add_field(
                name="💬 Close/Open Chat",
                value="Control who can **text** in your channel",
                inline=True
            )
            
            embed.set_footer(
                text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
            )
            
            # Send the privacy options message
            await interaction.response.send_message(
                embed=embed,
                view=privacy_view,
                ephemeral=True
            )
            
            # Log the privacy menu access
            print(f"[TEMPVOICE] 🔒 PRIVACY MENU | User: {interaction.user.name} ({interaction.user.id}) | Channel: {channel.name} ({channel.id}) | Guild: {interaction.guild.name}")
            
        except Exception as e:
            await self._safe_interaction_response(
                interaction,
                self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error=str(e))
            )
            print(f"[TEMPVOICE] ❌ PRIVACY MENU ERROR | User: {interaction.user.name} | Error: {str(e)}")
    
    @discord.ui.button(label="REGION", emoji="🌍", style=discord.ButtonStyle.secondary, row=0)
    async def region_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not self._can_manage_channel(interaction.user.id):
            # Create permission error embed
            error_embed = self.cog.loc_helper.create_error_embed(
                title_key="tempvoice_error_title",
                description_key="TEMPVOICE_NO_PERMISSION",
                user_id=interaction.user.id
            )
            await self._safe_interaction_response(
                interaction,
                "",
                embed=error_embed,
                ephemeral=True,
                delete_after=10
            )
            return
        
        try:
            channel = interaction.guild.get_channel(self.channel_data.channel_id)
            if not channel:
                await self._safe_interaction_response(
                    interaction,
                    self.cog.loc_helper.get_text("TEMPVOICE_CHANNEL_NOT_FOUND", interaction.user.id)
                )
                return
            
            # Create region selection dropdown view
            region_view = RegionDropdownView(self.cog, self.channel_data)
            
            # Create embed for region selection
            config = load_config()
            embed_color = int(config.get("DISCORD_EMBED_COLOR", "714C35"), 16)
            
            embed = discord.Embed(
                title="🌍 Voice Channel Region",
                description=self.cog.loc_helper.get_text("TEMPVOICE_REGION_SELECT", interaction.user.id),
                color=embed_color
            )
            
            # Show current region if available
            if hasattr(channel, 'rtc_region') and channel.rtc_region:
                current_region = channel.rtc_region.replace('_', ' ').title()
                embed.add_field(
                    name="Current Region",
                    value=f"📍 {current_region}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Current Region",
                    value="📍 Automatic (Discord chooses best)",
                    inline=False
                )
            
            embed.set_footer(
                text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
            )
            
            # Send the region selection message
            await interaction.response.send_message(
                embed=embed,
                view=region_view,
                ephemeral=True
            )
            
            # Log the region menu access
            print(f"[TEMPVOICE] 🌍 REGION MENU | User: {interaction.user.name} ({interaction.user.id}) | Channel: {channel.name} ({channel.id}) | Guild: {interaction.guild.name}")
            
        except Exception as e:
            await self._safe_interaction_response(
                interaction,
                self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error=str(e))
            )
            print(f"[TEMPVOICE] ❌ REGION MENU ERROR | User: {interaction.user.name} | Error: {str(e)}")
    
    @discord.ui.button(label="TRUST", emoji="✅", style=discord.ButtonStyle.success, row=1)
    async def trust_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.channel_data.owner_id:
            await self._safe_interaction_response(
                interaction,
                self.cog.loc_helper.get_text("TEMPVOICE_OWNER_ONLY", interaction.user.id)
            )
            return
        
        try:
            # Create user selection dropdown view
            user_select_view = UserActionSelectView(self.cog, self.channel_data, "trust")
            
            # Create embed for user selection
            config = load_config()
            embed_color = int(config.get("DISCORD_EMBED_COLOR", "714C35"), 16)
            
            embed = discord.Embed(
                title=self.cog.loc_helper.get_text("TEMPVOICE_TRUST_MENU_TITLE", interaction.user.id),
                description=self.cog.loc_helper.get_text("TEMPVOICE_TRUST_MENU_DESC", interaction.user.id),
                color=embed_color
            )
            
            embed.set_footer(
                text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
            )
            
            # Send the user selection message
            await interaction.response.send_message(
                embed=embed,
                view=user_select_view,
                ephemeral=True
            )
            
            # Log the trust menu access
            print(f"[TEMPVOICE] ✅ TRUST MENU | User: {interaction.user.name} ({interaction.user.id}) | Channel: {self.channel_data.channel_id} | Guild: {interaction.guild.name}")
            
        except Exception as e:
            await self._safe_interaction_response(
                interaction,
                self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error=str(e))
            )
            print(f"[TEMPVOICE] ❌ TRUST MENU ERROR | User: {interaction.user.name} | Error: {str(e)}")
    
    @discord.ui.button(label="UNTRUST", emoji="❌", style=discord.ButtonStyle.danger, row=1)
    async def untrust_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.channel_data.owner_id:
            await self._safe_interaction_response(
                interaction,
                self.cog.loc_helper.get_text("TEMPVOICE_OWNER_ONLY", interaction.user.id)
            )
            return
        
        try:
            # Create user selection dropdown view
            user_select_view = UserActionSelectView(self.cog, self.channel_data, "untrust")
            
            # Create embed for user selection
            config = load_config()
            embed_color = int(config.get("DISCORD_EMBED_COLOR", "714C35"), 16)
            
            embed = discord.Embed(
                title=self.cog.loc_helper.get_text("TEMPVOICE_UNTRUST_MENU_TITLE", interaction.user.id),
                description=self.cog.loc_helper.get_text("TEMPVOICE_UNTRUST_MENU_DESC", interaction.user.id),
                color=embed_color
            )
            
            embed.set_footer(
                text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
            )
            
            # Send the user selection message
            await interaction.response.send_message(
                embed=embed,
                view=user_select_view,
                ephemeral=True
            )
            
            # Log the untrust menu access
            print(f"[TEMPVOICE] ❌ UNTRUST MENU | User: {interaction.user.name} ({interaction.user.id}) | Channel: {self.channel_data.channel_id} | Guild: {interaction.guild.name}")
            
        except Exception as e:
            await self._safe_interaction_response(
                interaction,
                self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error=str(e))
            )
            print(f"[TEMPVOICE] ❌ UNTRUST MENU ERROR | User: {interaction.user.name} | Error: {str(e)}")
    
    @discord.ui.button(label="INVITE", emoji="📧", style=discord.ButtonStyle.secondary, row=1)
    async def invite_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not self._can_manage_channel(interaction.user.id):
            # Create error embed for permission denied
            error_embed = self.cog.create_error_embed(
                description_key="TEMPVOICE_NO_PERMISSION",
                user_id=interaction.user.id
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True, delete_after=10)
            return
        
        try:
            # Create user selection dropdown view for DM invites
            invite_select_view = InviteUserSelectView(self.cog, self.channel_data)
            
            # Create embed for user selection
            config = load_config()
            embed_color = int(config.get("DISCORD_EMBED_COLOR", "714C35"), 16)
            
            embed = discord.Embed(
                title=self.cog.loc_helper.get_text("TEMPVOICE_INVITE_MENU_TITLE_DROPDOWN", interaction.user.id),
                description=self.cog.loc_helper.get_text("TEMPVOICE_INVITE_MENU_DESC_DROPDOWN", interaction.user.id),
                color=embed_color
            )
            
            embed.set_footer(
                text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
            )
            
            # Send the user selection message
            await interaction.response.send_message(
                embed=embed,
                view=invite_select_view,
                ephemeral=True
            )
            
            # Log the invite menu access
            print(f"[TEMPVOICE] 📧 INVITE MENU | User: {interaction.user.name} ({interaction.user.id}) | Channel: {self.channel_data.channel_id} | Guild: {interaction.guild.name}")
            
        except Exception as e:
            await self._safe_interaction_response(
                interaction,
                self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error=str(e))
            )
            print(f"[TEMPVOICE] ❌ INVITE MENU ERROR | User: {interaction.user.name} | Error: {str(e)}")
    
    @discord.ui.button(label="KICK", emoji="👢", style=discord.ButtonStyle.danger, row=1)
    async def kick_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not self._can_manage_channel(interaction.user.id):
            # Create error embed for permission denied
            error_embed = self.cog.create_error_embed(
                description_key="TEMPVOICE_NO_PERMISSION",
                user_id=interaction.user.id
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True, delete_after=10)
            return
        
        try:
            # Create user selection dropdown view
            user_select_view = UserActionSelectView(self.cog, self.channel_data, "kick")
            
            # Create embed for user selection
            config = load_config()
            embed_color = int(config.get("DISCORD_EMBED_COLOR", "714C35"), 16)
            
            embed = discord.Embed(
                title=self.cog.loc_helper.get_text("TEMPVOICE_KICK_MENU_TITLE", interaction.user.id),
                description=self.cog.loc_helper.get_text("TEMPVOICE_KICK_MENU_DESC", interaction.user.id),
                color=embed_color
            )
            
            embed.set_footer(
                text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
            )
            
            # Send the user selection message
            await interaction.response.send_message(
                embed=embed,
                view=user_select_view,
                ephemeral=True
            )
            
            # Log the kick menu access
            print(f"[TEMPVOICE] 👢 KICK MENU | User: {interaction.user.name} ({interaction.user.id}) | Channel: {self.channel_data.channel_id} | Guild: {interaction.guild.name}")
            
        except Exception as e:
            await self._safe_interaction_response(
                interaction,
                self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error=str(e))
            )
            print(f"[TEMPVOICE] ❌ KICK MENU ERROR | User: {interaction.user.name} | Error: {str(e)}")
    
    @discord.ui.button(label="BLOCK", emoji="🚫", style=discord.ButtonStyle.danger, row=2)
    async def block_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not self._can_manage_channel(interaction.user.id):
            # Create error embed for permission denied
            error_embed = self.cog.create_error_embed(
                description_key="TEMPVOICE_NO_PERMISSION",
                user_id=interaction.user.id
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True, delete_after=10)
            return
        
        try:
            # Create user selection dropdown view
            user_select_view = UserActionSelectView(self.cog, self.channel_data, "block")
            
            # Create embed for user selection
            config = load_config()
            embed_color = int(config.get("DISCORD_EMBED_COLOR", "714C35"), 16)
            
            embed = discord.Embed(
                title=self.cog.loc_helper.get_text("TEMPVOICE_BLOCK_MENU_TITLE", interaction.user.id),
                description=self.cog.loc_helper.get_text("TEMPVOICE_BLOCK_MENU_DESC", interaction.user.id),
                color=embed_color
            )
            
            embed.set_footer(
                text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
            )
            
            # Send the user selection message
            await interaction.response.send_message(
                embed=embed,
                view=user_select_view,
                ephemeral=True
            )
            
            # Log the block menu access
            print(f"[TEMPVOICE] 🚫 BLOCK MENU | User: {interaction.user.name} ({interaction.user.id}) | Channel: {self.channel_data.channel_id} | Guild: {interaction.guild.name}")
            
        except Exception as e:
            await self._safe_interaction_response(
                interaction,
                self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error=str(e))
            )
            print(f"[TEMPVOICE] ❌ BLOCK MENU ERROR | User: {interaction.user.name} | Error: {str(e)}")
    
    @discord.ui.button(label="UNBLOCK", emoji="✅", style=discord.ButtonStyle.success, row=2)
    async def unblock_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not self._can_manage_channel(interaction.user.id):
            # Create error embed for permission denied
            error_embed = self.cog.create_error_embed(
                description_key="TEMPVOICE_NO_PERMISSION",
                user_id=interaction.user.id
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True, delete_after=10)
            return
        
        try:
            # Create user selection dropdown view
            user_select_view = UserActionSelectView(self.cog, self.channel_data, "unblock")
            
            # Create embed for user selection
            config = load_config()
            embed_color = int(config.get("DISCORD_EMBED_COLOR", "714C35"), 16)
            
            embed = discord.Embed(
                title=self.cog.loc_helper.get_text("TEMPVOICE_UNBLOCK_MENU_TITLE", interaction.user.id),
                description=self.cog.loc_helper.get_text("TEMPVOICE_UNBLOCK_MENU_DESC", interaction.user.id),
                color=embed_color
            )
            
            embed.set_footer(
                text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
            )
            
            # Send the user selection message
            await interaction.response.send_message(
                embed=embed,
                view=user_select_view,
                ephemeral=True
            )
            
            # Log the unblock menu access
            print(f"[TEMPVOICE] ✅ UNBLOCK MENU | User: {interaction.user.name} ({interaction.user.id}) | Channel: {self.channel_data.channel_id} | Guild: {interaction.guild.name}")
            
        except Exception as e:
            await self._safe_interaction_response(
                interaction,
                self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error=str(e))
            )
            print(f"[TEMPVOICE] ❌ UNBLOCK MENU ERROR | User: {interaction.user.name} | Error: {str(e)}")
    
    @discord.ui.button(label="CLAIM", emoji="👑", style=discord.ButtonStyle.secondary, row=2)
    async def claim_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        try:
            channel = interaction.guild.get_channel(self.channel_data.channel_id)
            if not channel:
                await self._safe_interaction_response(
                    interaction,
                    self.cog.loc_helper.get_text("TEMPVOICE_CHANNEL_NOT_FOUND", interaction.user.id)
                )
                return
            
            # Check if current owner is still in the channel
            current_owner = interaction.guild.get_member(self.channel_data.owner_id)
            if current_owner and current_owner in channel.members:
                # Create embed for claim ownership error
                config = load_config()
                embed_color = int(config.get("DISCORD_EMBED_COLOR", "714C35"), 16)
                
                embed = discord.Embed(
                    title=self.cog.loc_helper.get_text("TEMPVOICE_CLAIM_OWNER_PRESENT_TITLE", interaction.user.id),
                    description=self.cog.loc_helper.get_text("TEMPVOICE_CLAIM_OWNER_PRESENT_DESC", interaction.user.id),
                    color=0xFF0000  # Red color for error
                )
                
                embed.set_footer(
                    text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                    icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
                )
                
                await self._safe_interaction_response(
                    interaction,
                    "",
                    embed=embed
                )
                return
            
            # Check if user is in the channel
            if interaction.user not in channel.members:
                await self._safe_interaction_response(
                    interaction,
                    self.cog.loc_helper.get_text("TEMPVOICE_NOT_IN_CHANNEL", interaction.user.id)
                )
                return
            
            # Claim ownership
            self.channel_data.owner_id = interaction.user.id
            
            # Create success embed
            config = load_config()
            success_embed = discord.Embed(
                title="✅ Ownership Claimed",
                description=self.cog.loc_helper.get_text("TEMPVOICE_OWNERSHIP_CLAIMED", interaction.user.id),
                color=0x00FF00  # Green color for success
            )
            
            # Add bot branding footer
            success_embed.set_footer(
                text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
            )
            
            # Edit the original message to show success and auto-delete
            await self._safe_interaction_response(
                interaction,
                "",
                edit=True,
                embed=success_embed,
                delete_after=30
            )
        except Exception as e:
            await self._safe_interaction_response(
                interaction,
                self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error=str(e))
            )
    
    @discord.ui.button(label="TRANSFER", emoji="🔄", style=discord.ButtonStyle.secondary, row=2)
    async def transfer_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.channel_data.owner_id:
            await self._safe_interaction_response(
                interaction,
                self.cog.loc_helper.get_text("TEMPVOICE_OWNER_ONLY", interaction.user.id)
            )
            return
        
        try:
            # Create transfer ownership dropdown view
            transfer_select_view = TransferOwnershipSelectView(self.cog, self.channel_data)
            
            # Create embed for user selection
            config = load_config()
            embed_color = int(config.get("DISCORD_EMBED_COLOR", "714C35"), 16)
            
            embed = discord.Embed(
                title=self.cog.loc_helper.get_text("TEMPVOICE_TRANSFER_MENU_TITLE", interaction.user.id),
                description=self.cog.loc_helper.get_text("TEMPVOICE_TRANSFER_MENU_DESC", interaction.user.id),
                color=embed_color
            )
            
            embed.set_footer(
                text=config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮"),
                icon_url=interaction.client.user.avatar.url if interaction.client.user.avatar else None
            )
            
            # Send the user selection message
            await interaction.response.send_message(
                embed=embed,
                view=transfer_select_view,
                ephemeral=True
            )
            
            # Log the transfer menu access
            print(f"[TEMPVOICE] 🔄 TRANSFER MENU | User: {interaction.user.name} ({interaction.user.id}) | Channel: {self.channel_data.channel_id} | Guild: {interaction.guild.name}")
            
        except Exception as e:
            await self._safe_interaction_response(
                interaction,
                self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error=str(e))
            )
            print(f"[TEMPVOICE] ❌ TRANSFER MENU ERROR | User: {interaction.user.name} | Error: {str(e)}")
    
    @discord.ui.button(label="DELETE", emoji="🗑️", style=discord.ButtonStyle.danger, row=2)
    async def delete_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.channel_data.owner_id:
            try:
                await interaction.response.send_message(
                    self.cog.loc_helper.get_text("TEMPVOICE_OWNER_ONLY", interaction.user.id),
                    ephemeral=True
                )
            except discord.errors.NotFound:
                # Interaction expired, try followup
                try:
                    await interaction.followup.send(
                        self.cog.loc_helper.get_text("TEMPVOICE_OWNER_ONLY", interaction.user.id),
                        ephemeral=True
                    )
                except:
                    pass  # Silently fail if both methods don't work
            return
        
        try:
            # First respond to interaction to avoid timeout
            try:
                await interaction.response.defer(ephemeral=True)
            except discord.errors.NotFound:
                # Interaction already responded to or expired
                pass
            
            channel = interaction.guild.get_channel(self.channel_data.channel_id)
            if channel:
                try:
                    await channel.delete(reason="Channel deleted by owner")
                    
                    # Remove from active channels
                    if self.channel_data.channel_id in self.cog.active_channels:
                        del self.cog.active_channels[self.channel_data.channel_id]
                    
                    # Send success message
                    message = self.cog.loc_helper.get_text("TEMPVOICE_CHANNEL_DELETED", interaction.user.id)
                    try:
                        if interaction.response.is_done():
                            await interaction.followup.send(message, ephemeral=True)
                        else:
                            await interaction.response.send_message(message, ephemeral=True)
                    except discord.errors.NotFound:
                        # Channel or interaction no longer exists, that's fine
                        pass
                        
                except discord.errors.NotFound:
                    # Channel already deleted
                    if self.channel_data.channel_id in self.cog.active_channels:
                        del self.cog.active_channels[self.channel_data.channel_id]
                    
                    message = self.cog.loc_helper.get_text("TEMPVOICE_CHANNEL_DELETED", interaction.user.id)
                    try:
                        if interaction.response.is_done():
                            await interaction.followup.send(message, ephemeral=True)
                        else:
                            await interaction.response.send_message(message, ephemeral=True)
                    except discord.errors.NotFound:
                        pass
            else:
                # Channel not found
                if self.channel_data.channel_id in self.cog.active_channels:
                    del self.cog.active_channels[self.channel_data.channel_id]
                
                message = self.cog.loc_helper.get_text("TEMPVOICE_CHANNEL_NOT_FOUND", interaction.user.id)
                try:
                    if interaction.response.is_done():
                        await interaction.followup.send(message, ephemeral=True)
                    else:
                        await interaction.response.send_message(message, ephemeral=True)
                except discord.errors.NotFound:
                    pass
                    
        except Exception as e:
            # General error handling
            error_message = self.cog.loc_helper.get_text("TEMPVOICE_ERROR", interaction.user.id, error=str(e))
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(error_message, ephemeral=True)
                else:
                    await interaction.response.send_message(error_message, ephemeral=True)
            except discord.errors.NotFound:
                # Log the error since we can't send it to user
                print(f"[TEMPVOICE] Error in delete_button: {e}")


class TempVoiceCog(commands.Cog):
    """TempVoice system for creating and managing temporary voice channels"""
    
    def __init__(self, bot):
        self.bot = bot
        self.localization = LocalizationManager()
        self.loc_helper = LocalizationHelper(bot)
        
        # Active temporary channels
        self.active_channels: Dict[int, TempChannelData] = {}
        
        # Guild configurations
        self.guild_configs: Dict[int, GuildTempVoiceConfig] = {}
        
        # Lock to prevent race conditions during channel creation
        self.creation_locks: Dict[int, asyncio.Lock] = {}
        
        # Start cleanup task
        self.cleanup_task.start()
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.cleanup_task.cancel()
    
    def _get_guild_config(self, guild_id: int) -> GuildTempVoiceConfig:
        """Get or create guild configuration"""
        if guild_id not in self.guild_configs:
            config = load_config()
            allowed_roles = config.get("TEMPVOICE_ALLOWED_ROLES", [])
            print(f"[TEMPVOICE DEBUG] 📋 LOADING GUILD CONFIG | Guild ID: {guild_id}")
            print(f"[TEMPVOICE DEBUG] 📋 Raw TEMPVOICE_ALLOWED_ROLES from config: {allowed_roles}")
            print(f"[TEMPVOICE DEBUG] 📋 Allowed roles type: {type(allowed_roles)}")
            print(f"[TEMPVOICE DEBUG] 📋 Allowed roles count: {len(allowed_roles)}")
            
            self.guild_configs[guild_id] = GuildTempVoiceConfig(
                guild_id=guild_id,
                creator_channels=config.get("TEMPVOICE_CREATOR_CHANNELS", []),
                temp_category_id=config.get("TEMPVOICE_TEMP_CATEGORY"),
                enabled=config.get("TEMPVOICE_ENABLED", True),
                required_role=config.get("TEMPVOICE_REQUIRED_ROLE"),
                max_channels_per_user=config.get("TEMPVOICE_MAX_CHANNELS_PER_USER", 3),
                auto_delete_delay=config.get("TEMPVOICE_AUTO_DELETE_DELAY", 0),
                default_everyone_permissions=config.get("TEMPVOICE_DEFAULT_EVERYONE_PERMISSIONS", {"view_channel": True, "connect": True}),
                allowed_roles=allowed_roles
            )
            print(f"[TEMPVOICE DEBUG] 📋 Guild config created with allowed_roles: {self.guild_configs[guild_id].allowed_roles}")
        else:
            print(f"[TEMPVOICE DEBUG] 📋 Using cached guild config for {guild_id} with allowed_roles: {self.guild_configs[guild_id].allowed_roles}")
        return self.guild_configs[guild_id]
    
    def _save_guild_config(self, guild_config: GuildTempVoiceConfig):
        """Save guild configuration to config.json"""
        try:
            # Load current config
            config_path = "config/config.json"
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Update TempVoice settings
            config["TEMPVOICE_CREATOR_CHANNELS"] = guild_config.creator_channels
            config["TEMPVOICE_TEMP_CATEGORY"] = guild_config.temp_category_id
            config["TEMPVOICE_ENABLED"] = guild_config.enabled
            config["TEMPVOICE_REQUIRED_ROLE"] = guild_config.required_role
            config["TEMPVOICE_MAX_CHANNELS_PER_USER"] = guild_config.max_channels_per_user
            config["TEMPVOICE_AUTO_DELETE_DELAY"] = guild_config.auto_delete_delay
            config["TEMPVOICE_DEFAULT_EVERYONE_PERMISSIONS"] = guild_config.default_everyone_permissions
            config["TEMPVOICE_ALLOWED_ROLES"] = guild_config.allowed_roles
            
            # Save back to file
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            
            print(f"[TEMPVOICE] Configuration saved for guild {guild_config.guild_id}")
            
        except Exception as e:
            print(f"[TEMPVOICE] Error saving configuration: {e}")
    
    def _create_dm_embed(self, title: str, description: str) -> discord.Embed:
        """Create a standardized DM embed with bot styling"""
        config = load_config()
        embed_color = int(config.get("DISCORD_EMBED_COLOR", "714C35"), 16)
        trademark = config.get("DISCORD_MESSAGE_TRADEMARK", "BebraLand team 🚀🌍🎮")
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color(embed_color)
        )
        
        # Set footer with trademark and bot avatar
        embed.set_footer(
            text=trademark,
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )
        
        return embed
    
    def _create_control_panel_embed(self, channel_data: TempChannelData, guild: discord.Guild) -> discord.Embed:
        """Create the control panel embed"""
        config = load_config()
        embed_color = int(config.get("DISCORD_EMBED_COLOR", "714C35"), 16)
        
        embed = discord.Embed(
            title="🎙️ TempVoice Interface",
            description="This interface can be used to manage temporary voice channels.\nMore options are available with the buttons below.",
            color=discord.Color(embed_color)
        )
        
        # Channel info
        channel = guild.get_channel(channel_data.channel_id)
        if channel:
            member_count = len(channel.members)
            limit_text = "∞" if channel_data.user_limit == 0 else str(channel_data.user_limit)
            privacy_text = "🔒 Private" if channel_data.is_private else "🔓 Public"
            
            embed.add_field(
                name="📋 NAME",
                value=f"**{channel_data.channel_name}**",
                inline=True
            )
            embed.add_field(
                name="👥 LIMIT",
                value=f"**{member_count}/{limit_text}**",
                inline=True
            )
            embed.add_field(
                name="🔒 PRIVACY",
                value=privacy_text,
                inline=True
            )
            
            # Owner info
            owner = guild.get_member(channel_data.owner_id)
            owner_name = owner.display_name if owner else "Unknown"
            embed.add_field(
                name="👑 OWNER",
                value=f"**{owner_name}**",
                inline=True
            )
            
            # Trusted users
            if channel_data.trusted_users:
                trusted_names = []
                for user_id in list(channel_data.trusted_users)[:3]:  # Show max 3
                    user = guild.get_member(user_id)
                    if user:
                        trusted_names.append(user.display_name)
                
                trusted_text = ", ".join(trusted_names)
                if len(channel_data.trusted_users) > 3:
                    trusted_text += f" (+{len(channel_data.trusted_users) - 3} more)"
                
                embed.add_field(
                    name="✅ TRUSTED",
                    value=trusted_text,
                    inline=True
                )
            
            # Region (placeholder)
            embed.add_field(
                name="🌍 REGION",
                value="Auto",
                inline=True
            )
        
        embed.add_field(
            name="⚙️ Instructions",
            value="Press the buttons below to use the interface",
            inline=False
        )
        
        return embed
    
    def _determine_privacy_state(self, channel: discord.VoiceChannel) -> str:
        """Determine the current privacy state of a channel based on its overwrites"""
        everyone_overwrite = channel.overwrites_for(channel.guild.default_role)
        
        # Check if channel is locked (connect=False for @everyone)
        if everyone_overwrite.connect is False:
            if everyone_overwrite.view_channel is False:
                return "invisible"  # Can't see or connect
            else:
                return "lock"  # Can see but can't connect
        
        # Check if channel is visible but open
        if everyone_overwrite.view_channel is False:
            return "invisible"  # Can't see but might be able to connect if they know about it
        
        # Check text channel permissions for chat restrictions
        text_channel = None
        if channel.category:
            for ch in channel.category.text_channels:
                if ch.name.lower().replace("-", " ").replace("_", " ") == channel.name.lower().replace("-", " ").replace("_", " "):
                    text_channel = ch
                    break
        
        if text_channel:
            text_overwrite = text_channel.overwrites_for(channel.guild.default_role)
            if text_overwrite.send_messages is False:
                return "close_chat"
        
        # Default state - open/visible/unlocked
        return "unlock"
    
    async def _handle_user_action(self, channel: discord.VoiceChannel, user: discord.Member, action: str, channel_data: TempChannelData) -> bool:
        """Handle user management actions"""
        try:
            if action == "trust":
                channel_data.trusted_users.add(user.id)
                guild_config = self._get_guild_config(channel.guild.id)
                current_privacy_state = self._determine_privacy_state(channel)
                overwrites = apply_privacy_overwrites(
                    base_overwrites=channel.overwrites,
                    privacy_action="reconcile",
                    guild=channel.guild,
                    allowed_roles=guild_config.allowed_roles,
                    owner=channel.guild.get_member(channel_data.owner_id),
                    trusted_users=list(channel_data.trusted_users)
                )
                await channel.edit(overwrites=overwrites)
                print(f"[TEMPVOICE] 🔧 TRUST: Applied reconcile overwrites for newly trusted user {user.display_name} (effective state: {current_privacy_state})")
                return True
            
            elif action == "untrust":
                channel_data.trusted_users.discard(user.id)
                guild_config = self._get_guild_config(channel.guild.id)
                current_privacy_state = self._determine_privacy_state(channel)
                overwrites = apply_privacy_overwrites(
                    base_overwrites=channel.overwrites,
                    privacy_action="reconcile",
                    guild=channel.guild,
                    allowed_roles=guild_config.allowed_roles,
                    owner=channel.guild.get_member(channel_data.owner_id),
                    trusted_users=list(channel_data.trusted_users)
                )
                await channel.edit(overwrites=overwrites)
                print(f"[TEMPVOICE] 🔧 UNTRUST: Applied reconcile overwrites after removing trust from {user.display_name} (effective state: {current_privacy_state})")
                return True
            
            elif action == "kick":
                if user not in channel.members:
                    print(f"[TEMPVOICE] ❌ KICK FAILED: User {user.display_name} is not in channel {channel.name}")
                    return "TEMPVOICE_USER_NOT_IN_CHANNEL"
                await user.move_to(None, reason="Kicked from temp channel")
                return True
            
            elif action == "block":
                channel_data.blocked_users.add(user.id)
                # Update channel permissions
                overwrites = channel.overwrites
                overwrites[user] = discord.PermissionOverwrite(view_channel=False, connect=False)
                await channel.edit(overwrites=overwrites)
                
                # Kick if currently in channel
                if user in channel.members:
                    await user.move_to(None, reason="Blocked from temp channel")
                return True
            
            elif action == "unblock":
                channel_data.blocked_users.discard(user.id)
                # Remove permission overwrite
                overwrites = channel.overwrites
                if user in overwrites:
                    del overwrites[user]
                    await channel.edit(overwrites=overwrites)
                return True
            
            return False
        except Exception as e:
            print(f"[TEMPVOICE] Error handling user action {action}: {e}")
            return False
    
    async def _update_channel_permissions(self, channel: discord.VoiceChannel, new_owner: discord.Member, channel_data: TempChannelData) -> bool:
        """Update channel permissions when ownership is transferred"""
        try:
            guild_config = self._get_guild_config(channel.guild.id)
            
            # Create new permission overwrites with the new owner
            overwrites = create_permission_overwrites(
                everyone_permissions=guild_config.default_everyone_permissions,
                allowed_roles=guild_config.allowed_roles,
                guild=channel.guild,
                owner=new_owner
            )
            
            # Apply trusted users permissions
            for user_id in channel_data.trusted_users:
                user = channel.guild.get_member(user_id)
                if user:
                    overwrites[user] = discord.PermissionOverwrite(
                        view_channel=True,
                        connect=True,
                        speak=True,
                        stream=True,
                        use_voice_activation=True
                    )
            
            # Apply blocked users permissions
            for user_id in channel_data.blocked_users:
                user = channel.guild.get_member(user_id)
                if user:
                    overwrites[user] = discord.PermissionOverwrite(
                        view_channel=False,
                        connect=False
                    )
            
            # Update channel permissions
            await channel.edit(overwrites=overwrites)
            logger.info(f"[TEMPVOICE] ✅ PERMISSIONS UPDATED | Channel: {channel.name} | New Owner: {new_owner.display_name}")
            return True
            
        except Exception as e:
            logger.error(f"[TEMPVOICE] ❌ PERMISSION UPDATE FAILED | Channel: {channel.name} | Error: {str(e)}")
            return False
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Handle voice state updates for temp channel creation and cleanup"""
        guild_config = self._get_guild_config(member.guild.id)
        
        if not guild_config.enabled:
            return
        
        # Check if user joined a creator channel
        if after.channel and after.channel.id in guild_config.creator_channels:
            print(f"[TEMPVOICE] User {member.display_name} ({member.name}) joined creator channel '{after.channel.name}' in {member.guild.name}")
            await self._create_temp_channel(member, after.channel, guild_config)
        
        # Check if user left a creator channel
        if before.channel and before.channel.id in guild_config.creator_channels:
            print(f"[TEMPVOICE] User {member.display_name} ({member.name}) left creator channel '{before.channel.name}' in {member.guild.name}")
        
        # Check if a temp channel became empty
        if before.channel and before.channel.id in self.active_channels:
            if len(before.channel.members) == 0:
                print(f"[TEMPVOICE] Temp channel '{before.channel.name}' became empty, scheduling deletion in {guild_config.auto_delete_delay} seconds")
                await self._schedule_channel_deletion(before.channel.id, guild_config.auto_delete_delay)
    
    async def _create_temp_channel(self, member: discord.Member, creator_channel: discord.VoiceChannel, guild_config: GuildTempVoiceConfig):
        """Create a new temporary voice channel"""
        # Get or create a lock for this user to prevent race conditions
        if member.id not in self.creation_locks:
            self.creation_locks[member.id] = asyncio.Lock()
        
        async with self.creation_locks[member.id]:
            try:
                # Check if user already has an active temp channel in this guild
                existing_channels = [data for data in self.active_channels.values() 
                                   if data.owner_id == member.id and data.guild_id == member.guild.id]
                
                if existing_channels:
                    # User already has a temp channel, move them to it instead
                    existing_channel_data = existing_channels[0]
                    existing_channel = member.guild.get_channel(existing_channel_data.channel_id)
                    
                    if existing_channel:
                        print(f"[TEMPVOICE] User {member.display_name} already has temp channel '{existing_channel.name}', moving them to it")
                        try:
                            await member.move_to(existing_channel, reason="Moved to existing temp channel")
                            # Send a message to let them know
                            try:
                                embed = self._create_dm_embed(
                                    "✅ Temporary Channel",
                                    self.loc_helper.get_text("TEMPVOICE_MOVED_TO_EXISTING", member.id, 
                                                           channel=f"<#{existing_channel.id}>")
                                )
                                await member.send(embed=embed)
                            except:
                                pass
                        except Exception as e:
                            print(f"[TEMPVOICE] Failed to move user to existing channel: {e}")
                        return
                    else:
                        # Channel doesn't exist anymore, remove from active channels
                        print(f"[TEMPVOICE] Cleaning up non-existent channel {existing_channel_data.channel_id}")
                        del self.active_channels[existing_channel_data.channel_id]
                
                # Check user limits
                user_channels = sum(1 for data in self.active_channels.values() 
                                  if data.owner_id == member.id and data.guild_id == member.guild.id)
            
                print(f"[TEMPVOICE] User {member.display_name} has {user_channels}/{guild_config.max_channels_per_user} temp channels")
                
                if user_channels >= guild_config.max_channels_per_user:
                    print(f"[TEMPVOICE] User {member.display_name} reached channel limit ({guild_config.max_channels_per_user})")
                    # Send DM about limit
                    try:
                        embed = self._create_dm_embed(
                            "⚠️ Channel Limit Reached",
                            self.loc_helper.get_text("TEMPVOICE_USER_LIMIT_REACHED", member.id, 
                                                   limit=guild_config.max_channels_per_user)
                        )
                        await member.send(embed=embed)
                    except:
                        pass  # Ignore if can't send DM
                    return
                
                # Check required role
                if guild_config.required_role:
                    required_role = member.guild.get_role(guild_config.required_role)
                    if required_role and required_role not in member.roles:
                        print(f"[TEMPVOICE] User {member.display_name} missing required role '{required_role.name}'")
                        try:
                            embed = self._create_dm_embed(
                                "🔒 Role Required",
                                self.loc_helper.get_text("TEMPVOICE_ROLE_REQUIRED", member.id, 
                                                       role=required_role.name)
                            )
                            await member.send(embed=embed)
                        except:
                            pass
                        return
                    else:
                        print(f"[TEMPVOICE] User {member.display_name} has required role '{required_role.name}'")
                else:
                    print(f"[TEMPVOICE] No role requirement set for guild {member.guild.name}")
                
                # Determine category
                category = None
                if guild_config.temp_category_id:
                    category = member.guild.get_channel(guild_config.temp_category_id)
                if not category:
                    category = creator_channel.category
                
                # Create channel name
                config = load_config()
                name_template = config.get("TEMPVOICE_CHANNEL_NAME_TEMPLATE", "{username}'s Channel")
                channel_name = name_template.format(username=member.display_name)
                
                # Create the channel with permission overwrites using helper function
                overwrites = create_permission_overwrites(
                    everyone_permissions=guild_config.default_everyone_permissions,
                    allowed_roles=guild_config.allowed_roles,
                    guild=member.guild,
                    owner=member
                )
                
                temp_channel = await member.guild.create_voice_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites,
                    reason=f"TempVoice channel created by {member}"
                )
                
                # Move user to the new channel
                await member.move_to(temp_channel, reason="Moved to new temp channel")
                
                # Create channel data
                channel_data = TempChannelData(
                    channel_id=temp_channel.id,
                    owner_id=member.id,
                    guild_id=member.guild.id,
                    channel_name=channel_name
                )
                
                # Store in active channels
                self.active_channels[temp_channel.id] = channel_data
                
                # Send control panel
                embed = self._create_control_panel_embed(channel_data, member.guild)
                view = TempVoiceControlPanel(self, channel_data)
                
                try:
                    await temp_channel.send(embed=embed, view=view)
                except:
                    # If can't send to channel, try to send to user
                    try:
                        dm_embed = self._create_dm_embed(
                            "🎙️ Channel Created",
                            self.loc_helper.get_text("TEMPVOICE_CHANNEL_CREATED", member.id)
                        )
                        await member.send(embed=dm_embed)
                        # Also send the control panel
                        await member.send(embed=embed, view=view)
                    except:
                        pass  # Ignore if can't send anywhere
                
                print(f"[TEMPVOICE] Created temp channel '{channel_name}' for {member.display_name} ({member.name}) in {member.guild.name}")
                
            except Exception as e:
                print(f"[TEMPVOICE] Error creating temp channel: {e}")
    
    async def _schedule_channel_deletion(self, channel_id: int, delay: int):
        """Schedule a channel for deletion after a delay"""
        if delay > 0:
            print(f"[TEMPVOICE] Waiting {delay} seconds before checking channel {channel_id} for deletion")
            await asyncio.sleep(delay)
        
        # Check if channel is still empty
        if channel_id in self.active_channels:
            guild = self.bot.get_guild(self.active_channels[channel_id].guild_id)
            if guild:
                channel = guild.get_channel(channel_id)
                if channel and len(channel.members) == 0:
                    print(f"[TEMPVOICE] Channel {channel.name} is still empty after delay, proceeding with deletion")
                    await self._delete_temp_channel(channel_id)
                elif channel:
                    print(f"[TEMPVOICE] Channel {channel.name} is no longer empty, canceling deletion")
                else:
                    print(f"[TEMPVOICE] Channel {channel_id} no longer exists, cleaning up data")
                    if channel_id in self.active_channels:
                        del self.active_channels[channel_id]
    
    async def _delete_temp_channel(self, channel_id: int):
        """Delete a temporary channel"""
        try:
            if channel_id in self.active_channels:
                channel_data = self.active_channels[channel_id]
                guild = self.bot.get_guild(channel_data.guild_id)
                
                if guild:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        await channel.delete(reason="Empty temp channel cleanup")
                        print(f"[TEMPVOICE] Deleted empty temp channel '{channel_data.channel_name}' in {guild.name}")
                
                # Remove from active channels
                del self.active_channels[channel_id]
        except Exception as e:
            print(f"[TEMPVOICE] Error deleting temp channel {channel_id}: {e}")
    
    @tasks.loop(minutes=5)
    async def cleanup_task(self):
        """Periodic cleanup of abandoned channels"""
        try:
            print(f"[TEMPVOICE] Running cleanup task - checking {len(self.active_channels)} active channels")
            channels_to_delete = []
            
            for channel_id, channel_data in self.active_channels.items():
                guild = self.bot.get_guild(channel_data.guild_id)
                if not guild:
                    print(f"[TEMPVOICE] Guild {channel_data.guild_id} not found, marking channel {channel_id} for cleanup")
                    channels_to_delete.append(channel_id)
                    continue
                
                channel = guild.get_channel(channel_id)
                if not channel:
                    print(f"[TEMPVOICE] Channel {channel_id} not found in guild {guild.name}, marking for cleanup")
                    channels_to_delete.append(channel_id)
                    continue
                
                # Check if channel has been empty for too long
                if len(channel.members) == 0:
                    print(f"[TEMPVOICE] Found empty channel '{channel.name}' during cleanup, marking for deletion")
                    # Delete immediately during cleanup
                    channels_to_delete.append(channel_id)
            
            # Delete abandoned channels
            if channels_to_delete:
                print(f"[TEMPVOICE] Cleaning up {len(channels_to_delete)} abandoned channels")
                for channel_id in channels_to_delete:
                    await self._delete_temp_channel(channel_id)
            else:
                print(f"[TEMPVOICE] No channels need cleanup")
                
        except Exception as e:
            print(f"[TEMPVOICE] Error in cleanup task: {e}")
    
    @cleanup_task.before_loop
    async def before_cleanup_task(self):
        """Wait for bot to be ready before starting cleanup"""
        await self.bot.wait_until_ready()
    
    # Admin Commands
    tempvoice_group = discord.SlashCommandGroup(
        name="tempvoice",
        description="TempVoice administration commands",
        default_member_permissions=discord.Permissions(administrator=True)
    )
    
    @tempvoice_group.command(
        name="setup",
        description="Set up TempVoice creator channels"
    )
    async def setup_tempvoice(
        self,
        ctx: discord.ApplicationContext,
        creator_channel: discord.Option(
            discord.VoiceChannel,
            description="Voice channel that will create temp channels when joined",
            required=True
        ),
        category: discord.Option(
            discord.CategoryChannel,
            description="Category where temp channels will be created",
            required=False
        )
    ):
        """Set up a creator channel for TempVoice"""
        guild_config = self._get_guild_config(ctx.guild.id)
        
        if creator_channel.id not in guild_config.creator_channels:
            guild_config.creator_channels.append(creator_channel.id)
        
        if category:
            guild_config.temp_category_id = category.id
        
        # Save configuration to config.json
        self._save_guild_config(guild_config)
        print(f"[TEMPVOICE] Added creator channel {creator_channel.name} for guild {ctx.guild.name}")
        
        embed = discord.Embed(
            title="✅ TempVoice Setup Complete",
            description=f"Creator channel: {creator_channel.mention}\n" +
                       (f"Category: {category.mention}" if category else "Category: Same as creator channel"),
            color=discord.Color.green()
        )
        
        await ctx.respond(embed=embed)
    
    @tempvoice_group.command(
        name="remove",
        description="Remove a TempVoice creator channel"
    )
    async def remove_creator(
        self,
        ctx: discord.ApplicationContext,
        creator_channel: discord.Option(
            discord.VoiceChannel,
            description="Creator channel to remove",
            required=True
        )
    ):
        """Remove a creator channel"""
        guild_config = self._get_guild_config(ctx.guild.id)
        
        if creator_channel.id in guild_config.creator_channels:
            guild_config.creator_channels.remove(creator_channel.id)
            
            # Save configuration to config.json
            self._save_guild_config(guild_config)
            print(f"[TEMPVOICE] Removed creator channel {creator_channel.name} for guild {ctx.guild.name}")
            
            embed = discord.Embed(
                title="✅ Creator Channel Removed",
                description=f"Removed {creator_channel.mention} as a creator channel",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Not a Creator Channel",
                description=f"{creator_channel.mention} is not a creator channel",
                color=discord.Color.red()
            )
        
        await ctx.respond(embed=embed)
    
    @tempvoice_group.command(
        name="list",
        description="List all TempVoice creator channels"
    )
    async def list_creators(self, ctx: discord.ApplicationContext):
        """List all creator channels"""
        guild_config = self._get_guild_config(ctx.guild.id)
        
        if not guild_config.creator_channels:
            embed = discord.Embed(
                title="📋 TempVoice Creator Channels",
                description="No creator channels configured",
                color=discord.Color.orange()
            )
        else:
            channel_mentions = []
            for channel_id in guild_config.creator_channels:
                channel = ctx.guild.get_channel(channel_id)
                if channel:
                    channel_mentions.append(channel.mention)
                else:
                    channel_mentions.append(f"<#{channel_id}> (deleted)")
            
            embed = discord.Embed(
                title="📋 TempVoice Creator Channels",
                description="\n".join(channel_mentions),
                color=discord.Color.blue()
            )
            
            if guild_config.temp_category_id:
                category = ctx.guild.get_channel(guild_config.temp_category_id)
                category_name = category.mention if category else f"<#{guild_config.temp_category_id}> (deleted)"
                embed.add_field(
                    name="Default Category",
                    value=category_name,
                    inline=False
                )
        
        await ctx.respond(embed=embed)
    
    @tempvoice_group.command(
        name="config",
        description="Configure TempVoice settings"
    )
    async def config_tempvoice(
        self,
        ctx: discord.ApplicationContext,
        enabled: discord.Option(
            bool,
            description="Enable or disable TempVoice",
            required=False
        ),
        max_channels: discord.Option(
            int,
            description="Maximum channels per user (1-10)",
            min_value=1,
            max_value=10,
            required=False
        ),
        auto_delete_delay: discord.Option(
            int,
            description="Delay before deleting empty channels (seconds, 0 = immediate)",
            min_value=0,
            max_value=3600,
            required=False
        ),
        required_role: discord.Option(
            discord.Role,
            description="Role required to create temp channels",
            required=False
        ),
        everyone_can_view: discord.Option(
            bool,
            description="Allow @everyone to see temp channels by default",
            required=False
        ),
        everyone_can_join: discord.Option(
            bool,
            description="Allow @everyone to join temp channels by default",
            required=False
        ),
        add_allowed_role: discord.Option(
            discord.Role,
            description="Add a role that can always see/join temp channels",
            required=False
        ),
        remove_allowed_role: discord.Option(
            discord.Role,
            description="Remove a role from allowed roles list",
            required=False
        )
    ):
        """Configure TempVoice settings"""
        guild_config = self._get_guild_config(ctx.guild.id)
        
        changes = []
        
        if enabled is not None:
            guild_config.enabled = enabled
            changes.append(f"Enabled: {enabled}")
        
        if max_channels is not None:
            guild_config.max_channels_per_user = max_channels
            changes.append(f"Max channels per user: {max_channels}")
        
        if auto_delete_delay is not None:
            guild_config.auto_delete_delay = auto_delete_delay
            delay_text = "immediate" if auto_delete_delay == 0 else f"{auto_delete_delay} seconds"
            changes.append(f"Auto-delete delay: {delay_text}")
        
        if required_role is not None:
            guild_config.required_role = required_role.id
            changes.append(f"Required role: {required_role.mention}")
        
        # Handle permission settings
        if everyone_can_view is not None:
            guild_config.default_everyone_permissions["view_channel"] = everyone_can_view
            changes.append(f"@everyone can view channels: {everyone_can_view}")
        
        if everyone_can_join is not None:
            guild_config.default_everyone_permissions["connect"] = everyone_can_join
            changes.append(f"@everyone can join channels: {everyone_can_join}")
        
        # Handle allowed roles
        if add_allowed_role is not None:
            if add_allowed_role.id not in guild_config.allowed_roles:
                guild_config.allowed_roles.append(add_allowed_role.id)
                changes.append(f"Added allowed role: {add_allowed_role.mention}")
            else:
                changes.append(f"Role {add_allowed_role.mention} is already in allowed roles")
        
        if remove_allowed_role is not None:
            if remove_allowed_role.id in guild_config.allowed_roles:
                guild_config.allowed_roles.remove(remove_allowed_role.id)
                changes.append(f"Removed allowed role: {remove_allowed_role.mention}")
            else:
                changes.append(f"Role {remove_allowed_role.mention} was not in allowed roles")
        
        if changes:
            # Save configuration to config.json
            self._save_guild_config(guild_config)
            
            embed = discord.Embed(
                title="✅ TempVoice Configuration Updated",
                description="\n".join(changes),
                color=discord.Color.green()
            )
        else:
            # Show current config
            embed = discord.Embed(
                title="⚙️ Current TempVoice Configuration",
                color=discord.Color.blue()
            )
            embed.add_field(name="Enabled", value=guild_config.enabled, inline=True)
            embed.add_field(name="Max Channels/User", value=guild_config.max_channels_per_user, inline=True)
            
            delay_text = "Immediate" if guild_config.auto_delete_delay == 0 else f"{guild_config.auto_delete_delay}s"
            embed.add_field(name="Auto-Delete Delay", value=delay_text, inline=True)
            
            if guild_config.required_role:
                role = ctx.guild.get_role(guild_config.required_role)
                role_text = role.mention if role else "Role not found"
                embed.add_field(name="Required Role", value=role_text, inline=True)
            else:
                embed.add_field(name="Required Role", value="None", inline=True)
        
        await ctx.respond(embed=embed)
    
    @tempvoice_group.command(
        name="cleanup",
        description="Manually clean up empty temporary channels"
    )
    async def cleanup_channels(self, ctx: discord.ApplicationContext):
        """Manually trigger cleanup of empty channels"""
        await ctx.defer()
        
        cleaned_count = 0
        channels_to_delete = []
        
        for channel_id, channel_data in self.active_channels.items():
            if channel_data.guild_id == ctx.guild.id:
                channel = ctx.guild.get_channel(channel_id)
                if not channel or len(channel.members) == 0:
                    channels_to_delete.append(channel_id)
        
        for channel_id in channels_to_delete:
            await self._delete_temp_channel(channel_id)
            cleaned_count += 1
        
        embed = discord.Embed(
            title="🧹 Cleanup Complete",
            description=f"Cleaned up {cleaned_count} empty temporary channels",
            color=discord.Color.green()
        )
        
        await ctx.followup.send(embed=embed)
    
    @tempvoice_group.command(
        name="stats",
        description="Show TempVoice statistics"
    )
    async def tempvoice_stats(self, ctx: discord.ApplicationContext):
        """Show TempVoice statistics"""
        guild_channels = [data for data in self.active_channels.values() if data.guild_id == ctx.guild.id]
        
        embed = discord.Embed(
            title="📊 TempVoice Statistics",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Active Channels",
            value=str(len(guild_channels)),
            inline=True
        )
        
        # Count channels by owner
        owner_counts = {}
        for data in guild_channels:
            owner_counts[data.owner_id] = owner_counts.get(data.owner_id, 0) + 1
        
        if owner_counts:
            top_owners = sorted(owner_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            owner_list = []
            for owner_id, count in top_owners:
                user = ctx.guild.get_member(owner_id)
                name = user.display_name if user else "Unknown User"
                owner_list.append(f"{name}: {count}")
            
            embed.add_field(
                name="Top Channel Owners",
                value="\n".join(owner_list),
                inline=False
            )
        
        # Total members in temp channels
        total_members = 0
        for data in guild_channels:
            channel = ctx.guild.get_channel(data.channel_id)
            if channel:
                total_members += len(channel.members)
        
        embed.add_field(
            name="Total Members",
            value=str(total_members),
            inline=True
        )
        
        await ctx.respond(embed=embed)


def setup(bot):
    """Setup function for the cog"""
    bot.add_cog(TempVoiceCog(bot))