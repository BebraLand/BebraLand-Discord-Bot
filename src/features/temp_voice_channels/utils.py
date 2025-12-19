"""
Utility functions for temporary voice channels.
"""
import discord
import time
from typing import Optional
from config import constants
from src.utils.database import get_db


async def create_temp_channel(member: discord.Member, guild: discord.Guild) -> Optional[discord.VoiceChannel]:
    """
    Create a temporary voice channel for a member.
    
    Args:
        member: The member who triggered the creation
        guild: The guild where the channel will be created
        
    Returns:
        The created voice channel or None if creation failed
    """
    try:
        category = guild.get_channel(constants.TEMP_VOICE_CHANNEL_CATEGORY_ID)
        if not category or not isinstance(category, discord.CategoryChannel):
            return None

        # Create channel name
        channel_name = f"🎙️ {member.display_name}'s Channel"

        # Get roles for permissions
        everyone_role = guild.default_role
        default_user_role = guild.get_role(constants.DEFAULT_USER_ROLE_ID)

        # Create the channel
        overwrites = {
            everyone_role: discord.PermissionOverwrite(view_channel=False, connect=False),
            member: discord.PermissionOverwrite(view_channel=True, connect=True, manage_channels=False),
        }

        if default_user_role:
            overwrites[default_user_role] = discord.PermissionOverwrite(view_channel=True, connect=True)

        channel = await category.create_voice_channel(
            name=channel_name,
            overwrites=overwrites,
            user_limit=constants.TEMP_VOICE_DEFAULT_LIMIT,
            reason=f"Temp channel created for {member}"
        )

        # Send control panel
        from src.features.temp_voice_channels.views.TempVoiceControlView import TempVoiceControlView
        
        embed = discord.Embed(
            title="🎙️ Voice Channel Control Panel",
            description=f"Welcome to your temporary voice channel, {member.mention}!\n\nUse the buttons below to control your channel.",
            color=constants.DISCORD_EMBED_COLOR
        )
        embed.add_field(
            name="🔒 Lock/Unlock",
            value="Lock: Users can see but not connect\nUnlock: Users can see and connect",
            inline=False
        )
        embed.add_field(
            name="✅ Permit / ❌ Reject",
            value="Allow or deny specific users/roles access",
            inline=False
        )
        embed.add_field(
            name="👻 Ghost/Unghost",
            value="Make your channel invisible or visible",
            inline=False
        )
        if constants.TEMP_VOICE_INVITE_ENABLED:
            embed.add_field(
                name="📨 Invite",
                value="Send a DM invite to a user",
                inline=False
            )
        embed.add_field(
            name="🔄 Transfer",
            value="Transfer ownership to another user",
            inline=False
        )
        embed.add_field(
            name="⚙️ Settings",
            value="Change name, limit, bitrate, region, and more",
            inline=False
        )
        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=constants.DISCORD_EMBED_FOOTER_ICON
        )

        view = TempVoiceControlView(channel.id, member.id)
        control_message = await channel.send(embed=embed, view=view)

        # Store in database
        storage = await get_db()
        await storage.create_temp_voice_channel(
            channel_id=channel.id,
            owner_id=member.id,
            guild_id=guild.id,
            control_message_id=control_message.id,
            created_at=time.time()
        )

        return channel

    except Exception as e:
        print(f"Error creating temp channel: {e}")
        return None


async def delete_temp_channel(channel_id: int, guild: discord.Guild, reason: str = "Channel empty"):
    """
    Delete a temporary voice channel after a delay.
    
    Args:
        channel_id: ID of the channel to delete
        guild: The guild where the channel is located
        reason: Reason for deletion
    """
    import asyncio
    
    try:
        # Wait before deleting
        await asyncio.sleep(constants.DELETE_EMPTY_TEMP_VOICE_CHANNELS_AFTER_SECONDS)

        channel = guild.get_channel(channel_id)
        if channel and isinstance(channel, discord.VoiceChannel):
            # Check if still empty
            if len(channel.members) == 0:
                # Remove from database
                storage = await get_db()
                await storage.delete_temp_voice_channel(channel_id)
                
                # Delete channel
                await channel.delete(reason=reason)

    except Exception as e:
        print(f"Error deleting temp channel: {e}")


