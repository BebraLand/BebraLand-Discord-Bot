"""Shared function for inviting users to voice channels."""

import discord

import config.constants as constants
import src.languages.lang_constants as lang_constants
from src.languages.localize import _
from src.utils.database import get_db, get_language
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)


async def invite_user_to_channel(
    inviter: discord.Member,
    target_user: discord.Member,
    voice_channel: discord.VoiceChannel,
    inviter_lang: str,
) -> tuple[bool, discord.Embed]:
    """
    Invite a user to a voice channel.

    Args:
        inviter: The user sending the invite
        target_user: The user being invited
        voice_channel: The voice channel to invite to
        inviter_lang: Language code for the inviter

    Returns:
        tuple: (success: bool, embed: discord.Embed)
    """

    # Check if selected user is a bot
    if target_user.bot:
        embed = discord.Embed(
            title=f"{lang_constants.ERROR_EMOJI} {_('common.error', inviter_lang)}",
            description=_("temp_voice.errors.cannot_invite_bots", inviter_lang),
            color=constants.FAILED_EMBED_COLOR,
        )
        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=get_embed_icon(voice_channel.guild.me),
        )
        return False, embed

    # Check if inviting self
    if target_user == inviter:
        embed = discord.Embed(
            title=f"{lang_constants.ERROR_EMOJI} {_('common.error', inviter_lang)}",
            description=_("temp_voice.errors.cannot_invite_self", inviter_lang),
            color=constants.FAILED_EMBED_COLOR,
        )
        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=get_embed_icon(voice_channel.guild.me),
        )
        return False, embed

    # Check if user is already in the channel
    if target_user in voice_channel.members:
        embed = discord.Embed(
            title=f"{lang_constants.ERROR_EMOJI} {_('common.error', inviter_lang)}",
            description=_("temp_voice.errors.user_already_in_channel", inviter_lang),
            color=constants.FAILED_EMBED_COLOR,
        )
        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=get_embed_icon(voice_channel.guild.me),
        )
        return False, embed

    # Check if user has invites blocked
    db = await get_db()
    invites_blocked = await db.get_invite_preference(target_user.id)
    if invites_blocked:
        embed = discord.Embed(
            title=f"{lang_constants.ERROR_EMOJI} {_('common.error', inviter_lang)}",
            description=_(
                "temp_voice.errors.user_has_invites_disabled", inviter_lang
            ).format(selected_user=target_user),
            color=constants.FAILED_EMBED_COLOR,
        )
        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=get_embed_icon(voice_channel.guild.me),
        )
        return False, embed

    try:
        # Create invite
        invite = await voice_channel.create_invite(
            max_age=3600, max_uses=1, reason=f"Invited by {inviter}"
        )

        # Send DM to user
        target_lang = await get_language(target_user.id)
        dm_embed = discord.Embed(
            title=f"{lang_constants.MIC_EMOJI} {_('temp_voice.dm_invitation.voice_channel_invitation', target_lang)}",
            description=_(
                "temp_voice.dm_invitation.invitation_message", target_lang
            ).format(
                interaction=type(
                    "obj", (object,), {"user": inviter}
                )()  # Mock interaction object
            ),
            color=constants.DISCORD_EMBED_COLOR,
        )
        dm_embed.add_field(
            name=_("temp_voice.channel", target_lang),
            value=voice_channel.mention,
            inline=False,
        )
        dm_embed.add_field(
            name=_("temp_voice.invite_link", target_lang),
            value=invite.url,
            inline=False,
        )
        dm_embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=get_embed_icon(voice_channel.guild.me),
        )

        try:
            await target_user.send(embed=dm_embed)
            logger.info(
                f"User {inviter.id} sent invite for channel {voice_channel.id} to {target_user.id}"
            )

            # Success embed for inviter
            success_embed = discord.Embed(
                title=f"{lang_constants.SUCCESS_EMOJI} {_('common.success', inviter_lang)}",
                description=_("temp_voice.sent_invitation", inviter_lang).format(
                    selected_user=target_user
                ),
                color=constants.SUCCESS_EMBED_COLOR,
            )
            success_embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(voice_channel.guild.me),
            )
            return True, success_embed

        except discord.Forbidden:
            error_embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', inviter_lang)}",
                description=f"Could not send DM to {target_user.mention}. They may have DMs disabled.",
                color=constants.FAILED_EMBED_COLOR,
            )
            error_embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(voice_channel.guild.me),
            )
            return False, error_embed

    except Exception as e:
        logger.error(f"Error sending invite: {e}")
        error_embed = discord.Embed(
            title=f"{lang_constants.ERROR_EMOJI} {_('common.error', inviter_lang)}",
            description=f"Error: {str(e)}",
            color=constants.FAILED_EMBED_COLOR,
        )
        error_embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=get_embed_icon(voice_channel.guild.me),
        )
        return False, error_embed
