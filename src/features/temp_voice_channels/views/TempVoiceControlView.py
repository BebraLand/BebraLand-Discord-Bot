from typing import Optional

import discord
from discord import ui

import config.constants as constants
import src.languages.lang_constants as lang_constants
from src.languages.localize import _
from src.utils.database import get_db, get_language
from src.utils.embeds import get_embed_icon
from src.utils.logger import get_cool_logger

from .selectors.InviteUserSelect import InviteUserSelect as InviteView
from .selectors.KickUserSelect import KickUserSelect as KickView
from .selectors.PermitMentionableSelect import PermitMentionableSelect as PermitView
from .selectors.RejectMentionableSelect import RejectMentionableSelect as RejectView
from .selectors.TransferUserSelect import TransferUserSelect as TransferView

logger = get_cool_logger(__name__)


class TempVoiceControlView(ui.View):
    """Control panel for temporary voice channels."""

    def __init__(self, channel_id: int, owner_id: int):
        super().__init__(timeout=None)  # Persistent view
        self.channel_id = channel_id
        self.owner_id = owner_id
        self.custom_id = f"temp_voice_control:{channel_id}"

    async def _get_channel(
        self, interaction: discord.Interaction
    ) -> Optional[discord.VoiceChannel]:
        """Get the voice channel."""
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Channel not found!", ephemeral=True
            )
            logger.error(
                f"Channel {self.channel_id} not found in guild {interaction.guild.id}"
            )
            return None
        return channel

    async def _get_current_owner_id(self) -> int:
        """Get the current owner ID from the database."""
        try:
            storage = await get_db()
            temp_vc = await storage.get_temp_voice_channel(self.channel_id)
            if temp_vc:
                current_owner = temp_vc.get("owner_id")
                logger.debug(
                    f"Channel {self.channel_id} current owner from DB: {current_owner}"
                )
                return current_owner
            logger.warning(
                f"Channel {self.channel_id} not found in database, using fallback owner_id: {self.owner_id}"
            )
            return self.owner_id  # Fallback to stored owner_id
        except Exception as e:
            logger.error(
                f"Error getting current owner ID for channel {self.channel_id}: {e}"
            )
            return self.owner_id

    @ui.button(
        label=f"{lang_constants.LOCK_EMOJI} Lock",
        style=discord.ButtonStyle.secondary,
        custom_id="lock",
    )
    async def lock_button(self, button: ui.Button, interaction: discord.Interaction):
        current_lang = await get_language(interaction.user.id)
        """Lock the channel - DEFAULT_USER_ROLE_ID can see but not connect."""
        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', constants.DEFAULT_LANGUAGE)}",
                description=_("temp_voice.errors.only_owner_can_lock", current_lang),
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        try:
            # Handle DEFAULT_USER_ROLE_ID (can be int or list)
            default_role_ids = (
                constants.DEFAULT_USER_ROLE_ID
                if isinstance(constants.DEFAULT_USER_ROLE_ID, list)
                else [constants.DEFAULT_USER_ROLE_ID]
            )
            for role_id in default_role_ids:
                default_role = interaction.guild.get_role(role_id)
                if default_role:
                    # Get current permissions to preserve view_channel state
                    current_perms = channel.overwrites_for(default_role)
                    view_channel = (
                        current_perms.view_channel
                        if current_perms.view_channel is not None
                        else True
                    )
                    # Explicitly set all three permissions to prevent Discord from resetting them
                    await channel.set_permissions(
                        default_role,
                        view_channel=view_channel,
                        connect=False,
                        speak=True,
                    )

            embed = discord.Embed(
                title=f"{lang_constants.INFO_EMOJI} {_('common.info', constants.DEFAULT_LANGUAGE)}",
                description=f"{lang_constants.LOCK_EMOJI} {_('temp_voice.locked', current_lang)}",
                color=constants.INFO_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
        except Exception as e:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", ephemeral=True
            )

    @ui.button(
        label=f"{lang_constants.UNLOCK_EMOJI} Unlock",
        style=discord.ButtonStyle.secondary,
        custom_id="unlock",
    )
    async def unlock_button(self, button: ui.Button, interaction: discord.Interaction):
        """Unlock the channel - DEFAULT_USER_ROLE_ID can see and connect."""
        current_lang = await get_language(interaction.user.id)

        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', constants.DEFAULT_LANGUAGE)}",
                description=_("temp_voice.errors.only_owner_can_unlock", current_lang),
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        try:
            # Handle DEFAULT_USER_ROLE_ID (can be int or list)
            default_role_ids = (
                constants.DEFAULT_USER_ROLE_ID
                if isinstance(constants.DEFAULT_USER_ROLE_ID, list)
                else [constants.DEFAULT_USER_ROLE_ID]
            )
            for role_id in default_role_ids:
                default_role = interaction.guild.get_role(role_id)
                if default_role:
                    # Get current permissions to preserve view_channel state
                    current_perms = channel.overwrites_for(default_role)
                    view_channel = (
                        current_perms.view_channel
                        if current_perms.view_channel is not None
                        else True
                    )
                    # Explicitly set all three permissions to prevent Discord from resetting them
                    await channel.set_permissions(
                        default_role,
                        view_channel=view_channel,
                        connect=True,
                        speak=True,
                    )
            embed = discord.Embed(
                title=f"{lang_constants.INFO_EMOJI} {_('common.info', constants.DEFAULT_LANGUAGE)}",
                description=f"{lang_constants.UNLOCK_EMOJI} {_('temp_voice.unlocked', current_lang)}",
                color=constants.INFO_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
        except Exception as e:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", ephemeral=True
            )

    @ui.button(
        label=f"{lang_constants.SUCCESS_EMOJI} Permit",
        style=discord.ButtonStyle.success,
        custom_id="permit",
    )
    async def permit_button(self, button: ui.Button, interaction: discord.Interaction):
        """Permit a user or role to join the channel."""
        current_lang = await get_language(interaction.user.id)

        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', constants.DEFAULT_LANGUAGE)}",
                description=_("temp_voice.errors.only_owner_can_permit", current_lang),
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        message = (
            _("temp_voice.permit.select_users", current_lang)
            if not constants.TEMP_VOICE_PERMIT_ROLES_ENABLED
            else _("temp_voice.permit.select_users_roles", current_lang)
        )
        embed = discord.Embed(
            title=f"{lang_constants.INFO_EMOJI} {_('common.info', constants.DEFAULT_LANGUAGE)}",
            description=message,
            color=constants.INFO_EMBED_COLOR,
        )
        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=get_embed_icon(interaction.guild.me),
        )
        select = PermitView(channel, current_owner_id)
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True,
            delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
        )

    @ui.button(
        label=f"{lang_constants.ERROR_EMOJI} Reject",
        style=discord.ButtonStyle.danger,
        custom_id="reject",
    )
    async def reject_button(self, button: ui.Button, interaction: discord.Interaction):
        """Reject a user or role from joining the channel."""
        current_lang = await get_language(interaction.user.id)

        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
                description=_("temp_voice.errors.only_owner_can_reject", current_lang),
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        message = (
            "Select users to reject:"
            if not constants.TEMP_VOICE_REJECT_ROLES_ENABLED
            else "Select users/roles to reject:"
        )
        select = RejectView(channel, current_owner_id)
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message(message, view=view, ephemeral=True)

    @ui.button(
        label=f"{lang_constants.INVITE_EMOJI} Invite",
        style=discord.ButtonStyle.primary,
        custom_id="invite",
        row=1,
    )
    async def invite_button(self, button: ui.Button, interaction: discord.Interaction):
        """Invite a user to the channel via DM."""
        current_lang = await get_language(interaction.user.id)

        if not constants.TEMP_VOICE_INVITE_ENABLED:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
                description=_(
                    "temp_voice.errors.invite_feature_disabled", current_lang
                ),
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
            return

        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
                description=_("temp_voice.errors.only_owner_can_invite", current_lang),
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        # Show user select
        select = InviteView(channel, current_owner_id)
        view = ui.View()
        view.add_item(select)
        embed = discord.Embed(
            title=f"{lang_constants.INFO_EMOJI} {_('common.info', constants.DEFAULT_LANGUAGE)}",
            description=f"{lang_constants.INVITE_EMOJI} {_('temp_voice.select_user_to_invite', current_lang)}",
            color=constants.INFO_EMBED_COLOR,
        )
        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=get_embed_icon(interaction.guild.me),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ui.button(
        label=f"{lang_constants.KICK_EMOJI} Kick",
        style=discord.ButtonStyle.danger,
        custom_id="kick",
        row=1,
    )
    async def kick_button(self, button: ui.Button, interaction: discord.Interaction):
        """Kick a user from the channel."""
        current_lang = await get_language(interaction.user.id)

        if not constants.TEMP_VOICE_KICK_ENABLED:  # Those can be not translated
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
                description=_("temp_voice.errors.kick_feature_disabled", current_lang),
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
            return

        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', constants.DEFAULT_LANGUAGE)}",
                description=_("temp_voice.errors.only_owner_can_kick", current_lang),
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        # Show user select
        select = KickView(channel, current_owner_id)
        view = ui.View()
        view.add_item(select)
        embed = discord.Embed(
            title=f"{lang_constants.INFO_EMOJI} {_('common.info', current_lang)}",
            description=f"{lang_constants.KICK_EMOJI} {_('temp_voice.select_user_to_kick', current_lang)}",
            color=constants.INFO_EMBED_COLOR,
        )
        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=get_embed_icon(interaction.guild.me),
        )
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True,
            delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
        )

    @ui.button(
        label=f"{lang_constants.GHOST_EMOJI} Ghost",
        style=discord.ButtonStyle.secondary,
        custom_id="ghost",
        row=1,
    )
    async def ghost_button(self, button: ui.Button, interaction: discord.Interaction):
        """Make the channel invisible."""
        current_lang = await get_language(interaction.user.id)

        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
                description=_("temp_voice.errors.only_owner_can_ghost", current_lang),
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        try:
            # Handle DEFAULT_USER_ROLE_ID (can be int or list)
            default_role_ids = (
                constants.DEFAULT_USER_ROLE_ID
                if isinstance(constants.DEFAULT_USER_ROLE_ID, list)
                else [constants.DEFAULT_USER_ROLE_ID]
            )
            for role_id in default_role_ids:
                default_role = interaction.guild.get_role(role_id)
                if default_role:
                    # Get current permissions to preserve connect state
                    current_perms = channel.overwrites_for(default_role)
                    connect = (
                        current_perms.connect
                        if current_perms.connect is not None
                        else True
                    )
                    # Explicitly set all three permissions to prevent Discord from resetting them
                    await channel.set_permissions(
                        default_role, view_channel=False, connect=connect, speak=True
                    )

            embed = discord.Embed(
                title=f"{lang_constants.INFO_EMOJI} {_('common.info', current_lang)}",
                description=f"{lang_constants.GHOST_EMOJI} {_('temp_voice.ghosted', current_lang)}",
                color=constants.INFO_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
        except Exception as e:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", ephemeral=True
            )
            logger.error(f"Error ghosting channel {self.channel_id}: {e}")

    @ui.button(
        label=f"{lang_constants.EYE_EMOJI} Unghost",
        style=discord.ButtonStyle.secondary,
        custom_id="unghost",
        row=1,
    )
    async def unghost_button(self, button: ui.Button, interaction: discord.Interaction):
        """Make the channel visible."""
        current_lang = await get_language(interaction.user.id)

        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
                description=_("temp_voice.errors.only_owner_can_unghost", current_lang),
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        try:
            # Handle DEFAULT_USER_ROLE_ID (can be int or list)
            default_role_ids = (
                constants.DEFAULT_USER_ROLE_ID
                if isinstance(constants.DEFAULT_USER_ROLE_ID, list)
                else [constants.DEFAULT_USER_ROLE_ID]
            )
            for role_id in default_role_ids:
                default_role = interaction.guild.get_role(role_id)
                if default_role:
                    # Get current permissions to preserve connect state
                    current_perms = channel.overwrites_for(default_role)
                    connect = (
                        current_perms.connect
                        if current_perms.connect is not None
                        else True
                    )
                    # Explicitly set all three permissions to prevent Discord from resetting them
                    await channel.set_permissions(
                        default_role, view_channel=True, connect=connect, speak=True
                    )
            embed = discord.Embed(
                title=f"{lang_constants.INFO_EMOJI} {_('common.info', current_lang)}",
                description=f"{lang_constants.EYE_EMOJI} {_('temp_voice.visible', current_lang)}",
                color=constants.INFO_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
        except Exception as e:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Error: {str(e)}", ephemeral=True
            )
            logger.error(f"Error unghosting channel {self.channel_id}: {e}")

    @ui.button(
        label=f"{lang_constants.TRANSFER_EMOJI} Transfer",
        style=discord.ButtonStyle.secondary,
        custom_id="transfer",
        row=1,
    )
    async def transfer_button(
        self, button: ui.Button, interaction: discord.Interaction
    ):
        """Transfer ownership to another user."""
        # Get current owner ID from database first
        current_lang = await get_language(interaction.user.id)
        current_owner_id = await self._get_current_owner_id()

        # Check ownership BEFORE showing the selector
        if interaction.user.id != current_owner_id:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
                description=_(
                    "temp_voice.errors.only_owner_can_transfer", current_lang
                ),
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        current_lang = await get_language(interaction.user.id)

        # Get current owner member object
        current_owner = interaction.guild.get_member(current_owner_id)
        if not current_owner:
            await interaction.response.send_message(
                f"{lang_constants.ERROR_EMOJI} Current owner not found!", ephemeral=True
            )
            logger.error(
                f"Current owner {current_owner_id} not found in guild {interaction.guild.id}"
            )
            return

        select = TransferView(channel, current_owner_id, current_owner)
        view = ui.View()
        view.add_item(select)

        embed = discord.Embed(
            title=f"{lang_constants.INFO_EMOJI} {(_('common.info', current_lang))}",
            description=f"{lang_constants.TRANSFER_EMOJI} {_('temp_voice.select_user_to_transfer', current_lang)}",
            color=constants.INFO_EMBED_COLOR,
        )
        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=get_embed_icon(interaction.guild.me),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ui.button(
        label=f"{lang_constants.GEAR_EMOJI} Settings",
        style=discord.ButtonStyle.primary,
        custom_id="settings",
        row=2,
    )
    async def settings_button(
        self, button: ui.Button, interaction: discord.Interaction
    ):
        """Open channel settings."""
        current_lang = await get_language(interaction.user.id)
        current_owner_id = await self._get_current_owner_id()
        if interaction.user.id != current_owner_id:
            embed = discord.Embed(
                title=f"{lang_constants.ERROR_EMOJI} {_('common.error', current_lang)}",
                description=_(
                    "temp_voice.errors.only_owner_can_access_settings", current_lang
                ),
                color=constants.FAILED_EMBED_COLOR,
            )
            embed.set_footer(
                text=constants.DISCORD_MESSAGE_TRADEMARK,
                icon_url=get_embed_icon(interaction.guild.me),
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                delete_after=constants.ACTION_CONFIRMATION_MESSAGE_DELETE_DELAY,
            )
            return

        channel = await self._get_channel(interaction)
        if not channel:
            return

        # Import here to avoid circular imports
        from .settings.TempVoiceSettingsView import TempVoiceSettingsView

        embed = discord.Embed(
            title=f"{lang_constants.GEAR_EMOJI} {(_('temp_voice.channel_settings', current_lang))}",
            description=_(
                "temp_voice.configure_your_voice_channel_settings_below", current_lang
            ),
            color=constants.DISCORD_EMBED_COLOR,
        )
        embed.set_footer(
            text=constants.DISCORD_MESSAGE_TRADEMARK,
            icon_url=get_embed_icon(interaction.guild.me),
        )

        settings_view = TempVoiceSettingsView(self.channel_id, current_owner_id)
        settings_view.update_nsfw_button_style(channel)

        await interaction.response.send_message(
            embed=embed, view=settings_view, ephemeral=True
        )
        logger.info(
            f"User {interaction.user.id} opened settings for channel {self.channel_id}"
        )