async def transfer_ownership(channel_id: int, new_owner_id: int, guild: discord.Guild) -> bool:
    """
    Transfer ownership of a temp voice channel.
    
    Args:
        channel_id: ID of the channel
        new_owner_id: ID of the new owner
        guild: The guild where the channel is located
        
    Returns:
        True if successful, False otherwise
    """
    try:
        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            return False

        new_owner = guild.get_member(new_owner_id)
        if not new_owner:
            return False

        # Update database
        storage = await get_db()
        await storage.update_temp_voice_channel(channel_id, owner_id=new_owner_id)

        # Update permissions - give full control to new owner
        await channel.set_permissions(new_owner, view_channel=True, connect=True, manage_channels=False)

        return True

    except Exception as e:
        print(f"Error transferring ownership: {e}")
        return False


async def auto_claim_ownership(channel_id: int, guild: discord.Guild) -> Optional[int]:
    """
    Automatically transfer ownership to the next user in the channel.
    
    Args:
        channel_id: ID of the channel
        guild: The guild where the channel is located
        
    Returns:
        ID of the new owner or None if no one to transfer to
    """
    try:
        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            return None

        if len(channel.members) == 0:
            return None

        # Get first member in channel as new owner
        new_owner = channel.members[0]
        
        success = await transfer_ownership(channel_id, new_owner.id, guild)
        if success:
            # Update control panel message
            storage = await get_db()
            temp_vc = await storage.get_temp_voice_channel(channel_id)
            
            if temp_vc and temp_vc.get("control_message_id"):
                try:
                    message = await channel.fetch_message(temp_vc["control_message_id"])
                    
                    # Update view with new owner
                    from src.features.temp_voice_channels.views.TempVoiceControlView import TempVoiceControlView
                    view = TempVoiceControlView(channel_id, new_owner.id)
                    
                    # Update embed
                    embed = message.embeds[0] if message.embeds else None
                    if embed:
                        embed.description = f"Ownership transferred to {new_owner.mention}!\n\nUse the buttons below to control your channel."
                        await message.edit(embed=embed, view=view)
                except:
                    pass
            
            return new_owner.id
        
        return None

    except Exception as e:
        print(f"Error auto-claiming ownership: {e}")
        return None


async def cleanup_orphaned_channels(guild: discord.Guild):
    """
    Clean up temp voice channels that are in the database but no longer exist.
    
    Args:
        guild: The guild to clean up
    """
    try:
        storage = await get_db()
        all_temp_channels = await storage.get_all_temp_voice_channels(guild.id)
        
        for temp_vc in all_temp_channels:
            channel_id = temp_vc.get("channel_id")
            channel = guild.get_channel(channel_id)
            
            if not channel:
                # Channel doesn't exist, remove from database
                await storage.delete_temp_voice_channel(channel_id)

    except Exception as e:
        print(f"Error cleaning up orphaned channels: {e}")


async def restore_temp_channels(bot):
    """
    Restore temp voice channels from database on bot startup.
    Re-register persistent views for control panels.
    
    Args:
        bot: The Discord bot instance
    """
    try:
        from src.features.temp_voice_channels.views.TempVoiceControlView import TempVoiceControlView
        
        storage = await get_db()
        
        # Get all guilds
        for guild in bot.guilds:
            # Clean up orphaned channels first
            await cleanup_orphaned_channels(guild)
            
            # Get all temp channels for this guild
            temp_channels = await storage.get_all_temp_voice_channels(guild.id)
            
            for temp_vc in temp_channels:
                channel_id = temp_vc.get("channel_id")
                owner_id = temp_vc.get("owner_id")
                control_message_id = temp_vc.get("control_message_id")
                
                channel = guild.get_channel(channel_id)
                if channel and isinstance(channel, discord.VoiceChannel):
                    # Re-register view if control message exists
                    if control_message_id:
                        try:
                            message = await channel.fetch_message(control_message_id)
                            view = TempVoiceControlView(channel_id, owner_id)
                            bot.add_view(view, message_id=control_message_id)
                        except:
                            pass
                    
                    # Check if channel is empty and schedule deletion
                    if len(channel.members) == 0:
                        import asyncio
                        asyncio.create_task(delete_temp_channel(channel_id, guild, "Empty on startup"))

        print("✅ Restored temp voice channels")

    except Exception as e:
        print(f"❌ Error restoring temp channels: {e}")
