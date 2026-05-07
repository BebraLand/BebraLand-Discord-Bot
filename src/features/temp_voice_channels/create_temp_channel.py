import time
from typing import Optional

import discord

import src.languages.lang_constants as lang_constants
from config.config import config as bot_config
from src.utils.database import get_db
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


async def create_temp_channel(
    member: discord.Member, guild: discord.Guild
) -> Optional[discord.VoiceChannel]:
    """
    Create a temporary voice channel for a member.

    Args:
        member: The member who triggered the creation
        guild: The guild where the channel will be created

    Returns:
        The created voice channel or None if creation failed
    """
    try:
        category = guild.get_channel(bot_config.modules.temp_voice.category_id)
        if not category or not isinstance(category, discord.CategoryChannel):
            return None

        # Create channel name
        channel_name = f"{lang_constants.MIC_EMOJI} {member.display_name}'s Channel"

        # Get roles for permissions
        everyone_role = guild.default_role

        # Create the channel - use bot_config to control @everyone permissions
        overwrites = {
            everyone_role: discord.PermissionOverwrite(
                view_channel=bot_config.modules.temp_voice.everyone_can_see,
                connect=bot_config.modules.temp_voice.everyone_can_connect,
            ),
            member: discord.PermissionOverwrite(
                view_channel=True, connect=True, speak=True, manage_channels=True
            ),
        }

        # Handle bot_config.modules.temp_voice.default_user_role_ids (can be int or list) - always allow see and connect by default
        default_role_ids = (
            bot_config.modules.temp_voice.default_user_role_ids
            if isinstance(bot_config.modules.temp_voice.default_user_role_ids, list)
            else [bot_config.modules.temp_voice.default_user_role_ids]
        )
        for role_id in default_role_ids:
            default_user_role = guild.get_role(role_id)
            if default_user_role:
                overwrites[default_user_role] = discord.PermissionOverwrite(
                    view_channel=True, connect=True, speak=True
                )

        channel = await category.create_voice_channel(
            name=channel_name,
            overwrites=overwrites,
            user_limit=bot_config.modules.temp_voice.default_limit,
            reason=f"Temp channel created for {member}",
        )

        logger.info(
            f"{lang_constants.SUCCESS_EMOJI} Created temp voice channel {channel.name} ({channel.id}) for {member}"
        )

        # Send control panel
        from src.features.temp_voice_channels.views.TempVoiceControlView import (
            TempVoiceControlView,
        )

        embed = discord.Embed(
            title=f"{lang_constants.MIC_EMOJI} Voice Channel Control Panel",
            description=f"Welcome to your temporary voice channel, {member.mention}!\n\nUse the buttons below to control your channel.",
            color=bot_config.embeds.default_color,
        )
        embed.add_field(
            name=f"{lang_constants.LOCK_EMOJI} Lock/Unlock",
            value="Lock: Users can see but not connect\nUnlock: Users can see and connect",
            inline=False,
        )
        embed.add_field(
            name=f"{lang_constants.SUCCESS_EMOJI} Permit / {lang_constants.ERROR_EMOJI} Reject",
            value="Allow or deny specific users/roles access",
            inline=False,
        )
        embed.add_field(
            name=f"{lang_constants.GHOST_EMOJI} Ghost/Unghost",
            value="Make your channel invisible or visible",
            inline=False,
        )
        if bot_config.modules.temp_voice.invite_enabled:
            embed.add_field(
                name=f"{lang_constants.INVITE_EMOJI} Invite",
                value="Send a DM invite to a user",
                inline=False,
            )
        embed.add_field(
            name=f"{lang_constants.TRANSFER_EMOJI} Transfer",
            value="Transfer ownership to another user",
            inline=False,
        )
        embed.add_field(
            name=f"{lang_constants.GEAR_EMOJI} Settings",
            value="Change name, limit, bitrate, region, and more",
            inline=False,
        )
        embed.set_footer(
            text=bot_config.bot.trademark, icon_url=get_embed_icon(guild.me)
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
            created_at=time.time(),
        )

        return channel

    except Exception as e:
        logger.error(
            f"{lang_constants.ERROR_EMOJI} Error creating temp channel for {member} in guild {guild}: {e}"
        )
        return None
