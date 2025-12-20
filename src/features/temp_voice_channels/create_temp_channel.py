import discord
import time
from src.utils.get_embed_icon import get_embed_icon
from typing import Optional
import src.languages.lang_constants as lang_constants
import config.constants as constants
from src.utils.database import get_db
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)

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
        
        # Create the channel - use constants to control @everyone permissions
        overwrites = {
            everyone_role: discord.PermissionOverwrite(
                view_channel=constants.EVERYONE_ROLE_SEE_TEMP_VOICE_CHANNELS,
                connect=constants.EVERYONE_ROLE_CONNECT_TEMP_VOICE_CHANNELS
            ),
            member: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, manage_channels=True),
        }

        # Handle DEFAULT_USER_ROLE_ID (can be int or list) - always allow see and connect by default
        default_role_ids = constants.DEFAULT_USER_ROLE_ID if isinstance(constants.DEFAULT_USER_ROLE_ID, list) else [constants.DEFAULT_USER_ROLE_ID]
        for role_id in default_role_ids:
            default_user_role = guild.get_role(role_id)
            if default_user_role:
                overwrites[default_user_role] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)

        channel = await category.create_voice_channel(
            name=channel_name,
            overwrites=overwrites,
            user_limit=constants.TEMP_VOICE_DEFAULT_LIMIT,
            reason=f"Temp channel created for {member}"
        )

        logger.info(f"{lang_constants.SUCCESS_EMOJI} Created temp voice channel {channel.name} ({channel.id}) for {member}")

        # Send control panel
        from features.temp_voice_channels.views.TempVoiceViews import TempVoiceControlView
        
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
            icon_url=get_embed_icon(guild.me)
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