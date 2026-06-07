import json

import discord

from config.config import config as bot_config
from src.languages import lang_constants as lang_constants
from src.languages.localize import _
from src.utils.database import get_language
from src.utils.embeds import build_embeds_from_message_data, get_embed_icon
from src.utils.logger import get_cool_logger

logger = get_cool_logger(__name__)

TWITCH_MESSAGE_PATH = "src/languages/messages/twitch.json"


def _load_twitch_message() -> dict:
    try:
        with open(TWITCH_MESSAGE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Twitch message config not found: {TWITCH_MESSAGE_PATH}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse {TWITCH_MESSAGE_PATH}: {e}")

    return {
        "embed": {
            "title": "Twitch notifications unavailable",
            "description": "The Twitch message configuration could not be loaded.",
            "color": bot_config.embeds.failed_color,
        }
    }


def _twitch_replacements(ctx) -> dict:
    bot_avatar = get_embed_icon(ctx)
    return {
        "{trademark}": bot_config.bot.trademark,
        "{bot_avatar}": bot_avatar,
        "trademark": bot_config.bot.trademark,
        "bot_avatar": bot_avatar,
    }


def build_twitch_panel_embeds(ctx: discord.ApplicationContext = None) -> list[discord.Embed]:
    return build_embeds_from_message_data(
        _load_twitch_message(),
        replacements=_twitch_replacements(ctx),
        default_color=None,
        fallback={
            "title": "Twitch notifications unavailable",
            "description": "The Twitch message configuration could not be loaded.",
            "color": bot_config.embeds.failed_color,
        },
    )


def build_twitch_panel_embed(ctx: discord.ApplicationContext = None) -> discord.Embed:
    return build_twitch_panel_embeds(ctx)[0]


def _build_twitch_response_embed(
    title_key: str,
    description_key: str,
    locale: str,
    color: int,
    ctx,
    *,
    emoji: str = "",
) -> discord.Embed:
    title = _(title_key, locale)
    if emoji:
        title = f"{title} {emoji}"
    embed = discord.Embed(
        title=title,
        description=_(description_key, locale),
        color=color,
    )
    embed.set_footer(
        text=bot_config.bot.trademark,
        icon_url=get_embed_icon(ctx),
    )
    return embed


async def _get_twitch_locale(interaction) -> str:
    try:
        return await get_language(interaction.user.id)
    except Exception:
        return bot_config.bot.default_language


class TwitchPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        custom_id="subscribe_button",
        label="Subscribe",
        style=discord.ButtonStyle.success,
        emoji=lang_constants.BELL_EMOJI,
    )
    async def subscribe_button_callback(self, button, interaction):
        """Handle subscribe action - gives user the ping role."""
        await interaction.response.defer(ephemeral=True)
        lang = await _get_twitch_locale(interaction)

        try:
            # Get the ping role
            ping_role = interaction.guild.get_role(bot_config.modules.twitch.ping_role_id)

            if not ping_role:
                embed = _build_twitch_response_embed(
                    "twitch.configuration_error_title",
                    "twitch.role_not_configured",
                    lang,
                    color=bot_config.embeds.failed_color,
                    ctx=interaction,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Check if user already has the role
            if ping_role in interaction.user.roles:
                embed = _build_twitch_response_embed(
                    "twitch.already_subscribed_title",
                    "twitch.already_subscribed_description",
                    lang,
                    color=bot_config.embeds.twitch_color,
                    ctx=interaction,
                    emoji=lang_constants.BELL_EMOJI,
                )
            else:
                # Give the user the ping role
                await interaction.user.add_roles(ping_role)
                embed = _build_twitch_response_embed(
                    "twitch.subscribed_title",
                    "twitch.subscribed_description",
                    lang,
                    color=bot_config.embeds.success_color,
                    ctx=interaction,
                    emoji=lang_constants.BELL_EMOJI,
                )
                logger.info(
                    f"User {interaction.user.name} ({interaction.user.id}) subscribed to Twitch notifications"
                )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )

        except discord.Forbidden:
            logger.error(
                f"Missing permissions to manage roles for user {interaction.user.id}"
            )
            embed = _build_twitch_response_embed(
                "twitch.permission_error_title",
                "twitch.manage_roles_missing",
                lang,
                color=bot_config.embeds.failed_color,
                ctx=interaction,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in subscribe button callback: {e}")
            embed = _build_twitch_response_embed(
                "common.error",
                "twitch.unexpected_error",
                lang,
                color=bot_config.embeds.failed_color,
                ctx=interaction,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(
        custom_id="unsubscribe_button",
        label="Unsubscribe",
        style=discord.ButtonStyle.danger,
        emoji=lang_constants.MUTED_BELL_EMOJI,
    )
    async def unsubscribe_button_callback(self, button, interaction):
        """Handle unsubscribe action - removes the ping role from user."""
        await interaction.response.defer(ephemeral=True)
        lang = await _get_twitch_locale(interaction)

        try:
            # Get the ping role
            ping_role = interaction.guild.get_role(bot_config.modules.twitch.ping_role_id)

            if not ping_role:
                embed = _build_twitch_response_embed(
                    "twitch.configuration_error_title",
                    "twitch.role_not_configured",
                    lang,
                    color=bot_config.embeds.failed_color,
                    ctx=interaction,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Check if user has the role
            if ping_role not in interaction.user.roles:
                embed = _build_twitch_response_embed(
                    "twitch.not_subscribed_title",
                    "twitch.not_subscribed_description",
                    lang,
                    color=bot_config.embeds.twitch_color,
                    ctx=interaction,
                )
            else:
                # Remove the ping role from user
                await interaction.user.remove_roles(ping_role)
                embed = _build_twitch_response_embed(
                    "twitch.unsubscribed_title",
                    "twitch.unsubscribed_description",
                    lang,
                    color=bot_config.embeds.success_color,
                    ctx=interaction,
                    emoji=lang_constants.MUTED_BELL_EMOJI,
                )
                logger.info(
                    f"User {interaction.user.name} ({interaction.user.id}) unsubscribed from Twitch notifications"
                )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
                delete_after=bot_config.messages.action_confirmation_delete_delay,
            )

        except discord.Forbidden:
            logger.error(
                f"Missing permissions to manage roles for user {interaction.user.id}"
            )
            embed = _build_twitch_response_embed(
                "twitch.permission_error_title",
                "twitch.manage_roles_missing",
                lang,
                color=bot_config.embeds.failed_color,
                ctx=interaction,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in unsubscribe button callback: {e}")
            embed = _build_twitch_response_embed(
                "common.error",
                "twitch.unexpected_error",
                lang,
                color=bot_config.embeds.failed_color,
                ctx=interaction,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
